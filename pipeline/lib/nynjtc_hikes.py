"""Reading NYNJTC's Favorite Hikes - the twenty public pages of
nynjtc.org/favorite-hikes - into facts a route can be built from (#1290).

This module owns one job: **turn one WordPress `hike` post into facts**. It
owns nothing about whether those facts may be published (sources.json's
`nynjtc_hikes_licence`), nothing about where the route goes on the ground
(`route_nynjtc_hikes.py` and the reviewed rows in
reference/nynjtc_hike_routes.json), and nothing about the network. That split
is `lib/nynjtc_alerts.py`'s and is kept for the same reason: the parse is
tested here without a network, and the policy without one.

WHAT A PAGE IS, measured against the live API on 2026-09-09 (59 posts of
type `hike`, 20 public, 39 answering `content.protected: true`, which is
NYNJTC's own password gate and is not walked through - the maintainer's
instruction was "just do the 20 public ones"):

    GET /wp-json/wp/v2/hike?per_page=100&_embed=1

Each post carries the hike's categorisation as closed taxonomies - difficulty
in five levels, a distance bucket, a time commitment, a route type, the park,
county, region and state, the trails it uses - resolved to `{slug, name}` by
the `_embed` expansion, so no second request per vocabulary is needed. The
BODY is a WordPress block layout in one skeleton on nineteen of the twenty:
a title, the featured photo with a "Photo by" credit, the tag table, two or
three paragraphs of overview, an `<h2>How to Get There</h2>` with a Google
Maps embed whose marker is the trailhead, a shop block, and a
`<details><summary>Detailed Hike Description</summary>` block opening with a
`Publication:` line and carrying the turn-by-turn prose. The twentieth
(`catskill-fire-towers`) is a set of five map PDFs with no route, no map and
no description, and parses into a record with those absences rather than
into nothing - a reviewer sees it and holds it.

THE TRAILHEAD IS THE ONE COORDINATE NYNJTC PUBLISHES, and it is inside the
map embed's `pb=` parameter rather than in any field. Two shapes were
measured. A PLACED MARKER embed carries `...!4m3!3m2!1d<lat>!2d<lon>...`
after the viewport, and that pair is the trailhead (19 of 19 pages with an
embed, checked by eye against the parking their description names). A
PLACE-CARD embed (`forest-view-closter-dock-trail-loop...`) carries only the
viewport `!1d<scale>!2d<lon>!3d<lat>` and a Google place id, and its
viewport centre is the place - read as the start at LOWER confidence, and
said so in `start_basis`. The viewport's own `!1d` is a scale in metres
(17,446 on that page) and would parse as a latitude of 17,446° if the pairs
were taken blindly; `LAT_RANGE`/`LON_RANGE` are the guard.

WHAT IS DELIBERATELY NOT READ. The Avenza link the shop block carries (the
maintainer: "Leave Avenza out"). The "Trails Related to this Hike" list,
because the `trail` taxonomy already carries the same names as data. The
shop, membership and donate blocks. The `yoast_head` SEO copy.
"""

from __future__ import annotations

import html as html_module
import re
from dataclasses import dataclass, field
from datetime import date, datetime

#: The registry key this source's records are namespaced by, matching its
#: `sources.json` entry.
SOURCE_KEY = "nynjtc_favorite_hikes"

#: The custom post type's REST route under /wp-json/wp/v2/. Read off the
#: site's own `/wp-json/wp/v2/types` on 2026-09-09.
HIKE_ROUTE = "hike"

#: The taxonomies a hike is tagged from, as the REST route names them. The
#: `_embed` expansion returns every one that has a term on the post, so this
#: is the vocabulary a record CAN carry rather than a list each post must
#: fill - a page with no `dogs` term carries no `dogs` key.
TAXONOMIES = (
    "difficulty",
    "distance",
    "time-commitment",
    "route-type",
    "access",
    "dogs",
    "accessibility",
    "park",
    "county",
    "region",
    "state",
    "trail",
    "hike-feature",
    "allowed-use",
)

