"""Une todo: evento → JEV → umbral → guardrail, LLM o persona → se guarda la decisión y la ficha del CRM."""
import time
from typing import Any

from .. import crm
from ..models import Answer, Decision, Event, EventIn, Guardrail, Person
from ..store import get_store, now
from . import jev, policy


ACTIVE_STAGES = {"Registrado", "Contactado", "Potencial", "Calificado", "En gestión"}


def signals(person: Person, recent: list[Event]) -> dict[str, Any]:
    """Conteos y comparaciones que JEV no debe hacer: se calculan aquí y se le pasan ya resueltos."""
    return {
        "events_attended": person.events_attended,
        "emails_opened": person.emails_opened,
        "has_deal": person.relation == "Deal en el CRM",
        "deal_in_progress": person.crm_stage in ACTIVE_STAGES,
        "profile_updates_recent": sum(1 for e in recent if e.type == "profile_update"),
    }


def build_state(person: Person, event: Event, recent: list[Event]) -> dict[str, Any]:
    """Lo que JEV ve: el perfil, las señales calculadas, el evento actual y los anteriores."""
    def summary(e: Event) -> dict[str, Any]:
        return {"type": e.type, "timestamp": e.timestamp.isoformat(), "data": e.data}

    return {
        "person": person.model_dump(mode="json", exclude={"events_attended", "emails_opened"}),
        "signals": signals(person, recent),
        "event": summary(event),
        "recent_events": [summary(e) for e in recent],
    }


async def process_event(ev_in: EventIn) -> Decision:
    t0 = time.perf_counter()
    store = get_store()
    person, event, recent = await store.apply_event(ev_in)
    state = build_state(person, event, recent)

    result = await jev.ask(state)
    answers = result.answers
    route = policy.route(answers["segment"], answers["sales_ready"])
    action = policy.choose_action(answers["sales_ready"], answers["content"])
    cost = result.cost_usd
    guard = None
    explanation = None

    if route != "human" and policy.repeated_action(
            action, await store.recent_actions(person.person_id, policy.SPAM_WINDOW)
    ):
        spam = f"{policy.SPAM_REASON}: `{action}` ya salió en las últimas {policy.SPAM_WINDOW} decisiones."
        action = None
    else:
        spam = None

    if route == "auto":
        if spam:
            guard = Guardrail(passed=False, p=0.0, reason=spam)  # el antispam frena sin llamar a JEV
        elif action is None:
            guard = Guardrail(passed=True, p=1.0)  # no hay acción que revisar
        else:
            guard, guard_cost = await jev.guardrail(state, answers, action)
            cost += guard_cost
            if not guard.passed:
                action = None
    elif route == "llm":
        review = await jev.review_with_llm(state, answers, action)
        explanation = review.explanation
        cost += review.cost_usd
        if review.segment:  # el LLM corrigió el segmento; `p` sigue siendo la de JEV
            answers["segment"] = Answer(value=review.segment, p=answers["segment"].p)
        if review.action_changed and not policy.repeated_action(
                review.action, await store.recent_actions(person.person_id, policy.SPAM_WINDOW)
        ):
            action = review.action
        if spam:
            explanation = f"{explanation} {spam}"
    else:
        action = None  # lo decide una persona en la cola de revisión

    decision = Decision(
        decision_id=store.next_id("d"),
        person_id=person.person_id,
        event_id=event.event_id,
        segment=answers["segment"],
        maturity=answers["maturity"],
        sales_ready=answers["sales_ready"],
        content=answers["content"],
        route=route,
        guardrail=guard,
        action=action,
        explanation=explanation,
        latency_ms=round((time.perf_counter() - t0) * 1000, 1),
        cost_usd=round(cost, 10),
        created_at=now(),
    )
    await store.save_decision(decision)
    await crm.write(crm.from_decision(decision))
    # Una sola revisión pendiente por persona: los eventos siguientes no la duplican
    if route == "human" and not await store.has_pending_review(person.person_id):
        await store.add_review(decision.decision_id)
    return decision
