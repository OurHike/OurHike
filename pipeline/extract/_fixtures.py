"""Fixture mode: the real extract, over canned upstream answers, into a warehouse for CI's dbt job.

    python -m extract._fixtures --raw-dir <fixtures> --warehouse <warehouse.duckdb>

ELT.md, "Fixture mode", is the design: CI has no fetched data and may not
fetch any (TESTING.md), so the dbt job's warehouse used to come from
make_dbt_fixtures.py's GeoJSON files through load_raw.py, which shaped every
table the way no extract run ever would. This runs the extract's own
resources instead: the change checks, the ArcGIS and Socrata pagers, the
column hints, dlt's normalize and naming, the run check, the committed-load
read. What a staging model reads in CI is then a table dlt wrote.

THE ANSWERS COME FROM THE SAME FILES. make_dbt_fixtures.py still writes one
GeoJSON file per layer, and every property name in it is one sources.json
records as measured against the live layer (its docstring's "Nothing here is
invented"). FixtureAdapter serves each file the way its server would: an
ArcGIS layer's metadata, `returnCountOnly` count and GeoJSON pages; a
Socrata dataset's `count(*)` and `:id`-ordered pages; opentrail's feed. A
layer's `fields` are the file's property names, and the TYPES are read off
the fixture's own values (an integer, a float, otherwise a string), because
no file records the live layer's types. A field that is null on every
fixture row is typed as a string, the safest guess for a column nobody has
seen a value in (Reasoned).

What is left out of the run, and why:
- every resource whose key has no fixture file, because CI fetches nothing;
- OurHike's conditions queries and the reviewed files: no Postgres in the
  dbt job, and the reviewed files are not what staging reads yet.

An unknown URL raises, so a resource that reaches past its fixture fails
loudly rather than reaching the network.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import duckdb
import requests
from requests.structures import CaseInsensitiveDict

from extract import _kinds
from extract._contract import all_resources, discover, discover_shared
from extract._kinds import ArcgisLayer, OpentrailFeed, SocrataDataset, registry_entry
from extract._run import LANES, lane_resources, make_pipeline, run_pipeline
from extract._warehouse import load_warehouse
from lib.socrata import dataset_url

FIXTURE_ETAG = '"fixture"'
MAX_RECORD_COUNT = 1000
# opentrail's file is named for its table, raw_opentrail__at, not for a registry key.
FILE_NAMES = {"at": "opentrail_at.geojson"}


def fixture_file(raw_dir: Path, key: str) -> Path | None:
    """The GeoJSON file make_dbt_fixtures.py wrote for a key, or None."""
    for candidate in (raw_dir / FILE_NAMES.get(key, f"{key}.geojson"), raw_dir / "external" / f"{key}.geojson"):
        if candidate.exists():
            return candidate
    return None


def esri_type(values: list) -> str:
    """The ArcGIS field type the fixture's own values imply. Booleans are not ArcGIS types, so they read as integers."""
    present = [value for value in values if value is not None]
    if present and all(isinstance(value, int) for value in present):
        return "esriFieldTypeInteger"
    if present and all(isinstance(value, (int, float)) for value in present):
        return "esriFieldTypeDouble"
    return "esriFieldTypeString"


def layer_metadata(features: list[dict]) -> dict:
    """An ArcGIS layer's `?f=json` answer for these features: their property names, typed by their values."""
    names: list[str] = []
    for feature in features:
        for name in feature.get("properties") or {}:
            if name not in names:
                names.append(name)
    fields = [{"name": name, "type": esri_type([(f.get("properties") or {}).get(name) for f in features])} for name in names]
    oid = "OBJECTID" if "OBJECTID" in names else None
    return {"objectIdField": oid, "fields": fields, "maxRecordCount": MAX_RECORD_COUNT}


def _response(request, body, status: int = 200, headers: dict | None = None) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = b"" if body is None else json.dumps(body).encode()
    response.headers = CaseInsensitiveDict(headers or {})
    response.headers.setdefault("Content-Type", "application/json")
    response.url, response.request, response.encoding = request.url, request, "utf-8"
    return response


