import itertools
import json
import time
from datetime import datetime, timezone

import pytest

from app import crm, hubspot
from app.decision import pipeline
from app.models import CrmRecord, Event, Person

_ids = itertools.count(1)


def hs_event(kind, obj=101, prop=None, value=None):
    ev = {"eventId": next(_ids) + int(time.time() * 1000), "subscriptionType": kind, "objectId": obj}
    if prop:
        ev.update(propertyName=prop, propertyValue=value)
    return ev


def send(client, *events):
    r = client.post("/webhooks/hubspot", json=list(events))
    assert r.status_code == 200
    return r.json()


@pytest.fixture(autouse=True)
def sin_hubspot(monkeypatch):
    for var in ("HUBSPOT_TOKEN", "HUBSPOT_CLIENT_SECRET", "HUBSPOT_PROPERTY_MAP", "HUBSPOT_DEAL_STAGES"):
        monkeypatch.delenv(var, raising=False)


def test_contacto_nuevo_crea_la_persona(client):
    out = send(client, hs_event("contact.creation"))
    assert len(out["decisions"]) == 1
    person = client.get("/people/hs_101").json()["person"]
    assert person["relation"] == "Lead (sin deal)"
    assert client.get("/crm/hs_101").status_code in (200, 404)  # 404 si fue a la cola humana


def test_eventos_repetidos_se_ignoran(client):
    ev = hs_event("contact.creation")
    send(client, ev)
    out = send(client, ev)  # HubSpot reintenta con el mismo eventId
    assert out == {"received": 1, "ignored": 1, "decisions": []}


def test_cambio_de_propiedad_actualiza_el_perfil(client):
    send(client, hs_event("contact.propertyChange", prop="objetivo_30x", value="Vender más"))
    assert client.get("/people/hs_101").json()["person"]["objective"] == "Vender más"  # signup con el cambio
    send(client, hs_event("contact.propertyChange", prop="intereses_30x", value="sales;ai"))
    send(client, hs_event("contact.propertyChange", prop="rol_30x", value="Fundador, socio o CEO"))
    body = client.get("/people/hs_101").json()
    assert body["person"]["interests"] == ["sales", "ai"]
    assert body["person"]["role"] == "Fundador, socio o CEO"
    assert len(body["history"]) == 3


def test_apertura_de_correo_y_asistencia(client):
    send(client, hs_event("contact.creation"))
    send(client, hs_event("contact.propertyChange", prop=hubspot.EMAIL_OPEN_PROPERTY, value="1760000000000"))
    send(client, hs_event("contact.propertyChange", prop=hubspot.ATTENDANCE_PROPERTY, value="Free Sales Training"))
    person = client.get("/people/hs_101").json()["person"]
    assert person["emails_opened"] == 1 and person["events_attended"] == 1


def test_propiedad_que_no_usa_pulse_no_genera_decision(client):
    send(client, hs_event("contact.creation"))
    assert send(client, hs_event("contact.propertyChange", prop="phone", value="123"))["decisions"] == []


def test_deal_con_etapa_marca_al_contacto(client, monkeypatch):
    async def contactos(deal_id):
        return ["101"]

    monkeypatch.setattr(hubspot, "deal_contacts", contactos)
    monkeypatch.setenv("HUBSPOT_DEAL_STAGES", json.dumps({"123456": "Calificado"}))
    send(client, hs_event("contact.creation"))
    send(client, hs_event("deal.propertyChange", obj=900, prop="dealstage", value="123456"))
    person = client.get("/people/hs_101").json()["person"]
    assert person["relation"] == "Deal en el CRM" and person["crm_stage"] == "Calificado"


def test_mapa_de_propiedades_configurable(client, monkeypatch):
    monkeypatch.setenv("HUBSPOT_PROPERTY_MAP", json.dumps({"jobtitle_30x": "role"}))
    send(client, hs_event("contact.propertyChange", prop="jobtitle_30x", value="Perfil técnico"))
    assert client.get("/people/hs_101").json()["person"]["role"] == "Perfil técnico"


def test_firma_v3(client, monkeypatch):
    monkeypatch.setenv("HUBSPOT_CLIENT_SECRET", "secreto")
    body = json.dumps([hs_event("contact.creation")]).encode()
    url = "http://testserver/webhooks/hubspot"
    ts = str(int(time.time() * 1000))
    firma = hubspot.signature_v3("secreto", "POST", url, body, ts)
    headers = {"content-type": "application/json", "X-HubSpot-Request-Timestamp": ts}

    assert client.post("/webhooks/hubspot", content=body,
                       headers={**headers, "X-HubSpot-Signature-v3": "mala"}).status_code == 401
    viejo = str(int(time.time() * 1000) - 10 * 60 * 1000)
    assert client.post("/webhooks/hubspot", content=body, headers={
        **headers, "X-HubSpot-Request-Timestamp": viejo,
        "X-HubSpot-Signature-v3": hubspot.signature_v3("secreto", "POST", url, body, viejo)}).status_code == 401
    assert client.post("/webhooks/hubspot", content=body,
                       headers={**headers, "X-HubSpot-Signature-v3": firma}).status_code == 200


def test_la_decision_se_escribe_en_hubspot(client, monkeypatch):
    escritos = []

    async def update(cid, properties):
        escritos.append((cid, properties))
        return True

    async def fetch(cid):
        return {"relacion_30x": "Deal en el CRM", "estado_crm_30x": "En proceso", "etapa_crm_30x": "Calificado",
                "rol_30x": "Fundador, socio o CEO", "objetivo_30x": "Vender más", "intereses_30x": "sales;ai",
                "nivel_info_30x": "Alta", "info_disponible_30x": "Perfil con contexto (dolor u objetivo)"}

    monkeypatch.setenv("HUBSPOT_TOKEN", "pat-test")
    monkeypatch.setattr(hubspot, "update_contact", update)
    monkeypatch.setattr(hubspot, "fetch_contact", fetch)
    send(client, hs_event("contact.creation"))
    ficha = client.get("/crm/hs_101").json()
    assert escritos == [("101", hubspot.contact_properties(CrmRecord.model_validate(ficha)))]
    assert escritos[0][1]["pulse_segmento"] == "fundador_ventas"


def test_no_escribe_en_hubspot_si_nada_cambio(monkeypatch):
    r = CrmRecord(person_id="hs_1", segment="explorador", maturity="baja", sales_ready=False,
                  suggested_program="nutricion", confidence=0.9, decided_by="jev", last_action=None,
                  decision_id="d_000001", updated_at=datetime.now(timezone.utc))
    assert crm._same(r, r.model_copy(update={"confidence": 0.95}))
    assert not crm._same(r, r.model_copy(update={"sales_ready": True}))
    assert not crm._same(None, r)


def test_jev_no_recibe_el_id_de_la_persona():
    person = Person(person_id="hs_101", relation="Lead (sin deal)", objective="Vender más")
    event = Event(event_id="e_000001", person_id="hs_101", type="signup", timestamp=datetime.now(timezone.utc))
    state = pipeline.build_state(person, event, [])
    assert "hs_101" not in json.dumps(state)
