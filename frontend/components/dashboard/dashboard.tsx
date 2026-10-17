"use client";

import { EvaluationPanel } from "@/components/dashboard/evaluation-panel";
import { LiveFeed } from "@/components/dashboard/live-feed";
import { Logo30X } from "@/components/dashboard/logo";
import { MetricsPanel } from "@/components/dashboard/metrics-panel";
import { Notice } from "@/components/dashboard/notice";
import { PulseField } from "@/components/dashboard/pulse-field";
import { ReviewQueue } from "@/components/dashboard/review-queue";
import { SimulateButton } from "@/components/dashboard/simulate-button";
import { TransitionsSankey } from "@/components/dashboard/transitions-sankey";
import { buttonVariants } from "@/components/ui/button";
import { usePolling } from "@/hooks/use-polling";
import { API_URL, getMetrics } from "@/lib/api";
import { cn } from "@/lib/utils";

export function Dashboard() {
  // /metrics alimenta los indicadores y el estado del botón de simulación.
  const metrics = usePolling(getMetrics, 1000);
  const connected = metrics.data !== undefined && !metrics.error;

  return (
    <>
      <nav className="sticky top-0 z-20 border-b bg-card/85 backdrop-blur">
        <div className="mx-auto flex h-16 w-full max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex items-baseline gap-2">
            <Logo30X className="text-2xl" />
            <span className="text-lg font-semibold tracking-tight">Pulse</span>
          </div>
          <div className="flex min-w-0 items-center gap-2 rounded-full border bg-muted px-3 py-1 text-xs text-muted-foreground">
            <span aria-hidden className="relative inline-flex size-2 shrink-0">
              {connected && (
                <span className="absolute inset-0 rounded-full bg-[var(--status-good)] opacity-60 motion-safe:animate-[ping_2s_cubic-bezier(0,0,0.2,1)_infinite]" />
              )}
              <span
                className={cn(
                  "relative inline-block size-2 rounded-full transition-colors duration-300",
                  connected
                    ? "bg-[var(--status-good)]"
                    : "bg-[var(--status-critical)]",
                )}
              />
            </span>
            <span className="truncate">
              {connected ? "API conectada" : "Sin conexión con la API"}
              <span className="hidden sm:inline">
                {" "}
                · <span className="font-mono">{API_URL}</span>
              </span>
            </span>
          </div>
        </div>
      </nav>

      <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 pb-16 sm:px-6">
        <header className="flex flex-col items-center gap-6 pt-14 text-center sm:pt-20">
          <h1 className="text-5xl leading-[1.02] sm:text-7xl">
            Segmentación en <br className="hidden sm:inline" />
            <span className="text-brand-lime">tiempo real</span>
          </h1>
          <p className="max-w-2xl text-base text-pretty text-muted-foreground sm:text-lg">
            Cada señal reubica a la persona de la audiencia de 30X y decide qué
            programa ofrecerle, por la ruta automática, la del LLM o la cola
            humana.
          </p>
          <SimulateButton
            running={metrics.data?.running ?? false}
            onStarted={metrics.refresh}
          >
            <a
              href="#cola-humana"
              className={cn(
                buttonVariants({ variant: "secondary", size: "lg" }),
                "h-12 rounded-full px-6 text-base font-semibold hover:bg-white/85",
              )}
            >
              Revisar cola humana
            </a>
          </SimulateButton>
        </header>

        <PulseField metrics={metrics.data} />

        {metrics.error && (
          <Notice>
            La API en <span className="font-mono">{API_URL}</span> no responde.
            El tablero sigue intentando; revisa que el backend esté corriendo.
          </Notice>
        )}

        <MetricsPanel metrics={metrics.data} error={metrics.error} />

        <LiveFeed />

        <TransitionsSankey />

        <EvaluationPanel />

        <ReviewQueue />
      </div>
    </>
  );
}
