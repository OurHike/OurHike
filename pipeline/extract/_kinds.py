"""One builder per source kind: what a club file calls to declare a resource.

Every builder takes a KEY and never a URL. The URL, the field names, the
filter and the change marker come from the key's sources.json entry, so a club
file cannot fetch an upstream the registry does not register, and an upstream
has one home (pipeline/ELT.md, "One home: sources.json, trail_orgs.json, the
club file").

Nothing here imports dlt. A builder yields plain rows and says what its columns
are; extract/_run.py wraps each one in a dlt resource. That keeps the layout
test, which imports every club file, free of the run machinery, and keeps one
place deciding the dlt settings every resource shares.

The kinds built so far for stage 2 (#1793 — Rebuild the data platform as dlt → dbt):

    arcgis_layer(key)       an ArcGIS FeatureServer or MapServer layer
    socrata_dataset(key)    a Socrata dataset, under the entry's own `where`
    wordpress_posts(key)    one WordPress category's posts (NYNJTC's Trail Alerts)
    wordpress_terms(key, t) that site's taxonomy terms, daily, for dbt to resolve
    guide_pages(key)        a guide published as web pages, one row per section
    published_hikes(key)    the Hike Finder export, one row per hike, GPX as served
    club_pdf(key)           a club's PDF, one row per row its lib/club_pdfs.py parser reads
    opentrail_feed()        opentrail.org's A.T. waypoints, comments left out (no registry row)
    hydrography_watch(key)  the usgs_3dhp watch: 3DHP's work units at five probes on the trail
    bucket_listing(key)     a public S3 bucket's objects under one prefix (3DEP's tiles, NHD's GeoPackages)
    nws_alerts()            every active NWS alert, read in full each hour (no registry row)
    conditions_query(key)   one of OurHike's own conditions artifacts, from Postgres, through the bake's own query
    reviewed_input(key)     a registry entry whose rows a person reviews into a
                            file in git (ATC's Trail Updates), loaded from that file
    reviewed_file(path)     a reviewed pipeline/reference/ file with no registry
                            row of its own (water_distance.json)
    reviewed_dir(path)      a folder of reviewed files, one row per file (a
                            club's challenges)
    podcast_feed(key)       a podcast's RSS feed, one row per episode
    catalogue_row()         the club's own trail_orgs.json row, for org.py
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin, urlparse

import psycopg
import requests
from psycopg.rows import dict_row

import export_conditions
from check_freshness import CORRIDOR_PROBES
from extract._contract import EXTRACT_DIR, PIPELINE_DIR, Resource, Unavailable, read_club_file, slug_for_folder
from fetch_club_pdfs import extract_page_texts
from fetch_elevation import TILE_URL_TEMPLATE as DEM_TILE_URL_TEMPLATE
from fetch_hikefinder import sign_in as hikefinder_sign_in
from fetch_opentrail import API_URL as OPENTRAIL_API_URL
from fetch_opentrail import strip_comments as strip_opentrail_comments
from lib.arcgis import iter_layer_pages, layer_count
from lib.club_pdfs import PARSERS as CLUB_PDF_PARSERS
from lib.freshness_state import Freshness, compare_marker
from lib.hikefinder import DETAIL_PATH as HIKEFINDER_DETAIL_PATH
from lib.hikefinder import GPX_PATH as HIKEFINDER_GPX_PATH
from lib.hikefinder import LISTING_PATH as HIKEFINDER_LISTING_PATH
from lib.hikefinder import as_cache_entry as as_hike_row
from lib.hikefinder import listing_count as hikefinder_listing_count
from lib.hikefinder import listing_ids as hikefinder_listing_ids
from lib.hikefinder import parse_gpx, parse_hike
from lib.http_retry import request_with_retry
from lib.nhd import NHD_GPKG_URL
from lib.nws_alerts import ACCEPT as NWS_ACCEPT
from lib.nws_alerts import ALERTS_URL as NWS_ALERTS_URL
from lib.nws_alerts import check_response as check_nws_response
from lib.nynjtc_long_path_guide import parse_index as parse_guide_index
from lib.nynjtc_long_path_guide import parse_section as parse_guide_section
from lib.socrata import dataset_url, fetch_dataset_geojson
from lib.source_registry import PODCAST_FEED, load_registry, source_kind
from lib.user_agent import USER_AGENT

REGISTRY_PATH = PIPELINE_DIR / "sources.json"
TRAIL_ORGS_PATH = PIPELINE_DIR / "reference" / "trail_orgs.json"
REFERENCE_DIR = PIPELINE_DIR / "reference"

# Fields that name or reach a person, which never load, whatever the licence
# (ELT.md, "Who may publish", rule 8). Dropped inside the resource, before dlt
# sees the row, so no copy exists in the raw store to leak; never filtered in
# dbt. Compared case-insensitively against each layer's own field names.
#
# The list is the ones the coverage audit read off live layers (2026-10-01):
# Forest Ranger Contact's RANGER, PHONE_CELL, PHONE_ALT, EMAIL, SUPERVISOR and
# SUPERVIS_1, and the Central Iowa Trail Association status API's
# updateByDisplay. It is a denylist, so it is only as complete as the layers
# somebody has read: a new layer with a person field under another name loads
# it until the name is added here. That is the known weakness of a denylist,
# and the reason a new registry row is reviewed field by field.
PERSON_FIELDS = frozenset(
    name.lower()
    for name in (
        "RANGER",
        "PHONE_CELL",
        "PHONE_ALT",
        "EMAIL",
        "SUPERVISOR",
        "SUPERVIS_1",
        "updateByDisplay",
    )
)

# ArcGIS field types -> dlt data types. Hinting every column from the layer's
# own `fields` is what makes a column that is null on every row exist at all
# (dlt creates no column it never saw a value for; measured 2026-10-01, ELT.md
# "dlt configuration requirements"). Dates arrive as epoch milliseconds and
# stay integers here; the base model converts them.
ESRI_TYPES = {
    "esriFieldTypeOID": "bigint",
    "esriFieldTypeInteger": "bigint",
    "esriFieldTypeSmallInteger": "bigint",
    "esriFieldTypeBigInteger": "bigint",
    "esriFieldTypeDouble": "double",
    "esriFieldTypeSingle": "double",
    "esriFieldTypeString": "text",
    "esriFieldTypeGUID": "text",
    "esriFieldTypeGlobalID": "text",
    "esriFieldTypeDate": "bigint",
    "esriFieldTypeDateOnly": "text",
    "esriFieldTypeTimeOnly": "text",
    "esriFieldTypeTimestampOffset": "text",
}

# ArcGIS Online hosts its layers on servicesN.arcgis.com. Everything else is
# an ArcGIS Server somebody runs, whose ETags hash the response body and so
# never move when the features do (ELT.md, "The skip-unchanged check, by
# platform": identical ETags for identical bodies on DEC, USFS EDW and NPS,
# measured 2026-10-01).
AGOL_HOST = re.compile(r"^services\d*\.arcgis\.com$")


def session() -> requests.Session:
    """A session that names the project on every request, page and count included.

    Every request sends lib/user_agent.py's USER_AGENT, on every host, and
    never a browser's (decision 39): an operator should see who is asking from
    one line of their log, and a host that refuses our own named agent has
    refused us. lib/arcgis.py's fetchers send requests' default agent today;
    this one does not.
    """
    named = requests.Session()
    named.headers["User-Agent"] = USER_AGENT
    return named


@lru_cache(maxsize=4)
def _registry(path: Path) -> dict:
    return {entry["key"]: entry for entry in load_registry(path).get("sources", [])}


def registry_entry(key: str) -> dict:
    entry = _registry(REGISTRY_PATH).get(key)
    if entry is None:
        raise KeyError(f"{key} is not a sources.json key; a builder takes a registered key, never a URL")
    return entry


def _canonical(marker: dict) -> str:
    return json.dumps(marker, sort_keys=True)


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass(frozen=True)
class ArcgisLayer(Resource):
    """An ArcGIS FeatureServer or MapServer layer, read whole through lib/arcgis.py's own loop.

    Pages come from `lib.arcgis.iter_layer_pages`, the loop every fetcher
    already uses - stop on an empty page, advance by rows returned, halve a
    page the server refuses (#1790) - and the read is held to the server's own
    `returnCountOnly` count afterwards (#1730). ELT.md's first draft named
    dlt's `rest_api` source here; it is not used, because its OffsetPaginator
    steps by `limit` and a second pager is what #1295 took out.
    """

    @property
    def entry(self) -> dict:
        return registry_entry(self.key)

    @property
    def url(self) -> str:
        return self.entry["url"].rstrip("/")

    @property
    def where(self) -> str:
        return self.entry.get("where") or "1=1"

    @property
    def platform(self) -> str:
        return "agol" if AGOL_HOST.match(urlparse(self.url).hostname or "") else "onprem"

    @property
    def may_be_empty(self) -> bool:
        return super().may_be_empty or bool(self.entry.get("may_be_empty"))

    @property
    def schema_contract(self) -> dict:
        """New columns are welcome; a column whose type changes is refused at normalize.

        Without `freeze`, a mistyped value splits into a variant column
        (`code__v_text`) that no staging model reads (ELT.md, measured on the
        #1363 spike).
        """
        return {"columns": "evolve", "data_type": "freeze"}

    def metadata(self) -> dict:
        return request_with_retry(self.url, session=session(), params={"f": "json"}, timeout=30).json()

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        try:
            if self.platform == "agol":
                return self._agol_check(recorded)
            return self._onprem_check(recorded)
        except (requests.RequestException, ValueError, KeyError) as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None

    def _agol_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """A conditional GET on the layer's metadata: a 304 means FRESH.

        On ArcGIS Online the layer document's validators move with the layer's
        data version: 304 on 30 of 30 layers repeated, and the layer's
        `Last-Modified` equals `editingInfo.lastEditDate` (measured
        2026-10-01, ELT.md). A user-maintained `Edit_Date` field is never the
        marker: ATC's shelters max at 2023-03-02 against a layer edit of
        2026-08-14.
        """
        headers = {}
        if recorded:
            if recorded.get("etag"):
                headers["If-None-Match"] = recorded["etag"]
            if recorded.get("last_modified"):
                headers["If-Modified-Since"] = recorded["last_modified"]
        response = request_with_retry(self.url, session=session(), params={"f": "json"}, headers=headers or None, timeout=30)
        if response.status_code == 304:
            return Freshness.FRESH, recorded
        marker = {"etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified")}
        if not marker["etag"] and not marker["last_modified"]:
            return Freshness.UNKNOWN, None
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def _onprem_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """One statistics query: count and max of the object id, plus the maintained date.

        A delete lowers the count and an add raises max(OID); the maintained
        date sees an edit in place (ELT.md). With no maintained date declared
        in the entry's `freshness.field`, an attribute-only edit moves none of
        those, so the answer is UNKNOWN and the layer is read in full every
        run: a false-stale costs a read, a false-fresh keeps a rerouted line
        on a phone. ELT.md's per-page conditional read, which would let such a
        layer skip, is not built yet.
        """
        date_field = (self.entry.get("freshness") or {}).get("field")
        if not date_field:
            return Freshness.UNKNOWN, None
        oid = self.metadata().get("objectIdField") or "OBJECTID"
        statistics = [
            {"statisticType": "count", "onStatisticField": oid, "outStatisticFieldName": "n"},
            {"statisticType": "max", "onStatisticField": oid, "outStatisticFieldName": "max_oid"},
            {"statisticType": "max", "onStatisticField": date_field, "outStatisticFieldName": "max_date"},
        ]
        response = request_with_retry(
            self.url + "/query",
            session=session(),
            params={"where": self.where, "outStatistics": json.dumps(statistics), "f": "json"},
            timeout=30,
        )
        features = response.json().get("features") or []
        if not features:
            return Freshness.UNKNOWN, None
        attributes = features[0].get("attributes") or {}
        marker = {name: attributes.get(name) for name in ("n", "max_oid", "max_date")}
        if any(value is None for value in marker.values()):
            return Freshness.UNKNOWN, None
        marker = {name: str(value) for name, value in marker.items()}
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def column_hints(self) -> dict:
        hints = {"geometry": {"data_type": "json"}}
        for field in self.metadata().get("fields") or []:
            name = field.get("name")
            data_type = ESRI_TYPES.get(field.get("type"))
            if name and data_type and name.lower() not in PERSON_FIELDS:
                hints[name] = {"data_type": data_type}
        return hints

    def rows(self, proofs: dict[str, int]):
        """Every feature, as properties plus a `geometry` column, after the read is held to the server's count.

        The whole layer is read before the first row is yielded, so a short
        read raises before dlt has anything to normalize, and a failed page
        leaves nothing half-written.
        """
        named = session()
        fields = [field.get("name") for field in self.metadata().get("fields") or [] if field.get("name")]
        kept = [name for name in fields if name.lower() not in PERSON_FIELDS]
        # Person fields are left out of the field list asked for, so they never
        # cross the wire; "*" only when the layer has none to leave out.
        out_fields = "*" if len(kept) == len(fields) else ",".join(kept)
        pages = iter_layer_pages(self.url, where=self.where, out_fields=out_fields, session=named)
        features = [feature for page in pages for feature in page]
        count = layer_count(self.url + "/query", where=self.where, session=named)
        if count is not None:
            if len(features) < count:
                raise RuntimeError(f"{self.key}: the server counts {count} features and {len(features)} were read")
            proofs[self.table] = count
        for feature in features:
            row = {name: value for name, value in (feature.get("properties") or {}).items() if name.lower() not in PERSON_FIELDS}
            row["geometry"] = feature.get("geometry")
            yield row


def arcgis_layer(key: str, **overrides) -> ArcgisLayer:
    registry_entry(key)  # a key that is not registered fails at import, in the layout test, not mid-run
    return ArcgisLayer(key=key, **overrides)


@dataclass(frozen=True)
class SocrataDataset(Resource):
    """A Socrata dataset read as GeoJSON through lib/socrata.py's own loop, under the entry's `where`.

    The `where` is a SoQL predicate the portal applies, and it is the one
    filter that runs before dbt here: NYC DOT's bike network is about 29,700
    rows, of which the entry's predicate keeps the off-street greenways
    (lib/socrata.py). Pages come from `fetch_dataset_geojson`, ordered on
    `:id` so an offset is safe, and the read is held to the portal's own
    `count(*)` under the same `where` afterwards, the Socrata half of ELT.md's
    "an allowed zero counts only with the upstream's own count".
    """

    @property
    def entry(self) -> dict:
        return registry_entry(self.key)

    @property
    def where(self) -> str | None:
        return self.entry.get("where") or None

    def _soql(self, select: str) -> dict:
        params = {"$select": select}
        if self.where:
            params["$where"] = self.where
        url = dataset_url(self.entry["domain"], self.entry["dataset_id"], extension="json")
        rows = request_with_retry(url, session=session(), params=params, timeout=60).json()
        return rows[0] if rows else {}

    def count(self) -> int | None:
        value = self._soql("count(*) as n").get("n")
        return int(value) if value is not None else None

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """`count(*)` and `max(:updated_at)` under the entry's own `where`, with the `where` text kept.

        Measured 2026-10-01 (ELT.md, "The skip-unchanged check, by platform"):
        SODA ignores `If-None-Match`, `viewLastModified` is wrong in both
        directions, and `rowsUpdatedAt` is dataset-wide, so `nyc_park_drives`'
        filtered rows max at 2026-08-16 while the dataset reads 2026-09-26. A
        delete lowers the count (Reasoned). The `where` is in the marker because
        tightening a filter changes the rows while every date stays put.
        """
        try:
            answer = self._soql("count(*) as n, max(:updated_at) as updated")
        except (requests.RequestException, ValueError, KeyError, IndexError) as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        if answer.get("n") is None or answer.get("updated") is None:
            return Freshness.UNKNOWN, None
        marker = {"n": str(answer["n"]), "max_updated_at": str(answer["updated"]), "where": self.where or ""}
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def rows(self, proofs: dict[str, int]):
        """Every row under the `where`, as properties plus `geometry` and Socrata's `:id` as `_socrata_id`.

        Read whole before the first row is yielded, as ArcgisLayer does, so a
        short read raises before dlt normalizes anything.
        """
        collection = fetch_dataset_geojson(self.entry["domain"], self.entry["dataset_id"], where=self.where, session=session())
        features = collection["features"]
        count = self.count()
        if count is not None:
            if len(features) < count:
                raise RuntimeError(f"{self.key}: the portal counts {count} rows and {len(features)} were read")
            proofs[self.table] = count
        for feature in features:
            row = {name: value for name, value in (feature.get("properties") or {}).items() if name.lower() not in PERSON_FIELDS}
            row["_socrata_id"] = feature.get("id")
            row["geometry"] = feature.get("geometry")
            yield row


def socrata_dataset(key: str, **overrides) -> SocrataDataset:
    entry = registry_entry(key)
    if not entry.get("domain") or not entry.get("dataset_id"):
        raise KeyError(f"{key} has no domain and dataset_id in sources.json")
    return SocrataDataset(key=key, **overrides)


# WordPress lists cap `per_page` at 100 and page the rest; a short page is the
# last one. MAX_PAGES is a ceiling, so a misbehaving site cannot spin a run
# forever, and reaching it raises rather than loading a truncated list.
WP_PAGE_SIZE = 100
WP_MAX_PAGES = 20
# Taxonomy terms are refreshed once a day, riding the hourly lane when due:
# a renamed term does not touch a post's `modified` (ELT.md, "Every node
# carries its cadence"; Reasoned).
TERMS_CADENCE_REASON = "a renamed term does not touch a post's modified, so terms are read daily (ELT.md)"


def _wp_api(entry: dict) -> str:
    """The site's REST root, at the origin of the page the registry row names for a person."""
    parsed = urlparse(entry["url"])
    return f"{parsed.scheme}://{parsed.netloc}/wp-json/wp/v2"


def wp_list(api: str, route: str, params: dict, http: requests.Session) -> tuple[list, int | None]:
    """Every page of a WordPress list route, and the site's own `X-WP-Total` for it.

    Stops at `X-WP-TotalPages` as well as on a short page: a list of exactly
    100 fills page 1, and the posts route answers a page past the last with
    HTTP 400 `rest_post_invalid_page_number` (measured on NYNJTC 2026-10-01;
    its taxonomy routes answer 200 and an empty list instead).
    """
    collected, total = [], None
    for page in range(1, WP_MAX_PAGES + 1):
        response = request_with_retry(
            f"{api}/{route}", session=http, params={"per_page": WP_PAGE_SIZE, "page": page, **params}, timeout=60
        )
        if total is None and response.headers.get("X-WP-Total") is not None:
            total = int(response.headers["X-WP-Total"])
        batch = response.json()
        if not isinstance(batch, list):
            raise ValueError(f"{route} answered {type(batch).__name__}, not a list: the site's API has changed shape")
        collected.extend(batch)
        last_page = response.headers.get("X-WP-TotalPages")
        if len(batch) < WP_PAGE_SIZE or (last_page is not None and page >= int(last_page)):
            return collected, total
    raise RuntimeError(f"{route}: still paging at {WP_MAX_PAGES} pages, which is a ceiling rather than an ending")


@dataclass(frozen=True)
class WordpressPosts(Resource):
    """One WordPress category's posts, a row each, from the site's REST API.

    The registry row's `url` is the category page a person reads
    (`/category/<slug>/`); the REST root is that page's origin plus
    `/wp-json/wp/v2`, and the category's id is looked up by its slug each run,
    so a renumbered category is a refused run rather than an empty one. Posts
    land as WordPress serves them, `title` and `content` still rendered, with
    their taxonomy ids: the terms are their own daily table
    (`wordpress_terms`), resolved in dbt (ELT.md, "Source kinds").
    """

    @property
    def entry(self) -> dict:
        return registry_entry(self.key)

    @property
    def api(self) -> str:
        return _wp_api(self.entry)

    @property
    def category_slug(self) -> str:
        parts = [part for part in urlparse(self.entry["url"]).path.split("/") if part]
        if len(parts) < 2 or parts[-2] != "category":
            raise KeyError(f"{self.key}: url is not a /category/<slug>/ page: {self.entry['url']}")
        return parts[-1]

    def category_id(self, http: requests.Session) -> int:
        found, _ = wp_list(self.api, "categories", {"slug": self.category_slug, "_fields": "id,slug"}, http)
        ids = [term["id"] for term in found if term.get("slug") == self.category_slug]
        if len(ids) != 1:
            raise RuntimeError(f"{self.key}: category {self.category_slug!r} resolves to {len(ids)} ids")
        return ids[0]

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """A hash of the category's (id, modified) set, and its `X-WP-Total`.

        One small request: `_fields=id,modified_gmt,slug`. An unpublished post
        leaves the set, so a lifted closure moves the marker. The site's feed
        ETag and `Last-Modified` are site-wide (GATC's alerts and events feeds
        returned the same validator, measured 2026-10-01), so no feed validator
        ever decides FRESH here.
        """
        try:
            http = session()
            posts, total = wp_list(
                self.api, "posts", {"categories": self.category_id(http), "_fields": "id,modified_gmt,slug"}, http
            )
        except (requests.RequestException, ValueError, KeyError, RuntimeError) as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        if total is None:
            return Freshness.UNKNOWN, None
        pairs = sorted((post.get("id"), post.get("modified_gmt")) for post in posts)
        marker = {"total": str(total), "set_sha256": hashlib.sha256(json.dumps(pairs).encode()).hexdigest()}
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def rows(self, proofs: dict[str, int]):
        http = session()
        posts, total = wp_list(self.api, "posts", {"categories": self.category_id(http)}, http)
        if total is not None:
            if len(posts) < total:
                raise RuntimeError(f"{self.key}: the site counts {total} posts and {len(posts)} were read")
            proofs[self.table] = total
        for post in posts:
            yield {name: value for name, value in post.items() if name not in WP_DROPPED and name.lower() not in PERSON_FIELDS}


# Fields a post carries that are WordPress plumbing or name a person. `author`
# is a user id that resolves to a person, and Yoast's SEO blocks
# (`yoast_head`, `yoast_head_json`) spell that person's name out ("Written
# by"); `_links` is the API's own hypermedia. Read off NYNJTC's 18 posts,
# 2026-10-01.
WP_DROPPED = frozenset(
    {
        "author",
        "_links",
        "guid",
        "ping_status",
        "comment_status",
        "template",
        "meta",
        "yoast_head",
        "yoast_head_json",
        "class_list",
    }
)


@dataclass(frozen=True)
class WordpressTerms(Resource):
    """The site's place taxonomies' terms, a row each with its taxonomy: the lookup a post's ids resolve against.

    Its own table, `<posts table>_terms`, and its own daily cadence (a
    renamed term moves no post). The taxonomies are the registry row's
    `taxonomies`, or lib/nynjtc_alerts.py's PLACE_TAXONOMIES, which NYNJTC's
    fetcher reads today.
    """

    taxonomies: tuple[str, ...] = ()

    @property
    def table(self) -> str:
        return super().table + "_terms"

    @property
    def part(self) -> str:
        return "terms"

    @property
    def api(self) -> str:
        return _wp_api(registry_entry(self.key))

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """Always read when due: four small lists, once a day, cost less than a marker that could lie."""
        return Freshness.UNKNOWN, None

    def rows(self, proofs: dict[str, int]):
        http = session()
        rows, totals = [], []
        for taxonomy in self.taxonomies:
            terms, total = wp_list(self.api, taxonomy, {"_fields": "id,name,slug,count"}, http)
            if not terms:
                # An empty vocabulary is a route that stopped answering in the shape
                # expected, not a site that tags nothing (fetch_nynjtc_alerts.py's rule).
                raise RuntimeError(f"{self.key}: the {taxonomy!r} taxonomy came back empty, which is a broken read")
            if total is not None and len(terms) < total:
                raise RuntimeError(f"{self.key}: {taxonomy} counts {total} terms and {len(terms)} were read")
            totals.append(total)
            rows.extend({**term, "taxonomy": taxonomy} for term in terms)
        if all(total is not None for total in totals):
            proofs[self.table] = sum(totals)
        yield from rows


def wordpress_posts(key: str, **overrides) -> WordpressPosts:
    resource = WordpressPosts(key=key, **overrides)
    resource.category_slug  # a url that is not a category page fails at import, in the layout test
    return resource


def wordpress_terms(key: str, taxonomies: tuple[str, ...], **overrides) -> WordpressTerms:
    registry_entry(key)
    if not taxonomies:
        raise ValueError(f"{key}: wordpress_terms needs the taxonomies a post is tagged from")
    overrides.setdefault("cadence_override", "daily")
    overrides.setdefault("cadence_reason", TERMS_CADENCE_REASON)
    return WordpressTerms(key=key, taxonomies=tuple(taxonomies), **overrides)


# fetch_nynjtc_long_path_guide.py's throttle, one request every half second.
# nynjtc.org's robots.txt answered 200 and empty on 2026-10-01, so it asks
# for no crawl delay.
GUIDE_THROTTLE_SECONDS = 0.5

# The parsers a guide's pages are read with, by registry key. A guide is HTML
# written for people, so each one needs its own reading; a key with none here
# cannot be built.
GUIDE_PARSERS = {"nynjtc_long_path_guide": (parse_guide_index, parse_guide_section)}


@dataclass(frozen=True)
class GuidePages(Resource):
    """A guide an organization publishes as web pages: one row per section, as the guide's parser reads it.

    The registry row's `url` is the guide's index; each section page it links
    is read and parsed (ELT.md, "Source kinds": an HTML parse is extraction,
    rule SH01). A page the parser does not recognise raises, so a run never
    lands the sections that still happened to parse. Each row keeps the
    page's own sha256 beside the parse; the page's bytes go to the as-sent
    copy, which is not built yet.
    """

    @property
    def parsers(self):
        return GUIDE_PARSERS[self.key]

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """UNKNOWN: there is no cheap marker, so the monthly lane reads the guide whole.

        NYNJTC serves neither validator on these pages (read 2026-09-08), and
        every body differs on every render, by a WordPress gallery's random
        `galleryId` (fetch_nynjtc_long_path_guide.py). What moves is the
        parse, and seeing it means reading every page.
        """
        return Freshness.UNKNOWN, None

    def rows(self, proofs: dict[str, int]):
        parse_index, parse_section = self.parsers
        http = session()
        index = request_with_retry(registry_entry(self.key)["url"], session=http, timeout=60).text
        pages = parse_index(index)
        if not pages:
            raise RuntimeError(f"{self.key}: the index links no section page, which is a broken read")
        sections = []
        for number, url in pages:
            time.sleep(GUIDE_THROTTLE_SECONDS)
            html = request_with_retry(url, session=http, timeout=60, retryable_statuses=(429, 500, 502, 503, 504)).text
            section = parse_section(html, url, expected_number=number)
            sections.append({**section.to_dict(), "page_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest()})
        proofs[self.table] = len(pages)
        yield from sections


def guide_pages(key: str, **overrides) -> GuidePages:
    registry_entry(key)
    if key not in GUIDE_PARSERS:
        raise KeyError(f"{key}: no guide parser is registered in extract/_kinds.py's GUIDE_PARSERS")
    return GuidePages(key=key, **overrides)


# The Hike Finder's host asks for this: robots.txt `Crawl-delay: 10`, read
# 2026-10-01. fetch_hikefinder.py sends two a second; this layer does as the
# host asks, so its 385 pages and 113 tracks take about 83 minutes on the
# monthly lane (ELT.md, "The skip-unchanged check, by platform").
HIKEFINDER_THROTTLE_SECONDS = 10


@dataclass(frozen=True)
class PublishedHikes(Resource):
    """NYNJTC's hike write-ups through the Hike Finder export, one row per hike as lib/hikefinder.py parses it.

    The listing names every hike and states its own total, which is the
    proof the run check holds the rows to; a listing whose links and stated
    total disagree raises, as fetch_hikefinder.py refuses it. A hike with a
    published track carries the GPX as served in `gpx`, never as parsed
    points, because the track is somebody's survey and a later parse may want
    what this one did not keep. The export is behind a site password, read
    from HIKEFINDER_PASSWORD (Extract's credential table in ELT.md); with no
    password the listing is a login form, links no hike, and the run raises
    rather than landing an empty table.
    """

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """UNKNOWN: `hikes.php` serves neither an ETag nor a Last-Modified and there is no feed (measured 2026-09-15)."""
        return Freshness.UNKNOWN, None

    def _get(self, http: requests.Session, url: str) -> str:
        return request_with_retry(url, session=http, timeout=60, throttle_seconds=HIKEFINDER_THROTTLE_SECONDS).text

    def rows(self, proofs: dict[str, int]):
        base = registry_entry(self.key)["url"].rstrip("/") + "/"
        http = session()
        signed_in = hikefinder_sign_in(http, base)
        listing = self._get(http, urljoin(base, HIKEFINDER_LISTING_PATH))
        ids = hikefinder_listing_ids(listing)
        if not ids:
            hint = "the password was refused or the form changed" if signed_in else "no HIKEFINDER_PASSWORD was set"
            raise RuntimeError(f"{self.key}: the listing links no hike ({hint})")
        stated = hikefinder_listing_count(listing)
        if stated is not None and stated != len(ids):
            raise RuntimeError(f"{self.key}: the listing says {stated} hikes and links {len(ids)}")
        if stated is not None:
            proofs[self.table] = stated
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        for hike_id in ids:
            url = urljoin(base, HIKEFINDER_DETAIL_PATH.format(id=hike_id))
            hike = parse_hike(self._get(http, url), hike_id, url)
            if hike is None:
                raise RuntimeError(f"{self.key}: hike {hike_id} did not parse, which is the export changing shape")
            row = as_hike_row(hike, stamp)
            row["gpx"] = None
            if hike.has_published_route:
                track = self._get(http, urljoin(base, HIKEFINDER_GPX_PATH.format(id=hike_id)))
                row["gpx"] = track if parse_gpx(track) is not None else None
            yield row


def published_hikes(key: str, **overrides) -> PublishedHikes:
    registry_entry(key)
    return PublishedHikes(key=key, **overrides)


@dataclass(frozen=True)
class ClubPdf(Resource):
    """A PDF a club publishes: one row per row its parser reads, each carrying the document's own manifest.

    The registry row's `url` is the PDF. lib/club_pdfs.py's parser for the key
    turns the text layer into rows, and raises on a layout it has not seen, so
    a changed document refuses the run rather than relabelling a column. The
    manifest (url, ETag, Last-Modified, sha256, bytes) rides every row as
    `_document`, so the date the club put on the file is in the warehouse.
    The PDF's own bytes go to the as-sent copy, which is not built yet. The
    text comes from fetch_club_pdfs.py's `extract_page_texts`, which needs
    pypdf: requirements-extract.in pins it, and requirements.in's note says
    why the build jobs do not.
    """

    def _get(self, headers: dict | None = None) -> requests.Response:
        return request_with_retry(registry_entry(self.key)["url"], session=session(), headers=headers or None, timeout=120)

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """A conditional GET, then the body's sha256: WordPress re-serves the same bytes without a 304.

        GATC's file answers with its validators (fetch_club_pdfs.py), so a 304
        is FRESH; a 200 with the same sha256 as the last load is FRESH too.
        """
        headers = {}
        if recorded:
            if recorded.get("etag"):
                headers["If-None-Match"] = recorded["etag"]
            if recorded.get("last_modified"):
                headers["If-Modified-Since"] = recorded["last_modified"]
        try:
            response = self._get(headers)
        except requests.RequestException as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        if response.status_code == 304:
            return Freshness.FRESH, recorded
        marker = {
            "sha256": hashlib.sha256(response.content).hexdigest(),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
        }
        if not recorded or not recorded.get("sha256"):
            return Freshness.STALE, marker
        return (Freshness.FRESH if recorded["sha256"] == marker["sha256"] else Freshness.STALE), marker

    def rows(self, proofs: dict[str, int]):
        response = self._get()
        response.raise_for_status()
        body = response.content
        rows = CLUB_PDF_PARSERS[self.key](extract_page_texts(body))
        document = {
            "url": registry_entry(self.key)["url"],
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body),
        }
        for row in rows:
            yield {**row, "_document": document}


def club_pdf(key: str, **overrides) -> ClubPdf:
    registry_entry(key)
    if key not in CLUB_PDF_PARSERS:
        raise KeyError(f"{key}: lib/club_pdfs.py has no parser for it, so there is nothing to load but bytes")
    return ClubPdf(key=key, **overrides)


@dataclass(frozen=True)
class OpentrailFeed(Resource):
    """opentrail.org's A.T. waypoints, one row per feature, with every user comment left out.

    The API URL is fetch_opentrail.py's `API_URL`, its one home: opentrail is
    a non-registry input (ELT.md, "What moves"), so it has no sources.json row
    to read one from. Comments are dropped inside the resource, before dlt
    sees a row, because they are named individuals' own contributions and not
    ours to redistribute (fetch_opentrail.py's `strip_comments`). The
    API documents ETag and If-None-Match, so the change check is a
    conditional GET and a 304 is FRESH. The key is `at`, so the table keeps
    the name dbt already reads, `raw_opentrail__at`.
    """

    def _get(self, etag: str | None = None) -> requests.Response:
        headers = {"If-None-Match": etag} if etag else None
        return request_with_retry(OPENTRAIL_API_URL, session=session(), params={"trail": "AT"}, headers=headers, timeout=60)

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        try:
            response = self._get((recorded or {}).get("etag"))
        except requests.RequestException as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        if response.status_code == 304:
            return Freshness.FRESH, recorded
        etag = response.headers.get("ETag")
        if not etag:
            return Freshness.UNKNOWN, None
        return (Freshness.STALE if recorded is None else compare_marker(recorded.get("etag"), etag)), {"etag": etag}

    def column_hints(self) -> dict:
        # feature_id hinted so the column exists when no feature carries an id,
        # as on CI's fixtures (extract/_fixtures.py); dlt creates no column it
        # never saw a value for.
        return {"geometry": {"data_type": "json"}, "feature_id": {"data_type": "text"}}

    def rows(self, proofs: dict[str, int]):
        response = self._get()
        response.raise_for_status()
        collection = strip_opentrail_comments(response.json())
        for feature in collection["features"]:
            row = {name: value for name, value in (feature.get("properties") or {}).items() if name.lower() not in PERSON_FIELDS}
            row["feature_id"] = feature.get("id")
            row["geometry"] = feature.get("geometry")
            yield row


def opentrail_feed(**overrides) -> OpentrailFeed:
    return OpentrailFeed(key="at", **overrides)


@dataclass(frozen=True)
class HydrographyWatch(Resource):
    """The usgs_3dhp watch: which 3DHP work units the corridor's flowlines come from, one row per probe box.

    A watch, not a fetch (lib/source_registry.py's WATCHED_ONLY): no 3DHP
    geometry lands, only the answer that says whether USGS has resurveyed the
    corridor. The boxes are check_freshness.py's CORRIDOR_PROBES, five
    0.04-degree envelopes on the footpath, and the query is the registry row's
    `freshness.url`. Every box must name a work unit, or the read raises, so a
    resurveyed stretch cannot hide behind four boxes that still say `NHD`
    (check_freshness.py's `upstream_hydrography_marker`, whose rule this
    keeps). Measured 2026-08-14: all five answer `NHD`.
    """

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """UNKNOWN: five one-row queries a month cost less than a marker that could lie."""
        return Freshness.UNKNOWN, None

    def rows(self, proofs: dict[str, int]):
        url = registry_entry(self.key)["freshness"]["url"]
        http = session()
        rows = []
        for index, (west, south, east, north) in enumerate(CORRIDOR_PROBES):
            answer = request_with_retry(
                url,
                session=http,
                params={
                    "f": "json",
                    "where": "1=1",
                    "outFields": "workunitid",
                    "returnGeometry": "false",
                    "returnDistinctValues": "true",
                    "geometry": f"{west},{south},{east},{north}",
                    "geometryType": "esriGeometryEnvelope",
                    "inSR": 4326,
                    "spatialRel": "esriSpatialRelIntersects",
                },
                timeout=30,
            ).json()
            units = sorted(
                {str(unit) for feature in answer["features"] if (unit := (feature.get("attributes") or {}).get("workunitid"))}
            )
            if not units:
                raise RuntimeError(f"{self.key}: probe {index} named no work unit, which is not an answer about that stretch")
            rows.append({"probe": index, "west": west, "south": south, "east": east, "north": north, "workunitids": units})
        proofs[self.table] = len(CORRIDOR_PROBES)
        yield from rows


def hydrography_watch(key: str, **overrides) -> HydrographyWatch:
    entry = registry_entry(key)
    if not (entry.get("freshness") or {}).get("url"):
        raise KeyError(f"{key} has no freshness.url to ask 3DHP at")
    return HydrographyWatch(key=key, **overrides)


S3_NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
S3_MAX_PAGES = 50

# The bucket listings the extract reads, by key: each one the URL template a
# fetcher downloads from, so the listing covers exactly what that fetcher
# reads and the prefix has one home. None of these is a sources.json row
# (ELT.md, "What moves"); both are USGS's public `prd-tnm` bucket.
BUCKET_LISTINGS = {
    "3dep_13_current": DEM_TILE_URL_TEMPLATE,
    "nhd_hu4_gpkg": NHD_GPKG_URL,
}


def _bucket_and_prefix(template: str) -> tuple[str, str]:
    """`https://host/a/b/c_{x}.zip` -> ("https://host", "a/b/c_"): everything before the first placeholder."""
    parsed = urlparse(template)
    return f"{parsed.scheme}://{parsed.netloc}", parsed.path.lstrip("/").split("{", 1)[0]


@dataclass(frozen=True)
class BucketListing(Resource):
    """A public S3 bucket's objects under one prefix, one row per object: key, size, ETag, LastModified. Never the objects.

    A manifest, not a fetch. 3DEP's tiles are Cloud-Optimized GeoTIFFs read
    in place at build time, and NHD's subregions are ~270 MB zips read
    offline, so what lands is the listing that says whether either moved.
    One ListObjectsV2 walk replaces fetch_elevation.py's 476 HEADs (ELT.md,
    "The skip-unchanged check, by platform"). Measured 2026-10-01: 3DEP's
    `current/` lists 5,967 objects (1,449 of them tiles) in 6 pages, 1.8 MB
    and 1.8 s; NHD's HU4 GeoPackages 735 objects in 1 page, 195 KB and 0.8 s.
    Every object lands, the `.xml` and `.jpg` beside each file included,
    because the only filter before dbt is one the request carries.

    The change check walks the same listing and hashes every (key, ETag,
    size), so a replaced object moves the marker however its date reads.
    The walk raises unless the last page says it is the last, so a listing
    cut short is never read as the whole bucket.
    """

    def _walk(self) -> list[dict]:
        bucket, prefix = _bucket_and_prefix(BUCKET_LISTINGS[self.key])
        http, token, objects = session(), None, []
        for _ in range(S3_MAX_PAGES):
            params = {"list-type": "2", "prefix": prefix}
            if token:
                params["continuation-token"] = token
            page = ElementTree.fromstring(request_with_retry(f"{bucket}/", session=http, params=params, timeout=60).content)
            for item in page.findall("s:Contents", S3_NS):
                objects.append(
                    {
                        "key": item.findtext("s:Key", namespaces=S3_NS),
                        "size": int(item.findtext("s:Size", namespaces=S3_NS)),
                        "etag": item.findtext("s:ETag", namespaces=S3_NS),
                        "last_modified": item.findtext("s:LastModified", namespaces=S3_NS),
                        "storage_class": item.findtext("s:StorageClass", namespaces=S3_NS),
                    }
                )
            if page.findtext("s:IsTruncated", namespaces=S3_NS) != "true":
                return objects
            token = page.findtext("s:NextContinuationToken", namespaces=S3_NS)
            if not token:
                raise RuntimeError(f"{self.key}: a truncated page with no continuation token")
        raise RuntimeError(f"{self.key}: still truncated after {S3_MAX_PAGES} pages")

    def column_hints(self) -> dict:
        return {
            "key": {"data_type": "text"},
            "size": {"data_type": "bigint"},
            "etag": {"data_type": "text"},
            "last_modified": {"data_type": "text"},
            "storage_class": {"data_type": "text"},
        }

    @staticmethod
    def _marker(objects: list[dict]) -> dict:
        digest = hashlib.sha256(json.dumps(sorted((o["key"], o["etag"], o["size"]) for o in objects)).encode()).hexdigest()
        return {"objects": len(objects), "sha256": digest}

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        try:
            marker = self._marker(self._walk())
        except (requests.RequestException, ElementTree.ParseError, RuntimeError) as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def rows(self, proofs: dict[str, int]):
        objects = self._walk()
        proofs[self.table] = len(objects)
        yield from objects


def bucket_listing(key: str, **overrides) -> BucketListing:
    if key not in BUCKET_LISTINGS:
        raise KeyError(f"{key}: no bucket listing by that name in extract/_kinds.py's BUCKET_LISTINGS")
    return BucketListing(key=key, **overrides)


# NWS's alert properties, as /alerts/active served them on 2026-10-01: all 30
# on each of 353 alerts, besides JSON-LD's `@id` (the feature's own `id`, on
# 353 of 353) and `@type` (`wx:Alert` on all 353), which are left out.
# Hinting every one is what makes a column exist when it is null on every
# alert of a run, or when a quiet hour lands no alert at all (ELT.md, "dlt
# configuration requirements"). The times stay text: dlt reads an ISO stamp as
# a timestamp and normalises it to UTC (measured 2026-10-01, dlt 1.30.0),
# which loses the issuing office's offset that NWS's own words carry, and the
# exporter relays these fields exactly (export_weather_alerts.py's RELAYED).
NWS_TEXT_PROPERTIES = (
    "id",
    "areaDesc",
    "sent",
    "effective",
    "onset",
    "expires",
    "ends",
    "status",
    "messageType",
    "category",
    "severity",
    "certainty",
    "urgency",
    "event",
    "sender",
    "senderName",
    "headline",
    "description",
    "instruction",
    "response",
    "note",
    "scope",
    "code",
    "language",
    "web",
)
NWS_JSON_PROPERTIES = ("geocode", "affectedZones", "references", "parameters", "eventCode")


@dataclass(frozen=True)
class NwsAlerts(Resource):
    """Every active NWS alert in the US, one row per message, read in full every run.

    The endpoint is lib/nws_alerts.py's, shared with export_weather_alerts.py,
    which bakes today's `conditions/weather_alerts.json` from the same body.
    NWS is a non-registry input (ELT.md, "What moves"). Nothing is filtered
    here: `Test` messages and cancellations land, and staging leaves them out
    (WN01, `stg_nws__warnings`), because a filter belongs in the extract only
    when the request itself carries it (the dlt skill, "Load every club, gate
    publication downstream").

    No change check. `/alerts/active` ignores both If-None-Match and
    If-Modified-Since: each returned 200 with the same ETag (measured
    2026-10-01, ELT.md, "The skip-unchanged check, by platform"). So every run
    reads it, which is one request a run.

    THE ZERO. A quiet hour is a real answer, and warnings may be empty, so the
    proof is the body's own feature count. A 200 FeatureCollection with no
    features proves the zero. Anything else raises in check_nws_response, and
    a failed request raises in request_with_retry, so the run refuses before
    the load and the last good table stands. A failed request never becomes an
    empty table (ELT.md, "Source kinds"), which would read as "no warnings".
    """

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        return Freshness.UNKNOWN, None

    def column_hints(self) -> dict:
        hints = {name: {"data_type": "text"} for name in (*NWS_TEXT_PROPERTIES, "feature_id", "collection_updated")}
        hints.update({name: {"data_type": "json"} for name in (*NWS_JSON_PROPERTIES, "geometry")})
        return hints

    def rows(self, proofs: dict[str, int]):
        http = session()
        http.headers["Accept"] = NWS_ACCEPT
        body = request_with_retry(NWS_ALERTS_URL, session=http, timeout=60, label="NWS active alerts").json()
        features = check_nws_response(body)
        proofs[self.table] = len(features)
        for feature in features:
            row = {name: value for name, value in (feature.get("properties") or {}).items() if not name.startswith("@")}
            row["feature_id"] = feature.get("id")
            row["geometry"] = feature.get("geometry")
            # The collection's own `updated`, which the bake publishes as
            # `nws_updated`. A run that lands no alert has nowhere to keep it;
            # `_extract_runs.checked_at` is when that run asked.
            row["collection_updated"] = body.get("updated")
            yield row


def nws_alerts(**overrides) -> NwsAlerts:
    return NwsAlerts(key="alerts", **overrides)


# Each of OurHike's own conditions artifacts: the table its reader must be
# able to see, and the bake's own query text, run unchanged. The text is
# export_conditions.py's, held to the served schemas in both directions by
# backend/tests/test_conditions_publisher_contract.py, so what reaches the raw
# store is what reaches a phone today.
CONDITIONS_QUERIES = {
    "closures": ("closures", export_conditions.PUBLIC_CLOSURES_SQL),
    "reports": ("reports", export_conditions.PUBLIC_REPORTS_SQL),
    "notes": ("field_notes", export_conditions.PUBLIC_NOTES_SQL),
    "disputes": ("field_notes", export_conditions.PUBLIC_DISPUTES_SQL),
}

# The person columns the four query texts leave in the database: who reported,
# who verified, who hid a note, which maintainer. A second line behind the
# query text, so that a column added under one of these names fails the read
# rather than landing (#252, #430).
WITHHELD_COLUMNS = frozenset({"reported_by", "reporter_id", "verified_by", "hidden_by", "maintainer_id"})

# Postgres type names -> dlt data types, for describing a query's own columns.
# A type not listed, such as an enum, loads as a string in psycopg, so it lands
# as text.
POSTGRES_TYPES = {
    "bool": "bool",
    "int2": "bigint",
    "int4": "bigint",
    "int8": "bigint",
    "float4": "double",
    "float8": "double",
    "numeric": "decimal",
    "date": "date",
    "timestamp": "timestamp",
    "timestamptz": "timestamp",
    "json": "json",
    "jsonb": "json",
}


@dataclass(frozen=True)
class ConditionsQuery(Resource):
    """One of OurHike's own conditions artifacts, read from its Postgres through the bake's own query.

    Decision 6: moderator-verified rows only, hourly. The query is
    export_conditions.py's PUBLIC_*_SQL, whole, so its moderation predicate,
    its 90-day and five-per-place windows, and its two-account dispute rule
    all hold here as they hold in the bake, and `verified_by` and
    `reporter_id` never leave the database. The connection is the bake's own
    CONDITIONS_DATABASE_URL, so each conditions leg reads its own environment.

    Not dlt's sql_table. Its reflected column hints are the base table's,
    not the query's (measured 2026-10-01 on Postgres 16): for closures they
    name `reported_by` and `verified_by`, the two columns the query withholds,
    and for disputes they name `field_notes`' columns and miss the computed
    `accounts`, `latest_at` and `maintainer_said`. So the hints come from
    describing the query itself.

    The check runs reader_problem() first, as the bake does: a missing grant
    or policy reads as zero rows, and "empty is indistinguishable from a quiet
    trail". On a table export_conditions.py's PENDING_READER_SETUP names, the
    problem is Unavailable, and the lane carries on without it. On any other
    table it stops the lane. The read asks again, in the same transaction as
    the rows, so a policy dropped between the check and the read cannot prove
    a false zero. The proof is the query's own `count(*)`, under REPEATABLE
    READ with the rows.
    """

    @property
    def source_table(self) -> str:
        return CONDITIONS_QUERIES[self.key][0]

    @property
    def sql(self) -> str:
        return CONDITIONS_QUERIES[self.key][1]

    def _problem(self, conn) -> str | None:
        return export_conditions.reader_problem(conn, self.source_table)

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """UNKNOWN when the reader can see the table: a few hundred rows an hour cost less than a marker that could lie."""
        with psycopg.connect(export_conditions.connection_url(), connect_timeout=10) as conn:
            problem = self._problem(conn)
        if problem is None:
            return Freshness.UNKNOWN, None
        pending = export_conditions.PENDING_READER_SETUP.get(self.source_table)
        if pending is None:
            raise RuntimeError(problem)
        raise Unavailable(f"{problem} {pending}")

    def column_hints(self) -> dict:
        with psycopg.connect(export_conditions.connection_url(), connect_timeout=10) as conn:
            cursor = conn.execute(f"SELECT * FROM ({self.sql}) AS public_rows LIMIT 0")
            return {
                column.name: {
                    "data_type": POSTGRES_TYPES.get(getattr(conn.adapters.types.get(column.type_code), "name", None), "text")
                }
                for column in cursor.description
            }

    def rows(self, proofs: dict[str, int]):
        with psycopg.connect(export_conditions.connection_url(), connect_timeout=10) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            problem = self._problem(conn)
            if problem is not None:
                raise RuntimeError(f"{self.key}: {problem}")
            (count,) = conn.execute(f"SELECT count(*) FROM ({self.sql}) AS public_rows").fetchone()
            with conn.cursor(row_factory=dict_row) as cursor:
                cursor.execute(self.sql)
                withheld = WITHHELD_COLUMNS & {column.name for column in cursor.description}
                if withheld:
                    raise RuntimeError(f"{self.key}: the query now selects {sorted(withheld)}, which never leave the database")
                rows = cursor.fetchall()
        proofs[self.table] = count
        yield from rows


def conditions_query(key: str, **overrides) -> ConditionsQuery:
    if key not in CONDITIONS_QUERIES:
        raise KeyError(f"{key}: not one of export_conditions.py's artifacts {sorted(CONDITIONS_QUERIES)}")
    return ConditionsQuery(key=key, **overrides)


@dataclass(frozen=True)
class ReviewedFile(Resource):
    """A file in git that a person reviews row by row, loaded as the rows it holds.

    The change marker is the file's sha256: the file is its own upstream, so
    it is FRESH exactly when its bytes are, and its row count is its own proof.
    `rows_key` names the list a file keeps its rows under; None loads the
    whole document as one row. With `map_key` set, `rows_key` names a map of
    id -> row instead, and each row lands with its id under that column: the
    POI identity ledger keeps its 8,563 POIs that way. `_README` is the
    file's documentation and never a column. Every other top-level field (who
    reviewed it and when, the upstream marker it was reviewed against) rides
    each row as `_file`, so the "as of" a phone prints is in the warehouse and
    not only in git.
    """

    path: str = ""
    rows_key: str | None = None
    map_key: str | None = None
    # (column, dlt data type) pairs, for a file whose schema is written down
    # somewhere: dlt creates no column it never saw a value for, so a field no
    # row carries yet would otherwise be missing from the table.
    hints: tuple[tuple[str, str], ...] = ()
    # For a file a gate checks field by field, such as the podcast episodes:
    # each row lands whole in one `row_json` column, as the JSON text of what the
    # reviewer wrote, and dbt reads its fields. Typed columns would hide the
    # typos the gate exists to refuse. Measured 2026-10-01 on dlt 1.30.0: a
    # bigint hint landed "minutes": "34" as 34, a text hint landed
    # "title": 5 as "5", sql_ci_v1 folded a misspelt "At_Miles" into
    # at_miles, and a field null on every row made no column at all.
    verbatim: bool = False

    def column_hints(self) -> dict:
        hints = {name: {"data_type": data_type} for name, data_type in self.hints}
        return {**hints, "row_json": {"data_type": "text"}} if self.verbatim else hints

    @property
    def file(self) -> Path:
        return PIPELINE_DIR / self.path

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        if not self.file.is_file():
            return Freshness.UNKNOWN, None
        marker = {"sha256": _file_sha256(self.file)}
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def rows(self, proofs: dict[str, int]):
        document = json.loads(self.file.read_text())
        if self.rows_key is None:
            body = {name: value for name, value in document.items() if name != "_README"}
            proofs[self.table] = 1
            yield {**body, "_path": self.path}
            return
        rows = document[self.rows_key]
        if self.map_key is not None:
            if not isinstance(rows, dict):
                raise ValueError(f"{self.path}: {self.rows_key} is not a map, so it has no ids for {self.map_key}")
            if any(self.map_key in row for row in rows.values()):
                raise ValueError(f"{self.path}: a row already carries {self.map_key}, so the map's id cannot land there")
            rows = [{self.map_key: row_id, **row} for row_id, row in rows.items()]
        context = {name: value for name, value in document.items() if name not in ("_README", self.rows_key)}
        proofs[self.table] = len(rows)
        # `_row` is the row's place in the file, because a reviewed file's order is
        # often the published order (export_podcasts.py keeps it) and SQL has none.
        for index, row in enumerate(rows):
            fields = {"row_json": json.dumps(row, ensure_ascii=False)} if self.verbatim else row
            yield {**fields, "_row": index, "_file": context, "_path": self.path}


def reviewed_input(key: str, rows_key: str, **overrides) -> ReviewedFile:
    """A registry entry whose rows are reviewed into the file its `reviewed_input` names.

    ATC's Trail Updates is the case: the registry row is the upstream, and
    what ships today is the reviewed file (features/ATC_TRAIL_UPDATES.md, "the
    parse proposes; a human publishes"). The key is the claim, so the claim
    test sees the registry row once; the file is where the rows come from.
    """
    path = registry_entry(key).get("reviewed_input")
    if not path:
        raise KeyError(f"{key} has no reviewed_input in sources.json")
    return ReviewedFile(key=key, path=path, rows_key=rows_key, **overrides)


def reviewed_file(
    path: str,
    rows_key: str | None,
    map_key: str | None = None,
    hints: dict[str, str] | None = None,
    verbatim: bool = False,
    **overrides,
) -> ReviewedFile:
    if not (PIPELINE_DIR / path).is_file():
        raise FileNotFoundError(path)
    if verbatim and rows_key is None:
        raise ValueError(f"{path}: verbatim lands each row of a list or map, and rows_key names none")
    return ReviewedFile(
        key=path,
        path=path,
        rows_key=rows_key,
        map_key=map_key,
        hints=tuple(sorted((hints or {}).items())),
        verbatim=verbatim,
        **overrides,
    )


@dataclass(frozen=True)
class ReviewedDir(Resource):
    """A folder of reviewed files, one row per file: a club's challenges, one file per challenge.

    The marker hashes every file's name and bytes together, so adding,
    editing or removing one challenge reloads the folder.
    """

    path: str = ""

    @property
    def files(self) -> list[Path]:
        return sorted((PIPELINE_DIR / self.path).glob("*.json"))

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        digest = hashlib.sha256()
        for file in self.files:
            digest.update(file.name.encode() + b"\0" + file.read_bytes() + b"\0")
        marker = {"sha256": digest.hexdigest(), "files": str(len(self.files))}
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def rows(self, proofs: dict[str, int]):
        files = self.files
        proofs[self.table] = len(files)
        for file in files:
            document = json.loads(file.read_text())
            yield {
                **{name: value for name, value in document.items() if name != "_README"},
                "_path": str(file.relative_to(PIPELINE_DIR)),
            }


def reviewed_dir(path: str, **overrides) -> ReviewedDir:
    if not (PIPELINE_DIR / path).is_dir():
        raise FileNotFoundError(path)
    return ReviewedDir(key=path, path=path, **overrides)


# trail_orgs.json fields the sources mart reads (ELT.md: org, website, type,
# licence, licence_basis, attribution, load, via), and the licence fields of
# each key the club claims.
ORG_FIELDS = ("slug", "org", "website", "type", "licence", "licence_basis", "attribution", "load", "via")
CLAIM_FIELDS = ("licence", "licence_basis", "attribution", "reaches_hikers")
ORGS_TABLE = "raw_extract__orgs"


@lru_cache(maxsize=4)
def _trail_orgs(path: Path) -> dict:
    document = json.loads(path.read_text())
    return {row["slug"]: row for row in document["orgs"]}


@dataclass(frozen=True)
class CatalogueRow(Resource):
    """The club's trail_orgs.json row, plus the licence fields of every key the club claims.

    All clubs write one shared table, `raw_extract__orgs`, the sources mart's
    input. That is safe under `replace` only because these are local reads and
    every org resource runs on every monthly run (ELT.md, "The contract, and
    one file of each kind"); extract/_run.py never change-checks them away.
    """

    @property
    def table(self) -> str:
        return ORGS_TABLE

    @property
    def name(self) -> str:
        return f"org_{self.club}"

    def rows(self, proofs: dict[str, int]):
        slug = slug_for_folder(self.club)
        org = _trail_orgs(TRAIL_ORGS_PATH).get(slug)
        if org is None:
            raise KeyError(f"{self.club}/ has no trail_orgs.json row with slug {slug!r}")
        claims = []
        for path in sorted((EXTRACT_DIR / self.club).glob("*.py")):
            if path.stem == "org":
                continue
            club_file = read_club_file(path)
            for key in club_file.claims:
                entry = _registry(REGISTRY_PATH).get(key, {})
                claims.append({"key": key, "type": club_file.type, **{name: entry.get(name) for name in CLAIM_FIELDS}})
        yield {**{name: org.get(name) for name in ORG_FIELDS}, "claims": claims}


def catalogue_row() -> CatalogueRow:
    return CatalogueRow(key="reference/trail_orgs.json")


# RSS and the namespaces a podcast feed's items use. Each child of an <item>
# becomes a column named by its tag, the namespace written as a short prefix
# (itunes_duration), so nothing a feed carries is dropped before dbt sees it.
FEED_NAMESPACES = {
    "http://www.itunes.com/dtds/podcast-1.0.dtd": "itunes",
    "http://purl.org/rss/1.0/modules/content/": "content",
    "https://podcastindex.org/namespace/1.0": "podcast",
}


def _feed_column(tag: str) -> str:
    if tag.startswith("{"):
        uri, name = tag[1:].split("}", 1)
        return f"{FEED_NAMESPACES.get(uri, 'ns')}_{name}"
    return tag


@dataclass(frozen=True)
class PodcastFeed(Resource):
    """A podcast's RSS feed, one row per episode: its metadata, never its audio.

    Change check: a conditional GET with the feed's own validators. A 304 is
    FRESH. A feed is a change signal only on a safety path (an RSS window is not
    a list of current items; ELT.md, "The skip-unchanged check, by platform"),
    and podcasts are not one. A podcast feed lists the whole show: The Green
    Tunnel's held 51 items against Apple's count of 51 episodes (2026-10-01).
    Each episode's `guid` is the key it is staged on (51 of 51 unique, the
    same day).

    An <enclosure> is kept as its URL, length and type, and is never fetched.
    """

    @property
    def entry(self) -> dict:
        return registry_entry(self.key)

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        headers = {}
        if recorded:
            if recorded.get("etag"):
                headers["If-None-Match"] = recorded["etag"]
            if recorded.get("last_modified"):
                headers["If-Modified-Since"] = recorded["last_modified"]
        try:
            response = request_with_retry(self.entry["url"], session=session(), headers=headers or None, timeout=30)
        except requests.RequestException as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        if response.status_code == 304:
            return Freshness.FRESH, recorded
        marker = {"etag": response.headers.get("ETag"), "last_modified": response.headers.get("Last-Modified")}
        if not marker["etag"] and not marker["last_modified"]:
            return Freshness.UNKNOWN, None
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_canonical(recorded), _canonical(marker)), marker

    def rows(self, proofs: dict[str, int]):
        response = request_with_retry(self.entry["url"], session=session(), timeout=60)
        channel = ElementTree.fromstring(response.content).find("channel")
        if channel is None:
            raise ValueError(f"{self.key}: the answer is not an RSS feed (no <channel>)")
        items = channel.findall("item")
        proofs[self.table] = len(items)
        show = {"show_title": channel.findtext("title"), "show_link": channel.findtext("link")}
        for item in items:
            row = dict(show)
            for child in item:
                column = _feed_column(child.tag)
                if column == "enclosure":
                    row["enclosure_url"] = child.get("url")
                    row["enclosure_length"] = child.get("length")
                    row["enclosure_type"] = child.get("type")
                else:
                    row[column] = (child.text or "").strip() or None
            yield row


def podcast_feed(key: str, **overrides) -> PodcastFeed:
    entry = registry_entry(key)
    if source_kind(entry) != PODCAST_FEED:
        raise ValueError(f"{key} is a {source_kind(entry)}, not a {PODCAST_FEED}")
    return PodcastFeed(key=key, **overrides)
