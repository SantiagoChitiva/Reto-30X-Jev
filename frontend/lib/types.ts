// Tipos del contrato de la API. Fuente de verdad: ../CONTRACTS.md

export const ROUTES = ["auto", "llm", "human"] as const;
export type Route = (typeof ROUTES)[number];

export const SEGMENTS = [
  "explorador",
  "lider_negocio",
  "lider_tecnico",
  "equipo_adopcion",
  "lider_adopcion",
  "otro",
] as const;
export type Segment = (typeof SEGMENTS)[number];

export type Maturity = "baja" | "media" | "alta";

export type Content =
  | "intro_ia"
  | "caso_de_exito"
  | "taller_practico"
  | "programa_ejecutivo"
  | "otro";

/** Respuesta de JEV: un valor con su probabilidad calibrada `p` (0 a 1). */
export interface Scored<T> {
  value: T;
  p: number;
}

export interface Guardrail {
  passed: boolean;
  p: number;
  reason: string | null;
}

export interface Decision {
  decision_id: string;
  person_id: string;
  event_id: string;
  segment: Scored<Segment>;
  maturity: Scored<Maturity>;
  sales_ready: Scored<boolean>;
  content: Scored<Content>;
  route: Route;
  /** Solo se llena cuando `route = auto`. */
  guardrail: Guardrail | null;
  /** `send:<content>` | `notify_sales` | `null` */
  action: string | null;
  /** Texto del LLM cuando `route = llm`. */
  explanation: string | null;
  latency_ms: number;
  cost_usd: number;
  created_at: string;
}

export interface Review {
  review_id: string;
  decision_id: string;
  status: "pending" | "resolved";
  resolved_segment: Segment | null;
  resolved_action: string | null;
  created_at: string;
}

/** Body de `POST /review/{review_id}`. */
export interface ReviewResolution {
  segment: Segment;
  action: string | null;
}

export interface Metrics {
  total_decisions: number;
  auto_pct: number;
  llm_pct: number;
  human_pct: number;
  guardrail_blocked: number;
  total_cost_usd: number;
  cost_per_1k_usd: number;
  latency_p50_ms: number;
  latency_p95_ms: number;
  running: boolean;
}

export interface Transition {
  from: Segment;
  to: Segment;
  count: number;
}

export interface SimulateResponse {
  accepted: number;
}
