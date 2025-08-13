"use client";

import type { Provider } from "@/types/api";

type ProviderTableProps = {
  title?: string;
  rows: Provider[];
  onHeaderClick?: (k: keyof Provider) => void;
};

export default function ProviderTable({ title, rows, onHeaderClick }: ProviderTableProps) {
  return (
    <div className="grid gap-2">
      {title && <div className="text-xs font-semibold uppercase text-muted-foreground">{title}</div>}
      {rows.length > 0 ? (
        <div className="overflow-x-auto border rounded-md">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                {["provider_name","provider_city","provider_state","drg_code","drg_description","average_covered_charges","average_total_payments","total_discharges","overall_rating"].map((k) => (
                  <th key={k} className="px-3 py-2 text-left uppercase text-[10px] tracking-wide text-muted-foreground cursor-pointer" onClick={() => onHeaderClick?.(k as keyof Provider)}>
                    {k.replaceAll("_"," ")}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((p, i) => (
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
    </div>
  );
}

import { formatCurrency, formatRating } from "@/lib/format";


