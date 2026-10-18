"""Lo que 30X Pulse escribe de vuelta en el CRM de 30X: la ficha de cada persona.

La ficha siempre queda en la tabla `crm_profiles`. Si la persona viene de HubSpot (`hs_<id>`) y
hay `HUBSPOT_TOKEN`, también se escribe en las propiedades `pulse_*` del contacto (ver hubspot.py).
Es el único punto de salida del sistema.
"""
from typing import Optional

from . import hubspot
from .models import CrmRecord, Decision, Review
from .store import get_store, now


def from_decision(d: Decision) -> Optional[CrmRecord]:
    """La ficha que deja una decisión automática o revisada por el LLM. La ruta humana no
    escribe nada: la ficha queda como estaba hasta que una persona resuelva el caso."""
    if d.route == "human":
        return None
    return CrmRecord(
        person_id=d.person_id,
        segment=d.segment.value,
        maturity=d.maturity.value,
        sales_ready=d.sales_ready.value,
        suggested_program=d.content.value,
        confidence=round(min(d.segment.p, d.sales_ready.p), 4),
        decided_by="jev" if d.route == "auto" else "llm",
        last_action=d.action,
        decision_id=d.decision_id,
        updated_at=d.created_at,
    )


def from_review(r: Review, d: Decision) -> CrmRecord:
    """La ficha que deja una persona al resolver un caso de la cola humana."""
    action = r.resolved_action
    program = action[len("send:"):] if action and action.startswith("send:") else d.content.value
    return CrmRecord(
        person_id=d.person_id,
        segment=r.resolved_segment or d.segment.value,
        maturity=d.maturity.value,
        sales_ready=action == "notify_sales",
        suggested_program=program,
        confidence=1.0,
        decided_by="humano",
        last_action=action,
        decision_id=d.decision_id,
        updated_at=now(),
    )


def _same(a: Optional[CrmRecord], b: CrmRecord) -> bool:
    """¿Cambió algo que ventas vea? Si no, no se gasta una llamada a HubSpot."""
    keys = ("segment", "maturity", "sales_ready", "suggested_program", "decided_by", "last_action")
    return a is not None and all(getattr(a, k) == getattr(b, k) for k in keys)


async def write(record: Optional[CrmRecord]) -> None:
    if record is None:
        return
    store = get_store()
    previous = await store.crm_record(record.person_id)
    await store.upsert_crm(record)
    cid = hubspot.contact_id(record.person_id)
    if cid and hubspot.sync_enabled() and not _same(previous, record):
        try:
            await hubspot.update_contact(cid, hubspot.contact_properties(record))
        except Exception as e:  # HubSpot caído no frena las decisiones: la ficha local ya quedó
            print(f"No se pudo escribir en HubSpot ({type(e).__name__}): {e}")
