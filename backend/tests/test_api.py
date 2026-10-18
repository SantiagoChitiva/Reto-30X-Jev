import time

from app.models import CrmRecord, Decision, Review


FUNDADOR = {"relation": "Deal en el CRM", "crm_status": "En proceso", "crm_stage": "Calificado",
            "role": "Fundador, socio o CEO", "objective": "Vender más", "interests": ["sales", "ai"],
            "info_level": "Alta", "info_available": "Perfil con contexto (dolor u objetivo)"}
LEAD = {"relation": "Lead (sin deal)", "crm_status": "Lead sin oportunidad abierta", "objective": "Vender más",
        "interests": ["sales"], "info_level": "Baja", "info_available": "Solo interés declarado"}
SIN_INFO = {"relation": "Lead (sin deal)", "info_level": "Baja", "info_available": "Sin información"}


def person(pid="p_0001", profile=None):
    return {"person_id": pid, **(FUNDADOR if profile is None else profile)}


def signup(client, pid="p_0001", **kw):
    return client.post("/events", json={"person_id": pid, "type": "signup",
                                        "data": {"event_name": "Free Sales Training"}, "person": person(pid, **kw)})


def test_health(client):
    assert client.get("/health").json() == {"ok": True, "mock_jev": True}


def test_signup_devuelve_decision(client):
    r = signup(client)
    assert r.status_code == 200
    d = Decision.model_validate(r.json())
    assert d.person_id == "p_0001" and d.decision_id.startswith("d_") and d.event_id.startswith("e_")
    assert d.segment.value == "fundador_ventas"
    if d.route == "auto":
        if d.guardrail is not None and not d.guardrail.passed:
            assert d.action is None
        if d.action == "notify_sales":  # solo el aviso a ventas pasa por el guardrail de JEV
            assert d.guardrail is not None and d.guardrail.passed
    else:
        assert d.guardrail is None
    if d.route == "safe":
        assert d.explanation and d.action in ("send:nutricion", None)
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
    assert body["person"]["events_attended"] == 1  # el perfil del signup trae 0
    assert len(body["history"]) == 2
    assert set(body["history"][0]) == {"at", "segment", "maturity", "sales_ready"}
    assert client.get("/people/p_9999").status_code == 404


def test_email_open_suma_en_codigo(client):
    signup(client)
    client.post("/events", json={"person_id": "p_0001", "type": "email_open", "data": {"email_topic": "x"}})
    assert client.get("/people/p_0001").json()["person"]["emails_opened"] == 1


def test_transicion_cuando_aparece_el_rol(client):
    signup(client, profile=LEAD)
    client.post("/events", json={"person_id": "p_0001", "type": "profile_update",
                                 "data": {"relation": "Deal en el CRM", "role": "Líder comercial o de ventas"}})
    assert client.get("/transitions").json() == [{"from": "explorador", "to": "lider_comercial", "count": 1}]


def test_profile_update_invalido(client):
    signup(client)
    r = client.post("/events", json={"person_id": "p_0001", "type": "profile_update",
                                     "data": {"info_level": "Altísima"}})
    assert r.status_code == 422


def test_cola_humana(client):
    d = signup(client, profile=SIN_INFO).json()  # sin información: segmento `otro` → siempre humano
    assert d["route"] == "human" and d["action"] is None

    queue = client.get("/review-queue").json()
    assert len(queue) == 1
    review = Review.model_validate(queue[0])
    assert review.decision_id == d["decision_id"] and review.status == "pending"

    r = client.post(f"/review/{review.review_id}", json={"segment": "explorador", "action": "send:nutricion"})
    assert r.status_code == 200
    assert r.json()["status"] == "resolved" and r.json()["resolved_action"] == "send:nutricion"
    assert client.get("/review-queue").json() == []

    assert client.post(f"/review/{review.review_id}", json={"segment": "explorador"}).status_code == 409
    assert client.post("/review/r_9999", json={"segment": "explorador"}).status_code == 404
    assert client.post(f"/review/{review.review_id}", json={"segment": "nada"}).status_code == 422


def test_filtro_de_decisiones(client):
    signup(client, "p_0001", profile=SIN_INFO)
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
    assert abs(m["auto_pct"] + m["safe_pct"] + m["human_pct"] - 100) < 0.5
    assert m["total_cost_usd"] > 0 and m["cost_per_1k_usd"] > 0
    assert m["latency_p95_ms"] >= m["latency_p50_ms"]
    assert set(m) == {"total_decisions", "auto_pct", "safe_pct", "human_pct", "guardrail_blocked", "spam_suppressed",
                      "total_cost_usd", "cost_per_1k_usd", "latency_p50_ms", "latency_p95_ms", "running",
                      "failed_events", "last_error"}
    assert m["failed_events"] == 0


def test_antispam_frena_la_misma_accion(client, monkeypatch):
    from app.decision import jev, policy

    monkeypatch.setattr(policy, "route", lambda segment: "auto")
    monkeypatch.setattr(jev, "_mock_guardrail_answer", lambda state: {"type": "boolean", "probability": 0.95})
    first = signup(client).json()
    assert first["action"] is not None
    second = client.post("/events", json={"person_id": "p_0001", "type": "attendance", "data": {}}).json()
    assert second["action"] is None
    assert second["guardrail"]["passed"] is False and "frecuencia" in second["guardrail"]["reason"]
    m = client.get("/metrics").json()
    assert m["spam_suppressed"] == 1 and m["guardrail_blocked"] == 0


