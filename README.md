# 30X Pulse

**Segmentación dinámica en tiempo real con JEV.** Cada señal de una persona que llega a 30X (inscripción en Luma, asistencia, correo abierto, avance en el CRM) la reclasifica en milisegundos y decide qué programa de 30X ofrecerle o si avisar a ventas. Si duda, actúa con prudencia (contenido gratuito, sin avisar a ventas) o le pasa el caso a una persona.

> Los LLM piensan, JEV decide.

Proyecto para el reto **JEV** del Hackathon 30X.

## Cómo funciona

```
Señal → JEV decide (segmento, madurez, ¿lista para ventas?, oferta)
          ├─ p ≥ 0.85      → antispam → Guardrail JEV → acción (enviar oferta / avisar a ventas)
          ├─ 0.60 – 0.85   → acción prudente: contenido gratuito, sin avisar a ventas, por confirmar
          └─ < 0.60 / otro → cola de revisión humana
                                   ↓
                     Ficha de la persona en el CRM (segmento, programa sugerido, ¿lista para ventas?)
```

## Cómo se integra con 30X

30X usa HubSpot como CRM. Detalle y puesta en marcha: [`docs/HubSpot.md`](docs/HubSpot.md).

- **Entrada:** los webhooks de HubSpot (contacto creado, propiedad cambiada, deal con etapa nueva) llegan a `POST /webhooks/hubspot` y se convierten en eventos. Cualquier otra fuente puede usar `POST /events`.
- **Salida:** cada decisión se escribe en propiedades `pulse_*` del contacto (segmento, programa sugerido, ¿lista para ventas?). Los workflows de HubSpot que 30X ya usa deciden qué enviar y a quién avisar. Además, todo queda en la tabla `crm_profiles` (`GET /crm?sales_ready=true`).
- **ID único:** el ID del contacto en HubSpot (`hs_<id>`). Nunca se le envía a JEV, que solo recibe categorías anónimas.
- **Modo sombra:** con `HUBSPOT_SYNC=false`, Pulse decide sin escribir en HubSpot, para comparar antes de encenderlo.
- **Despliegue:** es un contenedor Docker con Postgres. Tablero en Vercel y API en Railway: [`docs/Despliegue.md`](docs/Despliegue.md).

## Correr en local

```bash
cp .env.example .env
docker compose up --build
```

Si ya lo habías levantado antes (antes de los perfiles de 30X o de la tabla `crm_profiles`), borra la base vieja una vez: `docker compose down -v`.

- API: http://localhost:8000
- Docs interactivas: http://localhost:8000/docs

Prueba rápida:

```bash
curl -X POST localhost:8000/simulate -H "Content-Type: application/json" -d '{"n": 1000}'
curl localhost:8000/metrics
```

Evaluación contra el set etiquetado (precisión, precisión por ruta y JEV frente a un LLM):

```bash
docker compose exec backend python -m app.evaluate
docker compose exec backend python -m pytest    # tests
```

Los perfiles ya vienen en `data/`. Para regenerarlos desde el Excel: `python data/build_profiles.py <excel>` (ver [`data/README.md`](data/README.md)).

Sin Docker:

```bash
cd backend
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload     # sin DATABASE_URL guarda en memoria
```

Tablero (en otra terminal, con el backend ya corriendo):

```bash
cd frontend
npm install      # solo la primera vez
npm run dev
```

- Tablero: http://localhost:3000 (usa `NEXT_PUBLIC_API_URL`, por defecto `http://localhost:8000`)

`USE_MOCK_JEV=true` usa respuestas simuladas con la misma forma que las de JEV, para desarrollar sin API key.

## Estructura

| Carpeta | Qué hay | Dueño |
|---|---|---|
| `backend/app/main.py`, `store.py`, `crm.py`, `hubspot.py` | API, almacenamiento, ficha en el CRM, HubSpot | Tech lead |
| `backend/app/decision/` | Llamadas a JEV, umbrales, guardrail, antispam | JEV e IA |
| `data/`, `backend/app/simulate.py`, `evaluate.py` | Perfiles de 30X, set etiquetado, evaluación | Datos |
| `frontend/` | Tablero en Next.js | Frontend |
| `docs/` | Guion del pitch y reparto del equipo | Producto |

## Stack

FastAPI · Postgres · Next.js · JEV (TypeSafe, vía Vercel AI Gateway) · HubSpot · Docker Compose. Sin LLM externo: 30X pidió evitar modelos externos, y la única llamada externa es JEV, con datos anónimos.

## Datos

Los perfiles salen del Excel anónimo que compartió 30X (solo categorías, sin datos personales). Los eventos son simulados.