class FixtureAdapter(requests.adapters.BaseAdapter):
    """Answers a session's requests from fixture features, as the upstream's own server would."""

    def __init__(self, arcgis: dict[str, list], socrata: dict[tuple[str, str], list], feeds: dict[str, list]):
        super().__init__()
        self.arcgis, self.socrata, self.feeds = arcgis, socrata, feeds

    def send(self, request, **kwargs):
        parts = urlsplit(request.url)
        base = f"{parts.scheme}://{parts.netloc}{parts.path}"
        query = {name: values[0] for name, values in parse_qs(parts.query, keep_blank_values=True).items()}
        if base in self.arcgis:
            if request.headers.get("If-None-Match") == FIXTURE_ETAG:
                return _response(request, None, 304)
            return _response(request, layer_metadata(self.arcgis[base]), headers={"ETag": FIXTURE_ETAG})
        if base.endswith("/query") and base[: -len("/query")] in self.arcgis:
            return _response(request, self._arcgis_query(self.arcgis[base[: -len("/query")]], query))
        if (base, query.get("$where", "")) in self.socrata:
            return _response(request, self._socrata(base, self.socrata[(base, query.get("$where", ""))], query))
        if base in self.feeds:
            return _response(request, {"type": "FeatureCollection", "features": self.feeds[base]}, headers={"ETag": FIXTURE_ETAG})
        raise requests.ConnectionError(f"fixture mode has no answer for {request.url}")

    @staticmethod
    def _arcgis_query(features: list[dict], query: dict) -> dict:
        if query.get("returnCountOnly") == "true":
            return {"count": len(features)}
        if "outStatistics" in query:
            return {"features": []}  # no statistics in fixture mode, so the on-prem check answers UNKNOWN and fetches
        offset = int(query.get("resultOffset", 0))
        size = min(int(query.get("resultRecordCount", MAX_RECORD_COUNT)), MAX_RECORD_COUNT)
        return {"type": "FeatureCollection", "features": features[offset : offset + size]}

    @staticmethod
    def _socrata(base: str, features: list[dict], query: dict):
        if base.endswith(".json"):
            return [{"n": str(len(features)), "updated": None}]
        offset, limit = int(query.get("$offset", 0)), int(query.get("$limit", MAX_RECORD_COUNT))
        page = [
            {**feature, "id": feature.get("id") or f"row-{offset + n}"}
            for n, feature in enumerate(features[offset : offset + limit])
        ]
        return {"type": "FeatureCollection", "features": page}

    def close(self):
        pass


def fixture_resources(raw_dir: Path) -> tuple[list, FixtureAdapter]:
    """The extract's own resources that have a fixture file, and the adapter that answers them."""
    arcgis, socrata, feeds, chosen = {}, {}, {}, []
    for resource in all_resources(discover() + discover_shared()):
        path = fixture_file(raw_dir, resource.key)
        if path is None:
            continue
        features = json.loads(path.read_text())["features"]
        if isinstance(resource, ArcgisLayer):
            arcgis[resource.url] = features
        elif isinstance(resource, SocrataDataset):
            # Keyed on the entry's `where` as well: NYC's paths and park drives are two
            # slices of one Centerline dataset, told apart only by it.
            entry = registry_entry(resource.key)
            for extension in ("json", "geojson"):
                socrata[(dataset_url(entry["domain"], entry["dataset_id"], extension), resource.where or "")] = features
        elif isinstance(resource, OpentrailFeed):
            feeds[_kinds.OPENTRAIL_API_URL] = features
        else:
            continue
        chosen.append(resource)
    return chosen, FixtureAdapter(arcgis, socrata, feeds)


def build(raw_dir: Path, warehouse: Path, store: Path) -> dict[str, int]:
    """Run every lane over the fixtures into a `file://` store under `store`, then load the warehouse. Returns {table: rows}."""
    # Resolved, because CI passes paths relative to pipeline/, and a file:// URI must be absolute.
    raw_dir, warehouse, store = raw_dir.resolve(), warehouse.resolve(), store.resolve()
    resources, adapter = fixture_resources(raw_dir)
    if not resources:
        raise SystemExit(f"no fixture file in {raw_dir} matches an extract resource; run make_dbt_fixtures.py first")
    real_session = _kinds.session

    def fixture_session() -> requests.Session:
        named = real_session()
        named.mount("https://", adapter)
        named.mount("http://", adapter)
        return named

    bucket_url, pipelines_dir = (store / "raw-store").as_uri(), str(store / "pipelines")
    _kinds.session = fixture_session
    try:
        for lane in LANES:
            if lane_resources(lane, resources):
                run_pipeline(lane, bucket_url, resources=resources, pipelines_dir=pipelines_dir)
    finally:
        _kinds.session = real_session
    counts: dict[str, int] = {}
    with duckdb.connect(str(warehouse)) as con:
        for lane in LANES:
            counts.update(load_warehouse(con, make_pipeline(lane, bucket_url, pipelines_dir)))
    return counts


def main(argv: list[str] | None = None) -> dict[str, int]:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--raw-dir", type=Path, required=True, help="where make_dbt_fixtures.py wrote its files")
    parser.add_argument("--warehouse", type=Path, required=True)
    parser.add_argument("--store", type=Path, help="the file:// raw store and dlt state; defaults beside the warehouse")
    args = parser.parse_args(argv)
    counts = build(args.raw_dir, args.warehouse, args.store or args.warehouse.parent / "fixture-store")
    print(f"{len(counts)} tables, {sum(counts.values())} rows, into {args.warehouse}")
    return counts


if __name__ == "__main__":
    main()
