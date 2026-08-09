"""Publish verified closures as a static artifact, so reading one needs no server.

[features/CONDITIONS_DELIVERY.md](../features/CONDITIONS_DELIVERY.md) is the
design and the reasoning; this is step 1 of its order of work. The short
version: `moderation_status == verified` is already the public/private line,
`GET /closures` already needs no account, and public read-mostly data is the
shape this pipeline already serves as static bytes with free egress. Serving
it from a running container makes the safety read path depend on the single
most fragile component in the system.

Closures only, deliberately. Reports are step 3 of that document's ordering,
and they carry a different predicate (`status` + `visibility`, not
`moderation_status`) which is worth landing on its own.

WHY THIS LIVES IN THE PIPELINE AND NOT THE BACKEND

The artifact's field list is a published contract: a key in this bucket is a
URL deployed clients already request, and `lib/r2_keys.py` exists because such
a key can never be renamed. Owning the shape here, next to the other exports
and the layout rules, keeps it from drifting with the ORM. The cost is this
file's one dependency the rest of the pipeline does not share - psycopg,
added to requirements.in for this script alone.

THE SHAPE MATCHES `ClosureOut` EXACTLY, AND THAT IS THE POINT

The client reads this artifact as a baseline and then, when it can reach the
backend, overlays a live `GET /closures` on top. Those two have to be the same
shape or the overlay is a conversion. So the column list below tracks
`backend/app/schemas/closure.py`, including `moderation_status` even though
every row here is verified by construction, and timestamps are stamped `...Z`
the way `app/core/time.py`'s `_stamp_utc` stamps them - a naive timestamp is
read as *local* by `new Date()`, which would move "Closed since August 1" by
the reader's offset.

`reported_by` and `verified_by` are absent because they are absent from
`ClosureOut` too (#430). The reader role is not granted `profiles` at all, so
this script could not resolve a person even if a future edit tried to.

THE FAILURE MODE THIS FILE IS MOSTLY ABOUT

Row-level security is on for every table, with no policies, and the backend is
unaffected only because it connects as the owner. The reader role is not the
owner, so `GRANT SELECT` alone returns **zero rows rather than an error**.
Published unchecked, that is an empty closures artifact, a client that treats
it as a valid baseline, and hikers shown no closure warnings - a permissions
mistake wearing the costume of "no closures exist".

`assert_reader_permissions` is what makes zero trustworthy. It asks the
catalog whether the grant and the policy are actually in place, and refuses to
write anything if they are not. After it passes, an empty result is a real
answer about the trail.

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
OUT_PATH = OUT_DIR / "closures.json"
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

# Which of the columns above are timestamps, and so need stamping on the way
# out. Listed rather than detected, so adding a column is a decision about its
# wire form rather than something type inference makes quietly.
TIMESTAMP_FIELDS = ("reported_at", "verified_at", "closed_since", "expected_reopen")


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


# The catalog questions `assert_reader_permissions` asks. Separated from the
# decision they feed so the decision can be tested without a second database
# role - the local Postgres role deliberately has no CREATEROLE, matching
# production's, so a test cannot mint a reader to be refused as.
MAY_SELECT_SQL = "SELECT has_table_privilege(current_user, 'public.closures', 'SELECT')"

# `pg_policies.roles` is a name[] of the roles a policy is FOR. A policy
# granted to PUBLIC lands as {public}, which covers this role too, so both
# spellings count as configured.
POLICY_COUNT_SQL = """
    SELECT count(*)
      FROM pg_policies
     WHERE schemaname = 'public'
       AND tablename = 'closures'
       AND (current_user = ANY(roles) OR 'public' = ANY(roles))
"""

# Whether RLS is on at all. Off means the grant alone is sufficient and no
# policy is needed - which is the local-development and CI case, where the
# suite owns its own table and never turns RLS on.
RLS_ENABLED_SQL = "SELECT relrowsecurity FROM pg_class WHERE oid = 'public.closures'::regclass"


def permission_problem(may_select: bool, rls_enabled: bool, policies: int) -> str | None:
    """The decision, as a pure function. Returns the reason to stop, or None.

    Two failures, because they fail differently and the fixes are different
    lines of SQL: the GRANT decides whether the table is addressable at all,
    and the POLICY decides whether RLS lets any row through. Both present as
    an empty result set rather than an error, which is the whole reason this
    exists - see the module docstring.
    """
    if not may_select:
        return (
            f"{READER_ROLE} has no SELECT on public.closures, so this would publish nothing. "
            "GRANT SELECT ON public.closures TO the reader role - see features/CONDITIONS_DELIVERY.md."
        )
    if rls_enabled and not policies:
        return (
            f"public.closures has row-level security on and no policy {READER_ROLE} can read through, "
            "so every query would return zero rows and this would publish an empty artifact. "
            "CREATE POLICY ... FOR SELECT ... USING (moderation_status = 'verified') - "
            "see features/CONDITIONS_DELIVERY.md."
        )
    return None


def assert_reader_permissions(conn) -> None:
    """Refuse to run unless the reader can actually see verified closures.

    Without this, a missing policy publishes an empty artifact instead of
    failing, and empty is indistinguishable from a quiet trail.
    """
    with conn.cursor() as cur:
        cur.execute(MAY_SELECT_SQL)
        (may_select,) = cur.fetchone()
        cur.execute(RLS_ENABLED_SQL)
        (rls_enabled,) = cur.fetchone()
        cur.execute(POLICY_COUNT_SQL)
        (policies,) = cur.fetchone()

    problem = permission_problem(bool(may_select), bool(rls_enabled), int(policies))
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


def read_closures(conn) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute(PUBLIC_CLOSURES_SQL)
        columns = [description.name for description in cur.description]
        rows = [dict(zip(columns, row)) for row in cur.fetchall()]

    for row in rows:
        for field in TIMESTAMP_FIELDS:
            row[field] = _stamp_utc(row[field])
    return rows


def build_document(closures: list[dict], generated_at: datetime) -> dict:
    """Wrap the rows with the one fact the rows cannot carry.

    `generated_at` is not decoration. The client renders it as "as of <date>",
    which is what makes a day-old baseline honest rather than misleading
    (OurHikeValues.md #4), and it is also the only thing that would reveal a
    bake job that silently stopped running - the artifact would age visibly
    instead of looking current forever.
    """
    return {
        "generated_at": _stamp_utc(generated_at),
        "closures": closures,
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
        assert_reader_permissions(conn)
        closures = read_closures(conn)

    document = build_document(closures, datetime.now(timezone.utc))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(document, indent=2) + "\n")

    manifest = {
        "path": str(OUT_PATH),
        "sha256": sha256_file(OUT_PATH),
        "count": len(closures),
        "generated_at": document["generated_at"],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"Wrote {len(closures)} verified closure(s) to {OUT_PATH}.")
    return manifest


if __name__ == "__main__":
    main()
