### Healthcare Cost Navigator – ORM Models

## Purpose
Defines the relational schema for Postgres. All models inherit from `Base` in `core.database` and align with `etl/init.sql` bootstrap.

## Entities
- `Provider`
  - `provider_id` (PK), name, address, city, `provider_state`, ZIP, optional RUCA and `location` (GEOMETRY Point 4326).
  - Indexes: `idx_provider_zip`, `idx_provider_state`, GIST on `location`.

- `DRGProcedure`
  - `drg_code` (PK), `drg_description`, `embedding Vector(1536)` for semantic search.
  - Index: trigram GIN on `drg_description`; vector IVFFlat index created post‑load.

- `ProviderProcedure`
  - Surrogate `id`, `provider_id` FK, `drg_code` FK.
  - Measures: `total_discharges`, `average_covered_charges`, `average_total_payments`, `average_medicare_payments`.
  - Denormalized `provider_state` to avoid join on hot paths.
  - Indexes: (`provider_id`, `drg_code`), `average_covered_charges`, `drg_code`.

- `ProviderRating`
  - Surrogate `id`, `provider_id` FK.
  - Ratings: `overall_rating`, `quality_rating`, `safety_rating`, `patient_experience_rating`.
  - Indexes on `provider_id` and `overall_rating`.

- `CSVColumnMapping`
  - ETL dictionary: `csv_column_name` → `normalized_field_name`, `table_name`, `data_type`, `description`.

- `TemplateCatalog`
  - Stores NL→SQL templates: `canonical_sql`, `raw_sql`, `embedding`, `comment`, timestamps.
  - Indexes on `canonical_sql`, `created_at`; vector index created after seeding.

## Relationships
```
Provider 1––* ProviderProcedure *––1 DRGProcedure
Provider 1––* ProviderRating
```

## Notes
- Services cast numeric DB values to JSON‑safe `float`/`int`.
- Alembic migrations add performance optimizations and materialized views when applicable.
- The denormalized `provider_state` is essential for fast state filters and multi‑state comparisons.
