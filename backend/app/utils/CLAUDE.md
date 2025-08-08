### Healthcare Cost Navigator – Utility Modules

## TemplateService (`app/utils/template_loader.py`)
- Responsibilities:
  - `normalize_and_search(session, sql_query, confidence_threshold, user_intent)`
    - Uses `SQLNormalizer.normalize_sql` to canonicalize and extract constants, then `VectorSearchEngine.find_best_template_match` to retrieve candidate templates.
  - `map_parameters(template_sql, user_constants)`
    - Maps `$n` placeholders with correct quoting. Special‑cases `ILIKE`/`LIKE` to expand wildcards; short numerics default to string (for DRG codes).
  - `validate_and_execute_template(session, template_match, user_constants, max_results)`
    - Builds executable SQL, validates safety, adds LIMIT, executes via SQLAlchemy `text()`.
  - Post-processing ensures `LIMIT` is numeric (quotes removed) to prevent driver errors.
  - `learn_from_successful_query(...)`
    - Normalizes SQL and conditionally inserts into `template_catalog` if not near‑duplicate.
  - `get_template_suggestions(session, user_query, limit)`
    - NL embedding search over `template_catalog.comment` for few‑shot examples.

## VectorSearchEngine (`app/utils/vector_search.py`)
- Uses OpenAI `text-embedding-3-small` for 1536‑dimensional embeddings.
- `search_similar_templates(session, query_sql, limit, similarity_threshold)` performs cosine similarity via pgvector (<=> operators) and returns `TemplateMatch`.
- `find_best_template_match(...)` adds Levenshtein edit‑distance ratio and optional intent filtering (e.g., exclude “expensive” when user asked for “cheapest”).
- `add_template_to_catalog(...)` stores canonical SQL, raw SQL, comment, and embedding.

## SQLNormalizer (`app/utils/sql_normalizer.py`)
- Canonicalizes SQL using `sqlglot` and replaces literals with `$1,$2,…` placeholders.
- Returns both normalized SQL and a list of extracted constants.
- Provides a crude `complexity_score` and a quick `validate_sql_safety` used as a fast pre‑check.

## SQLSafetyValidator (`app/utils/sql_safety_validator.py`)
- SELECT‑only enforcement; forbids DML/DDL keywords; function and table allow‑lists.
- Detects multiple statements, overly long queries, UNION/EXEC patterns, and missing LIMIT.
- Returns a `SafetyReport` with `issues`, `overall_score`, `complexity_score`, and `recommendations`.

## Data flow with templates
1. AI builds a candidate SQL (structured skeleton or RAG).
2. Normalizer produces `canonical_sql` + `constants`.
3. Vector engine finds best template; intent filter avoids mismatches (cheap vs expensive).
4. Parameter mapping injects constants by `$n` order, taking context into account.
5. Safety validation runs; then execution yields list[dict].

## Notes for state comparisons
- Prefer `pp.provider_state` for filters. If the template expects `p.provider_state`, ensure joins to `providers p` exist.
- For queries like “CA vs NY most expensive procedures”, build aggregate templates over `provider_procedures` grouped by `provider_state` and ordered by `AVG(pp.average_covered_charges)`.

## Improvements to consider
- Cache embeddings and template catalog lookups.
- Consolidate safety checks so `SQLSafetyValidator` is the primary gate; keep normalizer’s check as optional fast‑path.
