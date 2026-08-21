"""Route corroborated disputes to the steward whose data they contradict.

[features/FIELD_NOTES.md](../features/FIELD_NOTES.md) §4's last piece, and
the one that makes the rest of the feature worth having
([#876](https://github.com/OurHike/OurHike/issues/876)). A dispute that stops
at a mark on our own map is a private fork of somebody else's dataset: ATC
still publishes a spring that is not there, every other consumer of that
layer still gets it, and the next release of ours re-imports it. The
correction has to land in ATC's data, which means somebody at ATC has to
hear about it.

WHAT THIS SCRIPT IS, IN ONE LINE

The join between three things this repository already has and had never put
in the same room: the published `conditions/disputes.json` (what hikers
say), the published `poi_*.geojson` (which place they mean, by name and
mile), and [`sources.json`](sources.json) (whose layer that place came from,
via `lib/source_registry.py`'s `POI_SOURCE_KEYS`).

OVER PUBLISHED ARTIFACTS, NOT THE DATABASE - `check_note_anchors.py`'s
posture, adopted deliberately rather than by imitation. Both halves of the
join are public HTTPS reads of exactly what a phone reads, so this holds no
credential and is structurally incapable of changing anyone's map. It is
also the reason it can only ever see what a hiker can see, which matters
here more than it does there: the bake aggregates `reporter_id` away before
this script exists, so a routing job never learns who reported anything.
That is not a precaution this script takes, it is a fact about its input.

WHAT IT INHERITS FROM THE BAKE, INCLUDING THE GAP

`export_conditions.py`'s `PUBLIC_DISPUTES_SQL` has no maintainer clause -
`maintainer_assignments` is not in the conditions reader role's grant - so a
covering maintainer's lone dispute reaches a phone through the live read and
never through the baseline. This job reads the baseline. So it routes the
corroborated-count half of §4's rule and not the maintainer half, and a
maintainer's report of a missing spring is therefore NOT filed upstream by
this job today. That is a real gap, it is named in the report it writes, and
closing it means either widening that grant or giving this job a second
door - both of which are decisions rather than oversights.

ONE TRACKING ISSUE PER SOURCE, UPDATED IN PLACE

The volume rule from [DATA_RELEASES.md](DATA_RELEASES.md), enforced by the
same code the freshness and reachability monitors use
(`.github/scripts/tracking-issue.js`) rather than by a second mechanism that
would have to learn #431's lesson again. The workflow calls it once per
source: a source is a steward, and a steward wants one running list of
"places your layer says exist and hikers say do not", not an issue per
spring.

THREE DISPOSITIONS, AND ONLY ONE IS AN ASK

  to_file        the place is still in the current release and hikers say
                 it is gone. This is the correction, and the only thing
                 that keeps an issue open.
  already_gone   the place is disputed and is no longer in the release at
                 all - upstream removed it, or POI_IDENTITY.md's ledger
                 retired it. The dispute was right and is already answered;
                 filing it would be asking for something already done.
  unregistered   nobody is named for this source. Reported rather than
                 dropped - see `UNREGISTERED_POI_SOURCES` for the two very
                 different reasons an id namespace lands here.

AND ONE REFUSAL

If any published artifact this reads did not answer, the run routes nothing
at all - `routable` is false and the workflow touches no issue. `to_file`
and `already_gone` are both claims about the COMPLETE published id set: a
poi file that 503'd is exactly the file a disputed place might live in, and
telling a steward their spring is missing from their own layer on the
strength of a failed GET is the kind of confidently-wrong report that gets
this project's mail filtered. The same refusal `check_note_anchors.py`
makes about orphans, for the same reason (#446).

    python route_disputes.py --base https://data.example.org
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from check_note_anchors import FAILED, POI_KEY_PATTERN, UNREACHABLE, fetch_json
from lib.freshness_state import utc_today
from lib.source_registry import (
    POI_SOURCE_KEYS,
    UNREGISTERED_POI_SOURCES,
    load_registry,
    poi_source_entry,
    poi_source_steward,
)
from smoke_published import fetch_manifest

#: The published object this routes. Pairs with `DISPUTES_OUT_PATH` in
#: export_conditions.py and `PUBLISHED_DISPUTES_KEY` in the client.
DISPUTES_KEY = "conditions/disputes.json"

REGISTRY_PATH = Path(__file__).resolve().parent / "sources.json"


def published_places(base: str, manifest: dict, session=None) -> tuple[dict[str, dict], list[dict]]:
    """Every published POI id -> the facts a steward needs to find it.

    Deliberately not `check_note_anchors.py`'s `published_poi_ids`, which
    reads the same files: that one answers "does this id exist", and a
    steward cannot act on `atc_shelters:8f3c...`. What makes a report
    actionable is the name and the mile, so this keeps the properties. The
    completeness rule is shared, and that half is not duplicated - a file
    that did not answer, or answered without ids, is a `problem`, and the
    caller refuses to route on a run that has any.
    """
    places: dict[str, dict] = {}
    problems: list[dict] = []
    keys = sorted(k for k in (manifest.get("artifacts") or {}) if POI_KEY_PATTERN.match(k))
    if not keys:
        problems.append(
            {
                "key": "latest.json",
                "state": FAILED,
                "detail": "the manifest names no poi_*.geojson artifacts, so no disputed place can be located",
            }
        )
        return places, problems

    for key in keys:
        document, why_not = fetch_json(base, key, session)
        if document is None:
            problems.append({"key": key, "state": UNREACHABLE, "detail": why_not})
            continue
        features = document.get("features") or []
        found = 0
        for feature in features:
            properties = feature.get("properties") or {}
            poi_id = properties.get("id")
            if not poi_id:
                continue
            found += 1
            coordinates = (feature.get("geometry") or {}).get("coordinates") or [None, None]
            places[poi_id] = {
                "name": properties.get("name"),
                "poi_type": properties.get("poi_type"),
                "mile": properties.get("mile"),
                "lon": coordinates[0],
                "lat": coordinates[1],
            }
        if features and not found:
            problems.append(
                {
                    "key": key,
                    "state": FAILED,
                    "detail": f"{len(features)} feature(s) and none carries a properties.id - the id join this routing relies on is broken",
                }
            )
    return places, problems


def poi_source_of(poi_id: str) -> str:
    """The id namespace, which is the layer. `lib/poi_schema.py` mints
    `<source>:<source_feature_id>` and the feature id may itself contain a
    colon, so this splits once from the left."""
    return poi_id.split(":", 1)[0]


def route(base: str, registry: dict, session=None) -> dict | None:
    """The whole verdict, or None when nothing is published to route."""
    manifest = fetch_manifest(base, session)
    if manifest is None:
        return None

    problems: list[dict] = []
    document, why_not = fetch_json(base, DISPUTES_KEY, session)
    if document is None:
        # Not "nothing is disputed". A conditions-publish outage must never
        # read as an all-clear, because an all-clear closes every steward's
        # issue and loses the running list with it.
        problems.append({"key": DISPUTES_KEY, "state": UNREACHABLE, "detail": why_not})
        disputes = []
    else:
        disputes = document.get("disputes") or []

    places, poi_problems = published_places(base, manifest, session)
    problems.extend(poi_problems)
    routable = not problems

    # Every source that could carry a dispute, not only the sources that do -
    # because a source whose last dispute was answered has an issue open that
    # nothing else will ever close. The set is small and bounded by the
    # registry join, so enumerating it costs one issue lookup each.
    by_source: dict[str, list[dict]] = {source: [] for source in POI_SOURCE_KEYS}
    for row in disputes:
        poi_id = row.get("poi_id")
        if not poi_id:
            continue
        by_source.setdefault(poi_source_of(poi_id), []).append(row)

    sources = []
    for poi_source in sorted(by_source):
        entry = poi_source_entry(registry, poi_source)
        rows = sorted(by_source[poi_source], key=lambda row: row["poi_id"])
        to_file, already_gone = [], []
        for row in rows if routable else []:
            place = places.get(row["poi_id"])
            record = {
                "poi_id": row["poi_id"],
                "accounts": row.get("accounts"),
                "latest_at": row.get("latest_at"),
                "maintainer_said": row.get("maintainer_said", False),
                **(place or {}),
            }
            (to_file if place else already_gone).append(record)

        sources.append(
            {
                "poi_source": poi_source,
                "registry_key": POI_SOURCE_KEYS.get(poi_source),
                "title": (entry or {}).get("title"),
                "steward": poi_source_steward(registry, poi_source),
                # An id namespace nothing registers. `unregistered` is a
                # property of the SOURCE, so it is true whether or not that
                # source currently has anything to file - which is what lets
                # a report say "and there is still nowhere to send these".
                "unregistered": entry is None,
                "expected_unregistered": poi_source in UNREGISTERED_POI_SOURCES,
                "to_file": to_file,
                "already_gone": already_gone,
                # A source is healthy when it has nothing to ask of anybody.
                # `already_gone` is not an ask: upstream already did it.
                "healthy": routable and not to_file,
            }
        )

    return {
        "checked_at": utc_today().isoformat(),
        "base": base,
        "routable": routable,
        "disputes": len(disputes),
        "failed": [p for p in problems if p["state"] == FAILED],
        "unreachable": [p for p in problems if p["state"] == UNREACHABLE],
        "sources": sources,
        # The count that decides whether this ran usefully at all, kept
        # separate from `routable`: a run can be perfectly routable and have
        # nothing to route, which is the ordinary day.
        "to_file": sum(len(source["to_file"]) for source in sources),
    }


def render(verdict: dict) -> str:
    if not verdict["routable"]:
        lines = ["Nothing was routed: a published artifact this reads did not answer."]
        for problem in verdict["failed"] + verdict["unreachable"]:
            lines.append(f"  {problem['state']:>12}  {problem['key']}: {problem['detail']}")
        lines.append("No steward's issue was opened, updated or closed on this evidence.")
        return "\n".join(lines)

    lines = [f"{verdict['disputes']} corroborated dispute(s) published, {verdict['to_file']} to file upstream."]
    for source in verdict["sources"]:
        if not source["to_file"] and not source["already_gone"]:
            continue
        steward = source["steward"] or "nobody registered"
        lines.append(f"  {source['poi_source']} -> {steward}")
        for record in source["to_file"]:
            where = f"mile {record['mile']}" if record.get("mile") is not None else "mile unknown"
            lines.append(
                f"      file  {record['poi_id']}  {record.get('name') or '(unnamed)'}, {where}: "
                f"{record['accounts']} account(s), latest {record['latest_at']}"
            )
        for record in source["already_gone"]:
            lines.append(f"    already  {record['poi_id']}: disputed, and no longer in this release")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--base", required=True, help="Bucket base URL, e.g. https://data.example.org")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH, help="sources.json to resolve stewards against")
    parser.add_argument("--json", type=Path, help="Also write the verdict as JSON here")
    parser.add_argument(
        "--exit-zero",
        action="store_true",
        help="Exit 0 on an unroutable run; reserves 2 for nothing-published and other codes for crashes",
    )
    args = parser.parse_args(argv)

    verdict = route(args.base.rstrip("/"), load_registry(args.registry))
    if verdict is None:
        print(f"No {json.dumps('latest.json')} at {args.base} - nothing is published to route.")
        return 2

    print(render(verdict))
    if args.json:
        args.json.write_text(json.dumps(verdict, indent=2) + "\n")
    if args.exit_zero:
        return 0
    return 0 if verdict["routable"] else 1


if __name__ == "__main__":
    sys.exit(main())
