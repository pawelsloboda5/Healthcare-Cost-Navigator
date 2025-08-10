### Next.js Frontend Plan (React 19, Next 15, Tailwind)

## Objectives
- Rebuild the current static UI (`index.html`, `app.js`) as a modern React 19 + Next.js 15 app using the App Router and Tailwind.
- Keep behavior and API contracts identical to current frontend so we can deploy on Vercel without backend changes.

## Architecture
- Next.js 15 App Router with React Server Components for layout; client components for interactive sections (AI Assistant, Provider Search, Dashboards).
- TailwindCSS for styling; Chart.js via npm (no CDN).
- Single environment-driven API base: `NEXT_PUBLIC_API_BASE` → defaults to `http://localhost:8000/api/v1` locally.
- Minimal client-side state; prefer component-local state and simple fetch wrappers in `lib/api.ts`.

## Directory Layout (proposed)
- `app/`
  - `layout.tsx` – global shell, theme toggle, base styles
  - `page.tsx` – main dashboard (AI Assistant, Providers, Cost Analysis, Status)
  - `(components)/` – colocated lightweight sections if desired
- `components/`
  - `AI/AIForm.tsx`, `AI/AIResults.tsx`
  - `Providers/ProviderSearchForm.tsx`, `Providers/ProviderTable.tsx`
  - `Charts/Bar.tsx`, `Charts/Scatter.tsx` (thin wrappers over Chart.js)
  - `UI/Card.tsx`, `UI/Button.tsx`, `UI/Table.tsx`
- `lib/`
  - `api.ts` – typed fetch helpers (ask, explain, searchProviders, cheapest, highestRated, volumeLeaders, analysis)
  - `format.ts` – `formatCurrency`, `formatRating`, error helper
- `types/`
  - `api.ts` – TypeScript interfaces mirroring backend responses (AskResponse, Provider, CostAnalysis, TemplateStats)
- `styles/`
  - `globals.css` – Tailwind base + custom overrides
- `public/` – static assets (logo, icons)

## Feature Mapping (parity with current UI)
- AI Assistant
  - Textarea + actions (Ask, Clear)
  - Results table with technical details (template id, confidence, SQL, time)
- Provider Search
  - Form (state, city, drg_code, min_rating, max_cost, limit)
  - Quick actions (Cheapest, Highest Rated, Volume Leaders)
  - Results table with sorting/filtering/pagination (client-side)
- Cost Analysis
  - DRG input + optional state
  - Summary chips and 2–3 charts (distribution bars, rating vs cost scatter)
- System Status
  - API health and template stats

## Networking
- All calls go through `lib/api.ts` using `process.env.NEXT_PUBLIC_API_BASE`.
- Error normalization returns `{ message, context }` strings suitable for toasts or inline errors.

## Styling & Theming
- Tailwind with CSS variables for light/dark themes (ported from current CSS).
- Keep component classNames simple; extract shared primitives into `components/UI/*`.

## Charts
- Use `chart.js` + `react-chartjs-2` wrappers for simplicity and SSR-safety via dynamic import on client components.

## Types (high-level)
- `AskResponse` matches backend: `success, answer, template_used?, confidence_score?, sql_query?, execution_time_ms?, results?: Array<Record<string, any>>`.
- `Provider` row keys used today: `provider_name, provider_city, provider_state, drg_code?, drg_description?, average_covered_charges?, average_total_payments?, average_medicare_payments?, total_discharges?, overall_rating?, quality_rating?`.
- `CostAnalysis`: `drg_code, drg_description?, average_cost, median_cost, cost_variance, total_providers, cheapest_provider?, most_expensive_provider?`.
- `TemplateStats`: object map of counters.

## Migration Notes
- Preserve UX and terminology; keep example questions.
- Port utility functions from `app.js` to `lib/format.ts`.
- Replace CDN Chart.js with npm dependency and dynamic client-only charts.

## Deployment
- Vercel project → set `NEXT_PUBLIC_API_BASE` to your backend URL.
- Ensure backend CORS allows Vercel domain.

## QA Checklist
- AI queries: cheapest, most expensive, multi-state comparisons, highest rated (single/multi-state), cost analysis.
- Edge cases: empty results, template errors, SQL shown, long provider names, rating formatting.


