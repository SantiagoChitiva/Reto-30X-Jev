"use client";

import { CheckIcon, Loader2Icon } from "lucide-react";
import { useMemo, useState } from "react";

import { EmptyState, Notice } from "@/components/dashboard/notice";
import { Badge } from "@/components/ui/badge";
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { usePolling } from "@/hooks/use-polling";
import { getDecisions, getReviewQueue, resolveReview } from "@/lib/api";
import {
  CONTENT_LABELS,
  MATURITY_LABELS,
  REVIEW_ACTIONS,
  SEGMENT_LABELS,
  actionLabel,
  formatInt,
  formatP,
  formatTime,
  labelOf,
  type ReviewAction,
} from "@/lib/format";
import { SEGMENTS, type Decision, type Review, type Segment } from "@/lib/types";

const MAX_VISIBLE = 20;

const SEGMENT_ITEMS = Object.fromEntries(
  SEGMENTS.map((s) => [s, SEGMENT_LABELS[s]]),
);
const ACTION_ITEMS = Object.fromEntries(
  REVIEW_ACTIONS.map((a) => [a, actionLabel(a)]),
);

export function ReviewQueue() {
  const queue = usePolling(getReviewQueue, 2000);
  const context = usePolling(
    (signal) => getDecisions({ route: "human", limit: 200 }, signal),
    2000,
  );
  // Casos resueltos en esta pestaña: se ocultan sin esperar al siguiente sondeo.
  const [resolved, setResolved] = useState<ReadonlySet<string>>(new Set());

  const decisionsById = useMemo(
    () => new Map((context.data ?? []).map((d) => [d.decision_id, d])),
    [context.data],
  );

  // Las más recientes primero: son las que tienen contexto en las últimas 200
  // decisiones humanas.
  const pending = useMemo(
    () =>
      (queue.data ?? [])
        .filter((r) => r.status === "pending" && !resolved.has(r.review_id))
        .sort((a, b) => b.created_at.localeCompare(a.created_at)),
    [queue.data, resolved],
  );

  function handleResolved(reviewId: string) {
    setResolved((prev) => new Set(prev).add(reviewId));
    queue.refresh();
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cola humana</CardTitle>
        <CardDescription>
          Casos con p menor a 0,60 o segmento «otro». Elige el segmento y la
          acción correctos y resuelve. Se actualiza cada 2 segundos.
        </CardDescription>
        {queue.data && (
          <CardAction>
            <Badge variant="secondary" className="tabular-nums">
              {formatInt(pending.length)} pendientes
            </Badge>
          </CardAction>
        )}
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {queue.error && (
          <Notice>No se pudo cargar la cola: {queue.error.message}.</Notice>
        )}
        {queue.data === undefined ? (
          !queue.error && <EmptyState>Cargando cola…</EmptyState>
        ) : pending.length === 0 ? (
          <EmptyState>No hay casos pendientes de revisión.</EmptyState>
        ) : (
          <>
            {pending.length > MAX_VISIBLE && (
              <p className="text-xs text-muted-foreground">
                Mostrando los {MAX_VISIBLE} más recientes de{" "}
                {formatInt(pending.length)}.
              </p>
            )}
            <ul className="flex flex-col divide-y rounded-lg border">
              {pending.slice(0, MAX_VISIBLE).map((review) => (
                <ReviewItem
                  key={review.review_id}
                  review={review}
                  decision={decisionsById.get(review.decision_id)}
                  onResolved={handleResolved}
                />
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function suggestedAction(decision: Decision | undefined): ReviewAction | null {
  if (!decision) return null;
  if (decision.sales_ready.value) return "notify_sales";
  const send = `send:${decision.content.value}`;
  return (REVIEW_ACTIONS as readonly string[]).includes(send)
    ? (send as ReviewAction)
    : null;
}

function ReviewItem({
  review,
  decision,
  onResolved,
}: {
  review: Review;
  decision: Decision | undefined;
  onResolved: (reviewId: string) => void;
}) {
  // `undefined` = sin tocar: se propone lo que dijo JEV (el contexto puede
  // llegar después que la cola).
  const [segmentChoice, setSegment] = useState<Segment | null>();
  const [actionChoice, setAction] = useState<ReviewAction | null>();
  const segment =
    segmentChoice === undefined
      ? (decision?.segment.value ?? null)
      : segmentChoice;
  const action =
    actionChoice === undefined ? suggestedAction(decision) : actionChoice;
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string>();

  async function handleResolve() {
    if (!segment || !action) return;
    setSending(true);
    setError(undefined);
    try {
      await resolveReview(review.review_id, {
        segment,
        action: action === "ninguna" ? null : action,
      });
      onResolved(review.review_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSending(false);
    }
  }

  return (
    <li className="flex flex-col gap-3 px-3 py-3 xl:flex-row xl:items-center xl:justify-between">
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
          <span className="font-mono">{review.review_id}</span>
          <span>·</span>
          <span>{formatTime(review.created_at)}</span>
          {decision && (
            <>
              <span>·</span>
              <span className="font-mono text-foreground">
                {decision.person_id}
              </span>
            </>
          )}
        </div>
        {decision ? (
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <Fact
              label="Segmento"
              value={labelOf(SEGMENT_LABELS, decision.segment.value)}
              p={decision.segment.p}
            />
            <Fact
              label="Madurez"
              value={labelOf(MATURITY_LABELS, decision.maturity.value)}
              p={decision.maturity.p}
            />
            <Fact
              label="Ventas"
              value={decision.sales_ready.value ? "Sí" : "No"}
              p={decision.sales_ready.p}
            />
            <Fact
              label="Contenido"
              value={labelOf(CONTENT_LABELS, decision.content.value)}
              p={decision.content.p}
            />
          </div>
        ) : (
          <div className="text-sm">
            Decisión <span className="font-mono">{review.decision_id}</span>
          </div>
        )}
        {error && <Notice className="mt-1">No se pudo resolver: {error}</Notice>}
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-2">
        <Select
          items={SEGMENT_ITEMS}
          value={segment}
          onValueChange={(v) => setSegment(v as Segment | null)}
        >
          <SelectTrigger
            size="sm"
            className="w-44"
            aria-label={`Segmento para ${review.review_id}`}
          >
            <SelectValue placeholder="Segmento" />
          </SelectTrigger>
          <SelectContent>
            {SEGMENTS.map((s) => (
              <SelectItem key={s} value={s}>
                {SEGMENT_LABELS[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select
          items={ACTION_ITEMS}
          value={action}
          onValueChange={(v) => setAction(v as ReviewAction | null)}
        >
          <SelectTrigger
            size="sm"
            className="w-52"
            aria-label={`Acción para ${review.review_id}`}
          >
            <SelectValue placeholder="Acción" />
          </SelectTrigger>
          <SelectContent>
            {REVIEW_ACTIONS.map((a) => (
              <SelectItem key={a} value={a}>
                {actionLabel(a)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Button
          size="sm"
          disabled={!segment || !action || sending}
          onClick={handleResolve}
        >
          {sending ? (
            <Loader2Icon aria-hidden className="animate-spin" />
          ) : (
            <CheckIcon aria-hidden />
          )}
          Resolver
        </Button>
      </div>
    </li>
  );
}

function Fact({ label, value, p }: { label: string; value: string; p: number }) {
  return (
    <span>
      <span className="text-muted-foreground">{label}:</span> {value}{" "}
      <span className="text-xs tabular-nums text-muted-foreground">
        p {formatP(p)}
      </span>
    </span>
  );
}
