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


def fetch_layer_geojson(layer_url: str) -> dict:
    """Fetch every feature from an ArcGIS FeatureServer/MapServer layer as GeoJSON."""
    query_url = layer_url.rstrip("/") + "/query"
    features = []
    offset = 0
    while True:
        params = {
            "where": "1=1",
            "outFields": "*",
            "outSR": 4326,
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE,
        }
        resp = request_with_retry(query_url, params=params, timeout=60)
        batch = resp.json().get("features", [])
        if not batch:
            break
        features.extend(batch)
        offset += len(batch)
    return {"type": "FeatureCollection", "features": features}


def fetch_layer_to_file(layer_url: str, out_path: Path) -> int:
    """Fetch a layer and write it to out_path as GeoJSON. Returns feature count."""
    fc = fetch_layer_geojson(layer_url)
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
