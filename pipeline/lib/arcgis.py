"""Shared fetcher for ArcGIS FeatureServer layers.

Handles pagination via resultOffset since ArcGIS servers cap how many
features they'll return per request (maxRecordCount).

Every request goes through lib/http_retry (#659): this module used to do
bare requests.get, so one transient ATC 5xx failed a whole fetch_all run -
the exact failure shape http_retry was extracted for (#536), sitting one
directory away from the module that never called it.
"""

import json
from pathlib import Path

from lib.http_retry import request_with_retry

PAGE_SIZE = 1000


def fetch_layer_geojson(
    layer_url: str,
    *,
    out_fields: str = "*",
    geometry_precision: int | None = None,
    page_size: int | None = None,
) -> dict:
    """Fetch every feature from an ArcGIS FeatureServer/MapServer layer as GeoJSON.

    THE STOP CONDITION IS AN EMPTY PAGE, and never a short one. A page
    shorter than what was asked for is not proof there is no more data - a
    server whose own `maxRecordCount` sits below the requested size returns
    short pages the whole way through. This loop used to stop on a short
    page and did skip data; `tests/test_lib_arcgis.py` holds both regression
    tests. The cost of getting it right is one extra request per layer that
    comes back empty, which is the correct thing to buy.

    THE QUERY SHAPE IS THE CALLER'S (#1295), because there was a second
    implementation of this loop in `publish-conditions.yml` whose only reason
    to exist was that it needed a different one - geometry only, at reduced
    precision, in bigger pages. Its stop condition trusted
    `exceededTransferLimit`, which is the early exit the tests above exist to
    prevent, so the fix was to make this function able to answer that
    caller rather than to keep two loops.

    `page_size` resolves against the module constant in the BODY rather than
    in the signature, so a test monkeypatching `arcgis.PAGE_SIZE` still
    reaches it - a default bound at definition time would have captured the
    original forever. `lib/http_retry.py`'s `sleep` argument carries the same
    note for the same reason.
    """
    query_url = layer_url.rstrip("/") + "/query"
    records = PAGE_SIZE if page_size is None else page_size
    features = []
    offset = 0
    while True:
        params = {
            "where": "1=1",
            "outFields": out_fields,
            "outSR": 4326,
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": records,
        }
        if geometry_precision is not None:
            params["geometryPrecision"] = geometry_precision
        resp = request_with_retry(query_url, params=params, timeout=60)
        batch = resp.json().get("features", [])
        if not batch:
            break
        features.extend(batch)
        offset += len(batch)
    return {"type": "FeatureCollection", "features": features}


def fetch_layer_to_file(
    layer_url: str,
    out_path: Path,
    *,
    out_fields: str = "*",
    geometry_precision: int | None = None,
    page_size: int | None = None,
) -> int:
    """Fetch a layer and write it to out_path as GeoJSON. Returns feature count."""
    fc = fetch_layer_geojson(
        layer_url,
        out_fields=out_fields,
        geometry_precision=geometry_precision,
        page_size=page_size,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fc))
    return len(fc["features"])


def get_layer_edit_date(layer_url: str) -> int | None:
    """Fetch a layer's dataLastEditDate (epoch ms) - a cheap metadata-only
    request, used to skip re-fetching layers that haven't changed. Returns
    None if the service doesn't expose editingInfo (some don't)."""
    resp = request_with_retry(layer_url, params={"f": "json"}, timeout=30)
    editing_info = resp.json().get("editingInfo")
    if not editing_info:
        return None
    return editing_info.get("dataLastEditDate")


def get_field_coded_domain(layer_url: str, field_name: str) -> dict[int, str] | None:
    """Fetch a layer's field metadata and return field_name's coded-value
    domain as a {code: label} dict - e.g. side_trails' `Blaze` field, so its
    0-9 color codes are decoded from the service's own metadata rather than
    hand-copied (see features/TRAIL_BLAZE_COLORS.md). Returns None if the
    field isn't found, has no domain, or has a non-coded domain (e.g. a
    numeric range domain)."""
    resp = request_with_retry(layer_url, params={"f": "json"}, timeout=30)
    fields = resp.json().get("fields", [])
    for field in fields:
        if field.get("name") == field_name:
            domain = field.get("domain")
            if domain and domain.get("type") == "codedValue":
                return {cv["code"]: cv["name"] for cv in domain.get("codedValues", [])}
            return None
    return None


def get_layer_max_field(layer_url: str, field_name: str) -> str | None:
    """The layer's `max(field_name)`, as one statistics query, or None.

    The substitute change marker for a layer whose server exposes no
    `editingInfo` (#1311). An on-prem ArcGIS server - NYS DEC's, the Forest
    Service's - answers `get_layer_edit_date` with None, and until this
    existed that meant the layer was re-fetched on every run: 21,470
    back-country features for DEC alone, unchanged since 2026-08-18 by the
    field this reads. `sources.json` records the field per entry as
    `freshness.kind: arcgis_max_field`, with the measurement that chose it.

    Returned as a STRING, whatever the server's type, because the value is
    only ever compared verbatim against the one recorded on the last fetch -
    the same rule lib/freshness_state.compare_marker keeps for every other
    marker, so an epoch-millisecond integer and its JSON round-trip cannot
    manufacture a change.

    None when the server returns no statistics row, which the caller reads
    as "no marker" and fetches. Never rounded to "unchanged".
    """
    query_url = layer_url.rstrip("/") + "/query"
    statistics = [{"statisticType": "max", "onStatisticField": field_name, "outStatisticFieldName": "marker"}]
    params = {"where": "1=1", "outStatistics": json.dumps(statistics), "f": "json"}
    resp = request_with_retry(query_url, params=params, timeout=30)
    features = resp.json().get("features") or []
    if not features:
        return None
    value = (features[0].get("attributes") or {}).get("marker")
    return None if value is None else str(value)


def get_service_etag(url: str) -> str | None:
    """The ETag a HEAD on `url` answers with, or None if it answers none.

    The other substitute marker (#1311): the Forest Service's EDW server has
    no `editingInfo` AND no date column, so the only thing that can move
    when its data does is the ETag on the service description document.
    `sources.json` tags that as @unvalidated - an ETag on the METADATA has
    not been shown to move when the FEATURES do - which is why the caller
    records both sides of every comparison rather than trusting this alone.

    Compared verbatim, weak validators included: the question is only
    "did it move", exactly as check_freshness.py asks ATC's feed.
    """
    resp = request_with_retry(url, method="head", timeout=30)
    return resp.headers.get("ETag")
