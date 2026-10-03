"""Fixture mode: the real extract, over canned upstream answers, into a warehouse for CI's dbt job.

    python -m extract._fixtures --raw-dir <fixtures> --warehouse <warehouse.duckdb>

ELT.md, "Fixture mode", is the design. CI has no fetched data and may not
fetch any (TESTING.md), so this runs the extract's own resources over canned
answers: the change checks, the ArcGIS and Socrata pagers, the column hints,
dlt's normalize and naming, the run check and the committed-load read. What a
staging model reads in CI is then a table dlt wrote.

LAYER FILES. make_dbt_fixtures.py writes one GeoJSON file per layer, each
property name one sources.json records as measured against the live layer
(its docstring's "Nothing here is invented"). FixtureAdapter serves each file
as its server would: an ArcGIS layer's metadata, `returnCountOnly` count and
GeoJSON pages; a Socrata dataset's `count(*)` and `:id`-ordered pages;
opentrail's feed. A layer's `fields` are the file's property names, typed by
the fixture's own values (integer, float, else string), because no file
records the live layer's types. A field null on every fixture row is typed
string, the safest guess for a column nobody has seen a value in (Reasoned).

REVIEWED FILES run as they are: their upstream is a file in git under
pipeline/reference/ (the podcast episodes, the POI identity ledger, ATC's
reviewed Trail Updates, and each club's folder of challenge files, one row
per file through ReviewedDir), so CI reads the real thing.

OTHER UPSTREAMS are answered from what make_dbt_fixtures.py writes, so the
suggested_hikes, closures and warnings marts build in CI (stage 3 of #1793 —
Rebuild the data platform as dlt → dbt: seven contracted marts, a monthly
refresh, published docs, and lighter phone downloads). Only the transport,
the HTTP session or the Postgres connection, is swapped:
- NYNJTC's Hike Finder export (hikefinder/): the listing, pages and GPX at
  `hikes.php`, `hike.php?id=<id>` and `download_gpx.php?id=<id>`, so
  PublishedHikes' listing guard, parse and GPX check run;
- NWS's /alerts/active body (conditions/), for lib/nws_alerts.py's
  ALERTS_URL, so check_response(), the column hints and the count-as-proof run;
- NYNJTC's WordPress routes (conditions/): the category lookup by slug, the
  posts and the four place taxonomies, with X-WP-Total and X-WP-TotalPages,
  so wp_list()'s paging, the change check's marker, WP_DROPPED and the terms'
  empty-vocabulary refusal run;
- OurHike's Postgres (conditions/), through FixtureConnection, which answers
  ConditionsQuery's SQL (reader_problem()'s four catalog questions, the
  LIMIT 0 description, the count(*) and the rows), so reader_problem()'s
  decision, POSTGRES_TYPES, the count-as-proof and the WITHHELD_COLUMNS
  refusal run;
- ATC's website (TEXT_FIXTURES): the trail-updates sitemap and each update's
  page, so AtcTrailUpdatePages' sitemap parse, lib/atc_scrape.py's
  parse_update() and the slug count as proof run. The same file carries the
  listing pages fetch_atc_updates.py walks, which parity.py serves to
  today's fetcher;
- a guide published as web pages (the guide_pages kind), page by page from
  guide_pages/<key>/, so its own parser reads NYNJTC's skeleton;
- each page or feed notice (extract/_notices.py's PageNotice and FeedNotices),
  from conditions/notices/<key>.json: `{"answers": {url: {"content_type",
  "body"}}}`, served by exact URL as TEXT_FIXTURES are, so each reader's fetch,
  region, title, stated date and hash run. Their hosts' Crawl-delays and the
  readers' two-second gap are not waited out here, since no host is asked;
- each JSON API notice source (extract/_json_apis.py: NPS's alerts and road
  events, PA DCNR's advisories, USGS's volcanoes, TEHCC's wiki, FoOT's sheet
  and FMST's map), from conditions/json_apis/<key>.json: a list of answers,
  each a URL without its query, the query parameters it must carry, and the
  body, so a reader's paging, count and person-column rules run. NPS's key is
  set to a placeholder for the build, since no request leaves the process.

WHAT FIXTURE MODE DOES NOT EXERCISE for Postgres, so nobody reads a green
dbt job as evidence of it: the query text itself. The rows are the queries'
answers as the fixture states them, so the moderation predicates, the
90-day and five-per-place windows, the two-account dispute rule and the
ORDER BY run only against a real database (tests/test_extract_conditions*,
and backend/tests/test_conditions_publisher_contract.py for the column
lists). The catalog's answers are canned too: the table exists, the reader
may select, and row-level security is off, which is the CI database's case.

A fetched resource whose key has no fixture file is left out, because CI
fetches nothing. An unknown URL raises, so a resource that reaches past its
fixture fails loudly rather than reaching the network, and so does any SQL
FixtureConnection does not recognise.
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
from extract import _json_apis, _kinds, _notices
from extract._contract import all_resources, discover, discover_shared
from extract._kinds import (
    CONDITIONS_QUERIES,
    ArcgisLayer,
    AtcTrailUpdatePages,
    ConditionsQuery,
    FeedNotices,
    GuidePages,
    NwsAlerts,
    OpentrailFeed,
    PageNotice,
    PublishedHikes,
    ReviewedDir,
    ReviewedFile,
    SocrataDataset,
    WordpressPosts,
    WordpressTerms,
    registry_entry,
)
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
# A guide's pages (make_dbt_fixtures.py's _long_path_guide_fixtures()): one
# folder per registry key, its pages.json mapping each URL the guide_pages kind
# asks for to the HTML file that answers it.
GUIDE_PAGES_DIR = "guide_pages"
NWS_FIXTURE = "nws_alerts.json"
POSTGRES_FIXTURE = "ourhike_postgres.json"
# A website's pages, by the registry key they are read for: `{"answers": {url:
# {"content_type": ..., "body": ...}}}`, served as the site would serve them.
TEXT_FIXTURES = {"atc_trail_updates": "atc_trail_updates.json"}
# The JSON API notice sources' answers (make_dbt_fixtures.py's _json_api_fixtures()),
# one file per registry key: `{"answers": [{"url", "query", "content_type", "body"}]}`.
JSON_API_DIR = "json_apis"
# The page and feed notices' answers (make_dbt_fixtures.py), one file per registry key, the TEXT_FIXTURES
# shape: `{"answers": {url: {"content_type": ..., "body": ...}}}`.
NOTICES_DIR = "notices"
JSON_API_KINDS = (
    _json_apis.NpsAlerts,
    _json_apis.NpsRoadEvents,
    _json_apis.DcnrParkAdvisories,
    _json_apis.UsgsElevatedVolcanoes,
    _json_apis.MediawikiAnnouncements,
    _json_apis.SheetCsvSegments,
    _json_apis.MyMapsPlacemarks,
)
# What NPS_API_KEY holds while fixture mode runs, when the environment has none.
FIXTURE_NPS_KEY = "fixture-mode-key"


def text_answers(document: dict) -> dict[str, tuple[str, str]]:
    """A text fixture's pages as {url: (content type, body)}, the shape FixtureAdapter serves."""
    return {url: (answer["content_type"], answer["body"]) for url, answer in document["answers"].items()}


