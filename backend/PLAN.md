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