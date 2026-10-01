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

The four kinds stage 2 of #1793 needs for ATC and NYS DEC:

    arcgis_layer(key)       an ArcGIS FeatureServer or MapServer layer
    reviewed_input(key)     a registry entry whose rows a person reviews into a
                            file in git (ATC's Trail Updates), loaded from that file
    reviewed_file(path)     a reviewed pipeline/reference/ file with no registry
                            row of its own (water_distance.json)
    reviewed_dir(path)      a folder of reviewed files, one row per file (a
                            club's challenges)
    catalogue_row()         the club's own trail_orgs.json row, for org.py
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import requests

from extract._contract import EXTRACT_DIR, PIPELINE_DIR, Resource, read_club_file, slug_for_folder
from lib.arcgis import iter_layer_pages, layer_count
from lib.freshness_state import Freshness, compare_marker
from lib.http_retry import request_with_retry
from lib.source_registry import load_registry
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
class ReviewedFile(Resource):
    """A file in git that a person reviews row by row, loaded as the rows it holds.

    The change marker is the file's sha256: the file is its own upstream, so
    it is FRESH exactly when its bytes are, and its row count is its own proof.
    `rows_key` names the list a file keeps its rows under; None loads the
    whole document as one row. `_README` is the file's documentation and never
    a column. Every other top-level field (who reviewed it and when, the
    upstream marker it was reviewed against) rides each row as `_file`, so the
    "as of" a phone prints is in the warehouse and not only in git.
    """

    path: str = ""
    rows_key: str | None = None

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
        context = {name: value for name, value in document.items() if name not in ("_README", self.rows_key)}
        proofs[self.table] = len(rows)
        for row in rows:
            yield {**row, "_file": context, "_path": self.path}


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


def reviewed_file(path: str, rows_key: str | None, **overrides) -> ReviewedFile:
    if not (PIPELINE_DIR / path).is_file():
        raise FileNotFoundError(path)
    return ReviewedFile(key=path, path=path, rows_key=rows_key, **overrides)


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
