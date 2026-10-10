"""Decision 54 wave 3's content readers (section C): podcasts without their people, NPS's content lists, and
narrower reads of kinds that already exist.

pipeline/ELT.md, "Loading everything the clubs publish (decision 54)", wave 3, is the plan: the feeds and APIs
the clubs publish for suggested hikes, podcasts, challenges and photos. Each reader here is a subclass of a kind
that already reads its platform, and changes only what that kind could not do, so the paging, the change check
and the count-as-proof are the ones already tested (extract/_kinds.py, extract/_json_apis.py):

    podcast_episodes(key)         a podcast's RSS feed, one row per episode, with every tag that names a person
                                  left out (PodcastEpisodes, from _kinds.py's PodcastFeed)
    nps_content(key)              one of NPS's content lists, every row, national or for the park codes another
                                  registry row lists (NpsContent, from _json_apis.py's NpsAlerts)
    wordpress_child_pages(key, parent)
                                  a WordPress page's child pages, read whole: a guide published as pages under
                                  one parent (WordpressChildPages, from _kinds.py's WordpressPosts)
    site_terms(key, taxonomies)   a post type's own taxonomy terms, on the type's lane and at the host's
                                  Crawl-delay (SiteTerms, from _kinds.py's WordpressTerms)
    mediawiki_template_pages(key) a MediaWiki's pages that transclude one template, as a dataset of its own beside
                                  another template on the same wiki (MediawikiTemplatePages, from _json_apis.py's
                                  MediawikiAnnouncements)

WHY NOT podcast_feed AS IT IS. PodcastFeed lands every child of an <item> as a column, which is how nothing a
feed carries is dropped before dbt, and also how a person lands: the live reads of 2026-10-04 (section C's
worker, under lib/user_agent.py's agent, robots.txt first) found an item's `itunes:author` holding the guests'
names (AMC's Unlikely Stories, on 11 of 11 items; NHPR's Something Wild, its hosts' names on every item) and staff e-mail addresses (USGS's Outstanding in the Field, on 11 of 11 items), RSS
`<author>` holding an e-mail address (Unlikely Stories, 11 of 11), `dc:creator` naming a person (BLM's On the
Ground, The Trustees' feed) and `podcast:person` naming each guest (USGS). Decision 59 and the dlt skill's
"People never ship, and are never loaded" leave those out by an explicit list, before dlt sees the row, so
PodcastEpisodes drops PERSON_TAGS, then whatever extract/_kinds.py's PersonRule leaves out: the registry row's own
`person_fields` (an episode description that carries an e-mail address or a telephone number, measured per feed
and listed on its row) and a column named like a person's. The rest is
PodcastFeed's, and the lane is the type's, podcasts, which is monthly (extract/_contract.py's CADENCE_BY_TYPE):
no reader here rides the hourly lane or a notices leg.

Every request names the project (extract/_kinds.py's session(), looked up when a reader runs, so fixture mode's
swap reaches it) and waits at least DEFAULT_HOST_GAP_SECONDS after the last one to its host, or the host's
Crawl-delay where the registry row records one (extract/_notices.py's polite()).
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from urllib.parse import urlencode

import requests

from extract import _json_apis, _kinds
from extract._notices import DEFAULT_HOST_GAP_SECONDS, polite
from lib.freshness_state import Freshness, compare_marker
from lib.http_retry import request_with_retry

# --- Podcasts -----------------------------------------------------------------------------------------------------

# The feed namespaces and the tags that name a person live beside PodcastFeed in extract/_kinds.py, which
# drops them too; they are imported here under the names this module has always used.
ITUNES = _kinds.ITUNES
PODCAST_INDEX = _kinds.PODCAST_INDEX
DUBLIN_CORE = _kinds.DUBLIN_CORE
GOOGLE_PLAY = _kinds.GOOGLE_PLAY
PERSON_TAGS = _kinds.PERSON_TAGS


@dataclass(frozen=True)
class PodcastEpisodes(_kinds.PodcastFeed):
    """A podcast's RSS feed, one row per episode, as PodcastFeed lands it, with PERSON_TAGS and what PersonRule
    leaves out (the row's `person_fields` among it) gone.

    Three changes, each for something the live feeds carry:

    - PEOPLE (the module docstring). The tags are dropped before the row is built, and a `person_fields` name is
      the column as it would land (`description`, `content_encoded`, `itunes_summary`): a feed whose episode
      notes carry an e-mail address or a telephone number lists every column that repeats them, because
      decision 59 leaves such a column out whole rather than redacting it.
    - AN ATTRIBUTE IS A VALUE. `itunes:image` and `podcast:transcript` carry their URL in `href` and `url` and
      no text, so PodcastFeed's text-only read landed them empty; here an element with no text lands the first
      of `href` and `url` it has.
    - POLITE. The change check and the read wait DEFAULT_HOST_GAP_SECONDS between requests to one host, or the
      row's `crawl_delay`, which no podcast host asked for on 2026-10-04.

    THE COUNT is the item count of the same answer the rows come from, so the proof is exact. A feed is what
    its host serves, and some serve a window: NHPR's Something Wild lists 20 episodes while the Society for the
    Protection of New Hampshire Forests holds 166 transcript pages, so no model may read an episode's absence
    as its removal.
    """

    crawl_delay: float = 0.0

    @property
    def exact_proof(self) -> bool:
        return True

    @property
    def zero_proof(self) -> str:
        """PodcastFeed's, restated because this reads the feed again: the channel's items, from the answer rows() parses."""
        return "the RSS <channel>'s own items, in the answer the rows come from; a body with no <channel> raises"

    def _session(self) -> requests.Session:
        return polite(_kinds.session(), max(self.crawl_delay, DEFAULT_HOST_GAP_SECONDS))

    def change_check(self, recorded: dict | None) -> tuple[Freshness, dict | None]:
        """PodcastFeed's: a conditional GET with the feed's own validators, a 304 FRESH, neither validator UNKNOWN."""
        headers = {}
        if recorded:
            if recorded.get("etag"):
                headers["If-None-Match"] = recorded["etag"]
            if recorded.get("last_modified"):
                headers["If-Modified-Since"] = recorded["last_modified"]
        try:
            response = request_with_retry(self.entry["url"], session=self._session(), headers=headers or None, timeout=30)
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
        return compare_marker(_kinds._canonical(recorded), _kinds._canonical(marker)), marker

    def column_hints(self) -> dict:
        hints = {
            name: {"data_type": "text"}
            for name in ("show_title", "show_link", "guid", "title", "link", "pubDate", "enclosure_url", "enclosure_type")
        }
        hints.update({"feed_items": {"data_type": "bigint"}, "_row": {"data_type": "bigint"}})
        return hints

    def rows(self, proofs: dict[str, int]):
        response = request_with_retry(self.entry["url"], session=self._session(), timeout=60)
        channel = ElementTree.fromstring(response.content).find("channel")
        if channel is None:
            raise ValueError(f"{self.key}: the answer is not an RSS feed (no <channel>)")
        items = channel.findall("item")
        proofs[self.table] = len(items)
        show = {"show_title": channel.findtext("title"), "show_link": channel.findtext("link"), "feed_items": len(items)}
        episodes = []
        for item in items:
            row = {}
            for child in item:
                if child.tag in PERSON_TAGS:
                    continue
                column = _kinds._feed_column(child.tag)
                if column == "enclosure":
                    row["enclosure_url"] = child.get("url")
                    row["enclosure_length"] = child.get("length")
                    row["enclosure_type"] = child.get("type")
                    continue
                text = (child.text or "").strip() or None
                row[column] = text if text is not None else (child.get("href") or child.get("url"))
            episodes.append(row)
        for position, row in enumerate(self.without_people(episodes)):
            yield {**show, "_row": position, **row}


def podcast_episodes(key: str, *, crawl_delay: float = 0.0, **overrides) -> PodcastEpisodes:
    resource = PodcastEpisodes(key=key, crawl_delay=crawl_delay, **overrides)
    if _kinds.source_kind(resource.entry) != _kinds.PODCAST_FEED:
        raise ValueError(f"{key} is a {_kinds.source_kind(resource.entry)}, not a {_kinds.PODCAST_FEED}")
    return resource


# --- NPS's content lists ------------------------------------------------------------------------------------------

# The page asked for. The reader steps by the rows each page returns, so a smaller cap on the server costs a
# request, never a row. 100, not NpsAlerts' 500: monthly runs 16, 17 and 18 left nps_multimedia_audio out, and run
# 18 (refresh-reference.yml 37245577210) said why: a 500-item page arrived as 1,966,080 bytes ending inside a
# string ("Unterminated string ... char 1783562"), cut short in transit (Reasoned: two items of the same list parse,
# 2026-10-04). A page of 100 is about a fifth of that, at 52 requests for the audio list's 5,173 items.
# Run 19 (37253303123) says 100 does not keep every page whole: a page arrived as 163,840 bytes ending inside a
# string. So a page that will not parse is asked for once more (extract/_json_apis.py's _get_json) before the list
# is refused. Run 20 (37296900535) asked that page twice and got 98,304 bytes both times, still ending inside a
# string, so for that page the second ask does not get it whole (_json_apis._at_failure says why the same position).
NPS_CONTENT_PAGE_SIZE = 100
# @unvalidated: a ceiling, not an ending, picked above the largest list these rows read (the gallery assets for
# the clubs' 27 park codes, 14,630 on 2026-10-04, 147 pages of 100) and below NPS's whole gallery-asset list
# (206,685, 2,067 pages), so a park-code read the API stopped honouring raises rather than loading every photo NPS
# holds; reaching it raises rather than loading a short list. What would settle it is the page count a few monthly
# runs print.
NPS_CONTENT_MAX_PAGES = 400


#: Each list's columns that staging reads, by the endpoint's path, hinted so a column is there even on a run where
#: every row leaves it null (dlt creates no column it never saw a value for). The names are the ones each endpoint
#: served on 2026-10-04; a nested value is JSON. Every other field lands as dlt infers it.
NPS_CONTENT_COLUMNS = {
    "multimedia/audio": {"permalinkUrl": "text", "description": "text", "versions": "json", "relatedParks": "json"},
    "multimedia/galleries/assets": {
        "permalinkUrl": "text",
        "description": "text",
        "credit": "text",
        "constraintsInfo": "json",
        "fileInfo": "json",
        "relatedParks": "json",
    },
    "passportstamplocations": {"label": "text", "type": "text", "parks": "json"},
    "thingstodo": {"url": "text", "shortDescription": "text", "relatedParks": "json", "activities": "json"},
    "tours": {"description": "text", "park": "json", "activities": "json", "stops": "json"},
}


class RepeatedId(RuntimeError):
    """An NPS list served a key it had already served within one read: a page served twice, or two items under one key."""


def _repeated(fields: list[str], value: str, first: dict, again: dict) -> str:
    """The refusal's words for two items under one key: the key, and the names of the fields the two differ in.

    Names only, never what either copy holds, so no person field's value reaches a log (decision 59).
    """
    differing = sorted(
        name
        for name in {*first, *again}
        if json.dumps(first.get(name), sort_keys=True) != json.dumps(again.get(name), sort_keys=True)
    )
    copies = f"the copies differing in {', '.join(differing)}" if differing else "the copies exact"
    return (
        f"{' / '.join(fields)} {value!r} is repeated within one read, {copies}: a page served twice, or two items under one key"
    )


def nps_content_url(base: str, park_codes: list[str], start: int, limit: int = NPS_CONTENT_PAGE_SIZE) -> str:
    """One page's URL: `parkCode` only when the row names codes (none reads the national list), then `limit`, `start`."""
    query = [("parkCode", ",".join(park_codes))] if park_codes else []
    return f"{base}?{urlencode([*query, ('limit', limit), ('start', start)])}"


@dataclass(frozen=True)
class NpsContent(_json_apis.NpsAlerts):
    """One of NPS's content lists (audio, gallery assets, passport stamp locations, things to do, tours), every row.

    Read as NpsAlerts reads the alerts, through api.data.gov's gateway with NPS_API_KEY as the `X-Api-Key`
    header: with the variable unset the change check raises Unavailable, so the run leaves the resource out
    and the table is withdrawn, never read as an empty list. No change check otherwise (the API sends no
    validators), so every run reads the list. THE ZERO and THE COUNT are the answer's own `total`, read on
    every page: a total that moves within one read, a missing `id`, a repeated key on a second read (the first
    is read again, `rows`), or a read that ends short of the total raises, and the last good table stands.
    The key is the registry row's `key_fields`, the fields staging keys the table on (`id` where it names
    none), so two items NPS lists under one `id` at two URLs land on a key of `id` and `url`, and two copies of
    one key still refuse, naming the fields they differ in and never the values (_repeated).

    THE SCOPE is the registry row's: national when it names no park codes, or the codes another row lists in
    `park_codes`, named by `park_codes_from` (nps_alerts' map, the one home for which club folder draws on
    which park, decision 34). A row is landed as NPS serves it, nested lists and objects as JSON, except the
    top-level fields extract/_kinds.py's PersonRule leaves out before dlt sees the row: its row's `person_fields`,
    matched in any case, and a field named like a person's. A gallery asset's own `credit` and
    `constraintsInfo` are that photo's credit line and licence and land as they are: no park's or site's
    licence is ever written onto a photo here.
    """

    @property
    def park_codes(self) -> list[str]:
        source = self.entry.get("park_codes_from")
        if not source:
            return []
        return sorted(_kinds.registry_entry(source)["park_codes"])

    @property
    def key_fields(self) -> list[str]:
        """The fields one item is told apart by: the row's `key_fields`, as JsonFeatures' _copies reads them."""
        return list(self.entry.get("key_fields") or ["id"])

    @property
    def zero_proof(self) -> str:
        """NpsAlerts', restated because _read_list() reads the list again: the `total` every page states."""
        return "the API's own `total`, the same on every page of the read (an answer without one raises)"

    def column_hints(self) -> dict:
        path = self.entry["url"].rstrip("/").split("/api/v1/", 1)[-1]
        # Every list titles its rows but the stamp locations, which label them (`label`, hinted below).
        hints = {name: {"data_type": "text"} for name in ("id", "title") if (name, path) != ("title", "passportstamplocations")}
        hints.update({name: {"data_type": kind} for name, kind in NPS_CONTENT_COLUMNS.get(path, {}).items()})
        return hints

    def rows(self, proofs: dict[str, int]):
        """Every row, read once more where the first read met a key it had already read; refused if the second does too.

        NPS's start/limit order wobbled at a page boundary in monthly runs 17
        and 18 (refresh-reference.yml 37232256991 and 37245577210), and
        nps_things_to_do refused on the same repeated id both times, with no
        second read where JsonFeatures over the same API reads again (review
        finding EXD-9). So a repeat is read again once, as
        extract/_ogc.py's JsonFeatures._consistent_read does; a second read
        that repeats an id too is refused, so a list one item short never
        lands, and the last committed table stands.

        That id was not a wobble: runs 19 and 20 (37253303123 and
        37296900535) refused on it again at pages of 100 rather than 500, run
        20 on both of its reads, so NPS lists it twice (Reasoned from the
        four refusals), and nps_things_to_do now keys on `id` and `url`.
        """
        headers = {"X-Api-Key": _json_apis.nps_api_key(), "Accept": "application/json"}
        try:
            collected, total = self._read_list(headers)
        except RepeatedId as repeat:
            print(f"::warning title={self.key} read a key twice::{repeat}; reading the list again, once")
            collected, total = self._read_list(headers)
        proofs[self.table] = total
        yield from self.without_people(collected)

    def _read_list(self, headers: dict) -> tuple[list[dict], int]:
        """One whole read of the list, page by page, held to the `total` every page states."""
        base, codes, fields = self.entry["url"].rstrip("/"), self.park_codes, self.key_fields
        collected: list[dict] = []
        seen: dict[str, dict] = {}
        total: int | None = None
        start = 0
        for _ in range(NPS_CONTENT_MAX_PAGES):
            url = nps_content_url(base, codes, start)
            page = f"{self.key} from {start}"  # the page asked for, so a refusal says which one
            body = _json_apis._get_json(url, what=page, headers=headers, label=page, entry=self.entry)
            if not isinstance(body, dict) or not isinstance(body.get("data"), list) or body.get("total") is None:
                raise ValueError(f"{self.key}: the answer has no `total` and `data` list, so the API has changed shape")
            page_total = int(body["total"])
            if total is None:
                total = page_total
            elif page_total != total:
                raise RuntimeError(f"{self.key}: NPS counted {total} rows and then {page_total} within one read")
            for row in body["data"]:
                row_id = row.get("id") if isinstance(row, dict) else None
                if not row_id:
                    raise RuntimeError(f"{self.key}: id {row_id!r} is missing, so the API has changed shape")
                value = " / ".join(str(row.get(field)) for field in fields)  # as JsonFeatures' _copies joins it
                if value in seen:
                    raise RepeatedId(f"{self.key}: {_repeated(fields, value, seen[value], row)}")
                seen[value] = row
                collected.append(row)
            if not body["data"] or len(collected) >= total:
                break
            start += len(body["data"])
        else:
            raise RuntimeError(f"{self.key}: still paging at {NPS_CONTENT_MAX_PAGES} pages, a ceiling rather than an ending")
        if len(collected) != total:
            raise RuntimeError(f"{self.key}: NPS counts {total} rows and {len(collected)} were read")
        return collected, total


def nps_content(key: str, **overrides) -> NpsContent:
    entry = _kinds.registry_entry(key)
    if source := entry.get("park_codes_from"):
        if not _kinds.registry_entry(source).get("park_codes"):
            raise KeyError(f"{key}: park_codes_from names {source!r}, which lists no `park_codes`")
    return NpsContent(key=key, **overrides)


# --- A WordPress guide published as child pages -------------------------------------------------------------------


@dataclass(frozen=True)
class WordpressChildPages(_kinds.WordpressPosts):
    """Every child page of one WordPress page, a row each, read whole through `/wp/v2/pages?parent=<id>`.

    WordpressPosts reads a category or a whole post type; a guide that a club publishes as pages under one
    parent (New Mexico Volunteers for the Outdoors' "Hike New Mexico", page 2040, 38 children on 2026-10-04) is
    neither, and reading every page of the site would land its donation and membership pages too. So the scope
    is the parent's id, and everything else is WordpressPosts': X-WP-Total as the count and the proof, the
    (id, modified) set as the change check, and PersonRule's leaving out of WP_DROPPED and the row's `person_fields`.
    """

    parent: int = 0

    @property
    def zero_proof(self) -> str:
        """WordpressPosts', restated because the scope differs: the X-WP-Total the pages route states for this parent."""
        return "the site's X-WP-Total for the parent page's children (wp_list())"

    def scope(self, http: requests.Session) -> dict:
        return {"parent": str(self.parent)}


def wordpress_child_pages(key: str, parent: int, **overrides) -> WordpressChildPages:
    if not parent:
        raise ValueError(f"{key}: wordpress_child_pages needs the parent page's id")
    resource = WordpressChildPages(key=key, post_type="pages", parent=int(parent), **overrides)
    if refused := _kinds.query_refused(resource.entry["url"]):
        raise ValueError(f"{key}: {refused}, and every WordPress list request carries one")
    return resource


@dataclass(frozen=True)
class SiteTerms(_kinds.WordpressTerms):
    """WordpressTerms for a post type's own taxonomies, on the type's lane, sent at the host's Crawl-delay.

    The WordPress hike post types carry their facts as taxonomy ids (the Green Mountain Club's `hikes`: difficulty,
    distance, hike-feature, hike-status, hike-type and region, read 2026-10-04), so their terms are a table beside
    the posts, `<posts table>_terms`, as NYNJTC's are. Two differences from `wordpress_terms`: the cadence is the
    type's (monthly for suggested hikes; a renamed hike term moves no safety fact, so the daily read NYNJTC's alert
    terms take buys nothing here), and every request waits the host's Crawl-delay, or DEFAULT_HOST_GAP_SECONDS
    (greenmountainclub.org asks 10).
    """

    crawl_delay: float = 0.0

    @property
    def zero_proof(self) -> str:
        """WordpressTerms', restated because rows() is this class's own: each taxonomy's X-WP-Total, summed."""
        return "the sum of each taxonomy's X-WP-Total; an empty taxonomy raises before any zero"

    def rows(self, proofs: dict[str, int]):
        http = polite(_kinds.session(), max(self.crawl_delay, DEFAULT_HOST_GAP_SECONDS))
        rows, totals = [], []
        for taxonomy in self.taxonomies:
            terms, total = _kinds.wp_list(self.api, taxonomy, {"_fields": "id,name,slug,count"}, http)
            if not terms:
                raise RuntimeError(f"{self.key}: the {taxonomy!r} taxonomy came back empty, which is a broken read")
            if total is not None and len(terms) < total:
                raise RuntimeError(f"{self.key}: {taxonomy} counts {total} terms and {len(terms)} were read")
            totals.append(total)
            rows.extend({**term, "taxonomy": taxonomy} for term in terms)
        if all(total is not None for total in totals):
            proofs[self.table] = sum(totals)
        yield from rows


def site_terms(key: str, taxonomies: tuple[str, ...], *, crawl_delay: float = 0.0, **overrides) -> SiteTerms:
    if refused := _kinds.query_refused(_kinds.registry_entry(key)["url"]):
        raise ValueError(f"{key}: {refused}, and every WordPress list request carries one")
    if not taxonomies:
        raise ValueError(f"{key}: site_terms needs the taxonomies a post is tagged from")
    return SiteTerms(key=key, taxonomies=tuple(taxonomies), crawl_delay=crawl_delay, **overrides)


# --- A MediaWiki template's pages, beside another template on the same wiki ---------------------------------------


@dataclass(frozen=True)
class MediawikiTemplatePages(_json_apis.MediawikiAnnouncements):
    """MediawikiAnnouncements' read (every page that transcludes the row's `template`, latest revision, no editor)
    for a template other than the one a notice row reads on the same wiki.

    One wiki's api.php is one URL, and two templates on it are two datasets: TEHCC's `Template:Announcement`
    pages are its notices (decision 53), its `Template:Trail` and `Template:Hike` pages its trail and hike
    write-ups. `part` is the template, so the layout test's one-extraction rule tells the reads apart by what
    the server is asked for, as it tells NYNJTC's posts from its terms.
    """

    @property
    def part(self) -> str:
        return self.template

    @property
    def zero_proof(self) -> str:
        """MediawikiAnnouncements', restated: the same read, for another template."""
        return (
            "the embeddedin listing's own pages once the wiki says batchcomplete, after the template's own page is "
            "found (a missing template raises)"
        )


def mediawiki_template_pages(key: str, **overrides) -> MediawikiTemplatePages:
    entry = _kinds.registry_entry(key)
    if not entry.get("template"):
        raise KeyError(f"{key}: a MediaWiki template entry names the `template` its pages transclude")
    return MediawikiTemplatePages(key=key, **overrides)
