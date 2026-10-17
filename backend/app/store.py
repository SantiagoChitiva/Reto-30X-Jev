"""Dónde se guardan los datos.

- Sin `DATABASE_URL`: en memoria (se borra al reiniciar). Sirve para desarrollo y tests.
- Con `DATABASE_URL` (docker compose la define): Postgres con las tablas de `db/schema.sql`.

Las dos clases tienen los mismos métodos, así que el resto del sistema no sabe cuál usa.
"""
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Optional, Union

from .decision.policy import SPAM_REASON
from .models import (
    UPDATABLE_FIELDS,
    CrmRecord,
    Decision,
    Event,
    EventIn,
    HistoryItem,
    Person,
    PersonHistory,
    Review,
    Route,
    Transition,
)

# Ancho de los IDs, como en CONTRACTS.md: p_0001, e_000123, d_000123, r_0007
_ID_WIDTH = {"p": 4, "e": 6, "d": 6, "r": 4}
RECENT_EVENTS = 5  # eventos anteriores que se le pasan a JEV como contexto


class NotFound(LookupError):
    """La persona o el review no existe."""


class AlreadyResolved(ValueError):
    """El review ya estaba resuelto."""


def now() -> datetime:
    return datetime.now(timezone.utc)


def apply_to_person(current: Optional[Person], ev: EventIn) -> Person:
    """Cómo cambia la persona con un evento. Se calcula en código, nunca en JEV."""
    if ev.type == "signup":
        return ev.person
    if current is None:
        raise NotFound(f"La persona {ev.person_id} no existe; su primer evento debe ser signup")
    if ev.type == "attendance":
        return current.model_copy(update={"events_attended": current.events_attended + 1})
    if ev.type == "profile_update":
        changes = {k: v for k, v in ev.data.items() if k in UPDATABLE_FIELDS}
        return Person.model_validate({**current.model_dump(), **changes})
    if ev.type == "email_open":
        return current.model_copy(update={"emails_opened": current.emails_opened + 1})
    return current


def _percentile(sorted_values: list[float], q: float) -> float:
    """Percentil con interpolación lineal (igual que percentile_cont de Postgres)."""
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * q
    lo = int(k)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (k - lo)


