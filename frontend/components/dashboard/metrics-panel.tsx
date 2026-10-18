import { AnimatedNumber } from "@/components/dashboard/animated-number";
import { EmptyState, Notice } from "@/components/dashboard/notice";
import { ROUTE_COLORS, RouteDot } from "@/components/dashboard/route-badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ROUTE_LABELS,
  formatInt,
  formatMs,
  formatPct,
  formatUsd,
} from "@/lib/format";
import { ROUTES, type Metrics } from "@/lib/types";

export function MetricsPanel({
  metrics,
  error,
}: {
  metrics: Metrics | undefined;
  error: Error | undefined;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Indicadores</CardTitle>
        <CardDescription>
          Totales de todas las decisiones. Se actualizan cada segundo.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {error && (
          <Notice>
            No se pudieron cargar los indicadores: {error.message}.
          </Notice>
        )}
        {metrics === undefined ? (
          !error && <EmptyState>Cargando indicadores…</EmptyState>
        ) : (
          <>
            <dl className="grid grid-cols-2 overflow-hidden rounded-xl border md:grid-cols-4 xl:grid-cols-7">
              <Stat
                label="Decisiones"
                value={metrics.total_decisions}
                format={formatInt}
              />
              <Stat
                label="Costo total"
                value={metrics.total_cost_usd}
                format={formatUsd}
              />
              <Stat
                label="Costo por 1.000"
                value={metrics.cost_per_1k_usd}
                format={formatUsd}
              />
              <Stat
                label="Latencia p50"
                value={metrics.latency_p50_ms}
                format={formatMs}
              />
              <Stat
                label="Latencia p95"
                value={metrics.latency_p95_ms}
                format={formatMs}
              />
              <Stat
                label="Bloqueadas por guardrail"
                value={metrics.guardrail_blocked}
                format={formatInt}
              />
              <Stat
                label="Frenadas por antispam"
                value={metrics.spam_suppressed}
                format={formatInt}
              />
            </dl>
            <RouteMix metrics={metrics} />
          </>
        )}
      </CardContent>
    </Card>
  );
}

function Stat({
  label,
  value,
  format,
}: {
  label: string;
  value: number;
  format: (n: number) => string;
}) {
  // Filete a la derecha y abajo: la franja se lee como una tabla, no como tarjetas.
  return (
    <div className="px-4 py-3.5 [box-shadow:1px_0_0_var(--border),0_1px_0_var(--border)]">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-2xl font-bold tracking-tight whitespace-nowrap tabular-nums xl:text-xl">
        <AnimatedNumber value={value} format={format} />
      </dd>
    </div>
  );
}

const ROUTE_PCT_KEY = {
  auto: "auto_pct",
  safe: "safe_pct",
  human: "human_pct",
} as const;

/** Reparto por ruta: una barra apilada con su leyenda. */
function RouteMix({ metrics }: { metrics: Metrics }) {
  const total = ROUTES.reduce((sum, r) => sum + metrics[ROUTE_PCT_KEY[r]], 0);

  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <span className="text-xs text-muted-foreground">Reparto por ruta</span>
        <span className="text-sm">
          <span className="text-2xl font-bold tracking-tight text-brand-lime tabular-nums">
            <AnimatedNumber value={metrics.auto_pct} format={formatPct} />
          </span>{" "}
          <span className="text-muted-foreground">automático</span>
        </span>
      </div>
      <div
        className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full bg-muted"
        role="img"
        aria-label={ROUTES.map(
          (r) => `${ROUTE_LABELS[r]} ${formatPct(metrics[ROUTE_PCT_KEY[r]])}`,
        ).join(", ")}
      >
        {total > 0 &&
          ROUTES.map((r) => {
            const pct = metrics[ROUTE_PCT_KEY[r]];
            if (pct <= 0) return null;
            return (
              <div
                key={r}
                title={`${ROUTE_LABELS[r]}: ${formatPct(pct)}`}
                className="h-full transition-[flex-grow] duration-700 ease-[var(--ease-out-expo)]"
                style={{ flexGrow: pct, background: ROUTE_COLORS[r] }}
              />
            );
          })}
      </div>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {ROUTES.map((r) => (
          <li key={r} className="flex items-center gap-1.5">
            <RouteDot route={r} />
            <span>{ROUTE_LABELS[r]}</span>
            <span className="tabular-nums text-muted-foreground">
              {formatPct(metrics[ROUTE_PCT_KEY[r]])}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
