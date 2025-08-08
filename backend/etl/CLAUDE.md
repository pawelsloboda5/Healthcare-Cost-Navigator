### Healthcare Cost Navigator – ETL & Seeding

## Purpose
Bootstrap and enrich the database with structures and vectors needed for NL→SQL:
- Create tables, extensions, indexes (`init.sql`).
- Seed the SQL template catalog and create pgvector indices (`seed_templates.py`).
- Populate DRG embeddings for semantic procedure lookup.

## Files
- `init.sql`
  - Enables extensions: PostGIS, `pg_trgm`, `vector`.
  - Creates core tables: `providers`, `drg_procedures`, `provider_procedures`, `provider_ratings`, `csv_column_mappings`, `template_catalog`.
  - Performance: composite/covering indices, `provider_state` denormalization on `provider_procedures` plus trigger to sync on insert/update.
  - Optional materialized view `mv_state_drg_avg_cost` for pre‑aggregated state costs.

- `seed_templates.py`
  - Normalizes raw SQL → parameterizes literals as `$1..$n` when necessary (via `sqlglot`).
  - Embeds canonical SQL using OpenAI `text-embedding-3-small`.
  - Inserts into `template_catalog` and builds IVFFlat vector index.
  - Populates `drg_procedures.embedding` and creates vector index `idx_drg_embedding`.
  - Modes:
    - `--mode templates` – seed only catalog.
    - `--mode drg-embeddings` – populate DRG embeddings only.
    - `--mode both` – do both (default).
    - `--mode clean` – wipe catalog then re‑seed originals.

## Template coverage for NL→SQL
- Cheapest providers by description or DRG, nationwide or in a city/state.
- Most expensive providers and procedures (state level).
- Highest‑rated providers (with optional procedure and thresholds).
- Volume leaders by DRG or description.
- State comparisons (two‑state IN‑clause) for procedure costs and cheapest providers across states.
- Geographic lookups by ZIP prefix.
- Multi‑procedure provider listings and aggregate statistics.

## State comparison guidelines
- Favor `pp.provider_state` when only state is needed (no provider fields) for performance.
- Join `providers p` when provider fields (e.g., `provider_name`) are returned.
- For generic queries like “Who has the most expensive procedures CA or NY?” include templates that:
  1) compare average cost by state across all DRGs, and
  2) compare for a specific DRG/description when provided.

## Running
- Ensure `.env` includes `DATABASE_URL` and `OPENAI_API_KEY`.
- From `backend` directory:
  - Seed: `py etl/seed_templates.py --mode both`

## Maintenance
- When adding new patterns, extend `get_initial_templates()` with raw SQL and clear `comment` text describing intent, scope (state vs nationwide), and ordering (cheapest vs expensive).

