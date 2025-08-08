### Healthcare Cost Navigator – Services Layer

## Purpose
This package concentrates the backend business logic: NL→SQL orchestration, provider analytics, DRG semantic lookup, and structured query parsing. It composes utilities for normalization, vector/template search, and safety validation.

## NL→SQL pipeline (end-to-end)
- **Structured parsing**: `StructuredQueryParser.parse_query(user_query)` extracts `StructuredQuery` with fields like `query_type`, `procedure`, `drg_code`, `state`, `states`, `limit`.
- **Multi-state fast‑path**: simple regex detection of 2‑letter codes → `_execute_cheapest_multi_state` for direct, safe SQL when applicable.
- **Template path**: `_generate_structured_sql` → `TemplateService.normalize_and_search` → `map_parameters` → `validate_and_execute_template`.
- **Fallback path (RAG)**: `get_template_suggestions` → build few‑shot prompt → `_generate_sql_with_prompt` → safety validation → execution.
- **Learning**: `learn_from_successful_query` can normalize successful SQL and add to `template_catalog` (deduped by high‑threshold vector search).

## StructuredQuery schema and query types
- **Enum `QueryType`**: `CHEAPEST_PROVIDER`, `HIGHEST_RATED`, `COST_COMPARISON`, `VOLUME_ANALYSIS`, `STATE_COMPARISON`.
- **Dataclass `StructuredQuery`**: `procedure?`, `drg_code?`, `state?`, `city?`, `zip_code?`, `states?: List[str]`, `min_rating?`, `max_cost?`, `limit?`.
- Parser uses GPT function‑calling and normalizes state names to two‑letter codes when possible.

## EnhancedAIService (`app/services/ai_service.py`)
- **Key methods**
  - `process_natural_language_query(session, user_query, use_template_matching=True)`
    - Orchestrates parse → multi‑state fast‑path → template match → RAG fallback.
  - `_extract_state_codes(text)`: robust 2‑letter state detection, deduped.
  - `_execute_cheapest_multi_state(session, procedure_term, states, limit)`
    - Windowed per‑state cheapest selection; safe read‑only SQL with `FIRST_VALUE(...) OVER (PARTITION BY state ORDER BY cost)`.
  - `_try_structured_template_matching(session, user_query, params)`
    - Generates structured SQL for matching, extracts constants in `$n` order, executes template safely.
  - `_extract_template_constants(session, params, template_sql)`
    - Interprets `$n` in context (ILIKE vs equality, DRG code vs description, state, limit) to produce ordered constants.
  - `_generate_structured_sql(params)`
    - Emits deterministic SQL skeletons per `QueryType`. Uses denormalized `pp.provider_state` where possible to avoid unnecessary joins.
  - `_generate_with_structured_rag(...)` and `_generate_sql_with_prompt(...)`
    - Builds prompt with nearest templates and executes multiple guarded attempts.
  - `_execute_sql_safely(session, sql, max_results)`
    - Forces single statement with LIMIT, executes via `text(sql)`, returns rows as list[dict].

- **State comparison coverage**
  - `STATE_COMPARISON` in `_generate_structured_sql` groups by `pp.provider_state` and can compute min/avg/max per state.
  - Multi‑state helper supports queries mentioning multiple states inline (e.g., “NY vs CA” / “NY or CA”).
  - Prefer `pp.provider_state` for filters; join to `providers p` only when provider display fields are required.

## Recent changes
- Ratings path now supports multi-state comparisons and nationwide queries without procedures. Structured SQL adds `p.provider_state IN (...)` when `states` present.
- Multi-state cheapest helper uses CTE + ROW_NUMBER to avoid grouping errors.
- Template constants extraction now correctly maps `IN ($n,$n+1,...)` by inspecting only placeholders inside the parentheses and ensures `LIMIT` stays numeric.
- Parser preserves `highest_rated` intent for multi-state and uses text cues to override misclassification.

- **Example: “Who has the most expensive procedures CA or NY?”**
  - If no specific procedure is mentioned, we interpret “procedures” as “all procedures” and compare by aggregate per state.
  - Exemplary SQL pattern (avg cost comparison across two states):
    ```sql
    SELECT pp.provider_state,
           AVG(pp.average_covered_charges) AS avg_cost
    FROM provider_procedures pp
    WHERE pp.provider_state IN ('CA','NY')
    GROUP BY pp.provider_state
    ORDER BY avg_cost DESC
    LIMIT 2;
    ```
  - If a procedure is specified (“hip replacement”), add `JOIN drg_procedures d ON d.drg_code = pp.drg_code` and `d.drg_description ILIKE '%hip replacement%'`.

## ProviderService (`app/services/provider_service.py`)
- **Responsibilities**
  - Faceted provider search with cost/volume aggregates.
  - Cheapest providers for a DRG (optionally filtered by state).
  - Highest‑rated providers (optionally with procedure filter).
  - Volume leaders and per‑DRG cost distribution analysis.
- **Inputs**: `ProviderSearchCriteria(state?, city?, zip_code?, drg_code?, min_rating?, max_cost?, min_volume?)` and `limit`.
- **Outputs**: lists of dicts tailored for API models; numeric values cast to `float`/`int`.
- **Performance note**: For pure state filters prefer `pp.provider_state`; join `providers p` when provider details are needed.

## DRGLookupService (`app/services/drg_lookup.py`)
- Vector semantic search against `drg_procedures.embedding` (OpenAI `text-embedding-3-small`).
- Fallback trigram similarity search if vector pipeline fails.
- Utility function `drg_code_from_phrase(session, phrase)` exposes lookup to callers.

## StructuredQueryParser (`app/services/structured_query_parser.py`)
- GPT function‑calling returns a JSON argument payload coerced into `StructuredQuery`.
- Normalizes state names to two‑letter codes and defaults `limit` when omitted.

## Safety and correctness
- `SQLNormalizer` and `SQLSafetyValidator` enforce SELECT‑only, table/function allow‑lists, complexity limits, and injection pattern checks before execution.
- All DB IO uses async `AsyncSession` and parameter binding where queries are not static templates.

## Planning checklist for NL→SQL coverage
- **Cheapest / most expensive**: state, city, ZIP, multi‑state comparisons.
- **Procedure specificity**: by DRG code and description (supports ILIKE + embeddings).
- **Aggregations**: avg/min/max per state or provider; window functions for top‑k per partition.
- **Ratings**: integrate `provider_ratings` joins when requested.
- **Learning loop**: promote frequent successful ad‑hoc SQL to templates with comments clarifying intent.

## Next steps (suggested)
- Expand template catalog for “most expensive” multi‑state comparisons using `pp.provider_state` consistently (some existing templates use `p.provider_state`).
- Add a dedicated “overall state cost comparison” template (no procedure filter) to answer generic “CA vs NY” questions rapidly via the template path.
