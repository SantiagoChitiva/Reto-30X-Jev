"""Llamadas a JEV (real vía Vercel AI Gateway o simulado) y guardrail.

El JEV simulado devuelve el mismo JSON crudo que `POST /v1/evaluate`, y las dos
rutas pasan por `parse_answers`. Por eso pasar de uno a otro (USE_MOCK_JEV) no
cambia nada en el resto del sistema.
"""
import asyncio
import json
import math
import os
import random
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
# `state` llega como {person, signals, event, recent_events}; las instrucciones citan
# esos campos entre backticks, como recomienda la documentación de JEV. `person` usa las
# categorías del Excel de perfiles de 30X (null = sin dato) y `signals` se calcula en código.

QUESTIONS: dict[str, dict[str, Any]] = {
    "segment": {
        "type": "choice",
        "instructions": "Clasifica a `person` en el segmento de la audiencia de 30X que mejor la describe, "
                        "según su rol, su objetivo, su dolor y sus temas de interés. Si `role` es null, "
                        "decide con lo que sí hay; `signals` y `recent_events` muestran lo que ha hecho.",
        "criteria": {
            "fundador_ventas": "Dueño, socio o CEO (o, sin rol, alguien con contexto) cuyo foco es vender más: "
                               "objetivo de vender o de construir una máquina de ventas, o un dolor comercial "
                               "(sin proceso, vive de referidos, ventas estancadas).",
            "fundador_escala": "Dueño, socio o CEO cuyo foco es escalar la empresa: delegar, liderazgo, "
                               "expandirse a otros países, levantar capital, red de pares o claridad estratégica.",
            "lider_comercial": "Líder comercial o de ventas, o directivo no dueño responsable de vender más.",
            "ejecutivo_ia": "Dueño, directivo o gerente cuyo foco es automatizar o adoptar IA en su empresa, "
                            "sin ser un perfil técnico.",
            "perfil_tecnico": "Perfil técnico (ingeniería, datos, producto) que quiere construir con IA.",
            "explorador": "Lead que solo declaró interés o quiere formarse; todavía no hay contexto de su empresa.",
            "otro": "No hay información suficiente para ubicarla, o no es parte de la audiencia de 30X.",
        },
    },
    "maturity": {
        "type": "score",
        "instructions": "Qué tan madura está la empresa de `person` en la adopción de IA, según su objetivo, "
                        "su dolor, sus temas de interés y el programa en el que está.",
        "criteria": [
            "baja: no usa IA; el interés es aprender o tiene procesos manuales",
            "media: ya quiere automatizar procesos concretos o vender con IA",
            "alta: ya construye con IA o la usa en varias áreas del negocio",
        ],
    },
    "sales_ready": {
        "type": "boolean",
        "instructions": "¿`person` está lista para que el equipo comercial de 30X la contacte con un programa?",
        "criteria": {
            "true": "Tiene contexto claro (rol, dolor u objetivo), encaja con algún programa de 30X y muestra "
                    "interés activo (`signals`: asistió a eventos, abre correos o ya tiene un deal en proceso).",
            "false": "Solo declaró interés, no hay contexto suficiente, ya perdió la oportunidad o ya es cliente "
                     "del programa que le correspondería.",
        },
    },
    "content": {
        "type": "choice",
        "instructions": "Qué programa de 30X encaja mejor con el perfil de `person` en este momento (su "
                        "rol, su objetivo, su dolor y el tamaño de su reto). Solo existen estas opciones.",
        # Perfiles tomados de 30x.com/programas y de las páginas de cada programa
        "criteria": {
            "ai_sales": "AI Sales (Ventas): vender con IA. Para dueños o líderes comerciales que ya venden y "
                        "quieren usar IA en prospección, seguimiento y automatización comercial.",
            "inmersion_ejecutiva": "Inmersión Ejecutiva (presencial, 3 días): limitada a fundadores y C-Level que "
                                   "están escalando empresas: estrategia, contratación, cultura, capital, "
                                   "expansión y red de pares.",
            "sales_machine": "Sales Machine (Ventas): el playbook completo de ventas B2B. Para quien vende sin "
                             "proceso, vive de referidos o necesita armar su equipo y su embudo comercial.",
            "hardcore_ai": "Hardcore AI: perfiles técnicos (ingeniería, datos, producto) que construyen "
                           "agentes y soluciones de IA con código.",
            "achievers": "Achievers: acompañamiento y red de pares para dueños de empresa que buscan crecer "
                         "con otros que enfrentan los mismos retos.",
            "nutricion": "Contenido gratuito (clases gratis, Free Sales Training, newsletter) para quien aún no "
                         "tiene contexto suficiente o no encaja todavía con un programa.",
            "otro": "Ninguna de las anteriores aplica.",
        },
    },
}

