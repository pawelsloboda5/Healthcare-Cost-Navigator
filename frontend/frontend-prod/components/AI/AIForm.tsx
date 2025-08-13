"use client";

import { useMemo } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

type QuickDrg = { code: string; name: string };

type AIFormProps = {
  question: string;
  onChange: (v: string) => void;
  onAsk: () => void | Promise<void>;
  onClear: () => void;
  loading?: boolean;
  examples?: string[];
  quickDRGs?: QuickDrg[];
  children?: React.ReactNode; // place results below the composer
};

const STATE_CODES = new Set([
  "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY","DC"
]);

export default function AIForm({
  question,
  onChange,
  onAsk,
  onClear,
  loading,
  examples = [],
  quickDRGs = [],
  children,
}: AIFormProps) {
  const detectedStates = useMemo(() => {
    const matches = (question || "").toUpperCase().match(/\b[A-Z]{2}\b/g) || [];
    const unique = Array.from(new Set(matches)).filter((s) => STATE_CODES.has(s));
    return unique.slice(0, 6);
  }, [question]);

  const detectedDrgs = useMemo(() => {
    const codes: string[] = [];
    const re = /\b(?:DRG\s*)?(\d{3})\b/gi;
    let m;
    while ((m = re.exec(question || ""))) {
      codes.push(m[1]);
    }
    return Array.from(new Set(codes)).slice(0, 4);
  }, [question]);

  function removeToken(token: string) {
    const next = (question || "")
      .replace(new RegExp(`\\bDRG\\s*${token}\\b`, "gi"), "")
      .replace(new RegExp(`\\b${token}\\b`, "gi"), "")
      .replace(/\s{2,}/g, " ")
      .trim();
    onChange(next);
  }

  return (
    <div className="grid gap-3 md:grid-cols-3">
      {/* Composer */}
      <div className="md:col-span-2 grid gap-3">
        <Textarea
          value={question}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={async (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              const btn = document.getElementById("btnAskAI");
              if (btn) (btn as HTMLButtonElement).click();
            }
          }}
          placeholder="Ask about costs, ratings, DRGs… (Press Enter to ask)"
          rows={3}
        />
        {/* Detected chips */}
        {(detectedStates.length > 0 || detectedDrgs.length > 0) && (
          <div className="flex flex-wrap gap-2 text-xs">
            {detectedStates.map((s) => (
              <button
                key={s}
                onClick={() => removeToken(s)}
                className="px-2 py-1 rounded bg-accent text-accent-foreground hover:opacity-90"
                title="Remove from question"
              >
                {s} ✕
              </button>
            ))}
            {detectedDrgs.map((d) => (
              <button
                key={d}
                onClick={() => removeToken(d)}
                className="px-2 py-1 rounded bg-muted text-foreground hover:opacity-90 border"
                title="Remove from question"
              >
                DRG {d} ✕
              </button>
            ))}
          </div>
        )}
        <div className="flex gap-2">
          <Button id="btnAskAI" disabled={!!loading} onClick={onAsk}>
            {loading ? "Asking…" : "Ask AI"}
          </Button>
          <Button variant="secondary" onClick={onClear}>Clear</Button>
        </div>

        {/* Results placeholder injected by parent */}
        {children}

        {!children && (
          <div className="text-xs text-muted-foreground">
            Tip: Ask comparative questions like “Who has the most expensive procedure CA or NY?” or ratings like “Highest rated hospitals in TX”. Use DRG codes (e.g., 470) or names.
          </div>
        )}
      </div>

      {/* Sidebar */}
      <div className="md:col-span-1 grid gap-3">
        <div>
          <div className="text-xs font-semibold uppercase text-muted-foreground mb-2">Examples</div>
          <div className="grid gap-2">
            {examples.map((ex, i) => (
              <Button
                key={i}
                variant="outline"
                className="justify-start h-8 px-2 text-left text-xs"
                onClick={() => onChange(ex)}
              >
                {ex}
              </Button>
            ))}
          </div>
        </div>

        <div>
          <div className="text-xs font-semibold uppercase text-muted-foreground mb-2">Common DRGs</div>
          <div className="flex flex-wrap gap-2">
            {quickDRGs.map(({ code, name }) => (
              <Button
                key={`${code}-${name}`}
                variant="secondary"
                className="h-8 px-2 text-xs"
                onClick={() => onChange(`Who has the cheapest ${name.toLowerCase()} in NY? (DRG ${code})`)}
              >
                {code} • {name}
              </Button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}


