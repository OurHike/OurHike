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
every type's file at once; a run given one type would delete the rest, and
says so line by line first.

AND IT REFUSES TO EMPTY THE TABLE. Files that yield no mile at all are a
broken download or the wrong directory far more often than a trail with no
waypoints, and an empty table silently takes every maintainer's weight out of
`GET /disputes`. #1912 (Nothing refuses a conditions bake that drops closures
from N to 0, so an emptied table publishes an empty map to every phone that
opens with signal) is the same failure one pipeline over.
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
    """A file that is not the published waypoint GeoJSON, said by name."""


def parse(documents: dict[str, Any]) -> dict[str, float]:
    """Every waypoint's mile, from the published GeoJSON documents keyed by file name.

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
            properties = (feature or {}).get("properties") or {}
            poi_id, mile = properties.get("id"), properties.get("mile")
            if not isinstance(poi_id, str) or not poi_id:
                raise InvalidFile(f"{name} has a feature with no `id`")
            if isinstance(mile, bool) or not isinstance(mile, int | float) or not math.isfinite(mile):
                continue
            if poi_id in miles and miles[poi_id] != float(mile):
                raise InvalidFile(f"{poi_id} is at mile {miles[poi_id]} in one file and {mile} in {name}")
            miles[poi_id] = float(mile)
    if not miles:
        raise InvalidFile(
            "these files place no waypoint on the trail, which would empty waypoint_miles and take every "
            "maintainer's weight out of GET /disputes. Check they are the published waypoint GeoJSON."
        )
    return miles


def apply(db: Session, miles: dict[str, float]) -> list[str]:
    """Make the table match `miles`, returning one line per change.

    Flushes but never commits, for `load_assignments.py`'s reason: `main`
    decides, which is what makes `--commit` a gate rather than a label.
    """
    now = utc_now()
    existing = {row.poi_id: row for row in db.query(WaypointMile).all()}
    changes: list[str] = []

    for poi_id in sorted(miles):
        mile = miles[poi_id]
        row = existing.get(poi_id)
        if row is None:
            db.add(WaypointMile(poi_id=poi_id, mile=mile, loaded_at=now))
            changes.append(f"waypoint + {poi_id} at mile {mile}")
        elif row.mile != mile:
            changes.append(f"waypoint ~ {poi_id} moved from mile {row.mile} to {mile}")
            row.mile, row.loaded_at = mile, now

    for poi_id in sorted(set(existing) - set(miles)):
        db.delete(existing[poi_id])
        changes.append(f"waypoint - {poi_id}, in no file given")

    db.flush()
    return changes


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", type=Path, nargs="+", help="The published waypoint GeoJSON files, every type.")
    parser.add_argument(
        "--commit",
        action="store_true",
        help="Actually write. Without it, this says what it would do and rolls back.",
    )
    args = parser.parse_args(argv)

    documents: dict[str, Any] = {}
    for path in args.files:
        try:
            documents[path.name] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            print(f"Could not read {path}: {error}", file=sys.stderr)
            return 2

    db = SessionLocal()
    try:
        changes = apply(db, parse(documents))
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
        print("Nothing to do - the table already matches these files.")
    elif not args.commit:
        print(f"\n{len(changes)} change(s) NOT written. Re-run with --commit.")
    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
