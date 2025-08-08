### Healthcare Cost Navigator – Core

## Purpose
Centralizes infrastructure: configuration and async database setup.

## Files
- `config.py`
  - `Settings` reads from environment: `DATABASE_URL`, `OPENAI_API_KEY`, model names, query limits, safety thresholds, and CORS origins.
  - A single global `settings` is exported for import across the app.
  - Fails fast if `OPENAI_API_KEY` is missing to prevent runtime surprises.

- `database.py`
  - Creates async engine (`create_async_engine`) and session factory (`async_sessionmaker`).
  - Exposes `get_db()` for FastAPI DI and `init_db()` for bootstrapping tables.
  - Exports `Base` for models.

## Guarantees
- All DB IO is async; no global sessions.
- Secrets only via env; never hard‑code.
- Defaults enable local dev; production should supply explicit env.

## Important env variables
- `DATABASE_URL=postgresql+asyncpg://…/healthcare_cost_navigator`
- `OPENAI_API_KEY=sk-…`
- `OPENAI_MODEL`, `OPENAI_EMBEDDING_MODEL`, `LOG_LEVEL`

## Improvements to consider
- Validate `DATABASE_URL` includes `asyncpg` and is reachable on startup.
- Add pydantic‑based settings for stronger typing and env parsing.
