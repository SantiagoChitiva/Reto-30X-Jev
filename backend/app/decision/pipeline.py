"""Une todo: evento → JEV → umbral → guardrail, LLM o persona → se guarda la decisión."""
import time
from typing import Any

from ..models import Decision, Event, EventIn, Guardrail, Person
from ..store import get_store, now
from . import jev, policy


def build_state(person: Person, event: Event, recent: list[Event]) -> dict[str, Any]:
    """Lo que JEV ve: el perfil, el evento actual y los eventos anteriores."""
    def summary(e: Event) -> dict[str, Any]:
        return {"type": e.type, "timestamp": e.timestamp.isoformat(), "data": e.data}

    return {
        "person": person.model_dump(mode="json"),
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

    if route == "auto":
        if action is None:
            guard = Guardrail(passed=True, p=1.0)  # no hay acción que revisar
        else:
            guard, guard_cost = await jev.guardrail(state, answers, action)
            cost += guard_cost
            if not guard.passed:
                action = None
    elif route == "llm":
        explanation, llm_cost = await jev.review_with_llm(state, answers)
        cost += llm_cost
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
    if route == "human":
        await store.add_review(decision.decision_id)
    return decision
