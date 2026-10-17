# Contratos de datos — 30X Pulse

Estos formatos son la fuente de verdad. 
El código que los implementa está en `backend/app/models.py`.

`p` = probabilidad calibrada que devuelve JEV (0 a 1).

---

## Person

```json
{
  "person_id": "p_0001",
  "name": "María Gómez",
  "role": "Analista de datos",
  "company": "Banco Andino",
  "industry": "banca",
  "company_size": "1000+",
  "events_attended": 1
}
```

`company_size`: `1-10` | `11-50` | `51-200` | `201-1000` | `1000+`

Solo datos simulados. Nada de personas reales.

## Event

```json
{
  "event_id": "e_000123",
  "person_id": "p_0001",
  "type": "profile_update",
  "timestamp": "2026-10-17T15:04:05Z",
  "data": { "role": "Head of AI" }
}
```

`type`: `signup` | `attendance` | `email_open` | `profile_update`

| type | qué trae `data` |
|---|---|
| `signup` | `{ "event_name": "..." }` (la persona viene completa en el body, ver POST /events) |
| `attendance` | `{ "event_name": "..." }` |
| `email_open` | `{ "email_topic": "..." }` |
| `profile_update` | los campos de Person que cambiaron, ej. `{ "role": "Head of AI" }` |

## Decision

```json
{
  "decision_id": "d_000123",
  "person_id": "p_0001",
  "event_id": "e_000123",
  "segment":     { "value": "lider_adopcion", "p": 0.91 },
  "maturity":    { "value": "alta",           "p": 0.82 },
  "sales_ready": { "value": true,             "p": 0.88 },
  "content":     { "value": "caso_de_exito",  "p": 0.79 },
  "route": "auto",
  "guardrail": { "passed": true, "p": 0.95, "reason": null },
  "action": "notify_sales",
  "explanation": null,
  "latency_ms": 142.3,
  "cost_usd": 0.0000210,
  "created_at": "2026-10-17T15:04:05.300Z"
}
```

- `route`: `auto` (p ≥ 0.85) | `llm` (0.60 ≤ p < 0.85) | `human` (p < 0.60 o segmento `otro`)
- `guardrail`: solo se llena cuando `route = auto`. Si `passed = false`, `action = null`.
- `action`: `send:<content>` | `notify_sales` | `null`
- `explanation`: texto del LLM cuando `route = llm`. En esa ruta el LLM puede **corregir** `segment.value` y `action`; si corrige el segmento, `segment.p` sigue siendo la de JEV y la explicación dice qué había propuesto JEV. Si el LLM falla, se conserva la propuesta de JEV.

## Review (cola humana)

```json
{
  "review_id": "r_0007",
  "decision_id": "d_000123",
  "status": "pending",
  "resolved_segment": null,
  "resolved_action": null,
  "created_at": "2026-10-17T15:04:05Z"
}
```

`status`: `pending` | `resolved`

---

## Preguntas tipadas a JEV (v0, se cierran en el kickoff)

| Clave | Tipo JEV | Opciones |
|---|---|---|
| `segment` | Choice | `explorador`, `lider_negocio`, `lider_tecnico`, `equipo_adopcion`, `lider_adopcion`, `otro` |
| `maturity` | Score | `baja`, `media`, `alta` |
| `sales_ready` | Noul | sí / no |
| `content` | Choice | `intro_ia`, `caso_de_exito`, `taller_practico`, `programa_ejecutivo`, `otro` |

Contar, sumar o comparar fechas (ej. `events_attended`) se hace en código, nunca en JEV.

## Umbrales (v0)

| Probabilidad mínima de `segment` y `sales_ready` | Ruta |
|---|---|
| ≥ 0.85 | `auto` → pasa por guardrail → acción |
| 0.60 – 0.85 | `llm` → el LLM revisa y explica |
| < 0.60, o segmento `otro` | `human` → cola de revisión |

---

## API

Base: `http://localhost:8000` · Docs interactivas: `/docs`

| Método | Ruta | Body / query | Respuesta |
|---|---|---|---|
| POST | `/events` | `{ person_id, type, data, person? }` (`person` obligatorio en `signup`) | `Decision` |
| GET | `/decisions` | `?limit=50&route=auto` | `Decision[]` (más reciente primero) |
| GET | `/metrics` | — | ver abajo |
| GET | `/people/{id}` | — | `{ person, history: [{ at, segment, maturity, sales_ready }] }` |
| GET | `/transitions` | — | `[{ from, to, count }]` (para el Sankey) |
| GET | `/review-queue` | — | `Review[]` pendientes |
| POST | `/review/{review_id}` | `{ segment, action }` | `Review` resuelto |
| POST | `/simulate` | `{ n: 1000 }` | `{ accepted: n }` (corre en segundo plano) |
| GET | `/health` | — | `{ ok, mock_jev }` |

`/metrics`:

```json
{
  "total_decisions": 10000,
  "auto_pct": 71.2, "llm_pct": 19.5, "human_pct": 9.3,
  "guardrail_blocked": 42,
  "total_cost_usd": 0.21,
  "cost_per_1k_usd": 0.021,
  "latency_p50_ms": 140.0, "latency_p95_ms": 410.0,
  "running": false
}
```
