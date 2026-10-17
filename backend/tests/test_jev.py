import asyncio

from app.decision import jev

# Respuesta con la forma de POST /v1/evaluate (documentación de Vercel AI Gateway)
RAW = {
    "model": "typesafe-ai/jev",
    "answers": {
        "segment": {"type": "choice", "choice": "lider_adopcion",
                    "probabilities": {"explorador": 0.01, "lider_negocio": 0.02, "lider_tecnico": 0.03,
                                      "equipo_adopcion": 0.02, "lider_adopcion": 0.91, "otro": 0.01}},
        "maturity": {"type": "score", "score": 1.8, "probabilities": {"0": 0.04, "1": 0.14, "2": 0.82}},
        "sales_ready": {"type": "boolean", "probability": 0.88},
        "content": {"type": "choice", "choice": "caso_de_exito",
                    "probabilities": {"intro_ia": 0.05, "caso_de_exito": 0.79, "taller_practico": 0.1,
                                      "programa_ejecutivo": 0.05, "otro": 0.01}},
    },
    "usage": {"inputTokens": 500, "outputTokens": 20},
    "providerMetadata": {"gateway": {"cost": "0.00002100"}},
}

STATE = {
    "person": {"person_id": "p_0001", "name": "María Gómez", "role": "Head of AI", "company": "Banco Andino",
               "industry": "banca", "company_size": "1000+", "events_attended": 3},
    "event": {"type": "attendance", "timestamp": "2026-10-17T15:04:05+00:00", "data": {}},
    "recent_events": [],
}


def test_parse_answers():
    a = jev.parse_answers(RAW, jev.QUESTIONS)
    assert (a["segment"].value, a["segment"].p) == ("lider_adopcion", 0.91)
    assert (a["maturity"].value, a["maturity"].p) == ("alta", 0.82)
    assert (a["sales_ready"].value, a["sales_ready"].p) == (True, 0.88)
    assert (a["content"].value, a["content"].p) == ("caso_de_exito", 0.79)
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


def test_mock_reconoce_cargos():
    assert jev._guess_segment("Head of AI") == ("lider_adopcion", True)
    assert jev._guess_segment("Director de tecnología") == ("lider_tecnico", True)
    assert jev._guess_segment("Directora de marketing") == ("lider_negocio", True)
    assert jev._guess_segment("Analista de datos") == ("equipo_adopcion", True)
    assert jev._guess_segment("Estudiante") == ("otro", True)
    assert jev._guess_segment("Consultor independiente") == ("explorador", False)
