import type { AskResponse, CostAnalysis, Provider, TemplateStats, HealthStatus, AIQueryLog } from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000/api/v1";

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  const data = await res.json();
  if (!res.ok) throw new Error(data?.detail || `HTTP ${res.status}`);
  return data as T;
}

export async function askAI(question: string, useTemplateMatching = true): Promise<AskResponse> {
  const url = `${API_BASE}/ask?explain=false`;
  return getJson<AskResponse>(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, use_template_matching: useTemplateMatching })
  });
}

export async function explain(
  question: string,
  sqlQuery?: string,
  results?: AskResponse["results"]
): Promise<{ answer: string }> {
  const url = `${API_BASE}/explain`;
  return getJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question, sql_query: sqlQuery, results })
  });
}

export async function providerSearch(criteria: {
  state?: string | null;
  city?: string | null;
  drg_code?: string | null;
  min_rating?: number | null;
  max_cost?: number | null;
  limit?: number | null;
}): Promise<Provider[]> {
  const url = `${API_BASE}/providers/search`;
  return getJson(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(criteria)
  });
}

export async function fetchCheapest(drg: string, state?: string, limit = 15): Promise<Provider[]> {
  let url = `${API_BASE}/providers/cheapest/${encodeURIComponent(drg)}?limit=${limit}`;
  if (state) url += `&state=${encodeURIComponent(state)}`;
  return getJson(url);
}

export async function fetchHighestRated(state?: string, city?: string, limit = 15): Promise<Provider[]> {
  let url = `${API_BASE}/providers/highest-rated?limit=${limit}`;
  if (state) url += `&state=${encodeURIComponent(state)}`;
  if (city) url += `&city=${encodeURIComponent(city)}`;
  return getJson(url);
}

export async function fetchVolumeLeaders(drg: string, limit = 15): Promise<Provider[]> {
  const url = `${API_BASE}/providers/volume-leaders/${encodeURIComponent(drg)}?limit=${limit}`;
  return getJson(url);
}

export async function fetchCostAnalysis(drg: string, state?: string): Promise<CostAnalysis> {
  let url = `${API_BASE}/analysis/costs/${encodeURIComponent(drg)}`;
  if (state) url += `?state=${encodeURIComponent(state)}`;
  return getJson(url);
}

export async function checkHealth(): Promise<HealthStatus> {
  const url = `${API_BASE}/health`;
  return getJson(url);
}

export async function getTemplateStats(): Promise<TemplateStats> {
  const url = `${API_BASE}/template-stats`;
  return getJson(url);
}

export async function fetchAIQueryLogs(params: { limit?: number; success?: boolean | null; has_results?: boolean | null } = {}): Promise<AIQueryLog[]> {
  const u = new URL(`${API_BASE}/dev/ai-logs`);
  if (params.limit) u.searchParams.set("limit", String(params.limit));
  if (params.success !== undefined && params.success !== null) u.searchParams.set("success", String(params.success));
  if (params.has_results !== undefined && params.has_results !== null) u.searchParams.set("has_results", String(params.has_results));
  return getJson(u.toString());
}

