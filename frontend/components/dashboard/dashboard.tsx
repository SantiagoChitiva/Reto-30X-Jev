"use client";

import { LiveFeed } from "@/components/dashboard/live-feed";
import { MetricsPanel } from "@/components/dashboard/metrics-panel";
import { Notice } from "@/components/dashboard/notice";
import { ReviewQueue } from "@/components/dashboard/review-queue";
import { SimulateButton } from "@/components/dashboard/simulate-button";
import { TransitionsSankey } from "@/components/dashboard/transitions-sankey";
import { usePolling } from "@/hooks/use-polling";
import { API_URL, getMetrics } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Dashboard() {
  // /metrics alimenta los indicadores y el estado del botón de simulación.
  const metrics = usePolling(getMetrics, 1000);
  const connected = metrics.data !== undefined && !metrics.error;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-4 px-4 py-6 sm:px-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">30X Pulse</h1>
          <p className="text-sm text-muted-foreground">
            Segmentación en tiempo real con JEV: cada evento se decide en la
            ruta automática, la del LLM o la cola humana.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span
            aria-hidden
            className={cn(
              "inline-block size-2 rounded-full",
              connected
                ? "bg-[var(--status-good)]"
                : "bg-[var(--status-critical)]",
            )}
          />
          <span>
            {connected ? "API conectada" : "Sin conexión con la API"} ·{" "}
            <span className="font-mono">{API_URL}</span>
          </span>
        </div>
      </header>

      {metrics.error && (
        <Notice>
          La API en <span className="font-mono">{API_URL}</span> no responde.
          El tablero sigue intentando; revisa que el backend esté corriendo.
        </Notice>
      )}

      <LiveFeed />

      <div className="grid gap-4 lg:grid-cols-4">
        <div className="lg:col-span-3">
          <MetricsPanel metrics={metrics.data} error={metrics.error} />
        </div>
        <SimulateButton
          running={metrics.data?.running ?? false}
          onStarted={metrics.refresh}
        />
      </div>

      <TransitionsSankey />

      <ReviewQueue />
    </div>
  );
}
