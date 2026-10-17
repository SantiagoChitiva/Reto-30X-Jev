# Frontend (persona 4)

Next.js + Tailwind/shadcn + Recharts. Consume la API descrita en `../CONTRACTS.md`.

```bash
npx create-next-app@latest . --ts --tailwind --app --eslint
```

Variable: `NEXT_PUBLIC_API_URL=http://localhost:8000`

Pantallas: feed de decisiones en vivo (`GET /decisions`, polling 1 s), indicadores (`GET /metrics`),
Sankey (`GET /transitions`), cola humana (`GET /review-queue`), botón "Simular 10.000" (`POST /simulate`).
