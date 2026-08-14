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

import os
from pathlib import Path

from dotenv import dotenv_values
from pydantic import model_validator
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

    # Cloudflare R2, for report photos (#234). Same vendor and same credential
    # SHAPE as pipeline/publish.py, and deliberately not the same variables.
    #
    # A PRIVATE BUCKET, WHICH IS WHY THE NAMES DIFFER
    #
    # These read R2_PHOTO_* rather than the R2_* that publish.py reads, and the
    # prefix is the whole point rather than tidiness. `R2_BUCKET` names the
    # PUBLISHED bucket - world-readable with no auth in front of it, by design
    # (LAUNCH_CHECKLIST.md 1.5 turns public access on; pipeline/R2_LAYOUT.md
    # says in as many words that condition reports must never go in it). This
    # backend originally read those same four variables, so any deployment that
    # carried the publishing environment - a shared secret store, a platform
    # that injects one set for the whole project - would have written report
    # photos into the public bucket. For a `bad_hikers` report that is a photo
    # of a person, published, while the report it belongs to stays private:
    # exactly the hole a private bucket exists to close, reopened by a variable
    # name.
    #
    # The token is separate for the same reason. The published bucket's token
    # is scoped to that bucket alone (LAUNCH_CHECKLIST.md 1.2), so it could not
    # write here even if pointed here - a shared credential would simply fail,
    # and the failure would arrive as a 503 on a hiker's upload rather than as
    # a configuration error anybody saw.
    #
    # All four default to empty rather than being required, because a backend
    # with no bucket is a normal, working deployment: every developer machine
    # and every CI run is one. What it cannot do is accept or serve a photo,
    # and the endpoints say exactly that rather than failing at startup for a
    # feature most runs never touch.
    r2_photo_endpoint_url: str = ""
    r2_photo_bucket: str = ""
    r2_photo_access_key_id: str = ""
    r2_photo_secret_access_key: str = ""
    # The explicit gate, copied from pipeline/publish.py's R2_WRITE_ENABLED
    # rather than inferred from "are the credentials present". Credentials can
    # be present for a reason that is not this one - a shared environment, a
    # secret injected by a platform - and a process that should not upload
    # should be UNABLE to, not merely unlikely to.
    #
    # Writes only. Serving a photo that is already stored is not gated on this:
    # a deployment told to stop accepting uploads should still be able to show
    # a moderator the photo attached to the report they are deciding on.
    r2_photo_write_enabled: bool = False

    @model_validator(mode="after")
    def _photos_do_not_go_in_the_published_bucket(self) -> "Settings":
        """Refuse to start rather than publish a photo of a person.

        The separate `R2_PHOTO_` names above stop the publishing variables from
        CONFIGURING this backend by accident. They cannot stop somebody pasting
        the published bucket's name into `R2_PHOTO_BUCKET` on purpose, and that
        is the same outcome by a different route: a `bad_hikers` photo is a
        photo of a person, and LAUNCH_CHECKLIST.md 1.5 turns public read on for
        the bucket this would put it in.

        #395 calls misconfiguration the largest realistic risk in this system -
        larger than traffic - and asks for an alarm on it. This is the loudest
        available: a process that should not be able to do this is made unable
        to, rather than merely unlikely to, which is the same argument
        `r2_photo_write_enabled` above makes for uploads generally.

        It reads the publishing names through `_publishing_setting`, not as
        fields. `R2_BUCKET` and `R2_ACCESS_KEY_ID` must never CONFIGURE this
        backend - adding them as fields to compare against would undo the
        separation the comment above spends its length on. What is being asked
        is not "what is my published bucket" but "is this process also
        carrying the publishing variables, and have the two been pointed at
        the same place" - and "carrying" has to mean every channel this
        model's own fields arrive by. This guard used to ask `os.environ`
        alone, and the exact collision it exists to refuse constructed
        cleanly out of a `backend/.env` - the gitignored file the top of this
        class sanctions - because pydantic-settings loads a .env without
        exporting it (#649).

        Silent when the publishing variables are absent from both channels,
        which is every developer machine, every CI run, and a correctly
        separated production backend. Absent-and-quiet is not a safety proof,
        and this docstring used to imply one: a backend-only host where
        somebody pastes the published bucket's NAME with no publishing
        variables anywhere is indistinguishable, from inside this process,
        from a correctly configured one. That case has no in-process check -
        it is what LAUNCH_CHECKLIST.md 1.7's separate-bucket step and its
        scoped token exist to prevent - so this guard claims exactly the
        collisions it can see, and no more.
        """
        published_bucket = self._publishing_setting("R2_BUCKET")
        if published_bucket and self.r2_photo_bucket.strip() == published_bucket:
            raise ValueError(
                f"R2_PHOTO_BUCKET is {published_bucket!r}, which is also R2_BUCKET - the PUBLISHED "
                "bucket, which has public read turned on. Report photos are not published data: a "
                "bad_hikers report is a photo of a person and its report stays private. Create a "
                "second, private bucket (LAUNCH_CHECKLIST.md 1.7) and point R2_PHOTO_BUCKET at it."
            )

        published_key = self._publishing_setting("R2_ACCESS_KEY_ID")
        if published_key and self.r2_photo_access_key_id.strip() == published_key:
            raise ValueError(
                "R2_PHOTO_ACCESS_KEY_ID is the same token as R2_ACCESS_KEY_ID, which is scoped to "
                "the published bucket (LAUNCH_CHECKLIST.md 1.2). Either it cannot write here - so "
                "every upload 503s - or it is broader than it should be and can write there. "
                "Create a token scoped to the photo bucket alone (LAUNCH_CHECKLIST.md 1.7.2)."
            )

        return self

    def _publishing_setting(self, name: str) -> str:
        """A publishing variable as this process could be carrying it.

        Both channels this model's own fields arrive by, in the same order of
        precedence pydantic-settings applies to them: the process environment
        first, then the `.env` file `model_config` names. Reading only the
        first is how the collision guard above was bypassed (#649).
        """
        from_environ = os.environ.get(name)
        if from_environ is not None:
            return from_environ.strip()
        env_file = self.model_config.get("env_file")
        if isinstance(env_file, str) and Path(env_file).exists():
            return (dotenv_values(env_file).get(name) or "").strip()
        return ""


settings = Settings()
