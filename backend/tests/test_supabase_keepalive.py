"""Tests for supabase_keepalive.py, the weekly anti-pause job.

The script runs once a week, unattended, against a live project - which is the
worst combination there is for correctness. Nobody reads a green run, and the
one run anybody ever reads is the one after the pause email arrived, by which
point it is too late for it to have been worth reading.

So the judgement is all in `classify`, and this exercises every branch of it
without a network. Two of them are the ones that matter:

- A permission error has to count as *success*. It is what the project returns
  when the anon role was never granted these tables, and the whole premise of
  the job is that Postgres refusing a query still ran it.
- A `PGRST2xx` has to count as *failure*, even though it looks like the same
  kind of "no" - PostgREST answers that from its own schema cache and Postgres
  never hears about it, so a run made entirely of those keeps nothing awake
  while reporting that it did.

The last test is the one with a long future: it fails when a model is added
without being added to the sweep, the same way test_migration_rls.py fails
when one is added without an RLS revision.
"""

import supabase_keepalive as keepalive
from app.db.base import Base


def _report():
    return keepalive.Report()


# --- What a single answer proves ------------------------------------------


def test_an_empty_array_is_the_expected_answer_and_counts_as_activity():
    outcome, message = keepalive.classify("reports", 200, "[]")

    assert outcome == keepalive.REACHED
    assert "RLS held" in message


def test_a_permission_error_also_counts_as_activity():
    # The branch a naive implementation gets wrong. Postgres raised 42501,
    # which means Postgres ran the query - the job worked.
    body = '{"code":"42501","details":null,"hint":null,"message":"permission denied for table reports"}'

    outcome, message = keepalive.classify("reports", 401, body)

    assert outcome == keepalive.REACHED
    assert "42501" in message


def test_rows_coming_back_is_a_failure_rather_than_a_healthy_keepalive():
    # RLS is off. The project is awake, so the keepalive half succeeded, and
    # that is exactly why this must not be allowed to report success.
    outcome, message = keepalive.classify("reports", 200, '[{"id":1}]')

    assert outcome == keepalive.EXPOSED
    assert "LAUNCH_CHECKLIST.md 5a" in message


def test_the_rows_themselves_are_never_quoted_into_the_log():
    # This runs in a public Actions log, and the rows in the bad case are live
    # `reports` and `profiles`. The count is the alarm; the contents are not.
    outcome, message = keepalive.classify("profiles", 200, '[{"id":1,"display_name":"Ada","email":"ada@example.com"}]')

    assert outcome == keepalive.EXPOSED
    assert "ada@example.com" not in message
    assert "Ada" not in message


def test_a_table_postgrest_does_not_know_did_not_reach_the_database():
    # Looks like a refusal and is not one: PostgREST answered from its schema
    # cache, so this bought the project no activity at all.
    body = '{"code":"PGRST205","message":"Could not find the table \'public.reports\' in the schema cache"}'

    outcome, message = keepalive.classify("reports", 404, body)

    assert outcome == keepalive.MISSING
    assert "nothing reached Postgres" in message


def test_a_paused_or_misaddressed_project_is_unreachable():
    outcome, message = keepalive.classify("reports", 503, "")

    assert outcome == keepalive.UNREACHABLE
    assert "paused" in message


def test_a_connection_failure_is_unreachable_rather_than_a_crash():
    outcome, _ = keepalive.classify("reports", 0, "[Errno -2] Name or service not known")

    assert outcome == keepalive.UNREACHABLE


def test_a_200_that_is_not_a_postgrest_result_is_not_taken_as_success():
    # A captive portal, a proxy error page, an edge putting HTML in front of
    # the project - none of that is Postgres having run anything.
    outcome, _ = keepalive.classify("reports", 200, "<html>Service temporarily unavailable</html>")

    assert outcome == keepalive.UNREACHABLE


# --- What a whole sweep concludes -----------------------------------------


