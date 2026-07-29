# OurHike backend

Companion to [../TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md). This is the FastAPI backend behind auth, community condition reports/moderation, closures, and warning escalation - the "someone has to be able to mark a closure and a moderator has to be able to escalate a warning" half of v1 MVP (see that doc's Backend section for why this moved into MVP on 2026-07-28).

## Setup

```
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # Windows; .venv/bin/pip on macOS/Linux
```

## Quick start

```
.venv/Scripts/python -m uvicorn app.main:app --reload   # run the dev server
.venv/Scripts/python -m pytest                            # run everything (prints a coverage summary too)
.venv/Scripts/python -m pytest tests/test_x.py             # one file
.venv/Scripts/python -m pytest -k test_name                # one test
.venv/Scripts/python -m ruff check .                        # lint
.venv/Scripts/python -m ruff format .                       # auto-format
```

## DuckDB locally, Postgres in CI and production - and why

TECHNICAL_ARCHITECTURE.md specifies Postgres (Supabase-hosted) as the real backend database. This dev sandbox has no Docker and no admin rights to install Postgres natively, so a real local Postgres isn't available here. Rather than block on that:

- **Local/dev tests run against DuckDB** via `duckdb-engine` (a real SQLAlchemy dialect - the same `duckdb` dependency the data pipeline already relies on, not a new one) - fast, install-free, zero setup beyond `pip install`.
- **CI runs the same test suite against a real Postgres** (a `postgres:16` GitHub Actions `services:` container - GitHub-hosted runners do have Docker) - that job is the actual correctness gate. DuckDB is a local convenience layer only, never the thing that decides whether a change is correct.
- **`DATABASE_URL` is the only switch.** `app/config.py` defaults it to a local DuckDB file; CI and production override it via the environment to point at Postgres instead. No code branches on which database is in use.

**Real dialect gaps hit and worked around, not silently papered over** (duckdb-engine is a genuine, functioning SQLAlchemy dialect, but a less mainstream one than Postgres/MySQL/SQLite - these are the two rough edges found standing this up):

1. **`SERIAL` primary keys.** duckdb-engine's compiler is PostgreSQL-derived, so SQLAlchemy's default "auto" autoincrement on a single-column `Integer` primary key renders `CREATE TABLE ... SERIAL`, and DuckDB has no `SERIAL` type - `CatalogException: Type with name SERIAL does not exist!`. Worked around in `tests/test_db_session.py` by disabling autoincrement (the test supplies its own ids anyway). Real app models that need a DB-generated integer PK will need to pick a DuckDB-compatible pattern explicitly (e.g. a `Sequence`, or lean on Postgres-native `IDENTITY`/UUID defaults that DuckDB also supports) rather than relying on SQLAlchemy's default - noted here rather than solved preemptively, since no real model needs it yet.
2. **No Alembic DDL implementation for the `duckdb` dialect.** duckdb-engine registers a SQLAlchemy dialect but not an Alembic one - `alembic/env.py` hits `KeyError: 'duckdb'` immediately otherwise. `alembic/env.py` registers a minimal `DuckDBImpl` by subclassing Alembic's `PostgresqlImpl` (same PostgreSQL lineage as #1). This only matters for running migrations locally against DuckDB; CI/production use real Postgres, which Alembic already supports natively.
3. **Index reflection isn't implemented** (`DuckDBEngineWarning: duckdb-engine doesn't yet support reflection on indices`) - surfaced during `alembic revision --autogenerate`, harmless for table/column-level autogenerate but worth knowing if an index-heavy migration's autogenerate diff looks incomplete.

None of these are modeling differences serious enough to justify not testing locally against DuckDB at all - they're narrow, identified, and either worked around in test code or documented as a "decide when it's real" open item, not hidden behind a workaround that would mask an actual Postgres-vs-DuckDB behavior difference.

## Auth

Supabase Auth issues the JWTs this backend verifies (`SUPABASE_JWT_SECRET`) - see [../features/AUTHENTICATION.md](../features/AUTHENTICATION.md) for the full design and why Supabase specifically. `SUPABASE_URL`/`SUPABASE_ANON_KEY` round out the client-facing config the backend may need to hand back. None of these have a default in `app/config.py` - they're **required** environment variables (or a local, gitignored `.env` file); `Settings()` raises a `pydantic.ValidationError` at import time if any is missing, rather than the app silently starting with an empty credential. `tests/conftest.py` sets harmless test-only placeholder values for all three (via `os.environ.setdefault`, so a real environment's actual values always win) purely so `pytest` doesn't require live Supabase credentials just to run - no auth-verification logic exists yet to actually need real ones.

## Layout

`app/` is the FastAPI application (`main.py`'s `app`, `config.py`'s env-driven `Settings`, `db/` for the SQLAlchemy engine/session/base). `alembic/` holds migrations, wired to `app.db.base`'s metadata and `app.config`'s `DATABASE_URL` - see `alembic/env.py`. `tests/` mirrors `pipeline/tests/`'s shape: `conftest.py` for shared fixtures (a fresh per-test DuckDB engine/session, a `TestClient` with `get_db` overridden), one file per behavior area.

## CI

`.github/workflows/backend-tests.yml` runs `ruff check`, `ruff format --check`, and two pytest jobs on every push and on PRs targeting `main` - one against the DuckDB fixture (fast, always runs), one against a real `postgres:16` service (the actual correctness gate for the database this backend really runs on). Same visibility-only posture as the pipeline's CI (see `../TESTING.md`'s CI section): not yet a required check via branch protection.
