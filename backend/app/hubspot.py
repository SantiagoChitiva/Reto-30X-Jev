"""Integración con HubSpot, el CRM de 30X.

- **Entrada:** `POST /webhooks/hubspot` recibe los webhooks de HubSpot (contacto creado, propiedad
  cambiada, deal creado o con etapa nueva) y los convierte en eventos de 30X Pulse.
- **Salida:** `update_contact` escribe la decisión en propiedades del contacto (`pulse_*`), para que
  ventas la vea en la ficha y un workflow de HubSpot actúe (por ejemplo, crear una tarea cuando
  `pulse_lista_para_ventas` pasa a sí).
- **ID único:** el ID del contacto en HubSpot, como `hs_<id>`. Nunca se le envía a JEV.

Sin `HUBSPOT_TOKEN` se aceptan webhooks, pero no se lee ni se escribe nada en HubSpot. Los nombres
internos de las propiedades de 30X se ajustan con `HUBSPOT_PROPERTY_MAP` (JSON) sin tocar código.

CLI: `python -m app.hubspot crear-propiedades` crea en HubSpot el grupo y las propiedades `pulse_*`.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import os
import sys
import time
from collections import OrderedDict
from typing import Any, Optional

import httpx

from .models import CONTENT, MATURITY, SEGMENTS, CrmRecord, EventIn, Person

API_URL = "https://api.hubapi.com"
PREFIX = "hs_"
MAX_SIGNATURE_AGE_MS = 5 * 60 * 1000  # lo que recomienda HubSpot para la firma v3

# Propiedad de HubSpot → campo de Person. Las de 30X son una propuesta: se ajustan con
# HUBSPOT_PROPERTY_MAP cuando se conozcan los nombres internos reales.
DEFAULT_PROPERTY_MAP = {
    "relacion_30x": "relation",
    "estado_crm_30x": "crm_status",
    "etapa_crm_30x": "crm_stage",
    "programa_30x": "program",
    "rol_30x": "role",
    "country": "country",
    "dolor_30x": "pain",
    "objetivo_30x": "objective",
    "intereses_30x": "interests",       # casillas múltiples: valores separados por ";"
    "nivel_info_30x": "info_level",
    "info_disponible_30x": "info_available",
}
EMAIL_OPEN_PROPERTY = "hs_email_last_open_date"     # HubSpot la actualiza en cada apertura
ATTENDANCE_PROPERTY = "ultimo_evento_asistido_30x"  # la llena la integración de Luma
DEAL_RELATION = "Deal en el CRM"

# Lo que Pulse escribe en el contacto (grupo `30x_pulse`)
PULSE_GROUP = "30x_pulse"
PULSE_PROPERTIES: list[dict[str, Any]] = [
    {"name": "pulse_segmento", "label": "Pulse: segmento", "type": "enumeration", "fieldType": "select",
     "options": SEGMENTS},
    {"name": "pulse_programa_sugerido", "label": "Pulse: programa sugerido", "type": "enumeration",
     "fieldType": "select", "options": CONTENT},
    {"name": "pulse_lista_para_ventas", "label": "Pulse: lista para ventas", "type": "bool",
     "fieldType": "booleancheckbox", "options": ["true", "false"]},
    {"name": "pulse_madurez_ia", "label": "Pulse: madurez en IA", "type": "enumeration", "fieldType": "select",
     "options": MATURITY},
    {"name": "pulse_confianza", "label": "Pulse: confianza", "type": "number", "fieldType": "number"},
    {"name": "pulse_decidido_por", "label": "Pulse: decidido por", "type": "enumeration", "fieldType": "select",
     "options": ["jev", "jev_por_confirmar", "humano"]},
    {"name": "pulse_ultima_accion", "label": "Pulse: última acción", "type": "string", "fieldType": "text"},
    {"name": "pulse_actualizado", "label": "Pulse: actualizado", "type": "datetime", "fieldType": "date"},
]


def token() -> Optional[str]:
    return os.getenv("HUBSPOT_TOKEN") or None


def sync_enabled() -> bool:
    """¿Se escriben las decisiones en HubSpot? Sí si hay token, salvo HUBSPOT_SYNC=false."""
    return bool(token()) and os.getenv("HUBSPOT_SYNC", "true").strip().lower() != "false"


def property_map() -> dict[str, str]:
    custom = os.getenv("HUBSPOT_PROPERTY_MAP")
    return {**DEFAULT_PROPERTY_MAP, **json.loads(custom)} if custom else dict(DEFAULT_PROPERTY_MAP)


def deal_stage_map() -> dict[str, str]:
    """ID de etapa del pipeline de deals en HubSpot → etapa de 30X (`HUBSPOT_DEAL_STAGES`, JSON)."""
    custom = os.getenv("HUBSPOT_DEAL_STAGES")
    return json.loads(custom) if custom else {}


def person_id(contact_id: Any) -> str:
    return f"{PREFIX}{contact_id}"


def contact_id(pid: str) -> Optional[str]:
    """El ID de HubSpot detrás de un `person_id`, o None si la persona no viene de HubSpot."""
    return pid[len(PREFIX):] if pid.startswith(PREFIX) else None


# --- Firma de los webhooks (v3) ---

def signature_v3(secret: str, method: str, uri: str, body: bytes, timestamp: str) -> str:
    message = method.upper().encode() + uri.encode() + body + timestamp.encode()
    return base64.b64encode(hmac.new(secret.encode(), message, hashlib.sha256).digest()).decode()


def verify_signature(method: str, uri: str, body: bytes, signature: Optional[str],
                     timestamp: Optional[str]) -> bool:
    """Valida `X-HubSpot-Signature-v3`. Sin `HUBSPOT_CLIENT_SECRET` no se valida (solo desarrollo)."""
    secret = os.getenv("HUBSPOT_CLIENT_SECRET")
    if not secret:
        return True
    if not signature or not timestamp or not timestamp.isdigit():
        return False
    if abs(time.time() * 1000 - int(timestamp)) > MAX_SIGNATURE_AGE_MS:
        return False
    uri = os.getenv("HUBSPOT_WEBHOOK_URL") or uri  # la URL pública, si hay un proxy delante
    return hmac.compare_digest(signature_v3(secret, method, uri, body, timestamp), signature)


# --- De HubSpot a Person ---

def to_field(field: str, value: Any) -> Any:
    """Valor de una propiedad de HubSpot → valor del campo de Person (None = sin dato)."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return [] if field == "interests" else None
    if field == "interests":
        return [v.strip() for v in str(value).split(";") if v.strip()]
    if field == "info_level":
        return value if value in ("Baja", "Media", "Alta") else None
    return str(value).strip()


