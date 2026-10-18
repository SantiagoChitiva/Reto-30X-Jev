"use client";

import { useEffect, useRef } from "react";

import { AnimatedNumber } from "@/components/dashboard/animated-number";
import { RouteDot } from "@/components/dashboard/route-badge";
import { ROUTE_LABELS, formatInt, formatPct } from "@/lib/format";
import { ROUTES, type Metrics, type Route } from "@/lib/types";

/** Decisiones que llenan el campo: una simulación completa. */
const CAPACITY = 10_000;
const SPACING = 12;
const HEIGHT = 132;
const FLASH_MS = 1400;
/** Tope de destellos por consulta, para que el canvas no se sature. */
const MAX_FLASHES = 160;

const ROUTE_VARS: Record<Route, string> = {
  auto: "--route-auto",
  safe: "--route-safe",
  human: "--route-human",
};
const PCT_KEY = { auto: "auto_pct", safe: "safe_pct", human: "human_pct" } as const;

interface Field {
  cols: number;
  rows: number;
  /** Orden fijo y aleatorio en que se encienden los puntos. */
  order: number[];
  /** Ruta de cada punto encendido; `undefined` = apagado. */
  route: (Route | undefined)[];
  /** Momento del último destello de cada punto. */
  flashAt: Float64Array;
  lit: number;
}