# The Hike Finder's answers (make_dbt_fixtures.py's suggested_hikes_fixtures()):
# the listing, `hike-<id>.html` per page and `track-<id>.gpx` per GPX.
HIKEFINDER_DIR = "hikefinder"


def fixture_file(raw_dir: Path, key: str) -> Path | None:
    """The GeoJSON file make_dbt_fixtures.py wrote for a key, or None."""
    for candidate in (raw_dir / FILE_NAMES.get(key, f"{key}.geojson"), raw_dir / "external" / f"{key}.geojson"):
        if candidate.exists():
            return candidate
    return None


HIKEFINDER_HTML = "text/html; charset=UTF-8"
HIKEFINDER_GPX = "application/gpx+xml"


def hikefinder_answers(raw_dir: Path, base: str) -> dict[str, tuple[str, str]] | None:
    """{URL: (content type, body)} for the Hike Finder export at `base`, from make_dbt_fixtures.py's files, or None
    when it wrote none: the listing and each page as HTML, each track as GPX, the shape FixtureAdapter's `pages` holds."""
    folder = raw_dir / HIKEFINDER_DIR
    if not (folder / "hikes.html").exists():
        return None
    answers = {base + "hikes.php": (HIKEFINDER_HTML, (folder / "hikes.html").read_text())}
    for page in sorted(folder.glob("hike-*.html")):
        answers[f"{base}hike.php?id={page.stem.removeprefix('hike-')}"] = (HIKEFINDER_HTML, page.read_text())
    for track in sorted(folder.glob("track-*.gpx")):
        answers[f"{base}download_gpx.php?id={track.stem.removeprefix('track-')}"] = (HIKEFINDER_GPX, track.read_text())
    return answers


