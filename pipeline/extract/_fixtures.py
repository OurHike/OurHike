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

THE REVIEWED FILES RUN AS THEY ARE. Their upstream is a file in git under
pipeline/reference/, so CI reads the real thing: the podcast episodes, the
POI identity ledger, ATC's reviewed Trail Updates and the rest, and each
club's folder of challenge files (ReviewedDir), one row per file.

THE HOURLY LANE'S OTHER UPSTREAMS ARE ANSWERED TOO, so the closures and
warnings marts build in CI (#1793, stage 3). make_dbt_fixtures.py writes one
answer for each under conditions/, and only the transport is swapped:
- NWS's /alerts/active body is served for lib/nws_alerts.py's ALERTS_URL, so
  check_response(), the column hints and the count-as-proof all run;
- NYNJTC's WordPress routes (the category lookup by slug, the posts, the four
  place taxonomies) are served with X-WP-Total and X-WP-TotalPages, so
  wp_list()'s paging, the change check's marker, WP_DROPPED and the terms'
  empty-vocabulary refusal all run;
- OurHike's Postgres is a stand-in connection (FixtureConnection) that answers
  the SQL ConditionsQuery sends: reader_problem()'s four catalog questions,
  the LIMIT 0 description its column hints come from, the count(*) that is
  its proof, and the rows. reader_problem()'s decision, POSTGRES_TYPES, the
  count-as-proof and the WITHHELD_COLUMNS refusal all run.
WHAT FIXTURE MODE DOES NOT EXERCISE for Postgres, so nobody reads a green
dbt job as evidence of it: the query text itself. The rows are the queries'
answers as the fixture states them, so the moderation predicates, the
90-day and five-per-place windows, the two-account dispute rule and the
ORDER BY run only against a real database (tests/test_extract_conditions*,
and backend/tests/test_conditions_publisher_contract.py for the column
lists). The catalog's answers are canned too: the table exists, the reader
may select, and row-level security is off, which is the CI database's case.

What is left out of the run, and why:
- every fetched resource whose key has no fixture file, because CI fetches
  nothing.

An unknown URL raises, so a resource that reaches past its fixture fails
loudly rather than reaching the network, and so does any SQL the stand-in
connection does not recognise.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import duckdb
import requests
from requests.structures import CaseInsensitiveDict

import export_conditions
from extract import _kinds
from extract._contract import all_resources, discover, discover_shared
from extract._kinds import (
    CONDITIONS_QUERIES,
    ArcgisLayer,
    ConditionsQuery,
    NwsAlerts,
    OpentrailFeed,
    ReviewedDir,
    ReviewedFile,
    SocrataDataset,
    WordpressPosts,
    WordpressTerms,
    registry_entry,
)
from extract._run import LANES, lane_resources, make_pipeline, run_pipeline
from extract._warehouse import load_warehouse
from lib.nws_alerts import ALERTS_URL as NWS_ALERTS_URL
from lib.socrata import dataset_url

FIXTURE_ETAG = '"fixture"'
MAX_RECORD_COUNT = 1000
# opentrail's file is named for its table, raw_opentrail__at, not for a registry key.
FILE_NAMES = {"at": "opentrail_at.geojson"}

# The hourly lane's answers that are not layer files (make_dbt_fixtures.py's
# closures_and_warnings_fixtures()): one file per upstream, under conditions/.
# A WordPress source's file is named for its registry key.
CONDITIONS_DIR = "conditions"
NWS_FIXTURE = "nws_alerts.json"
POSTGRES_FIXTURE = "ourhike_postgres.json"


def fixture_file(raw_dir: Path, key: str) -> Path | None:
    """The GeoJSON file make_dbt_fixtures.py wrote for a key, or None."""
    for candidate in (raw_dir / FILE_NAMES.get(key, f"{key}.geojson"), raw_dir / "external" / f"{key}.geojson"):
        if candidate.exists():
            return candidate
    return None


def conditions_fixture(raw_dir: Path, name: str) -> dict | None:
    """One of the conditions/ answers make_dbt_fixtures.py wrote, parsed, or None."""
    path = raw_dir / CONDITIONS_DIR / name
    return json.loads(path.read_text()) if path.exists() else None


