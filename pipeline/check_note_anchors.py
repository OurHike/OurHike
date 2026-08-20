"""Diff published POI ids against published field-note anchors; report orphans.

[features/FIELD_NOTES.md](../features/FIELD_NOTES.md) §7's check, built
([#878](https://github.com/OurHike/OurHike/issues/878)). Notes anchor on
`poi_id` — the deterministic id `lib/poi_schema.py` promises stays stable
across runs on unchanged input. Two things break the promise: ATC deleting
and re-creating a feature (re-minting its GlobalID), and a feature falling
onto `lib/feature_id.py`'s positional `generated-{index}` fallback. Under
POI_IDENTITY.md's ledger neither is silent any more — a re-key carries the
id forward and a removal retires into a published tombstone — so this check
is a backstop **expected to find nothing**, kept because it is what proves
that, and because it is the recovery path for anything written before the
ledger existed.

OVER PUBLISHED ARTIFACTS, NOT THE DATABASE — a decision, recorded on #878.

`conditions/notes.json` already carries every visible note's `poi_id` (its
5-per-POI cap keeps each distinct anchor), and `latest.json` names every
published `poi_*.geojson` — so both sides of the diff are public HTTPS
reads of what a hiker's phone reads, in `smoke_published.py`'s posture: no
credential, structurally incapable of changing anything. The alternative is
a new scheduled road into the Supabase project, which the roster in
`test_supabase_keepalive_workflow.py` exists to resist.

The trade, stated rather than buried: the published artifact is windowed
(90 days, 5 per POI, `hidden_at IS NULL` — `export_conditions.py` owns
those numbers), so this check sees exactly the anchors a hiker can
currently see. A hidden or older note's orphaning goes undetected until it
republishes. Acceptable because anchors are never deleted — every note
keeps its `lat`/`lon`, so an orphan caught late is re-anchorable exactly as
one caught early — and full coverage is the ledger's job, not this
backstop's.

`volunteer_hours.work_project_id` is the same shape one resource over and
is deliberately NOT covered here: hours are private and never published,
and the conditions reader role is not granted private tables (the #430
posture). #878 records the reasoning; the club queue surface (#877) reads
those rows anyway and is where that half belongs.

WHAT AN ORPHAN REPORT SAYS, PER ORPHAN

`retired_poi.geojson` publishes the ledger's tombstones with their
`superseded_by`, so an orphaned anchor sorts into three dispositions:

  - superseded — the ledger knows the successor; re-anchoring is mechanical.
  - retired    — the place is gone and the ledger says so; the note stands
                 as history at its own coordinates.
  - unknown    — no live id, no tombstone. The real alarm: a pre-ledger
                 break, or an id the ledger never minted.

Only `unknown` counts against health. And one refusal on the way to that
verdict: if every distinct anchor is orphaned at once, the likeliest truth
is that the id scheme itself moved — a renamed property, a re-keyed export
— and a report listing hundreds of orphans would be confidently wrong about
each of them. That case is reported as a single failure of the join instead
(the #446 class: never let a check's output outrun what it actually knows).

    python check_note_anchors.py --base https://data.example.org
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import requests

from lib.freshness_state import utc_today
from smoke_published import HTTP_TIMEOUT, fetch_manifest

# The published keys this check joins, spelled once. NOTES_KEY pairs with
# PUBLISHED_NOTES_KEY in client/src/lib/publishedConditions.ts — the check
# reads the same object a phone reads, which is the point.
NOTES_KEY = "conditions/notes.json"
RETIRED_KEY = "retired_poi.geojson"
POI_KEY_PATTERN = re.compile(r"^poi_[a-z0-9_]+\.geojson$")

# When every distinct anchor is orphaned at once, past this many, the verdict
# is "the join is broken" rather than a per-anchor list. Ten is small enough
# that a real mass-orphaning event (an ATC refresh before the ledger) still
# reports properly at nine, and large enough that a handful of genuinely
# broken anchors never trips it.
SUSPICIOUS_ORPHAN_FLOOR = 10

OK = "ok"
FAILED = "failed"
UNREACHABLE = "unreachable"


def _fetch_json(base: str, key: str, session=None) -> tuple[dict | None, str | None]:
    """The object behind `key` as parsed JSON, or (None, why-not).

    requests decodes `Content-Encoding: gzip` before json() sees a byte,
    which matches how the client reads these artifacts (they are stored
    gzipped on purpose since #717).
    """
    getter = (session or requests).get
    try:
        response = getter(f"{base}/{key}", timeout=HTTP_TIMEOUT)
    except requests.RequestException as error:
        return None, f"could not be fetched: {error}"
    if response.status_code != 200:
        return None, f"answered {response.status_code}"
    try:
        return response.json(), None
    except ValueError as error:
        return None, f"is not JSON: {error}"


def published_poi_ids(base: str, manifest: dict, session=None) -> tuple[set[str], list[dict]]:
    """Every id the current release publishes, from every poi_*.geojson the
    manifest names — never a hardcoded list, for smoke_published.py's reason:
    a new poi_type is covered the day it publishes.

    A file whose features carry no `id` property is a FAILURE, not an empty
    set: the id column renamed out from under this check would otherwise read
    as every anchor orphaning simultaneously (#446's shape).
    """
    ids: set[str] = set()
    problems: list[dict] = []
    keys = sorted(k for k in (manifest.get("artifacts") or {}) if POI_KEY_PATTERN.match(k))
    if not keys:
        problems.append(
            {
                "key": "latest.json",
                "state": FAILED,
                "detail": "the manifest names no poi_*.geojson artifacts, so there are no published ids to check against",
            }
        )
        return ids, problems
    for key in keys:
        document, why_not = _fetch_json(base, key, session)
        if document is None:
            problems.append({"key": key, "state": UNREACHABLE, "detail": why_not})
            continue
        features = document.get("features") or []
        file_ids = {feature.get("properties", {}).get("id") for feature in features if feature.get("properties", {}).get("id")}
        if features and not file_ids:
            problems.append(
                {
                    "key": key,
                    "state": FAILED,
                    "detail": f"{len(features)} feature(s) and none carries a properties.id — the id join this check relies on is broken",
                }
            )
            continue
        ids.update(file_ids)
    return ids, problems


def retired_dispositions(base: str, manifest: dict, session=None) -> dict[str, str | None]:
    """Tombstoned id → its `superseded_by` (None where the place simply
    ended), or an empty map when the artifact is absent or unreadable.

    Absent is tolerated rather than failed: the tombstone artifact postdates
    the notes feature, and a bucket without it just means every orphan reports
    as `unknown` — a louder answer, never a wrong one.
    """
    if RETIRED_KEY not in (manifest.get("artifacts") or {}):
        return {}
    document, _ = _fetch_json(base, RETIRED_KEY, session)
    if document is None:
        return {}
    return {
        feature["properties"]["id"]: feature["properties"].get("superseded_by")
        for feature in document.get("features") or []
        if feature.get("properties", {}).get("id")
    }


def anchor_rows(notes_document: dict) -> dict[str, dict]:
    """Distinct `poi_id` → the facts the report needs: how many visible notes
    hang on it, the most recent `observed_at`, and the coordinates that
    re-anchor it. Notes with no `poi_id` are pin-drops anchored by
    coordinates alone, by design — nothing to orphan."""
    anchors: dict[str, dict] = {}
    for row in notes_document.get("notes") or []:
        poi_id = row.get("poi_id")
        if not poi_id:
            continue
        entry = anchors.setdefault(poi_id, {"notes": 0, "latest_observed_at": "", "lat": None, "lon": None, "mile": None})
        entry["notes"] += 1
        observed = row.get("observed_at") or ""
        if observed >= entry["latest_observed_at"]:
            entry["latest_observed_at"] = observed
            entry["lat"], entry["lon"], entry["mile"] = row.get("lat"), row.get("lon"), row.get("mile")
    return anchors


def check_anchors(base: str, session=None) -> dict | None:
    """The whole verdict, or None when there is no manifest to check against."""
    manifest = fetch_manifest(base, session)
    if manifest is None:
        return None

    problems: list[dict] = []
    notes_document, why_not = _fetch_json(base, NOTES_KEY, session)
    if notes_document is None:
        # No notes artifact is not "no orphans" — it is "nothing could be
        # checked", reported as such so a conditions-publish outage cannot
        # read as anchor health.
        problems.append({"key": NOTES_KEY, "state": UNREACHABLE, "detail": why_not})
        anchors = {}
    else:
        anchors = anchor_rows(notes_document)

    ids, poi_problems = published_poi_ids(base, manifest, session)
    problems.extend(poi_problems)

    tombstones = retired_dispositions(base, manifest, session)

    # Per-anchor claims are made only over a COMPLETE id set. A poi file that
    # did not answer, or answered without ids, may be exactly the file an
    # anchor lives in — naming that anchor an orphan would be the check
    # saying more than it read. The problem entries above are the whole
    # verdict for such a run: unhealthy, with the artifact named, and no
    # anchor accused on partial evidence.
    orphaned = {poi_id: entry for poi_id, entry in anchors.items() if poi_id not in ids} if not poi_problems else {}

    # The join-is-broken refusal (module docstring): ids were all readable and
    # every anchor is missing from them anyway.
    join_broken = bool(anchors) and ids and len(orphaned) == len(anchors) and len(orphaned) >= SUSPICIOUS_ORPHAN_FLOOR
    if join_broken:
        problems.append(
            {
                "key": NOTES_KEY,
                "state": FAILED,
                "detail": f"every one of {len(anchors)} distinct anchors is missing from {len(ids)} published ids — "
                "that is the shape of a renamed id scheme, not of mass orphaning, so no per-anchor report is made",
            }
        )
        orphaned = {}

    orphans = []
    for poi_id in sorted(orphaned):
        entry = orphaned[poi_id]
        if poi_id in tombstones:
            successor = tombstones[poi_id]
            disposition = "superseded" if successor else "retired"
        else:
            successor = None
            disposition = "unknown"
        orphans.append(
            {
                "poi_id": poi_id,
                "disposition": disposition,
                "superseded_by": successor,
                **entry,
            }
        )

    unknown = [orphan for orphan in orphans if orphan["disposition"] == "unknown"]
    failed = [p for p in problems if p["state"] == FAILED]
    unreachable = [p for p in problems if p["state"] == UNREACHABLE]

    return {
        "checked_at": utc_today().isoformat(),
        "base": base,
        "published_ids": len(ids),
        "anchored_pois": len(anchors),
        "orphans": orphans,
        "unknown_orphans": len(unknown),
        "failed": failed,
        "unreachable": unreachable,
        # The workflow's `healthy`, computed here so the two cannot drift:
        # nothing unknown, nothing failed, nothing unreachable. A superseded
        # or retired orphan is the ledger working, not an alarm.
        "healthy": not unknown and not failed and not unreachable,
    }


def render(verdict: dict) -> str:
    lines = [
        f"{verdict['anchored_pois']} anchored POI(s) among the published notes, "
        f"{verdict['published_ids']} published id(s), {len(verdict['orphans'])} orphan(s) "
        f"({verdict['unknown_orphans']} unknown to the ledger).",
    ]
    for orphan in verdict["orphans"]:
        where = f"({orphan['lat']}, {orphan['lon']}, mile {orphan['mile']})"
        succession = f" -> {orphan['superseded_by']}" if orphan["superseded_by"] else ""
        lines.append(
            f"  {orphan['disposition']:>10}  {orphan['poi_id']}{succession}  "
            f"{orphan['notes']} note(s), latest {orphan['latest_observed_at']}, re-anchorable at {where}"
        )
    for problem in verdict["failed"] + verdict["unreachable"]:
        lines.append(f"  {problem['state']:>10}  {problem['key']}: {problem['detail']}")
    lines.append("healthy" if verdict["healthy"] else "NOT healthy")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--base", required=True, help="Bucket base URL, e.g. https://data.example.org")
    parser.add_argument("--json", type=Path, help="Also write the verdict as JSON here")
    parser.add_argument(
        "--exit-zero",
        action="store_true",
        help="Exit 0 on an unhealthy verdict; reserves 2 for nothing-published and other codes for crashes",
    )
    args = parser.parse_args(argv)

    verdict = check_anchors(args.base.rstrip("/"))
    if verdict is None:
        print(f"No {json.dumps('latest.json')} at {args.base} — nothing is published to check.")
        return 2

    print(render(verdict))
    if args.json:
        args.json.write_text(json.dumps(verdict, indent=2) + "\n")
    if args.exit_zero:
        return 0
    return 0 if verdict["healthy"] else 1


if __name__ == "__main__":
    sys.exit(main())
