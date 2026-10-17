-- Esquema Postgres de 30X Pulse (mismo modelo que CONTRACTS.md).
-- Se carga automáticamente al levantar docker compose por primera vez.

CREATE TABLE IF NOT EXISTS people (
    person_id        TEXT PRIMARY KEY,
    relation         TEXT,             -- mismas categorías del Excel de perfiles de 30X; NULL = sin dato
    crm_status       TEXT,
    crm_stage        TEXT,
    program          TEXT,
    role             TEXT,
    country          TEXT,
    pain             TEXT,
    objective        TEXT,
    interests        JSONB NOT NULL DEFAULT '[]',
    info_level       TEXT NOT NULL DEFAULT 'Baja',
    info_available   TEXT,
    events_attended  INT  NOT NULL DEFAULT 0,
    emails_opened    INT  NOT NULL DEFAULT 0,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS events (
    event_id   TEXT PRIMARY KEY,
    person_id  TEXT NOT NULL REFERENCES people(person_id),
    type       TEXT NOT NULL CHECK (type IN ('signup','attendance','email_open','profile_update')),
    timestamp  TIMESTAMPTZ NOT NULL DEFAULT now(),
    data       JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id    TEXT PRIMARY KEY,
    person_id      TEXT NOT NULL REFERENCES people(person_id),
    event_id       TEXT NOT NULL REFERENCES events(event_id),
    segment        JSONB NOT NULL,   -- {value, p}
    maturity       JSONB NOT NULL,
    sales_ready    JSONB NOT NULL,
    content        JSONB NOT NULL,
    route          TEXT NOT NULL CHECK (route IN ('auto','llm','human')),
    guardrail      JSONB,            -- {passed, p, reason}
    action         TEXT,
    explanation    TEXT,
    latency_ms     REAL NOT NULL,
    cost_usd       DOUBLE PRECISION NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_decisions_person ON decisions(person_id, created_at);
CREATE INDEX IF NOT EXISTS idx_decisions_created ON decisions(created_at DESC);

CREATE TABLE IF NOT EXISTS reviews (
    review_id         TEXT PRIMARY KEY,
    decision_id       TEXT NOT NULL REFERENCES decisions(decision_id),
    status            TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','resolved')),
    resolved_segment  TEXT,
    resolved_action   TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