# Postgres type names as the stand-in connection reports them: each fixture
# column's declared type, so POSTGRES_TYPES maps it as it maps a real one.
TIMESTAMP_TYPES = frozenset({"timestamp", "timestamptz"})


class FixtureCursor:
    """A psycopg cursor's surface as ConditionsQuery and reader_problem() use it: execute, fetchone, fetchall, description."""

    def __init__(self, connection: FixtureConnection):
        self.connection = connection
        self.description: list = []
        self._rows: list = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql: str, params=None):
        self.description, self._rows = self.connection.answer(sql)
        return self

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class FixtureConnection:
    """OurHike's Postgres for fixture mode: answers the SQL ConditionsQuery sends from make_dbt_fixtures.py's rows.

    Only the connection is a stand-in. The SQL it recognises is the extract's
    own text (export_conditions.py's catalog questions and PUBLIC_*_SQL,
    wrapped as _kinds.py wraps them), and anything else raises, so a change to
    what the extract asks fails here rather than passing on a canned answer.
    """

    def __init__(self, document: dict):
        self.document = document
        self.adapters = SimpleNamespace(types=SimpleNamespace(get=lambda type_code: SimpleNamespace(name=type_code)))
        self.queries = {sql.strip(): key for key, (_table, sql) in CONDITIONS_QUERIES.items()}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, row_factory=None) -> FixtureCursor:
        return FixtureCursor(self)

    def execute(self, sql: str, params=None) -> FixtureCursor:
        return FixtureCursor(self).execute(sql, params)

    def _artifact(self, sql: str) -> dict:
        key = self.queries.get(sql.strip())
        if key is None or key not in self.document:
            raise RuntimeError(f"fixture mode's Postgres has no answer for {sql.strip()[:80]!r}")
        return self.document[key]

    def answer(self, sql: str) -> tuple[list, list]:
        """(description, rows) for one statement, as psycopg would return them."""
        text = sql.strip()
        catalog = {
            export_conditions.TABLE_EXISTS_SQL.strip(): True,
            export_conditions.MAY_SELECT_SQL.strip(): True,
            export_conditions.RLS_ENABLED_SQL.strip(): False,
            export_conditions.POLICY_COUNT_SQL.strip(): 0,
        }
        if text in catalog:
            return [], [(catalog[text],)]
        if text == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ":
            return [], []
        for prefix, suffix, kind in (
            ("SELECT * FROM (", ") AS public_rows LIMIT 0", "describe"),
            ("SELECT count(*) FROM (", ") AS public_rows", "count"),
        ):
            if text.startswith(prefix) and text.endswith(suffix):
                artifact = self._artifact(text[len(prefix) : -len(suffix)])
                if kind == "describe":
                    return self._description(artifact), []
                return [], [(len(artifact["rows"]),)]
        artifact = self._artifact(text)
        return self._description(artifact), [self._row(artifact, row) for row in artifact["rows"]]

    @staticmethod
    def _description(artifact: dict) -> list:
        return [SimpleNamespace(name=name, type_code=type_name) for name, type_name in artifact["columns"]]

    @staticmethod
    def _row(artifact: dict, row: dict) -> dict:
        """A row as psycopg hands it back: timestamps as datetimes, naive as the columns are, and every column present."""
        values = {}
        for name, type_name in artifact["columns"]:
            value = row.get(name)
            values[name] = datetime.fromisoformat(value) if type_name in TIMESTAMP_TYPES and value is not None else value
        return values


