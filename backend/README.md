# 📦 Backend — Healthcare Cost Navigator

> *Python 3.11 · FastAPI · PostgreSQL (+ PostGIS & pgvector) · OpenAI GPT‑4o*
>
> The engine that turns free‑text healthcare cost questions into secure, explainable SQL.

---

## 1  Repository map (backend subset)

```
backend/
├─ app/                      # FastAPI application
│  ├─ core/                  # settings, DB engine helpers
│  ├─ models/                # SQLAlchemy ORM tables
│  ├─ services/              # 🧠 AI & helper layers
│  │  ├─ ai_service.py         # NL → (template‑safe) SQL → answer
│  │  ├─ structured_query_parser.py
│  │  ├─ drg_lookup.py
│  │  └─ …
│  ├─ utils/                 # SQL normaliser, pgvector search, template loader
│  ├─ routes.py              # REST routes
│  └─ main.py                # Uvicorn entry‑point
├─ alembic/                  # migrations
├─ etl/
│  ├─ init.sql               # create tables, enable extensions, prime indexes
│  └─ seed_templates.py      # seed SQL templates & DRG embeddings
├─ tests/                    # pytest suite
├─ Dockerfile                # API container
└─ requirements.txt          # pinned deps (pip-tools export)
```

---

## 2  Local development (venv)

```bash
# clone root repo first, then …
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# secrets
cp ../.env.example ../.env    # add OPENAI_API_KEY
export $(cat ../.env | xargs) # quick shell‑export

# Postgres in Docker (from root compose)
docker compose up -d postgres
alembic upgrade head          # create tables

# Seed SQL templates + DRG embeddings
python etl/seed_templates.py --mode both

# launch API w/ hot‑reload
uvicorn app.main:app --reload --port 8000
# → http://localhost:8000/docs
```

### Handy scripts / aliases

| Command                                    | Purpose                      |
| ------------------------------------------ | ---------------------------- |
| `alembic revision --autogenerate -m "msg"` | create migration             |
| `pytest -q`                                | run unit + integration tests |
| `ruff check .` / `black .`                 | lint / format                |

---

## 3  Docker‑compose (prod‑like)

```bash
docker compose up --build      # at repo root
```

| Service      | Stack                                   | Notes                        |
| ------------ | --------------------------------------- | ---------------------------- |
| **api**      | FastAPI in Gunicorn (4 Uvicorn workers) | auto‑reload disabled in prod |
| **postgres** | PostGIS + pgvector                      | tuned via env vars below     |

### Perf‑tune quick‑reference (32 GB host)

```yaml
POSTGRES_SHARED_BUFFERS:   1GB   # 25 % RAM ≈ good sweet‑spot
POSTGRES_WORK_MEM:         64MB  # sorts & hashes
POSTGRES_EFFECTIVE_CACHE_SIZE: 8GB
MAX_PARALLEL_WORKERS_PER_GATHER: 4
```

---

## 4  Environment variables

# ── App settings ──────────────────────────────
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=true

# ── Database (async URL for SQLAlchemy) ───────
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
POSTGRES_HOST=           # service name in docker-compose
POSTGRES_PORT=5432
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@${POSTGRES_HOST}:${POSTGRES_PORT}/${POSTGRES_DB}

# ── OpenAI API ────────────────────────────────
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ── Misc / telemetry ──────────────────────────

AZURE_MAPS_KEY=XXXXXXXXXXXXXXXXXXX


---

## 5  Performance cheat‑sheet

| Layer               | Optimisation                            | Typical latency      |
| ------------------- | --------------------------------------- | -------------------- |
| **Template search** | pgvector IVFFlat (lists=100)            | ≈ 3 ms               |
| **DRG lookup**      | pg\_trgm + embeddings fallback          | ≈ 1 ms               |
| **Query exec**      | tuned `work_mem`, parallel workers      | 20‑200 ms            |
| **OpenAI calls**    | single completions & embedding requests | \~1.2 s *(dominant)* |

---

## 6  API surface

| Endpoint                           | Verb   | Body / Params                                      | Description                |
| ---------------------------------- | ------ | -------------------------------------------------- | -------------------------- |
| `/api/v1/ask`                      | `POST` | `{ "question": "cheapest hip replacement in NY" }` | streams answer + SQL trace |
| `/api/v1/providers/cheapest/{drg}` | `GET`  | `?state=&limit=`                                   | DB‑only shortcut           |
| `/api/v1/health`                   | `GET`  | —                                                  | liveness probe             |

Swagger UI auto‑generated at **`/docs`**.

---

## 7  Extending the engine

1. **New data domain** → add columns in `models/`, create Alembic migration, re‑seed.
2. **Extra SQL templates** → append to `etl/seed_templates.py`, run `--mode templates`.
3. **New embedding sets** (e.g. CPT codes) → copy pattern of `populate_drg_embeddings()`.
4. **Custom NL parser prompts** → update `services/structured_query_parser.py` schema & few‑shot examples.

---

## 8  Testing & CI

```bash
pytest -q                 # offline tests (temp Postgres schema)
pytest -m integration      # hits OpenAI, needs key
```

### Suggested GitHub Actions pipeline

1. Spin up docker‑compose (Postgres only).
2. `ruff` → `black --check` → `pytest`.
3. Build & push `ghcr.io/…/backend-api` on `main`.

---

## 9  Troubleshooting

| Issue                                     | Solution                                                                |
| ----------------------------------------- | ----------------------------------------------------------------------- |
| **`OperationalError: could not connect`** | `docker compose up -d postgres` then retry                              |
| GPT rate‑limit while seeding              | run templates first, then embeddings with `--sleep 2`                   |
| 0 rows for broad queries                  | ensure fallback template without `state` filter OR raise `VECTOR_TOP_K` |

---

### 🏁  That’s it — clone, seed, query!

Send PRs or questions — we 💚 community contributions.