def to_person(pid: str, properties: dict[str, Any]) -> Person:
    fields: dict[str, Any] = {}
    for prop, field in property_map().items():
        if prop in properties:
            fields[field] = to_field(field, properties[prop])
    fields["relation"] = fields.get("relation") or "Lead (sin deal)"  # sin deal = lead
    if fields.get("info_level") is None:
        fields.pop("info_level", None)
    return Person(person_id=pid, **fields)


# --- Llamadas a la API de HubSpot ---

_client: Optional[httpx.AsyncClient] = None


def _http() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=API_URL, timeout=10.0)
    return _client


async def aclose() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def _request(method: str, path: str, **kw) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token()}"}
    for attempt in range(2):
        resp = await _http().request(method, path, headers=headers, **kw)
        if resp.status_code == 429 and attempt == 0:
            await asyncio.sleep(float(resp.headers.get("Retry-After", "1")))  # límite de uso: un reintento
            continue
        return resp
    return resp


async def fetch_contact(cid: str) -> Optional[dict[str, Any]]:
    """Propiedades del contacto que usa Pulse, o None sin token o si falla."""
    if not token():
        return None
    props = ",".join(property_map())
    resp = await _request("GET", f"/crm/v3/objects/contacts/{cid}", params={"properties": props})
    return resp.json().get("properties", {}) if resp.status_code == 200 else None


async def deal_contacts(deal_id: str) -> list[str]:
    """IDs de los contactos asociados a un deal (los webhooks de deals no los traen)."""
    if not token():
        return []
    resp = await _request("GET", f"/crm/v4/objects/deals/{deal_id}/associations/contacts")
    if resp.status_code != 200:
        return []
    return [str(r["toObjectId"]) for r in resp.json().get("results", [])]


def contact_properties(r: CrmRecord) -> dict[str, str]:
    return {
        "pulse_segmento": r.segment,
        "pulse_programa_sugerido": r.suggested_program,
        "pulse_lista_para_ventas": "true" if r.sales_ready else "false",
        "pulse_madurez_ia": r.maturity,
        "pulse_confianza": f"{r.confidence:.2f}",
        "pulse_decidido_por": r.decided_by,
        "pulse_ultima_accion": r.last_action or "",
        "pulse_actualizado": r.updated_at.isoformat(),
    }


