# Healthcare Cost Navigator – Core

## Purpose
This package centralises application-wide infrastructure.

### config.py
* `Settings` class loads all runtime configuration solely from **environment variables** with sane defaults.
  – `DATABASE_URL`, `OPENAI_API_KEY`, model names, CORS list, query limits, safety thresholds.
* Instantiated once as `settings` and imported elsewhere – **do not** create additional copies.

### database.py
* Creates an async SQLAlchemy engine (`create_async_engine`) and `async_sessionmaker`.
* Public helpers:
  * `get_db()` – FastAPI dependency generator yielding an `AsyncSession`.
  * `init_db()` – Alembic-friendly helper that issues `Base.metadata.create_all`.
* Declarative base is exposed as `Base` so models can import it without circularity.

## Conventions & Guarantees
1. All DB access is asynchronous.
2. No global sessions – callers must acquire via DI or explicit context.
3. Sensitive credentials are injected via env; **never** hard-code in code or markdown.

## Potential Improvements
* Add runtime validation to ensure `DATABASE_URL` includes `asyncpg` driver.
* Consider splitting `Settings` into smaller pydantic-based config for stronger type-safety and easier overrides during testing.
