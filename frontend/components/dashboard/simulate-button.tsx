"use client";

import { Loader2Icon, PlayIcon } from "lucide-react";
import { useState } from "react";

import { Notice } from "@/components/dashboard/notice";
import { Button } from "@/components/ui/button";
import { simulate } from "@/lib/api";
import { formatInt } from "@/lib/format";
import { cn } from "@/lib/utils";

const N = 10_000;

export function SimulateButton({
  running,
  onStarted,
  children,
}: {
  /** `metrics.running`: hay una simulación en curso. */
  running: boolean;
  onStarted: () => void;
  /** Acciones secundarias que van al lado del botón. */
  children?: React.ReactNode;
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
    <div className="flex flex-col items-center gap-3">
      <div className="flex flex-wrap justify-center gap-3">
        <Button
          size="lg"
          className={cn(
            "h-12 rounded-full px-6 text-base",
            running && "sweep disabled:opacity-100",
          )}
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
        {children}
      </div>
      <p className="text-sm text-muted-foreground" aria-live="polite">
        {running
          ? "Simulación en curso: mira cómo se encienden los puntos."
          : accepted !== undefined
            ? `Última simulación: ${formatInt(accepted)} eventos aceptados.`
            : `Envía ${formatInt(N)} eventos simulados al pipeline.`}
      </p>
      {error && <Notice>No se pudo iniciar la simulación: {error}</Notice>}
    </div>
  );
}
