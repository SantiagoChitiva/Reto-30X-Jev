# Despliegue

- **Tablero (Next.js) → Vercel.**
- **API (FastAPI) + Postgres → Railway.** Vercel corre funciones que se apagan entre pedidos, y la API necesita quedarse encendida: corre la simulación en segundo plano y mantiene conexiones abiertas a Postgres.

Los dos servicios toman el código de GitHub. Elijan la rama `feat/perfiles-30x-evaluacion` o, mejor, júntenla primero con `main`.

## 1. API en Railway

1. Entrar a [railway.com](https://railway.com) con GitHub → **New Project → Deploy from GitHub repo** → `Reto-30X-Jev`.
   Railway lee `railway.json` y construye con `backend/Dockerfile`.
2. En el mismo proyecto: **New → Database → PostgreSQL**. Las tablas se crean solas al arrancar la API.
3. En el servicio de la API, pestaña **Variables**:

   | Variable | Valor |
   |---|---|
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (la referencia a la base del paso 2) |
   | `USE_MOCK_JEV` | `false` |
   | `AI_GATEWAY_API_KEY` | la clave de Vercel AI Gateway |
   | `ALLOWED_ORIGINS` | la URL del tablero en Vercel, por ejemplo `https://reto-30x-jev.vercel.app` (se completa en el paso 3) |
   | `MAX_CONCURRENCY` | `20` |

4. **Settings → Networking → Generate Domain**. Esa es la URL de la API, por ejemplo `https://reto-30x-jev-production.up.railway.app`.
5. Probar: abrir `<URL de la API>/health`; debe responder `{"ok":true,"mock_jev":false}`.

## 2. Tablero en Vercel

1. En [vercel.com](https://vercel.com): **Add New → Project → importar** `Reto-30X-Jev`.
2. **Root Directory:** `frontend`. Vercel detecta Next.js solo.
3. **Environment Variables:** `NEXT_PUBLIC_API_URL` = la URL de la API del paso 1.4, sin `/` al final.
4. **Deploy.** Al terminar, Vercel da la URL del tablero.

## 3. Conectar los dos

1. Copiar la URL del tablero a `ALLOWED_ORIGINS` en Railway. Railway vuelve a desplegar solo.
2. Abrir el tablero: el indicador debe decir «API conectada». Pulsar **Simular 10.000**.

Si el tablero dice «Sin conexión con la API», casi siempre es `ALLOWED_ORIGINS` (debe ser la URL exacta, con `https://` y sin `/` final) o `NEXT_PUBLIC_API_URL`. Si se cambia `NEXT_PUBLIC_API_URL`, hay que volver a desplegar en Vercel: el valor queda fijo al construir.

## 4. Antes de la demo

- Con JEV real, 10.000 decisiones cuestan centavos, pero cada clic en «Simular 10.000» gasta crédito. Pónganle un presupuesto a la clave de AI Gateway.
- Correr la evaluación con JEV real: en Railway, en el servicio de la API, abrir una consola y ejecutar `python -m app.evaluate`. Actualiza el panel «¿Acierta JEV?» y da las cifras para el deck.
- HubSpot es opcional para la demo. Si lo conectan, la URL del webhook es `<URL de la API>/webhooks/hubspot` (ver `docs/HubSpot.md`).
