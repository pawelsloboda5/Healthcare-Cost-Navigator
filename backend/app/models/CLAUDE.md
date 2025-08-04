# Healthcare Cost Navigator – ORM Models

All models inherit from `Base` in `core.database`.  They represent the **source-of-truth schema** for Postgres.

## Entity Overview
### Provider
* PK: `provider_id` (CMS ID, string)
* Geo & address fields plus RUCA meta.
* Spatial `location GEOPOINT` enables distance queries (`gist` index).

### DRGProcedure
* PK: `drg_code`
* `drg_description` plus **OpenAI 1536-dim embedding** for semantic search.

### ProviderProcedure (bridge)
* PK: surrogate `id`.
* FK → Provider, DRGProcedure.
* Denormalised `provider_state` column to avoid joins during geo filters → critical for query performance.

### ProviderRating
* 1-to-1 optional rating snapshot per provider.

### CSVColumnMapping
Tracks ETL metadata – which raw CSV column maps to which model field / table.

### TemplateCatalog
Vector-searchable SQL template store (`embedding vector`) driving RAG/template matching.

## Indexing & Performance Notes
* Multiple GIN / trigram indices for full-text search (DRG descriptions).
* `provider_location` GIST index for spatial queries.
* Composite indices on (`provider_id`, `drg_code`) for cost lookups.

## Data Relationships
```
Provider 1––* ProviderProcedure *––1 DRGProcedure
Provider 1––* ProviderRating
```
All FK constraints are **on delete cascade** (default SQLAlchemy), ensuring orphan cleanup.

## Serialisation Rules
Numeric fields (`Numeric`, `Integer`) are read as `Decimal/Decimal128`; service layer casts to `float/int` before JSON.

## Migration Strategy
Schema is managed via Alembic (see `alembic/versions`).  Ensure new columns have accompanying indices & ETL updates.