class FixturePsycopg:
    """Stands in for the psycopg module inside extract/_kinds.py while fixture mode runs."""

    def __init__(self, document: dict):
        self.document = document

    def connect(self, url: str, **kwargs) -> FixtureConnection:
        return FixtureConnection(self.document)


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

    def __init__(
        self,
        arcgis: dict[str, list],
        socrata: dict[tuple[str, str], list],
        feeds: dict[str, list],
        wordpress: dict[str, dict] | None = None,
        nws: dict | None = None,
    ):
        super().__init__()
        self.arcgis, self.socrata, self.feeds = arcgis, socrata, feeds
        # A WordPress site's REST root -> its answers: categories, posts, and terms by taxonomy.
        self.wordpress = wordpress or {}
        # NWS's /alerts/active body.
        self.nws = nws

    def send(self, request, **kwargs):
        parts = urlsplit(request.url)
        base = f"{parts.scheme}://{parts.netloc}{parts.path}"
        query = {name: values[0] for name, values in parse_qs(parts.query, keep_blank_values=True).items()}
        if self.nws is not None and base == NWS_ALERTS_URL:
            return _response(request, self.nws, headers={"Content-Type": "application/geo+json"})
        for api, document in self.wordpress.items():
            if base.startswith(api + "/"):
                return self._wordpress(request, document, base[len(api) + 1 :], query)
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
    def _wordpress(request, document: dict, route: str, query: dict) -> requests.Response:
        """One WordPress list route, paged and counted as WordPress does: `per_page`, `page`, `_fields`, X-WP-Total."""
        if route == "categories":
            items = [term for term in document["categories"] if "slug" not in query or term.get("slug") == query["slug"]]
        elif route == "posts":
            category = int(query["categories"]) if "categories" in query else None
            items = [post for post in document["posts"] if category is None or category in (post.get("categories") or [])]
        elif route in document["terms"]:
            items = document["terms"][route]
        else:
            raise requests.ConnectionError(f"fixture mode has no WordPress route {route!r}")
        if query.get("_fields"):
            fields = query["_fields"].split(",")
            items = [{name: item[name] for name in fields if name in item} for item in items]
        per_page, page = int(query.get("per_page", 10)), int(query.get("page", 1))
        pages = max(1, -(-len(items) // per_page))
        if route == "posts" and page > pages:
            # What nynjtc.org answers past the last page of posts (measured 2026-10-01, _kinds.py's wp_list).
            return _response(request, {"code": "rest_post_invalid_page_number"}, status=400)
        headers = {"X-WP-Total": str(len(items)), "X-WP-TotalPages": str(pages)}
        return _response(request, items[(page - 1) * per_page : page * per_page], headers=headers)

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
    arcgis, socrata, feeds, wordpress, chosen = {}, {}, {}, {}, []
    nws, postgres = conditions_fixture(raw_dir, NWS_FIXTURE), conditions_fixture(raw_dir, POSTGRES_FIXTURE)
    for resource in all_resources(discover() + discover_shared()):
        if isinstance(resource, ReviewedFile | ReviewedDir):
            chosen.append(resource)  # a committed file, or a folder of them, is its own fixture
            continue
        if isinstance(resource, NwsAlerts):
            if nws is not None:
                chosen.append(resource)
            continue
        if isinstance(resource, ConditionsQuery):
            # Served by FixtureConnection in build(); an artifact the file does not answer stays out.
            if postgres is not None and resource.key in postgres:
                chosen.append(resource)
            continue
        if isinstance(resource, WordpressPosts | WordpressTerms):
            document = conditions_fixture(raw_dir, f"{resource.key}.json")
            if document is not None:
                wordpress[resource.api] = document
                chosen.append(resource)
            continue
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
    return chosen, FixtureAdapter(arcgis, socrata, feeds, wordpress=wordpress, nws=nws)


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
    # OurHike's Postgres, swapped at the connection and nowhere else: ConditionsQuery
    # still asks export_conditions.connection_url() first, which refuses an unset
    # URL, so fixture mode names one that no real driver could reach.
    real_psycopg, url_was = _kinds.psycopg, os.environ.get(export_conditions.URL_ENV_VAR)
    postgres = conditions_fixture(raw_dir, POSTGRES_FIXTURE)
    _kinds.session = fixture_session
    if postgres is not None:
        _kinds.psycopg = FixturePsycopg(postgres)
        os.environ[export_conditions.URL_ENV_VAR] = "postgresql://fixture-mode.invalid/none"
    try:
        for lane in LANES:
            if lane_resources(lane, resources):
                run_pipeline(lane, bucket_url, resources=resources, pipelines_dir=pipelines_dir)
    finally:
        _kinds.session = real_session
        _kinds.psycopg = real_psycopg
        if postgres is not None:
            if url_was is None:
                os.environ.pop(export_conditions.URL_ENV_VAR, None)
            else:
                os.environ[export_conditions.URL_ENV_VAR] = url_was
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
