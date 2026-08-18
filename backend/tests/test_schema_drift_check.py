"""check_schema_drift.py tells the three states apart, against real Postgres.

The script exists to be run against Supabase, where the interesting states are
the ones nobody can arrange on purpose: a database at a revision this
repository has never seen, or one at head that still does not match the
models. Both are cheap to arrange *here*, which is the point of testing it
this way - the alternative is finding out what the script does on the day
production is already wrong.

`classify` is tested as a pure function because UNKNOWN cannot be produced by
any sequence of real migrations: it needs a revision id this repository does
not contain, which is exactly what makes it worth having a branch for.

The fixture below is deliberately a copy of `test_migrations.py`'s rather than
a shared one in conftest.py. That file's comment explains what the teardown is
protecting (a run interrupted mid-test leaves a half-built schema, and
`upgrade head` onto one fails for reasons that have nothing to do with the
subject) and both files want it for that reason - but a fixture in conftest.py
is offered to every test in the suite, including the ones whose whole
assumption is that no migration has run.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy

import check_schema_drift
from alembic import command
from app.config import settings
from tests.conftest import _reset_schema

REAL_REVISIONS = {"aaaa1111", "bbbb2222", "cccc3333"}

BACKEND_DIR = Path(__file__).resolve().parents[1]

# A well-formed session-mode string, so the subprocess tests below fail on the
# thing they are about rather than on the URL. The password is fake and is
# asserted absent from the output.
SESSION_POOLER_URL = "postgresql+psycopg://postgres.abc:hunter2@aws-0-us-east-1.pooler.supabase.com:5432/postgres"


@pytest.fixture()
def migration_engine():
    engine = sqlalchemy.create_engine(settings.database_url)
    _reset_schema(engine)
    try:
        yield engine
    finally:
        _reset_schema(engine)
        engine.dispose()


# --- the connection string is one a migration can use ----------------------


def test_a_dashboard_url_without_the_driver_is_refused():
    """What you get by pasting Supabase's string unedited.

    SQLAlchemy resolves a bare `postgresql://` to psycopg2, which this backend
    does not install, so without this the failure is an import error naming a
    driver nobody chose.
    """
    reason = check_schema_drift.unsuitable_reason("postgresql://postgres:pw@db.abc.supabase.co:5432/postgres")
    assert reason is not None
    assert "postgresql+psycopg://" in reason


def test_the_transaction_pooler_is_refused():
    """Port 6543 is right for the running app and wrong for a migration -
    each transaction gets a different backend, so the DDL and the advisory
    lock do not share a session."""
    reason = check_schema_drift.unsuitable_reason(
        "postgresql+psycopg://postgres.abc:pw@aws-0-us-east-1.pooler.supabase.com:6543/postgres"
    )
    assert reason is not None
    assert "5432" in reason, "The message names the port to use instead, not just the one that is wrong."


def test_the_session_pooler_is_accepted():
    """Session mode: IPv4, and one backend per connection for its whole life.
    The combination GitHub's hosted runners actually need."""
    assert (
        check_schema_drift.unsuitable_reason(
            "postgresql+psycopg://postgres.abc:pw@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
        )
        is None
    )


def test_the_direct_endpoint_is_accepted_but_warned_about():
    """Not refused, because it is the best target for a migration and works
    from a laptop with IPv6 or a project with the IPv4 add-on. Warned about,
    because it is IPv6-only by default and hosted runners are IPv4-only, so
    the failure it produces is a timeout that names nothing."""
    url = "postgresql+psycopg://postgres:pw@db.abc.supabase.co:5432/postgres"
    assert check_schema_drift.unsuitable_reason(url) is None
    assert "IPv6" in (check_schema_drift.warn_if_hard_to_reach(url) or "")


def test_the_local_database_warns_about_nothing():
    assert check_schema_drift.warn_if_hard_to_reach(settings.database_url) is None


def test_url_only_stops_before_touching_the_network(monkeypatch, capsys):
    """The preflight migrate.yml runs before `alembic upgrade head`, so a
    mistyped secret is caught before anything is half-applied."""

    def fail(_url):
        raise AssertionError("--url-only must not connect")

    monkeypatch.setattr(check_schema_drift, "read_current_revision", fail)

    assert check_schema_drift.main(["--label", "test", "--url-only"]) == 0
    assert "usable for a migration" in capsys.readouterr().out


