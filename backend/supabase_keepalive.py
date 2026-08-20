"""Keep the free-tier Supabase project awake by giving its database something to do.

Supabase pauses a Free plan project that shows too little activity over a
rolling seven-day window, and the thing it measures is *database* activity:
"a Free plan project is considered inactive if it does not receive sufficient
user database activity over the past week"
(https://supabase.com/docs/guides/platform/free-project-pausing).

That sentence is the whole design constraint, and it rules out the obvious
implementation. Pinging `/auth/v1/settings`, the way check_supabase_config.py
opens, proves the project is up without ever reaching Postgres - GoTrue
answers that from its own configuration, and a keepalive built on it would
report a healthy project every week right up until the pause email arrived.

So this reads tables instead, over PostgREST, with the anon key: the same
request LAUNCH_CHECKLIST.md 5a already tells a maintainer to make by hand, and
safe to make from a public CI log for the same reason it is safe to publish
the key at all. RLS is on with no policies, so anon gets an empty array or a
permission error and never any rows. Both answers are proof that Postgres ran
a query, which is the only thing that counts against the pause.

Which makes the second half free. A request whose expected answer is "no rows,
ever" is an RLS assertion as much as a keepalive - and unlike
tests/test_migration_rls.py, which reads migrations, this one asks the live
project through the front door that is actually exposed to the internet. If a
later migration, policy or default grant ever makes one of these tables
readable with the key that ships in the client bundle, this is what says so.

**How often it needs to run is Supabase's call, not ours.** Their wording is
"a few user requests to the database each day over the previous week" - a
per-day measure, which is what ruled out the weekly job this started as. The
schedule in .github/workflows/supabase-keepalive.yml leaves no more than 20
hours between runs, so every calendar day gets a sweep and a single failed or
late run cannot open a gap that matters. Nothing in this file depends on the
cadence; changing it is a cron expression there and nothing here.

Stdlib only, like check_supabase_config.py, so the workflow installs nothing.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# Its sibling diagnostic's reporter, imported rather than copied. Both scripts
# sit in this directory, both are stdlib-only, and both want the same thing:
# every problem in one run, because each round trip to fix one costs a trip to
# the dashboard.
from check_supabase_config import Report

# Every table the backend's schema puts in `public`, which is every table
# PostgREST serves. Duplicated from app.models rather than imported, so this
# stays a stdlib-only script with nothing to install -
# tests/test_supabase_keepalive.py asserts the copy still matches
# Base.metadata, which is what stops a table added later from quietly falling
# out of the sweep and out of the RLS assertion with it.
#
# All of them rather than one, deliberately. A handful of small reads is closer to
# the "few requests" Supabase describes than a single read is, and the RLS
# half is worth exactly as much as the number of tables it covers.
KEEPALIVE_TABLES: tuple[str, ...] = (
    # alembic_version is not in Base.metadata - alembic owns it - which is
    # exactly how it sat outside both live RLS watchers (#658): this sweep
    # walked the models' tables, and check_schema_drift.py declines RLS by
    # deferring to this sweep. e5b2f7c1a903 locked the table; this is what
    # notices if that lock ever comes undone in a live project.
    "alembic_version",
    # The app-failure inbox (#848). It carries a contact detail somebody gave
    # while shaken, so of every table here it is the one where "readable with
    # the anon key" would be worst.
    "app_failures",
    "clubs",
    "closures",
    # The field-notes pair (features/FIELD_NOTES.md): notes carry a
    # reporter_id beside a position and a date - #252's route-reconstruction
    # pair - so their RLS staying on is worth a read an hour.
    "field_notes",
    "hikes",
    "maintainer_assignments",
    "note_flags",
    "poi_photos",
    "profiles",
    "reports",
    "user_preferences",
    # A volunteer's own logbook (#761), locations and free-text notes - the
    # resource whose whole design is that it is private.
    "volunteer_hours",
)

TIMEOUT_SECONDS = 15

# What one table's answer proved.
REACHED = "reached"  # Postgres ran a query. This is the point of the job.
EXPOSED = "exposed"  # It ran one and handed back rows. RLS is off.
MISSING = "missing"  # PostgREST answered from its schema cache; Postgres never saw it.
UNREACHABLE = "unreachable"  # No usable answer at all.


def _read(url: str, api_key: str) -> tuple[int, str]:
    """One PostgREST GET, reduced to a status and a raw body.

    Deliberately not parsed here: `classify` has to be able to decide what an
    unparseable body means, and it cannot do that if the parse already failed
    somewhere it could not report from.
    """
    request = urllib.request.Request(url, headers={"apikey": api_key, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return 0, str(error)


def classify(table: str, status: int, body: str) -> tuple[str, str]:
    """Decide what a single answer proves, and say it in one line.

    A pure function on purpose - it holds all the judgement in this script,
    and the tests exercise every branch of it without a network.

    **The body is never quoted back for a 200.** If RLS were ever off, these
    rows would be `reports` and `profiles` from a live database, and this runs
    in a public Actions log. The count is enough to raise the alarm; anyone
    who needs the rows can go and look somewhere that is not a log.
    """
    try:
        payload = json.loads(body)
    except ValueError:
        payload = None

    if status == 200:
        if not isinstance(payload, list):
            return UNREACHABLE, f"{table}: 200 with a body PostgREST would not send - something is in front of the project."
        if payload:
            return EXPOSED, (
                f"{table}: readable with the anon key - {len(payload)} row(s) came back where RLS should allow none. "
                "See LAUNCH_CHECKLIST.md 5a; this table is exposed to anyone who opens the app and reads the bundle."
            )
        return REACHED, f"{table}: empty result - RLS held, and Postgres ran the query."

    code = payload.get("code") if isinstance(payload, dict) else None

    # PostgREST stamps its own failures PGRST###; anything else in that field
    # is a Postgres SQLSTATE, which means Postgres is what produced the error
    # and therefore that Postgres did the work this job exists to cause. A
    # permission denial (42501) is the expected shape on a project whose anon
    # role was never granted these tables.
    if isinstance(code, str) and code and not code.startswith("PGRST"):
        return REACHED, f"{table}: refused by Postgres ({code}) - RLS or grants held, and Postgres ran the query."

    if isinstance(code, str) and code.startswith("PGRST2"):
        return MISSING, (
            f"{table}: PostgREST does not know this table ({code}). It answered from its schema cache, so nothing "
            "reached Postgres. Either the table list here has drifted from the project's schema, or the migrations "
            "have not been applied to it."
        )

    if status == 0:
        return UNREACHABLE, f"{table}: no response - {body}"

    return UNREACHABLE, f"{table}: {status}{f' {code}' if code else ''} - the URL or the key is wrong, or the project is paused."


def sweep(url: str, api_key: str, report: Report, tables: tuple[str, ...] = KEEPALIVE_TABLES) -> list[str]:
    """Read every table once, and return what each answer proved."""
    outcomes = []
    for table in tables:
        # limit=1 rather than a full read: one row is all it takes to know RLS
        # is off, and asking for no more than that keeps the answer small even
        # in the case where the answer is the bad news.
        status, body = _read(f"{url}/rest/v1/{table}?select=*&limit=1", api_key)
        outcome, message = classify(table, status, body)
        outcomes.append(outcome)

        if outcome == REACHED:
            report.ok(message)
        elif outcome == EXPOSED:
            report.fail(message)
        else:
            report.warn(message)

    return outcomes


def main() -> int:
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    api_key = os.environ.get("SUPABASE_ANON_KEY") or ""

    report = Report()

    print("Configuration")
    if not url or not api_key:
        report.fail(
            "SUPABASE_URL and SUPABASE_ANON_KEY must both be set as repository variables. Note the names carry no "
            "VITE_ prefix. See LAUNCH_CHECKLIST.md 4.3a."
        )
        return 1
    report.ok(f"Project URL: {url}")

    print(f"\nReading {len(KEEPALIVE_TABLES)} tables over PostgREST")
    outcomes = sweep(url, api_key, report)

    print("\nResult")
    reached = outcomes.count(REACHED)
    if reached:
        report.ok(f"{reached} of {len(outcomes)} tables gave Postgres a query to run. The project has activity for this week.")
    else:
        # The failure worth being loud about: no table reached the database, so
        # nothing here counts against the pause, whatever else the run said.
        report.fail(
            "Not one table reached Postgres, so this run bought the project nothing. Check the messages above - a "
            "project that is already paused, a wrong URL or key, and a schema that was never migrated all land here."
        )

    print("\nFAILED - see above." if report.failed else "\nDone.")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
