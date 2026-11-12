"""`/clubs/{slug}/inventory/export.csv` and `.geojson` - a club's structures, for its own GIS.

#1993 — The inventory exports as CSV and GeoJSON for the club's GIS,
admin-only, with every estimate labelled as one. features/STRUCTURE_INVENTORY.md's
permissions table puts both behind `require_org_admin`, the check
`download_entries` in `app/routers/trail_challenges.py` already uses.

**One row (or feature) per structure, carrying its latest accepted
observation.** "Current condition is the latest accepted observation - a
query, not a column" (`app/models/inventory.py`), so this is that query. What
the export leaves out, and why:

- A structure with no accepted observation. Nothing about it has been
  reviewed yet, and a club's GIS layer is where an unreviewed guess would
  start reading as the club's record.
- A `merged` structure. It is the same thing as the structure named in its
  `merged_into_id`, and exporting both would count one bridge twice.
- Who walked it, every raw GPS reading, and the photos. The club's file is
  about the structures; the volunteers' names belong to the roster, which
  `GET /clubs/{slug}/export` already carries, and the readings are the
  server's evidence for the median, not a GIS attribute.

A `removed` structure is kept, with its status, because "gone from the
ground" is something a club's map should be able to show.

**Rule 3 is applied here as well as at upload.** `ObservationCreate` already
refuses a bucket that carries a number. This file does not rely on that: a
size is written as a number only when `size_method` is `tape`, so a row that
reached the table some other way still cannot print a bucket as a
measurement. `_size_cells` is the one place that decision is made.

"Latest" is by `captured_at`, the phone's clock when the volunteer saved the
record, because the export describes the structure as it was last seen, not
as it was last uploaded. Ties fall back to `created_at` and then the id, so
the answer does not depend on row order.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.org_access import OrgAccess, require_org_admin
from app.core.trail_challenge import spreadsheet_safe
from app.db.session import get_db
from app.models.inventory import (
    InventoryObservation,
    InventoryStructure,
    ReviewState,
    SizeMethod,
    StructureStatus,
)

router = APIRouter(tags=["inventory"])

# The CSV's header and the GeoJSON's property names, in the same order.
EXPORT_COLUMNS = (
    "code",
    "structure_id",
    "kind",
    "subkind",
    "status",
    "trail_id",
    "section_id",
    "lat",
    "lon",
    "mile",
    "off_line_ft",
    "observed_at",
    "observation_id",
    "condition",
    "problems",
    "repair",
    "timing",
    # How the size was arrived at, before the size itself, so nobody reads
    # the number without passing the word that says whether it is one.
    "size_method",
    "size_bucket",
    "size_measured",
    "size_unit",
    "counts",
    "railings",
    "notes",
    "photo_count",
    "accuracy_m",
    "fix_source",
)


def _current(db: Session, club_id: str) -> list[tuple[InventoryStructure, InventoryObservation]]:
    """Each exportable structure with its latest accepted observation, ordered by code then id."""
    structures = (
        db.query(InventoryStructure)
        .filter(InventoryStructure.club_id == club_id, InventoryStructure.status != StructureStatus.merged)
        .all()
    )
    if not structures:
        return []
    observations = (
        db.query(InventoryObservation)
        .filter(
            InventoryObservation.club_id == club_id,
            InventoryObservation.review_state == ReviewState.accepted,
            InventoryObservation.structure_id.in_([structure.id for structure in structures]),
        )
        .all()
    )
    latest: dict[str, InventoryObservation] = {}
    for row in observations:
        held = latest.get(row.structure_id)
        if held is None or (row.captured_at, row.created_at, row.id) > (held.captured_at, held.created_at, held.id):
            latest[row.structure_id] = row
    pairs = [(structure, latest[structure.id]) for structure in structures if structure.id in latest]
    # A structure without a code yet sorts after every coded one.
    pairs.sort(key=lambda pair: (pair[0].code is None, pair[0].code or "", pair[0].id))
    return pairs


def _size_cells(observation: InventoryObservation) -> tuple[str | None, str | None, float | None, str | None]:
    """(size_method, size_bucket, size_measured, size_unit), with a number only for a tape.

    Rule 3: a bucket is a guess, so it travels as its label and its method
    and never as a number, even if the row somehow holds one. A size with no
    method is nobody's answer and is exported as no size at all.
    """
    method = observation.size_method
    if method is SizeMethod.tape:
        return (method.value, None, observation.size_measured, observation.size_unit)
    if method is SizeMethod.bucket:
        return (method.value, observation.size_bucket, None, None)
    return (None, None, None, None)


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def _properties(structure: InventoryStructure, observation: InventoryObservation) -> dict[str, Any]:
    """One structure's exported fields, typed as JSON would carry them."""
    size_method, size_bucket, size_measured, size_unit = _size_cells(observation)
    return {
        "code": structure.code,
        "structure_id": structure.id,
        "kind": _enum_value(structure.kind),
        "subkind": structure.subkind,
        "status": _enum_value(structure.status),
        "trail_id": structure.trail_id,
        "section_id": structure.section_id,
        "lat": structure.lat,
        "lon": structure.lon,
        "mile": structure.mile,
        "off_line_ft": structure.off_line_ft,
        # Naive UTC stored, so the `Z` is put back on: an unmarked UTC time
        # in a file is read as local (download_entries's reason).
        "observed_at": observation.captured_at.isoformat() + "Z",
        "observation_id": observation.id,
        "condition": _enum_value(observation.condition),
        "problems": list(observation.problems or []),
        "repair": _enum_value(observation.repair),
        "timing": _enum_value(observation.timing),
        "size_method": size_method,
        "size_bucket": size_bucket,
        "size_measured": size_measured,
        "size_unit": size_unit,
        "counts": dict(observation.counts) if observation.counts else None,
        "railings": observation.railings,
        "notes": observation.notes,
        "photo_count": observation.photo_count,
        "accuracy_m": observation.accuracy_m,
        "fix_source": _enum_value(observation.fix_source),
    }