def conditions_fixture(raw_dir: Path, name: str) -> dict | None:
    """One of the conditions/ answers make_dbt_fixtures.py wrote, parsed, or None."""
    path = raw_dir / CONDITIONS_DIR / name
    return json.loads(path.read_text()) if path.exists() else None


# The declared column types whose values _row() hands back as datetimes, as
# psycopg does. FixtureConnection reports each fixture column's declared type
# name as its type, so POSTGRES_TYPES maps it as it maps a real one.
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


def _esri_feature(feature: dict, keep_z: bool) -> dict:
    """A fixture's GeoJSON feature as ArcGIS answers it under f=json: attributes, and an Esri geometry.

    The shapes lib/arcgis.py's esri_feature_to_geojson converts back, which are
    the shapes a Z-enabled fixture layer has: points, multipoints and lines.
    """
    geometry = feature.get("geometry")

    def vertex(coordinates: list) -> list:
        return list(coordinates[:3] if keep_z else coordinates[:2])

    if geometry is None:
        esri = None
    elif geometry["type"] == "Point":
        esri = dict(zip(("x", "y", "z"), vertex(geometry["coordinates"]), strict=False))
    elif geometry["type"] == "MultiPoint":
        esri = {"points": [vertex(point) for point in geometry["coordinates"]]}
    elif geometry["type"] == "LineString":
        esri = {"paths": [[vertex(point) for point in geometry["coordinates"]]]}
    elif geometry["type"] == "MultiLineString":
        esri = {"paths": [[vertex(point) for point in path] for path in geometry["coordinates"]]}
    else:
        raise ValueError(f"fixture mode answers no {geometry['type']} as Esri JSON")
    return {"attributes": feature.get("properties") or {}, "geometry": esri}


def _response(request, body, status: int = 200, headers: dict | None = None) -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response._content = b"" if body is None else json.dumps(body).encode()
    response.headers = CaseInsensitiveDict(headers or {})
    response.headers.setdefault("Content-Type", "application/json")
    response.url, response.request, response.encoding = request.url, request, "utf-8"
    return response


def _text_response(request, content_type: str, body: str) -> requests.Response:
    """A page or a file as a site serves it, its own bytes and content type, not JSON: ATC's pages, and the Hike
    Finder's HTML and GPX."""
    response = _response(request, None, headers={"Content-Type": content_type})
    response._content = body.encode("utf-8")
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
        pages: dict[str, tuple[str, str]] | None = None,
        routed: list[dict] | None = None,
    ):
        super().__init__()
        self.arcgis, self.socrata, self.feeds = arcgis, socrata, feeds
        # The JSON API sources' answers (JSON_API_DIR): the first whose `url` is the
        # request's without its query, and whose `query` the request's query holds.
        self.routed = routed or []
        # A WordPress site's REST root -> its answers: categories, posts, and terms by taxonomy.
        self.wordpress = wordpress or {}
        # NWS's /alerts/active body.
        self.nws = nws
        # Text served by exact URL as (content type, body): ATC's Trail Updates
        # pages (text_answers()), the Hike Finder export (hikefinder_answers())
        # and a guide's pages (fixture_resources()).
        self.pages = pages or {}

    def send(self, request, **kwargs):
        if request.url in self.pages:
            return _text_response(request, *self.pages[request.url])
        parts = urlsplit(request.url)
        base = f"{parts.scheme}://{parts.netloc}{parts.path}"
        query = {name: values[0] for name, values in parse_qs(parts.query, keep_blank_values=True).items()}
        if request.method == "POST" and request.body:
            # lib/arcgis.py's query_page() sends a page query as a POST form once its GET URL would pass
            # GET_URL_LIMIT (a layer with 120 fields asks for each by name), and a server reads the form as
            # it reads a query string; without this, every page of such a layer answers as offset 0.
            body = request.body.decode() if isinstance(request.body, bytes) else request.body
            query.update({name: values[0] for name, values in parse_qs(body, keep_blank_values=True).items()})
        if self.nws is not None and base == NWS_ALERTS_URL:
            return _response(request, self.nws, headers={"Content-Type": "application/geo+json"})
        for answer in self.routed:
            if base == answer["url"] and all(query.get(name) == value for name, value in (answer.get("query") or {}).items()):
                return _text_response(request, answer["content_type"], answer["body"])
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
        page = features[offset : offset + size]
        if query.get("f") == "json":
            # A layer registered with `return_z` asks for Esri JSON, because f=geojson drops Z
            # (lib/arcgis.py's iter_layer_pages); a server keeps the Z only when returnZ asks.
            keep_z = query.get("returnZ") == "true"
            return {"features": [_esri_feature(feature, keep_z) for feature in page]}
        return {"type": "FeatureCollection", "features": page}

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
    arcgis, socrata, feeds, wordpress, pages, routed, chosen = {}, {}, {}, {}, {}, [], []
    nws, postgres = conditions_fixture(raw_dir, NWS_FIXTURE), conditions_fixture(raw_dir, POSTGRES_FIXTURE)
    for resource in all_resources(discover() + discover_shared()):
        if isinstance(resource, ReviewedFile | ReviewedDir):
            chosen.append(resource)  # a committed file, or a folder of them, is its own fixture
            continue
        if isinstance(resource, JSON_API_KINDS):
            document = conditions_fixture(raw_dir, f"{JSON_API_DIR}/{resource.key}.json")
            if document is not None:
                routed.extend(document["answers"])
                chosen.append(resource)
            continue
        if isinstance(resource, FeedNotices | PageNotice):
            # A page or feed notice, served by exact URL; one with no file (a PDF, which needs pypdf) stays out.
            document = conditions_fixture(raw_dir, f"{NOTICES_DIR}/{resource.key}.json")
            if document is not None:
                pages.update(text_answers(document))
                chosen.append(resource)
            continue
        if isinstance(resource, AtcTrailUpdatePages):
            document = conditions_fixture(raw_dir, TEXT_FIXTURES[resource.key])
            if document is not None:
                pages.update(text_answers(document))
                chosen.append(resource)
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
        if isinstance(resource, PublishedHikes):
            answers = hikefinder_answers(raw_dir, registry_entry(resource.key)["url"].rstrip("/") + "/")
            if answers is not None:
                pages.update(answers)
                chosen.append(resource)
            continue
        if isinstance(resource, GuidePages):
            # Served page by page from the folder's pages.json; a guide with no folder stays out.
            folder = raw_dir / GUIDE_PAGES_DIR / resource.key
            if (folder / "pages.json").exists():
                for url, name in json.loads((folder / "pages.json").read_text()).items():
                    pages[url] = ("text/html; charset=UTF-8", (folder / name).read_text(encoding="utf-8"))
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
    return chosen, FixtureAdapter(arcgis, socrata, feeds, wordpress=wordpress, nws=nws, pages=pages, routed=routed)


