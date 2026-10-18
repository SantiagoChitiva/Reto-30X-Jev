"use client";

import { Loader2Icon, RotateCcwIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { resetDemo } from "@/lib/api";

/** Borra los datos simulados para que la demo arranque de cero. Las personas de HubSpot no se tocan. */
export function ResetButton({
  running,
  onReset,
}: {
  running: boolean;
  onReset: () => void;
}) {
  const [busy, setBusy] = useState(false);

  async function handleClick() {
    if (!window.confirm("¿Borrar los datos simulados y empezar de cero?")) return;
    setBusy(true);
    try {
      await resetDemo();
      onReset();
    } catch (err) {
      window.alert(`No se pudo limpiar: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button
      variant="outline"
      size="lg"
      className="h-12 rounded-full px-6 text-base"
      disabled={running || busy}
      onClick={handleClick}
      title="Borra solo los datos simulados"
    >
      {busy ? <Loader2Icon aria-hidden className="animate-spin" /> : <RotateCcwIcon aria-hidden />}
      Empezar de cero
    </Button>
  );
}