#: NYNJTC's five difficulty levels, by their own slug, in their own order.
#: The app's vocabulary becomes these five (the maintainer, 2026-09-09: "keep
#: their 5 and make 5 the standard"); the slugs are carried as published so a
#: badge quotes the publisher rather than a mapping of them.
DIFFICULTY_LEVELS = ("easy", "easy-moderate", "moderate", "moderate-strenuous", "strenuous")

#: Where NYNJTC's hikes are: New York City to the Catskills, the Delaware
#: Water Gap to the Connecticut line, with a margin. A coordinate outside it
#: is not a trailhead - it is the viewport's scale, or a typo - and is
#: refused rather than placed. Loose on purpose (lib/nynjtc_long_path_guide
#: .py's reasoning): the point is to catch the impossible, not the unlikely.
LAT_RANGE = (39.5, 43.6)
LON_RANGE = (-76.5, -72.0)

#: How the start was read. `marker` is a placed pin, `map_centre` is the
#: centre of a place-card embed; the difference is confidence, and a
#: reviewer building a route should know which they are looking at.
START_MARKER = "marker"
START_MAP_CENTRE = "map_centre"

_TAG = re.compile(r"<[^>]+>")
#: Tags that sit INSIDE a run of words. Replaced with nothing rather than a
#: space, so "<strong>rocky ascents</strong>," reads "rocky ascents," and not
#: "rocky ascents ," - every overview on the site bolds its nouns.
_INLINE_TAG = re.compile(r"</?(?:strong|em|b|i|a|span|u|sup|sub)\b[^>]*>", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s+")
_DROPPED = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.DOTALL | re.IGNORECASE)
_FIGURE = re.compile(r"<figure[^>]*>.*?</figure>", re.DOTALL | re.IGNORECASE)
_PARAGRAPH = re.compile(r"<(p|li)\b[^>]*>(.*?)</\1>", re.DOTALL | re.IGNORECASE)
_HOW_TO_GET_THERE = re.compile(r"<h2[^>]*>\s*How to Get There\s*</h2>", re.IGNORECASE)
_SHOP_BLOCK = re.compile(r"Don(?:&#8217;|')t Leave Unprepared", re.IGNORECASE)
_DETAILS = re.compile(r"<details[^>]*>\s*<summary[^>]*>(.*?)</summary>(.*?)</details>", re.DOTALL | re.IGNORECASE)
_DESCRIPTION_SUMMARY = re.compile(r"Detailed Hike Description", re.IGNORECASE)
_EMBED = re.compile(r"maps/embed\?pb=([^\"'\s]+)")
_LAT_LON_PAIR = re.compile(r"!1d(-?\d+(?:\.\d+)?)!2d(-?\d+(?:\.\d+)?)")
_VIEWPORT = re.compile(r"!2d(-?\d+(?:\.\d+)?)!3d(-?\d+(?:\.\d+)?)")
_PUBLICATION = re.compile(
    r"Publication:\s*Submitted by\s+(.+?)\s+on\s+(\d{1,2}/\d{1,2}/\d{4})"
    r"(?:,?\s*updated/verified on\s+(\d{1,2}/\d{1,2}/\d{4}))?",
    re.IGNORECASE,
)
#: "Photo by Daniel Chazin", "Photo: Jane Daniels", "Photo credit: Daniela
#: Wagstaff" - the three spellings the twenty pages use between them
#: (measured 2026-09-09), in the alt text, the caption, or the paragraph
#: under the figure. One name, cut at the first punctuation.
_PHOTO_BY = re.compile(r"Photo(?:graph)?(?:\s+credit)?\s*(?:\bby\b|:)\s*([^.,;()\-–—]+)", re.IGNORECASE)
_CONTENT_IMAGE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_ATTR = re.compile(r'\b(src|alt|width|height)="([^"]*)"')
_TITLE_PREFIX = re.compile(r"^\s*Hike:\s*", re.IGNORECASE)
#: "a 3.8-mile loop", "this 6.7-mile hike": the adjectival form NYNJTC's
#: overviews use for the hike's own length. "3.4 miles from the trailhead"
#: (a distance along the way) is deliberately not this pattern.
_STATED_MILES = re.compile(r"(\d+(?:\.\d+)?)-mile\b")