def test_evaluation_404_y_luego_resultado(client, tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    assert client.get("/evaluation").status_code == 404
    (tmp_path / "eval_results.json").write_text(json.dumps({"n": 1}))
    assert client.get("/evaluation").json() == {"n": 1}


def test_una_sola_revision_pendiente_por_persona(client):
    signup(client, profile=SIN_INFO)
    client.post("/events", json={"person_id": "p_0001", "type": "email_open", "data": {}})
    assert len(client.get("/review-queue").json()) == 1


def test_ficha_crm_tras_decision(client):
    d = signup(client).json()
    assert d["route"] != "human"
    ficha = CrmRecord.model_validate(client.get("/crm/p_0001").json())
    assert ficha.segment == d["segment"]["value"] and ficha.suggested_program == d["content"]["value"]
    # Lista para ventas solo si se avisó a ventas (primera decisión: el antispam no interviene)
    assert ficha.sales_ready == (d["action"] == "notify_sales") and ficha.decision_id == d["decision_id"]
    assert ficha.decided_by == ("jev" if d["route"] == "auto" else "jev_por_confirmar")
    assert ficha.confidence == round(min(d["segment"]["p"], d["sales_ready"]["p"]), 4)
    assert client.get("/crm/p_9999").status_code == 404


def test_ficha_crm_la_escribe_la_persona_en_la_ruta_humana(client):
    signup(client, profile=SIN_INFO)
    assert client.get("/crm/p_0001").status_code == 404  # la ruta humana no escribe sola
    review = client.get("/review-queue").json()[0]
    client.post(f"/review/{review['review_id']}", json={"segment": "fundador_ventas", "action": "notify_sales"})
    ficha = client.get("/crm/p_0001").json()
    assert ficha["decided_by"] == "humano" and ficha["segment"] == "fundador_ventas"
    assert ficha["sales_ready"] is True and ficha["confidence"] == 1.0
    assert [f["person_id"] for f in client.get("/crm", params={"sales_ready": "true"}).json()] == ["p_0001"]
    assert client.get("/crm", params={"sales_ready": "false"}).json() == []


def test_ruta_prudente_nunca_avisa_a_ventas(client, monkeypatch):
    from app.decision import policy

    monkeypatch.setattr(policy, "route", lambda segment: "safe")
    d = signup(client).json()  # el fundador está listo para ventas, pero con confianza media
    assert d["route"] == "safe" and d["sales_ready"]["value"] is True
    assert d["action"] == "send:nutricion" and "por confirmar" in d["explanation"]
    ficha = client.get("/crm/p_0001").json()
    assert ficha["decided_by"] == "jev_por_confirmar" and ficha["sales_ready"] is False


def test_enviar_contenido_no_pasa_por_el_guardrail(client, monkeypatch):
    from app.decision import policy

    monkeypatch.setattr(policy, "route", lambda segment: "auto")
    d = signup(client, profile=LEAD).json()  # sin rol ni dolor: nunca se avisa a ventas
    assert d["action"].startswith("send:") and d["guardrail"] is None
    assert client.get("/crm/p_0001").json()["sales_ready"] is False


def test_aviso_a_ventas_pasa_por_el_guardrail(client, monkeypatch):
    from app.decision import jev, policy
    from app.models import Answer

    monkeypatch.setattr(policy, "route", lambda segment: "auto")
    real_ask = jev.ask

    async def ask_listo(state):
        r = await real_ask(state)
        r.answers["sales_ready"] = Answer(value=True, p=0.95)
        return r

    monkeypatch.setattr(jev, "ask", ask_listo)
    monkeypatch.setattr(jev, "_mock_guardrail_answer", lambda state: {"type": "boolean", "probability": 0.7})
    d = signup(client).json()
    assert d["action"] == "notify_sales" and d["guardrail"]["passed"] is True
    assert client.get("/crm/p_0001").json()["sales_ready"] is True

    monkeypatch.setattr(jev, "_mock_guardrail_answer", lambda state: {"type": "boolean", "probability": 0.3})
    d = signup(client, pid="p_0002").json()
    assert d["action"] is None and d["guardrail"]["passed"] is False
    assert client.get("/crm/p_0002").json()["sales_ready"] is False


def test_la_revision_sale_de_la_cola_cuando_ya_se_sabe_quien_es(client):
    signup(client, profile=SIN_INFO)
    assert len(client.get("/review-queue").json()) == 1
    d = client.post("/events", json={"person_id": "p_0001", "type": "profile_update", "data": FUNDADOR}).json()
    assert d["route"] != "human"
    assert client.get("/review-queue").json() == []


def test_el_programa_de_la_ficha_no_cambia_si_jev_duda(client, monkeypatch):
    from app.decision import jev
    from app.models import Answer

    signup(client)
    antes = client.get("/crm/p_0001").json()["suggested_program"]
    real_ask = jev.ask

    async def ask_dudosa(state):
        r = await real_ask(state)
        otro = "achievers" if antes != "achievers" else "hardcore_ai"
        r.answers["content"] = Answer(value=otro, p=0.40)
        return r

    monkeypatch.setattr(jev, "ask", ask_dudosa)
    d = client.post("/events", json={"person_id": "p_0001", "type": "attendance", "data": {}}).json()
    if d["route"] != "human":
        assert client.get("/crm/p_0001").json()["suggested_program"] == antes


def test_empezar_de_cero_borra_solo_lo_simulado(client):
    signup(client)
    client.post("/webhooks/hubspot", json=[{"eventId": 777001, "subscriptionType": "contact.propertyChange",
                                            "objectId": 42, "propertyName": "objetivo_30x", "propertyValue": "Vender más"}])
    assert client.post("/reset").json() == {"deleted_people": 1}
    assert client.get("/people/p_0001").status_code == 404
    assert client.get("/people/hs_42").status_code == 200  # lo de HubSpot no se toca
    assert client.get("/metrics").json()["total_decisions"] == 1
