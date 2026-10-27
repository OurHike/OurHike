"""The two startup guards on which Supabase this backend trusts (app/config.py).

Both make `Settings()` refuse to build, and app/config.py builds it at import,
so a deployment carrying either mistake never starts rather than starting and
serving it. The project refs below are made up; the real ones are in
LAUNCH_CHECKLIST.md §6.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings

PASSWORD = "hunter2-not-a-real-password"


def _pooled(ref: str) -> str:
    """The pooled string LAUNCH_CHECKLIST.md §6 step 2 pastes: the project rides in the user name."""
    return f"postgresql+psycopg://postgres.{ref}:{PASSWORD}@aws-0-us-east-1.pooler.supabase.com:6543/postgres"


def _direct(ref: str) -> str:
    """A direct connection: the project rides in the host."""
    return f"postgresql+psycopg://postgres:{PASSWORD}@db.{ref}.supabase.co:5432/postgres"


@pytest.fixture(autouse=True)
def _no_dot_env(monkeypatch, tmp_path):
    """Settings() reads `.env` from the working directory, and a developer's own must not decide these."""
    monkeypatch.chdir(tmp_path)


def _settings(monkeypatch, *, database_url: str, supabase_url: str) -> Settings:
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("SUPABASE_URL", supabase_url)
    return Settings()


# --- SUPABASE_URL is where the signing keys come from ------------------------


def test_supabase_url_over_https_is_accepted(monkeypatch):
    built = _settings(monkeypatch, database_url=_pooled("aaaa1111"), supabase_url="https://aaaa1111.supabase.co")

    assert built.supabase_url == "https://aaaa1111.supabase.co"


@pytest.mark.parametrize(
    "url",
    [
        "http://aaaa1111.supabase.co",
        # Starts with an allowed host's name and is somebody else's machine.
        "http://localhost.example.com",
        "http://127.0.0.1.nip.io",
        "aaaa1111.supabase.co",
        "",
    ],
)
def test_supabase_url_that_is_not_https_is_refused(monkeypatch, url):
    """app/core/auth.py checks every token against the keys this URL answers
    with. Over plain http, anyone on the network path can answer with their
    own keys and sign in as anybody, moderators included."""
    with pytest.raises(ValidationError) as caught:
        _settings(monkeypatch, database_url=_pooled("aaaa1111"), supabase_url=url)

    assert "SUPABASE_URL has to be https://" in str(caught.value)


@pytest.mark.parametrize("url", ["http://localhost:54321", "http://127.0.0.1:54321", "http://[::1]:54321"])
def test_plain_http_is_accepted_for_a_supabase_on_this_machine(monkeypatch, url):
    """What `supabase start` serves on a developer's machine, where nothing sits on the path."""
    assert _settings(monkeypatch, database_url=_pooled("aaaa1111"), supabase_url=url).supabase_url == url


# --- DATABASE_URL and SUPABASE_URL name one project --------------------------


@pytest.mark.parametrize("database_url", [_pooled("aaaa1111"), _direct("aaaa1111")], ids=["pooled", "direct"])
def test_a_database_in_one_project_and_sign_in_in_another_refuses_to_start(monkeypatch, database_url):
    """Production's database string pasted beside UA's SUPABASE_URL, or the
    reverse. Without this the process boots, `SELECT 1` passes, and hikers
    are served the other project's closures as live."""
    with pytest.raises(ValidationError) as caught:
        _settings(monkeypatch, database_url=database_url, supabase_url="https://bbbb2222.supabase.co")

    message = str(caught.value)
    assert "DATABASE_URL is Supabase project aaaa1111, but SUPABASE_URL is project bbbb2222" in message


def test_the_refusal_prints_no_part_of_the_connection_string(monkeypatch):
    """A refusal at startup lands in the host's log. Pydantic would print
    `input_value=` (every setting given, DATABASE_URL included, cut down to
    its two ends) unless the model hides it, and the guard's own message
    names the two projects and nothing else."""
    with pytest.raises(ValidationError) as caught:
        _settings(monkeypatch, database_url=_pooled("aaaa1111"), supabase_url="https://bbbb2222.supabase.co")

    message = str(caught.value)
    assert PASSWORD not in message
    assert "pooler.supabase.com" not in message
    assert "input_value" not in message


@pytest.mark.parametrize("database_url", [_pooled("aaaa1111"), _direct("aaaa1111")], ids=["pooled", "direct"])
def test_one_project_on_both_starts(monkeypatch, database_url):
    built = _settings(monkeypatch, database_url=database_url, supabase_url="https://aaaa1111.supabase.co")

    assert built.database_url == database_url


@pytest.mark.parametrize(
    ("database_url", "supabase_url"),
    [
        # The suite's own database, and any developer's.
        ("postgresql+psycopg://ourhike:ourhike@localhost:5432/ourhike_test", "https://aaaa1111.supabase.co"),
        # A pooler string missing its project names none, so nothing is compared.
        (
            "postgresql+psycopg://postgres:pw@aws-0-us-east-1.pooler.supabase.com:6543/postgres",
            "https://aaaa1111.supabase.co",
        ),
        # migrate.yml and schema-drift.yml pass this beside the real DATABASE_URL.
        (_pooled("aaaa1111"), "https://migrations-never-call-this.invalid"),
        # pages.yml's OpenAPI dump.
        (_pooled("aaaa1111"), "https://openapi-dump.invalid"),
        # A self-hosted Supabase names no project in either string.
        ("postgresql+psycopg://postgres:pw@db.example.org:5432/postgres", "https://supabase.example.org"),
    ],
    ids=["local", "pooler-without-project", "migration-placeholder", "openapi-placeholder", "self-hosted"],
)
def test_a_pair_that_names_no_project_on_one_side_is_not_compared(monkeypatch, database_url, supabase_url):
    """The guard compares only what both strings state. It cannot tell a
    self-hosted project from a wrong paste, and does not guess."""
    assert _settings(monkeypatch, database_url=database_url, supabase_url=supabase_url).supabase_url == supabase_url
