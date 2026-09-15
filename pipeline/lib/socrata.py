"""Shared fetcher for Socrata (SODA 2.1) datasets published as GeoJSON.

WHY THIS EXISTS AT ALL, given lib/arcgis.py already fetches trail lines.

New York City does not publish its trails on ArcGIS. Every other source in
sources.json is an ArcGIS layer, so registering NYC (#1432) was the first
time this pipeline met a steward whose publication of record is a Socrata
portal - data.cityofnewyork.us - rather than a FeatureServer.

The ArcGIS copies of NYC's data that do exist are not a way around that.
NYC DCP mirrors DOT's bike network at services5.arcgis.com/GfwWNkhOj9bNBqoJ
/Bike_Routes, and measured live 2026-09-15 it reports dataLastEditDate
2017-03-08, carries 13,953 rows against the portal's 29,695, and has no
`grnwy` column at all - so it cannot even express "which of these is a
greenway", which is the entire filter NYC's entry ships behind. That is
NYC_SOURCE_SURVEY.md section 9's "data.ny.gov copies - precedent, not a
source" in a second city, and the reason this module exists instead of a
convenient URL.

WHAT IS DIFFERENT FROM lib/arcgis.py, and what is deliberately the same.

Different: Socrata pages on `$limit`/`$offset` rather than
`resultOffset`/`resultRecordCount`, filters with a SoQL `$where` string
rather than an ArcGIS `where`, and answers GeoJSON natively at
`/resource/<id>.geojson` with no `outSR` to ask for - the portal is WGS84
already (verified 2026-09-15: coordinates come back as lon/lat degrees).

The same, on purpose: the stop condition is AN EMPTY PAGE AND NEVER A SHORT
ONE, for the reason lib/arcgis.py's docstring gives at length - a server
whose own cap sits below the requested size returns short pages the whole
way through, and a loop that stops on one silently drops data. Socrata's
documented ceiling is 50,000 rows per request and both NYC datasets fit
inside a single page today (7,059 and 3,039, measured 2026-09-15), so the
paging loop is not exercised by either of them in production. It is written
correctly anyway, because "it fits today" is a fact about 2026 and not about
the code. tests/test_lib_socrata.py holds the regression test.

`$order=:id` IS LOAD-BEARING AND NOT A TIDINESS. SoQL gives no ordering
guarantee without it, so `$offset` against an unordered result set can
repeat one row and skip another - the same page-boundary corruption
lib/arcgis.py's tests cover, arriving through a different door. `:id` is
Socrata's internal row identifier, present on every dataset and stable
across the paging of one query.
"""

from __future__ import annotations

import json
from pathlib import Path

from lib.http_retry import request_with_retry

# Socrata's documented per-request ceiling for SoQL queries. Both NYC
# datasets come back inside one page of this size; see the module docstring
# for why the loop is written for the day one does not.
PAGE_SIZE = 50000


def dataset_url(domain: str, dataset_id: str, extension: str = "geojson") -> str:
    """The SODA resource URL for one dataset.

    Assembled rather than stored so an entry in sources.json carries the two
    facts that identify a dataset - the portal it is on and its four-four id
    - instead of a URL whose shape a reader has to parse back into them.
    """
    return f"https://{domain}/resource/{dataset_id}.{extension}"


def fetch_dataset_geojson(
    domain: str,
    dataset_id: str,
    *,
    where: str | None = None,
    page_size: int | None = None,
) -> dict:
    """Fetch every row of a Socrata dataset as a GeoJSON FeatureCollection.

    `where` is a SoQL predicate applied BY THE PORTAL, which is the point:
    NYC DOT's bike layer is 29,695 rows of which 3,039 are the current
    off-street greenway this project may draw as a walking path, and
    filtering at the source means the other 26,656 are never fetched, never
    written to disk and never available to be drawn by mistake. A filter
    that lives in the registry entry is also a filter a reviewer can read
    without running anything.

    `page_size` resolves against the module constant in the BODY rather than
    in the signature, so a test monkeypatching `socrata.PAGE_SIZE` still
    reaches it - the same note lib/arcgis.py and lib/http_retry.py carry for
    the same reason.
    """
    url = dataset_url(domain, dataset_id)
    records = PAGE_SIZE if page_size is None else page_size
    features: list[dict] = []
    offset = 0
    while True:
        params = {
            "$limit": records,
            "$offset": offset,
            # See the module docstring: without this, $offset is not safe.
            "$order": ":id",
        }
        if where:
            params["$where"] = where
        resp = request_with_retry(url, params=params, timeout=120)
        batch = resp.json().get("features", [])
        if not batch:
            break
        features.extend(batch)
        offset += len(batch)
    return {"type": "FeatureCollection", "features": features}


def fetch_dataset_to_file(
    domain: str,
    dataset_id: str,
    out_path: Path,
    *,
    where: str | None = None,
    page_size: int | None = None,
) -> int:
    """Fetch a dataset and write it to out_path as GeoJSON. Returns feature count."""
    fc = fetch_dataset_geojson(domain, dataset_id, where=where, page_size=page_size)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fc))
    return len(fc["features"])


def get_dataset_updated_at(domain: str, dataset_id: str) -> int | None:
    """A dataset's `rowsUpdatedAt` (epoch SECONDS), or None if it has none.

    Socrata's analog of ArcGIS `editingInfo.dataLastEditDate`, and the change
    marker fetch_external_layers.py compares between runs. The units differ
    from ArcGIS's - seconds here, milliseconds there - which is why the
    manifest records the marker's `kind` beside its value rather than a bare
    number that two sources would spell incompatibly.

    IT IS THE ROW TIMESTAMP, NOT THE VIEW'S. `viewLastModified` moves when
    somebody edits the dataset's DESCRIPTION, and `rowsUpdatedAt` moves when
    the data moves; reading the wrong one would re-fetch on a typo fix and
    skip on a real update. Measured on NYC Parks Trails 2026-09-15: both read
    2026-09-03, so the two are indistinguishable on that day's evidence and
    the choice rests on Socrata's documented meaning rather than on a
    measurement here. @unvalidated - what would settle it is watching one
    dataset across a metadata-only edit, which nobody has done.
    """
    resp = request_with_retry(
        f"https://{domain}/api/views/{dataset_id}.json",
        timeout=30,
    )
    updated = resp.json().get("rowsUpdatedAt")
    return int(updated) if updated is not None else None
