# Healthcare Cost Navigator – Utility Modules

## template_loader.py / Vector + Template Matching
* `TemplateService` orchestrates **normalisation ➜ embedding ➜ search ➜ parameter mapping ➜ execution**.
* `ParameterMapping` keeps provenance (`$n` → value/type).
* Uses `VectorSearchEngine` (see below) for similarity search & catalog CRUD.

## vector_search.py
* Wraps pgvector similarity using OpenAI embeddings.
* `TemplateMatch` dataclass provides both similarity and Levenshtein edit distance for confidence scoring.

## sql_normalizer.py
* Replaces literals with `$1,$2,…` placeholders using `sqlglot` for robust parsing.
* Calculates a *complexity score* (joins, subqueries, aggregates, where-clauses).
* Supplies basic read-only safety check.

## sql_safety_validator.py
* **Comprehensive** SELECT-only validator: forbidden keywords, function whitelist, table whitelist, complexity limits.
* Produces `SafetyReport` with issues & recommendations – ideal for automated feedback loops.

## Misc
* All utils are **stateless**, pure-function style (except OpenAI client dependency).
* Strictly separated concerns: normalisation vs safety vs search.

## Potential Enhancements
* Cache embeddings locally to reduce repeated OpenAI calls.
* Promote `SQLSafetyValidator` as the single truth; deprecate duplicate checks inside `SQLNormalizer`.
