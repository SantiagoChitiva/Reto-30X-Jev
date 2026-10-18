import type { Content, Maturity, Route, Segment } from "@/lib/types";

export const ROUTE_LABELS: Record<Route, string> = {
  auto: "Automática",
  safe: "Prudente",
  human: "Humana",
};

export const SEGMENT_LABELS: Record<Segment, string> = {
  fundador_ventas: "Fundador · ventas",
  fundador_escala: "Fundador · escalar",
  lider_comercial: "Líder comercial",
  ejecutivo_ia: "Ejecutivo · IA",
  perfil_tecnico: "Perfil técnico",
  explorador: "Explorador",
  otro: "Otro",
};

export const MATURITY_LABELS: Record<Maturity, string> = {
  baja: "Baja",
  media: "Media",
  alta: "Alta",
};

export const CONTENT_LABELS: Record<Content, string> = {
  ai_sales: "AI Sales",
  inmersion_ejecutiva: "Inmersión Ejecutiva",
  sales_machine: "Sales Machine",
  hardcore_ai: "Hardcore AI",
  achievers: "Achievers",
  nutricion: "Contenido gratuito",
  otro: "Otro",
};

/** Acciones que puede elegir quien revisa un caso. `ninguna` se envía como `null`. */
export const REVIEW_ACTIONS = [
  "send:ai_sales",
  "send:inmersion_ejecutiva",
  "send:sales_machine",
  "send:hardcore_ai",
  "send:achievers",
  "send:nutricion",
  "notify_sales",
  "ninguna",
] as const;
export type ReviewAction = (typeof REVIEW_ACTIONS)[number];

export function labelOf<K extends string>(
  labels: Record<K, string>,
  value: string,
): string {
  return labels[value as K] ?? value;
}

export function actionLabel(action: string | null): string {
  if (action === null || action === "ninguna") return "Ninguna";
  if (action === "notify_sales") return "Avisar a ventas";
  if (action.startsWith("send:")) {
    return `Enviar ${labelOf(CONTENT_LABELS, action.slice(5))}`;
  }
  return action;
}

const integer = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 });
const oneDecimal = new Intl.NumberFormat("es-CO", {
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

export const formatInt = (n: number) => integer.format(n);
export const formatPct = (n: number) => `${oneDecimal.format(n)} %`;
export const formatMs = (n: number) => `${integer.format(n)} ms`;
export const formatP = (p: number) => p.toFixed(2);

export function formatUsd(n: number): string {
  const digits = n === 0 ? 2 : n < 0.01 ? 6 : n < 1 ? 4 : 2;
  return `US$ ${n.toLocaleString("es-CO", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`;
}

export function formatTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleTimeString("es-CO", { hour12: false });
}
