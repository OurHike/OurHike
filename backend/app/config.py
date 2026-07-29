"""App configuration, entirely env-driven.

The only setting with a real default is DATABASE_URL, and that default
points at a local DuckDB file - a fast, install-free path for local dev
(see backend/README.md for the full DuckDB-local/Postgres-CI rationale).
Every Supabase-related setting has no default: there is no world where a
hardcoded real secret belongs in this file, and failing loudly (a missing
required setting raises on startup) is better than silently running with
an empty string standing in for a real credential.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Local dev default only - DuckDB, file-backed so it survives across a
    # single dev session. CI overrides this to a real Postgres service URL;
    # production points at Supabase's hosted Postgres. See backend/README.md.
    database_url: str = "duckdb:///./dev.duckdb"

    # No defaults below - these are real credentials/identifiers for the
    # Supabase project this backend talks to, and must come from the
    # environment (or a local, gitignored .env file), never be hardcoded.
    # Omitting them entirely (as opposed to defaulting to "") means
    # `Settings()` raises a clear pydantic ValidationError at startup if
    # they're missing, rather than the app silently running with an empty
    # credential. Tests supply test-only dummy values via
    # tests/conftest.py - see the note there.
    supabase_jwt_secret: str
    supabase_url: str
    supabase_anon_key: str


settings = Settings()
