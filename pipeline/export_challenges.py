"""Publish the challenges clubs put on their own trails.

#1780 - Let a club publish a challenge - places on its own trails that
hikers opt into and tag at camp - starting with the ATC's A.T. Summer Bucket
List.

features/CHALLENGES.md is the design. A challenge is a list of places on one
organization's trails, a date window, an optional finish line and an
optional reward; a hiker opts in, walks, and tags the places at camp. The
first is the ATC's A.T. Summer Bucket List, transcribed from its 2025 PDF and
published as a labelled draft.

WHERE THE JUDGEMENT IS AND WHERE THE NUMBERS ARE

reference/challenges/<org>/<id>.json is the judgement - which line of a
club's list is which place - one file per challenge, committed so a diff
reviews it row by row. reference/challenges/publishers.json is the scope:
which trails each organization may put a challenge on (design principle 5).
Neither carries a mile or a coordinate. Items name published POI ids, and
lib/challenges.py copies the published record's own mile, coordinate and name
into the artifact, so what the phone matches a day's walk against is the
number every other screen already shows.

RUNS AFTER export_poi.py AND export_trails.py, and both orderings are
load-bearing:

  - export_poi.py, for export_highlights.py's reason: the ids have to be the
    ones already on the device, and the miles the ones the client already
    agrees with. Resolving against raw ATC points would publish places
    calibrated differently from every other mile in the app.
  - export_trails.py, because every place must lie within its own tag radius
    of the published A.T. centerline or say `off_trail`. export_poi.py's
    attach_miles gives any point an A.T. mile, so a mile proves nothing about
    distance; trails.geojson's `centerline` features are what the distance is
    measured against. If that file is absent, or holds no centerline, the
    check is SKIPPED and the run says so as a workflow annotation - never
    silently.

WHAT DOES NOT PUBLISH, AND HOW ANYBODY FINDS OUT

Everything lib/challenges.py refuses - a POI gone or off its trail, a place
past its radius, a finish line no longer reachable - is printed to stderr,
item by item, and so is every publishers.json row or trail this script
refuses. Not a failure exit, the stance export_highlights.py takes: this runs
in the job that publishes the trail itself, one bad row must not hold that
back, and a list quietly shrinking is prevented by the report rather than by
the exit code.

NO NETWORK - reads the reference files, sources.json, and data/processed/,
which export_poi.py and export_trails.py write.

    .venv/Scripts/python export_challenges.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from collections.abc import Mapping
from datetime import date, datetime, timezone
from pathlib import Path

from lib.challenges import Resolution, resolve, trail_distance_index
from lib.manifest_paths import to_manifest_path
from lib.poi_schema import POI_TYPES, poi_output_name
from lib.source_registry import load_registry

ROOT = Path(__file__).parent
PROCESSED_DIR = ROOT / "data" / "processed"
POI_DIR = PROCESSED_DIR / "poi"
TRAILS_PATH = PROCESSED_DIR / "trails.geojson"
REFERENCE_DIR = ROOT / "reference" / "challenges"
PUBLISHERS_PATH = REFERENCE_DIR / "publishers.json"
SOURCES_PATH = ROOT / "sources.json"

OUT_PATH = PROCESSED_DIR / "challenges.json"
MANIFEST_PATH = PROCESSED_DIR / "challenges_manifest.json"

#: How trails.geojson marks the A.T. itself - export_trails.py's
#: CHAIN_MERGED_SOURCES. Everything else in that file is a side trail, and a
#: place beside a side trail is not a place on the A.T.
CENTERLINE_SOURCE = "centerline"


def load_challenge_files(reference_dir: Path | None = None) -> list[tuple[Path, object]]:
    """Every reviewed challenge file, parsed, in path order.

    `<org>/<id>.json`, one directory down, so publishers.json beside the
    directories is never read as a challenge. Path order is the order a
    person maintains them in (lib/challenges.resolve's docstring).

    A file that is not valid JSON parses to None, which the resolver drops as
    "file is not an object", with the parser's own complaint printed here
    first. Dropped rather than raised, because this runs in the job that
    publishes the trail, and one broken file must not hold that back.
    """
    reference_dir = REFERENCE_DIR if reference_dir is None else reference_dir
    files: list[tuple[Path, object]] = []
    for path in sorted(reference_dir.glob("*/*.json")):
        try:
            files.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except json.JSONDecodeError as error:
            print(f"{path} is not valid JSON ({error}) - it will not publish", file=sys.stderr)
            files.append((path, None))
    return files


def load_publishers(path: Path | None = None) -> list[object]:
    """publishers.json's rows. Absent is fatal, as export_highlights.py's
    curated list is: without it no organization may publish anything, and an
    empty challenges.json looks exactly like a trail no club has put a
    challenge on."""
    path = PUBLISHERS_PATH if path is None else path
    if not path.exists():
        raise SystemExit(f"{path} is missing - it is the scope every challenge is checked against")
    rows = json.loads(path.read_text(encoding="utf-8")).get("publishers")
    return rows if isinstance(rows, list) else []


def load_organizations(path: Path | None = None) -> dict[str, dict]:
    """sources.json's registered organizations, keyed `org:<slug>`."""
    path = SOURCES_PATH if path is None else path
    return load_registry(path).get("organizations", {}).get("orgs", {})


def load_published_pois(poi_dir: Path | None = None) -> list[dict]:
    """Every published POI's properties, across every type.

    Every type, for export_highlights.py's reason: an item can name any place
    the ATC's layers carry - a vista, a shelter, a Community - and narrowing
    the set would silently drop an item rather than refuse it. Its own copy
    rather than an import of that script's, so the None-sentinel default
    below follows THIS module's POI_DIR when a test moves it.
    """
    poi_dir = POI_DIR if poi_dir is None else poi_dir
    pois: list[dict] = []
    for poi_type in POI_TYPES:
        path = poi_dir / poi_output_name(poi_type)
        if not path.exists():
            continue
        for feature in json.loads(path.read_text()).get("features") or []:
            properties = feature.get("properties") or {}
            if properties.get("id"):
                pois.append(properties)
    return pois


def load_centerline(path: Path | None = None) -> list[list[tuple[float, float]]] | None:
    """The A.T. centerline as (lon, lat) polylines, or None when trails.geojson
    is absent - which the caller must report, never absorb.

    LineString and MultiLineString both, so a change in how export_trails.py
    writes its merged chains cannot quietly empty the distance check.
    """
    path = TRAILS_PATH if path is None else path
    if not path.exists():
        return None
    lines: list[list[tuple[float, float]]] = []
    for feature in json.loads(path.read_text()).get("features") or []:
        if (feature.get("properties") or {}).get("source") != CENTERLINE_SOURCE:
            continue
        geometry = feature.get("geometry") or {}
        if geometry.get("type") == "LineString":
            parts = [geometry.get("coordinates") or []]
        elif geometry.get("type") == "MultiLineString":
            parts = geometry.get("coordinates") or []
        else:
            continue
        for part in parts:
            lines.append([(float(c[0]), float(c[1])) for c in part])
    return lines


def publisher_scope(
    rows: list[object], organizations: Mapping[str, dict], pois: list[dict]
) -> tuple[dict[str, set[str]], list[str]]:
    """publishers.json, checked against what this run can stand behind.

    Returns org -> the trails it may put a challenge on, and one line for
    every row or trail refused:

      - the org must be registered in sources.json as `org:<org>`, with a
        `name` and a `provider`, because every published challenge carries
        both (`org_name`, `org_short`) and the phone has no other source for
        "ATC · until Sep 1";
      - the row must say `why` - the file's own README promises one reason per
        row, and a scope nobody explained is a scope nobody reviewed;
      - each trail must be carried by at least one published POI's `trail_id`.
        A trail with nothing placed on it can hold no challenge place, and a
        trail id spelled differently from the POIs' (`at` for `AT`) is exactly
        how that happens.

    A registered org whose every trail was refused stays in the result with
    an empty set, so its challenges drop as "trail 'AT' is not one 'atc'
    publishes" - which is then true - rather than as an unknown organization.
    """
    carried = {p.get("trail_id") for p in pois if isinstance(p.get("trail_id"), str)}
    scope: dict[str, set[str]] = {}
    refused: list[str] = []
    for row in rows:
        if not isinstance(row, Mapping):
            refused.append(f"a row is not an object: {row!r}")
            continue
        org = row.get("org")
        registered = organizations.get(f"org:{org}") if isinstance(org, str) else None
        if not isinstance(registered, Mapping):
            refused.append(f"{org!r}: not an organization in sources.json (looked for 'org:{org}')")
            continue
        if not _text(registered.get("name")) or not _text(registered.get("provider")):
            refused.append(f"{org}: sources.json 'org:{org}' has no name or no provider to publish beside its challenges")
            continue
        if org in scope:
            refused.append(f"{org}: listed twice - the first row stands")
            continue
        if not _text(row.get("why")):
            refused.append(f"{org}: the row gives no `why`")
            continue
        trails = row.get("trails")
        if not isinstance(trails, list):
            refused.append(f"{org}: `trails` is not a list")
            continue
        scope[org] = set()
        for trail in trails:
            if isinstance(trail, str) and trail in carried:
                scope[org].add(trail)
            else:
                refused.append(f"{org}: trail {trail!r} is carried by no published POI")
    return scope, refused


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def build_output(
    files: list[tuple[Path, object]],
    *,
    org_trails: Mapping[str, set[str]],
    organizations: Mapping[str, dict],
    pois: list[dict],
    centerline: list[list[tuple[float, float]]] | None,
    today: date,
) -> tuple[dict, Resolution]:
    """The artifact, and everything that did not make it in.

    `centerline` None or empty skips the distance check; main() is what says
    so out loud, because this function has no audience."""
    by_id = {p["id"]: p for p in pois if isinstance(p.get("id"), str)}
    # The types at least one published POI carries, not every declared type:
    # POI_TYPES admits `trailhead`, which the ATC does not publish
    # (lib/poi_schema.py's ALLOWED_EMPTY_POI_TYPES), and "tag any trailhead"
    # on the A.T. would be an item nobody could ever tag.
    published_types = tuple(t for t in POI_TYPES if any(p.get("poi_type") == t for p in pois))
    distance = trail_distance_index(centerline) if centerline else None

    # The directory is part of what a reviewer reads: a file under atc/ that
    # says `org: gatc` would pass review as the ATC's and publish as GATC's.
    # The same editing accident lib/challenges.resolve refuses for a stem that
    # disagrees with its id, one level up.
    misplaced: list[tuple[str, str]] = []
    candidates: list[tuple[str, object]] = []
    for path, raw in files:
        org = raw.get("org") if isinstance(raw, Mapping) else None
        if isinstance(org, str) and org != path.parent.name:
            misplaced.append((path.stem, f"file is under {path.parent.name}/ but its org is {org!r}"))
            continue
        candidates.append((path.stem, raw))

    resolution = resolve(
        candidates,
        org_trails=org_trails,
        poi_types=published_types,
        pois=by_id,
        trail_distance_m=distance,
        today=today,
    )
    resolution.dropped[:0] = misplaced

    challenges = []
    for record in resolution.challenges:
        registered = organizations.get(f"org:{record['org']}") or {}
        name, short = _text(registered.get("name")), _text(registered.get("provider"))
        if not name or not short:
            # publisher_scope already refuses such an org, so this is reached
            # only by a caller that built org_trails some other way.
            resolution.dropped.append((record["id"], f"sources.json 'org:{record['org']}' has no name or no provider"))
            continue
        # What the phone prints as "ATC · until Sep 1" and "Draft · not yet
        # confirmed by the ATC". The registry's own two spellings, so the
        # club reads its name the way every other screen already spells it.
        challenges.append({**record, "org_name": name, "org_short": short})
    resolution.challenges = challenges

    output = {
        # Named rather than dated, as highlights.json is, and with no
        # `generated_at` for a reason publish.py's conditions block records
        # from experience: a stamp moves the sha256 every run, so a run that
        # changed no challenge would still upload one and mint a new version.
        # The date that matters is each record's `reviewed`, the day somebody
        # last stood behind the list.
        "source": "reference/challenges",
        "challenges": challenges,
    }
    return output, resolution


def _kinds(record: dict) -> str:
    counts = Counter(item["match"]["kind"] for item in record["items"])
    return ", ".join(f"{kind} {n}" for kind, n in counts.most_common())


def main(today: date | None = None) -> dict:
    # UTC, like every stamp this pipeline writes: a mystery item unseals on
    # the first run on or after its reveal_on, and "today" must not depend on
    # which timezone the runner happens to be in.
    today = datetime.now(timezone.utc).date() if today is None else today

    files = load_challenge_files()
    publishers = load_publishers()
    organizations = load_organizations()
    pois = load_published_pois()
    centerline = load_centerline()

    if not pois:
        # export_highlights.py's stance on the same input, and its wording:
        # every place would drop, which looks like a club that published
        # nothing. Naming both sides, because "run export_poi.py first" is
        # false when it already ran and wrote files under other names.
        print(f"WARNING: no published POIs under {POI_DIR} - run export_poi.py first.")
        found = sorted(p.name for p in POI_DIR.glob("*.geojson")) if POI_DIR.is_dir() else []
        print(f"  found: {', '.join(found) if found else '(nothing - directory is empty or absent)'}")

    # `::warning::` rather than a bare print, as export_conditions.py does, so
    # a skipped check reaches the run's annotations without anybody opening
    # the step log. Every non-off_trail place publishes UNCHECKED on this
    # path, which is the one thing here a reviewer must not miss.
    if centerline is None:
        print(f"::warning::{TRAILS_PATH} is absent, so the challenge distance check was SKIPPED - run export_trails.py first.")
    elif not centerline:
        print(f"::warning::{TRAILS_PATH} holds no '{CENTERLINE_SOURCE}' feature, so the challenge distance check was SKIPPED.")
    else:
        vertices = sum(len(line) for line in centerline)
        print(f"distance check: every on-trail place against {vertices:,} centerline vertices in {TRAILS_PATH.name}")

    org_trails, refused = publisher_scope(publishers, organizations, pois)
    output, resolution = build_output(
        files,
        org_trails=org_trails,
        organizations=organizations,
        pois=pois,
        centerline=centerline,
        today=today,
    )

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False: the ATC's titles carry its own curly quotes, and a
    # hiker comparing this list with the PDF must find the same lines.
    OUT_PATH.write_bytes((json.dumps(output, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"))
    digest = hashlib.sha256(OUT_PATH.read_bytes()).hexdigest()
    # Via to_manifest_path(), as export_highlights.py's manifest is; the
    # helper's own docstring has why a plain relative path is not enough.
    manifest = {"path": to_manifest_path(OUT_PATH), "sha256": digest}
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    published = output["challenges"]
    print(f"{len(published)} challenge(s) -> {OUT_PATH} (today = {today.isoformat()}, UTC)")
    for record in published:
        sealed = sum(1 for item in record["items"] if "sealed_title" in item)
        print(f"  {record['id']:<32} {record['status']:<10} {len(record['items']):>3} items: {_kinds(record)}")
        if sealed:
            print(f"  {'':<32} {'':<10} {sealed} sealed until their reveal_on")

    # A list quietly shrinking is the failure nobody notices, so a refusal is
    # never just an absence from the output.
    if refused:
        print(f"\n{len(refused)} publishers.json row(s) or trail(s) refused:", file=sys.stderr)
        for line in refused:
            print(f"  {line}", file=sys.stderr)
    if resolution.dropped:
        print(f"\n{len(resolution.dropped)} challenge(s) did not publish:", file=sys.stderr)
        for challenge_id, why in resolution.dropped:
            print(f"  {challenge_id}: {why}", file=sys.stderr)
    if resolution.dropped_items:
        print(f"\n{len(resolution.dropped_items)} item(s) did not publish:", file=sys.stderr)
        for challenge_id, item_id, why in resolution.dropped_items:
            print(f"  {challenge_id} / {item_id}: {why}", file=sys.stderr)
    if refused or resolution.dropped or resolution.dropped_items:
        print(
            f"::warning::challenges: {len(resolution.dropped)} challenge(s) and "
            f"{len(resolution.dropped_items)} item(s) did not publish, and {len(refused)} "
            "publishers.json line(s) were refused - the step log lists each."
        )

    return manifest


if __name__ == "__main__":
    main()
