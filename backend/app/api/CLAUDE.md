# Healthcare Cost Navigator – API Layer

## Purpose & Scope
This folder exposes the public HTTP interface for the backend.  All FastAPI routes are declared in `routes.py`; `websocket.py` is currently a stub for future real-time updates; `__init__.py` simply wires the router for application startup.

## Key Concepts
1. **Router instance** – a single `APIRouter` is exported and mounted by `main.py`.
2. **Pydantic Schemas** – request/response validation is colocated with the endpoints.
   • `ProviderSearchRequest`, `ProviderResponse`
   • `AskRequest`, `AskResponse`
   • `CostAnalysisResponse`
3. **Service Composition** – endpoints are *thin* wrappers; they delegate to domain services:
   • `EnhancedAIService` → natural-language → SQL/RAG pipeline.
   • `ProviderService` → provider search / analytics.
4. **Dependency Injection** – all DB access uses `Depends(get_db)` which yields a SQLAlchemy `AsyncSession`.

## REST Contract (high-level)
| Method & Path | Function | Major Params | Output |
| --- | --- | --- | --- |
| GET /health | health_check | – | status JSON |
| POST /ask | ask_ai_assistant | question, use_template_matching | NL answer + sql + results |
| POST /providers/search | search_providers_advanced | geo/rating/cost filters | `[ProviderResponse]` |
| GET /providers/cheapest/{drg_code} | get_cheapest_providers | drg_code, state | cheapest providers |
| GET /providers/highest-rated | get_highest_rated_providers | state/city | top providers |
| GET /providers/volume-leaders/{drg_code} | get_volume_leaders | drg_code | high-volume providers |
| GET /providers/{provider_id} | get_provider_details | provider_id | provider + aggregates |
| GET /analysis/costs/{drg_code} | analyze_procedure_costs | drg_code, state | cost stats |
| GET /template-stats | get_template_statistics | – | catalog meta |
| GET /providers (legacy) | search_providers_legacy | drg, zip | legacy format |

## Serialization & Validation
All responses are plain JSON produced from Pydantic models.  Numeric DB fields are cast to `float`/`int` **before** model construction in the services layer ensuring predictable JSON numbers.

## Error Handling Pattern
• Business / validation errors raise `HTTPException` (4xx).  
• Unexpected exceptions are logged and returned as 500.

## Notes for Future Work
• `websocket.py` can be filled with subscription APIs (e.g., long-running analyses).  
• Consider extracting Pydantic models into a shared `schemas` module once they grow.
