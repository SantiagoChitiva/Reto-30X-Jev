# Contratos de datos — 30X Pulse

Estos formatos son la fuente de verdad. 
El código que los implementa está en `backend/app/models.py`.

`p` = probabilidad calibrada que devuelve JEV (0 a 1).

---

## Person

Perfil anónimo con las **mismas categorías del Excel de perfiles de 30X** (`data/perfiles_30x.json`). Sin nombres ni empresas. `null` = sin dato.

```json
{
  "person_id": "p_0001",
  "relation": "Deal en el CRM",
  "crm_status": "En proceso",
  "crm_stage": "Calificado",
  "program": "AI Sales",
  "role": "Fundador, socio o CEO",
  "country": null,
  "pain": "Vive de referidos y prospecta a mano",
  "objective": "Vender más",
  "interests": ["sales", "ai", "gtm"],
  "info_level": "Alta",
  "info_available": "Perfil con contexto (dolor u objetivo)",
  "events_attended": 2,
  "emails_opened": 1
}
```

- `info_level`: `Baja` | `Media` | `Alta`
- `events_attended` y `emails_opened` los cuenta el código (`attendance` y `email_open`), nunca JEV.
- Los leads no tienen `role`: en el Excel ese campo solo existe cuando hay deal.

Solo datos anónimos o simulados. Nada de personas reales.

## Event

```json
{
  "event_id": "e_000123",
  "person_id": "p_0001",
  "type": "profile_update",
  "timestamp": "2026-10-17T15:04:05Z",
  "data": { "crm_stage": "Calificado" }
}
```

`type`: `signup` | `attendance` | `email_open` | `profile_update`

| type | qué trae `data` |
|---|---|
| `signup` | `{ "event_name": "..." }` (la persona viene completa en el body, ver POST /events) |
| `attendance` | `{ "event_name": "..." }` |
| `email_open` | `{ "email_topic": "..." }` |
| `profile_update` | los campos de Person que cambiaron, ej. `{ "relation": "Deal en el CRM", "role": "Líder comercial o de ventas" }` |

## Decision

```json
{
  "decision_id": "d_000123",
  "person_id": "p_0001",
  "event_id": "e_000123",
  "segment":     { "value": "fundador_ventas", "p": 0.91 },
  "maturity":    { "value": "media",           "p": 0.82 },
  "sales_ready": { "value": true,              "p": 0.88 },
  "content":     { "value": "ai_sales",        "p": 0.79 },
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
- `guardrail`: solo se llena cuando `route = auto`. Si `passed = false`, `action = null`. Si lo frenó el antispam, `reason` empieza por `Frenada por frecuencia`.
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

## CrmRecord (ficha en el CRM)

Lo que el sistema escribe de vuelta: la última decisión sobre cada persona, como propiedades de su ficha. 30X pidió trabajarlo por ahora como una base de datos, así que vive en la tabla `crm_profiles`. Con el CRM real son las mismas propiedades, y solo cambia `backend/app/crm.py`.

```json
{
  "person_id": "p_0001",
  "segment": "fundador_ventas",
  "maturity": "media",
  "sales_ready": true,
  "suggested_program": "sales_machine",
  "confidence": 0.91,
  "decided_by": "jev",
  "last_action": "notify_sales",
  "decision_id": "d_000123",
  "updated_at": "2026-10-17T15:04:05Z"
}
```

- `suggested_program`: la oferta (`content`), igual que la columna «Programa sugerido» del Excel de 30X.
- `confidence`: la `p` más baja entre `segment` y `sales_ready`; `1.0` si lo decidió una persona.
- `decided_by`: `jev` (ruta `auto`) | `llm` | `humano` (al resolver la cola). La ruta `human` no escribe nada hasta que una persona resuelva el caso.

---

## Preguntas tipadas a JEV (v1)

Una sola llamada por evento. JEV recibe `{ person, signals, event, recent_events }`; `signals` trae los conteos ya calculados en código.

| Clave | Tipo JEV | Opciones |
|---|---|---|
| `segment` | Choice | `fundador_ventas`, `fundador_escala`, `lider_comercial`, `ejecutivo_ia`, `perfil_tecnico`, `explorador`, `otro` |
| `maturity` | Score | `baja`, `media`, `alta` (madurez de su empresa en IA) |
| `sales_ready` | Noul | sí / no (¿lista para que la contacte el equipo comercial?) |
| `content` | Choice | `ai_sales`, `inmersion_ejecutiva`, `sales_machine`, `hardcore_ai`, `achievers`, `nutricion`, `otro` |

`content` es la **oferta**: solo programas que 30X vende (los del Excel) o `nutricion` (contenido gratuito). Igual que la afinidad de 30X, mide si la persona encaja con el perfil de cada programa; los criterios de cada opción salen de 30x.com/programas y están en `backend/app/decision/jev.py`.

Contar, sumar o comparar fechas se hace en código, nunca en JEV.

Guardrail (segunda llamada, solo en `auto` y con acción): Noul `apropiada`. ¿La acción respeta el perfil y la línea editorial de 30X?

## Umbrales (v1)

| Probabilidad mínima de `segment` y `sales_ready` | Ruta |
|---|---|
| ≥ 0.85 | `auto` → antispam → guardrail JEV (≥ 0.85) → acción |
| 0.60 – 0.85 | `llm` → el LLM revisa y explica |
| < 0.60, o segmento `otro` | `human` → cola de revisión (una sola pendiente por persona) |

**Antispam (en código, antes de JEV):** si la misma acción salió en las últimas 3 decisiones de la persona, no se repite.

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
| POST | `/review/{review_id}` | `{ segment, action }` | `Review` resuelto (y actualiza la ficha del CRM) |
| GET | `/crm` | `?limit=50&sales_ready=true` | `CrmRecord[]` (más reciente primero) |
| GET | `/crm/{id}` | — | `CrmRecord` (404 si aún no tiene ficha) |
| POST | `/simulate` | `{ n: 1000 }` | `{ accepted: n }` (corre en segundo plano) |
| GET | `/evaluation` | — | último resultado de `python -m app.evaluate` (404 si no se ha corrido) |
| GET | `/health` | — | `{ ok, mock_jev }` |

`/metrics`:

```json
{
  "total_decisions": 10000,
  "auto_pct": 71.2, "llm_pct": 19.5, "human_pct": 9.3,
  "guardrail_blocked": 42,
  "spam_suppressed": 310,
  "total_cost_usd": 0.21,
  "cost_per_1k_usd": 0.021,
  "latency_p50_ms": 140.0, "latency_p95_ms": 410.0,
  "running": false
}
```
