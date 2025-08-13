# Healthcare Cost Navigator - NL→SQL Implementation Plan

## Overview
Transform the basic `/ask` endpoint into a sophisticated Natural Language to SQL system with RAG (Retrieval-Augmented Generation), template matching, and safety validation.

## Current Status ✅
- **Database**: Loaded with 3,015 providers, 533 DRG procedures, 145,742 provider procedures
- **Basic API**: `/providers` endpoint working with structured queries
- **Basic NL**: Simple `/ask` endpoint with direct GPT-4 SQL generation
- **Infrastructure**: PostgreSQL with PostGIS, pgvector extensions, Docker setup

## Implementation Phases

### Phase 1: Foundation & Template Catalog 🔧
**Goal**: Set up the core infrastructure for template-based SQL generation

#### 1.1 Database Schema Extensions
- [ ] Add `template_catalog` table model to SQLAlchemy
- [ ] Create migration for new table
- [ ] Seed with initial templates based on existing `/providers` queries

#### 1.2 Dependencies & Tools
- [ ] Add `sqlglot` for SQL parsing and normalization
- [ ] Add `python-Levenshtein` for edit distance calculations
- [ ] Add `sentence-transformers` as backup embedding option
- [ ] Update requirements.txt

#### 1.3 Core Services Structure
- [ ] `TemplateService` - SQL normalization, embedding, vector search
- [ ] `SQLSafetyValidator` - Comprehensive safety validation
- [ ] `EnhancedAIService` - RAG-enhanced SQL generation

### Phase 2: SQL Safety & Validation 🛡️
**Goal**: Implement robust safety measures per SQL_Safety_Guide.md

#### 2.1 SQL Validation Pipeline
- [ ] Syntax parsing with sqlglot
- [ ] Whitelist validation (SELECT only)
- [ ] Parameter extraction and normalization
- [ ] Multi-statement detection and blocking

#### 2.2 Safety Features
- [ ] Read-only database user enforcement
- [ ] SQL injection prevention via parameterization
- [ ] Query complexity limits (JOIN depth, result size)
- [ ] Audit logging for all queries

### Phase 3: Template System & Vector Search 🔍
**Goal**: Implement template matching per Template_Catalog_Vector_Search.md

#### 3.1 SQL Normalization
- [ ] Constant replacement with `$1`, `$2` placeholders
- [ ] Canonical query formatting (lowercase, whitespace)
- [ ] AST-based predicate ordering for consistency

#### 3.2 Vector Search Implementation
- [ ] OpenAI embedding generation for templates
- [ ] pgvector cosine similarity search
- [ ] Edit distance filtering with configurable thresholds
- [ ] Template ranking and selection logic

### Phase 4: RAG Enhancement 🧠
**Goal**: Implement context-aware SQL generation per Embedding_and_RAG.md

#### 4.1 Context Retrieval
- [ ] Semantic search for relevant templates
- [ ] Schema-aware prompt construction
- [ ] Example-based few-shot learning

#### 4.2 Enhanced AI Pipeline
- [ ] Multi-attempt generation with self-repair
- [ ] Template-guided prompt engineering
- [ ] Confidence scoring for generated queries

### Phase 5: Error Handling & Self-Repair 🔄
**Goal**: Implement robust error recovery per Error_handling_Self_Repair.md

#### 5.1 Error Detection
- [ ] Syntax error catching and reporting
- [ ] Runtime error handling (unknown columns, etc.)
- [ ] Semantic validation (result structure checking)

#### 5.2 Self-Repair Mechanisms
- [ ] GPT-4 error feedback loop
- [ ] Template fallback strategies
- [ ] Graceful degradation with user-friendly messages

### Phase 6: Advanced Features 🚀
**Goal**: Polish and optimize the system

#### 6.1 Performance Optimization
- [ ] Query result caching
- [ ] Template embedding caching
- [ ] Async pipeline optimization

#### 6.2 Monitoring & Analytics
- [ ] Query success/failure metrics
- [ ] Template usage analytics
- [ ] Performance monitoring

### Phase 7: Developer Tab – AI Query Logs (Minimal)
Goal: Persist NL→SQL requests to inspect successes/failures locally and power a public Developer tab in the frontend.

