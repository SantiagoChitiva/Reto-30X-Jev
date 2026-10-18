# 30X Pulse: qué hay en el repo y qué hace cada uno

## Qué hace el sistema hoy

El backend ya funciona de punta a punta, pero con **un JEV simulado**: responde con el mismo formato que el JEV real, para que nadie tenga que esperar la API para avanzar.

El recorrido de cada evento:

1. Llega un **evento**, por ejemplo "María se inscribió" o "María cambió de cargo".
2. Se le pregunta a **JEV** (por ahora el simulado) qué tipo de persona es, qué tan madura está en IA, si está lista para ventas y qué contenido le sirve. Cada respuesta trae un porcentaje de seguridad.
3. Según ese porcentaje, el sistema decide el camino:
   - **Seguro (85% o más):** actúa solo, pero antes pasa por el **guardrail**, una segunda revisión de JEV.
   - **Más o menos seguro (60% a 85%):** acción **prudente**: contenido gratuito, sin avisar a ventas, y queda «por confirmar».
   - **Inseguro (menos de 60%):** va a la **cola de revisión** de una persona.
4. Se guarda la decisión y queda disponible para el tablero.

Probado: 10.000 eventos se procesan en unos 16 segundos.

## Qué hace cada archivo

### En la raíz

| Archivo | Para qué sirve |
|---|---|
| `CONTRACTS.md` | **El más importante.** Cómo se ven los datos (persona, evento, decisión), las preguntas a JEV, los umbrales y los endpoints. Es el acuerdo del equipo: si alguien lo cambia, avisa a todos. |
| `README.md` | Qué es el proyecto y cómo correrlo. |
| `docker-compose.yml` | Levanta la API y la base de datos Postgres con un solo comando. |
| `.env.example` | Plantilla de configuración (API keys, modo simulado). Se copia a `.env`, que nunca se sube a GitHub. |
| `.gitignore` | Lo que Git ignora: claves, `node_modules`, archivos temporales. |

### En `backend/app/` (el cerebro)

| Archivo | Para qué sirve |
|---|---|
| `main.py` | Todos los endpoints de la API: recibir eventos, listar decisiones, métricas, cola humana y simular. |
| `models.py` | Los formatos de `CONTRACTS.md` escritos en código. |
| `store.py` | Dónde se guardan los datos. Por ahora en memoria, así que se borran al reiniciar. Pasa a Postgres en el primer bloque de trabajo. |
| `simulate.py` | Genera personas y eventos falsos para probar y para la demo. |
| `decision/jev.py` | Donde se habla con JEV, hoy en modo simulado. También tiene el guardrail. |
| `decision/policy.py` | Los umbrales (85% y 60%) y la regla de qué acción tomar. |
| `decision/pipeline.py` | Une todo: evento → JEV → umbral → guardrail, acción prudente o persona → se guarda la decisión. |

### Otros

- `backend/db/schema.sql`: las tablas de Postgres. Se crean solas al levantar Docker.
- `frontend/`, `data/` y `docs/`: por ahora solo tienen un README con lo que va en cada una.

## Cómo correrlo

```bash
cp .env.example .env
docker compose up --build
```

Abran http://localhost:8000/docs. Ahí se prueban todos los endpoints desde el navegador, sin escribir código.

---

## Qué hace cada uno

### Persona 1: Santiago · Backend e integración

**Archivos:** `backend/app/main.py`, `store.py`, `pipeline.py` y `docker-compose.yml`.

1. Pasar el almacenamiento de memoria a Postgres.
2. Desplegar temprano (backend en Railway y base de datos en Supabase), aunque se vea feo.
3. Ir conectando lo que cada uno entregue al sistema.
4. Agregar el **modo replay**, para que la demo funcione aunque falle el internet.

### Persona 2: JEV e IA

**Archivos:** `backend/app/decision/jev.py` y, si hace falta, `policy.py`.

1. Conseguir el acceso a JEV (por Vercel AI Gateway) y hacer una llamada de prueba **lo antes posible**.
2. Reemplazar el JEV simulado por el real en la función `_call_jev_real`.
3. Hacer real el **guardrail**, la segunda revisión antes de actuar.
4. ~~Hacer real el LLM de los casos dudosos~~: descartado, 30X pidió evitar modelos externos. Esos casos llevan una acción prudente.
5. Guardar las respuestas reales de JEV en `data/replay.jsonl`, para el modo replay de la demo.
6. Cuando funcione, poner `USE_MOCK_JEV=false` en el `.env`.

No cambies el formato de las respuestas. Si lo respetas, el resto del sistema no se entera del cambio.

### Persona 3: Datos y evaluación

> **Estado:** los puntos 1, 2, 4 y 5 ya están hechos (`data/build_profiles.py`, `simulate.py`, `python -m app.evaluate`). Falta el punto 3: revisar a mano `segment_ref` en `data/labeled_set.json` y marcar `"revisado": true`.

**Archivos:** la carpeta `data/` y `backend/app/simulate.py`.

1. Crear perfiles falsos pero realistas, basados en los ejemplos de perfiles que compartió 30X.
2. Ajustar `simulate.py` para que use esos perfiles en lugar de las listas de prueba.
3. Etiquetar a mano unas **200 personas** con el segmento correcto. Ese es el "examen" para medir a JEV.
4. Hacer un script que compare lo que dice JEV con esas etiquetas y calcule qué porcentaje acierta.
5. Medir costo y velocidad de JEV frente a un LLM normal con las mismas personas. **Esos números son el corazón del pitch.**

### Persona 4: Frontend

**Archivos:** la carpeta `frontend/`. Puedes empezar ya, porque la API funciona con datos simulados.

1. Crear el proyecto con Next.js (el comando está en `frontend/README.md`).
2. Construir estas pantallas, en este orden:
   1. **Feed en vivo** de decisiones que se refresca cada segundo (`GET /decisions`).
   2. **Indicadores:** costo total, % automático y velocidad (`GET /metrics`).
   3. **Botón "Simular 10.000"** (`POST /simulate`). Es el momento WOW de la demo.
   4. **Sankey:** cómo las personas cambian de segmento (`GET /transitions`).
   5. **Cola humana:** donde una persona resuelve los casos dudosos (`GET /review-queue`).
3. Si el tiempo no alcanza, el Sankey puede ser un gráfico de barras.

### Persona 5: Producto y pitch

**Archivos:** la carpeta `docs/`.

1. Cerrar con la persona 2 **los 6 segmentos y las 4 preguntas**. Hay una propuesta en `CONTRACTS.md`; ajústenla a lo que 30X realmente necesita.
2. Escribir el **playbook** (máximo 8 slides, es un entregable obligatorio): qué decide JEV, con qué preguntas, con qué umbrales, quién revisa los casos dudosos y cómo se mide si funciona.
3. Ayudar a la persona 3 a etiquetar las 200 personas.
4. Escribir el guion del pitch y de la demo, y organizar los ensayos.

---