class MemoryStore:
    def __init__(self) -> None:
        self.people: dict[str, Person] = {}
        self.events: defaultdict[str, list[Event]] = defaultdict(list)
        self.decisions: list[Decision] = []
        self.decisions_by_person: defaultdict[str, list[Decision]] = defaultdict(list)
        self.reviews: dict[str, Review] = {}
        self.crm: dict[str, CrmRecord] = {}
        self._seq: Counter[str] = Counter()

    async def open(self) -> None:
        pass

    async def close(self) -> None:
        pass

    def next_id(self, prefix: str) -> str:
        while True:
            self._seq[prefix] += 1
            new_id = f"{prefix}_{self._seq[prefix]:0{_ID_WIDTH[prefix]}d}"
            if prefix != "p" or new_id not in self.people:
                return new_id

    async def apply_event(self, ev: EventIn) -> tuple[Person, Event, list[Event]]:
        """Actualiza la persona y guarda el evento. Devuelve (persona, evento, eventos anteriores)."""
        person = apply_to_person(self.people.get(ev.person_id), ev)
        self.people[person.person_id] = person
        history = self.events[person.person_id]
        recent = history[-RECENT_EVENTS:]
        event = Event(event_id=self.next_id("e"), person_id=person.person_id, type=ev.type,
                      timestamp=now(), data=ev.data)
        history.append(event)
        return person, event, recent

    async def save_decision(self, d: Decision) -> None:
        self.decisions.append(d)
        self.decisions_by_person[d.person_id].append(d)

    async def add_review(self, decision_id: str) -> Review:
        review = Review(review_id=self.next_id("r"), decision_id=decision_id, created_at=now())
        self.reviews[review.review_id] = review
        return review

    async def has_pending_review(self, person_id: str) -> bool:
        mine = {d.decision_id for d in self.decisions_by_person[person_id]}
        return any(r.status == "pending" and r.decision_id in mine for r in self.reviews.values())

    async def recent_actions(self, person_id: str, n: int) -> list[Optional[str]]:
        """Acciones de las últimas n decisiones de la persona (para el antispam)."""
        return [d.action for d in self.decisions_by_person[person_id][-n:]]

    async def list_decisions(self, limit: int, route: Optional[Route] = None) -> list[Decision]:
        out = []
        for d in reversed(self.decisions):
            if route is None or d.route == route:
                out.append(d)
                if len(out) >= limit:
                    break
        return out

    async def metrics(self) -> dict[str, Any]:
        ds = self.decisions
        routes = Counter(d.route for d in ds)
        latencies = sorted(d.latency_ms for d in ds)
        return {
            "total": len(ds),
            "auto": routes["auto"], "llm": routes["llm"], "human": routes["human"],
            "blocked": sum(1 for d in ds if d.guardrail is not None and not d.guardrail.passed
                           and not (d.guardrail.reason or "").startswith(SPAM_REASON)),
            "spam": sum(1 for d in ds if SPAM_REASON in ((d.guardrail and d.guardrail.reason) or "")
                        or SPAM_REASON in (d.explanation or "")),
            "cost": sum(d.cost_usd for d in ds),
            "p50": _percentile(latencies, 0.5),
            "p95": _percentile(latencies, 0.95),
        }

    async def person_history(self, person_id: str) -> Optional[PersonHistory]:
        person = self.people.get(person_id)
        if person is None:
            return None
        history = [
            HistoryItem(at=d.created_at, segment=d.segment.value, maturity=d.maturity.value,
                        sales_ready=d.sales_ready.value)
            for d in self.decisions_by_person[person_id]
        ]
        return PersonHistory(person=person, history=history)

    async def transitions(self) -> list[Transition]:
        """Cambios de segmento entre decisiones consecutivas de la misma persona."""
        counts: Counter[tuple[str, str]] = Counter()
        for ds in self.decisions_by_person.values():
            for prev, cur in zip(ds, ds[1:]):
                if prev.segment.value != cur.segment.value:
                    counts[(prev.segment.value, cur.segment.value)] += 1
        return [Transition(from_=a, to=b, count=n) for (a, b), n in counts.most_common()]

    async def get_decision(self, decision_id: str) -> Optional[Decision]:
        return next((d for d in self.decisions if d.decision_id == decision_id), None)

    async def upsert_crm(self, record: CrmRecord) -> None:
        self.crm[record.person_id] = record

    async def crm_record(self, person_id: str) -> Optional[CrmRecord]:
        return self.crm.get(person_id)

    async def list_crm(self, limit: int, sales_ready: Optional[bool] = None) -> list[CrmRecord]:
        rows = [r for r in self.crm.values() if sales_ready is None or r.sales_ready == sales_ready]
        return sorted(rows, key=lambda r: r.updated_at, reverse=True)[:limit]

    async def pending_reviews(self) -> list[Review]:
        return [r for r in self.reviews.values() if r.status == "pending"]

    async def resolve_review(self, review_id: str, segment: str, action: Optional[str]) -> Review:
        review = self.reviews.get(review_id)
        if review is None:
            raise NotFound(f"El review {review_id} no existe")
        if review.status == "resolved":
            raise AlreadyResolved(f"{review_id} ya está resuelto")
        review = review.model_copy(update={"status": "resolved", "resolved_segment": segment,
                                           "resolved_action": action})
        self.reviews[review_id] = review
        return review


async def _init_connection(conn) -> None:
    await conn.set_type_codec("jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog")


_PERSON_COLUMNS = tuple(Person.model_fields)


def _person(row) -> Person:
    return Person(**{k: row[k] for k in _PERSON_COLUMNS})


def _decision(row) -> Decision:
    d = dict(row)
    d["latency_ms"] = round(d["latency_ms"], 1)  # REAL → float32
    return Decision.model_validate(d)


_CRM_COLUMNS = tuple(CrmRecord.model_fields)


def _crm(row) -> CrmRecord:
    d = dict(row)
    d["confidence"] = round(d["confidence"], 4)  # REAL → float32
    return CrmRecord.model_validate(d)


_UPSERT_PERSON = (
    f"INSERT INTO people ({', '.join(_PERSON_COLUMNS)}, updated_at) "
    f"VALUES ({', '.join(f'${i + 1}' for i in range(len(_PERSON_COLUMNS)))}, now()) "
    "ON CONFLICT (person_id) DO UPDATE SET "
    + ", ".join(f"{k} = EXCLUDED.{k}" for k in _PERSON_COLUMNS[1:])
    + ", updated_at = now()"
)