def test_an_unusable_url_stops_the_run_before_it_connects(monkeypatch, capsys):
    """Exit 2, the same as an unreachable database: both mean the check could
    not form a verdict, which is a different thing from the schema being
    wrong."""

    def fail(_url):
        raise AssertionError("a refused URL must not connect")

    monkeypatch.setattr(check_schema_drift, "read_current_revision", fail)
    monkeypatch.setattr(
        check_schema_drift,
        "load_settings",
        lambda: SimpleNamespace(database_url="postgresql://postgres:pw@localhost:5432/x"),
    )

    assert check_schema_drift.main(["--label", "test"]) == 2
    assert "postgresql+psycopg://" in capsys.readouterr().out


# --- the environment a migration job actually has --------------------------


def _run_in(env: dict[str, str]):
    """The script in its own process, with exactly the environment given.

    A subprocess rather than monkeypatch because `tests/conftest.py` sets
    SUPABASE_URL and SUPABASE_ANON_KEY for the whole session - which is right
    for the suite and is precisely why no in-process test could have caught
    the failure this covers. Nothing in this process can un-import
    `app.config` once conftest has made it importable.
    """
    return subprocess.run(
        [sys.executable, "check_schema_drift.py", "--label", "test", "--url-only"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def test_only_database_url_is_not_enough_and_the_message_says_which():
    """What migrate.yml passed on the merge commit of #411.

    `app/config.py` builds Settings() at import time and several fields have
    no default, so a job carrying only DATABASE_URL cannot import the module
    that holds DATABASE_URL. alembic/env.py imports the same settings, so the
    upgrade step would have died the same way one step later.
    """
    result = _run_in({"PATH": os.environ["PATH"], "DATABASE_URL": SESSION_POOLER_URL})

    assert result.returncode == 2
    # SUPABASE_ANON_KEY used to be named here too; it became optional in #257
    # (nothing in app/ reads it), so SUPABASE_URL is the one required setting
    # left for this message to name.
    assert "SUPABASE_URL" in result.stdout


def test_a_missing_setting_never_prints_the_connection_string():
    """The reason load_settings() catches ValidationError rather than letting
    it raise. Pydantic renders the rejected input, which for this model is the
    dict holding DATABASE_URL - and GitHub's log masking matches whole secret
    values, so a truncated one prints in fragments. That is how #411's run
    revealed which endpoint the credential named.
    """
    result = _run_in({"PATH": os.environ["PATH"], "DATABASE_URL": SESSION_POOLER_URL})

    combined = result.stdout + result.stderr
    assert "supabase.com" not in combined, "the host leaked"
    assert "hunter2" not in combined, "the password leaked"
    assert "Traceback" not in combined, "a traceback here is how the fragments got out in the first place"


def test_the_environment_the_workflows_pass_is_enough():
    """The fix, asserted as the workflows configure it: DATABASE_URL plus the
    two Supabase settings the app needs and a migration does not."""
    result = _run_in(
        {
            "PATH": os.environ["PATH"],
            "DATABASE_URL": SESSION_POOLER_URL,
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_ANON_KEY": "sb_publishable_example",
        }
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "usable for a migration" in result.stdout


# --- classify, as a pure function -----------------------------------------


def test_a_database_with_no_alembic_version_is_empty_not_a_fault():
    state, detail = check_schema_drift.classify(None, "cccc3333", REAL_REVISIONS, [])
    assert state == check_schema_drift.EMPTY
    assert state not in check_schema_drift.FAILING_STATES, (
        "A database nobody has migrated yet is the state UA and production are both in today."
    )
    assert "never had a migration applied" in detail


def test_a_revision_this_repository_does_not_contain_fails():
    """The signature of a second ledger, or of `alembic stamp` run by hand.

    Worth failing on rather than reporting, and the reason is that it is not
    recoverable by doing the obvious thing: `upgrade head` from a revision
    Alembic cannot place in its graph does not run the missing steps, it
    errors. Somebody has to look.
    """
    state, detail = check_schema_drift.classify("dddd4444", "cccc3333", REAL_REVISIONS, [])
    assert state == check_schema_drift.UNKNOWN
    assert state in check_schema_drift.FAILING_STATES
    assert "not a revision in this repository" in detail


def test_being_behind_head_is_reported_and_never_failed():
    """The state production is in between a migration merging and somebody
    applying it - which RELEASING.md 8c makes a deliberate wait, so this is
    the normal condition rather than a delay. A check that went red for it
    would be red most weeks, and a check that is usually red is not read."""
    state, detail = check_schema_drift.classify("aaaa1111", "cccc3333", REAL_REVISIONS, ["bbbb2222", "cccc3333"])
    assert state == check_schema_drift.BEHIND
    assert state not in check_schema_drift.FAILING_STATES
    assert "2 revision(s) behind" in detail
    assert "bbbb2222, cccc3333" in detail, "The pending revisions are named, so the log says what applying would do."


def test_at_head_is_reported_as_such():
    state, _ = check_schema_drift.classify("cccc3333", "cccc3333", REAL_REVISIONS, [])
    assert state == check_schema_drift.AT_HEAD


# --- against a real database ----------------------------------------------


def test_an_empty_database_passes_and_says_so(migration_engine, capsys):
    assert check_schema_drift.main(["--label", "test"]) == 0
    assert check_schema_drift.EMPTY in capsys.readouterr().out


def test_a_fully_migrated_database_passes(migration_engine, capsys):
    command.upgrade(check_schema_drift.alembic_config(), "head")

    assert check_schema_drift.main(["--label", "test"]) == 0
    output = capsys.readouterr().out
    assert check_schema_drift.AT_HEAD in output
    assert "No difference between the models and the live schema." in output


def test_a_hand_edited_schema_at_head_fails(migration_engine, capsys):
    """The case the whole script is for.

    Every revision has been applied, so nothing is pending and nothing is
    unknown - and the schema still is not what the models describe, because
    somebody added a column outside a migration. Adding one rather than
    dropping one keeps the fixture's teardown honest and models the likelier
    accident: a column added in the Supabase dashboard to unblock something.
    """
    command.upgrade(check_schema_drift.alembic_config(), "head")
    with migration_engine.begin() as connection:
        connection.execute(sqlalchemy.text("alter table profiles add column added_in_the_dashboard text"))

    assert check_schema_drift.main(["--label", "test"]) == 1
    output = capsys.readouterr().out
    assert check_schema_drift.AT_HEAD in output
    assert "changed by something other than a migration" in output


def test_a_partially_migrated_database_passes_and_names_what_is_pending(migration_engine, capsys):
    """Reads the real revision chain rather than hard-coding one, so adding a
    migration does not quietly turn this into a test of nothing."""
    config = check_schema_drift.alembic_config()
    revisions = list(check_schema_drift.ScriptDirectory.from_config(config).walk_revisions())
    if len(revisions) < 2:
        pytest.skip("Needs at least two revisions for one to be behind the other.")
    second_to_last = revisions[1].revision

    command.upgrade(config, second_to_last)

    assert check_schema_drift.main(["--label", "test"]) == 0
    output = capsys.readouterr().out
    assert check_schema_drift.BEHIND in output
    assert revisions[0].revision in output, "The head revision is named, so the log says what is not applied yet."


def test_a_database_at_an_unknown_revision_fails_the_run(migration_engine, monkeypatch, capsys):
    """The UNKNOWN branch end to end, not just through `classify`.

    Reaching it with a real database would mean writing a revision id into
    `alembic_version` that no file here declares - which is the corrupt state
    this is meant to detect, not a fixture worth building. Stubbing the read
    is the honest way to exercise the exit code that follows it.
    """
    command.upgrade(check_schema_drift.alembic_config(), "head")
    monkeypatch.setattr(check_schema_drift, "read_current_revision", lambda _url: "from_another_branch")

    assert check_schema_drift.main(["--label", "test"]) == 1
    assert check_schema_drift.UNKNOWN in capsys.readouterr().out


def test_an_unreachable_database_is_a_broken_check_not_a_verdict(monkeypatch, capsys):
    """Exit 2, distinct from the 1 that means the schema is wrong.

    A network blip read as drift would send somebody looking for a dashboard
    edit that never happened, and - worse - a real drift signal that only ever
    appears as "the check failed" is one that gets rerun rather than
    investigated.
    """

    def unreachable(_url):
        raise sqlalchemy.exc.OperationalError("select 1", {}, Exception("connection refused"))

    monkeypatch.setattr(check_schema_drift, "read_current_revision", unreachable)

    assert check_schema_drift.main(["--label", "test"]) == 2
    assert "Could not read test's current revision" in capsys.readouterr().out
