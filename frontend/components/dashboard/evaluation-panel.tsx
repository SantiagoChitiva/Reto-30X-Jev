"use client";

import { EmptyState, Notice } from "@/components/dashboard/notice";
import { RouteDot } from "@/components/dashboard/route-badge";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { usePolling } from "@/hooks/use-polling";
import { getEvaluation } from "@/lib/api";
import {
  ROUTE_LABELS,
  formatInt,
  formatMs,
  formatPct,
  formatUsd,
} from "@/lib/format";
import { ROUTES, type Evaluation, type Question } from "@/lib/types";

const QUESTION_LABELS: Record<Question, string> = {
  segment: "Segmento",
  content: "Oferta",
  sales_ready: "¿Lista para ventas?",
};
const QUESTIONS = Object.keys(QUESTION_LABELS) as Question[];

export function EvaluationPanel() {
  // El resultado solo cambia cuando alguien corre la evaluación: basta con revisarlo de vez en cuando.
  const { data, error } = usePolling(getEvaluation, 15000);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          ¿Acierta JEV?
          {data?.mock_jev && <Badge variant="secondary">JEV simulado</Badge>}
        </CardTitle>
        <CardDescription>
          Precisión contra el set etiquetado con perfiles de 30X y costo frente
          a un LLM normal.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {error && (
          <Notice>No se pudo cargar la evaluación: {error.message}.</Notice>
        )}
        {data === undefined && !error && (
          <EmptyState>Cargando evaluación…</EmptyState>
        )}
        {data === null && (
          <EmptyState>
            Aún no hay evaluación. Córrela con{" "}
            <span className="font-mono">
              docker compose exec backend python -m app.evaluate
            </span>
            .
          </EmptyState>
        )}
        {data && <EvaluationBody evaluation={data} />}
      </CardContent>
    </Card>
  );
}

function EvaluationBody({ evaluation: e }: { evaluation: Evaluation }) {
  const costRatio = e.jev.cost_per_1k_usd
    ? e.llm.cost_per_1k_usd / e.jev.cost_per_1k_usd
    : 0;
  const speedRatio = e.jev.latency_p50_ms
    ? e.llm.latency_ms_typical / e.jev.latency_p50_ms
    : 0;

  return (
    <>
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="flex flex-col gap-2">
          <h3 className="text-xs text-muted-foreground">
            Precisión sobre {formatInt(e.n)} perfiles
          </h3>
          <dl className="grid grid-cols-3 overflow-hidden rounded-xl border">
            {QUESTIONS.map((q) => (
              <div key={q} className="px-4 py-3.5 [box-shadow:1px_0_0_var(--border),0_1px_0_var(--border)]">
                <dt className="text-xs text-muted-foreground">
                  {QUESTION_LABELS[q]}
                </dt>
                <dd className="mt-1 text-2xl font-bold tracking-tight">
                  {formatPct(e.accuracy[q])}
                </dd>
              </div>
            ))}
          </dl>
          <table className="w-full text-sm">
            <caption className="sr-only">Precisión por ruta</caption>
            <thead className="text-xs text-muted-foreground">
              <tr>
                <th className="py-1 text-left font-normal">Ruta</th>
                <th className="py-1 text-right font-normal">Casos</th>
                {QUESTIONS.map((q) => (
                  <th key={q} className="py-1 text-right font-normal">
                    {QUESTION_LABELS[q]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="tabular-nums">
              {ROUTES.map((r) => (
                <tr key={r} className="border-t">
                  <td className="py-1.5">
                    <span className="flex items-center gap-1.5">
                      <RouteDot route={r} />
                      {ROUTE_LABELS[r]}
                    </span>
                  </td>
                  <td className="py-1.5 text-right">
                    {formatInt(e.by_route[r].n)}
                  </td>
                  {QUESTIONS.map((q) => (
                    <td key={q} className="py-1.5 text-right">
                      {e.by_route[r].n ? formatPct(e.by_route[r][q]) : "—"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex flex-col gap-2">
          <h3 className="text-xs text-muted-foreground">
            JEV frente a {e.llm.model}
            {e.llm.estimated && " (estimado)"}
          </h3>
          <dl className="grid overflow-hidden rounded-xl border sm:grid-cols-2">
            <Compare
              label="Costo por 1.000 decisiones"
              jev={formatUsd(e.jev.cost_per_1k_usd)}
              llm={formatUsd(e.llm.cost_per_1k_usd)}
              ratio={costRatio}
              unit="más barato"
            />
            <Compare
              label="Latencia por decisión"
              jev={formatMs(e.jev.latency_p50_ms)}
              llm={formatMs(e.llm.latency_ms_typical)}
              ratio={speedRatio}
              unit="más rápido"
            />
          </dl>
          <p className="text-xs text-muted-foreground">
            Etiquetas: {e.labels}. Revisadas a mano: {formatInt(e.reviewed_labels)}{" "}
            de {formatInt(e.n)}.
          </p>
        </div>
      </div>
    </>
  );
}

function Compare({
  label,
  jev,
  llm,
  ratio,
  unit,
}: {
  label: string;
  jev: string;
  llm: string;
  ratio: number;
  unit: string;
}) {
  return (
    <div className="flex flex-col gap-1 px-4 py-3.5 [box-shadow:1px_0_0_var(--border),0_1px_0_var(--border)]">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-2xl font-bold tracking-tight text-brand-lime">
        {ratio >= 1 ? `${ratio.toFixed(ratio < 10 ? 1 : 0)}× ${unit}` : "—"}
      </dd>
      <dd className="text-xs tabular-nums text-muted-foreground">
        JEV {jev} · LLM {llm}
      </dd>
    </div>
  );
}
