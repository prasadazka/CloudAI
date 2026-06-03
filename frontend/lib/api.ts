// Typed fetch wrapper. Routes through Next.js /api/* rewrites
// so the browser doesn't hit CORS in dev.

import type {
  ApproveDeployRequest,
  ApproveDeployResponse,
  FullWorkflow,
  TraceResponse,
  WorkflowCreateRequest,
  WorkflowCreateResponse,
  WorkflowSummary,
} from "./types";

const API_BASE = "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = "";
    try { detail = (await res.json())?.detail ?? ""; } catch {}
    throw new Error(`${res.status} ${res.statusText}${detail ? ` — ${detail}` : ""}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  createWorkflow: (body: WorkflowCreateRequest) =>
    request<WorkflowCreateResponse>("/workflows", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  listWorkflows: (limit = 20) =>
    request<WorkflowSummary[]>(`/workflows?limit=${limit}`),

  getWorkflow: (id: string) => request<WorkflowSummary>(`/workflows/${id}`),

  getTrace: (id: string) => request<TraceResponse>(`/workflows/${id}/trace`),

  getFull: (id: string) => request<FullWorkflow>(`/workflows/${id}/full`),

  approveDeploy: (id: string, body: ApproveDeployRequest) =>
    request<ApproveDeployResponse>(`/workflows/${id}/deploy`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  pdfUrl: (id: string) => `${API_BASE}/workflows/${id}/pdf`,
};
