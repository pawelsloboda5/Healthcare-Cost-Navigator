# 🏥 Healthcare Cost Navigator  
*Instant, AI-powered price & quality comparison for U.S. hospitals*

---

## What is it?
**Healthcare Cost Navigator** turns the massive, hard-to-read public Medicare pricing dataset into an easy-to-use conversational API.  
Ask _“Who has the cheapest hip-replacement near Los Angeles?”_ or _“Show the 5 most expensive procedures in Texas”_ and get a streaming answer in seconds, backed by real SQL on a fully indexed PostgreSQL + PostGIS + pgvector warehouse.

> **Tech baseline**  
> * Python 3.11.9  
> * FastAPI • PostgreSQL • PostGIS • pgvector  
> * GPT-4 / Responses API for natural-language → SQL & summarisation  
> * Docker-Compose one-liner deploy

---

## Why you’ll love it

| 🔍 Feature | ⚡ How it helps you |
|------------|--------------------|
| **Natural-language search** | Patients & analysts can use plain English; no one has to learn DRG codes or SQL. |
| **True cost transparency** | Pulls *average covered charge, Medicare payment, discharges* for every DRG at ~3 k hospitals. |
| **Quality + cost in one place** | Merges CMS star-ratings so you can weigh price *and* quality. |
| **Geospatial radius queries** | “Within 25 mi of 94107” powered by PostGIS & spatial indexes. |
| **Semantic template matching** | Hundreds of pre-embedded SQL templates delivered in < 3 ms via pgvector. |
| **Realtime streaming answers** | SSE / WebSocket streams tokens as soon as GPT-4 generates them—no spinning wheels. |
| **Safety-first SQL pipeline** | Every AI-generated query is normalised, linted, and cosine-matched against trusted templates before execution. |
| **One-command deploy** | `docker compose up --build` gives you a ready-to-use API with demo data & docs. |

---

## High-level architecture

┌───────────────────────────────────────  Client / Browser  ────────────────────────────────────────┐
│  index.html + app.js                                                                             │
│  ├─ Search box & results grid                                                                    │
│                                                                            
└──────────────▲────────────────────────────────────────────────────▲───────────────────────────────┘
               │ SSE (EventSource)  –or–  WebSocket  ◀── continuous token push                      │
               │ REST (JSON)  ◀── CRUD endpoints                                                    │
┌──────────────┴────────────────────────────────────────────────────┴───────────────────────────────┐
│                                     API Gateway / Edge (Caddy)                                    │
│  • TLS termination                                                                                 │
│  • Path routing →  /api → FastAPI&nbsp;&nbsp;•&nbsp;/docs → ReDoc&nbsp;&nbsp;•&nbsp;/metrics → Prom│
└──────────────▲────────────────────────────────────────────────────▲───────────────────────────────┘
               │ internal HTTP/2                                                                       
┌──────────────┴────────────────────────────────────────────────────┴───────────────────────────────┐
│                            FastAPI 0.112  (Uvicorn workers, async)                                 │
│                                                                                                   │
│  ┌────────  AI Service  ────────┐   ┌────────  Template Loader  ────────┐                         │
│  │ • GPT-4o “NL → Structured”  │   │ • SQLGlot canonicaliser          │                         │
│  │ • DRG & template embeddings │   │ • pgvector cosine reuse          │                         │
│  │ • Streams OpenAI chunks → WS│   │ • Read-only SQL safety gate      │                         │
│  └─────────────────────────────┘   └───────────────────────────────────┘                         │
│  • Provider Service / DRG Lookup (geo + pg_trgm + pgvector)                                       │
│  • Metrics → Prometheus  `/metrics`                                                                │
│  • Background tasks (Celery async – nightly re-embedding, VACUUM, etc.)                           │
└──────────────▲────────────────────────────────────────────────────▲───────────────────────────────┘
               │ asyncpg pool                               │ SQLAlchemy (async)                    
┌──────────────┴────────────────────────────────────────────────────┴───────────────────────────────┐
│                        PostgreSQL 15   +   PostGIS 3   +   pgvector 0.6                           │
│                                                                                                   │
│  • providers  (≈ 13 k)          – GiST spatial idx on (lon, lat)                                  │
│  • drg_procedures (533)         – 768-D `text-embedding-3-small`; IVFFlat idx (lists = 100)       │
│  • provider_procedures (2.7 M)  – btree on (drg_code, provider_id)                                │
│  • template_catalog             – canonical_sql + 768-D vector + IVFFlat idx (lists = 100)        │
│  • Logical replica slot         → Prometheus `pg_exporter`                                        │
└────────────────────────────────────────────────────────────────────────────────────────────────────┘



### Data-flow (“happy path”)

User query ─► SPA (WebSocket) ─► /api/v1/ask

      AI Service
        ├─► GPT-4o  ⇢  Structured JSON  (query_type, state, procedure, …)
        ├─► Template search (pgvector cosine)
        │     └─► Extract constants → Render SQL
        ├─► Async **read-only** query  (asyncpg)
        │        ↳ ≥ 98 % of latency < OpenAI time
        └─► Row chunks streamed back (tokens)  ≈ 1-2 s TTFB

---

### Performance numbers

| Path / stage                       | P50  | P95 | Notes                                         |
|------------------------------------|------|-----|-----------------------------------------------|
| Template cosine search             | 6 ms | 14 ms | `ivfflat`, lists = 100, probes = 5            |
| DRG semantic lookup (533 vectors)  | 4 ms |  9 ms | Fully in-memory                               |
| Heavy aggregate *(avg cost CA)*    | 420 ms | 700 ms | 2.7 M rows, parallel seq-scan + hash agg      |
| GPT-4o structured parse            | 1.8 s | 2.4 s | Main driver of tail-latency                   |


*Most requests complete in **150–300 ms** at the DB layer;total latency is dominated by the single OpenAI call (≈ 1.5 s).*

---

## Live demo (cURL)

```bash
# Cheapest hip-replacement (DRG 470) within 50 mi of Denver (80202)
curl -X POST http://localhost:8000/api/v1/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "Cheapest DRG 470 within 50 miles of 80202"}'

Example response (abridged)

{
  "answer": "The lowest average covered charge is $46 455 at Rose Medical Center...",
  "sql_query": "SELECT ... WHERE pp.drg_code = 470 AND ST_DWithin(...) ORDER BY ...",
  "execution_time_ms": 714,
  "template_used": 31,
  "confidence_score": 0.96
}

Quick-start (Docker)

# 1 – clone & configure
git clone https://github.com/your-org/healthcare-cost-navigator.git
cd healthcare-cost-navigator
cp .env.example .env        # add your OPENAI_API_KEY here

# 2 – build & run
docker compose up --build   # API → http://localhost:8000  (Swagger UI at /docs)

The compose file spins up:

Postgres + PostGIS + pgvector (with tuned shared_buffers / work_mem)

FastAPI running on Python 3.11.9

Automatic DB bootstrap and demo Medicare dataset load

Roadmap
❤️ Patient-facing web UI (React) with interactive charts

📈 Incremental ETL updates as CMS releases new cost files

🏥 Private-payer claims ingestion for richer comparisons

⚡ Caching layer for sub-second repeat queries