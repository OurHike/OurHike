"""Decision 54, wave 3: the geographic APIs, OGC API Features and a JSON API whose items carry a coordinate.

    ogc_features(key)    an OGC API Features collection's items, paged by the `next` link the server gives
    json_features(key)   a JSON API's list of items, each a row, its coordinate made a Point

pipeline/ELT.md, "Loading everything the clubs publish (decision 54)", wave 3:
"feeds and APIs: WordPress, RSS, JSON, OGC Features | WordPress exists; OGC
Features and generic JSON are new". Both are builders like extract/_kinds.py's:
each takes a sources.json key, never a URL. They live here, beside each other,
because both page a JSON answer, flatten its items the same way and leave out
the same person fields; extract/_gis_files.py is the file-shaped half of the
same wave.

THE ROW, for both: the item's own fields flattened one column each, every value
as text (a string as served, anything else as its JSON), for the reason
extract/_gis_files.py's docstring gives: an API declares no column types a read
can hold, and text cannot split into a variant column. `geometry` is GeoJSON
under rule 1's JSON hint. For OGC API Features the feature's own `id` lands as
`feature_id`; a JSON API's item keeps whatever id it carries under its own name.

OGC API FEATURES (OGC 17-069r4, Part 1: Core). The row's `url` is the
collection's `/items`. Pages follow the `next` link each page names (`links`,
`rel: next`), never an offset this code computes, because a server may page by
a cursor and an offset it does not honour would repeat or skip rows; a `next`
that names a page already read raises rather than loop. The count is the first
page's `numberMatched` where the server sends one, held as the proof, and a
read shorter than it raises; with none, the count is unknown, so an empty
answer is UNKNOWN to the run check rather than a proven zero. No change check:
the standard has no collection-wide validator, and a page's ETag says nothing
about the pages after it, so every run reads the whole collection (rule 4:
UNKNOWN fetches).

A JSON API (`json_features`). Each row of sources.json says how its list is
read, so one reader serves APIs that page three different ways:
- `paging`: `wordpress` (`page` and `per_page`, stopping at `X-WP-TotalPages`
  or a short page, the count from `X-WP-Total`, extract/_kinds.py's wp_list()),
  `next_url` (the item list's own next-page URL under `next_url_field`, the
  count under `total_field`: The Events Calendar's venues), `start_limit`
  (`start` and `limit`, stepping by the rows each page returned, the count
  under `total_field`: NPS's API), or `single` (one answer, counted by itself).
- `items_field`: where the list sits in the answer (none for a bare list).
- `params`: the query every request carries, as the site's own client sends it
  (MTSG's map asks `_latlng=acf_loc_address`, and without it no item has a
  location).
- `lat_field` and `lon_field`: dotted paths to the coordinate (`location.lat`);
  an item with either missing or not a number gets no geometry, never a guess.
- `api_key_env` and `api_key_header`: a key read from the environment at run
  time and sent in that header, never the URL. With the variable unset the
  change check raises Unavailable (extract/_contract.py), so the run leaves the
  table out and the warehouse withdraws it: a missing secret reads as unknown,
  never as an empty answer (extract/_json_apis.py's NPS readers, the precedent).
The change check is a hash of the items' ids and modified dates where the row
names `id_field` and `modified_field`, read with the same paging but asking only
for those two fields where the API takes `_fields`; otherwise UNKNOWN.

PERSON FIELDS never load: extract/_kinds.py's PERSON_FIELDS, the row's own
`person_fields`, WordPress's plumbing that names a user (WP_DROPPED: `author`,
Yoast's blocks), and a top-level field whose name reads as a person's
(PERSON_SHAPED) unless the row's `not_person_fields` clears it. They are left
out of the row before dlt sees it, and never redacted downstream (decision 59).

ACCESS: lib/user_agent.py's USER_AGENT through extract/_kinds.py's session(),
and extract/_notices.py's per-host gate, at least POLITE_SECONDS between two
requests to one host or the row's `crawl_delay` where its robots.txt asks for
more (tennesseetrails.org asks 60). A redirect to another host the row does not
name in `redirect_hosts` raises (extract/_notices.py's redirect_refused).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from urllib.parse import urljoin

import requests

from extract import _kinds, _notices
from extract._contract import Resource, Unavailable
from lib.freshness_state import Freshness, compare_marker
from lib.http_retry import request_with_retry

#: The gap kept between two requests to one host when its robots.txt asks for none (extract/_gis_files.py's).
POLITE_SECONDS = _notices.DEFAULT_HOST_GAP_SECONDS

#: A ceiling on pages, not an ending: reaching it raises rather than land a short read.
MAX_PAGES = 200

#: The page size asked of an OGC API Features server. Its own `limit` ceiling may be smaller, and paging by the
#: `next` link it gives costs a request then, never a row. @unvalidated as a fit for any one server.
OGC_LIMIT = 1000

PAGINGS = ("wordpress", "next_url", "start_limit", "single")


def _text(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _path(item, dotted: str):
    """The value at a dotted path (`location.lat`), or None where any step is missing."""
    value = item
    for step in dotted.split("."):
        if not isinstance(value, dict) or step not in value:
            return None
        value = value[step]
    return value


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # NaN is not a coordinate


class _Paged(Resource):
    """What both readers share: the registry row, the polite session, and the person-field rule."""

    @property
    def entry(self) -> dict:
        return _kinds.registry_entry(self.key)

    @property
    def may_be_empty(self) -> bool:
        return super().may_be_empty or bool(self.entry.get("may_be_empty"))

    @property
    def field_rules(self) -> dict[str, list[str]]:
        """The row's person-field rules, lower-cased, kept in the marker by extract/_run.py's definition_digest()."""
        entry = self.entry
        return {rule: sorted(name.lower() for name in entry.get(rule) or []) for rule in ("person_fields", "not_person_fields")}

    def _session(self) -> requests.Session:
        delay = max(POLITE_SECONDS, float(self.entry.get("crawl_delay") or 0))
        return _notices.polite(_kinds.session(), delay)

    def _get(
        self, http: requests.Session, url: str, params: dict | None = None, headers: dict | None = None
    ) -> requests.Response:
        response = request_with_retry(url, session=http, params=params, headers=headers, timeout=120, label=self.key)
        blocked = _notices.wall(response)
        if blocked:
            raise RuntimeError(f"{self.key}: {url} answered as a wall ({blocked})")
        if refused := _notices.redirect_refused(self.entry, url, response.url):
            raise RuntimeError(f"{self.key}: {refused}")
        return response

    def left_out(self, name: str) -> bool:
        """Whether a field never loads (the module docstring's PERSON FIELDS)."""
        lower = name.lower()
        rules = self.field_rules
        if lower in rules["not_person_fields"]:
            return lower in _kinds.PERSON_FIELDS or lower in rules["person_fields"]
        return (
            lower in _kinds.PERSON_FIELDS
            or lower in rules["person_fields"]
            or lower in _kinds.WP_DROPPED
            or bool(_kinds.PERSON_SHAPED.search(_kinds._name_words(name)))
        )

    def flatten(self, fields: dict, reserved: tuple[str, ...]) -> dict:
        """An item's fields as text columns, the person fields left out, a name that collides with ours prefixed."""
        row = {}
        taken = {name.lower() for name in reserved}
        for name, value in fields.items():
            if self.left_out(name):
                continue
            column = f"property_{name}" if name.lower() in taken else name
            row[column] = _text(value)
        return row

    def column_hints(self) -> dict:
        return {"geometry": {"data_type": "json"}}


# --- OGC API Features ---------------------------------------------------------------


@dataclass(frozen=True)
class OgcFeatures(_Paged):
    """An OGC API Features collection's items, a row each (the module docstring)."""

    @property
    def items_url(self) -> str:
        url = self.entry["url"].rstrip("/")
        return url if url.endswith("/items") else f"{url}/items"

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        return Freshness.UNKNOWN, None

    def rows(self, proofs: dict[str, int]):
        http = self._session()
        headers = {"Accept": "application/geo+json, application/json;q=0.9"}
        url, params = self.items_url, {"limit": OGC_LIMIT, "f": "json"}
        seen: set[str] = set()
        rows: list[dict] = []
        matched = None
        for _ in range(MAX_PAGES):
            response = self._get(http, url, params=params, headers=headers)
            page = response.json()
            if page.get("type") != "FeatureCollection":
                raise RuntimeError(f"{self.key}: {response.url} answered a {page.get('type')!r}, not a FeatureCollection")
            if matched is None and isinstance(page.get("numberMatched"), int):
                matched = page["numberMatched"]
            for feature in page.get("features") or []:
                row = {"feature_id": _text(feature.get("id"))}
                row.update(self.flatten(feature.get("properties") or {}, ("feature_id", "geometry")))
                row["geometry"] = feature.get("geometry")
                rows.append(row)
            following = next((link.get("href") for link in page.get("links") or [] if link.get("rel") == "next"), None)
            if not following or not page.get("features"):
                break
            following = urljoin(response.url, following)
            if following in seen:
                raise RuntimeError(f"{self.key}: the server's next link repeats a page it already gave ({following})")
            seen.add(following)
            url, params = following, None  # the next link carries its own query, as the server wrote it
        else:
            raise RuntimeError(f"{self.key}: still paging at {MAX_PAGES} pages, which is a ceiling rather than an ending")
        if matched is not None:
            if len(rows) < matched:
                raise RuntimeError(f"{self.key}: the server matches {matched} features and {len(rows)} were read")
            proofs[self.table] = matched
        print(f"  {self.key}: {len(rows)} features, numberMatched {matched}")
        yield from rows


def ogc_features(key: str, **overrides) -> OgcFeatures:
    _kinds.registry_entry(key)  # a key that is not registered fails at import, in the layout test, not mid-run
    return OgcFeatures(key=key, **overrides)


# --- A JSON API whose items carry a coordinate --------------------------------------


@dataclass(frozen=True)
class JsonFeatures(_Paged):
    """A JSON API's items, a row each, with a Point where the item's own coordinate fields hold one."""

    @property
    def paging(self) -> str:
        return self.entry.get("paging") or "single"

    @property
    def exact_proof(self) -> bool:
        return self.paging == "single"

    def _headers(self) -> dict | None:
        variable = self.entry.get("api_key_env")
        if not variable:
            return None
        key = os.environ.get(variable, "").strip()
        if not key:
            raise Unavailable(
                f"{variable} is not set, so {self.key}'s API cannot be asked (it refuses a request without a key); "
                "the table is withdrawn rather than read as empty"
            )
        return {self.entry.get("api_key_header") or "X-Api-Key": key}

    def _items(self, answer) -> list:
        field = self.entry.get("items_field")
        items = answer if not field else _path(answer, field)
        if not isinstance(items, list):
            raise RuntimeError(f"{self.key}: the answer's {field or 'body'} is {type(items).__name__}, not a list")
        return items

    def read(self, http: requests.Session, extra: dict | None = None) -> tuple[list, int | None]:
        """Every item, and the API's own count of them where it sends one."""
        entry, headers = self.entry, self._headers()
        params = {**(entry.get("params") or {}), **(extra or {})}
        url = entry["url"]
        paging, size = self.paging, int(entry.get("page_size") or 100)
        collected: list = []
        total = None
        if paging == "single":
            items = self._items(self._get(http, url, params=params, headers=headers).json())
            return items, len(items)
        for page in range(1, MAX_PAGES + 1):
            if paging == "wordpress":
                response = self._get(http, url, params={**params, "per_page": size, "page": page}, headers=headers)
                if total is None and response.headers.get("X-WP-Total") is not None:
                    total = int(response.headers["X-WP-Total"])
                items = self._items(response.json())
                collected.extend(items)
                last = response.headers.get("X-WP-TotalPages")
                if len(items) < size or (last is not None and page >= int(last)):
                    return collected, total
            elif paging == "start_limit":
                response = self._get(http, url, params={**params, "limit": size, "start": len(collected)}, headers=headers)
                answer = response.json()
                if total is None and entry.get("total_field"):
                    total = int(_path(answer, entry["total_field"]))
                items = self._items(answer)
                collected.extend(items)
                if not items or (total is not None and len(collected) >= total):
                    return collected, total
            elif paging == "next_url":
                response = self._get(http, url, params=params if page == 1 else None, headers=headers)
                answer = response.json()
                if total is None and entry.get("total_field"):
                    total = int(_path(answer, entry["total_field"]))
                collected.extend(self._items(answer))
                following = _path(answer, entry["next_url_field"])
                if not following:
                    return collected, total
                if following == url:
                    raise RuntimeError(f"{self.key}: the next page's URL is the page just read ({following})")
                url = following
            else:
                raise KeyError(f"{self.key}: paging {paging!r} is not one of {PAGINGS}")
        raise RuntimeError(f"{self.key}: still paging at {MAX_PAGES} pages, which is a ceiling rather than an ending")

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """A hash of every item's (id, modified), read with the same paging; UNKNOWN where the row names neither field."""
        entry = self.entry
        id_field, modified_field = entry.get("id_field"), entry.get("modified_field")
        if not id_field or not modified_field:
            self._headers()  # a missing key is Unavailable here too, so the table is withdrawn, never read as empty
            return Freshness.UNKNOWN, None
        extra = {"_fields": f"{id_field},{modified_field}"} if self.paging == "wordpress" else None
        try:
            items, total = self.read(self._session(), extra)
        except (requests.RequestException, ValueError, KeyError, RuntimeError) as error:
            print(f"  {self.key}: change check failed ({error}); reading it")
            return Freshness.UNKNOWN, None
        pairs = sorted((str(_path(item, id_field)), str(_path(item, modified_field))) for item in items)
        marker = {"total": str(total), "set_sha256": hashlib.sha256(json.dumps(pairs).encode()).hexdigest()}
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(json.dumps(recorded, sort_keys=True), json.dumps(marker, sort_keys=True)), marker

    def _copies(self, items: list) -> tuple[int, dict[str, list[str]]]:
        """How many distinct values of the row's key the items hold, and {value: the fields its copies differ in}.

        The key is every field of the row's `key_fields`, read from each item.
        Only values whose copies differ are named; exact copies are the staging
        dedupe's (decision 40). An item missing a key field counts as one
        distinct item, since it cannot be shown to repeat another. A row with
        no key, or whose key holds the geometry, answers (len(items), {}); a
        paged row needs one (json_features()).
        """
        fields = self.entry.get("key_fields") or []
        if not fields or "geometry" in fields:
            return len(items), {}
        groups: dict[str, list] = {}
        keyless = 0
        for item in items:
            values = [_path(item, field) for field in fields]
            if all(value is not None for value in values):
                groups.setdefault(" / ".join(str(value) for value in values), []).append(item)
            else:
                keyless += 1
        differing = {}
        for value, group in groups.items():
            if len(group) > 1:
                names = sorted(
                    {
                        name
                        for one in group
                        for name in one
                        if len({json.dumps(other.get(name), sort_keys=True) for other in group}) > 1
                    }
                )
                if names:
                    differing[value] = names
        return len(groups) + keyless, differing

    def _consistent_read(self) -> tuple[list, int | None]:
        """read(), and once more where a paged read holds fewer distinct keys than the API counts; RuntimeError on differing copies.

        Paging by offset over a list that changes during the read can hand back
        one item twice and skip another: an item added or removed before the
        offset shifts every later one (Reasoned). The count check cannot see
        it, because the repeat makes up the number. Monthly run 17
        (refresh-reference.yml 37232256991) loaded nps_api_places with one `id`
        on two rows that differ, which failed duplicates_are_exact and stopped
        the build; what differed was not kept, and the list (17,505 items
        on 2026-10-04) is too long for the demo key to read again here. So a
        paged read with fewer distinct keys than the API's total is read once
        more, and differing copies left after that refuse the read with the
        fields that differ named, never the values.

        AND SO DOES A SECOND READ STILL SHORT OF THE TOTAL. An exact copy
        makes up the count as well as a differing one does, and a
        start/limit read stops once it holds `total` items, so a list whose
        order wobbles at a page boundary on every read served one item twice
        and another never, and landed one item short with no error (review
        finding EXD-8). Stepping by `start` cannot be made safe from this
        side, so the honest answer is the refusal: the last committed table
        stands.
        """
        items, total = self.read(self._session())
        distinct, differing = self._copies(items)
        if self.paging != "single" and (differing or (total is not None and distinct < total)):
            print(
                f"::warning title={self.key} read an item twice::{distinct} distinct of {len(items)} items, "
                f"the API counts {total}; reading the list again, once"
            )
            items, total = self.read(self._session())
            distinct, differing = self._copies(items)
        if differing:
            value, names = next(iter(differing.items()))
            raise RuntimeError(
                f"{self.key}: {len(differing)} {' / '.join(self.entry['key_fields'])} value(s) on items that differ "
                f"(first: {value}, in {', '.join(names)}), so its key would drop a real item"
            )
        if self.paging != "single" and self.entry.get("key_fields") and total is not None and len(items) >= total > distinct:
            raise RuntimeError(
                f"{self.key}: read twice, and both reads hold {distinct} distinct {' / '.join(self.entry['key_fields'])} "
                f"values where the API counts {total}: an item was served twice in place of another"
            )
        return items, total

    def rows(self, proofs: dict[str, int]):
        entry = self.entry
        items, total = self._consistent_read()
        if total is not None:
            if len(items) < total:
                raise RuntimeError(f"{self.key}: the API counts {total} items and {len(items)} were read")
            proofs[self.table] = total
        located = 0
        for item in items:
            row = self.flatten(item, ("geometry",))
            lat, lon = _number(_path(item, entry["lat_field"])), _number(_path(item, entry["lon_field"]))
            if lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180:
                row["geometry"] = {"type": "Point", "coordinates": [lon, lat]}
                located += 1
            else:
                row["geometry"] = None
            yield row
        print(f"  {self.key}: {len(items)} items, {located} with a coordinate, the API counts {total}")


def json_features(key: str, **overrides) -> JsonFeatures:
    entry = _kinds.registry_entry(key)  # a key that is not registered fails at import, in the layout test, not mid-run
    if (entry.get("paging") or "single") not in PAGINGS:
        raise KeyError(f"{key}: paging {entry.get('paging')!r} is not one of {PAGINGS}")
    if not (entry.get("lat_field") and entry.get("lon_field")):
        raise KeyError(f"{key}: a json_features row names its lat_field and lon_field")
    if entry.get("paging") == "next_url" and not entry.get("next_url_field"):
        raise KeyError(f"{key}: a next_url row names its next_url_field")
    key_fields = entry.get("key_fields") or []
    if (entry.get("paging") or "single") != "single" and (not key_fields or "geometry" in key_fields):
        # Without a key a page served twice cannot be seen, and its repeat makes up the count (review finding EXD-8).
        raise KeyError(f"{key}: a paged json_features row names the key_fields its items are told apart by")
    if _notices.query_refused(entry["url"]):
        raise KeyError(f"{key}: {_notices.query_refused(entry['url'])}")
    return JsonFeatures(key=key, **overrides)
