"use client";

import { useEffect, useRef, useState } from "react";

/** Desaceleración exponencial, la misma curva que `--ease-out-expo`. */
function easeOutExpo(t: number) {
  return t >= 1 ? 1 : 1 - 2 ** (-10 * t);
}

function prefersReducedMotion() {
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Muestra `value` con `format`. Cuando el valor cambia, recorre el tramo desde
 * lo que se veía hasta el nuevo valor, para que el salto se lea como cambio.
 * Con movimiento reducido el valor cambia de golpe.
 */
export function AnimatedNumber({
  value,
  format,
  duration = 600,
}: {
  value: number;
  format: (n: number) => string;
  duration?: number;
}) {
  const [shown, setShown] = useState(value);
  const shownRef = useRef(value);

  useEffect(() => {
    const from = shownRef.current;
    if (from === value) return;
    const ms = prefersReducedMotion() ? 0 : duration;
    const start = performance.now();
    let frame = requestAnimationFrame(function step(now) {
      // El sello del cuadro puede ser anterior a `start`: se acota a [0, 1].
      const t = ms === 0 ? 1 : Math.min(Math.max((now - start) / ms, 0), 1);
      const next = from + (value - from) * easeOutExpo(t);
      shownRef.current = next;
      setShown(next);
      if (t < 1) frame = requestAnimationFrame(step);
    });
    return () => cancelAnimationFrame(frame);
  }, [value, duration]);

  return <>{format(shown)}</>;
}