async def update_contact(cid: str, properties: dict[str, str]) -> bool:
    resp = await _request("PATCH", f"/crm/v3/objects/contacts/{cid}", json={"properties": properties})
    if resp.status_code >= 400:
        print(f"HubSpot no aceptó la ficha de {cid}: {resp.status_code} {resp.text[:200]}", file=sys.stderr)
        return False
    return True


# --- De webhook a eventos de Pulse ---

_seen: "OrderedDict[str, None]" = OrderedDict()  # eventId ya procesados: HubSpot reintenta
_SEEN_MAX = 10_000


def already_seen(event: dict[str, Any]) -> bool:
    key = str(event.get("eventId") or "")
    if not key:
        return False
    if key in _seen:
        return True
    _seen[key] = None
    if len(_seen) > _SEEN_MAX:
        _seen.popitem(last=False)
    return False


async def to_events(event: dict[str, Any], exists) -> list[EventIn]:
    """Un evento del webhook → los eventos de Pulse que genera (puede ser ninguno).

    `exists(person_id)` dice si la persona ya está en Pulse. Si no está, el primer evento es un
    `signup` con su perfil (leído de HubSpot si hay token) y el cambio ya incluido.
    """
    kind = str(event.get("subscriptionType", ""))
    obj = str(event.get("objectId", ""))
    prop, value = event.get("propertyName"), event.get("propertyValue")

    if kind.startswith("deal."):
        if kind == "deal.propertyChange" and prop != "dealstage":
            return []
        changes: dict[str, Any] = {"relation": DEAL_RELATION}
        stage = deal_stage_map().get(str(value)) if prop == "dealstage" else None
        if stage:
            changes["crm_stage"] = stage
        out = []
        for cid in await deal_contacts(obj):
            out += await _contact_change(person_id(cid), cid, "profile_update", changes, exists)
        return out

    if not kind.startswith("contact."):
        return []
    pid = person_id(obj)
    if kind == "contact.creation":
        return [] if await exists(pid) else await _contact_change(pid, obj, None, {}, exists)
    if kind != "contact.propertyChange":
        return []
    if prop == EMAIL_OPEN_PROPERTY:
        return await _contact_change(pid, obj, "email_open", {}, exists)
    if prop == ATTENDANCE_PROPERTY:
        return await _contact_change(pid, obj, "attendance", {"event_name": value}, exists)
    field = property_map().get(prop)
    if field is None:
        return []
    return await _contact_change(pid, obj, "profile_update", {field: to_field(field, value)}, exists)


async def _contact_change(pid: str, cid: str, kind: Optional[str], data: dict[str, Any], exists) -> list[EventIn]:
    if await exists(pid):
        return [EventIn(person_id=pid, type=kind, data=data)] if kind else []
    # Primera vez que Pulse ve a esta persona: signup con su perfil actual
    properties = await fetch_contact(cid)
    person = to_person(pid, properties or {})
    if kind == "profile_update":  # el valor del webhook es el más reciente
        person = Person.model_validate({**person.model_dump(), **data})
    signup = EventIn(person_id=pid, type="signup", data={"source": "hubspot"}, person=person)
    if kind in ("email_open", "attendance"):
        return [signup, EventIn(person_id=pid, type=kind, data=data)]
    return [signup]


# --- CLI: crear las propiedades pulse_* en HubSpot ---

async def create_properties() -> None:
    if not token():
        raise SystemExit("Falta HUBSPOT_TOKEN en .env")
    resp = await _request("POST", "/crm/v3/properties/contacts/groups",
                          json={"name": PULSE_GROUP, "label": "30X Pulse", "displayOrder": -1})
    print(f"grupo {PULSE_GROUP}: {resp.status_code}")
    for prop in PULSE_PROPERTIES:
        body = {k: v for k, v in prop.items() if k != "options"}
        body["groupName"] = PULSE_GROUP
        if "options" in prop:
            body["options"] = [{"label": o, "value": o, "displayOrder": i} for i, o in enumerate(prop["options"])]
        resp = await _request("POST", "/crm/v3/properties/contacts", json=body)
        status = "ya existía" if resp.status_code == 409 else resp.status_code
        print(f"{prop['name']}: {status}")
    await aclose()


if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()
    if sys.argv[1:] != ["crear-propiedades"]:
        raise SystemExit("Uso: python -m app.hubspot crear-propiedades")
    asyncio.run(create_properties())
