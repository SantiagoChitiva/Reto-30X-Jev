"use client";

import { ShieldXIcon } from "lucide-react";
import { useState } from "react";

import { EmptyState, Notice } from "@/components/dashboard/notice";
import { RouteBadge, RouteDot } from "@/components/dashboard/route-badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { usePolling } from "@/hooks/use-polling";
import { getDecisions } from "@/lib/api";
import {
  CONTENT_LABELS,
  MATURITY_LABELS,
  ROUTE_LABELS,
  SEGMENT_LABELS,
  actionLabel,
  formatMs,
  formatP,
  formatTime,
  labelOf,
} from "@/lib/format";
import { ROUTES, type Decision, type Route } from "@/lib/types";

type RouteFilter = Route | "all";

export function LiveFeed() {
  const [filter, setFilter] = useState<RouteFilter>("all");
  const { data, error } = usePolling(
    (signal) =>
      getDecisions(
        { limit: 50, route: filter === "all" ? undefined : filter },
        signal,
      ),
    1000,
    filter,
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle>Feed en vivo</CardTitle>
        <CardDescription>
          Últimas 50 decisiones de JEV, de la más reciente a la más antigua. Se
          actualiza cada segundo.
        </CardDescription>
        <CardAction>
          <div
            role="group"
            aria-label="Filtrar por ruta"
            className="flex flex-wrap gap-1"
          >
            {(["all", ...ROUTES] as const).map((value) => (
              <Button
                key={value}
                size="sm"
                variant={filter === value ? "default" : "outline"}
                aria-pressed={filter === value}
                onClick={() => setFilter(value)}
              >
                {value !== "all" && <RouteDot route={value} />}
                {value === "all" ? "Todas" : ROUTE_LABELS[value]}
              </Button>
            ))}
          </div>
        </CardAction>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {error && (
          <Notice>
            No se pudo cargar el feed: {error.message}. Se reintenta cada
            segundo.
          </Notice>
        )}
        {data === undefined ? (
          !error && <EmptyState>Cargando decisiones…</EmptyState>
        ) : data.length === 0 ? (
          <EmptyState>
            {filter === "all"
              ? "Aún no hay decisiones. Pulsa «Simular 10.000» para generar eventos."
              : `No hay decisiones con ruta ${ROUTE_LABELS[filter]}.`}
          </EmptyState>
        ) : (
          <div className="max-h-[420px] overflow-auto rounded-lg border">
            <Table className="text-xs">
              <TableHeader className="sticky top-0 z-10 bg-card">
                <TableRow>
                  <TableHead>Hora</TableHead>
                  <TableHead>Persona</TableHead>
                  <TableHead>Segmento</TableHead>
                  <TableHead>Madurez</TableHead>
                  <TableHead>Lista para ventas</TableHead>
                  <TableHead>Contenido</TableHead>
                  <TableHead>Ruta</TableHead>
                  <TableHead>Acción</TableHead>
                  <TableHead className="text-right">Latencia</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody className="tabular-nums">
                {data.map((d) => (
                  <DecisionRow key={d.decision_id} decision={d} />
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function DecisionRow({ decision: d }: { decision: Decision }) {
  return (
    <TableRow title={d.explanation ?? undefined}>
      <TableCell className="text-muted-foreground">
        {formatTime(d.created_at)}
      </TableCell>
      <TableCell className="font-mono">{d.person_id}</TableCell>
      <ScoredCell
        label={labelOf(SEGMENT_LABELS, d.segment.value)}
        p={d.segment.p}
      />
      <ScoredCell
        label={labelOf(MATURITY_LABELS, d.maturity.value)}
        p={d.maturity.p}
      />
      <ScoredCell label={d.sales_ready.value ? "Sí" : "No"} p={d.sales_ready.p} />
      <ScoredCell
        label={labelOf(CONTENT_LABELS, d.content.value)}
        p={d.content.p}
      />
      <TableCell>
        <RouteBadge route={d.route} />
      </TableCell>
      <TableCell>
        {d.guardrail && !d.guardrail.passed ? (
          <span
            className="inline-flex items-center gap-1"
            title={d.guardrail.reason ?? undefined}
          >
            <ShieldXIcon
              aria-hidden
              className="size-3.5 text-[var(--status-critical)]"
            />
            Bloqueada por guardrail
          </span>
        ) : d.action === null ? (
          <span className="text-muted-foreground">—</span>
        ) : (
          actionLabel(d.action)
        )}
      </TableCell>
      <TableCell className="text-right">{formatMs(d.latency_ms)}</TableCell>
    </TableRow>
  );
}

function ScoredCell({ label, p }: { label: string; p: number }) {
  return (
    <TableCell>
      {label}{" "}
      <span className="text-muted-foreground" title="Probabilidad de JEV">
        p {formatP(p)}
      </span>
    </TableCell>
  );
}
