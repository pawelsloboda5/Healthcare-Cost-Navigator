"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useMemo, useState } from "react";
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

      <Tabs defaultValue="ai" className="w-full">
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
              <div className="grid gap-3 md:grid-cols-3">
                {/* Main composer */}
                <div className="md:col-span-2 grid gap-3">
                  <Textarea
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    onKeyDown={async (e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        (document.getElementById("btnAskAI") as HTMLButtonElement)?.click();
                      }
                    }}
                    placeholder="Ask about costs, ratings, DRGs… (Press Enter to ask)"
                    rows={3}
                  />
                  <div className="flex gap-2">
                    <Button id="btnAskAI" disabled={aiLoading} onClick={async () => {
                  setAiLoading(true);
                  try {
                    const data = await askAI(question, true);
                    setAiData(data);
                    if (data.explanation_pending) {
                      // fire and forget explanation
                      explain(question, data.sql_query, data.results).then(exp => setAiData(prev => prev ? { ...prev, answer: exp.answer } : prev)).catch(() => {});
                    }
                  } catch (e) {
                    setAiData({ success: false, answer: friendlyError(e, "AI Assistant") } as AskResponse);
                  } finally {
                    setAiLoading(false);
                  }
                }}>{aiLoading ? "Asking…" : "Ask AI"}</Button>
                    <Button variant="secondary" onClick={() => { setQuestion(""); setAiData(null); }}>Clear</Button>
                  </div>
                  {aiData ? (
                <div className="space-y-2">
                  <div className="text-sm"><strong>Answer:</strong> {aiData.answer}</div>
                  <div className="text-xs text-muted-foreground">
                    {aiData.template_used !== undefined && (
                      <div>Template: #{aiData.template_used} {aiData.confidence_score !== undefined && `(Confidence: ${(aiData.confidence_score * 100).toFixed(1)}%)`}</div>
                    )}
                    {aiData.sql_query && (<div className="mt-1"><strong>SQL:</strong><pre className="mt-1 whitespace-pre-wrap text-[11px] p-2 rounded bg-muted/40 border border-border">{aiData.sql_query}</pre></div>)}
                    {aiData.execution_time_ms !== undefined && (<div>Execution Time: {aiData.execution_time_ms}ms</div>)}
                  </div>
                  {aiData.results && aiData.results.length > 0 && (
                    <div className="overflow-x-auto border rounded-md">
                      <table className="w-full text-sm">
                        <thead className="bg-muted/50">
                          <tr>
                            {Object.keys(aiData.results[0]).map((k) => (
                              <th key={k} className="text-left px-3 py-2 uppercase text-[10px] tracking-wide text-muted-foreground">{k.replaceAll("_"," ")}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {aiData.results.map((r, i) => (
                            <tr key={i} className="odd:bg-background even:bg-muted/20">
                              {Object.keys(aiData.results![0]).map((k) => (
                                <td key={k} className="px-3 py-2 align-top">{String(r[k] ?? "N/A")}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
                  ) : (
                    <div className="text-xs text-muted-foreground">
                      Tip: Ask comparative questions like “Who has the most expensive procedure CA or NY?” or ratings like “Highest rated hospitals in TX”. Use DRG codes (e.g., 470) or names.
                    </div>
                  )}
                </div>

                {/* Sidebar with examples and DRGs */}
                <div className="md:col-span-1 grid gap-3">
                  <div>
                    <div className="text-xs font-semibold uppercase text-muted-foreground mb-2">Examples</div>
                    <div className="grid gap-2">
                      {examples.map((ex, i) => (
                        <Button key={i} variant="outline" className="justify-start h-8 px-2 text-left text-xs" onClick={() => setQuestion(ex)}>
                          {ex}
                        </Button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs font-semibold uppercase text-muted-foreground mb-2">Common DRGs</div>
                    <div className="flex flex-wrap gap-2">
                      {quickDRGs.map(({ code, name }) => (
                        <Button key={code} variant="secondary" className="h-8 px-2 text-xs" onClick={() => setQuestion(`Who has the cheapest ${name.toLowerCase()} in NY? (DRG ${code})`)}>
                          {code} • {name}
                        </Button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
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
