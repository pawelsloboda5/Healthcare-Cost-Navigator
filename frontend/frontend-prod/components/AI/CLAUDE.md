### AI Components (AIForm, AIResults)

## Purpose
Reusable UI for the NL→SQL assistant in the dashboard. Extracted from `app/page.tsx` to keep files small and enable reuse.

## Contracts
- `AIForm`
  - Props: `{ question, onChange, onAsk, onClear, loading?, examples?, quickDRGs?, children? }`
  - Behavior: client‑side detection of 2‑letter US states and 3‑digit DRG codes; renders removable chips. Press Enter (without Shift) triggers `onAsk`.
  - Sidebar renders example prompts and common DRGs provided by the caller.
  - Renders `children` directly beneath the composer (used for results panel).

- `AIResults`
  - Props: `{ data: AskResponse, onOpenInProviders?: ({ state?, drg_code? }) => void }`
  - Features: confidence badge coloring, copy SQL/CSV, generic results table, optional quick bar chart (client‑only via Chart.js) inferred from results, and an action to open the Providers tab with inferred params.

## Data Dependencies
- Types mirror `@/types/api` `AskResponse` shape. No direct network calls; parent supplies `data` and actions.

## Notes
- Chart rendering is intentionally simple: it infers a categorical key (state/city/name/description) and the first numeric key; plots at most 10 rows to avoid clutter.
- All copy actions use the Clipboard API; failures are ignored silently to avoid blocking the UX.
- Keep `AIResults` free of provider‑specific logic; the `onOpenInProviders` hook passes minimal inferred params back to the page, which owns navigation/state.

## Future Enhancements
- Optional streaming of explanation text.
- Dedicated column selector and CSV download file naming.
- Shared `DataTable` primitive for both AI and Providers tables.


