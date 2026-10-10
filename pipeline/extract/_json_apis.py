"""One small adapter per JSON API that publishes closures or warnings (ELT.md decision 53, phase B, "JSON API").

Each is a Resource over a sources.json key, as every kind in extract/_kinds.py
is, and lives here rather than there so the phase B readers for other formats
(feeds, pages, PDFs) are not all edits to one file:

    nps_alerts(key)               NPS's /alerts for every park code the entry lists, one row per alert
    nps_road_events(key)          NPS's WZDx road events, one row per event
    dcnr_park_advisories(key)     PA DCNR's ParkAdvisory, one row per advisory per park id
    usgs_elevated_volcanoes(key)  USGS's elevated volcanoes, one row per volcano
    mediawiki_announcements(key)  a MediaWiki's pages that transclude one template, latest revision each
    sheet_csv_segments(key)       a Google Sheet's CSV export, one row per trail-segment row
    my_maps_placemarks(key)       a Google My Maps KML export, one row per placemark, as served

The last is a KML file, not JSON: the decision 53 inventory listed it among the
JSON APIs, and it is the one closure source in that list with the steward's own
geometry and status, so it is read here rather than waiting for decision 54's
GIS-file wave.

THE ZERO. Closures and warnings may be empty, and an empty table counts only
beside the upstream's own count read in the same run (the dlt skill, rule 2's
second half). Each adapter says where its count comes from, in its
`zero_proof` (extract/_contract.py's Resource.zero_proof); the condition-report
sheet's is None, because its count is its own parser's. Where the rows and the
count come from one answer, the proof is exact (Resource.exact_proof).

THE KEY. NPS's two endpoints sit behind api.data.gov's gateway, which refuses a
request with no key (`API_KEY_MISSING`, answered to /robots.txt itself; the
decision 53 inventory, 2026-10-03). The key is read from NPS_API_KEY_ENV at
run time and sent as the gateway's `X-Api-Key` header, never in the URL, so no
log line, retry message or raise_for_status() text can carry it. With the
variable unset, the change check raises Unavailable: the run leaves the
resource out, logs it `unavailable`, and extract/_warehouse.py withdraws the
table, so a missing secret reads as unknown and never as "no alerts". The
public demonstration key allows 10 requests an hour (measured by the
inventory, `x-ratelimit-limit: 10`) and is never used here or in CI.

Every request sends lib/user_agent.py's USER_AGENT, through extract/_kinds.py's
session(), looked up at call time so fixture mode's swap reaches it. No two
requests to one host start closer than POLITE_GAP_SECONDS apart.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import time
import xml.etree.ElementTree as ElementTree
from collections import Counter
from dataclasses import dataclass
from urllib.parse import urlencode, urlparse

import requests

from extract import _kinds
from extract._contract import Resource, Unavailable
from lib.freshness_state import Freshness, compare_marker
from lib.http_retry import request_with_retry

NPS_API_KEY_ENV = "NPS_API_KEY"

# A host that states no Crawl-delay still gets at least this long between two
# requests: ELT.md decision 53's "Gentle on their servers", as a number. It is
# a floor this pull request's readers chose, not one any host asked for
# (@unvalidated as a courtesy; no host here has said what it wants).
# docs.google.com's robots.txt asks `Crawl-delay: 1` (read 2026-10-03), which
# this exceeds. Fixture mode and the tests set it to 0, as they reach no host.
POLITE_GAP_SECONDS = 2.0
_LAST_REQUEST_END: dict[str, float] = {}


def _get(url: str, *, headers: dict | None = None, label: str | None = None, entry: dict | None = None) -> requests.Response:
    """One GET under USER_AGENT, POLITE_GAP_SECONDS after the last request to the same host ended.

    `entry` is the reader's sources.json row, whose `redirect_hosts` the session's refusal of another host's answer
    reads (extract/_kinds.py's session()).
    """
    host = urlparse(url).hostname or ""
    last = _LAST_REQUEST_END.get(host)
    if last is not None:
        pause = last + POLITE_GAP_SECONDS - time.monotonic()
        if pause > 0:
            time.sleep(pause)
    try:
        return request_with_retry(url, session=_kinds.session(entry), headers=headers, timeout=60, label=label or url)
    finally:
        _LAST_REQUEST_END[host] = time.monotonic()


class NotJson(ValueError):
    """An answer whose body does not parse as JSON (_json): a ValueError, as the refusal always was."""


def _json(response: requests.Response, what: str):
    """The body as JSON; NotJson naming its content type, its length, where it stopped parsing and what the text holds
    there (_at_failure), and its Content-Length.

    Monthly run 17 (refresh-reference.yml 37232256991) left nps_multimedia_audio out on
    "answered 'application/json;charset=utf-8', not JSON" and nothing else, while two items
    of the same list asked again parse (2026-10-04). Whether that body was cut short or an
    error page is not known; the length and the parser's own error say so next time.

    The parser is the one `requests` picks, which in the extract job is simplejson and refuses a
    bare NaN; it is not loosened here, so an answer carrying NaN stays refused rather than landing
    a number nobody can read.
    """
    try:
        return response.json()
    except ValueError as error:
        raise NotJson(
            f"{what} answered {response.headers.get('Content-Type')!r}, not JSON: {len(response.content):,} bytes, "
            f"{error}{_at_failure(error)}; {_against_content_length(response)}"
        ) from error


#: How far before where the parser stopped _at_failure() looks for the field's name: far enough for a long key and
#: its whitespace, and only ever a name, never a value (below).
FIELD_NAME_LOOKBACK_CHARS = 200
_FIELD_NAME_BEFORE = re.compile(r'"([A-Za-z0-9_]{1,80})"\s*:\s*$')


def _at_failure(error: ValueError) -> str:
    """Which field the parser stopped in, by its name only, and how much of it arrived, for _json()'s refusal.

    "Unterminated string starting at" is raised only when the text ends before that string closes: a raw control
    character or NUL inside a string is "Invalid control character" instead, and an escaped lone surrogate or a
    byte that is not UTF-8 parses (tests/test_extract_content.py, on the simplejson the extract job installs). So
    `strict=False`, which accepts raw control characters, would not read such a body, and is not used. The position
    is where the string began, not where the text stopped, so monthly runs 19 and 20 (refresh-reference.yml
    37253303123 and 37296900535) reporting char 23,867 on 163,840 bytes and on 98,304 is what one string running
    from char 23,867 past the end of both bodies looks like, cut at two points (Reasoned from that).

    NO VALUE IS QUOTED. The log is public, and the field the parser stops in can be one this extract never loads
    because it can hold people's names (nps_multimedia_audio's `transcript` is in its row's person_fields), so
    only the field's name, read off the JSON key just before the position, and a character count reach it.
    """
    text, position = getattr(error, "doc", None), getattr(error, "pos", None)
    if not isinstance(text, str) or not isinstance(position, int):
        return ""
    named = _FIELD_NAME_BEFORE.search(text[max(0, position - FIELD_NAME_LOOKBACK_CHARS) : position])
    said = f" (in the value of {named.group(1)!r}" if named else " (in a field this could not name"
    if getattr(error, "msg", "") == "Unterminated string starting at":
        said += f"; the text ends {len(text) - position:,} characters later, still inside that string"
    return said + ")"


def _against_content_length(response: requests.Response) -> str:
    """The bytes that arrived beside the Content-Length header's own count, in words, for _json()'s refusal.

    The header counts the bytes as sent, so an encoded body (Content-Encoding: gzip) is compared by the
    bytes read off the connection (urllib3's tell()), not by its decoded length. urllib3 2 enforces the
    header and raises on a short body before this is reached, which request_with_retry asks again for; so
    a shortfall named here means a connection that did not enforce it, and "all ... arrived" means every
    byte the header promised came and the body was already cut when it was framed (Reasoned, not seen).
    """
    declared = (response.headers.get("Content-Length") or "").strip()
    if not declared.isdigit():
        return "no Content-Length to compare against"
    try:
        arrived = int(response.raw.tell())
    except (AttributeError, TypeError, ValueError, OSError):
        arrived = len(response.content)
    encoding = response.headers.get("Content-Encoding")
    sent = f"{int(declared):,} its Content-Length states" + (f" ({encoding})" if encoding else "")
    if arrived < int(declared):
        return f"{arrived:,} bytes arrived, {int(declared) - arrived:,} bytes short of the {sent}"
    return f"all {sent} arrived"


def _get_json(url: str, *, what: str, headers: dict | None = None, label: str | None = None, entry: dict | None = None):
    """_get() and then _json(), with an answer that will not parse asked for once more before it is refused.

    nps_multimedia_audio was refused on such an answer in monthly runs 16 to 19: run 18
    (refresh-reference.yml 37245577210) at 500 a page got 1,966,080 bytes, and run 19 (37253303123) at 100 a page
    163,840 bytes ending inside a string ("Unterminated string starting at: line 545 column 15"). Both are whole
    multiples of 16,384, which reads as a body cut off in transit rather than one the API wrote wrong (Reasoned
    from the two lengths, not measured: neither body was kept). So the page is asked for once more, through
    _get(), which waits POLITE_GAP_SECONDS after the last request to the host ended, and a second answer that will
    not parse is refused as the first was, so a list missing a page never lands. Run 20 (37296900535) asked one
    page twice and got 98,304 bytes both times, each ending inside a string that starts at char 23,867, where run
    19's did, so for that page one more ask does not help; whether it helps a page cut at random is @unvalidated.
    """
    try:
        return _json(_get(url, headers=headers, label=label, entry=entry), what)
    except NotJson as first:
        print(f"::warning title={what} answered a body that will not parse::{first}; asking for it once more")
        return _json(_get(url, headers=headers, label=label, entry=entry), what)


def _sha256(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


# --- NPS ----------------------------------------------------------------------


def nps_api_key() -> str:
    """The NPS key from the environment, or Unavailable: a missing secret is unknown, never an empty answer."""
    key = os.environ.get(NPS_API_KEY_ENV, "").strip()
    if not key:
        raise Unavailable(
            f"{NPS_API_KEY_ENV} is not set, so developer.nps.gov cannot be asked (its gateway refuses a request "
            "without a key); the table is withdrawn rather than read as no alerts"
        )
    return key


# The page asked for. @unvalidated as NPS's own ceiling: the coverage audit read
# "the first 500" of the national list on 2026-10-01, so 500 was served then.
# The reader steps by the rows each page returns, so a smaller server cap costs
# a request, never a row. What would settle it is one read with the real key.
NPS_PAGE_SIZE = 500
# A ceiling, not an ending: reaching it raises rather than loading a short list.
NPS_MAX_PAGES = 20

NPS_ALERT_TEXT = ("id", "url", "title", "parkCode", "description", "category", "lastIndexedDate")
NPS_ALERT_JSON = ("relatedRoadEvents",)


def nps_alerts_url(base: str, park_codes: list[str], start: int, limit: int = NPS_PAGE_SIZE) -> str:
    """The URL one page of alerts is read from: every listed code in one `parkCode`, the page's `limit` and `start`."""
    return f"{base}?{urlencode([('parkCode', ','.join(park_codes)), ('limit', limit), ('start', start)])}"


@dataclass(frozen=True)
class NpsAlerts(_kinds.PersonRuled, Resource):
    """NPS's alerts for every park code the sources.json entry lists, read in one paged request, one row per alert.

    The entry's `park_codes` maps each code to the club folders that draw on
    it, so the list and the reason for each code have one home; dbt assigns a
    club its portion from the same map (decision 34's `via` rule). Every
    alert lands as NPS serves it. `category` is NPS's own field (Park Closure,
    Danger, Caution, Information): the closures staging model reads it too, and
    which category feeds which mart is decided in dbt, never by leaving rows
    out here. No alert carries geometry: a park code is the place.

    No change check. The API sends no ETag and no Last-Modified (the
    inventory, 2026-10-03), so every run reads it: one request for the
    listed codes. THE ZERO is the response's own `total`, a string, read in
    the same answer as the rows, so the proof is exact. A total that moves
    between pages, a repeated alert id, or a read that stops short of the
    total raises, and the last good table stands.
    """

    @property
    def entry(self) -> dict:
        return _kinds.registry_entry(self.key)

    @property
    def park_codes(self) -> list[str]:
        return sorted(self.entry["park_codes"])

    @property
    def exact_proof(self) -> bool:
        return True

    @property
    def zero_proof(self) -> str:
        return "the API's own `total`, the same on every page of the read (an answer without one raises)"

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        nps_api_key()
        return Freshness.UNKNOWN, None

    def column_hints(self) -> dict:
        hints = {name: {"data_type": "text"} for name in NPS_ALERT_TEXT}
        hints.update({name: {"data_type": "json"} for name in NPS_ALERT_JSON})
        return hints

    def rows(self, proofs: dict[str, int]):
        headers = {"X-Api-Key": nps_api_key(), "Accept": "application/json"}
        base = self.entry["url"].rstrip("/")
        collected: list[dict] = []
        seen: set[str] = set()
        total: int | None = None
        start = 0
        for _ in range(NPS_MAX_PAGES):
            url = nps_alerts_url(base, self.park_codes, start)
            body = _json(_get(url, headers=headers, label=f"{self.key} from {start}", entry=self.entry), self.key)
            if not isinstance(body, dict) or not isinstance(body.get("data"), list) or body.get("total") is None:
                raise ValueError(f"{self.key}: the answer has no `total` and `data` list, so the API has changed shape")
            page_total = int(body["total"])
            if total is None:
                total = page_total
            elif page_total != total:
                raise RuntimeError(f"{self.key}: NPS counted {total} alerts and then {page_total} within one read")
            for alert in body["data"]:
                alert_id = alert.get("id")
                if not alert_id or alert_id in seen:
                    raise RuntimeError(f"{self.key}: alert id {alert_id!r} is missing or repeated, so a page was served twice")
                seen.add(alert_id)
                collected.append(alert)
            if not body["data"] or len(collected) >= total:
                break
            start += len(body["data"])
        else:
            raise RuntimeError(f"{self.key}: still paging at {NPS_MAX_PAGES} pages, a ceiling rather than an ending")
        if len(collected) != total:
            raise RuntimeError(f"{self.key}: NPS counts {total} alerts and {len(collected)} were read")
        proofs[self.table] = total
        yield from self.without_people(collected)


def nps_alerts(key: str, **overrides) -> NpsAlerts:
    entry = _kinds.registry_entry(key)
    if not entry.get("park_codes"):
        raise KeyError(f"{key}: an NPS alerts entry lists the park codes it reads in `park_codes`")
    return NpsAlerts(key=key, **overrides)


NPS_ROAD_EVENT_JSON = ("core_details", "types_of_incident", "types_of_work", "geometry")


@dataclass(frozen=True)
class NpsRoadEvents(_kinds.PersonRuled, Resource):
    """NPS's road events feed (WZDx 4.1), every event in it, one row per event with its geometry.

    The feed is national and takes no park filter. Each event's properties
    land as served, `core_details` as JSON, beside its LineString or
    MultiLineString. Two values come from the feed's own header: its
    `update_date`, and the `organization_name` of the event's data source
    (a park's name, joined on `core_details.data_source_id`), because an
    event names no park otherwise. The header's `contact_name` and
    `contact_email`, the feed's and every data source's, are never copied:
    the denylist rule for person fields is applied by building the row from
    named parts only.

    No change check: no validators (the inventory, 2026-10-03), so every run
    reads it, one request of about 457 KB. THE ZERO is a FeatureCollection
    whose `features` list is empty, the same answer the rows come from, so
    the proof is exact; anything that is not a FeatureCollection raises.
    """

    @property
    def entry(self) -> dict:
        return _kinds.registry_entry(self.key)

    @property
    def exact_proof(self) -> bool:
        return True

    @property
    def zero_proof(self) -> str:
        return "a FeatureCollection whose features list is empty, the answer the rows come from (anything else raises)"

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        nps_api_key()
        return Freshness.UNKNOWN, None

    def column_hints(self) -> dict:
        hints = {name: {"data_type": "json"} for name in NPS_ROAD_EVENT_JSON}
        hints.update(
            {
                name: {"data_type": "text"}
                for name in ("Id", "start_date", "end_date", "vehicle_impact", "data_source_organization", "feed_update_date")
            }
        )
        return hints

    def rows(self, proofs: dict[str, int]):
        headers = {"X-Api-Key": nps_api_key(), "Accept": "application/json"}
        body = _json(_get(self.entry["url"], headers=headers, label=self.key, entry=self.entry), self.key)
        if not isinstance(body, dict) or body.get("type") != "FeatureCollection" or not isinstance(body.get("features"), list):
            raise ValueError(f"{self.key}: the answer is not a FeatureCollection, so the feed has changed shape")
        info = body.get("road_event_feed_info") or {}
        organizations = {
            source.get("data_source_id"): source.get("organization_name") for source in info.get("data_sources") or []
        }
        features = body["features"]
        proofs[self.table] = len(features)
        kept = self.without_people([feature.get("properties") or {} for feature in features])
        for feature, row in zip(features, kept, strict=True):
            source_id = (row.get("core_details") or {}).get("data_source_id")
            row["data_source_organization"] = organizations.get(source_id)
            row["feed_update_date"] = info.get("update_date")
            row["geometry"] = feature.get("geometry")
            yield row


def nps_road_events(key: str, **overrides) -> NpsRoadEvents:
    _kinds.registry_entry(key)
    return NpsRoadEvents(key=key, **overrides)


# --- PA DCNR ------------------------------------------------------------------


def advisory_key(park_id: int, message: str, occurrence: int) -> str:
    """A ParkAdvisory item's key: its park and its text, plus how many identical texts that park listed before it.

    The items carry no id, title or date (measured 2026-10-03), so the text
    is the identity: an edited advisory is a new key, and decision 52's
    snapshot closes the old one and opens the new. `occurrence` keeps two
    identical advisories in one park apart instead of refusing the read.
    """
    return hashlib.sha256(f"{park_id}\x1f{occurrence}\x1f{message}".encode()).hexdigest()


@dataclass(frozen=True)
class DcnrParkAdvisories(_kinds.PersonRuled, Resource):
    """PA DCNR's ParkAdvisory answer for each park id the entry lists, one row per advisory.

    Each answer is a JSON list of `{IsAlert, Message}`, Message being HTML.
    That is all an item carries, so each row adds the park id it was asked
    for and `advisory_key` (above). The park pages' Danger and Information
    sections render from this API by script (the inventory found the page's
    `data-api-url` and `data-park-id`), which is why the coverage audit saw
    them empty.

    No change check: no validators (measured 2026-10-03), so every run reads
    each id, POLITE_GAP_SECONDS apart. THE ZERO is a 200 whose body is a JSON
    list; an empty list for every id is a proven zero (Reasoned: the API
    answers a list for a park id, and an empty one was not observed). Any
    other body raises, and the last good table stands.
    """

    @property
    def entry(self) -> dict:
        return _kinds.registry_entry(self.key)

    @property
    def park_ids(self) -> list[int]:
        return sorted(int(park_id) for park_id in self.entry["park_ids"])

    @property
    def exact_proof(self) -> bool:
        return True

    @property
    def zero_proof(self) -> str:
        """@unvalidated: an empty list was never observed, and what the API answers for a park id it no longer uses is
        unknown, so a renumbered park would read as every advisory there lifted. What would settle it: one answer for
        an id DCNR does not use, read once and recorded on the entry's sources.json row."""
        return "a 200 JSON list for every park id the entry lists, each empty (an answer that is not a list raises)"

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        return Freshness.UNKNOWN, None

    def column_hints(self) -> dict:
        return {
            "advisory_key": {"data_type": "text"},
            "park_id": {"data_type": "bigint"},
            "IsAlert": {"data_type": "bool"},
            "Message": {"data_type": "text"},
        }

    def rows(self, proofs: dict[str, int]):
        base = self.entry["url"].rstrip("/")
        collected = []
        for park_id in self.park_ids:
            asked = f"{base}?{urlencode({'id': park_id})}"
            body = _json(_get(asked, label=f"{self.key} park {park_id}", entry=self.entry), self.key)
            if not isinstance(body, list):
                raise ValueError(f"{self.key}: park {park_id} answered {type(body).__name__}, not a list of advisories")
            seen: Counter = Counter()
            for item in body:
                message = item.get("Message") if isinstance(item, dict) else None
                if not isinstance(message, str):
                    raise ValueError(f"{self.key}: park {park_id} listed an advisory with no Message text")
                occurrence = seen[message]
                seen[message] += 1
                collected.append((advisory_key(park_id, message, occurrence), park_id, item))
        proofs[self.table] = len(collected)
        kept = self.without_people([item for _, _, item in collected])
        for (advisory, park_id, _), item in zip(collected, kept, strict=True):
            yield {"advisory_key": advisory, "park_id": park_id, **item}


def dcnr_park_advisories(key: str, **overrides) -> DcnrParkAdvisories:
    entry = _kinds.registry_entry(key)
    if not entry.get("park_ids"):
        raise KeyError(f"{key}: a ParkAdvisory entry lists the park ids it reads in `park_ids`")
    return DcnrParkAdvisories(key=key, **overrides)


# --- USGS ---------------------------------------------------------------------

USGS_VOLCANO_TEXT = (
    "obs_fullname",
    "obs_abbr",
    "volcano_name",
    "vnum",
    "notice_type_cd",
    "notice_identifier",
    "sent_utc",
    "color_code",
    "alert_level",
    "notice_url",
    "notice_data",
)


@dataclass(frozen=True)
class UsgsElevatedVolcanoes(_kinds.PersonRuled, Resource):
    """Every US volcano USGS rates above normal, one row per volcano, as the Volcano Hazards Program serves it.

    `vnum` is the key: an observatory's daily update covers several volcanoes
    under one `notice_identifier` (three AVO volcanoes shared one on
    2026-10-03), so the notice cannot be. No coordinates: `vnum` joins the
    Smithsonian volcano number. No change check: no validators (the
    inventory, 2026-10-03), one request a run. THE ZERO is a 200 whose body
    is a JSON list, the answer the rows come from (an empty list is Reasoned
    to mean "nothing elevated", not observed).
    """

    @property
    def entry(self) -> dict:
        return _kinds.registry_entry(self.key)

    @property
    def exact_proof(self) -> bool:
        return True

    @property
    def zero_proof(self) -> str:
        """Reasoned, not observed: the docstring's THE ZERO, that an empty list means nothing elevated."""
        return "a 200 JSON list with no volcano in it, the answer the rows come from (anything else raises)"

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        return Freshness.UNKNOWN, None

    def column_hints(self) -> dict:
        hints = {name: {"data_type": "text"} for name in USGS_VOLCANO_TEXT}
        hints["sent_unixtime"] = {"data_type": "bigint"}
        return hints

    def rows(self, proofs: dict[str, int]):
        body = _json(_get(self.entry["url"], label=self.key, entry=self.entry), self.key)
        if not isinstance(body, list):
            raise ValueError(f"{self.key}: answered {type(body).__name__}, not a list of volcanoes")
        numbers = Counter(item.get("vnum") for item in body)
        if None in numbers or any(n > 1 for n in numbers.values()):
            raise RuntimeError(f"{self.key}: a volcano number is missing or listed twice, so it cannot key the table")
        proofs[self.table] = len(body)
        yield from self.without_people(body)


def usgs_elevated_volcanoes(key: str, **overrides) -> UsgsElevatedVolcanoes:
    _kinds.registry_entry(key)
    return UsgsElevatedVolcanoes(key=key, **overrides)


# --- MediaWiki ----------------------------------------------------------------

# A ceiling on continuation batches, not an ending: reaching it raises.
MEDIAWIKI_MAX_BATCHES = 20
MEDIAWIKI_PAGE_TEXT = ("title", "touched", "fullurl", "timestamp", "content")
MEDIAWIKI_PAGE_NUMBERS = ("pageid", "ns", "lastrevid", "length", "revid")


def mediawiki_url(api: str, params: dict) -> str:
    """The URL a MediaWiki query is read from: its parameters sorted, plus JSON in formatversion 2."""
    return f"{api}?{urlencode(sorted({**params, 'format': 'json', 'formatversion': '2'}.items()))}"


@dataclass(frozen=True)
class MediawikiAnnouncements(Resource):
    """Every page of a club's MediaWiki that transcludes the entry's `template`, one row per page, latest revision.

    MediaWiki's `embeddedin` generator lists a transclusion through another
    template too, so a page carrying a template that itself carries the
    announcement is listed, and that template's own page is a row. Each row
    is the page's id, title, `fullurl` and `touched`, and its latest
    revision's id, timestamp and wikitext. The editor's name is a person
    field and is never asked for (`rvprop` names ids, timestamp and content
    only, never `user` or `comment`).

    THE CHANGE CHECK is one small request: the listing with `prop=info`,
    hashed over each page's (pageid, lastrevid, touched) plus the count.
    `touched` moves when a template the page carries is edited, which the
    page's own revision does not. THE ZERO is the listing's own count once
    it reports `batchcomplete`, from the same answers as the rows. A
    template that no longer exists would list nothing, so the read first
    asks for the template's page and raises when it is missing, rather than
    reading a renamed template as every announcement lifted.
    """

    @property
    def entry(self) -> dict:
        return _kinds.registry_entry(self.key)

    @property
    def api(self) -> str:
        return self.entry["url"].rstrip("/")

    @property
    def template(self) -> str:
        return self.entry["template"]

    @property
    def exact_proof(self) -> bool:
        return True

    @property
    def zero_proof(self) -> str:
        return (
            "the embeddedin listing's own pages once the wiki says batchcomplete, after the template's own page is "
            "found (a missing template raises)"
        )

    def _listing(self, extra: dict) -> list[dict]:
        """Every page the generator lists, merged across continuation batches by pageid."""
        params = {
            "action": "query",
            "generator": "embeddedin",
            "geititle": self.template,
            "geilimit": "50",
            "prop": "info",
            "inprop": "url",
            **extra,
        }
        pages: dict[int, dict] = {}
        for _ in range(MEDIAWIKI_MAX_BATCHES):
            body = _json(_get(mediawiki_url(self.api, params), label=self.key, entry=self.entry), self.key)
            if not isinstance(body, dict) or "error" in body:
                raise ValueError(f"{self.key}: the wiki answered an error or no object: {str(body)[:200]}")
            for page in (body.get("query") or {}).get("pages") or []:
                merged = pages.setdefault(page["pageid"], {})
                revisions = merged.get("revisions", []) + (page.get("revisions") or [])
                merged.update(page)
                merged["revisions"] = revisions
            if "continue" not in body:
                if not body.get("batchcomplete"):
                    raise RuntimeError(f"{self.key}: the listing ended without batchcomplete, so it may be short")
                return [pages[pageid] for pageid in sorted(pages)]
            params = {**params, **body["continue"]}
        raise RuntimeError(f"{self.key}: still continuing at {MEDIAWIKI_MAX_BATCHES} batches")

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        try:
            pages = self._listing({})
        except (requests.RequestException, ValueError, KeyError, RuntimeError) as error:
            print(f"  {self.key}: change check failed ({error}); fetching")
            return Freshness.UNKNOWN, None
        marker = {
            "count": str(len(pages)),
            "set_sha256": _sha256(sorted((p.get("pageid"), p.get("lastrevid"), p.get("touched")) for p in pages)),
        }
        if recorded is None:
            return Freshness.STALE, marker
        return compare_marker(_kinds._canonical(recorded), _kinds._canonical(marker)), marker

    def column_hints(self) -> dict:
        hints = {name: {"data_type": "text"} for name in MEDIAWIKI_PAGE_TEXT}
        hints.update({name: {"data_type": "bigint"} for name in MEDIAWIKI_PAGE_NUMBERS})
        return hints

    def rows(self, proofs: dict[str, int]):
        asked = mediawiki_url(self.api, {"action": "query", "titles": self.template})
        body = _json(_get(asked, label=self.key, entry=self.entry), self.key)
        found = ((body or {}).get("query") or {}).get("pages") or []
        if not found or any(page.get("missing") or page.get("invalid") for page in found):
            raise RuntimeError(f"{self.key}: {self.template!r} is missing from the wiki, so an empty listing proves nothing")
        pages = self._listing({"prop": "info|revisions", "rvprop": "ids|timestamp|content", "rvslots": "main"})
        proofs[self.table] = len(pages)
        for page in pages:
            revision = (page.get("revisions") or [{}])[-1]
            slot = (revision.get("slots") or {}).get("main") or {}
            yield {
                **{name: page.get(name) for name in ("pageid", "ns", "title", "lastrevid", "touched", "length", "fullurl")},
                "revid": revision.get("revid"),
                "timestamp": revision.get("timestamp"),
                # MediaWiki 1.32 and later put the text in the main slot; earlier, on the revision itself.
                "content": slot.get("content", revision.get("content")),
            }


def mediawiki_announcements(key: str, **overrides) -> MediawikiAnnouncements:
    entry = _kinds.registry_entry(key)
    if not entry.get("template"):
        raise KeyError(f"{key}: a MediaWiki announcements entry names the `template` its pages transclude")
    return MediawikiAnnouncements(key=key, **overrides)


# --- Google Sheets ------------------------------------------------------------

# The columns that load, by their header text with whitespace collapsed and
# case folded, and the name each lands under. A column the sheet adds is not
# loaded until somebody reads it and adds it here: two of the sheet's eleven
# name people (FoOT's "Adopted by" and "Source of Last Condition Report",
# read 2026-10-03), so the rule is an allow list, not a denylist.
SHEET_COLUMNS = {
    "sect": "sect",
    "ranger district": "ranger_district",
    "begin": "begin_mile",
    "end": "end_mile",
    "description": "description",
    "miles": "miles",
    "last condition report submitted": "last_report_month",
    "comments": "comments",
    "shelter distance": "shelter_distance",
}
# The columns a segment row cannot be read without: a header that loses one is a sheet that changed shape.
SHEET_REQUIRED = ("sect", "begin", "end")
# Columns known to name a person. Never loaded, whatever the allow list says; listed so a test can hold them out.
SHEET_PERSON_COLUMNS = frozenset({"adopted by", "source of last condition report"})
_DATE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")


def _header_name(cell: str) -> str:
    return " ".join(cell.split()).lower()


def parse_segment_sheet(text: str) -> tuple[str | None, list[dict]]:
    """(the sheet's report date, its segment rows) from a condition-report CSV.

    The sheet is several tables one under another (measured 2026-10-03: the
    Ouachita Trail, then Black Fork Wilderness, Eagle Rock Loop and the Womble
    Trail), each a title row, a header row starting `Sect`, and its segments,
    with a legend at the foot. A segment row is one with a section and a
    begin mile under a header. The report date is the first row's one
    date-shaped cell, kept as text as served, and None when there is none
    (never filled in). Raises when no header is found or a header lacks a
    SHEET_REQUIRED column.
    """
    rows = list(csv.reader(io.StringIO(text)))
    report_date = None
    if rows:
        dates = [cell.strip() for cell in rows[0] if _DATE.match(cell.strip())]
        report_date = dates[0] if len(dates) == 1 else None
    title, columns, segments = None, None, []
    for number, row in enumerate(rows, start=1):
        cells = [cell.strip() for cell in row]
        names = [_header_name(cell) for cell in row]
        if names and names[0] == "sect":
            missing = [name for name in SHEET_REQUIRED if name not in names]
            if missing:
                raise ValueError(f"row {number}: a header without {missing}, so the sheet has changed shape")
            columns = {index: SHEET_COLUMNS[name] for index, name in enumerate(names) if name in SHEET_COLUMNS}
            continue
        if cells and cells[0] and not any(cells[1:]):
            title, columns = cells[0], None
            continue
        if columns is None or not cells or not cells[0]:
            continue
        values = {name: (cells[index] if index < len(cells) else "") for index, name in columns.items()}
        if not values.get("begin_mile"):
            continue
        segments.append({"table_title": title, **values, "row_number": number, "report_date": report_date})
    if not segments:
        raise ValueError("no segment rows under a `Sect` header, so the sheet has changed shape or is not this report")
    return report_date, segments


@dataclass(frozen=True)
class SheetCsvSegments(Resource):
    """A Google Sheet's CSV export, read as a trail condition report: one row per segment, person columns never kept.

    The entry's `url` is the export (`/export?format=csv&gid=…`), which
    docs.google.com's robots.txt allows for every agent (`Allow:
    /spreadsheet`, the longest match, read 2026-10-03) and which redirects to
    a googleusercontent.com host whose /robots.txt answered 404 (no rules,
    RFC 9309) that day. The columns kept are SHEET_COLUMNS, an allow list.

    WHAT THE CSV DOES NOT CARRY. The sheet colours each segment's cells by
    condition (its legend: green clear, yellow impediments, red difficult to
    follow, gray no report, and two more), and a CSV export holds values,
    not fills, so that status does not land. The xlsx export carries it, and
    would need a spreadsheet reader the extract job does not install.

    No change check: no validators. One request a run. A segment table is
    never empty, so zero segments raises rather than proving a zero; the
    proof is the segment count read from the same answer.
    """

    @property
    def entry(self) -> dict:
        return _kinds.registry_entry(self.key)

    @property
    def exact_proof(self) -> bool:
        return True

    @property
    def zero_proof(self) -> None:
        """None: the count is the segments this reader's parser finds in a sheet laid out for people (title rows, a
        legend, several tables stacked), not a count the sheet states. Zero segments raise first, and a warnings table
        of this kind keeps the shrink floor (extract/_run.py's run_check), so a sheet half rearranged is refused rather
        than read as half its segments gone."""
        return None

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        return Freshness.UNKNOWN, None

    def column_hints(self) -> dict:
        names = ("table_title", *SHEET_COLUMNS.values(), "report_date")
        hints = {name: {"data_type": "text"} for name in names}
        hints["row_number"] = {"data_type": "bigint"}
        return hints

    def rows(self, proofs: dict[str, int]):
        response = _get(self.entry["url"], label=self.key, entry=self.entry)
        if "csv" not in (response.headers.get("Content-Type") or ""):
            raise ValueError(f"{self.key}: answered {response.headers.get('Content-Type')!r}, not CSV")
        _, segments = parse_segment_sheet(response.content.decode("utf-8-sig"))
        proofs[self.table] = len(segments)
        yield from segments


def sheet_csv_segments(key: str, **overrides) -> SheetCsvSegments:
    entry = _kinds.registry_entry(key)
    if "format=csv" not in entry.get("url", ""):
        raise KeyError(f"{key}: the entry's url is not a CSV export")
    return SheetCsvSegments(key=key, **overrides)


# --- Google My Maps (KML) -----------------------------------------------------

KML = "{http://www.opengis.net/kml/2.2}"
KML_GEOMETRIES = ("Point", "LineString", "Polygon", "MultiGeometry")


def _kml_coordinates(element) -> list[list[float]]:
    """A KML `coordinates` element's `lon,lat[,alt]` tuples as GeoJSON positions, the altitude dropped."""
    text = element.text if element is not None else ""
    return [[float(part) for part in token.split(",")[:2]] for token in (text or "").split()]


def _kml_geometry(element) -> dict | None:
    """One KML geometry element as GeoJSON, or None for a kind this reader does not know."""
    tag = element.tag.removeprefix(KML)
    if tag == "Point":
        return {"type": "Point", "coordinates": _kml_coordinates(element.find(f"{KML}coordinates"))[0]}
    if tag == "LineString":
        return {"type": "LineString", "coordinates": _kml_coordinates(element.find(f"{KML}coordinates"))}
    if tag == "Polygon":
        rings = [element.find(f"{KML}outerBoundaryIs/{KML}LinearRing/{KML}coordinates")]
        rings += element.findall(f"{KML}innerBoundaryIs/{KML}LinearRing/{KML}coordinates")
        return {"type": "Polygon", "coordinates": [_kml_coordinates(ring) for ring in rings]}
    if tag == "MultiGeometry":
        parts = [_kml_geometry(child) for child in element if child.tag.removeprefix(KML) in KML_GEOMETRIES]
        return {"type": "GeometryCollection", "geometries": [part for part in parts if part is not None]}
    return None


def parse_kml_placemarks(text: str) -> list[dict]:
    """Every Placemark in a KML document, in document order, with the name of the Folder it sits in.

    Nothing is parsed out of a placemark's text: its name, description (HTML
    or plain, as served), styleUrl and any ExtendedData land as they are, and
    dbt reads a status out of them. A placemark with a geometry this reader
    does not know lands with a null geometry rather than being dropped.
    """
    root = ElementTree.fromstring(text)
    rows: list[dict] = []

    def walk(node, folder: str | None) -> None:
        for child in node:
            tag = child.tag.removeprefix(KML)
            if tag == "Folder":
                walk(child, child.findtext(f"{KML}name"))
            elif tag == "Document":
                walk(child, folder)
            elif tag == "Placemark":
                geometry = next((g for g in child if g.tag.removeprefix(KML) in KML_GEOMETRIES), None)
                extended = child.find(f"{KML}ExtendedData")
                data = (
                    {item.get("name"): item.findtext(f"{KML}value") for item in extended.findall(f"{KML}Data")}
                    if extended is not None
                    else None
                )
                rows.append(
                    {
                        "folder": folder,
                        "name": child.findtext(f"{KML}name"),
                        "description": child.findtext(f"{KML}description"),
                        "style_url": child.findtext(f"{KML}styleUrl"),
                        "extended_data": data,
                        "placemark_index": len(rows),
                        "geometry": _kml_geometry(geometry) if geometry is not None else None,
                    }
                )

    walk(root, None)
    return rows


@dataclass(frozen=True)
class MyMapsPlacemarks(_kinds.PersonRuled, Resource):
    """A Google My Maps map's KML export, one row per placemark: its folder, name, description, style and geometry.

    The entry's `url` is the export (`/maps/d/kml?mid=…&forcekml=1`), which
    www.google.com's robots.txt allows for every agent: `Disallow: /maps/`
    but the longer `Allow: /maps/d/` wins (RFC 9309's longest match; the
    decision 53 inventory, 2026-10-03). FMST's map, the first, records each
    line's status twice, and both land as served: in the description's
    "Trail Status" line, and in the line's style, whose colour the map's own
    legend reads (red closed, orange detour, green open, yellow open but not
    assessed). Which is the status is dbt's to read, not this reader's.

    No change check: no ETag, no Last-Modified, `cache-control: no-store`
    (measured 2026-10-03), so every run reads the whole file, about 1.7 MB.
    A status map with no placemarks is a broken read, not every closure
    lifted, so zero placemarks raises; the proof is the placemark count read
    from the same document.
    """

    @property
    def entry(self) -> dict:
        return _kinds.registry_entry(self.key)

    @property
    def exact_proof(self) -> bool:
        return True

    @property
    def zero_proof(self) -> str:
        """Google's KML export of the map, a fixed format: its placemarks are the map's own. Zero placemarks raise first."""
        return "the placemarks of My Maps' own KML export of the map; a map with none raises before any zero"

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        return Freshness.UNKNOWN, None

    def column_hints(self) -> dict:
        hints = {name: {"data_type": "text"} for name in ("folder", "name", "description", "style_url")}
        hints.update({"extended_data": {"data_type": "json"}, "geometry": {"data_type": "json"}})
        hints["placemark_index"] = {"data_type": "bigint"}
        return hints

    def rows(self, proofs: dict[str, int]):
        response = _get(self.entry["url"], label=self.key, entry=self.entry)
        content_type = response.headers.get("Content-Type") or ""
        if "xml" not in content_type and "kml" not in content_type:
            raise ValueError(f"{self.key}: answered {content_type!r}, not KML")
        placemarks = parse_kml_placemarks(response.content.decode("utf-8"))
        if not placemarks:
            raise RuntimeError(f"{self.key}: the map's KML holds no placemark, which is a broken read, not a quiet trail")
        proofs[self.table] = len(placemarks)
        # ExtendedData is the map maker's own fields, named as they chose, so the person rule reads its names; the
        # placemark's other columns are KML's own and this reader's.
        with_data = [placemark for placemark in placemarks if placemark["extended_data"] is not None]
        for placemark, data in zip(with_data, self.without_people([p["extended_data"] for p in with_data]), strict=True):
            placemark["extended_data"] = data
        yield from placemarks


def my_maps_placemarks(key: str, **overrides) -> MyMapsPlacemarks:
    entry = _kinds.registry_entry(key)
    if "/maps/d/kml" not in entry.get("url", ""):
        raise KeyError(f"{key}: the entry's url is not a My Maps KML export")
    return MyMapsPlacemarks(key=key, **overrides)