def strip_html(markup: str) -> str:
    """Tags out, entities in, whitespace flattened."""
    return _WHITESPACE.sub(" ", html_module.unescape(_TAG.sub(" ", _INLINE_TAG.sub("", markup)))).strip()


def paragraphs(markup: str) -> list[str]:
    """The prose in a block of markup: every `<p>` and `<li>`, as plain text,
    empties dropped.

    ELEMENTS, NOT SPLITS. NYNJTC's tag table is `<div><span>Region: </span>
    <a rel="tag">...</a></div>` - no paragraph element at all - so reading
    only `<p>`/`<li>` bodies leaves it out without a rule naming it. A split
    on `</p>` would have carried "Region: Catskill Park: Catskill Park ..." in
    as the first paragraph of every overview (measured while writing this).
    """
    found = []
    for _, body in _PARAGRAPH.findall(markup):
        text = strip_html(body)
        if text:
            found.append(text)
    return found


def _text_of(rendered) -> str:
    if isinstance(rendered, dict):
        rendered = rendered.get("rendered")
    return strip_html(str(rendered or ""))


@dataclass
class Term:
    slug: str
    name: str

    def to_dict(self) -> dict:
        return {"slug": self.slug, "name": self.name}


@dataclass
class Publication:
    """NYNJTC's own provenance line: who wrote the description and when it
    was last walked. `verified_on` is the date that says whether the
    turn-by-turn is current, and it is absent on a page never re-verified
    (`hike-west-kill-mountain...`, submitted 2017 and not since)."""

    submitted_by: str
    submitted_on: str
    verified_on: str | None
    raw: str

    def to_dict(self) -> dict:
        return {
            "submitted_by": self.submitted_by,
            "submitted_on": self.submitted_on,
            "verified_on": self.verified_on,
            "raw": self.raw,
        }


@dataclass
class Photo:
    """The page's photograph, as NYNJTC serves it, with its credit.

    `basis` says where it was read from: the post's featured media (19 of
    20), or the first credited figure in the body when the post has no
    featured media (`hike-bear-mountain-summit-loop`). `credit` is the
    photographer's name from the alt text or caption, or None when neither
    names one - and a photo with no credit is one the exporter must not
    ship, because the credit line is the licence's condition.
    """

    source_url: str
    width: int | None
    height: int | None
    alt: str
    caption: str
    credit: str | None
    basis: str

    def to_dict(self) -> dict:
        return {
            "source_url": self.source_url,
            "width": self.width,
            "height": self.height,
            "alt": self.alt,
            "caption": self.caption,
            "credit": self.credit,
            "basis": self.basis,
        }


@dataclass
class ParsedHike:
    """One hike, as facts. Says nothing about whether it may ship or where
    its route goes."""

    id: int
    slug: str
    name: str
    title: str
    published_at: str
    modified_at: str
    source_url: str
    terms: dict[str, list[Term]] = field(default_factory=dict)
    overview: list[str] = field(default_factory=list)
    description: list[str] = field(default_factory=list)
    publication: Publication | None = None
    start: tuple[float, float] | None = None
    start_basis: str | None = None
    photo: Photo | None = None
    stated_miles: float | None = None
    stated_miles_mentioned: list[float] = field(default_factory=list)

    @property
    def difficulty(self) -> str | None:
        """NYNJTC's level, by their slug, or None when the page carries none."""
        levels = [term.slug for term in self.terms.get("difficulty", []) if term.slug in DIFFICULTY_LEVELS]
        return levels[0] if levels else None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "title": self.title,
            "published_at": self.published_at,
            "modified_at": self.modified_at,
            "source_url": self.source_url,
            "difficulty": self.difficulty,
            "terms": {taxonomy: [term.to_dict() for term in terms] for taxonomy, terms in self.terms.items()},
            "overview": list(self.overview),
            "description": list(self.description),
            "publication": self.publication.to_dict() if self.publication else None,
            "start": {"lat": self.start[0], "lon": self.start[1], "basis": self.start_basis} if self.start else None,
            "photo": self.photo.to_dict() if self.photo else None,
            "stated_miles": self.stated_miles,
            "stated_miles_mentioned": list(self.stated_miles_mentioned),
        }


