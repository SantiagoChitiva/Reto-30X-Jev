// Tipos del contrato de la API. Fuente de verdad: ../CONTRACTS.md

export const ROUTES = ["auto", "safe", "human"] as const;
export type Route = (typeof ROUTES)[number];

export const SEGMENTS = [
  "fundador_ventas",
  "fundador_escala",
  "lider_comercial",
  "ejecutivo_ia",
  "perfil_tecnico",
  "explorador",
  "otro",
] as const;
export type Segment = (typeof SEGMENTS)[number];

export type Maturity = "baja" | "media" | "alta";

/** Ofertas reales de 30X (programas) + contenido gratuito de nutrición. */
export const CONTENTS = [
  "ai_sales",
  "inmersion_ejecutiva",
  "sales_machine",
  "hardcore_ai",
  "achievers",
  "nutricion",
  "otro",
] as const;
export type Content = (typeof CONTENTS)[number];

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
  /** Por qué se tomó la acción prudente cuando `route = safe`. */
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

/** Ficha de la persona en el CRM (`GET /crm`): lo último que se decidió. */
export interface CrmRecord {
  person_id: string;
  segment: Segment;
  maturity: Maturity;
  sales_ready: boolean;
  suggested_program: Content;
  confidence: number;
  decided_by: "jev" | "jev_por_confirmar" | "humano";
  last_action: string | null;
  decision_id: string;
  updated_at: string;
}

export interface Metrics {
  total_decisions: number;
  auto_pct: number;
  safe_pct: number;
  human_pct: number;
  guardrail_blocked: number;
  /** Acciones repetidas que frenó el antispam (en código, sin llamar a JEV). */
  spam_suppressed: number;
  /** Eventos de la última simulación que no se pudieron procesar. */
  failed_events?: number;
  last_error?: string | null;
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

export type Question = "segment" | "content" | "sales_ready";
type Accuracy = Record<Question, number>;

/** `GET /evaluation`: JEV contra el set etiquetado y frente a un LLM. */
export interface Evaluation {
  created_at: string;
  mock_jev: boolean;
  n: number;
  labels: string;
  reviewed_labels: number;
  accuracy: Accuracy;
  by_route: Record<Route, Accuracy & { n: number; pct: number }>;
  jev: {
    cost_usd: number;
    cost_per_1k_usd: number;
    latency_p50_ms: number;
    latency_p95_ms: number;
    wall_ms: number;
  };
  llm: {
    model: string;
    cost_usd: number;
    cost_per_1k_usd: number;
    latency_ms_typical: number;
    estimated: boolean;
  };
}

export interface SimulateResponse {
  accepted: number;
}