def _sweep_answering(monkeypatch, answers):
    """Run a sweep against a canned answer per table, with no network."""
    calls = []

    def fake_read(url, api_key):
        calls.append(url)
        return answers[len(calls) - 1]

    monkeypatch.setattr(keepalive, "_read", fake_read)
    report = _report()
    outcomes = keepalive.sweep("https://project.supabase.co", "key", report, tables=("reports", "profiles"))
    return outcomes, report, calls


def test_a_sweep_asks_for_one_row_from_each_table(monkeypatch):
    _, _, calls = _sweep_answering(monkeypatch, [(200, "[]"), (200, "[]")])

    assert calls == [
        "https://project.supabase.co/rest/v1/reports?select=*&limit=1",
        "https://project.supabase.co/rest/v1/profiles?select=*&limit=1",
    ]


def test_one_table_failing_does_not_fail_the_sweep(monkeypatch):
    # Deliberate: the sweep is its own redundancy. A single timeout on a job
    # that runs weekly should not page anybody when six other reads landed.
    outcomes, report, _ = _sweep_answering(monkeypatch, [(0, "timed out"), (200, "[]")])

    assert outcomes == [keepalive.UNREACHABLE, keepalive.REACHED]
    assert not report.failed


def test_an_exposed_table_fails_the_sweep_even_though_the_project_is_awake(monkeypatch):
    outcomes, report, _ = _sweep_answering(monkeypatch, [(200, '[{"id":1}]'), (200, "[]")])

    assert outcomes == [keepalive.EXPOSED, keepalive.REACHED]
    assert report.failed


# --- What the run as a whole concludes ------------------------------------


def _run(monkeypatch, answers, url="https://project.supabase.co", key="anon-key"):
    monkeypatch.setenv("SUPABASE_URL", url)
    monkeypatch.setenv("SUPABASE_ANON_KEY", key)
    answers = list(answers)
    monkeypatch.setattr(keepalive, "_read", lambda u, k: answers.pop(0))
    return keepalive.main()


def test_a_run_where_every_table_answered_succeeds(monkeypatch):
    assert _run(monkeypatch, [(200, "[]")] * len(keepalive.KEEPALIVE_TABLES)) == 0


def test_a_run_where_nothing_reached_postgres_fails(monkeypatch):
    # The failure the job exists to report. Every table said "no" in a way that
    # never touched the database, so the week's activity is still zero - and a
    # green run here would be the single most misleading thing this could do.
    body = '{"code":"PGRST205","message":"Could not find the table in the schema cache"}'

    assert _run(monkeypatch, [(404, body)] * len(keepalive.KEEPALIVE_TABLES)) == 1


def test_a_run_with_no_settings_configured_fails_before_asking_the_network(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_ANON_KEY", raising=False)
    monkeypatch.setattr(keepalive, "_read", _refuse_the_network)

    assert keepalive.main() == 1


def _refuse_the_network(url, api_key):  # pragma: no cover - reached only if main() misbehaves
    raise AssertionError("main() reached the network without a URL or a key")


def test_a_trailing_slash_on_the_url_does_not_produce_a_double_slash(monkeypatch):
    seen = []
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co/")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key")
    monkeypatch.setattr(keepalive, "_read", lambda u, k: (seen.append(u), (200, "[]"))[1])

    keepalive.main()

    assert all("//rest" not in url for url in seen)


# --- What stops the sweep going stale -------------------------------------


def test_the_sweep_covers_every_table_the_schema_creates():
    # KEEPALIVE_TABLES is duplicated rather than imported so the script stays
    # stdlib-only and installs nothing. That is a reasonable trade only while
    # something guarantees the copy is honest, and this is that something -
    # the same guarantee test_migration_rls.py gives the RLS revision.
    #
    # A table missing from here is not a broken keepalive; it is a table whose
    # exposure to the anon key nothing checks.
    # Plus alembic's own version table, which Base.metadata cannot know
    # about: e5b2f7c1a903 locked it, and the sweep is what notices if that
    # lock ever comes undone (#658).
    assert set(keepalive.KEEPALIVE_TABLES) == set(Base.metadata.tables) | {"alembic_version"}