def is_public(post: dict) -> bool:
    """Whether the post's body is readable without NYNJTC's password.

    `content.protected: true` is WordPress saying the body is withheld; the
    rendered content on such a post is an empty string, and a record built
    from it would be a hike with no prose and no start, looking exactly like
    a parse failure. Deciding here keeps the two apart.
    """
    content = post.get("content")
    return isinstance(content, dict) and not content.get("protected")


def _iso_date(mm_dd_yyyy: str) -> str:
    """`08/24/2016` as `2016-08-24`. Left as written when it does not parse,
    so the record still says what the page said."""
    try:
        return datetime.strptime(mm_dd_yyyy, "%m/%d/%Y").date().isoformat()
    except ValueError:
        return mm_dd_yyyy


def parse_publication(text: str) -> Publication | None:
    match = _PUBLICATION.search(text)
    if match is None:
        return None
    author, submitted, verified = match.groups()
    return Publication(
        submitted_by=author.strip(),
        submitted_on=_iso_date(submitted),
        verified_on=_iso_date(verified) if verified else None,
        raw=match.group(0).strip(),
    )


def _in_range(lat: float, lon: float) -> bool:
    return LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]


def parse_start(markup: str) -> tuple[tuple[float, float], str] | None:
    """The trailhead from the page's map embed: `((lat, lon), basis)`, or
    None when the page has no embed or the embed places nothing readable.

    The LAST in-range `!1d<lat>!2d<lon>` pair is the marker: the embed's
    viewport pair comes first and its `!1d` is a scale, not a latitude, so
    the range check alone tells them apart; taking the last one is for an
    embed that carries a route with several placed points, where the last is
    the one Google centres on. Falls back to the viewport centre for a
    place-card embed, at the lower `map_centre` confidence.
    """
    embed = _EMBED.search(markup)
    if embed is None:
        return None
    parameter = html_module.unescape(embed.group(1))
    placed = [(float(lat), float(lon)) for lat, lon in _LAT_LON_PAIR.findall(parameter) if _in_range(float(lat), float(lon))]
    if placed:
        return placed[-1], START_MARKER
    viewport = _VIEWPORT.search(parameter)
    if viewport is not None:
        lon, lat = float(viewport.group(1)), float(viewport.group(2))
        if _in_range(lat, lon):
            return (lat, lon), START_MAP_CENTRE
    return None


def photo_credit(*texts: str) -> str | None:
    """The photographer named in an alt text or caption, or None."""
    for text in texts:
        match = _PHOTO_BY.search(text or "")
        if match:
            name = match.group(1).strip().rstrip(".")
            if name:
                return name
    return None


def _featured_photo(post: dict) -> Photo | None:
    media = (post.get("_embedded") or {}).get("wp:featuredmedia")
    if not isinstance(media, list) or not media or not isinstance(media[0], dict):
        return None
    record = media[0]
    source_url = record.get("source_url")
    if not isinstance(source_url, str) or not source_url.startswith("http"):
        return None
    details = record.get("media_details") or {}
    width, height = details.get("width"), details.get("height")
    alt = strip_html(str(record.get("alt_text") or ""))
    caption = _text_of(record.get("caption"))
    return Photo(
        source_url=source_url,
        width=width if isinstance(width, int) else None,
        height=height if isinstance(height, int) else None,
        alt=alt,
        caption=caption,
        credit=photo_credit(alt, caption),
        basis="featured_media",
    )


