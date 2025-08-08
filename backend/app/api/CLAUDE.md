### Healthcare Cost Navigator – API Layer

## Purpose & Scope
Hosts the public HTTP interface. `routes.py` defines all endpoints and request/response schemas. `websocket.py` is a stub for future live updates.

## Endpoints (high‑level)
- GET `/health`: liveness.
- POST `/ask`: NL→SQL assistant. Body: `AskRequest { question, use_template_matching }`. Returns `AskResponse { success, sql_query, results, template_used, confidence_score, execution_time_ms }`. Optionally returns a short explanation when `explain=true`.
- POST `/providers/search`: advanced search via `ProviderSearchRequest` → `[ProviderResponse]`.
- GET `/providers/cheapest/{drg_code}`: cheapest providers for DRG (optionally `state`).
- GET `/providers/highest-rated`: top providers (optional `state`, `city`).
- GET `/providers/volume-leaders/{drg_code}`: highest volume.
- GET `/providers/{provider_id}`: provider details + aggregates.
- GET `/analysis/costs/{drg_code}`: cost distribution statistics.
- GET `/template-stats`: template catalog stats.
- GET `/providers` (legacy): backward‑compatible search.

## Contracts & Models
- `AskRequest`, `AskResponse`, `ExplainRequest`, `ExplainResponse` for AI endpoints.
- `ProviderSearchRequest`, `ProviderResponse`, `CostAnalysisResponse` for provider and analytics endpoints.
- All numeric DB fields are cast to primitives in services before schema construction.

## Dependency Injection & Sessions
- Every endpoint uses `Depends(get_db)` from `core.database` to acquire an `AsyncSession`.
- Services instantiated once per module: `EnhancedAIService`, `ProviderService`.

## NL→SQL coverage from API
- The `/ask` endpoint delegates all NL→SQL logic to `EnhancedAIService`:
  - Structured parsing → template match → RAG fallback → safe execution.
  - Handles multi‑state comparisons (e.g., “CA vs NY”), most/least expensive, highest‑rated, volume, and aggregated state‑level statistics.

## Error handling
- Input validation errors → 400/404 via `HTTPException`.
- Unexpected errors → 500 with logged details.

## Future notes
- Move Pydantic models into a `schemas` subpackage if they grow.
- Add WebSocket streaming for long‑running analysis results.
