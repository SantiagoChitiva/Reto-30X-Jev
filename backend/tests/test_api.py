import time

from app.models import Decision, Review


def person(pid="p_0001", role="Head of AI", size="1000+"):
    return {"person_id": pid, "name": "María Gómez", "role": role, "company": "Banco Andino",
            "industry": "banca", "company_size": size, "events_attended": 1}


def signup(client, pid="p_0001", **kw):
    return client.post("/events", json={"person_id": pid, "type": "signup",
                                        "data": {"event_name": "30X AI Summit"}, "person": person(pid, **kw)})


def test_health(client):
    assert client.get("/health").json() == {"ok": True, "mock_jev": True}


def test_signup_devuelve_decision(client):
    r = signup(client)
    assert r.status_code == 200
    d = Decision.model_validate(r.json())
    assert d.person_id == "p_0001" and d.decision_id.startswith("d_") and d.event_id.startswith("e_")
    assert d.segment.value == "lider_adopcion"
    if d.route == "auto":
        assert d.guardrail is not None
        assert d.action is None if not d.guardrail.passed else d.action is not None
    else:
        assert d.guardrail is None
    if d.route == "llm":
        assert d.explanation
    if d.route == "human":
        assert d.action is None


def test_signup_sin_person_es_invalido(client):
    r = client.post("/events", json={"person_id": "p_0001", "type": "signup", "data": {}})
    assert r.status_code == 422


def test_evento_de_persona_inexistente(client):
    r = client.post("/events", json={"person_id": "p_9999", "type": "attendance", "data": {}})
    assert r.status_code == 404


def test_attendance_suma_en_codigo(client):
    signup(client)
    client.post("/events", json={"person_id": "p_0001", "type": "attendance", "data": {"event_name": "x"}})
    body = client.get("/people/p_0001").json()
    assert body["person"]["events_attended"] == 2
    assert len(body["history"]) == 2
    assert set(body["history"][0]) == {"at", "segment", "maturity", "sales_ready"}
    assert client.get("/people/p_9999").status_code == 404


def test_transicion_por_cambio_de_cargo(client):
    signup(client, role="Analista de datos")
    client.post("/events", json={"person_id": "p_0001", "type": "profile_update", "data": {"role": "Head of AI"}})
    assert client.get("/transitions").json() == [{"from": "equipo_adopcion", "to": "lider_adopcion", "count": 1}]


def test_profile_update_invalido(client):
    signup(client)
    r = client.post("/events", json={"person_id": "p_0001", "type": "profile_update",
                                     "data": {"company_size": "enorme"}})
    assert r.status_code == 422


def test_cola_humana(client):
    d = signup(client, role="Estudiante").json()  # segmento `otro` → siempre humano
    assert d["route"] == "human" and d["action"] is None

    queue = client.get("/review-queue").json()
    assert len(queue) == 1
    review = Review.model_validate(queue[0])
    assert review.decision_id == d["decision_id"] and review.status == "pending"

    r = client.post(f"/review/{review.review_id}", json={"segment": "explorador", "action": "send:intro_ia"})
    assert r.status_code == 200
    assert r.json()["status"] == "resolved" and r.json()["resolved_action"] == "send:intro_ia"
    assert client.get("/review-queue").json() == []

    assert client.post(f"/review/{review.review_id}", json={"segment": "explorador"}).status_code == 409
    assert client.post("/review/r_9999", json={"segment": "explorador"}).status_code == 404
    assert client.post(f"/review/{review.review_id}", json={"segment": "nada"}).status_code == 422


def test_filtro_de_decisiones(client):
    signup(client, "p_0001", role="Estudiante")
    signup(client, "p_0002")
    humans = client.get("/decisions?route=human").json()
    assert humans and all(d["route"] == "human" for d in humans)
    assert [d["person_id"] for d in client.get("/decisions").json()] == ["p_0002", "p_0001"]


def test_simulate_y_metrics(client):
    assert client.get("/metrics").json()["total_decisions"] == 0
    assert client.post("/simulate", json={"n": 200}).json() == {"accepted": 200}

    deadline = time.time() + 20
    while client.get("/metrics").json()["running"] and time.time() < deadline:
        time.sleep(0.05)

    m = client.get("/metrics").json()
    assert m["running"] is False
    assert m["total_decisions"] == 200
    assert abs(m["auto_pct"] + m["llm_pct"] + m["human_pct"] - 100) < 0.5
    assert m["total_cost_usd"] > 0 and m["cost_per_1k_usd"] > 0
    assert m["latency_p95_ms"] >= m["latency_p50_ms"]
    assert set(m) == {"total_decisions", "auto_pct", "llm_pct", "human_pct", "guardrail_blocked",
                      "total_cost_usd", "cost_per_1k_usd", "latency_p50_ms", "latency_p95_ms", "running"}
