## NL→SQL Plan (Templates + Parser + Ops)

### Goal
Make every Natural Language → SQL query work reliably, including multi‑state comparisons like “Who has the most expensive procedures CA or NY?”, while keeping changes minimal, scalable, and maintainable.

### Scope and ownership
- Backend only: `@utils/`, `@services/`, `@models/`, `@structured_query_parser.py`.
- Frontend/Netlify: no code changes required; ensure env points to backend API.

### What changed (implemented)
- Parser enum now includes `state_comparison` in `structured_query_parser.py` function schema.
- Two new state‑comparison templates added to `backend/etl/seed_templates.py`:
  1) Most expensive across two states (aggregate):
     ```sql
     SELECT pp.provider_state, AVG(pp.average_covered_charges) AS avg_cost
     FROM provider_procedures pp
     WHERE pp.provider_state IN ($1, $2)
     GROUP BY pp.provider_state
     ORDER BY avg_cost DESC
     LIMIT 2;
     ```
  2) Most expensive for a procedure across two states:
     ```sql
     SELECT pp.provider_state,
            AVG(pp.average_covered_charges) AS avg_cost,
            MIN(pp.average_covered_charges) AS min_cost,
            MAX(pp.average_covered_charges) AS max_cost
     FROM provider_procedures pp
     JOIN drg_procedures d ON d.drg_code = pp.drg_code
     WHERE d.drg_description ILIKE $1
       AND pp.provider_state IN ($2, $3)
     GROUP BY pp.provider_state
     ORDER BY avg_cost DESC
     LIMIT 2;
     ```

### Why this scales
- Template‑first approach handles the majority of queries with low latency; pgvector scales to thousands of templates (IVFFlat, lists tuning).
- The parser change is minimal; the services already implement multi‑state logic and reuse `pp.provider_state` for performance.
- RAG fallback remains for novel patterns; successful ad‑hoc queries can be promoted to templates.

### Conciseness and code hygiene
- No new tech or patterns; reused existing `TemplateService`, `VectorSearchEngine`, and safety checks.
- Parser update limited to function schema enum extension.
- Templates are parameterized and value‑agnostic; comments clarify intent for intent‑filtering.

### Suggested tests (high‑value)
- Unit: parser extracts `states=["CA","NY"]` for prompts with “CA or NY”/“CA vs NY”.
- Integration: `/ask` for
  - “Who has the most expensive procedures CA or NY?” → two rows, ordered by `avg_cost DESC`.
  - “Cheapest hip replacement CA or NY?” → two rows with cheapest provider per state when cheapest templates used.

### CLI commands (do not auto‑run)
- Reseed templates after changes:
  - cd backend
  - py etl/seed_templates.py --mode templates

### Netlify (frontend) note
- Ensure frontend uses the backend API URL via env (e.g., `VITE_API_BASE_URL` or similar) and that Netlify env is set accordingly.

### Rollout checklist
- Reseed template catalog.
- Quick sanity test via `/template-stats` and sample `/ask` queries.
- Monitor logs for intent filtering (cheap vs expensive) and adjust template comments if needed.