Scope (minimal):
- New table `ai_query_logs` with: `id SERIAL PK`, `created_at TIMESTAMP DEFAULT NOW()`, `user_question TEXT`, `success BOOLEAN`, `answer TEXT`, `sql_query TEXT`, `results JSONB`, `template_used INT`, `confidence_score NUMERIC(3,2)`, `execution_time_ms INT`, `error_message TEXT`, `result_count INT`, `has_results BOOLEAN`.
- Insert a row on every `/ask` call (both success and error).
- Read endpoint `GET /dev/ai-logs?limit=100&success?=&has_results?=` ordered by `created_at DESC`.
- Local script to (re)create the table using SQLAlchemy models and `init_db()`.

Steps:
1) Add SQLAlchemy model `AIQueryLog` in `app/models/models.py` and include indices on `(created_at)` and `(success, has_results)`.
2) In `app/api/routes.py` `/ask`, after computing the result (or on exception), insert a log row via the session.
3) Add router handler `GET /dev/ai-logs` returning latest entries with simple filters + limit.
4) Create `backend/scripts/create_ai_query_logs_table.py` to import `init_db()` and ensure the new table exists (idempotent).
5) Frontend: add a new “Developer” tab that fetches `/dev/ai-logs` and renders a compact table with expand-on-row JSON view; copy buttons for SQL/CSV.


## Technical Architecture

### Database Schema
```sql
-- New table for template catalog
template_catalog(
  template_id SERIAL PRIMARY KEY,
  canonical_sql TEXT NOT NULL,
  raw_sql TEXT NOT NULL,
  embedding VECTOR(1536),
  comment TEXT,
  created_at TIMESTAMP DEFAULT NOW()
)
```

### Service Layer Architecture
```
EnhancedAIService
├── TemplateService
│   ├── normalize_sql()
│   ├── get_embedding()
│   └── find_similar_templates()
├── SQLSafetyValidator
│   ├── validate_sql()
│   ├── extract_parameters()
│   └── check_safety_rules()
└── ErrorHandler
    ├── detect_error_type()
    ├── attempt_self_repair()
    └── generate_fallback_response()
```

### API Flow
```
1. User NL Query → /ask endpoint
2. Healthcare relevance check
3. Template retrieval (RAG)
4. Enhanced prompt construction
5. GPT-4 SQL generation
6. Safety validation
7. Template similarity check
8. Safe execution
9. Natural language response
```

## Initial Template Catalog

### Template Categories

#### 1. Cost Comparison Queries
```sql
-- Cheapest providers for procedure
SELECT p.provider_name, pp.average_covered_charges 
FROM providers p 
JOIN provider_procedures pp ON p.provider_id = pp.provider_id 
JOIN drg_procedures d ON pp.drg_code = d.drg_code 
WHERE d.drg_code = $1 AND p.provider_state = $2 
ORDER BY pp.average_covered_charges ASC 
LIMIT $3;
```

#### 2. Quality & Rating Queries
```sql
-- Highest rated providers
SELECT p.provider_name, pr.overall_rating 
FROM providers p 
JOIN provider_ratings pr ON p.provider_id = pr.provider_id 
WHERE p.provider_city ILIKE $1 
ORDER BY pr.overall_rating DESC 
LIMIT $2;
```

#### 3. Geographic/Location Queries
```sql
-- Providers near location
SELECT p.provider_name, p.provider_city 
FROM providers p 
WHERE p.provider_zip_code LIKE $1 
LIMIT $2;
```

#### 4. Procedure Volume Queries
```sql
-- High volume providers
SELECT p.provider_name, pp.total_discharges 
FROM providers p 
JOIN provider_procedures pp ON p.provider_id = pp.provider_id 
WHERE pp.drg_code = $1 
ORDER BY pp.total_discharges DESC 
LIMIT $2;
```

## Success Metrics

### Functional Goals
- [ ] 95%+ SQL safety validation accuracy
- [ ] 90%+ successful query execution rate
- [ ] 80%+ user satisfaction with NL understanding
- [ ] <2 second average response time

### Technical Goals
- [ ] Zero SQL injection vulnerabilities
- [ ] Comprehensive error handling and recovery
- [ ] Scalable template catalog (1000+ templates)
- [ ] Efficient vector search (<100ms)

## Risk Mitigation

### Security Risks
- **SQL Injection**: Parameterized queries, input validation
- **Data Exposure**: Read-only DB user, result filtering
- **API Abuse**: Rate limiting, authentication

### Performance Risks
- **Slow Vector Search**: Index optimization, caching
- **OpenAI API Limits**: Retry logic, fallback strategies
- **Memory Usage**: Efficient embedding storage

### Operational Risks
- **Query Failures**: Comprehensive error handling
- **Template Drift**: Regular template validation
- **Schema Changes**: Version-aware template management

