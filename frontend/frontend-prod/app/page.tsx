"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import type { AskResponse, Provider, CostAnalysis, TemplateStats, HealthStatus } from "@/types/api";
import { formatCurrency, formatRating, friendlyError } from "@/lib/format";

export default function Home() {
  const [tab, setTab] = useState("ai");
  const examples = [
    "Who has the cheapest hip replacement in NY?",
    "Most expensive knee replacement between CA and NY?",
    "Who has the highest rated hospital NY or CA?",
    "Find highest rated hospitals for heart surgery",
    "Which hospitals have ratings above 8 in Florida?",
  ];
  const quickDRGs: Array<{ code: string; name: string }> = [
    { code: "470", name: "Hip Replacement" },
    { code: "191", name: "Heart Surgery" },
    { code: "003", name: "ECMO/Tracheostomy" },
    { code: "292", name: "Heart Failure & Shock" },
    { code: "291", name: "Heart Failure MCC" },
  ];
  // AI Assistant state
  const [question, setQuestion] = useState("");
  const [aiData, setAiData] = useState<AskResponse | null>(null);
  const [aiLoading, setAiLoading] = useState(false);

  // Providers state
  const [criteria, setCriteria] = useState({ state: "", city: "", drg_code: "", min_rating: "", max_cost: "", limit: "10" });
  const [providers, setProviders] = useState<Provider[]>([]);
  const [providerLoading, setProviderLoading] = useState(false);
  const [providerFilter, setProviderFilter] = useState("");
  const [sortKey, setSortKey] = useState<keyof Provider>("provider_name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

  // Analysis state
  const [drgAnalysis, setDrgAnalysis] = useState({ drg: "", state: "" });
  const [analysis, setAnalysis] = useState<CostAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);

  // Status state
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [stats, setStats] = useState<TemplateStats | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  function inferDrgFromContext(q: string, sql?: string, rows?: Array<Record<string, any>> | null): string | undefined {
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
        <TabsList className="grid grid-cols-4 w-full md:w-auto">
          <TabsTrigger value="ai">AI Assistant</TabsTrigger>
          <TabsTrigger value="providers">Providers</TabsTrigger>
          <TabsTrigger value="analysis">Cost Analysis</TabsTrigger>
          <TabsTrigger value="status">Status</TabsTrigger>
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
                      setCriteria((c) => ({
                        ...c,
                        state: state || c.state || "",
                        drg_code: inferredDrg || c.drg_code || "",
                      }));
                      setTab("providers");
                      // Auto-run a provider query when we have enough context
                      try {
                        setProviderLoading(true);
                        const payload = {
                          state: (state || criteria.state || "") || null,
                          city: null,
                          drg_code: (inferredDrg || criteria.drg_code || "") || null,
                          min_rating: criteria.min_rating ? Number(criteria.min_rating) : null,
                          max_cost: criteria.max_cost ? Number(criteria.max_cost) : null,
                          limit: criteria.limit ? Number(criteria.limit) : 10,
                        };
                        const data = await providerSearch(payload);
                        setProviders(data || []);
                      } catch {
                        setProviders([]);
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
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <Input placeholder="State (NY)" maxLength={2} value={criteria.state} onChange={(e) => setCriteria({ ...criteria, state: e.target.value })} />
                <Input placeholder="City (New York)" value={criteria.city} onChange={(e) => setCriteria({ ...criteria, city: e.target.value })} />
                <Input placeholder="DRG Code (470)" value={criteria.drg_code} onChange={(e) => setCriteria({ ...criteria, drg_code: e.target.value })} />
                <Input placeholder="Min Rating (8.0)" value={criteria.min_rating} onChange={(e) => setCriteria({ ...criteria, min_rating: e.target.value })} />
                <Input placeholder="Max Cost (100000)" value={criteria.max_cost} onChange={(e) => setCriteria({ ...criteria, max_cost: e.target.value })} />
                <Input placeholder="Limit (10)" value={criteria.limit} onChange={(e) => setCriteria({ ...criteria, limit: e.target.value })} />
              </div>
              <div className="flex gap-2 mt-1">
                <Button disabled={providerLoading} onClick={async () => {
                  setProviderLoading(true);
                  try {
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
                  } catch (e) {
                    setProviders([]);
                  } finally {
                    setProviderLoading(false);
                  }
                }}>Search Providers</Button>
                <Button variant="secondary" onClick={() => { setCriteria({ state: "", city: "", drg_code: "", min_rating: "", max_cost: "", limit: "10" }); setProviders([]); setProviderFilter(""); }}>Clear</Button>
                <div className="ml-auto flex gap-2">
                  <Button variant="outline" onClick={async () => {
                    setProviderLoading(true);
                    try { const rows = await fetchCheapest("470", criteria.state || undefined, 25); setProviders(rows || []); } catch { setProviders([]); } finally { setProviderLoading(false); }
                  }}>Cheapest DRG 470</Button>
                  <Button variant="outline" onClick={async () => {
                    setProviderLoading(true);
                    try { const rows = await fetchHighestRated(criteria.state || undefined, criteria.city || undefined, 25); setProviders(rows || []); } catch { setProviders([]); } finally { setProviderLoading(false); }
                  }}>Highest Rated</Button>
                  <Button variant="outline" onClick={async () => {
                    if (!criteria.drg_code) return;
                    setProviderLoading(true);
                    try { const rows = await fetchVolumeLeaders(criteria.drg_code, 25); setProviders(rows || []); } catch { setProviders([]); } finally { setProviderLoading(false); }
                  }}>Volume Leaders</Button>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Input placeholder="Filter by provider/city/state..." value={providerFilter} onChange={(e) => setProviderFilter(e.target.value)} />
                <div className="text-xs text-muted-foreground ml-auto">{filteredProviders.length} results</div>
              </div>
              {filteredProviders.length > 0 ? (
                <div className="overflow-x-auto border rounded-md">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        {[
                          "provider_name","provider_city","provider_state","drg_code","drg_description","average_covered_charges","average_total_payments","total_discharges","overall_rating"
                        ].map((k) => (
                          <th key={k} className="px-3 py-2 text-left uppercase text-[10px] tracking-wide text-muted-foreground cursor-pointer" onClick={() => onHeaderClick(k as keyof Provider)}>{k.replaceAll("_"," ")}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {filteredProviders.map((p, i) => (
                        <tr key={i} className="odd:bg-background even:bg-muted/20">
                          <td className="px-3 py-2 font-semibold">{p.provider_name ?? "N/A"}</td>
                          <td className="px-3 py-2">{p.provider_city ?? "N/A"}</td>
                          <td className="px-3 py-2">{p.provider_state ?? "N/A"}</td>
                          <td className="px-3 py-2">{p.drg_code ?? ""}</td>
                          <td className="px-3 py-2">{p.drg_description ?? ""}</td>
                          <td className="px-3 py-2 text-right font-semibold text-green-600">{formatCurrency(p.average_covered_charges)}</td>
                          <td className="px-3 py-2 text-right">{formatCurrency(p.average_total_payments)}</td>
                          <td className="px-3 py-2 text-center">{p.total_discharges ?? ""}</td>
                          <td className="px-3 py-2 text-center font-semibold">{formatRating(p.overall_rating)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="text-xs text-muted-foreground">No results.</div>
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
      </Tabs>
    </div>
  );
}
