"""Configuration, from the environment, every name prefixed STEWARD_.

Its own prefix rather than backend/'s names, so a host that injects OurHike's
environment can never hand this service OurHike's database by accident: the
two share a Supabase project for sign-in (PLAN.md §11) and nothing else.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STEWARD_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    #: Local default only, on the Postgres backend/scripts/local-postgres.sh
    #: starts. The credentials are that script's throwaway local ones.
    database_url: str = "postgresql+psycopg://ourhike:ourhike@localhost:5432/steward_dev"

    #: The Supabase project whose sign-in this API trusts. No default: a
    #: deployment without it must fail at startup, not accept no one or anyone.
    supabase_url: str

    #: Only for a self-hosted Supabase signing with HS256; a hosted project
    #: signs with ES256 and has no shared secret (backend/app/core/auth.py).
    supabase_jwt_secret: str = ""

    #: The `aud` every Supabase user access token carries.
    jwt_audience: str = "authenticated"

    #: Browser origins allowed to call this API, comma-separated: the steward
    #: web app's address. Empty allows none, which is the safe default.
    allowed_origins: Annotated[list[str], NoDecode] = []

    #: Where the analysis job's public summary.json is served, for the list of
    #: clubs a weights change may name. Empty refuses every weights change.
    summary_url: str = ""

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        return value
