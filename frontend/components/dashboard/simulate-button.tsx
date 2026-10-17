"use client";

import { Loader2Icon, PlayIcon } from "lucide-react";
import { useState } from "react";

import { Notice } from "@/components/dashboard/notice";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { simulate } from "@/lib/api";
import { formatInt } from "@/lib/format";

const N = 10_000;

export function SimulateButton({
  running,
  onStarted,
}: {
  /** `metrics.running`: hay una simulación en curso. */
  running: boolean;
  onStarted: () => void;
}) {
  const [sending, setSending] = useState(false);
  const [accepted, setAccepted] = useState<number>();
  const [error, setError] = useState<string>();

  async function handleClick() {
    setSending(true);
    setError(undefined);
    try {
      const res = await simulate(N);
      setAccepted(res.accepted);
      onStarted();
      // Da tiempo a que /metrics empiece a reportar running = true.
      setTimeout(() => setSending(false), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setSending(false);
    }
  }

  const busy = running || sending;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Simulación</CardTitle>
        <CardDescription>
          Envía {formatInt(N)} eventos simulados al pipeline. Corre en segundo
          plano; mira cómo se mueven el feed, los indicadores y el Sankey.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <Button
          size="lg"
          className="h-11 text-base"
          disabled={busy}
          onClick={handleClick}
        >
          {busy ? (
            <Loader2Icon aria-hidden className="animate-spin" />
          ) : (
            <PlayIcon aria-hidden />
          )}
          {running ? "Simulando…" : sending ? "Enviando…" : "Simular 10.000"}
        </Button>
        <p className="text-xs text-muted-foreground" aria-live="polite">
          {running
            ? "Hay una simulación en curso. El botón se activa cuando termine."
            : accepted !== undefined
              ? `Última simulación: ${formatInt(accepted)} eventos aceptados.`
              : "Sin simulaciones en esta sesión."}
        </p>
        {error && <Notice>No se pudo iniciar la simulación: {error}</Notice>}
      </CardContent>
    </Card>
  );
}
