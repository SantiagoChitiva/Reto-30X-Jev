# 30X Pulse

**Segmentación dinámica en tiempo real con JEV.** Cada señal de una persona (inscripción, asistencia, correo abierto, cambio de cargo) la reclasifica en milisegundos y decide qué contenido u oferta debe recibir. Los casos dudosos escalan a un LLM o a una persona.

> Los LLM piensan, JEV decide.

Proyecto para el reto **JEV** del Hackathon 30X.

## Cómo funciona

```
Señal → JEV decide (segmento, madurez, ¿lista para ventas?, contenido)
          ├─ p ≥ 0.85      → Guardrail JEV → acción (enviar contenido / avisar a ventas)
          ├─ 0.60 – 0.85   → LLM revisa y explica
          └─ < 0.60 / otro → cola de revisión humana
```

Detalle de datos, preguntas tipadas, umbrales y API: [`CONTRACTS.md`](CONTRACTS.md).

## Correr en local

```bash
cp .env.example .env
docker compose up --build
```

- API: http://localhost:8000
- Docs interactivas: http://localhost:8000/docs

Prueba rápida:

```bash
curl -X POST localhost:8000/simulate -H "Content-Type: application/json" -d '{"n": 1000}'
curl localhost:8000/metrics
```

Sin Docker:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
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
| `backend/app/main.py`, `store.py` | API, almacenamiento, orquestación | Tech lead |
| `backend/app/decision/` | Llamadas a JEV, umbrales, guardrail, LLM | JEV e IA |
| `data/`, `backend/app/simulate.py` | Datos sintéticos, set etiquetado, evaluación | Datos |
| `frontend/` | Tablero en Next.js | Frontend |
| `docs/` | Playbook y pitch | Producto |

## Stack

FastAPI · Postgres · Next.js · JEV (TypeSafe, vía Vercel AI Gateway) · LLM para el camino lento · Docker Compose

## Datos

Todos los datos son simulados. No se usan datos personales reales.