def _figure_photo(markup: str) -> Photo | None:
    """The first credited image in the body - the fallback for a post whose
    featured media is unset. Credited, because an uncredited figure on these
    pages is the Avenza logo or a shop icon, never the hike."""
    for figure in _FIGURE.findall(markup):
        image = _CONTENT_IMAGE.search(figure)
        if image is None:
            continue
        attrs = dict(_ATTR.findall(image.group(0)))
        alt = html_module.unescape(attrs.get("alt", ""))
        caption = strip_html(figure)
        credit = photo_credit(alt, caption)
        src = attrs.get("src", "")
        if credit and src.startswith("http"):
            return Photo(
                source_url=src,
                width=int(attrs["width"]) if attrs.get("width", "").isdigit() else None,
                height=int(attrs["height"]) if attrs.get("height", "").isdigit() else None,
                alt=alt,
                caption=caption,
                credit=credit,
                basis="content_figure",
            )
    return None


def rendition_url(post: dict, max_width: int = 1024) -> str | None:
    """The widest featured-media rendition no wider than `max_width`, or the
    original when WordPress lists none - what the fetcher downloads.

    1024 because that is the width the app's detail screen draws the photo at
    on the widest phone it lays out for, and the originals run to 4,000 px
    and 3 MB: a rendition is the same photograph at the size a phone will
    show, and the original is bytes every download would carry for nothing.
    """
    media = (post.get("_embedded") or {}).get("wp:featuredmedia")
    if not isinstance(media, list) or not media or not isinstance(media[0], dict):
        return None
    record = media[0]
    sizes = (record.get("media_details") or {}).get("sizes") or {}
    candidates = [
        (entry.get("width"), entry.get("source_url"))
        for entry in sizes.values()
        if isinstance(entry, dict) and isinstance(entry.get("width"), int) and isinstance(entry.get("source_url"), str)
    ]
    fitting = [(width, url) for width, url in candidates if width <= max_width]
    if fitting:
        return max(fitting)[1]
    source = record.get("source_url")
    return source if isinstance(source, str) else None


def _terms(post: dict) -> dict[str, list[Term]]:
    groups = (post.get("_embedded") or {}).get("wp:term") or []
    terms: dict[str, list[Term]] = {}
    for group in groups:
        if not isinstance(group, list):
            continue
        for entry in group:
            if not isinstance(entry, dict):
                continue
            taxonomy, slug, name = entry.get("taxonomy"), entry.get("slug"), entry.get("name")
            if taxonomy not in TAXONOMIES or not isinstance(slug, str) or not isinstance(name, str):
                continue
            terms.setdefault(taxonomy, []).append(Term(slug=slug, name=html_module.unescape(name)))
    return terms


def _overview(body: str, photo: Photo | None) -> tuple[list[str], list[str]]:
    """The paragraphs above "How to Get There" (or above the shop block on a
    page without a map), split into the prose and the caption lines.

    The figure and every caption line are left out of the prose: the credit
    is the photo record's, and a page prints it beside the picture rather
    than as the opening sentence. A caption line is one naming a
    photographer, or one that IS the photo's alt text or caption repeated
    as a paragraph - `catskill-fire-towers` opens "The five Fire Towers of
    the Catskill Park" under a picture whose alt says the same.
    """
    cut = _HOW_TO_GET_THERE.search(body) or _SHOP_BLOCK.search(body)
    head = body[: cut.start()] if cut else body
    head = _FIGURE.sub(" ", head)
    repeats = {photo.alt.strip().lower(), photo.caption.strip().lower()} - {""} if photo else set()
    prose, captions = [], []
    for text in paragraphs(head):
        if _PHOTO_BY.search(text) or text.strip().lower() in repeats:
            captions.append(text)
        else:
            prose.append(text)
    return prose, captions


def _description(body: str) -> tuple[list[str], Publication | None]:
    for summary, inner in _DETAILS.findall(body):
        if not _DESCRIPTION_SUMMARY.search(strip_html(summary)):
            continue
        texts = paragraphs(inner)
        publication = None
        prose = []
        for text in texts:
            parsed = parse_publication(text) if publication is None else None
            if parsed is not None:
                publication = parsed
                continue
            prose.append(text)
        return prose, publication
    return [], None