---

## Next Steps
1. ✅ **Start Phase 1.1**: Create template catalog table and initial templates
2. **Add missing dependencies** to requirements.txt
3. **Implement TemplateService** with basic normalization
4. **Test with simple NL queries** on existing data
5. **Iterate and expand** template catalog based on usage patterns

---

## Feature: Multi-State Cost Comparison Queries ("Cheapest procedure in NY vs CA")

### Objective
Enable users to compare procedure costs across multiple states in a single natural-language question.

### Deliverables
1. **StructuredQueryParser**
   • Add optional `states: List[str]` field (plural) and new `query_type` value `STATE_COMPARISON`.
   • Extend function-calling schema and normalisation logic to extract multiple states from queries like "NY or CA" / "New York vs California".

2. **Templates & Catalog**
   • Create template:  
```sql
SELECT pp.provider_state,
       MIN(pp.average_covered_charges)  AS cheapest_cost,
       FIRST_VALUE(p.provider_name) OVER w AS cheapest_provider,
       FIRST_VALUE(d.drg_description) OVER w AS procedure
FROM   provider_procedures pp
JOIN   providers p ON p.provider_id = pp.provider_id
JOIN   drg_procedures d ON d.drg_code = pp.drg_code
WHERE  d.drg_description ILIKE $1            -- procedure keyword
  AND  pp.provider_state IN ($2,$3)          -- dynamic state list (2+)
WINDOW w AS (PARTITION BY pp.provider_state ORDER BY pp.average_covered_charges)
GROUP  BY pp.provider_state
ORDER  BY cheapest_cost
LIMIT  $4;
```
   • Comment: "Cheapest provider for procedure across multiple states".
   • Embed + add to `template_catalog` via migration/seed.

3. **EnhancedAIService**
   • Map `STATE_COMPARISON` to new `_generate_structured_sql()` branch.
   • When multiple states provided, request template matching with user_intent containing `state_comparison`.
   • Fallback RAG prompt must include example comparing two states.

4. **ProviderService** *(optional path)*
   • Add helper `get_cheapest_by_state(procedure_drg, states, limit)` returning list of dicts.
   • Used by templates as execution fallback.

5. **Explanation Layer**
   • `explain_query_results()` to spot state aggregates and craft comparative language ("In NY the cheapest is …, whereas in CA …").

6. **Testing**
   • Unit tests for parser extracting `['NY','CA']` from sample question.
   • Integration test hitting `/ask` with the user question; assert both states present in answer.

7. **Documentation**
   • Update `docs/AI_SQL_Generation.md` with new query type examples.
   • Add entry to API README showcasing the feature.
 
### Affected Files
| File | Change |
| --- | --- |
| `backend/app/services/structured_query_parser.py` | Add `states: List[str]`, new `QueryType.STATE_COMPARISON`, parsing logic |
| `backend/app/services/ai_service.py` | Handle `STATE_COMPARISON` in `_generate_structured_sql`, intent extraction, RAG prompt |
| `backend/app/services/provider_service.py` | (Optional) new helper `get_cheapest_by_state` |
| `backend/app/models/models.py` | No schema changes, but migration seed touches `template_catalog` |
| `alembic/versions/*_add_state_comparison_template.py` | Migration script to insert new template & embedding |
| `backend/app/utils/template_loader.py` | Ensure parameter mapping supports dynamic IN-clause counts |
| `*tests/test_state_comparison.py` | New unit & integration tests |
| `docs/AI_SQL_Generation.md` | Add examples & explanation |
| `README.md` | Update API examples section |

> NOTE: file names prefixed with `*` will be created new during implementation.

### Timeline & Ownership
| Task | Owner | Est. Effort |
| --- | --- | --- |
| Parser update & tests | AI team | 4h |
| Template creation & migration | DB team | 2h |
| AI service logic | AI team | 3h |
| ProviderService helper | Data team | 2h |
| Docs & examples | DevRel | 1h |

### Risks & Mitigations
• Mis-parsing "or"/"vs" syntax → Extensive prompt examples and unit tests.  
• Dynamic IN-clause length → Build param list programmatically; cap at 5 states for safety.  
• Template match confidence drop → Use intent filter `state_comparison` to avoid single-state templates.

### Success Criteria
✓ `/ask` query "Who has the cheapest heart surgeries NY or CA?" returns two rows (NY, CA) with provider names & costs **under 2s** execution time and passes safety validator.
 