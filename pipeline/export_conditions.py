"""Publish verified closures and reports as static artifacts, needing no server.

[features/CONDITIONS_DELIVERY.md](../features/CONDITIONS_DELIVERY.md) is the
design and the reasoning; this covers steps 1 and 3 of its order of work. The
short version: the moderation gate is already the public/private line,
`GET /closures` and `GET /reports` already need no account, and public
read-mostly data is the shape this pipeline already serves as static bytes
with free egress. Serving it from a running container makes the safety read
path depend on the single most fragile component in the system.

Two artifacts, two predicates, and the difference is the whole risk (#436):

    conditions/closures.json   moderation_status = 'verified'
    conditions/reports.json    status IN ('verified', 'resolved')
                               AND visibility = 'public'

Reports gate on two columns because two different things are being decided.
`status` mirrors `_MODERATED_STATUSES` in `backend/app/routers/reports.py` -
`resolved` stays public deliberately, because a blowdown someone has since
cleared reads as "Fixed" and is information rather than noise, while
`submitted` must not leak or verification stops being a gate. `visibility`
excludes the two audiences that are not hikers: `internal_only` is where
`bad_hikers` reports go - the one type that reports on *people* - and
`club_only` is `thanks`. A key in this bucket cannot be renamed, only
abandoned in place and served forever, so publishing either would be
irreversible.

WHY THIS LIVES IN THE PIPELINE AND NOT THE BACKEND

The artifact's field list is a published contract: a key in this bucket is a
URL deployed clients already request, and `lib/r2_keys.py` exists because such
a key can never be renamed. Owning the shape here, next to the other exports
and the layout rules, keeps it from drifting with the ORM. The cost is this
file's one dependency the rest of the pipeline does not share - psycopg,
added to requirements.in for this script alone.

THE SHAPES MATCH THE ANONYMOUS API RESPONSES, AND THAT IS THE POINT

The client reads these artifacts as a baseline and then, when it can reach the
backend, overlays the live endpoints on top. Those two have to be the same
shape or the overlay is a conversion. So the closures column list tracks
`backend/app/schemas/closure.py`, and the reports one tracks what
`ReportOut.for_viewer` sends an anonymous caller - which is why it has no
`reporter_id`, `received_at`, `maintainer_id` or `club_id`: those are withheld
from anonymous responses (#252), so the baseline never holds them at all
rather than holding them as nulls. `verified_by`/`verified_at` are absent from
the public report schema entirely, and the reader role is not granted
`profiles`, so this script could not resolve a person even if a future edit
tried to (#430).

`photo_url` is deliberately absent from the reports artifact, and that is a
decision rather than an omission (#436). The live endpoint answers it with a
short-lived presigned URL against a private bucket; a baked artifact is
rewritten daily, so a published signature would be broken by the time it was
read, and a long-lived one would defeat the private bucket. The live tier
supplies photos; the baseline supplies the warning.

Timestamps are stamped `...Z` the way `app/core/time.py`'s `_stamp_utc`
stamps them - a naive timestamp is read as *local* by `new Date()`, which
would move "Closed since August 1" by the reader's offset.

THE FAILURE MODE THIS FILE IS MOSTLY ABOUT

Row-level security is on for every table, with no policies, and the backend is
unaffected only because it connects as the owner. The reader role is not the
owner, so `GRANT SELECT` alone returns **zero rows rather than an error**.
Published unchecked, that is an empty artifact, a client that treats it as a
valid baseline, and hikers shown no warnings - a permissions mistake wearing
the costume of "nothing to report".

`assert_reader_permissions` is what makes zero trustworthy. It asks the
catalog whether the grant and the policy are actually in place - for each
table, before anything is written, so a half-configured database publishes
nothing rather than one artifact of two. After it passes, an empty result is
a real answer about the trail.

    CONDITIONS_DATABASE_URL=postgresql://... python export_conditions.py
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "data" / "processed" / "conditions"
CLOSURES_OUT_PATH = OUT_DIR / "closures.json"
REPORTS_OUT_PATH = OUT_DIR / "reports.json"
MANIFEST_PATH = ROOT / "data" / "processed" / "conditions_manifest.json"

URL_ENV_VAR = "CONDITIONS_DATABASE_URL"

# The role the workflow connects as. Named here because the permission check
# below reports it by name, and a message naming the role is the difference
# between a five-minute fix and a hunt through Supabase's UI.
READER_ROLE = "ourhike_conditions_reader"

# Mirrors the RLS policy rather than replacing it. The database is the thing
# that actually enforces this - a policy the reader cannot see past - and
# repeating it here means a reader of this file does not have to go and look
# up what the role is allowed to see. If the two ever disagree, the policy
# wins, silently and correctly, by returning fewer rows.
PUBLIC_CLOSURES_SQL = """
    SELECT id,
           reported_at,
           trail_id,
           start_mile_marker,
           end_mile_marker,
           reason_type,
           note,
           status,
           moderation_status,
           verified_at,
           closed_since,
           expected_reopen,
           reroute_url
      FROM public.closures
     WHERE moderation_status = 'verified'
     ORDER BY start_mile_marker, id
