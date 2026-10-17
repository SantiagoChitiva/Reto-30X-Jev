"use client";

import { useMemo } from "react";
import {
  Sankey,
  Tooltip,
  type SankeyLinkProps,
  type SankeyNodeProps,
} from "recharts";

import { EmptyState, Notice } from "@/components/dashboard/notice";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { usePolling } from "@/hooks/use-polling";
import { getTransitions } from "@/lib/api";
import { SEGMENT_LABELS, formatInt, labelOf } from "@/lib/format";
import { SEGMENTS, type Transition } from "@/lib/types";

const SEGMENT_COLORS: Record<string, string> = {
  explorador: "var(--series-1)",
  lider_negocio: "var(--series-2)",
  lider_tecnico: "var(--series-3)",
  equipo_adopcion: "var(--series-4)",
  lider_adopcion: "var(--series-5)",
  otro: "var(--series-other)",
};

interface FlowNode {
  name: string;
  segment: string;
  side: "antes" | "después";
}

/**
 * Convierte `[{from, to, count}]` en nodos y enlaces del Sankey. Cada segmento
 * aparece dos veces, "X (antes)" y "X (después)", para que no haya ciclos.
 */
function toSankeyData(transitions: Transition[]) {
  const flows = transitions.filter((t) => t.count > 0);
  const order = (s: string) => {
    const i = SEGMENTS.indexOf(s as (typeof SEGMENTS)[number]);
    return i === -1 ? SEGMENTS.length : i;
  };
  const sides = (pick: (t: Transition) => string) =>
    [...new Set(flows.map(pick))].sort((a, b) => order(a) - order(b));

  const nodes: FlowNode[] = [];
  const index = new Map<string, number>();
  for (const [side, segments] of [
    ["antes", sides((t) => t.from)],
    ["después", sides((t) => t.to)],
  ] as const) {
    for (const segment of segments) {
      index.set(`${side}:${segment}`, nodes.length);
      nodes.push({
        name: `${labelOf(SEGMENT_LABELS, segment)} (${side})`,
        segment,
        side,
      });
    }
  }

  const links = flows.map((t) => ({
    source: index.get(`antes:${t.from}`)!,
    target: index.get(`después:${t.to}`)!,
    value: t.count,
  }));

  return { nodes, links };
}

export function TransitionsSankey() {
  const { data, error } = usePolling(getTransitions, 3000);
  const sankey = useMemo(() => (data ? toSankeyData(data) : undefined), [data]);
  const total = sankey?.links.reduce((sum, l) => sum + l.value, 0) ?? 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cambios de segmento</CardTitle>
        <CardDescription>
          Cómo pasan las personas de un segmento a otro entre una decisión y la
          siguiente
          {total > 0 && ` (${formatInt(total)} transiciones)`}. Se actualiza
          cada 3 segundos.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {error && (
          <Notice>No se pudieron cargar las transiciones: {error.message}.</Notice>
        )}
        {sankey === undefined ? (
          !error && <EmptyState>Cargando transiciones…</EmptyState>
        ) : sankey.links.length === 0 ? (
          <EmptyState>
            Todavía no hay cambios de segmento. Aparecen cuando una persona
            recibe más de un evento.
          </EmptyState>
        ) : (
          <div className="h-[420px] w-full overflow-x-auto">
            <div className="h-full min-w-[640px]">
              <Sankey
                width="100%"
                height="100%"
                data={sankey}
                node={(props: SankeyNodeProps) => (
                  <FlowNodeShape {...props} nodes={sankey.nodes} />
                )}
                link={(props: SankeyLinkProps) => (
                  <FlowLinkShape {...props} sankey={sankey} />
                )}
                nodePadding={18}
                nodeWidth={12}
                margin={{ top: 8, right: 190, bottom: 8, left: 190 }}
              >
                <Tooltip
                  formatter={(value) => formatInt(Number(value))}
                  contentStyle={{
                    borderRadius: 8,
                    fontSize: 12,
                    border: "1px solid var(--border)",
                  }}
                />
              </Sankey>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

type SankeyInput = ReturnType<typeof toSankeyData>;

function FlowLinkShape({
  sourceX,
  sourceY,
  sourceControlX,
  targetX,
  targetY,
  targetControlX,
  linkWidth,
  index,
  sankey,
}: SankeyLinkProps & { sankey: SankeyInput }) {
  const source = sankey.nodes[sankey.links[index]?.source ?? -1];
  return (
    <path
      d={`M${sourceX},${sourceY} C${sourceControlX},${sourceY} ${targetControlX},${targetY} ${targetX},${targetY}`}
      fill="none"
      stroke={SEGMENT_COLORS[source?.segment ?? ""] ?? "var(--series-other)"}
      strokeOpacity={0.3}
      strokeWidth={Math.max(linkWidth, 1)}
      className="transition-[stroke-opacity] hover:[stroke-opacity:0.6]"
    />
  );
}

function FlowNodeShape({
  x,
  y,
  width,
  height,
  index,
  payload,
  nodes,
}: SankeyNodeProps & { nodes: FlowNode[] }) {
  const node = nodes[index];
  const isSource = node?.side === "antes";
  const textX = isSource ? x - 8 : x + width + 8;

  return (
    <g>
      <rect
        x={x}
        y={y}
        width={width}
        height={Math.max(height, 1)}
        rx={2}
        fill={SEGMENT_COLORS[node?.segment ?? ""] ?? "var(--series-other)"}
      />
      <text
        x={textX}
        y={y + height / 2}
        textAnchor={isSource ? "end" : "start"}
        dominantBaseline="middle"
        className="fill-foreground text-xs"
      >
        {node?.name ?? payload.name}
        <tspan className="fill-muted-foreground">
          {"  "}
          {formatInt(Number(payload.value) || 0)}
        </tspan>
      </text>
    </g>
  );
}