function shuffle(n: number) {
  const a = Array.from({ length: n }, (_, i) => i);
  for (let i = n - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

/** Elige una ruta al azar con el reparto actual. */
function sampleRoute(m: Metrics): Route {
  const total = ROUTES.reduce((s, r) => s + m[PCT_KEY[r]], 0);
  let x = Math.random() * (total || 1);
  for (const r of ROUTES) {
    x -= m[PCT_KEY[r]];
    if (x <= 0) return r;
  }
  return "auto";
}

/**
 * El pulso de la audiencia: cada punto es un grupo de decisiones. Las
 * decisiones nuevas encienden puntos con el color de su ruta y dejan una
 * huella tenue; con 10.000 decisiones el campo queda lleno.
 */
export function PulseField({ metrics }: { metrics: Metrics | undefined }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fieldRef = useRef<Field | null>(null);
  const totalRef = useRef<number | undefined>(undefined);
  const metricsRef = useRef(metrics);
  const drawRef = useRef<() => void>(() => {});

  // Dibujo y tamaño: se montan una vez y viven en refs.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const styles = getComputedStyle(canvas);
    const colors = Object.fromEntries(
      ROUTES.map((r) => [r, styles.getPropertyValue(ROUTE_VARS[r]).trim()]),
    ) as Record<Route, string>;
    let frame = 0;

    function draw() {
      frame = 0;
      const field = fieldRef.current;
      if (!field || !ctx || !canvas) return;
      const now = performance.now();
      const dpr = window.devicePixelRatio || 1;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const offsetX = (canvas.clientWidth - (field.cols - 1) * SPACING) / 2;
      const offsetY = (HEIGHT - (field.rows - 1) * SPACING) / 2;
      let animating = false;

      for (let i = 0; i < field.cols * field.rows; i++) {
        const x = offsetX + (i % field.cols) * SPACING;
        const y = offsetY + Math.floor(i / field.cols) * SPACING;
        const route = field.route[i];
        const age = now - field.flashAt[i];
        const flash =
          route && !reduced.matches && age < FLASH_MS
            ? 1 - age / FLASH_MS
            : 0;
        if (flash > 0) animating = true;

        if (!route) {
          ctx.globalAlpha = 0.14;
          ctx.fillStyle = "#ffffff";
          ctx.beginPath();
          ctx.arc(x, y, 1.4, 0, Math.PI * 2);
          ctx.fill();
          continue;
        }
        ctx.fillStyle = colors[route];
        if (flash > 0) {
          // Halo que se apaga con el destello.
          ctx.globalAlpha = 0.22 * flash;
          ctx.beginPath();
          ctx.arc(x, y, 2 + 4 * flash, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.globalAlpha = 0.42 + 0.58 * flash;
        ctx.beginPath();
        ctx.arc(x, y, 1.8 + 0.8 * flash, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      if (animating) frame = requestAnimationFrame(draw);
    }
    drawRef.current = () => {
      if (!frame) frame = requestAnimationFrame(draw);
    };

    function resize() {
      if (!canvas) return;
      const width = canvas.clientWidth;
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(HEIGHT * dpr);
      const cols = Math.max(1, Math.floor((width - SPACING) / SPACING));
      const rows = Math.floor((HEIGHT - SPACING) / SPACING);
      const prev = fieldRef.current;
      if (!prev || prev.cols !== cols || prev.rows !== rows) {
        // Nueva cuadrícula: se vuelve a sembrar con el total actual, sin destellos.
        const n = cols * rows;
        fieldRef.current = {
          cols,
          rows,
          order: shuffle(n),
          route: new Array(n),
          flashAt: new Float64Array(n).fill(-Infinity),
          lit: 0,
        };
        const m = metricsRef.current;
        if (m) light(fieldRef.current, m, m.total_decisions, false);
      }
      draw();
    }

    const observer = new ResizeObserver(resize);
    observer.observe(canvas);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
      drawRef.current = () => {};
    };
  }, []);

  // Cada consulta nueva de /metrics enciende los puntos que le tocan.
  useEffect(() => {
    metricsRef.current = metrics;
    const field = fieldRef.current;
    if (!metrics || !field) return;
    const prev = totalRef.current;
    const total = metrics.total_decisions;
    totalRef.current = total;
    if (prev === undefined || total < prev) {
      // Primera lectura o backend reiniciado: se siembra sin destellos.
      field.route.fill(undefined);
      field.lit = 0;
      light(field, metrics, total, false);
    } else if (total > prev) {
      light(field, metrics, total, true, total - prev);
    } else {
      return;
    }
    drawRef.current();
  }, [metrics]);

  const total = metrics?.total_decisions ?? 0;
  const label = metrics
    ? `${formatInt(total)} decisiones. ` +
      ROUTES.map(
        (r) => `${ROUTE_LABELS[r]} ${formatPct(metrics[PCT_KEY[r]])}`,
      ).join(", ")
    : "Cargando decisiones";

  return (
    <figure className="flex flex-col gap-3">
      <canvas
        ref={canvasRef}
        role="img"
        aria-label={label}
        style={{ height: HEIGHT }}
        className="w-full [mask-image:linear-gradient(to_right,transparent,black_12%,black_88%,transparent)]"
      />
      <figcaption className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2 text-sm">
        <span className="text-muted-foreground">
          <span className="text-lg font-bold tracking-tight text-foreground tabular-nums">
            <AnimatedNumber value={total} format={formatInt} />
          </span>{" "}
          decisiones · cada destello es una decisión nueva
        </span>
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-xs">
          {ROUTES.map((r) => (
            <li key={r} className="flex items-center gap-1.5">
              <RouteDot route={r} />
              {ROUTE_LABELS[r]}
            </li>
          ))}
        </ul>
      </figcaption>
    </figure>
  );
}

/**
 * Enciende los puntos que corresponden a `total`. Pasada la capacidad, el
 * campo ya está lleno y los destellos caen sobre puntos al azar.
 */
function light(
  field: Field,
  metrics: Metrics,
  total: number,
  flash: boolean,
  delta = 0,
) {
  const n = field.cols * field.rows;
  const target = Math.min(n, Math.round((total / CAPACITY) * n));
  const now = performance.now();
  let flashes = 0;

  for (; field.lit < target; field.lit++) {
    const i = field.order[field.lit];
    field.route[i] = sampleRoute(metrics);
    if (flash && flashes < MAX_FLASHES) {
      field.flashAt[i] = now;
      flashes++;
    }
  }

  if (flash && field.lit >= n) {
    // Campo lleno: la actividad sigue viéndose como destellos sueltos.
    const extra = Math.min(MAX_FLASHES - flashes, Math.ceil((delta / CAPACITY) * n));
    for (let k = 0; k < extra; k++) {
      const i = Math.floor(Math.random() * n);
      field.route[i] = sampleRoute(metrics);
      field.flashAt[i] = now;
    }
  }
}