GUARDRAIL_QUESTIONS: dict[str, dict[str, Any]] = {
    "apropiada": {
        "type": "boolean",
        "instructions": "El equipo comercial de 30X va a contactar a `person` porque `decision` dice que está "
                        "lista para ventas. ¿Es apropiado contactarla ahora?",
        "criteria": {
            "true": "El perfil y las señales muestran interés real y un programa de 30X que le encaja: una "
                    "llamada de ventas sería bienvenida.",
            "false": "Es prematuro o invasivo: el interés es solo exploratorio, ya es cliente del programa, "
                     "perdió la oportunidad hace poco o el perfil no encaja con lo que 30X vende.",
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


RETRIES = 3
_RETRY_STATUS = {429, 500, 502, 503, 504}


async def _call_jev_real(state: dict[str, Any], questions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """POST /v1/evaluate de Vercel AI Gateway con el modelo typesafe-ai/jev."""
    key = os.getenv("AI_GATEWAY_API_KEY")
    if not key:
        raise RuntimeError("USE_MOCK_JEV=false requiere AI_GATEWAY_API_KEY en .env")
    body = {"model": MODEL, "state": state, "questions": questions}
    for attempt in range(RETRIES + 1):
        try:
            resp = await _http().post(GATEWAY_URL, headers={"Authorization": f"Bearer {key}"}, json=body)
        except httpx.TransportError:  # timeout o conexión cortada
            if attempt == RETRIES:
                raise
        else:
            if resp.status_code not in _RETRY_STATUS or attempt == RETRIES:
                break
        # Límite de uso o falla temporal: espera y reintenta (0,5 s, 1 s, 2 s)
        await asyncio.sleep(0.5 * 2 ** attempt)
    if resp.status_code >= 400:
        try:
            reason = resp.json()["error"]["message"]
        except Exception:
            reason = resp.text[:300]
        raise RuntimeError(f"JEV respondió {resp.status_code}: {reason}")
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
    """Segunda revisión de JEV antes de avisar a ventas en la ruta `auto`.

    Frena si JEV se inclina por «no apropiado» (p < GUARDRAIL_MIN). Las acciones de bajo riesgo
    (enviar contenido) no pasan por aquí: las cubren las reglas del harness.
    """
    g_state = {**state, "decision": {k: a.value for k, a in answers.items()}, "action": action}
    raw = await _evaluate(g_state, GUARDRAIL_QUESTIONS)
    p = round(float(raw["answers"]["apropiada"]["probability"]), 4)
    passed = p >= policy.GUARDRAIL_MIN
    reason = None if passed else f"JEV no confirma que `{action}` sea apropiada para esta persona (p={p:.2f})"
    return Guardrail(passed=passed, p=p, reason=reason), cost_of(raw)



# --- JEV simulado ---
# Heurística sencilla sobre las categorías del perfil. No intenta acertar como JEV
# (a propósito se equivoca a veces, más cuando duda): sirve para desarrollar y hacer
# la demo con respuestas de la misma forma.

_rng = random.Random()

_SALES = {"Vender más", "Construir una máquina de ventas"}
_SALES_PAINS = {"No tiene proceso comercial estructurado", "Vive de referidos y prospecta a mano",
                "Ventas estancadas o cayendo"}
_SCALE = {"Delegar y pasar a un rol estratégico", "Desarrollar liderazgo y equipo", "Expandirse a otros países",
          "Levantar capital", "Entrar a una red de pares", "Transformar el modelo de negocio"}
_ACTIVE_STAGES = {"Registrado", "Contactado", "Potencial", "Calificado", "En gestión"}


def _guess_segment(person: dict[str, Any]) -> tuple[str, float]:
    """(segmento, qué tan clara es la señal, de 0 a 1)."""
    role, objective, pain = person.get("role") or "", person.get("objective"), person.get("pain")
    interests = set(person.get("interests") or [])
    sales = objective in _SALES or pain in _SALES_PAINS
    if not role and not objective and not interests:
        return "otro", 0.93
    if "técnico" in role or person.get("program") == "AI for devs":
        return "perfil_tecnico", 0.95
    if "comercial" in role:
        return "lider_comercial", 0.96
    if "Fundador" in role:
        if sales:
            return "fundador_ventas", 0.95
        if objective in _SCALE or pain:
            return "fundador_escala", 0.93
        return "ejecutivo_ia", 0.9
    if role:  # director, VP o gerente
        return ("lider_comercial", 0.78) if sales else ("ejecutivo_ia", 0.9)
    if person.get("info_available") != "Perfil con contexto (dolor u objetivo)":
        return "explorador", 0.94 if interests else 0.5
    # Sin rol pero con contexto: se adivina por el objetivo, con menos seguridad
    clarity = {"Alta": 0.88, "Media": 0.82}.get(person.get("info_level"), 0.74)
    if sales:
        return "fundador_ventas", clarity
    if objective in _SCALE:
        return "fundador_escala", clarity
    if objective == "Automatizar con IA":
        return "ejecutivo_ia", clarity
    return "explorador", clarity


def _guess_maturity(person: dict[str, Any], segment: str) -> int:
    interests = set(person.get("interests") or [])
    if segment == "perfil_tecnico" or person.get("program") in ("AI for devs", "AI Second Brain"):
        return 2
    if person.get("pain") == "Procesos manuales y rezago tecnológico":
        return 0
    if person.get("objective") == "Automatizar con IA":
        return 1
    return 1 if "ai" in interests else 0


def _guess_sales_ready(person: dict[str, Any], signals: dict[str, Any], segment: str) -> bool:
    if segment in ("explorador", "otro") or person.get("crm_status") in ("Oportunidad perdida", "Cliente (pagó)"):
        return False
    active_deal = person.get("crm_stage") in _ACTIVE_STAGES
    engaged = signals.get("events_attended", 0) + signals.get("emails_opened", 0) >= 2
    return active_deal or (person.get("info_level") != "Baja" and engaged)


def _guess_content(person: dict[str, Any], segment: str) -> str:
    interests = set(person.get("interests") or [])
    if person.get("info_level") == "Baja" and segment in ("explorador", "ejecutivo_ia") and len(interests) < 2:
        return "nutricion"
    if person.get("objective") == "Entrar a una red de pares":
        return "achievers"
    return {
        "fundador_ventas": "ai_sales" if "ai" in interests else "sales_machine",
        "lider_comercial": "ai_sales" if "ai" in interests else "sales_machine",
        "fundador_escala": "inmersion_ejecutiva",
        "ejecutivo_ia": "ai_sales" if "sales" in interests else "inmersion_ejecutiva",
        "perfil_tecnico": "hardcore_ai",
        "explorador": "nutricion",
    }.get(segment, "otro")


def _clarity(base: float, rng: random.Random) -> float:
    """Seguridad simulada alrededor de `base`, para que haya casos en las tres rutas."""
    return max(0.35, min(0.99, rng.gauss(base, 0.06)))


def _maybe_wrong(options: list[str], chosen: str, p: float, rng: random.Random) -> str:
    """Cuando duda, a veces se equivoca (como puede pasarle a un modelo real)."""
    if rng.random() < (1 - p) * 0.8:
        return rng.choice([o for o in options if o != chosen])
    return chosen


def _spread(options: list[str], chosen: str, p: float, rng: random.Random = _rng) -> dict[str, float]:
    """Probabilidades por opción: `chosen` recibe p y el resto se reparte sin superarla."""
    others = [o for o in options if o != chosen]
    weights = [1 + rng.random() * 0.5 for _ in others]
    total = sum(weights)
    probs = {o: round((1 - p) * w / total, 2) for o, w in zip(others, weights)}
    probs[chosen] = round(p, 2)
    return {o: probs[o] for o in options}


def _mock_main_answers(state: dict[str, Any]) -> dict[str, Any]:
    person, signals = state["person"], state.get("signals", {})
    # Mismo perfil → misma respuesta, como un modelo real: solo cambia cuando cambia el perfil
    profile = {k: v for k, v in person.items() if k != "person_id"}
    rng = random.Random(json.dumps(profile, sort_keys=True, ensure_ascii=False))
    segment, base = _guess_segment(person)
    clarity = _clarity(base, rng)
    segment = _maybe_wrong(SEGMENTS, segment, clarity, rng)
    maturity = _guess_maturity(person, segment)
    sales = _guess_sales_ready(person, signals, segment)
    content_p = _clarity(base, rng)
    content = _maybe_wrong(CONTENT, _guess_content(person, segment), content_p, rng)

    sales_p = max(0.51, min(0.99, clarity + rng.uniform(-0.02, 0.04)))
    maturity_probs = _spread([str(i) for i in range(len(MATURITY))], str(maturity), rng.uniform(0.55, 0.97), rng)
    return {
        "segment": {"type": "choice", "choice": segment,
                    "probabilities": _spread(SEGMENTS, segment, clarity, rng)},
        "maturity": {
            "type": "score",
            "score": round(sum(int(k) * v for k, v in maturity_probs.items()), 2),
            "probabilities": maturity_probs,
        },
        "sales_ready": {"type": "boolean", "probability": round(sales_p if sales else 1 - sales_p, 2)},
        "content": {"type": "choice", "choice": content,
                    "probabilities": _spread(CONTENT, content, content_p, rng)},
    }


def _mock_guardrail_answer(state: dict[str, Any]) -> dict[str, Any]:
    # Como JEV real: el guardrail rara vez pasa de 0.75 y a veces se inclina por «no»
    p = _rng.uniform(0.35, 0.8)
    if state["signals"].get("events_attended", 0) == 0 and state["signals"].get("emails_opened", 0) == 0:
        p -= 0.1  # sin señales de interés, contactar es más prematuro
    return {"type": "boolean", "probability": round(max(0.05, p), 2)}


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
