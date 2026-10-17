import { Badge } from "@/components/ui/badge";
import { ROUTE_LABELS } from "@/lib/format";
import type { Route } from "@/lib/types";

export const ROUTE_COLORS: Record<Route, string> = {
  auto: "var(--route-auto)",
  llm: "var(--route-llm)",
  human: "var(--route-human)",
};

export function RouteDot({ route }: { route: Route }) {
  return (
    <span
      aria-hidden
      className="inline-block size-2 shrink-0 rounded-full"
      style={{ background: ROUTE_COLORS[route] }}
    />
  );
}

export function RouteBadge({ route }: { route: Route }) {
  return (
    <Badge variant="outline" className="gap-1.5">
      <RouteDot route={route} />
      {ROUTE_LABELS[route] ?? route}
    </Badge>
  );
}
