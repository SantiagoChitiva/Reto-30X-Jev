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
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from ..models import CONTENT, MATURITY, SEGMENTS, Answer, Guardrail, valid_action
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
        "instructions": "Qué oferta de 30X le conviene más a `person` en este momento. Solo existen estas.",
        "criteria": {
            "ai_sales": "AI Sales: vender más usando IA en prospección y seguimiento comercial.",
            "inmersion_ejecutiva": "Inmersión Ejecutiva: dueños y ejecutivos que quieren escalar, delegar, "
                                   "expandirse o transformar su negocio.",
            "sales_machine": "Sales Machine: construir un proceso comercial estructurado y un equipo de ventas.",
            "hardcore_ai": "Hardcore AI: perfiles técnicos que construyen soluciones con IA.",
            "achievers": "Achievers: red de pares y crecimiento para dueños de empresa.",
            "nutricion": "Contenido gratuito (newsletter, Free Sales Training, eventos) para quien aún no "
                         "tiene contexto o afinidad suficiente con un programa.",
            "otro": "Ninguna de las anteriores aplica.",
        },
    },
}

GUARDRAIL_QUESTIONS: dict[str, dict[str, Any]] = {
    "apropiada": {
        "type": "boolean",
        "instructions": "Un agente de 30X va a ejecutar `action` con `person`. ¿Es seguro y apropiado hacerlo? "
                        "Revisa que sea coherente con `decision` y con el perfil, que respete la línea "
                        "editorial de 30X (útil, no invasiva) y que no prometa algo que 30X no ofrece.",
        "criteria": {
            "true": "La oferta corresponde al perfil y al momento de la persona, y el tono sería bienvenido.",
            "false": "La oferta no corresponde al perfil, es prematura (por ejemplo, avisar a ventas sin "
                     "contexto) o podría sentirse como spam.",
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



# --- LLM para los casos dudosos (OpenAI) ---

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
LLM_SYSTEM_PROMPT = (
    "Eres el revisor de 30X Pulse. 30X es una escuela de negocios para dueños y líderes de empresa en "
    "Latinoamérica. Un modelo de clasificación (JEV) propuso un segmento y una acción para una persona, "
    "pero con confianza media. Revisa el caso con el perfil (categorías anónimas, null = sin dato), las "
    "señales y los eventos recientes. Confirma la propuesta o corrígela solo si el perfil lo contradice "
    "con claridad. Nunca ofrezcas algo fuera de la lista.\n"
    f"Segmentos válidos: {', '.join(SEGMENTS)}.\n"
    f"Acciones válidas: notify_sales, send:<oferta> con oferta en [{', '.join(CONTENT)}], o null.\n"
    'Responde solo con JSON: {"segment": "...", "action": "..." | null, '
    '"explanation": "2 o 3 frases en español que justifican la decisión"}.'
)

_llm_slots: Optional[asyncio.Semaphore] = None


@dataclass
class LlmReview:
    explanation: str
    segment: Optional[str]  # segmento corregido; None si se mantiene el de JEV
    action: Optional[str]   # acción corregida; solo vale si `action_changed`
    action_changed: bool
    cost_usd: float


def use_mock_llm() -> bool:
    flag = os.getenv("USE_MOCK_LLM", "").strip().lower()
    if flag:
        return flag != "false"
    return not os.getenv("OPENAI_API_KEY")


def _llm_cost(raw: dict[str, Any]) -> float:
    usage = raw.get("usage") or {}
    price_in = float(os.getenv("OPENAI_USD_PER_M_INPUT", "0.15"))
    price_out = float(os.getenv("OPENAI_USD_PER_M_OUTPUT", "0.60"))
    return (usage.get("prompt_tokens", 0) * price_in + usage.get("completion_tokens", 0) * price_out) / 1_000_000


async def _call_llm_real(state: dict[str, Any], answers: dict[str, Answer], action: Optional[str]) -> dict[str, Any]:
    """POST /v1/chat/completions de OpenAI; devuelve la respuesta cruda."""
    global _llm_slots
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("USE_MOCK_LLM=false requiere OPENAI_API_KEY en .env")
    if _llm_slots is None:
        _llm_slots = asyncio.Semaphore(int(os.getenv("MAX_CONCURRENCY", "50")))
    case = {
        "state": state,
        "jev": {k: {"value": a.value, "p": a.p} for k, a in answers.items()},
        "action_propuesta": action,
    }
    body = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": LLM_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(case, ensure_ascii=False)},
        ],
    }
    async with _llm_slots:
        for attempt in range(2):
            resp = await _http().post(OPENAI_URL, headers={"Authorization": f"Bearer {key}"}, json=body)
            if resp.status_code == 429 and attempt == 0:
                await asyncio.sleep(1.0)  # un solo reintento ante el límite de uso
                continue
            resp.raise_for_status()
            return resp.json()
    raise RuntimeError("OpenAI respondió 429 dos veces")


async def _call_llm_mock(state: dict[str, Any], answers: dict[str, Answer], action: Optional[str]) -> dict[str, Any]:
    """Misma forma que la respuesta de OpenAI: confirma la propuesta de JEV."""
    await asyncio.sleep(_mock_latency_s())
    seg = answers["segment"]
    text = f"JEV propone {seg.value} (p={seg.p:.2f}); el perfil es coherente y se mantiene la propuesta."
    content = {"segment": seg.value, "action": action, "explanation": text}
    return {"choices": [{"message": {"content": json.dumps(content, ensure_ascii=False)}}],
            "usage": {"prompt_tokens": 600, "completion_tokens": 60}}


def _fallback_review(answers: dict[str, Answer], why: str) -> LlmReview:
    seg = answers["segment"]
    text = f"El LLM no estuvo disponible ({why}); se mantiene la propuesta de JEV: {seg.value} (p={seg.p:.2f})."
    return LlmReview(explanation=text, segment=None, action=None, action_changed=False, cost_usd=0.0)


async def review_with_llm(state: dict[str, Any], answers: dict[str, Answer], action: Optional[str] = None) -> LlmReview:
    """Camino lento (0.60 ≤ p < 0.85): el LLM revisa la propuesta de JEV, la explica y puede corregirla.

    `action` es la acción que salió de la propuesta de JEV. Nunca lanza: si el LLM falla o responde
    algo inválido, se conserva la propuesta de JEV.
    """
    seg = answers["segment"]
    try:
        call = _call_llm_mock if use_mock_llm() else _call_llm_real
        raw = await call(state, answers, action)
        out = json.loads(raw["choices"][0]["message"]["content"])
        explanation = str(out["explanation"]).strip()
        if not explanation:
            raise ValueError("explicación vacía")
    except Exception as e:  # el pipeline no debe caerse por el LLM
        return _fallback_review(answers, type(e).__name__)

    cost = _llm_cost(raw)
    new_seg = out.get("segment")
    new_action = out.get("action")
    seg_changed = isinstance(new_seg, str) and new_seg in SEGMENTS and new_seg != seg.value
    # `action` ausente en el JSON = sin opinión; null = el LLM no enviaría nada
    act_changed = "action" in out and valid_action(new_action) and new_action != action
    if seg_changed:
        explanation = f"JEV propuso {seg.value} (p={seg.p:.2f}); el LLM lo corrige a {new_seg}. {explanation}"
    return LlmReview(explanation=explanation, segment=new_seg if seg_changed else None,
                     action=new_action if act_changed else None, action_changed=act_changed, cost_usd=cost)


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
    p = _rng.uniform(0.88, 0.99)
    person = state["person"]
    if state.get("action") == "notify_sales" and person.get("info_level") == "Baja" and not person.get("role"):
        p = _rng.uniform(0.3, 0.7)  # avisar a ventas sin contexto es prematuro
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