class PgStore:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.pool = None
        self._seq: Counter[str] = Counter()

    async def open(self) -> None:
        import asyncpg

        size = max(2, int(os.getenv("MAX_CONCURRENCY", "50")))  # una conexión por evento en vuelo
        self.pool = await asyncpg.create_pool(self.dsn, min_size=2, max_size=size, init=_init_connection)
        # Los contadores siguen desde el último ID guardado, para no chocar al reiniciar.
        tables = (("p", "people", "person_id"), ("e", "events", "event_id"),
                  ("d", "decisions", "decision_id"), ("r", "reviews", "review_id"))
        async with self.pool.acquire() as c:
            for prefix, table, column in tables:
                last = await c.fetchval(
                    f"SELECT COALESCE(MAX(NULLIF(regexp_replace({column}, '\\D', '', 'g'), '')::numeric), 0) "
                    f"FROM {table}"
                )
                self._seq[prefix] = int(last)

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()

    def next_id(self, prefix: str) -> str:
        self._seq[prefix] += 1
        return f"{prefix}_{self._seq[prefix]:0{_ID_WIDTH[prefix]}d}"

    async def apply_event(self, ev: EventIn) -> tuple[Person, Event, list[Event]]:
        async with self.pool.acquire() as c, c.transaction():
            row = await c.fetchrow("SELECT * FROM people WHERE person_id = $1 FOR UPDATE", ev.person_id)
            person = apply_to_person(_person(row) if row else None, ev)
            await c.execute(_UPSERT_PERSON, *(getattr(person, k) for k in _PERSON_COLUMNS))
            rows = await c.fetch(
                "SELECT event_id, person_id, type, timestamp, data FROM events "
                "WHERE person_id = $1 ORDER BY timestamp DESC, event_id DESC LIMIT $2",
                person.person_id, RECENT_EVENTS,
            )
            recent = [Event(**dict(r)) for r in reversed(rows)]
            event = Event(event_id=self.next_id("e"), person_id=person.person_id, type=ev.type,
                          timestamp=now(), data=ev.data)
            await c.execute(
                "INSERT INTO events (event_id, person_id, type, timestamp, data) VALUES ($1, $2, $3, $4, $5)",
                event.event_id, event.person_id, event.type, event.timestamp, event.data,
            )
        return person, event, recent

    async def save_decision(self, d: Decision) -> None:
        await self.pool.execute(
            """
            INSERT INTO decisions (decision_id, person_id, event_id, segment, maturity, sales_ready, content,
                                   route, guardrail, action, explanation, latency_ms, cost_usd, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            """,
            d.decision_id, d.person_id, d.event_id, d.segment.model_dump(), d.maturity.model_dump(),
            d.sales_ready.model_dump(), d.content.model_dump(), d.route,
            d.guardrail.model_dump() if d.guardrail else None, d.action, d.explanation,
            d.latency_ms, d.cost_usd, d.created_at,
        )

    async def add_review(self, decision_id: str) -> Review:
        review = Review(review_id=self.next_id("r"), decision_id=decision_id, created_at=now())
        await self.pool.execute(
            "INSERT INTO reviews (review_id, decision_id, status, created_at) VALUES ($1, $2, $3, $4)",
            review.review_id, review.decision_id, review.status, review.created_at,
        )
        return review

    async def has_pending_review(self, person_id: str) -> bool:
        return bool(await self.pool.fetchval(
            "SELECT 1 FROM reviews r JOIN decisions d USING (decision_id) "
            "WHERE d.person_id = $1 AND r.status = 'pending' LIMIT 1",
            person_id,
        ))

    async def recent_actions(self, person_id: str, n: int) -> list[Optional[str]]:
        rows = await self.pool.fetch(
            "SELECT action FROM decisions WHERE person_id = $1 ORDER BY created_at DESC, decision_id DESC LIMIT $2",
            person_id, n,
        )
        return [r["action"] for r in reversed(rows)]

    async def list_decisions(self, limit: int, route: Optional[Route] = None) -> list[Decision]:
        if route:
            rows = await self.pool.fetch(
                "SELECT * FROM decisions WHERE route = $2 ORDER BY created_at DESC, decision_id DESC LIMIT $1",
                limit, route,
            )
        else:
            rows = await self.pool.fetch(
                "SELECT * FROM decisions ORDER BY created_at DESC, decision_id DESC LIMIT $1", limit,
            )
        return [_decision(r) for r in rows]

    async def metrics(self) -> dict[str, Any]:
        row = await self.pool.fetchrow(
            f"""
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE route = 'auto') AS auto,
                   count(*) FILTER (WHERE route = 'llm') AS llm,
                   count(*) FILTER (WHERE route = 'human') AS human,
                   count(*) FILTER (WHERE (guardrail->>'passed')::boolean IS FALSE
                                    AND COALESCE(guardrail->>'reason', '') NOT LIKE '{SPAM_REASON}%') AS blocked,
                   count(*) FILTER (WHERE COALESCE(guardrail->>'reason', '') LIKE '{SPAM_REASON}%'
                                    OR COALESCE(explanation, '') LIKE '%{SPAM_REASON}%') AS spam,
                   COALESCE(sum(cost_usd), 0) AS cost,
                   COALESCE(percentile_cont(0.5) WITHIN GROUP (ORDER BY latency_ms), 0) AS p50,
                   COALESCE(percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms), 0) AS p95
            FROM decisions
            """
        )
        return dict(row)

    async def person_history(self, person_id: str) -> Optional[PersonHistory]:
        async with self.pool.acquire() as c:
            row = await c.fetchrow("SELECT * FROM people WHERE person_id = $1", person_id)
            if row is None:
                return None
            rows = await c.fetch(
                """
                SELECT created_at AS at, segment->>'value' AS segment, maturity->>'value' AS maturity,
                       (sales_ready->>'value')::boolean AS sales_ready
                FROM decisions WHERE person_id = $1 ORDER BY created_at, decision_id
                """,
                person_id,
            )
        return PersonHistory(person=_person(row), history=[HistoryItem(**dict(r)) for r in rows])

    async def transitions(self) -> list[Transition]:
        rows = await self.pool.fetch(
            """
            SELECT prev AS from_, seg AS to, count(*) AS count
            FROM (
                SELECT segment->>'value' AS seg,
                       LAG(segment->>'value') OVER (PARTITION BY person_id ORDER BY created_at, decision_id) AS prev
                FROM decisions
            ) t
            WHERE prev IS NOT NULL AND prev <> seg
            GROUP BY prev, seg
            ORDER BY count DESC
            """
        )
        return [Transition(**dict(r)) for r in rows]

    async def get_decision(self, decision_id: str) -> Optional[Decision]:
        row = await self.pool.fetchrow("SELECT * FROM decisions WHERE decision_id = $1", decision_id)
        return _decision(row) if row else None

    async def upsert_crm(self, r: CrmRecord) -> None:
        await self.pool.execute(
            f"INSERT INTO crm_profiles ({', '.join(_CRM_COLUMNS)}) "
            f"VALUES ({', '.join(f'${i + 1}' for i in range(len(_CRM_COLUMNS)))}) "
            "ON CONFLICT (person_id) DO UPDATE SET "
            + ", ".join(f"{k} = EXCLUDED.{k}" for k in _CRM_COLUMNS[1:]),
            *(getattr(r, k) for k in _CRM_COLUMNS),
        )

    async def crm_record(self, person_id: str) -> Optional[CrmRecord]:
        row = await self.pool.fetchrow("SELECT * FROM crm_profiles WHERE person_id = $1", person_id)
        return _crm(row) if row else None

    async def list_crm(self, limit: int, sales_ready: Optional[bool] = None) -> list[CrmRecord]:
        if sales_ready is None:
            rows = await self.pool.fetch("SELECT * FROM crm_profiles ORDER BY updated_at DESC LIMIT $1", limit)
        else:
            rows = await self.pool.fetch(
                "SELECT * FROM crm_profiles WHERE sales_ready = $2 ORDER BY updated_at DESC LIMIT $1",
                limit, sales_ready,
            )
        return [_crm(r) for r in rows]

    async def pending_reviews(self) -> list[Review]:
        rows = await self.pool.fetch("SELECT * FROM reviews WHERE status = 'pending' ORDER BY created_at")
        return [Review(**dict(r)) for r in rows]

    async def resolve_review(self, review_id: str, segment: str, action: Optional[str]) -> Review:
        row = await self.pool.fetchrow(
            """
            UPDATE reviews SET status = 'resolved', resolved_segment = $2, resolved_action = $3
            WHERE review_id = $1 AND status = 'pending' RETURNING *
            """,
            review_id, segment, action,
        )
        if row is not None:
            return Review(**dict(row))
        if await self.pool.fetchval("SELECT 1 FROM reviews WHERE review_id = $1", review_id):
            raise AlreadyResolved(f"{review_id} ya está resuelto")
        raise NotFound(f"El review {review_id} no existe")


Store = Union[MemoryStore, PgStore]
_store: Optional[Store] = None


async def init_store() -> Store:
    global _store
    dsn = os.getenv("DATABASE_URL")
    _store = PgStore(dsn) if dsn else MemoryStore()
    await _store.open()
    return _store


def get_store() -> Store:
    if _store is None:
        raise RuntimeError("El store no está inicializado (lo abre el lifespan de main.py)")
    return _store


async def close_store() -> None:
    global _store
    if _store is not None:
        await _store.close()
        _store = None
