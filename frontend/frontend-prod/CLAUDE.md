### Frontend Knowledge (Next.js 15 + React 19 + Tailwind)

## Purpose
This document captures the key contracts, types, and component boundaries required to implement the Next.js frontend with feature parity to `index.html` + `app.js`.

## Environment
- `NEXT_PUBLIC_API_BASE`: string – e.g., `http://localhost:8000/api/v1` (required)

## API Contracts (Backend)
- Health: `GET /health` → `{ status: string, service: string }`
- Template Stats: `GET /template-stats` → `{ template_statistics: Record<string, number> }`
- Ask (NL→SQL): `POST /ask?explain=false` body `{ question: string, use_template_matching: boolean }` → `AskResponse`
- Explain: `POST /explain` body `{ question, sql_query, results }` → `{ answer: string }`
- Provider Search: `POST /providers/search` body `{ state?, city?, drg_code?, min_rating?, max_cost?, limit? }` → `Provider[]`
- Cheapest: `GET /providers/cheapest/:drg?limit=n&state?=XX` → `Provider[]`
- Highest Rated: `GET /providers/highest-rated?limit=n&state?=XX&city?=name` → `Provider[]`
- Volume Leaders: `GET /providers/volume-leaders/:drg?limit=n` → `Provider[]`
- Cost Analysis: `GET /analysis/costs/:drg?state?=XX` → `CostAnalysis`

## Shared Types (TypeScript)
- `type Provider = {
  provider_id?: string;
  provider_name?: string;
  provider_city?: string;
  provider_state?: string;
  provider_zip_code?: string;
  drg_code?: string;
  drg_description?: string;
  average_covered_charges?: number | string;
  average_total_payments?: number | string;
  average_medicare_payments?: number | string;
  total_discharges?: number | string;
  overall_rating?: number | string;
  quality_rating?: number | string;
};`

- `type AskResponse = {
  success: boolean;
  answer: string;
  explanation_pending?: boolean;
  template_used?: number;
  confidence_score?: number; // 0..1
  sql_query?: string;
  execution_time_ms?: number;
  results?: Array<Record<string, any>>;
};`

- `type CostAnalysis = {
  drg_code: string;
  drg_description?: string;
  average_cost: number;
  median_cost: number;
  cost_variance: number;
  total_providers: number;
  cheapest_provider?: { provider_name: string; provider_city: string; provider_state: string; cost: number };
  most_expensive_provider?: { provider_name: string; provider_city: string; provider_state: string; cost: number };
};`

- `type TemplateStats = { template_statistics?: Record<string, number> }`

## Key Variables & Utilities (ported from current frontend)
- `formatCurrency(amount: number | string): string`
- `formatRating(rating: number | string): string`
- Error helper returns friendly message strings.

## Component Contracts
- `AIForm`: Props → `{ onAsk: (q: string) => Promise<void>; examples: string[] }`
- `AIResults`: Props → `{ data?: AskResponse }`
- `ProviderSearchForm`: Props → `{ onSearch: (criteria) => Promise<void> }`
- `ProviderTable`: Props → `{ rows: Provider[] }` (client-side sort/filter/page)
- `Charts.Bar`: Props → `{ labels: string[], data: number[], label?: string }`
- `Charts.Scatter`: Props → `{ points: { x: number, y: number, label?: string }[] }`

## Pages & Layout
- `app/layout.tsx` – HTML shell, theme provider, Tailwind globals.
- `app/page.tsx` – Dashboard with sections: AI Assistant, Providers, Cost Analysis, Status.
- All interactive sections are client components (`"use client"`).

## Styling
- Tailwind + a small set of CSS variables in `globals.css` for theme parity with current UI.

## Non-Goals
- No state management library initially; revisit if complexity grows.
- No server actions for initial version (all client fetches against REST API).


