"use client";

import { useCallback, useEffect, useEffectEvent, useState } from "react";

export interface PollingState<T> {
  /** Última respuesta buena. Se conserva si una consulta posterior falla. */
  data: T | undefined;
  /** Error de la última consulta, o `undefined` si salió bien. */
  error: Error | undefined;
  /** Vuelve a consultar ya, sin esperar al siguiente ciclo. */
  refresh: () => void;
}

/**
 * Consulta `fetcher` cada `intervalMs`. La siguiente consulta arranca cuando
 * termina la anterior, así nunca hay dos en vuelo. Cambiar `key` reinicia el
 * ciclo (por ejemplo, al cambiar un filtro).
 */
export function usePolling<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  intervalMs: number,
  key = "",
): PollingState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<Error>();
  const [nonce, setNonce] = useState(0);

  const load = useEffectEvent((signal: AbortSignal) => fetcher(signal));

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function tick() {
      try {
        const next = await load(controller.signal);
        if (controller.signal.aborted) return;
        setData(next);
        setError(undefined);
      } catch (err) {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err : new Error(String(err)));
      }
      timer = setTimeout(tick, intervalMs);
    }

    tick();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [intervalMs, key, nonce]);

  const refresh = useCallback(() => setNonce((n) => n + 1), []);

  return { data, error, refresh };
}
