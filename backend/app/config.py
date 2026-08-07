"""App configuration, entirely env-driven.

The only setting with a real default is DATABASE_URL, and that default
points at a local Postgres - the same engine Supabase runs in production
(see backend/README.md, and backend/scripts/local-postgres.sh for the one
command that stands it up).
Every Supabase-related setting has no default: there is no world where a
hardcoded real secret belongs in this file, and failing loudly (a missing
required setting raises on startup) is better than silently running with
an empty string standing in for a real credential.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Local dev default only, and deliberately a real Postgres rather than an
    # embedded stand-in: everything this backend writes ends up in Supabase's
    # hosted Postgres, so the local database is the same engine, differing
    # only in where it runs. `backend/scripts/local-postgres.sh` creates
    # exactly this role/database (and the ourhike_test one the suite uses).
    # CI overrides this to point at its own Postgres service container;
    # production points at Supabase. See backend/README.md.
    #
    # The credentials here are local-only, for a database holding throwaway
    # data on a developer's own machine - unlike everything below, which is
    # why they can sit in the file at all.
    database_url: str = "postgresql+psycopg://ourhike:ourhike@localhost:5432/ourhike_dev"

    # Off by default, which is the unusual direction for a performance
    # feature and is deliberate. psycopg prepares a statement server-side
    # after its 5th execution on a connection; through Supabase's
    # transaction-mode pooler the next transaction can land on a different
    # backend, and the prepared name means nothing there. The failure is a
    # 500 on a warm endpoint, in production only, under the connection
    # string Supabase's dashboard offers first - see app/db/session.py's
    # `engine_options` for the reproduction. Set this true on a deployment
    # that connects directly to Postgres (no pooler) and wants the plan
    # caching.
    database_prepared_statements: bool = False

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