def _csv_cell(value: Any) -> str:
    """A property as one spreadsheet cell. Absent is an empty cell, never 0 or "none"."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    if isinstance(value, dict):
        return ";".join(f"{key}={value[key]}" for key in sorted(value))
    return str(value)


def _safe_cell(value: Any) -> str:
    """`_csv_cell`, with text guarded by `spreadsheet_safe` and numbers left as numbers.

    Only a string can carry a formula somebody typed. A longitude of -73.88
    starts with `-`, one of the leads `spreadsheet_safe` quotes, and quoting
    it would turn every western coordinate into text in the club's GIS.
    """
    cell = _csv_cell(value)
    return spreadsheet_safe(cell) if isinstance(value, str) else cell


@router.get(
    "/clubs/{slug}/inventory/export.csv",
    responses={200: {"content": {"text/csv": {}}, "description": "One row per reviewed structure."}},
)
def export_inventory_csv(
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> Response:
    """The club's structures as a CSV a spreadsheet or a GIS opens. Admins only.

    `download_entries`'s file conventions: a UTF-8 byte-order mark so Excel
    reads it as UTF-8, every cell quoted, and every text cell through
    `spreadsheet_safe`, because `notes` and `subkind` were typed by a
    volunteer and a leading `=` would otherwise arrive as a live formula.
    Numbers are not passed through it (`_safe_cell` says why).
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_ALL)
    writer.writerow(EXPORT_COLUMNS)
    for structure, observation in _current(db, access.club.id):
        properties = _properties(structure, observation)
        writer.writerow([_safe_cell(properties[column]) for column in EXPORT_COLUMNS])
    return Response(
        content="﻿" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="structure-inventory.csv"',
            "Cache-Control": "private, no-store, max-age=0",
        },
    )


@router.get(
    "/clubs/{slug}/inventory/export.geojson",
    responses={200: {"content": {"application/geo+json": {}}, "description": "A FeatureCollection of points."}},
)
def export_inventory_geojson(
    access: OrgAccess = Depends(require_org_admin),
    db: Session = Depends(get_db),
) -> Response:
    """The club's structures as a GeoJSON FeatureCollection of points. Admins only.

    The first GeoJSON this backend writes. Each feature is a `Point` at the
    structure's `[lon, lat]` (RFC 7946 order) with the same properties the
    CSV's columns carry, typed: `problems` a list, `counts` an object, and
    every absent value `null`. `size_method` is on every feature, `null`
    where nobody gave a size.
    """
    features = [
        {
            "type": "Feature",
            "id": structure.id,
            "geometry": {"type": "Point", "coordinates": [structure.lon, structure.lat]},
            "properties": _properties(structure, observation),
        }
        for structure, observation in _current(db, access.club.id)
    ]
    return Response(
        content=json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False),
        media_type="application/geo+json",
        headers={
            "Content-Disposition": 'attachment; filename="structure-inventory.geojson"',
            "Cache-Control": "private, no-store, max-age=0",
        },
    )
