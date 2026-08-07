# OurHike backend

Companion to [../TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md). This is the FastAPI backend behind auth, community condition reports/moderation, closures, and warning escalation - the "someone has to be able to mark a closure and a moderator has to be able to escalate a warning" half of v1 MVP (see that doc's Backend section for why this moved into MVP on 2026-07-28).

## Setup

```
python -m venv .venv
.venv/Scripts/pip install -r requirements-dev.txt   # Windows; .venv/bin/pip on macOS/Linux
bash scripts/local-postgres.sh                      # start the local database
```

`scripts/local-postgres.sh` is idempotent - run it whenever nothing is listening on 5432. It starts a Postgres if the machine has one installed (Debian/Ubuntu's `pg_ctlcluster` layout, Homebrew, anything already running), otherwise brings one up from `docker-compose.yml`, and either way creates the `ourhike` role plus the `ourhike_dev` and `ourhike_test` databases that `app/config.py` and `tests/conftest.py` default to. `OURHIKE_PG_PORT`, `OURHIKE_PG_USER` and friends override the defaults; `OURHIKE_PG_MODE=native|docker` overrides the auto-detection.

Everything the suite touches lives in `ourhike_test`, which it drops tables from freely - that is why it is a separate database from `ourhike_dev` and why nothing you are working on lives there.

## Quick start

```
.venv/Scripts/python -m uvicorn app.main:app --reload   # run the dev server
.venv/Scripts/python -m pytest                            # run everything (prints a coverage summary too)
.venv/Scripts/python -m pytest tests/test_x.py             # one file
.venv/Scripts/python -m pytest -k test_name                # one test
.venv/Scripts/python -m ruff check .                        # lint
.venv/Scripts/python -m ruff format .                       # auto-format
```

## Postgres everywhere - and why DuckDB is not here

TECHNICAL_ARCHITECTURE.md specifies Postgres (Supabase-hosted) as the real backend database. Every environment this code runs in is that same engine:

- **Local dev and local tests: a real Postgres**, started by `scripts/local-postgres.sh` (see Setup). Whatever major version the machine has - 16 on the Claude Code web sandbox, which is what its image ships.
- **CI: a real Postgres**, a `postgres:17` `services:` container - see `.github/workflows/backend-tests.yml`. 17 because that is what the Supabase project runs (17.6, checked 2026-08-07), and the gate is the thing that should track production.
- **Production: Supabase's Postgres**, 17.6.
- **`DATABASE_URL` is the only difference between them.** `app/config.py` defaults it to the local database; CI and production override it via the environment. No code branches on which database is in use, because there is only one kind.

**DuckDB is the data pipeline's engine, not this one.** `pipeline/` uses it for what it is excellent at - spatial analytics over the trail dataset, columnar scans across millions of rows, all of it read-mostly and rebuildable from source. None of that describes a transactional API writing rows a hiker cannot afford to lose. This backend previously ran on DuckDB locally (via `duckdb-engine`) with Postgres only in CI, on the reasoning that a local Postgres was unavailable in the dev sandbox; that turned out not to be true, and the split cost more than it saved:

1. **`SERIAL` primary keys didn't exist there.** duckdb-engine's compiler is PostgreSQL-derived, so SQLAlchemy's default autoincrement on an `Integer` primary key rendered `CREATE TABLE ... SERIAL`, which DuckDB has no type for. Worked around in test code, and a standing constraint on any real model that wanted a database-generated integer id.
2. **`TIMESTAMPTZ` couldn't be read back** without the optional `pytz` package, which is why every datetime column here is stored naive-UTC and stamped on the way out (see `app/models/profile.py` - the convention stays for now, and changing it is a migration, not a comment edit).
3. **Alembic had no DDL implementation for the dialect**, so `alembic/env.py` had to register one by subclassing `PostgresqlImpl` - and the row-level-security migration then had to guard itself against being handed Postgres DDL it could not run.
4. **Index reflection was unimplemented**, so `alembic revision --autogenerate` could not see indexes at all.

Every one of those is now gone rather than worked around, and the local suite exercises the migrations themselves for the first time (`tests/test_migrations.py`) - which was impossible while local dev ran on an engine that could not execute them.

## Connecting through Supabase's pooler

Supabase offers more than one connection string, and they are not interchangeable. The **transaction pooler** (Supavisor, port 6543) is the one its dashboard presents first, and it hands each transaction whatever Postgres backend is free - so nothing a driver leaves on a connection between transactions survives.

psycopg leaves exactly that: it prepares a statement server-side after its 5th execution and refers to it by name afterwards. Through a transaction pooler, that name means nothing on the next backend. The result is a 500 on an endpoint that worked the first four times, in production only.

**`app/db/session.py`'s `engine_options` turns it off**, along with `pool_pre_ping` for connections a pooler or an idle timeout has closed underneath us. The default is the safe one: `DATABASE_PREPARED_STATEMENTS=true` opts a direct-connection deployment back into the plan caching.

**It is tested against a real pooler, not asserted about.** `scripts/local-pooler.sh` runs pgbouncer in transaction mode in front of `ourhike_test` and prints a `POOLER_DATABASE_URL`; `tests/test_pooler.py` drives interleaved transactions through it, and skips itself when that variable is unset. CI sets it up the same way, using the same script. One of the two tests deliberately asserts the *unfixed* configuration still breaks - without it, deleting `prepare_threshold` from the engine options would leave a green suite.

```
bash scripts/local-pooler.sh
export POOLER_DATABASE_URL=postgresql+psycopg://ourhike:ourhike@127.0.0.1:6432/ourhike_test
python -m pytest tests/test_pooler.py -v
```

pgbouncer is not Supavisor. What it reproduces is the constraint they share - a transaction may land anywhere - which is the part the driver has to be configured for. Whether the *real* pooler behaves identically is still unverified, and needs the production connection string (see the open half of [#95](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/95)).

## Auth

Supabase Auth issues the JWTs this backend verifies - see [../features/AUTHENTICATION.md](../features/AUTHENTICATION.md) for the full design and why Supabase specifically.

**How they are signed depends on where Supabase runs, and both cases are handled.** A hosted project signs **ES256** and publishes the public half as a JWKS at `<SUPABASE_URL>/auth/v1/.well-known/jwks.json` - confirmed against a token a real project issued. A self-hosted one signs **HS256** against a shared secret. `verify_supabase_jwt` reads the algorithm off the token and picks the matching key, pinning one algorithm and one key source per branch; see the module docstring in `app/core/auth.py` for why that is not an algorithm-confusion hole, since reading `alg` off an unverified header is how those start.

`SUPABASE_URL` and `SUPABASE_ANON_KEY` are **required** environment variables (or a local, gitignored `.env` file); `Settings()` raises a `pydantic.ValidationError` at import time if either is missing, rather than the app silently starting with an empty credential. `SUPABASE_JWT_SECRET` is the exception and defaults to empty, because a hosted project has no shared secret to supply and demanding one would stop a correctly configured deployment from starting. An HS256 token arriving with it unset is refused with a message naming the reason, rather than verified against an empty key - an empty HMAC key is a perfectly valid HMAC key, which would accept tokens anyone could mint.

`tests/conftest.py` sets harmless placeholder values (via `os.environ.setdefault`, so a real environment's values always win) so `pytest` needs no live credentials. The ES256 tests generate their own keypair and hand the public half to the `signing_key_for` seam, so the signature checking is real without touching the network.

`check_supabase_config.py` is the live counterpart, run from the **Supabase config check** workflow: it reads a real project and reports whether its signing algorithm is one this code accepts, and whether the providers the client offers are actually enabled. Read-only, stdlib-only, manual.

`SUPABASE_JWT_AUDIENCE` is the one auth setting that *does* have a default, `authenticated`, because it is neither a secret nor project-specific - it is the `aud` claim Supabase Auth puts on every signed-in user's access token. It has to be passed to PyJWT explicitly: a token carrying `aud` is rejected outright when the verifier names no audience, so leaving it unset would 401 every real signed-in request while accepting the `aud`-less tokens only a test could produce. Set it if a project is configured differently, or to an empty string to skip the audience check entirely. Test tokens are minted in one place, `tests/tokens.py`, in the shape Supabase really issues.

## Report photos

`PUT /reports/{report_id}/photo` writes a JPEG to a **private** Cloudflare R2 bucket and records the object key on the row. Part 1 of three (#363); nothing can read a photo yet, and the client cannot take one yet.

**Five environment variables, and none of them has a default.** Four are the same names `pipeline/publish.py` already reads, deliberately - one bucket, one set of credentials to rotate, rather than two that drift:

| Variable | |
|---|---|
| `R2_ENDPOINT_URL` | the account's S3-compatible endpoint |
| `R2_BUCKET` | private; never public-read |
| `R2_ACCESS_KEY_ID` | |
| `R2_SECRET_ACCESS_KEY` | |
| `R2_WRITE_ENABLED` | the gate — uploads are refused unless this is `true` |

Unlike the Supabase settings, a missing one of these does **not** stop the app booting: a deployment with no photo storage is a valid deployment, and everything else still works. The endpoint answers `503` and names which variable is missing, because "R2 is not configured" without saying which half is a support ticket rather than a fix.

`R2_WRITE_ENABLED` is `pipeline/publish.py`'s gate reused, not a second one. It exists so an environment that should not be writing to the bucket cannot, and finds out loudly.

**The bucket must stay private.** `bad_hikers` reports are `internal_only` and their photos are photos of people; `thanks` is `club_only`; and every report is unmoderated at the moment a photo is attached. A public-read bucket would publish the image while the report stayed private. `app/core/photo_storage.py` passes no ACL for that reason, and the Worker that checks the owning report's `visibility` and `status` before streaming an object is part 2.

Tests use `moto` to mock S3 in-process, the same choice `pipeline/tests/test_publish.py` made — a real boto3 client against a fake bucket, rather than a mocked call and an assertion that it happened.

## Layout

`app/` is the FastAPI application (`main.py`'s `app`, `config.py`'s env-driven `Settings`, `db/` for the SQLAlchemy engine/session/base). `alembic/` holds migrations, wired to `app.db.base`'s metadata and `app.config`'s `DATABASE_URL` - see `alembic/env.py`. `scripts/` holds `local-postgres.sh` (the database) and `local-pooler.sh` (a transaction-mode pooler in front of it, for the tests that need one); `docker-compose.yml` is the database `local-postgres.sh` falls back to when the machine has no Postgres installed. `tests/` mirrors `pipeline/tests/`'s shape: `conftest.py` for shared fixtures (a clean-schema engine/session per test against the local Postgres, a `TestClient` with `get_db` overridden), one file per behavior area.

## Migrations

`alembic/versions/` has two migrations: `initial_schema`, creating all seven tables (`clubs`, `profiles`, `closures`, `hikes`, `maintainer_assignments`, `reports`, `user_preferences`), and `enable_row_level_security`, which locks them against Supabase's PostgREST front door.

**Both now run against a real Postgres in the test suite** - `tests/test_migrations.py` applies the chain to the local database, reads the RLS flags back out of `pg_class`, downgrades to base, and runs `alembic check` for drift between the models and the migrations. That is new: while local dev ran on DuckDB, no test had ever executed a migration at all, and the RLS revision was specifically unrunnable there. Review a migration yourself before trusting it against real data all the same - a passing test says the DDL is valid, not that it is what you meant.

**One thing running it on real Postgres immediately showed, not fixed here:** the `Enum(..., native_enum=False)` columns render as a bare `VARCHAR(20)` with no `CHECK` constraint - SQLAlchemy has defaulted `create_constraint` to `False` since 1.4, so a comment claiming "VARCHAR + CHECK" had been wrong for as long as it existed and there was no way to notice while the local database was DuckDB. Nothing is currently broken by it: every write path goes through the pydantic schemas, which reject an unknown value long before SQLAlchemy sees it. Adding the constraints is a schema migration and a judgement call about what the database should enforce on its own, so it is written down here rather than slipped into a change about which database runs locally.

**A real bug this surfaced, now fixed:** `app/models/__init__.py` was empty, and nothing else reachable from `alembic/env.py` ever imported the actual model modules - so `Base.metadata` was empty at the exact moment autogenerate looked at it, and `alembic revision --autogenerate` silently produced a no-op migration (`pass`/`pass`) instead of one creating any tables. `app/models/__init__.py` now imports every model (so `Base.metadata` is complete for any caller, not just this one), and `alembic/env.py` explicitly imports `app.models` too, since nothing else in its own import chain would trigger that registration. Worth knowing this existed if a *future* model ever gets added without a matching entry in `app/models/__init__.py` - the symptom would be the same silent empty migration, not an error.

**Applying it to the real Supabase database** (never run against production from here - that needs credentials this environment doesn't have):

```
DATABASE_URL=postgresql+psycopg://... .venv/Scripts/python -m alembic upgrade head
```

Point `DATABASE_URL` at the real Supabase Postgres connection string first. Deliberately a manual, separate step from deployment (see Deployment below) - a migration should be a reviewed, intentional action, not something that fires automatically on every container start/restart.

## CI

`.github/workflows/backend-tests.yml` runs `ruff check`, `ruff format --check` and `pytest` on every push and on PRs targeting `main`, against a `postgres:16` service container. One job, because there is one database engine - the second job that used to run the suite against DuckDB went away with the DuckDB dev path (see above), having become a check on an engine nothing uses. Same visibility-only posture as the pipeline's CI (see `../TESTING.md`'s CI section): not yet a required check via branch protection.

## Deployment

`Dockerfile` + `fly.toml` target [Fly.io](https://fly.io) - picked over Render specifically to avoid Render's free-tier sleep-on-idle behavior (a cold start on the first request after idle is a worse experience for something safety-adjacent than a small ongoing hosting cost). `fly.toml` deliberately keeps `min_machines_running = 1` for the same reason - see the comment in that file if that tradeoff ever needs revisiting.

**Not yet done, and needs real decisions first:**
1. `fly apps create` (or `fly launch`) with a real, globally-unique app name - `fly.toml`'s `app = "ourhike-backend"` is a placeholder, update it to match.
2. Set the real secrets Fly.io needs at runtime (`fly secrets set DATABASE_URL=... SUPABASE_JWT_SECRET=... SUPABASE_URL=... SUPABASE_ANON_KEY=...`) - never committed, never baked into the image.
3. `fly deploy` from this directory.
4. Run the Migrations step above against the real `DATABASE_URL` - not automatic, see why above.
5. Point the client's API base URL at the deployed app, and add its origin to Supabase's allowed redirect URLs (see `../LAUNCH_CHECKLIST.md`).

**Build/deploy config is untested against a real Fly.io account or Docker daemon** - this sandbox has no Fly.io account, and while the Docker CLI is on its PATH, no daemon is running behind it (the same reason `docker-compose.yml` is documented but unexercised here, and why `scripts/local-postgres.sh` uses the container's own Postgres install instead). The Dockerfile follows a standard, well-established FastAPI/uvicorn pattern and `fly.toml`'s shape matches Fly's own documented format, but "should work" isn't the same claim as "confirmed working" - budget for the first real `fly deploy` to surface something this couldn't catch locally.
