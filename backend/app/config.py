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
    # The one Supabase setting with an empty default, and not for convenience.
    # A hosted project signs with ES256 and publishes the public half as a
    # JWKS; there is no shared secret in that arrangement, so demanding one
    # would make a correctly configured deployment refuse to start. Self-hosted
    # Supabase does sign with HS256, which is the case this still exists for -
    # see app/core/auth.py for how the two are told apart, and why an HS256
    # token arriving with this unset is refused rather than waved through.
    supabase_jwt_secret: str = ""
    supabase_url: str
    supabase_anon_key: str

    # The `aud` claim every Supabase user access token carries. This one DOES
    # have a default, unlike the credentials above, because it is not a secret
    # and not project-specific: "authenticated" is what Supabase Auth puts in
    # a signed-in user's token everywhere. It is a setting at all so a project
    # configured otherwise can say so without a code change - and setting it
    # to "" turns the audience check off, for a token shape this does not
    # anticipate. See app/core/auth.py for why it must be passed explicitly.
    supabase_jwt_audience: str = "authenticated"


settings = Settings()
