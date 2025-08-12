"use client";

import { useMemo, useState } from "react";
import type { AskResponse } from "@/types/api";
import { Button } from "@/components/ui/button";
import { Chart } from "@/lib/charts";

type AIResultsProps = {
  data: AskResponse;
  onOpenInProviders?: (params: { state?: string; drg_code?: string }) => void;
};

function toCsv(rows: Array<Record<string, any>>): string {
  if (!rows || rows.length === 0) return "";
  const headers = Object.keys(rows[0]);
  const escape = (v: unknown) => {
    const s = String(v ?? "");
    return /[,"]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  const lines = [headers.join(",")].concat(
    rows.map((r) => headers.map((h) => escape(r[h])).join(","))
  );
  return lines.join("\n");
}

function inferChartData(rows: Array<Record<string, any>>): { labels: string[]; values: number[] } | null {
  if (!rows || rows.length === 0) return null;
  const sample = rows[0];
  const keys = Object.keys(sample);
  // prefer state/category + a numeric value
  const categoryKey = keys.find((k) => /state|city|name|description/i.test(k));
  const numericKey = keys.find((k) => typeof sample[k] === "number");
  if (!categoryKey || !numericKey) return null;
  const labels: string[] = [];
  const values: number[] = [];
  rows.slice(0, 10).forEach((r) => {
    const l = String(r[categoryKey] ?? "");
    const v = Number(r[numericKey]);
    if (l && Number.isFinite(v)) { labels.push(l); values.push(v); }
  });
  if (labels.length < 2) return null;
  return { labels, values };
}

export default function AIResults({ data, onOpenInProviders }: AIResultsProps) {
  const [chartId] = useState(() => `chart-${Math.random().toString(36).slice(2)}`);

  const csv = useMemo(() => (data.results ? toCsv(data.results) : ""), [data.results]);
  const chartData = useMemo(() => (data.results ? inferChartData(data.results) : null), [data.results]);

  function copy(text: string) {
    if (!text) return;
    navigator.clipboard.writeText(text).catch(() => {});
  }

  function openInProviders() {
    if (!onOpenInProviders || !data?.results || data.results.length === 0) return;
    const sample = data.results[0];
    const state = (sample["provider_state"] || sample["state"]) as string | undefined;
    const drg = (sample["drg_code"]) as string | undefined;
    onOpenInProviders({ state, drg_code: drg });
  }

  return (
    <div className="space-y-2">
      <div className="text-sm"><strong>Answer:</strong> {data.answer}</div>
      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground items-center">
        {data.template_used !== undefined && (
          <div>Template: #{data.template_used}</div>
        )}
        {data.confidence_score !== undefined && (
          <div className={
            data.confidence_score >= 0.8 ? "text-green-600" : data.confidence_score >= 0.5 ? "text-yellow-600" : "text-red-600"
          }>
            Confidence: {(data.confidence_score * 100).toFixed(1)}%
          </div>
        )}
        {data.execution_time_ms !== undefined && (<div>Time: {data.execution_time_ms}ms</div>)}
        {onOpenInProviders && (
          <Button variant="outline" size="sm" onClick={openInProviders}>Open in Provider Search</Button>
        )}
      </div>

      {data.sql_query && (
        <div className="mt-1">
          <div className="flex items-center justify-between">
            <strong className="text-xs">SQL</strong>
            <Button variant="ghost" size="sm" onClick={() => copy(data.sql_query!)}>Copy SQL</Button>
          </div>
          <pre className="mt-1 whitespace-pre-wrap text-[11px] p-2 rounded bg-muted/40 border border-border">{data.sql_query}</pre>
        </div>
      )}

      {data.results && data.results.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <strong className="text-xs">Results</strong>
            <Button variant="ghost" size="sm" onClick={() => copy(csv)}>Copy CSV</Button>
          </div>
          <div className="overflow-x-auto border rounded-md">
            <table className="w-full text-sm">
              <thead className="bg-muted/50">
                <tr>
                  {Object.keys(data.results[0]).map((k) => (
                    <th key={k} className="text-left px-3 py-2 uppercase text-[10px] tracking-wide text-muted-foreground">{k.replaceAll("_"," ")}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.results.map((r, i) => (
                  <tr key={i} className="odd:bg-background even:bg-muted/20">
                    {Object.keys(data.results![0]).map((k) => (
                      <td key={k} className="px-3 py-2 align-top">{String(r[k] ?? "N/A")}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {chartData && (
            <div className="mt-2">
              <canvas id={chartId} height={140}></canvas>
            </div>
          )}
        </div>
      )}

      {/* Initialize chart lazily to avoid SSR issues */}
      {chartData && (
        <ChartComponent mountId={chartId} labels={chartData.labels} values={chartData.values} />
      )}
    </div>
  );
}

function ChartComponent({ mountId, labels, values }: { mountId: string; labels: string[]; values: number[] }) {
  useState(() => {
    const el = document.getElementById(mountId) as HTMLCanvasElement | null;
    if (!el) return;
    const chart = new Chart(el, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Value",
            data: values,
            backgroundColor: "rgba(99, 102, 241, 0.5)",
          },
        ],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: { x: { ticks: { maxRotation: 45, minRotation: 0 } }, y: { beginAtZero: true } },
      },
    });
    return () => chart?.destroy();
  });
  return null;
}