def build(raw_dir: Path, warehouse: Path, store: Path) -> dict[str, int]:
    """Run every lane over the fixtures into a `file://` store under `store`, then load the warehouse. Returns {table: rows}."""
    # Imported here, not at the top: parity.py's old sides (today's exporters)
    # import FixtureConnection and FixtureAdapter under requirements.txt's
    # pins, which hold no dlt and no pyarrow (measured 2026-10-02: with every
    # package requirements.txt does not pin blocked, `import dlt` stopped the
    # closures, reports and atc_updates old sides).
    from extract._run import LANES, lane_resources, make_pipeline, run_pipeline
    from extract._warehouse import load_warehouse

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
    # No host is asked anything here, so ATC's Crawl-delay and the Hike
    # Finder's 10 s a request, both the live hosts' asks, are set to 0 and
    # restored below.
    crawl_delay, real_throttle = _kinds.ATC_CRAWL_DELAY_SECONDS, _kinds.HIKEFINDER_THROTTLE_SECONDS
    _kinds.ATC_CRAWL_DELAY_SECONDS, _kinds.HIKEFINDER_THROTTLE_SECONDS = 0, 0
    polite_gap, nps_key_was = _json_apis.POLITE_GAP_SECONDS, os.environ.get(_json_apis.NPS_API_KEY_ENV)
    _json_apis.POLITE_GAP_SECONDS = 0
    # The notice readers' per-host gap (extract/_notices.py's polite()) waits in _pause; nothing waits here.
    real_pause = _notices._pause
    _notices._pause = lambda seconds: None
    # The NPS readers refuse to run without a key (Unavailable). No request leaves
    # the process here, so a placeholder stands in when the environment has none.
    os.environ.setdefault(_json_apis.NPS_API_KEY_ENV, FIXTURE_NPS_KEY)
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
        _kinds.ATC_CRAWL_DELAY_SECONDS = crawl_delay
        _kinds.psycopg = real_psycopg
        _kinds.HIKEFINDER_THROTTLE_SECONDS = real_throttle
        _json_apis.POLITE_GAP_SECONDS = polite_gap
        _notices._pause = real_pause
        if nps_key_was is None:
            os.environ.pop(_json_apis.NPS_API_KEY_ENV, None)
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
