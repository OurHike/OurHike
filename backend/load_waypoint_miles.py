"""Load where each waypoint sits on the A.T. from the published waypoint export.

**The way rows get into `waypoint_miles`** (#1917 - A maintainer's note
settles a water dispute anywhere on the trail, because the covering check reads
the mile the note's author typed, not where the waypoint is). `GET /disputes`
decides whether a maintainer covers a waypoint from the waypoint's own mile,
and this is the only writer of that mile.

WHY THE PUBLISHED FILES, AND WHY A SCRIPT

The miles already exist: `pipeline/export_poi.py`'s `attach_miles` projects
every waypoint near the A.T. onto the centerline and publishes the result as
one GeoJSON per waypoint type, each feature carrying `id` and `mile`. This
reads those files - from `pipeline/data/processed/poi/` after an export, or
copies downloaded from the data bucket - rather than computing anything, so
the backend's idea of a waypoint's mile is the one hikers' phones draw. A
script rather than an endpoint for `load_assignments.py`'s reasons, and with
its posture: nothing is written without `--commit`.

    python load_waypoint_miles.py ../pipeline/data/processed/poi/*.geojson           # says what it would do
    python load_waypoint_miles.py ../pipeline/data/processed/poi/*.geojson --commit  # does it

THE FILES ARE THE WHOLE ANSWER. A waypoint in the table and in no file is
deleted, and a waypoint whose file withholds its mile has no row: the export
withholds one from a waypoint on another organization's trail rather than the
A.T. (`mark_off_trail_records` in pipeline/export_poi.py). So run it with
every type's file at once. A run given one type would delete the rest -
measured against release 2026-10-10-2, `poi_water.geojson` alone would have
deleted 2,592 of 3,024 rows - so a run that would delete more than
`MAX_SHRINK_SHARE` of the table is refused unless `--allow-shrink` says the
release really retired them.

AND IT REFUSES TO EMPTY THE TABLE. Files that yield no mile at all are a
broken download or the wrong directory far more often than a trail with no
waypoints. #1912 (Nothing refuses a conditions bake that drops closures
from N to 0, so an emptied table publishes an empty map to every phone that
opens with signal) is the same failure one pipeline over.

WHAT A MISSING ROW COSTS, and which half of it is unsafe. `GET /disputes`
reads a waypoint with no row as unplaced: a covering maintainer's `not_found`
still marks it from the mile they typed, and their confirmation no longer
clears one (app/routers/field_notes.py says why). So an empty or stale table
cannot hide a maintainer's warning; what it costs is a dispute that waits for
two people's confirmations where one maintainer's would have done. Every run
stamps every row it keeps with `loaded_at`, so `max(loaded_at)` is when the
table last matched a release. Nothing runs this on a schedule yet; after a
release, somebody runs it.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.db.session import SessionLocal
from app.models.waypoint_mile import WaypointMile


class InvalidFile(Exception):
    """A load refused, said by name: files that cannot be the published
    waypoint GeoJSON, or a load that would delete most of the table."""


# @unvalidated A tenth, and ten rows, are picked rather than measured: a
# release retiring a few waypoints passes, and one type's file standing in for
# all of them (86% of the table deleted, above) does not. What would settle it
# is the largest share of waypoints a real release has retired, read from the
# releases' own manifests, which nobody has tallied.
MAX_SHRINK_SHARE = 0.10
MAX_SHRINK_FLOOR = 10

# @unvalidated The same bound app/schemas/analytics.py puts on a mile: longer
# than any trail this app draws, and a guard against nonsense rather than a
# measurement. A mile below zero is before Springer and cannot be a position.
MAX_MILE = 5_000.0


def parse(documents: dict[str, Any]) -> dict[str, float]:
    """Every waypoint's mile, from the published GeoJSON documents keyed by path.

    A feature with no `mile`, or one that is not a finite number, is a
    waypoint the export placed nowhere on the trail, and is left out. Two
    files giving one waypoint different miles is refused rather than
    resolved: the export names each id once, so a disagreement means two
    exports from different runs were mixed.
    """
    miles: dict[str, float] = {}
    for name, document in documents.items():
        if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
            raise InvalidFile(f"{name} is not a GeoJSON FeatureCollection")
        for feature in document.get("features") or []:
            properties = feature.get("properties") if isinstance(feature, dict) else None
            if not isinstance(properties, dict):
                raise InvalidFile(f"{name} has a feature that is not a GeoJSON Feature with properties")
            poi_id, mile = properties.get("id"), properties.get("mile")
            if not isinstance(poi_id, str) or not poi_id:
                raise InvalidFile(f"{name} has a feature with no `id`")
            if isinstance(mile, bool) or not isinstance(mile, int | float) or not math.isfinite(mile):
                continue
            if not 0 <= mile <= MAX_MILE:
                raise InvalidFile(f"{poi_id} in {name} is at mile {mile}, which is no position on a trail")
            if poi_id in miles and miles[poi_id] != float(mile):
                raise InvalidFile(f"{poi_id} is at mile {miles[poi_id]} in one file and {mile} in {name}")
            miles[poi_id] = float(mile)
    if not miles:
        raise InvalidFile(
            "these files place no waypoint on the trail, which would empty waypoint_miles and take every "
            "maintainer's weight out of GET /disputes. Check they are the published waypoint GeoJSON."
        )
    return miles


def apply(db: Session, miles: dict[str, float], *, allow_shrink: bool = False) -> list[str]:
    """Make the table match `miles`, returning one line per change.

    Refuses, before writing anything, a load that would delete more than
    `MAX_SHRINK_SHARE` of the table (and more than `MAX_SHRINK_FLOOR` rows)
    unless `allow_shrink`. Stamps every row it keeps with this run's time, so
    `max(loaded_at)` says when the table last matched a release.

    Flushes but never commits, for `load_assignments.py`'s reason: `main`
    decides, which is what makes `--commit` a gate rather than a label.
    """
    now = utc_now()
    existing = {row.poi_id: row for row in db.query(WaypointMile).all()}
    leaving = sorted(set(existing) - set(miles))
    if not allow_shrink and len(leaving) > max(MAX_SHRINK_FLOOR, MAX_SHRINK_SHARE * len(existing)):
        raise InvalidFile(
            f"these files would delete {len(leaving)} of the {len(existing)} waypoints in the table, which is a "
            "partial set of files far more often than a release that retired them. Pass every type's file, or "
            "--allow-shrink if the release really did."
        )
    changes: list[str] = []

    for poi_id in sorted(miles):
        mile = miles[poi_id]
        row = existing.get(poi_id)
        if row is None:
            db.add(WaypointMile(poi_id=poi_id, mile=mile, loaded_at=now))
            changes.append(f"waypoint + {poi_id} at mile {mile}")
        elif row.mile != mile:
            changes.append(f"waypoint ~ {poi_id} moved from mile {row.mile} to {mile}")
            row.mile = mile

    for poi_id in leaving:
        db.delete(existing[poi_id])
        changes.append(f"waypoint - {poi_id}, in no file given")

    db.flush()
    # Every row left is one this load named, so one statement stamps the run.
    db.query(WaypointMile).update({WaypointMile.loaded_at: now}, synchronize_session=False)
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", type=Path, nargs="+", help="The published waypoint GeoJSON files, every type.")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually write. Without it, this says what it would do and rolls back.",
    )
    parser.add_argument(
        "--allow-shrink",
        action="store_true",
        # `%%`, because argparse %-formats help text: a bare `10% of` is read as
        # the conversion `% o`. Python 3.14 refuses that when the argument is
        # added, so `main` could not start under CI's interpreter at all.
        help=f"Allow a load that deletes more than {MAX_SHRINK_SHARE * 100:.0f}%% of the table, for a release that retired them.",
    )
    args = parser.parse_args(argv)

    # Keyed by path, and one file per name: two `poi_water.geojson` from two
    # downloads would otherwise have the second silently replace the first.
    documents: dict[str, Any] = {}
    names: set[str] = set()
    for path in args.files:
        if path.name in names:
            print(f"Refused: {path.name} is given twice; pass each type's file once.", file=sys.stderr)
            return 2
        names.add(path.name)
        try:
            documents[str(path)] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"Could not read {path}: {error}", file=sys.stderr)
            return 2

    db = SessionLocal()
    try:
        changes = apply(db, parse(documents), allow_shrink=args.allow_shrink)
        if args.commit:
            db.commit()
        else:
            db.rollback()
    except InvalidFile as error:
        db.rollback()
        print(f"Refused: {error}", file=sys.stderr)
        return 2
    finally:
        db.close()

    for line in changes:
        print(line)
    if not changes:
        print("No waypoint arrived, moved or left." + (" Every row's loaded_at is now this run's." if args.commit else ""))
    elif not args.commit:
        print(f"\n{len(changes)} change(s) NOT written. Re-run with --commit.")
    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
