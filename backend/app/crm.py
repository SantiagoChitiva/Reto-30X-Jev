"""Lo que 30X Pulse escribe de vuelta en el CRM de 30X: la ficha de cada persona.

30X pidió trabajarlo por ahora como una base de datos, así que la ficha vive en la tabla
`crm_profiles`. Es el único punto de salida del sistema: conectar el CRM real es cambiar
`write` para que mande estas mismas propiedades a su API, sin tocar el resto.
"""
from typing import Optional

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


async def write(record: Optional[CrmRecord]) -> None:
    if record is not None:
        await get_store().upsert_crm(record)
