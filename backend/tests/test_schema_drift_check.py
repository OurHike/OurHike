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

import pytest
import sqlalchemy

import check_schema_drift
from alembic import command
from app.config import settings
from tests.conftest import _reset_schema

REAL_REVISIONS = {"aaaa1111", "bbbb2222", "cccc3333"}


@pytest.fixture()
def migration_engine():
    engine = sqlalchemy.create_engine(settings.database_url)
    _reset_schema(engine)
    try:
        yield engine
    finally:
        _reset_schema(engine)
        engine.dispose()


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