"""

# Same stance for reports, with the two-column predicate the module docstring
# walks through. `"timestamp"` is quoted because it is also a type name and
# this is the one place a bare spelling could ever read as one. Ordered by
# authoring time then id so the bytes are deterministic - publish.py diffs
# sha256 per artifact, and a day with no report changes must upload nothing.
PUBLIC_REPORTS_SQL = """
    SELECT id,
           type,
           poi_id,
           lat,
           lon,
           mile,
           reporter_type,
           "timestamp",
           note,
           follow_up,
           status,
           visibility,
           severity
      FROM public.reports
     WHERE status IN ('verified', 'resolved')
       AND visibility = 'public'
     ORDER BY "timestamp", id
"""

# Which of the columns above are timestamps, and so need stamping on the way
# out. Listed rather than detected, so adding a column is a decision about its
# wire form rather than something type inference makes quietly.
CLOSURE_TIMESTAMP_FIELDS = ("reported_at", "verified_at", "closed_since", "expected_reopen")
REPORT_TIMESTAMP_FIELDS = ("timestamp",)

# What each table's policy must let through - quoted back at whoever has to
# write the missing CREATE POLICY, so the refusal carries its own fix.
POLICY_PREDICATES = {
    "closures": "moderation_status = 'verified'",
    "reports": "status IN ('verified', 'resolved') AND visibility = 'public'",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def connection_url() -> str:
    """Read the connection string, accepting either spelling of the scheme.

    `UA_MIGRATION_DATABASE_URL` and friends carry `postgresql+psycopg://`
    because SQLAlchemy needs the driver named. Raw psycopg does not understand
    that suffix, and the likeliest way to configure this secret is by copying
    the shape of one that already exists - so both are accepted and normalised
    rather than one of them failing with a parse error about a URL that looks
    right.

    Unlike a migration, this job has no opinion about which pooler: it runs a
    couple of SELECTs and disconnects, so transaction mode's prepared-statement
    problem never arises. Session mode on 5432 is the recommendation only
    because it is the simpler thing to hold in your head.
    """
    url = os.environ.get(URL_ENV_VAR, "").strip()
    if not url:
        raise SystemExit(f"{URL_ENV_VAR} is unset. See features/CONDITIONS_DELIVERY.md for what it needs to be.")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


# The catalog questions `assert_reader_permissions` asks, parameterised by
# table because closures and reports are checked one after the other.
# Separated from the decision they feed so the decision can be tested without
# a second database role - the local Postgres role deliberately has no
# CREATEROLE, matching production's, so a test cannot mint a reader to be
# refused as.
MAY_SELECT_SQL = "SELECT has_table_privilege(current_user, %s, 'SELECT')"

# `pg_policies.roles` is a name[] of the roles a policy is FOR. A policy
# granted to PUBLIC lands as {public}, which covers this role too, so both
# spellings count as configured.
POLICY_COUNT_SQL = """
    SELECT count(*)
      FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = %s
       AND (current_user = ANY(roles) OR 'public' = ANY(roles))
