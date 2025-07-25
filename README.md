# Healthcare Cost Navigator

**Healthcare Cost Navigator** is a FastAPI-based service that helps patients search for hospitals offering specific MS-DRG procedures, view estimated prices, and access quality ratings. It integrates **GPT-driven natural language queries** (via OpenAI) with a **Postgres + PostGIS + pgvector database** to provide accurate, real-time responses using a hybrid **template + free-form SQL generation** architecture.

---

## Key Features
- **Search by DRG & Location:** Query hospitals by MS-DRG code, ZIP code, and radius.
- **Cost & Quality Data:** Access average charges, total payments, and hospital star ratings.
- **Natural Language Queries:** `POST /ask` endpoint converts NL questions to SQL with **RAG**.
- **ETL Pipeline:** Load and normalize Medicare CSV data using `etl.py`.
- **PostGIS & GeoAlchemy2:** Efficient geographic radius queries.
- **pgvector Support:** Vector-based semantic search for SQL templates and RAG context.
- **Safe SQL Execution:** Read-only query pool, SQL normalization, and template matching.
- **Streaming AI Responses:** Real-time answers over WebSockets.

---

## Project Structure

healthcare-cost-navigator/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # FastAPI entrypoint
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── routes.py        # Providers & /ask endpoints
│   │   │   └── websocket.py     # Streaming WebSocket (optional)
│   │   ├── core/
│   │   │   ├── config.py        # Settings, env variables
│   │   │   ├── database.py      # Async DB engine & session
│   │   │   └── security.py      # Future authentication (optional)
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── hospital.py      # SQLAlchemy models
│   │   ├── services/
│   │   │   ├── ai_service.py    # OpenAI NL → SQL logic
│   │   │   └── provider_service.py
│   │   └── utils/
│   │       ├── sql_normalizer.py # Uses sqlglot/pglast
│   │       ├── vector_search.py  # pgvector search utils
│   │       └── template_loader.py
│   ├── etl/
│   │   ├── etl.py               # CSV → DB loading
│   │   └── init.sql
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yaml
│
├── frontend/
│   ├── index.html               # Minimal HTML page
│   ├── app.js                   # Fetch API routes
│   └── ws.js                    # WebSocket example (if needed)
│
├── data/
│   └── medicare-data-raw.csv
│
├── docs/
│   ├── AI_SQL_Generation.md
│   ├── Catalog_Growth_Strategy.md
│   ├── Embedding_and_RAG.md
│   ├── Error_handling_Self_Repair.md
│   ├── Hybrid_Query_Architecture.md
│   ├── Parameter_Extraction_Mapping.md
│   ├── SQL_Safety_Guide.md
│   └── Template_Catalog_Vector_Search.md
│
├── .env.example
├── README.md
└── ProjectImportVersions.txt

