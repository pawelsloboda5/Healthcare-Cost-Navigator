# Healthcare Cost Navigator – Services Layer

## Overview
Services encapsulate **business logic** and orchestrate utilities/data-access.

### EnhancedAIService (`ai_service.py`)
* Pipeline: Natural-language → `StructuredQueryParser` → (Template match | RAG) → SQL.
* Enforces safety via `SQLNormalizer.validate_sql_safety`.
* Learns successful queries → stores in `template_catalog` for future matches.
* Maintains rich **healthcare schema prompt** with denormalisation tips (use `provider_state`).

### ProviderService (`provider_service.py`)
* Rich, parameterised SQL for provider search, ratings, cost analytics.
* Accepts `ProviderSearchCriteria` dataclass.
* Performs dynamic SQL assembly (strings + bound params) – aims for read-only queries.
* Supplies utility methods: cheapest providers, highest rated, volume leaders, procedure cost analysis.
* Validation helpers for DRG code/state code formats.

### DRGLookupService (`drg_lookup.py`)
* Semantic search of DRG descriptions.
* Uses OpenAI embeddings (`text-embedding-3-small`) against pgvector column.
* Fallback trigram similarity if vector search fails.

### StructuredQueryParser (`structured_query_parser.py`)
* Uses GPT function-calling to translate NL into `StructuredQuery` dataclass.
* Normalises state names and sets sensible defaults.

## Cross-cutting Concerns
* All services expect an **async SQLAlchemy session** (no sync queries).
* OpenAI client is instantiated once per service to avoid connection overhead.
* Logging is pervasive (`logger = logging.getLogger(__name__)`) enabling granular debugging.

## Extensibility Notes
* New business operations should live here, not in the API layer.
* Consider abstracting SQL construction into reusable query-builder utilities to reduce string concatenation risk.