"""

# Whether RLS is on at all. Off means the grant alone is sufficient and no
# policy is needed - which is the local-development and CI case, where the
# suite owns its own table and never turns RLS on.
RLS_ENABLED_SQL = "SELECT relrowsecurity FROM pg_class WHERE oid = %s::regclass"


def permission_problem(table: str, may_select: bool, rls_enabled: bool, policies: int) -> str | None:
    """The decision, as a pure function. Returns the reason to stop, or None.

    Two failures, because they fail differently and the fixes are different
    lines of SQL: the GRANT decides whether the table is addressable at all,
    and the POLICY decides whether RLS lets any row through. Both present as
    an empty result set rather than an error, which is the whole reason this
    exists - see the module docstring.
    """
    if not may_select:
        return (
            f"{READER_ROLE} has no SELECT on public.{table}, so this would publish nothing. "
            f"GRANT SELECT ON public.{table} TO the reader role - see features/CONDITIONS_DELIVERY.md."
        )
    if rls_enabled and not policies:
        return (
            f"public.{table} has row-level security on and no policy {READER_ROLE} can read through, "
            "so every query would return zero rows and this would publish an empty artifact. "
            f"CREATE POLICY ... FOR SELECT ... USING ({POLICY_PREDICATES[table]}) - "
            "see features/CONDITIONS_DELIVERY.md."
        )
    return None


def assert_reader_permissions(conn, table: str) -> None:
    """Refuse to run unless the reader can actually see the table's public rows.

    Without this, a missing policy publishes an empty artifact instead of
    failing, and empty is indistinguishable from a quiet trail.
    """
    with conn.cursor() as cur:
        cur.execute(MAY_SELECT_SQL, (f"public.{table}",))
        (may_select,) = cur.fetchone()
        cur.execute(RLS_ENABLED_SQL, (f"public.{table}",))
        (rls_enabled,) = cur.fetchone()
        cur.execute(POLICY_COUNT_SQL, (table,))
        (policies,) = cur.fetchone()

    problem = permission_problem(table, bool(may_select), bool(rls_enabled), int(policies))
    if problem:
        raise SystemExit(problem)


def _stamp_utc(value: datetime | None) -> str | None:
    """The pipeline's copy of `backend/app/core/time.py`'s stamping.

    Copied rather than imported because nothing here may import the backend,
    and duplicated deliberately rather than approximated: the client parses
    both this artifact and the live endpoint with the same code, so a
    difference of one `Z` is a four-to-five hour error along the trail.
    """
    if value is None:
        return None
    aware = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_rows(conn, sql: str, timestamp_fields: tuple[str, ...]) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(sql)
        columns = [description.name for description in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    for row in rows:
        for field in timestamp_fields:
            row[field] = _stamp_utc(row[field])
    return rows


def read_closures(conn) -> list[dict]:
    return _read_rows(conn, PUBLIC_CLOSURES_SQL, CLOSURE_TIMESTAMP_FIELDS)


def read_reports(conn) -> list[dict]:
    return _read_rows(conn, PUBLIC_REPORTS_SQL, REPORT_TIMESTAMP_FIELDS)


def build_document(key: str, rows: list[dict], generated_at: datetime) -> dict:
    """Wrap the rows with the one fact the rows cannot carry.

    `generated_at` is not decoration. The client renders it as "as of <date>",
    which is what makes a day-old baseline honest rather than misleading
    (OurHikeValues.md #4), and it is also the only thing that would reveal a
    bake job that silently stopped running - the artifact would age visibly
    instead of looking current forever.

    `key` names the payload - "closures" or "reports" - so each document says
    what it holds the way the live endpoints' paths do.
    """
    return {
        "generated_at": _stamp_utc(generated_at),
        key: rows,
    }


def connect():
    """Connect, and turn one confusing failure into an actionable one.

    Supabase's pooler routes on a tenant-qualified username -
    `<role>.<project-ref>` - and rejects a bare role with
    `FATAL: (ENOTFOUND) tenant/user ... not found`. That message reads like
    the role was never created, which sends you back to the SQL to check
    something that is already correct. It is a URL format problem, and the
    first real run of publish-conditions.yml failed on exactly it
    (2026-08-08), so it is worth catching by name rather than documenting and
    hoping.
    """
    try:
        return psycopg.connect(connection_url())
    except psycopg.OperationalError as exc:
        if "tenant" in str(exc).lower() or "ENOTFOUND" in str(exc):
            raise SystemExit(
                f"The database refused the connection with:\n\n{exc}\n\n"
                "This usually means the username is not tenant-qualified. Supabase's pooler wants "
                f"`{READER_ROLE}.<project-ref>`, not the bare role name - the role itself is probably fine. "
                "See features/CONDITIONS_DELIVERY.md."
            ) from exc
        raise


def main() -> dict:
    with connect() as conn:
        # Both tables checked before either read, so a half-configured
        # database - the closures policy applied, the reports one forgotten -
        # publishes nothing rather than one artifact of two. Half a baseline
        # would look exactly like a day with no reports.
        for table in ("closures", "reports"):
            assert_reader_permissions(conn, table)
        closures = read_closures(conn)
        reports = read_reports(conn)

    # One clock for both documents: they came from one read of one database,
    # and two timestamps would invite the client to reason about a skew that
    # does not exist.
    generated_at = datetime.now(timezone.utc)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CLOSURES_OUT_PATH.write_text(json.dumps(build_document("closures", closures, generated_at), indent=2) + "\n")
    REPORTS_OUT_PATH.write_text(json.dumps(build_document("reports", reports, generated_at), indent=2) + "\n")

    manifest = {
        "artifacts": {
            "closures": {
                "path": str(CLOSURES_OUT_PATH),
                "sha256": sha256_file(CLOSURES_OUT_PATH),
                "count": len(closures),
                "generated_at": _stamp_utc(generated_at),
            },
            "reports": {
                "path": str(REPORTS_OUT_PATH),
                "sha256": sha256_file(REPORTS_OUT_PATH),
                "count": len(reports),
                "generated_at": _stamp_utc(generated_at),
            },
        }
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"Wrote {len(closures)} verified closure(s) to {CLOSURES_OUT_PATH}.")
    print(f"Wrote {len(reports)} public report(s) to {REPORTS_OUT_PATH}.")
    return manifest


if __name__ == "__main__":
    main()
