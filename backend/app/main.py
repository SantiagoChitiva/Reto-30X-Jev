"""API de 30X Pulse. Los endpoints y sus formas están en CONTRACTS.md."""
from dotenv import load_dotenv

load_dotenv()  # antes de que los demás módulos lean variables de entorno

import asyncio  # noqa: E402
import json  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402
from typing import Optional  # noqa: E402

from fastapi import FastAPI, HTTPException, Query, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from pydantic import ValidationError  # noqa: E402

from . import crm, hubspot, simulate, store  # noqa: E402
from .decision import jev, pipeline  # noqa: E402
from .models import (  # noqa: E402
    CrmRecord,
    Decision,
    EventIn,
    Metrics,
    PersonHistory,
    Review,
    ReviewIn,
    Route,
    SimulateIn,
    Transition,
)

_background: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await store.init_store()
    yield
    for task in _background:
        task.cancel()
    await jev.aclose()
    await hubspot.aclose()
    await store.close_store()


app = FastAPI(title="30X Pulse", description="Segmentación dinámica en tiempo real con JEV.", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # tablero Next.js
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/events", response_model=Decision)
async def post_event(ev: EventIn):
    try:
        return await pipeline.process_event(ev)
    except store.NotFound as e:
        raise HTTPException(404, str(e))
    except ValidationError as e:  # profile_update con un valor inválido
        raise HTTPException(422, e.errors(include_url=False, include_context=False))


@app.post("/webhooks/hubspot")
async def hubspot_webhook(request: Request):
    """Webhooks de HubSpot (contactos y deals) → eventos de Pulse. Ver app/hubspot.py."""
    body = await request.body()
    if not hubspot.verify_signature(request.method, str(request.url), body,
                                    request.headers.get("X-HubSpot-Signature-v3"),
                                    request.headers.get("X-HubSpot-Request-Timestamp")):
        raise HTTPException(401, "Firma de HubSpot inválida")
    try:
        events = json.loads(body or b"[]")
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(400, "El cuerpo debe ser JSON en UTF-8")
    if isinstance(events, dict):
        events = [events]

    st = store.get_store()

    async def exists(pid: str) -> bool:
        return await st.get_person(pid) is not None

    # Cada persona en orden; personas distintas en paralelo
    by_person: dict[str, list[dict]] = {}
    ignored = 0
    for ev in events:
        if hubspot.already_seen(ev):
            ignored += 1
            continue
        by_person.setdefault(str(ev.get("objectId")), []).append(ev)

    async def run(group: list[dict]) -> list[str]:
        ids = []
        for ev in group:
            for pulse_event in await hubspot.to_events(ev, exists):
                try:
                    ids.append((await pipeline.process_event(pulse_event)).decision_id)
                except (store.NotFound, ValidationError):
                    pass
        return ids

    results = await asyncio.gather(*(run(g) for g in by_person.values()))
    decisions = [d for r in results for d in r]
    return {"received": len(events), "ignored": ignored, "decisions": decisions}


@app.get("/decisions", response_model=list[Decision])
async def get_decisions(limit: int = Query(50, ge=1, le=1000), route: Optional[Route] = None):
    return await store.get_store().list_decisions(limit, route)


@app.get("/metrics", response_model=Metrics)
async def get_metrics():
    m = await store.get_store().metrics()
    total = m["total"]
    cost = float(m["cost"])

    def pct(key: str) -> float:
        return round(100 * m[key] / total, 1) if total else 0.0

    return Metrics(
        total_decisions=total,
        auto_pct=pct("auto"),
        safe_pct=pct("safe"),
        human_pct=pct("human"),
        guardrail_blocked=m["blocked"],
        spam_suppressed=m["spam"],
        total_cost_usd=round(cost, 6),
        cost_per_1k_usd=round(cost / total * 1000, 6) if total else 0.0,
        latency_p50_ms=round(float(m["p50"]), 1),
        latency_p95_ms=round(float(m["p95"]), 1),
        running=simulate.running,
    )


@app.get("/people/{person_id}", response_model=PersonHistory)
async def get_person(person_id: str):
    history = await store.get_store().person_history(person_id)
    if history is None:
        raise HTTPException(404, f"La persona {person_id} no existe")
    return history


@app.get("/transitions", response_model=list[Transition])
async def get_transitions():
    return await store.get_store().transitions()


@app.get("/review-queue", response_model=list[Review])
async def get_review_queue():
    return await store.get_store().pending_reviews()


@app.post("/review/{review_id}", response_model=Review)
async def resolve_review(review_id: str, body: ReviewIn):
    st = store.get_store()
    try:
        review = await st.resolve_review(review_id, body.segment, body.action)
    except store.NotFound as e:
        raise HTTPException(404, str(e))
    except store.AlreadyResolved as e:
        raise HTTPException(409, str(e))
    decision = await st.get_decision(review.decision_id)
    if decision is not None:
        await crm.write(crm.from_review(review, decision))
    return review


@app.get("/crm", response_model=list[CrmRecord])
async def get_crm(limit: int = Query(50, ge=1, le=1000), sales_ready: Optional[bool] = None):
    """Fichas del CRM, de la más reciente a la más antigua. `sales_ready=true` = la lista de ventas."""
    return await store.get_store().list_crm(limit, sales_ready)


@app.get("/crm/{person_id}", response_model=CrmRecord)
async def get_crm_record(person_id: str):
    record = await store.get_store().crm_record(person_id)
    if record is None:
        raise HTTPException(404, f"La persona {person_id} todavía no tiene ficha en el CRM")
    return record


@app.post("/simulate")
async def post_simulate(body: SimulateIn):
    if simulate.running:
        raise HTTPException(409, "Ya hay una simulación corriendo")
    simulate.running = True  # visible en /metrics desde ya
    task = asyncio.create_task(simulate.run(body.n))
    _background.add(task)
    task.add_done_callback(_background.discard)
    return {"accepted": body.n}


@app.get("/evaluation")
async def get_evaluation():
    """Último resultado de `python -m app.evaluate` (precisión vs set etiquetado y JEV vs un LLM)."""
    path = simulate.data_dir() / "eval_results.json"
    if not path.exists():
        raise HTTPException(404, "Aún no hay evaluación. Córrela con: python -m app.evaluate")
    return json.loads(path.read_text(encoding="utf-8"))


@app.get("/health")
async def health():
    return {"ok": True, "mock_jev": jev.use_mock()}