def parse_hike(post: dict) -> ParsedHike | None:
    """One post as facts, or None if the payload was not understood.

    THE REQUIRED FIVE are id, slug, title, `modified_gmt` and link - the
    identity, the change signal and where a hiker is sent to read NYNJTC's
    own page. Everything else may be legitimately absent on a real hike:
    `catskill-fire-towers` has no map, no description and no publication
    line, and refusing it would be this module inventing a completeness the
    site does not promise. `hike_problems` says what is missing; the route
    review decides what to do about it.

    `modified_gmt` rather than `modified`: WordPress's `modified` is
    site-local with no offset, and lib/nynjtc_alerts.py records the bounded
    error of stamping it as UTC. The GMT field is in the payload and is
    exact, so this reads it from the start.
    """
    if not isinstance(post, dict) or not is_public(post):
        return None
    identifier = post.get("id")
    slug = post.get("slug")
    modified = post.get("modified_gmt") or post.get("modified")
    link = post.get("link")
    if not isinstance(identifier, int):
        return None
    if not (isinstance(slug, str) and slug.strip()):
        return None
    if not (isinstance(modified, str) and modified.strip()):
        return None
    if not (isinstance(link, str) and link.startswith("http")):
        return None
    title = _text_of(post.get("title"))
    if not title:
        return None

    body = _DROPPED.sub(" ", str((post.get("content") or {}).get("rendered") or ""))
    description, publication = _description(body)
    photo = _featured_photo(post) or _figure_photo(body)
    overview, captions = _overview(body, photo)
    if photo is not None and photo.credit is None:
        # The credit is on the page even when the media record does not
        # carry it: the paragraph under the figure ("... - Photo: Daniel
        # Chazin") on six of the twenty, measured 2026-09-09.
        photo.credit = photo_credit(*captions)
        if not photo.caption and captions:
            photo.caption = captions[0]
    located = parse_start(body)
    mentioned = [float(m) for m in _STATED_MILES.findall(" ".join(overview))]
    published = post.get("date_gmt") or post.get("date")

    return ParsedHike(
        id=identifier,
        slug=slug.strip(),
        name=_TITLE_PREFIX.sub("", title).strip(),
        title=title,
        published_at=published.strip() if isinstance(published, str) else "",
        modified_at=modified.strip(),
        source_url=link,
        terms=_terms(post),
        overview=overview,
        description=description,
        publication=publication,
        start=located[0] if located else None,
        start_basis=located[1] if located else None,
        photo=photo,
        stated_miles=mentioned[0] if mentioned else None,
        stated_miles_mentioned=mentioned,
    )


def hike_problems(hike: ParsedHike) -> list[str]:
    """What stops this hike reaching a phone as it stands, in the order a
    reviewer should read them.

    A REVIEW AID RATHER THAN A GATE. Nothing refuses to cache a hike for
    having problems - the cache is what a person reads - and the exporter
    has its own gate (a reviewed row in reference/nynjtc_hike_routes.json).
    An empty list means "everything a route needs was on the page", NOT
    "this hike is publishable": that additionally needs the route built and
    a person to have signed it off.
    """
    problems = []
    if hike.start is None:
        problems.append("no map embed with a readable trailhead - the route has nowhere to start from")
    elif hike.start_basis == START_MAP_CENTRE:
        problems.append(
            "start is a place-card map's centre rather than a placed marker - check it against the parking the description names"
        )
    if not hike.description:
        problems.append("no Detailed Hike Description block - nothing to build a route from")
    if hike.publication is None:
        problems.append("no Publication line - nobody's name and no verified-on date to carry")
    if hike.photo is None:
        problems.append("no photo")
    elif hike.photo.credit is None:
        problems.append("photo carries no 'Photo by' credit, and the licence's condition is the credit line")
    if hike.difficulty is None:
        problems.append("no difficulty term from NYNJTC's five")
    if hike.stated_miles is None:
        problems.append("overview states no '<N>-mile' length to check the built route against")
    return problems


def as_cache_entry(hike: ParsedHike, fetched_at: str) -> dict:
    """One parsed hike, flattened for the cache, with the fetch clock kept
    apart from NYNJTC's own `modified_gmt` - the one that says whether the
    page changed."""
    return {**hike.to_dict(), "fetched_at": fetched_at, "problems": hike_problems(hike)}


def today() -> str:
    return date.today().isoformat()
