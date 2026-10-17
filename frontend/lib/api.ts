import type {
  CrmRecord,
  Decision,
  Evaluation,
  Metrics,
  Review,
  ReviewResolution,
  Route,
  SimulateResponse,
  Transition,
} from "@/lib/types";

export const API_URL = (
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      cache: "no-store",
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError(`No se pudo conectar con la API en ${API_URL}`);
  }
  if (!res.ok) {
    throw new ApiError(`La API respondió ${res.status} en ${path}`, res.status);
  }
  return (await res.json()) as T;
}

export function getDecisions(
  { limit = 50, route }: { limit?: number; route?: Route },
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (route) params.set("route", route);
  return request<Decision[]>(`/decisions?${params}`, { signal });
}

export function getMetrics(signal?: AbortSignal) {
  return request<Metrics>("/metrics", { signal });
}

/** `null` si todavía no se ha corrido `python -m app.evaluate` (404). */
export async function getEvaluation(signal?: AbortSignal) {
  try {
    return await request<Evaluation>("/evaluation", { signal });
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) return null;
    throw err;
  }
}

/** Fichas del CRM, de la más reciente a la más antigua. */
export function getCrm(
  { limit = 50, salesReady }: { limit?: number; salesReady?: boolean },
  signal?: AbortSignal,
) {
  const params = new URLSearchParams({ limit: String(limit) });
  if (salesReady !== undefined) params.set("sales_ready", String(salesReady));
  return request<CrmRecord[]>(`/crm?${params}`, { signal });
}

export function getTransitions(signal?: AbortSignal) {
  return request<Transition[]>("/transitions", { signal });
}

export function getReviewQueue(signal?: AbortSignal) {
  return request<Review[]>("/review-queue", { signal });
}

export function resolveReview(reviewId: string, body: ReviewResolution) {
  return request<Review>(`/review/${encodeURIComponent(reviewId)}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function simulate(n: number) {
  return request<SimulateResponse>("/simulate", {
    method: "POST",
    body: JSON.stringify({ n }),
  });
}
