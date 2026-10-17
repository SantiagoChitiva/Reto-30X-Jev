import asyncio

from app.decision import jev

# Respuesta con la forma de POST /v1/evaluate (documentación de Vercel AI Gateway)
RAW = {
    "model": "typesafe-ai/jev",
    "answers": {
        "segment": {"type": "choice", "choice": "fundador_ventas",
                    "probabilities": {"fundador_ventas": 0.91, "fundador_escala": 0.03, "lider_comercial": 0.02,
                                      "ejecutivo_ia": 0.01, "perfil_tecnico": 0.01, "explorador": 0.01,
                                      "otro": 0.01}},
        "maturity": {"type": "score", "score": 1.8, "probabilities": {"0": 0.04, "1": 0.14, "2": 0.82}},
        "sales_ready": {"type": "boolean", "probability": 0.88},
        "content": {"type": "choice", "choice": "ai_sales",
                    "probabilities": {"ai_sales": 0.79, "inmersion_ejecutiva": 0.05, "sales_machine": 0.1,
                                      "hardcore_ai": 0.01, "achievers": 0.02, "nutricion": 0.02, "otro": 0.01}},
    },
    "usage": {"inputTokens": 500, "outputTokens": 20},
    "providerMetadata": {"gateway": {"cost": "0.00002100"}},
}

STATE = {
    "person": {"person_id": "p_0001", "relation": "Deal en el CRM", "role": "Fundador, socio o CEO",
               "objective": "Vender más", "interests": ["sales", "ai"], "info_level": "Alta"},
    "signals": {"events_attended": 3, "emails_opened": 1},
    "event": {"type": "attendance", "timestamp": "2026-10-17T15:04:05+00:00", "data": {}},
    "recent_events": [],
}


def test_parse_answers():
    a = jev.parse_answers(RAW, jev.QUESTIONS)
    assert (a["segment"].value, a["segment"].p) == ("fundador_ventas", 0.91)
    assert (a["maturity"].value, a["maturity"].p) == ("alta", 0.82)
    assert (a["sales_ready"].value, a["sales_ready"].p) == (True, 0.88)
    assert (a["content"].value, a["content"].p) == ("ai_sales", 0.79)
    assert jev.cost_of(RAW) == 0.000021


def test_boolean_no_usa_la_probabilidad_del_valor_elegido():
    raw = {"answers": {"sales_ready": {"type": "boolean", "probability": 0.01}}}
    a = jev.parse_answers(raw, {"sales_ready": jev.QUESTIONS["sales_ready"]})
    assert (a["sales_ready"].value, a["sales_ready"].p) == (False, 0.99)


def test_mock_tiene_la_misma_forma_que_jev_real(monkeypatch):
    monkeypatch.setattr(jev, "_mock_latency_s", lambda: 0)
    raw = asyncio.run(jev._call_jev_mock(STATE, jev.QUESTIONS))
    assert set(raw) == set(RAW)
    assert set(raw["answers"]) == set(jev.QUESTIONS)
    for key, question in jev.QUESTIONS.items():
        assert raw["answers"][key]["type"] == question["type"]
    for key in ("segment", "maturity", "content"):
        assert abs(sum(raw["answers"][key]["probabilities"].values()) - 1) < 0.05
    assert jev.cost_of(raw) > 0
    jev.parse_answers(raw, jev.QUESTIONS)  # no falla


def test_mock_reconoce_perfiles():
    def seg(**p):
        return jev._guess_segment(p)[0]

    assert seg(role="Fundador, socio o CEO", objective="Vender más") == "fundador_ventas"
    assert seg(role="Fundador, socio o CEO", objective="Levantar capital") == "fundador_escala"
    assert seg(role="Líder comercial o de ventas") == "lider_comercial"
    assert seg(role="Gerente o jefe de área", objective="Automatizar con IA") == "ejecutivo_ia"
    assert seg(role="Perfil técnico (ingeniería, datos, producto)") == "perfil_tecnico"
    assert seg(interests=["ai"], info_available="Solo interés declarado") == "explorador"
    assert seg(info_available="Sin información") == "otro"


def test_mock_solo_ofrece_programas_de_30x():
    from app.models import CONTENT

    for segment in jev.QUESTIONS["segment"]["criteria"]:
        assert jev._guess_content({"interests": ["ai", "sales"], "info_level": "Alta"}, segment) in CONTENT
