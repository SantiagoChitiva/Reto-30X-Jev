"""Llamadas a JEV (real vía Vercel AI Gateway o simulado), guardrail y LLM.

El JEV simulado devuelve el mismo JSON crudo que `POST /v1/evaluate`, y las dos
rutas pasan por `parse_answers`. Por eso pasar de uno a otro (USE_MOCK_JEV) no
cambia nada en el resto del sistema.
"""
import asyncio
import json
import math
import os
import random
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from ..models import CONTENT, MATURITY, SEGMENTS, Answer, Guardrail
from . import policy

GATEWAY_URL = "https://ai-gateway.vercel.sh/v1/evaluate"
MODEL = "typesafe-ai/jev"
USD_PER_INPUT_TOKEN = 0.042 / 1_000_000  # JEV cobra solo la entrada


def use_mock() -> bool:
    return os.getenv("USE_MOCK_JEV", "true").strip().lower() != "false"


# --- Preguntas tipadas (CONTRACTS.md) ---
# `state` llega como {person, event, recent_events}; las instrucciones citan
# esos campos entre backticks, como recomienda la documentación de JEV.

QUESTIONS: dict[str, dict[str, Any]] = {
    "segment": {
        "type": "choice",
        "instructions": "Clasifica a `person` en el segmento que mejor la describe según su cargo, "
                        "su empresa y lo que ha hecho (`event`, `recent_events`).",
        "criteria": {
            "explorador": "Curiosa por la IA, sin equipo a cargo ni poder de decisión; está dando sus primeros pasos.",
            "lider_negocio": "Dirige un área de negocio (comercial, marketing, operaciones, finanzas, personas) "
                             "y evalúa la IA por su impacto en el negocio.",
            "lider_tecnico": "Dirige tecnología, ingeniería o arquitectura (CTO, gerente de TI, head of engineering) "
                             "y decide sobre herramientas.",
            "equipo_adopcion": "Trabaja en el equipo que implementa IA (analista, ingeniero, científico de datos) "
                               "sin poder de compra.",
            "lider_adopcion": "Es responsable de la estrategia o la adopción de IA en su organización "
                              "(Head of AI, Chief Data Officer, transformación digital, innovación).",
            "otro": "No encaja en ningún segmento (estudiante, proveedor o perfil sin información suficiente).",
        },
    },
    "maturity": {
        "type": "score",
        "instructions": "Qué tan madura es la organización de `person` en el uso de IA.",
        "criteria": [
            "baja: no usa IA o solo hay pruebas individuales",
            "media: tiene pilotos o casos de uso en algunas áreas",
            "alta: la IA está en producción, con estrategia y equipo dedicados",
        ],
    },
    "sales_ready": {
        "type": "boolean",
        "instructions": "¿`person` está lista para que el equipo de ventas la contacte con una oferta?",
        "criteria": {
            "true": "Decide o influye en compras, su empresa tiene más de 50 personas y muestra interés "
                    "repetido (varios eventos, o llegó a un cargo de liderazgo en IA).",
            "false": "No decide compras, su empresa es muy pequeña o su interés todavía es inicial.",
        },
    },
    "content": {
        "type": "choice",
        "instructions": "Qué contenido le sirve más a `person` en este momento.",
        "criteria": {
            "intro_ia": "Introducción a la IA para quien está empezando.",
            "caso_de_exito": "Casos de éxito de empresas parecidas, para líderes que evalúan invertir.",
            "taller_practico": "Taller práctico para equipos que implementan.",
            "programa_ejecutivo": "Programa ejecutivo para líderes de organizaciones maduras.",
            "otro": "Ninguno de los anteriores aplica.",
        },
    },
}

GUARDRAIL_QUESTIONS: dict[str, dict[str, Any]] = {
    "apropiada": {
        "type": "boolean",
        "instructions": "¿Es apropiado ejecutar `action` con `person` en este momento? Revisa que sea "
                        "coherente con `decision`, con su cargo y con su empresa, y que no resulte invasiva.",
        "criteria": {
            "true": "La acción es coherente con el perfil y el momento de la persona.",
            "false": "La acción no corresponde al perfil, es prematura o podría molestar a la persona.",
        },
    },
}


@dataclass
class JevResult:
    answers: dict[str, Answer]  # segment, maturity, sales_ready, content
    cost_usd: float


# --- Lectura de la respuesta (igual para real y simulado) ---

def parse_answers(raw: dict[str, Any], questions: dict[str, dict[str, Any]]) -> dict[str, Answer]:
    """Convierte `answers` de /v1/evaluate en {value, p} por pregunta.

    - choice: la opción elegida y su probabilidad.
    - score: el nivel más probable (etiqueta antes de ":" en `criteria`) y su probabilidad.
    - boolean: sí/no según probability ≥ 0.5; `p` es la probabilidad del valor elegido.
    """
    out: dict[str, Answer] = {}
    for key, question in questions.items():
        ans = raw["answers"][key]
        kind = ans.get("type", question["type"])
        if kind == "choice":
            out[key] = Answer(value=ans["choice"], p=float(ans["probabilities"][ans["choice"]]))
        elif kind == "score":
            labels = [c.split(":", 1)[0].strip() for c in question["criteria"]]
            idx, p = max(((int(i), float(v)) for i, v in ans["probabilities"].items()), key=lambda t: t[1])
            out[key] = Answer(value=labels[idx], p=p)
        elif kind in ("boolean", "noul"):
            prob = float(ans["probability"])
            value = prob >= 0.5
            out[key] = Answer(value=value, p=round(prob if value else 1 - prob, 4))
        else:
            raise ValueError(f"Tipo de respuesta de JEV desconocido: {kind}")
    return out


