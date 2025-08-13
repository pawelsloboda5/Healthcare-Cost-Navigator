"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import ProviderSearchForm, { ProviderCriteria } from "@/components/Providers/ProviderSearchForm";
import ProviderTable from "@/components/Providers/ProviderTable";
import { useMemo, useState } from "react";
import AIForm from "@/components/AI/AIForm";
import AIResults from "@/components/AI/AIResults";
import {
  askAI,
  explain,
  providerSearch,
  fetchCheapest,
  fetchHighestRated,
  fetchVolumeLeaders,
  fetchCostAnalysis,
  checkHealth,
  getTemplateStats,
} from "@/lib/api";
import type { AskResponse, Provider, CostAnalysis, TemplateStats, HealthStatus, AIQueryLog } from "@/types/api";
import { formatCurrency, formatRating, friendlyError } from "@/lib/format";
import { fetchAIQueryLogs } from "@/lib/api";

export default function Home() {
  const [tab, setTab] = useState("ai");
  const examples = [
    "Who has the cheapest hip replacement in NY?",
    "Most expensive knee replacement between CA and NY?",
    "Who has the highest rated hospital NY or CA?",
    "Find highest rated hospitals for heart surgery",
    "Which hospitals have ratings above 8 in Florida?",
    "Show top 10 providers by discharges for DRG 470",
    "Compare average total payments for DRG 191 in TX and CA",
    "Find cheapest DRG 3 provider in NY",
  ];
  const quickDRGs: Array<{ code: string; name: string }> = [
    { code: "470", name: "Hip Replacement" },
    { code: "469", name: "Hip Replacement (MCC)" },
    { code: "3", name: "ECMO/Tracheostomy" },
    { code: "191", name: "Heart Surgery" },
    { code: "190", name: "Heart Surgery (MCC)" },
    { code: "291", name: "Heart Failure MCC" },
    { code: "292", name: "Heart Failure & Shock" },
    { code: "293", name: "Heart Failure w/o MCC" },
    { code: "470", name: "Major Joint Replacement" },
  ];
  // AI Assistant state
  const [question, setQuestion] = useState("");
  const [aiData, setAiData] = useState<AskResponse | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  // Providers state
  const [criteria, setCriteria] = useState<ProviderCriteria>({ state: "", city: "", drg_code: "", min_rating: "", max_cost: "", limit: "10" });
  const [providers, setProviders] = useState<Provider[]>([]);
  const [providerLoading, setProviderLoading] = useState(false);
  const [providerFilter, setProviderFilter] = useState("");
  const [sortKey, setSortKey] = useState<keyof Provider>("provider_name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [providersByState, setProvidersByState] = useState<Record<string, Provider[]>>({});

  // Analysis state
  const [drgAnalysis, setDrgAnalysis] = useState({ drg: "", state: "" });
  const [analysis, setAnalysis] = useState<CostAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // Status state
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [stats, setStats] = useState<TemplateStats | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  // Developer tab state
  const [devLoading, setDevLoading] = useState(false);
  const [devLogs, setDevLogs] = useState<AIQueryLog[]>([]);
  const [devFilter, setDevFilter] = useState<{ success?: string; has_results?: string; limit: string }>({ success: "", has_results: "", limit: "100" });

  function inferDrgFromContext(q: string, sql?: string, rows?: AskResponse["results"] | null): string | undefined {
    // 1) explicit in SQL
    if (sql) {
      const m = sql.match(/drg_code\s*=\s*'?([0-9]{3})'?/i);
      if (m) return m[1];
    }
    // 2) explicit in question
    const qm = (q || "").match(/\bdrg\s*([0-9]{3})\b/i);
    if (qm) return qm[1];
    // 3) present in result rows
    if (rows && rows.length > 0) {
      const codes = rows.map((r) => String(r["drg_code"] || "")).filter(Boolean);
      if (codes.length > 0) return codes[0];
    }
    // 4) phrase mapping via quickDRGs names
    const lowerQ = (q || "").toLowerCase();
    const map: Record<string, string> = Object.fromEntries(quickDRGs.map((d) => [d.name.toLowerCase(), d.code]));
    // Common synonyms
    map["knee replacement"] = "470";
    map["hip replacement"] = "470";
    map["major joint replacement"] = "470";
    for (const key of Object.keys(map)) {
      if (lowerQ.includes(key)) return map[key];
    }
    // 5) fallback via drg_description in rows
    if (rows && rows.length > 0) {
      const desc = String(rows[0]["drg_description"] || "").toLowerCase();
      for (const key of Object.keys(map)) {
        if (desc.includes(key)) return map[key];
      }
    }
    return undefined;
  }

  function extractStatesFromContext(q: string, sql?: string, rows?: AskResponse["results"] | null): string[] {
    const states = new Set<string>();
    // From results columns
    if (rows && rows.length > 0) {
      for (const r of rows) {
        const s = (r["provider_state"] || r["state"]) as string | undefined;
        if (s && /^([A-Za-z]{2})$/.test(String(s))) states.add(String(s).toUpperCase());
      }
    }
    // From SQL IN ('CA','NY')
    if (sql) {
      const m = sql.match(/in\s*\(([^\)]*)\)/i);
      if (m) {
        m[1]
          .split(",")
          .map((x) => x.replace(/['\s]/g, "").toUpperCase())
          .filter((x) => x.length === 2)
          .forEach((x) => states.add(x));
      }
    }
    // From question tokens
    const qm = (q || "").toUpperCase().match(/\b[A-Z]{2}\b/g) || [];
    qm.forEach((x) => states.add(x));
    return Array.from(states);
  }

  const filteredProviders = useMemo(() => {
    const t = providerFilter.trim().toLowerCase();
    const base = t
      ? providers.filter(p =>
          (p.provider_name || "").toLowerCase().includes(t) ||
          (p.provider_city || "").toLowerCase().includes(t) ||
          (p.provider_state || "").toLowerCase().includes(t) ||
          (p.drg_description || "").toLowerCase().includes(t)
        )
      : providers;
    const sorted = [...base].sort((a: Provider, b: Provider) => {
      const va = a?.[sortKey];
      const vb = b?.[sortKey];
      if (typeof va === "number" && typeof vb === "number") return sortDir === "asc" ? va - vb : vb - va;
      return sortDir === "asc" ? String(va).localeCompare(String(vb)) : String(vb).localeCompare(String(va));
    });
    return sorted;
  }, [providers, providerFilter, sortKey, sortDir]);

  function onHeaderClick(k: keyof Provider) {
    if (sortKey === k) setSortDir(d => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(k);
      setSortDir("asc");
    }
  }
  return (
    <div className="min-h-screen w-full px-5 py-6 md:px-8 lg:px-10">
      <div className="mb-5">
        <h1 className="text-2xl font-extrabold tracking-tight text-foreground">Healthcare Cost Navigator</h1>
        <p className="text-sm text-muted-foreground">NL → SQL • Provider Search • Analytics</p>
      </div>

      <Tabs value={tab} onValueChange={setTab} className="w-full">
        <TabsList className="grid grid-cols-5 w-full md:w-auto">
          <TabsTrigger value="ai">AI Assistant</TabsTrigger>
          <TabsTrigger value="providers">Providers</TabsTrigger>
          <TabsTrigger value="analysis">Cost Analysis</TabsTrigger>
          <TabsTrigger value="status">Status</TabsTrigger>
          <TabsTrigger value="developer">Developer</TabsTrigger>
        </TabsList>

        <TabsContent value="ai" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>AI Assistant</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 md:gap-4">
              <AIForm
                question={question}
                onChange={setQuestion}
                onAsk={async () => {
                  setAiLoading(true);
                  try {
                    const data = await askAI(question, true);
                    setAiData(data);
                    if (data.explanation_pending) {
                      explain(question, data.sql_query, data.results)
                        .then((exp) => setAiData((prev) => (prev ? { ...prev, answer: exp.answer } : prev)))
                        .catch(() => {});
                    }
                  } catch (e) {
                    setAiData({ success: false, answer: friendlyError(e, "AI Assistant") } as AskResponse);
                  } finally {
                    setAiLoading(false);
                  }
                }}
                onClear={() => { setQuestion(""); setAiData(null); }}
                loading={aiLoading}
                examples={examples}
                quickDRGs={quickDRGs}
              >
                {aiData ? (
                  <AIResults
                    data={aiData}
                    onOpenInProviders={async ({ state, drg_code }) => {
                      const inferredDrg = drg_code || inferDrgFromContext(question, aiData.sql_query, aiData.results);
                      const inferredStates = extractStatesFromContext(question, aiData.sql_query, aiData.results);
                      setCriteria((c) => ({
                        ...c,
                        state: inferredStates.length > 0 ? inferredStates.join(",") : (state || c.state || ""),
                        drg_code: inferredDrg || c.drg_code || "",
                      }));
                      setTab("providers");
                      // Auto-run a provider query when we have enough context
                      try {
                        setProviderLoading(true);
                        const stateList = inferredStates.length > 0 ? inferredStates : ((state ? [state] : []) as string[]);
                        if (stateList.length <= 1) {
                          const payload = {
                            state: (stateList[0] || criteria.state || "") || null,
                            city: null,
                            drg_code: (inferredDrg || criteria.drg_code || "") || null,
                            min_rating: criteria.min_rating ? Number(criteria.min_rating) : null,
                            max_cost: criteria.max_cost ? Number(criteria.max_cost) : null,
                            limit: criteria.limit ? Number(criteria.limit) : 10,
                          };
                          const data = await providerSearch(payload);
                          setProvidersByState({});
                          setProviders(data || []);
                        } else {
                          const entries: Record<string, Provider[]> = {};
                          for (const st of stateList) {
                            const payload = {
                              state: st,
                              city: null,
                              drg_code: (inferredDrg || criteria.drg_code || "") || null,
                              min_rating: criteria.min_rating ? Number(criteria.min_rating) : null,
                              max_cost: criteria.max_cost ? Number(criteria.max_cost) : null,
                              limit: criteria.limit ? Number(criteria.limit) : 10,
                            };
                            try {
                              const data = await providerSearch(payload);
                              entries[st] = data || [];
                            } catch { entries[st] = []; }
                          }
                          setProviders([]);
                          setProvidersByState(entries);
                        }
                      } catch {
                        setProviders([]);
                        setProvidersByState({});
                      } finally {
                        setProviderLoading(false);
                      }
                    }}
                  />
                ) : (
                  <div className="text-xs text-muted-foreground">
                    Tip: Ask comparative questions like “Who has the most expensive procedure CA or NY?” or ratings like “Highest rated hospitals in TX”. Use DRG codes (e.g., 470) or names.
                  </div>
                )}
              </AIForm>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="providers" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Provider Search</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              <ProviderSearchForm
                criteria={criteria}
                onChange={setCriteria}
                loading={providerLoading}
                onSearchStates={async (states) => {
                  setProviderLoading(true);
                  setProvidersByState({});
                  setProviders([]);
                  try {
                    if (states.length <= 1) {
                      const payload = {
                        state: criteria.state || null,
                        city: criteria.city || null,
                        drg_code: criteria.drg_code || null,
                        min_rating: criteria.min_rating ? Number(criteria.min_rating) : null,
                        max_cost: criteria.max_cost ? Number(criteria.max_cost) : null,
                        limit: criteria.limit ? Number(criteria.limit) : 10,
                      };
                      const data = await providerSearch(payload);
                      setProviders(data || []);
                    } else {
                      const entries: Record<string, Provider[]> = {};
                      for (const st of states) {
                        const payload = {
                          state: st,
                          city: criteria.city || null,
                          drg_code: criteria.drg_code || null,
                          min_rating: criteria.min_rating ? Number(criteria.min_rating) : null,
                          max_cost: criteria.max_cost ? Number(criteria.max_cost) : null,
                          limit: criteria.limit ? Number(criteria.limit) : 10,
                        };
                        try {
                          const data = await providerSearch(payload);
                          entries[st] = data || [];
                        } catch { entries[st] = []; }
                      }
                      setProvidersByState(entries);
                    }
                  } finally {
                    setProviderLoading(false);
                  }
                }}
                onClear={() => { setCriteria({ state: "", city: "", drg_code: "", min_rating: "", max_cost: "", limit: "10" }); setProviders([]); setProvidersByState({}); setProviderFilter(""); }}
                onCheapest470={async (state) => {
                  setProviderLoading(true);
                  try { const rows = await fetchCheapest("470", state || undefined, 25); setProviders(rows || []); setProvidersByState({}); } catch { setProviders([]); } finally { setProviderLoading(false); }
                }}
                onHighestRated={async (state, city) => {
                  setProviderLoading(true);
                  try { const rows = await fetchHighestRated(state || undefined, city || undefined, 25); setProviders(rows || []); setProvidersByState({}); } catch { setProviders([]); } finally { setProviderLoading(false); }
                }}
                onVolumeLeaders={async (drg) => {
                  if (!drg) return;
                  setProviderLoading(true);
                  try { const rows = await fetchVolumeLeaders(drg, 25); setProviders(rows || []); setProvidersByState({}); } catch { setProviders([]); } finally { setProviderLoading(false); }
                }}
              />
              <div className="flex items-center gap-2">
                <Input placeholder="Filter by provider/city/state..." value={providerFilter} onChange={(e) => setProviderFilter(e.target.value)} />
                <div className="text-xs text-muted-foreground ml-auto flex items-center gap-2">
                  {criteria.min_rating ? (
                    <span
                      className={
                        "px-2 py-1 rounded bg-muted/50 " +
                        (Number(criteria.min_rating) >= 8
                          ? "text-green-600"
                          : Number(criteria.min_rating) >= 5
                          ? "text-yellow-600"
                          : "text-red-600")
                      }
                    >
                      Min rating: {formatRating(criteria.min_rating)}
                    </span>
                  ) : null}
                  {Object.keys(providersByState).length > 1 ? "multi-state" : `${filteredProviders.length} results`}
                </div>
              </div>
                  {Object.keys(providersByState).length > 1 ? (
                <div className="grid gap-6">
                  {Object.entries(providersByState).map(([st, rows]) => (
                    <ProviderTable key={st} title={`State: ${st}`} rows={rows} onHeaderClick={onHeaderClick} sortKey={sortKey} sortDir={sortDir} />
                  ))}
                </div>
              ) : (
                filteredProviders.length > 0 ? (
                  <ProviderTable rows={filteredProviders} onHeaderClick={onHeaderClick} sortKey={sortKey} sortDir={sortDir} />
                ) : (
                  <div className="text-xs text-muted-foreground">No results.</div>
                )
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="analysis" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Cost Analysis</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <Input placeholder="DRG Code (470)" value={drgAnalysis.drg} onChange={(e) => setDrgAnalysis({ ...drgAnalysis, drg: e.target.value })} />
                <Input placeholder="State (optional)" value={drgAnalysis.state} onChange={(e) => setDrgAnalysis({ ...drgAnalysis, state: e.target.value })} />
              </div>
              <Button className="w-fit" disabled={analysisLoading} onClick={async () => {
                if (!drgAnalysis.drg) return;
                setAnalysisLoading(true);
                try { const data = await fetchCostAnalysis(drgAnalysis.drg, drgAnalysis.state || undefined); setAnalysis(data); }
                catch { setAnalysis(null); }
                finally { setAnalysisLoading(false); }
              }}>Analyze Costs</Button>
              {analysis ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                  <div className="chip bg-muted/50 rounded px-3 py-2">Average: {formatCurrency(analysis.average_cost)}</div>
                  <div className="chip bg-muted/50 rounded px-3 py-2">Median: {formatCurrency(analysis.median_cost)}</div>
                  <div className="chip bg-muted/50 rounded px-3 py-2">Variance: {formatCurrency(analysis.cost_variance)}</div>
                  <div className="chip bg-muted/50 rounded px-3 py-2">Providers: {analysis.total_providers}</div>
                </div>
              ) : (
                <div className="text-xs text-muted-foreground">Summary metrics will render here.</div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="status" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>System Status</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              <div className="flex gap-2">
                <Button variant="outline" disabled={statusLoading} onClick={async () => {
                  setStatusLoading(true);
                  try { const h = await checkHealth(); setHealth(h); }
                  finally { setStatusLoading(false); }
                }}>Check API</Button>
                <Button variant="outline" disabled={statusLoading} onClick={async () => {
                  setStatusLoading(true);
                  try { const s = await getTemplateStats(); setStats(s); }
                  finally { setStatusLoading(false); }
                }}>Template Statistics</Button>
              </div>
              {health && (
                <div className="text-sm">Status: {health.status} • Service: {health.service}</div>
              )}
              {stats?.template_statistics ? (
                <div className="overflow-x-auto border rounded-md text-sm">
                  <table className="w-full">
                    <thead className="bg-muted/50">
                      <tr><th className="px-3 py-2 text-left">Metric</th><th className="px-3 py-2 text-left">Value</th></tr>
                    </thead>
                    <tbody>
                      {Object.entries(stats.template_statistics).map(([k,v]) => (
                        <tr key={k} className="odd:bg-background even:bg-muted/20"><td className="px-3 py-2">{k}</td><td className="px-3 py-2">{String(v)}</td></tr>
                      ))}
                    </tbody>
                  </table>
        </div>
              ) : (
                <div className="text-xs text-muted-foreground">Template stats will render here.</div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="developer" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle>Developer – AI Query Logs</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              <div className="grid grid-cols-1 md:grid-cols-5 gap-2">
                <Input placeholder="Limit (100)" value={devFilter.limit} onChange={(e) => setDevFilter({ ...devFilter, limit: e.target.value })} />
                <Input placeholder="Success: true|false (optional)" value={devFilter.success}
                  onChange={(e) => setDevFilter({ ...devFilter, success: e.target.value })} />
                <Input placeholder="Has Results: true|false (optional)" value={devFilter.has_results}
                  onChange={(e) => setDevFilter({ ...devFilter, has_results: e.target.value })} />
                <Button disabled={devLoading} onClick={async () => {
                  setDevLoading(true);
                  try {
                    const successFilter = devFilter.success ?? "";
                    const hasResultsFilter = devFilter.has_results ?? "";
                    const logs = await fetchAIQueryLogs({
                      limit: devFilter.limit ? Number(devFilter.limit) : 100,
                      success: successFilter === "" ? null : (successFilter.toLowerCase() === "true"),
                      has_results: hasResultsFilter === "" ? null : (hasResultsFilter.toLowerCase() === "true"),
                    });
                    setDevLogs(logs || []);
                  } catch {
                    setDevLogs([]);
                  } finally {
                    setDevLoading(false);
                  }
                }}>Refresh</Button>
                <Button variant="secondary" onClick={() => { setDevLogs([]); setDevFilter({ success: "", has_results: "", limit: "100" }); }}>Clear</Button>
              </div>

              {devLogs.length > 0 ? (
                <div className="overflow-x-auto border rounded-md">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        {["created_at","success","has_results","result_count","template_used","confidence_score","execution_time_ms","user_question"].map((k) => (
                          <th key={k} className="px-3 py-2 text-left uppercase text-[10px] tracking-wide text-muted-foreground">{k.replaceAll("_"," ")}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {devLogs.map((r) => (
                        <tr key={r.id} className="odd:bg-background even:bg-muted/20 align-top">
                          <td className="px-3 py-2 whitespace-nowrap">{new Date(r.created_at).toLocaleString()}</td>
                          <td className="px-3 py-2">{String(r.success)}</td>
                          <td className="px-3 py-2">{String(r.has_results)}</td>
                          <td className="px-3 py-2 text-right">{r.result_count}</td>
                          <td className="px-3 py-2">{r.template_used ?? ""}</td>
                          <td className="px-3 py-2">{r.confidence_score ?? ""}</td>
                          <td className="px-3 py-2 text-right">{r.execution_time_ms ?? ""}</td>
                          <td className="px-3 py-2 max-w-[520px] truncate" title={r.user_question}>{r.user_question}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-xs text-muted-foreground">No logs.</div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
