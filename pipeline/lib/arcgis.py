"""Shared fetcher for ArcGIS FeatureServer layers.

Handles pagination via resultOffset since ArcGIS servers cap how many
features they'll return per request (maxRecordCount).
"""

import json
from pathlib import Path

import requests

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
        resp = requests.get(query_url, params=params, timeout=60)
        resp.raise_for_status()
        batch = resp.json().get("features", [])
        if not batch:
            break
        features.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
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
    resp = requests.get(layer_url, params={"f": "json"}, timeout=30)
    resp.raise_for_status()
    editing_info = resp.json().get("editingInfo")
    if not editing_info:
        return None
    return editing_info.get("dataLastEditDate")