def cost_of(raw: dict[str, Any]) -> float:
    try:
        return float(raw["providerMetadata"]["gateway"]["cost"])
    except (KeyError, TypeError, ValueError):
        return 0.0


# --- JEV real ---

_client: Optional[httpx.AsyncClient] = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        n = int(os.getenv("MAX_CONCURRENCY", "50"))
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),
            limits=httpx.Limits(max_connections=n, max_keepalive_connections=n),
        )
    return _client


async def aclose() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def _call_jev_real(state: dict[str, Any], questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """POST /v1/evaluate de Vercel AI Gateway con el modelo typesafe-ai/jev."""
    key = os.getenv("AI_GATEWAY_API_KEY")
    if not key:
        raise RuntimeError("USE_MOCK_JEV=false requiere AI_GATEWAY_API_KEY en .env")
    resp = await _http().post(
        GATEWAY_URL,
        headers={"Authorization": f"Bearer {key}"},
        json={"model": MODEL, "state": state, "questions": questions},
    )
    resp.raise_for_status()
    return resp.json()


async def _evaluate(state: dict[str, Any], questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if use_mock():
        return await _call_jev_mock(state, questions)
    return await _call_jev_real(state, questions)


# --- Lo que usa el pipeline ---

async def ask(state: dict[str, Any]) -> JevResult:
    """Las 4 preguntas tipadas en una sola llamada."""
    raw = await _evaluate(state, QUESTIONS)
    return JevResult(answers=parse_answers(raw, QUESTIONS), cost_usd=cost_of(raw))


async def guardrail(state: dict[str, Any], answers: dict[str, Answer], action: str) -> tuple[Guardrail, float]:
    """Segunda revisión de JEV antes de actuar en la ruta `auto`."""
    g_state = {**state, "decision": {k: a.value for k, a in answers.items()}, "action": action}
    raw = await _evaluate(g_state, GUARDRAIL_QUESTIONS)
    p = round(float(raw["answers"]["apropiada"]["probability"]), 4)
    passed = p >= policy.GUARDRAIL_MIN
    reason = None if passed else f"JEV no confirma que `{action}` sea apropiada para esta persona (p={p:.2f})"
    return Guardrail(passed=passed, p=p, reason=reason), cost_of(raw)


async def review_with_llm(state: dict[str, Any], answers: dict[str, Answer]) -> tuple[str, float]:
    """Camino lento (0.60 ≤ p < 0.85): el LLM revisa el caso y explica la decisión.

    Devuelve (explicación, costo_usd).

    TODO(Persona 2): conectar el LLM real (Claude u otro). Hoy devuelve un texto
    de relleno con costo 0, así que la latencia y el costo de esta ruta no son reales.
    """
    seg, sales = answers["segment"], answers["sales_ready"]
    explanation = (
        f"[TODO LLM] Caso pendiente de revisión por el LLM. JEV propone segmento "
        f"{seg.value} (p={seg.p:.2f}) y sales_ready={sales.value} (p={sales.p:.2f})."
    )
    return explanation, 0.0


# --- JEV simulado ---
# Heurística sencilla sobre cargo, empresa e historial. No intenta acertar como
# JEV: sirve para desarrollar y hacer la demo con respuestas de la misma forma.

_rng = random.Random()
_SIZES = ["1-10", "11-50", "51-200", "201-1000", "1000+"]
_MATURE_INDUSTRIES = {"banca", "fintech", "tecnologia", "telecomunicaciones", "seguros"}

# El primer patrón que coincide gana, así que el orden importa.
_SEGMENT_PATTERNS = [
    ("otro", r"\b(estudiante|proveedor|freelance)\b"),
    ("lider_adopcion", r"\b(head of ai|chief (ai|data)|transformacion digital|lider de ia|director de ia|innovacion)\b"),
    ("lider_tecnico", r"\b(cto|cio|tecnologia|arquitect\w*|gerente de ti|head of engineering|lider tecnico)\b"),
    ("lider_negocio", r"\b(gerente|director|directora|cfo|ceo|coo|vp|jefe|jefa)\b"),
    ("equipo_adopcion", r"\b(analista|ingenier\w*|cientific\w*|desarroll\w*|data|machine learning)\b"),
    ("explorador", r"\b(coordinador\w*|asistente|especialista|profesional|ejecutiv\w*|practicante)\b"),
]


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _guess_segment(role: str) -> tuple[str, bool]:
    """(segmento, ¿el cargo es claro?). Un cargo sin patrón se vuelve un explorador dudoso."""
    r = _norm(role)
    for segment, pattern in _SEGMENT_PATTERNS:
        if re.search(pattern, r):
            return segment, True
    return "explorador", False


def _guess_maturity(person: dict[str, Any], segment: str) -> int:
    score = _SIZES.index(person["company_size"]) * 0.45
    if _norm(person["industry"]) in _MATURE_INDUSTRIES:
        score += 0.6
    if segment == "lider_adopcion":
        score += 0.6
    score += min(person.get("events_attended", 0), 4) * 0.15
    return 0 if score < 1.0 else 1 if score < 2.0 else 2


def _guess_sales_ready(person: dict[str, Any], segment: str, maturity: int) -> bool:
    leader = segment in ("lider_negocio", "lider_tecnico", "lider_adopcion")
    big = _SIZES.index(person["company_size"]) >= 2
    interested = person.get("events_attended", 0) >= 2 or maturity == 2
    return leader and big and interested


def _guess_content(segment: str, maturity: int) -> str:
    return {
        "explorador": "intro_ia",
        "equipo_adopcion": "taller_practico",
        "lider_negocio": "caso_de_exito",
        "lider_tecnico": "caso_de_exito" if maturity == 2 else "taller_practico",
        "lider_adopcion": "programa_ejecutivo" if maturity == 2 else "caso_de_exito",
    }.get(segment, "otro")


def _clarity(clear_role: bool) -> float:
    """Seguridad simulada. Con cargos claros da ~74% auto, ~18% llm y ~8% humano."""
    r = _rng.random()
    auto_share, llm_share = (0.74, 0.92) if clear_role else (0.25, 0.70)
    if r < auto_share:
        return _rng.uniform(0.86, 0.99)
    if r < llm_share:
        return _rng.uniform(0.61, 0.84)
    return _rng.uniform(0.35, 0.59)


def _spread(options: list[str], chosen: str, p: float) -> dict[str, float]:
    """Probabilidades por opción: `chosen` recibe p y el resto se reparte sin superarla."""
    others = [o for o in options if o != chosen]
    weights = [1 + _rng.random() * 0.5 for _ in others]
    total = sum(weights)
    probs = {o: round((1 - p) * w / total, 2) for o, w in zip(others, weights)}
    probs[chosen] = round(p, 2)
    return {o: probs[o] for o in options}


def _mock_main_answers(state: dict[str, Any]) -> dict[str, Any]:
    person = state["person"]
    segment, clear_role = _guess_segment(person["role"])
    maturity = _guess_maturity(person, segment)
    sales = _guess_sales_ready(person, segment, maturity)
    content = _guess_content(segment, maturity)

    clarity = _clarity(clear_role)
    sales_p = max(0.51, min(0.99, clarity + _rng.uniform(0.0, 0.05)))
    maturity_probs = _spread([str(i) for i in range(len(MATURITY))], str(maturity), _rng.uniform(0.55, 0.97))
    return {
        "segment": {"type": "choice", "choice": segment, "probabilities": _spread(SEGMENTS, segment, clarity)},
        "maturity": {
            "type": "score",
            "score": round(sum(int(k) * v for k, v in maturity_probs.items()), 2),
            "probabilities": maturity_probs,
        },
        "sales_ready": {"type": "boolean", "probability": round(sales_p if sales else 1 - sales_p, 2)},
        "content": {"type": "choice", "choice": content,
                    "probabilities": _spread(CONTENT, content, _rng.uniform(0.6, 0.97))},
    }


def _mock_guardrail_answer(state: dict[str, Any]) -> dict[str, Any]:
    p = _rng.uniform(0.88, 0.99)
    if state.get("action") == "notify_sales" and state["person"]["company_size"] in ("1-10", "11-50"):
        p = _rng.uniform(0.3, 0.7)
    elif _rng.random() < 0.004:
        p = _rng.uniform(0.5, 0.84)
    return {"type": "boolean", "probability": round(p, 2)}


def _mock_latency_s() -> float:
    """Latencia simulada por llamada: mediana ~90 ms, entre 50 y 500 ms."""
    return min(0.5, max(0.05, _rng.lognormvariate(math.log(0.09), 0.45)))


async def _call_jev_mock(state: dict[str, Any], questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Mismo JSON que /v1/evaluate, con latencia y costo simulados."""
    await asyncio.sleep(_mock_latency_s())
    if "apropiada" in questions:
        answers = {"apropiada": _mock_guardrail_answer(state)}
    else:
        answers = {k: v for k, v in _mock_main_answers(state).items() if k in questions}
    tokens = len(json.dumps({"state": state, "questions": questions}, ensure_ascii=False)) // 4
    return {
        "model": MODEL,
        "answers": answers,
        "usage": {"inputTokens": tokens, "outputTokens": 5 * len(answers)},
        "providerMetadata": {"gateway": {"cost": f"{tokens * USD_PER_INPUT_TOKEN:.8f}"}},
    }
