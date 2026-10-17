import asyncio
import json

from app.decision import jev
from app.models import Answer

ANSWERS = {
    "segment": Answer(value="explorador", p=0.71),
    "maturity": Answer(value="media", p=0.7),
    "sales_ready": Answer(value=False, p=0.75),
    "content": Answer(value="intro_ia", p=0.8),
}
STATE = {"person": {"role": "Consultor independiente"}, "event": {}, "recent_events": []}


def fake_llm(monkeypatch, content, usage=None):
    async def call(state, answers, action):
        return {"choices": [{"message": {"content": json.dumps(content)}}],
                "usage": usage or {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}}

    monkeypatch.setattr(jev, "_call_llm_real", call)
    monkeypatch.setenv("USE_MOCK_LLM", "false")


def review(action="send:intro_ia"):
    return asyncio.run(jev.review_with_llm(STATE, ANSWERS, action))


def test_el_llm_corrige_segmento_y_accion(monkeypatch):
    fake_llm(monkeypatch, {"segment": "lider_tecnico", "action": "send:taller_practico", "explanation": "Dirige TI."})
    r = review()
    assert r.segment == "lider_tecnico"
    assert r.action_changed and r.action == "send:taller_practico"
    assert r.explanation.startswith("JEV propuso explorador (p=0.71); el LLM lo corrige a lider_tecnico.")
    assert abs(r.cost_usd - 0.75) < 1e-9  # 1M tokens de entrada (0.15) + 1M de salida (0.60)


def test_el_llm_confirma(monkeypatch):
    fake_llm(monkeypatch, {"segment": "explorador", "action": "send:intro_ia", "explanation": "Coherente."})
    r = review()
    assert r.segment is None and not r.action_changed and r.explanation == "Coherente."


def test_el_llm_puede_quitar_la_accion(monkeypatch):
    fake_llm(monkeypatch, {"segment": "explorador", "action": None, "explanation": "Es prematuro."})
    r = review()
    assert r.action_changed and r.action is None


def test_correccion_invalida_se_ignora(monkeypatch):
    fake_llm(monkeypatch, {"segment": "inventado", "action": "send:nada", "explanation": "Texto."})
    r = review()
    assert r.segment is None and not r.action_changed and r.explanation == "Texto."


def test_error_del_llm_conserva_a_jev(monkeypatch):
    async def boom(state, answers, action):
        raise RuntimeError("sin red")

    monkeypatch.setattr(jev, "_call_llm_real", boom)
    monkeypatch.setenv("USE_MOCK_LLM", "false")
    r = review()
    assert r.segment is None and not r.action_changed and r.cost_usd == 0
    assert "no estuvo disponible" in r.explanation


def test_json_invalido_conserva_a_jev(monkeypatch):
    async def basura(state, answers, action):
        return {"choices": [{"message": {"content": "no es json"}}]}

    monkeypatch.setattr(jev, "_call_llm_real", basura)
    monkeypatch.setenv("USE_MOCK_LLM", "false")
    assert "no estuvo disponible" in review().explanation


def test_mock_confirma_y_tiene_costo():
    r = review()  # conftest fuerza USE_MOCK_LLM=true
    assert r.segment is None and not r.action_changed
    assert "TODO" not in r.explanation and r.cost_usd > 0


def test_mock_por_defecto_sin_clave(monkeypatch):
    monkeypatch.delenv("USE_MOCK_LLM")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert jev.use_mock_llm()
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    assert not jev.use_mock_llm()


def test_pipeline_aplica_la_correccion_del_llm(client, monkeypatch):
    from app.decision import policy

    monkeypatch.setattr(policy, "route", lambda segment, sales_ready: "llm")
    fake_llm(monkeypatch, {"segment": "lider_tecnico", "action": "notify_sales", "explanation": "Dirige TI."})
    body = {"person_id": "p_0001", "type": "signup", "data": {},
            "person": {"person_id": "p_0001", "name": "Ana", "role": "Analista de datos", "company": "Acme",
                       "industry": "banca", "company_size": "1000+", "events_attended": 1}}
    d = client.post("/events", json=body).json()
    assert d["route"] == "llm"
    assert d["segment"]["value"] == "lider_tecnico" and d["action"] == "notify_sales"
    assert "el LLM lo corrige a lider_tecnico" in d["explanation"]
    assert client.get("/people/p_0001").json()["history"][0]["segment"] == "lider_tecnico"
