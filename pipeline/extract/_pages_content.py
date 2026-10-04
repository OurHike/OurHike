"""Decision 54 wave 5's page readers for the content types (section K): the suggested hikes, challenges, podcasts and
photos a club publishes as web pages, one parser per site.

pipeline/ELT.md, "Loading everything the clubs publish (decision 54)", wave 5, is the plan: "a parser per site". A
page is written for people, so no generic reader can tell one hike on it from the next; each site's parser below
knows where that site puts its items and what facts it states, and refuses rather than guesses when the page has
changed shape. The parsers are small on purpose: a shared DOM (`parse_html`), the facts' patterns (`miles`, `feet`),
and one function a site.

    content_pages(key)        a site's page, or its index and the item pages it links, one row per item its
                              site parser (SITE_PARSERS) reads

WHAT A ROW CARRIES: FACTS AND THE LINK (decision 55, the maintainer's poll of 2026-10-03, and the round brief's
item 3). A row is one item: its name, the place the page puts it in, its numbers with their units, a date where the
page states one, and the link a hiker follows. No description, no turn-by-turn text, no paragraph lands in any
column: each type's columns are an allowlist (TYPE_COLUMNS, plus the few each site's parser declares), a parser
that returns another column raises, and a text value longer than MAX_FACT_CHARS raises too, so a parser that
caught a paragraph in a name fails its test rather than publishing the club's wording. Every number keeps the text
it was read from beside it (`distance_text` beside `distance_mi`), so a value this module read wrongly can be
checked against what the page said, and a figure the page states ambiguously ('1.300 feet') lands as its text with
no number: absent means unknown, never a guess (CLAUDE.md). A coordinate lands only where the page's own data states
one (decision 54's rule: "never geocoded from a name").

PEOPLE NEVER LAND (decision 59). A challenge's finisher roster is never read at all, an episode's guests and a
photo's uploader are person fields, and a page that names a person beside an item (a hike's leader, a route's
author) has that left out by its parser, which reads named facts and nothing else.

POLITE, AND ONE READ A RUN. Each reader is decision 53's notice source (extract/_notices.py's _NoticeSource): every
request sends lib/user_agent.py's agent through the polite() gate, held at least the host's robots.txt
Crawl-delay, or DEFAULT_HOST_GAP_SECONDS where it asks none, after the last request to that host ended; a 401, 403,
429 or 451, a challenge header or page, and a redirect to another host raise NoticeUnreadable and are never solved
or retried; and the change check's read is kept for the read that follows, so a site costs one read a run. A site
whose items sit on pages of their own is read through its index: the parser follows only links on the registry
row's own host, and never a URL with a query string unless its entry in SITE_PARSERS says the host's robots.txt
allows one (`queries`).

THE CHANGE CHECK is the read: the rows are parsed and hashed, and FRESH only when they hash as the last load's
(_NoticeSource's default, `trust_validators` False). Decision 53's inventory found most HTML validators lie (the
request time as Last-Modified, a render-time ETag; extract/_notices.py's PageNotice docstring lists them), and the
dlt skill's rule 4 forbids a site-wide validator deciding FRESH, so no page validator decides it here. The lane is
the type's, monthly (extract/_contract.py's CADENCE_BY_TYPE); nothing here rides the hourly lane.

THE COUNT is the number of items the page lists, read from the same answer the rows are built from (`exact_proof`).
A page that lists none has changed shape and raises: none of these types may be empty (extract/_contract.py's
MAY_BE_EMPTY), and an empty list from a redesigned page looks the same as an empty list from a club with no hikes.

THE LIVE READS behind each parser were section K's of 2026-10-04 (the round brief for decision 54's waves 4 and 5),
one request per URL under lib/user_agent.py's agent, robots.txt first; each sources.json row's `notes` records what
its read found, and each parser's docstring the markup it reads.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

from extract._notices import (
    RETRYABLE_STATUSES,
    WALL_STATUSES,
    WALL_TITLES,
    NoticeUnreadable,
    _decoded,
    _NoticeSource,
    same_site,
    wall,
)
from lib.http_retry import request_with_retry

# --- A page as a tree -------------------------------------------------------------------------------------------

VOID_ELEMENTS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
)
# Elements whose text is never a fact on the page: code, styles and markup a browser does not show.
HIDDEN_ELEMENTS = frozenset({"script", "style", "noscript", "template", "svg", "iframe", "head"})
INLINE_ELEMENTS = frozenset(
    {"a", "abbr", "b", "bdi", "bdo", "cite", "code", "data", "em", "font", "i", "kbd", "label", "mark", "q", "s",
     "samp", "small", "span", "strong", "sub", "sup", "time", "u", "var"}
)  # fmt: skip
# An element a page leaves open, closed by the next one of these: a browser's own recovery for the common cases.
CLOSED_BY = {
    "li": {"li"},
    "p": {"p", "div", "ul", "ol", "table", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"},
    "tr": {"tr"},
    "td": {"td", "th", "tr"},
    "th": {"td", "th", "tr"},
    "dt": {"dt", "dd"},
    "dd": {"dt", "dd"},
    "option": {"option"},
}


class Node:
    """One element: its tag, its attributes and its children, which are Nodes and strings of text."""

    __slots__ = ("attrs", "children", "parent", "tag")

    def __init__(self, tag: str, attrs: dict[str, str], parent: Node | None):
        self.tag, self.attrs, self.parent, self.children = tag, attrs, parent, []

    def get(self, name: str, default: str | None = None) -> str | None:
        return self.attrs.get(name, default)

    @property
    def classes(self) -> list[str]:
        return (self.attrs.get("class") or "").split()

    def iter(self):
        """Every element below this one, in document order."""
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.iter()

    def find_all(self, tag: str | None = None, cls: str | None = None, id: str | None = None, **attrs: str) -> list[Node]:
        """Every element below this one with that tag, class, id and attribute values; `cls` is one of its classes."""
        found = []
        for node in self.iter():
            if tag is not None and node.tag != tag:
                continue
            if cls is not None and cls not in node.classes:
                continue
            if id is not None and node.attrs.get("id") != id:
                continue
            if any(node.attrs.get(name.rstrip("_").replace("_", "-")) != value for name, value in attrs.items()):
                continue
            found.append(node)
        return found

    def find(self, tag: str | None = None, cls: str | None = None, id: str | None = None, **attrs: str) -> Node | None:
        found = self.find_all(tag, cls, id, **attrs)
        return found[0] if found else None

    def text(self) -> str:
        """The element's visible text, whitespace folded, a block boundary read as a space."""
        parts: list[str] = []
        self._text(parts)
        return " ".join("".join(parts).split())

    def _text(self, parts: list[str]) -> None:
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            elif child.tag not in HIDDEN_ELEMENTS:
                if child.tag not in INLINE_ELEMENTS:
                    parts.append(" ")
                child._text(parts)
                if child.tag not in INLINE_ELEMENTS:
                    parts.append(" ")

    def raw(self) -> str:
        """The text of a script or style element, as written."""
        return "".join(child for child in self.children if isinstance(child, str))

    def following(self):
        """Every element after this one in document order, outside it."""
        node = self
        while node.parent is not None:
            siblings = node.parent.children
            for sibling in siblings[siblings.index(node) + 1 :]:
                if isinstance(sibling, Node):
                    yield sibling
                    yield from sibling.iter()
            node = node.parent


class _TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("document", {}, None)
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        closes = CLOSED_BY.get(self.stack[-1].tag)
        while len(self.stack) > 1 and closes and tag in closes:
            self.stack.pop()
            closes = CLOSED_BY.get(self.stack[-1].tag)
        node = Node(tag, {name: value or "" for name, value in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID_ELEMENTS:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Node(tag, {name: value or "" for name, value in attrs}, self.stack[-1])
        self.stack[-1].children.append(node)

    def handle_endtag(self, tag):
        for depth in range(len(self.stack) - 1, 0, -1):
            if self.stack[depth].tag == tag:
                del self.stack[depth:]
                return  # an end tag nothing opened, which pages carry, is ignored

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def parse_html(text: str) -> Node:
    """A page as a tree of Nodes. HTMLParser closes nothing itself, so CLOSED_BY recovers the common unclosed tags."""
    builder = _TreeBuilder()
    builder.feed(text)
    builder.close()
    return builder.root


@dataclass(frozen=True)
class Page:
    """One page as a parser reads it: the URL it was read from, its tree, and its text as served (a JSON answer's)."""

    url: str
    root: Node
    text: str = ""

    def link(self, href: str | None) -> str | None:
        """`href` made absolute against this page, or None for none, an in-page anchor or a mailto/tel link."""
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            return None
        return urljoin(self.url, href.strip())


# The elements a page's text sits in: each block below is the innermost of these, so a paragraph inside a div is read
# once, as the paragraph.
BLOCK_ELEMENTS = frozenset(
    {"h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "dt", "dd", "td", "th", "div", "blockquote", "figcaption", "pre",
     "address", "section", "article", "header", "footer", "aside", "main", "nav", "ul", "ol", "table", "tr", "dl"}
)  # fmt: skip
HEADINGS = ("h1", "h2", "h3", "h4", "h5", "h6")


@dataclass(frozen=True)
class Block:
    """One innermost block of a page: its element and its visible text."""

    node: Node
    text: str

    @property
    def level(self) -> int | None:
        """A heading's level, 1 to 6, or None for a block that is not one."""
        return int(self.node.tag[1]) if self.node.tag in HEADINGS else None


def blocks(root: Node) -> list[Block]:
    """The page's innermost blocks in document order, empty ones left out, a heading always its own block."""
    found: list[Block] = []

    def walk(node: Node) -> None:
        for child in node.children:
            if not isinstance(child, Node) or child.tag in HIDDEN_ELEMENTS:
                continue
            if child.tag in HEADINGS or (child.tag in BLOCK_ELEMENTS and not any(d.tag in BLOCK_ELEMENTS for d in child.iter())):
                if text := child.text():
                    found.append(Block(child, text))
                continue
            walk(child)

    walk(root)
    return found


def sections(found: list[Block], level: int) -> list[tuple[Block, list[Block]]]:
    """Each heading of `level` and the blocks after it, up to the next heading of that level or a higher one."""
    out: list[tuple[Block, list[Block]]] = []
    current: tuple[Block, list[Block]] | None = None
    for block in found:
        if block.level is not None and block.level <= level:
            current = (block, []) if block.level == level else None
            if current is not None:
                out.append(current)
            continue
        if current is not None:
            current[1].append(block)
    return out


LABEL = re.compile(r"(?P<label>[A-Z][\w &/()'’.-]{0,40}?)\s*[:–—]\s*(?P<value>.+)", re.DOTALL)


def labelled(found: list[Block]) -> dict[str, str]:
    """'Label: value' blocks as {label, lower-cased: value}, the first of each label kept: a page's own fact lines."""
    facts: dict[str, str] = {}
    for block in found:
        match = LABEL.fullmatch(block.text)
        if match:
            facts.setdefault(match["label"].strip().lower(), match["value"].strip())
    return facts


# --- The facts a row may carry ------------------------------------------------------------------------------------

#: Each type's columns, the only ones a row may carry beside its parser's own `columns`, with the dlt type each is
#: hinted as, so a column a site leaves empty on every row is still created. `source_url` is the page the row's facts
#: were read from; `link` the page a hiker follows, which is the same page for a list with no page per item.
TYPE_COLUMNS = {
    "suggested_hikes": {
        "name": "text",
        "link": "text",
        "place": "text",
        "section": "text",
        "distance_mi": "double",
        "distance_text": "text",
        "elevation_gain_ft": "double",
        "elevation_gain_text": "text",
        "route_type": "text",
        "difficulty": "text",
        "latitude": "double",
        "longitude": "double",
        "source_url": "text",
    },
    "challenges": {
        "challenge": "text",
        "name": "text",
        "link": "text",
        "place": "text",
        "section": "text",
        "item_type": "text",
        "distance_mi": "double",
        "distance_text": "text",
        "elevation_ft": "double",
        "elevation_text": "text",
        "latitude": "double",
        "longitude": "double",
        "source_url": "text",
    },
    "podcasts": {
        "title": "text",
        "published": "text",
        "link": "text",
        "audio_url": "text",
        "duration": "text",
        "source_url": "text",
    },
    "photos": {
        "title": "text",
        "image_url": "text",
        "credit": "text",
        "licence": "text",
        "link": "text",
        "source_url": "text",
    },
}
#: Columns whose value is a URL, which may be longer than a fact.
URL_COLUMNS = frozenset({"link", "source_url", "audio_url", "image_url"})
# @unvalidated: the longest text a fact may be. A name, a place or a difficulty on the pages read on 2026-10-04 ran to
# 96 characters at most (CDTC's 'Rollins Pass and Rogers Pass to James Peak, Arapaho Roosevelt National Forest' is
# 77); 160 leaves room and still refuses a paragraph, which ran to 300 and more. It is a guard against a parser that
# caught prose, not a measurement of names; what would settle it is the longest name a year of monthly reads lands.
MAX_FACT_CHARS = 160

_NUMBER = r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?|\.\d+)"
# '4.6 miles', '4.6 mi', '4.6-mile', '4.6 mile loop', '½', '4½-mile' are distances; '1,540 feet', '1,540 ft' heights.
MILES = re.compile(_NUMBER + r"\s*(?:-\s*)?(?:miles?|mi\b)", re.IGNORECASE)
FEET = re.compile(_NUMBER + r"\s*(?:-\s*)?(?:feet|foot|ft\b|')", re.IGNORECASE)
_FRACTIONS = {"½": 0.5, "¼": 0.25, "¾": 0.75, "⅓": 1 / 3, "⅔": 2 / 3}


def number(text: str | None) -> float | None:
    """A number as a page writes it ('1,540', '4.6', '.5'), or None where it is not one plainly ('1.300', 'varies')."""
    if text is None:
        return None
    text = text.strip()
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+", text):
        return float(text.replace(",", ""))
    if re.fullmatch(r"[1-9]\d{0,2}\.\d{3}", text):
        return None  # '1.300': a thousands point or a decimal, which the page does not say
    if re.fullmatch(r"\d+(?:\.\d+)?|\.\d+", text):
        return float(text)
    return None


def miles(text: str | None) -> tuple[float | None, str | None]:
    """The first distance in `text`, as (miles, the words it was read from); a fraction sign counts ('4½-mile')."""
    if not text:
        return None, None
    found = re.search(r"(\d+)?\s*([½¼¾⅓⅔])\s*(?:-\s*)?(?:miles?|mi\b)", text, re.IGNORECASE)
    plain = MILES.search(text)
    if found and (plain is None or found.start() <= plain.start()):
        whole = float(found.group(1) or 0)
        return round(whole + _FRACTIONS[found.group(2)], 3), found.group(0).strip()
    if plain:
        return number(plain.group(1)), plain.group(0).strip()
    return None, None


def feet(text: str | None) -> tuple[float | None, str | None]:
    """The first height in `text`, as (feet, the words it was read from)."""
    if not text:
        return None, None
    found = FEET.search(text)
    return (number(found.group(1)), found.group(0).strip()) if found else (None, None)


def fact(value: str | None) -> str | None:
    """A text fact, whitespace folded, or None for none."""
    value = " ".join((value or "").split())
    return value or None


# --- The reader -----------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SiteParser:
    """How one site's pages are read: the function, the columns it adds to its type's, and what it may follow.

    `read(page, fetch)` returns the rows; `fetch(url)` reads another page on the same host through the reader's
    gate and returns it as a Page. `queries` is True only where the host's robots.txt, read at registration,
    allows a URL with a query string, which no parser asks for otherwise.
    """

    read: Callable[[Page, Callable[[str], Page]], list[dict]]
    columns: dict[str, str] = field(default_factory=dict)
    queries: bool = False


class LayoutChanged(NoticeUnreadable):
    """A page that no longer has the shape its site's parser was written for: the run refuses, the last rows stand."""


@dataclass(frozen=True)
class ContentPages(_NoticeSource):
    """A site's content pages, one row per item its parser in SITE_PARSERS reads: facts and the link (module docstring).

    The registry row's `url` is the page the parser starts from: the list itself, or the index whose links lead to
    one page an item. `site` names the parser, the registry key unless one site's parser reads two rows' pages.
    """

    site: str = ""

    @property
    def parser(self) -> SiteParser:
        return SITE_PARSERS[self.site or self.key]

    @property
    def columns(self) -> dict[str, str]:
        if self.type not in TYPE_COLUMNS:
            raise ValueError(f"{self.key}: a content page reader feeds {sorted(TYPE_COLUMNS)}, not {self.type}")
        return {**TYPE_COLUMNS[self.type], **self.parser.columns}

    def column_hints(self) -> dict:
        return {name: {"data_type": kind} for name, kind in self.columns.items()}

    def _fetch(self, url: str) -> Page:
        """Another page of the same site, through the same gate and the same refusals as the first."""
        if not same_site(self.url, url):
            raise LayoutChanged(f"{self.key}: the page links {url}, off {urlparse(self.url).hostname}, which is not read")
        if urlparse(url).query and not self.parser.queries:
            raise LayoutChanged(f"{self.key}: {url} carries a query string, which this site's parser does not ask")
        return self._page(url, guarded_get(self, url))

    def _page(self, url: str, response: requests.Response) -> Page:
        text = _decoded(response)
        root = parse_html(text)
        title = root.find("title")
        if title is not None and title.text().lower() in WALL_TITLES:
            raise NoticeUnreadable(f"{self.key}: {url} is a challenge page ({title.text()!r}); not solved, not retried")
        return Page(url, root, text)

    def _parse(self, response: requests.Response):
        rows = self.parser.read(self._page(self.fetch_url, response), self._fetch)
        if not rows:
            raise LayoutChanged(f"{self.key}: the page lists no item, which is a changed shape, not an empty list")
        return [self._checked(row) for row in rows], len(rows)

    def _checked(self, row: dict) -> dict:
        return checked_row(self.key, self.type, self.columns, row)


def guarded_get(source: _NoticeSource, url: str, headers: dict | None = None) -> requests.Response:
    """One GET of `url` through `source`'s polite gate, refusing as _NoticeSource._get refuses its own URL.

    A wall (a 401, 403, 429 or 451, or a challenge header), a redirect to another host and any status but 200 or a
    304 to a conditional request raise NoticeUnreadable; a 5xx is retried first (RETRYABLE_STATUSES).
    """
    try:
        response = request_with_retry(
            url,
            session=source._session(),
            headers=headers,
            timeout=source.timeout,
            retryable_statuses=RETRYABLE_STATUSES,
            label=source.key,
        )
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else None
        kind = ", a wall; nothing is read past it" if status in WALL_STATUSES else ""
        raise NoticeUnreadable(f"{source.key}: {url} answered HTTP {status}{kind}") from error
    if reason := wall(response):
        raise NoticeUnreadable(f"{source.key}: {url} answered with a challenge ({reason}); not solved, not retried")
    if not same_site(url, response.url):
        raise NoticeUnreadable(f"{source.key}: {url} now redirects to {response.url}, another host")
    if response.status_code == 304 and headers:
        return response
    if response.status_code != 200:
        raise NoticeUnreadable(f"{source.key}: {url} answered HTTP {response.status_code}")
    return response


def checked_row(key: str, type_: str, columns: dict[str, str], row: dict) -> dict:
    """`row` with every one of `columns` present, or a raise for a column outside them or a text too long for a fact."""
    if extra := sorted(set(row) - set(columns)):
        raise ValueError(f"{key}: the parser returned {extra}, outside {type_}'s columns (decision 55)")
    for name, value in row.items():
        if isinstance(value, str) and name not in URL_COLUMNS and len(value) > MAX_FACT_CHARS:
            raise ValueError(f"{key}: {name} is {len(value)} characters, prose rather than a fact: {value[:60]!r}")
    return {name: row.get(name) for name in columns}


def content_pages(key: str, *, site: str | None = None, crawl_delay: float = 0.0, **overrides) -> ContentPages:
    """A ContentPages for a registry key; `crawl_delay` is the host's robots.txt Crawl-delay, as its live read found."""
    resource = ContentPages(key=key, site=site or key, crawl_delay=crawl_delay, **overrides)
    if resource.site not in SITE_PARSERS:
        raise KeyError(f"{key}: extract/_pages_content.py's SITE_PARSERS has no parser {resource.site!r}")
    url = resource.url  # an unregistered key fails at import, in the layout test
    if urlparse(url).query and not resource.parser.queries:
        raise ValueError(f"{key}: the registry url carries a query string, which this site's parser does not ask")
    return resource


# --- The sites ------------------------------------------------------------------------------------------------------


def _mazamas_hikelist(page: Page, fetch) -> list[dict]:
    """The Mazamas' Hike List View (mazamas.org/hikelist/): 153 hikes in four regions, read 2026-10-04.

    Each region is a rich-text block (`article.block-richtextblock`) titled by an h3 (`h3.block--title`: 'Columbia
    River Gorge Hikes', 'Mt. Hood', 'Clackamas River', 'Oregon Coast'), whose first line says what each item holds,
    "List includes: hike name, hike distance, hike elevation, appx. driving distance, trailhead fee", above one list
    of lines such as 'Angels Rest 4.6 miles 1,540 feet 42 miles, no'. The page's 'Hike Details' block says hiking
    and driving miles are round trip "(unless otherwise noted)", so an item whose name notes '(1-way)' is one way,
    and that elevation gain is cumulative. The page names a fifth destination, Gifford Pinchot National Forest,
    which has no block of its own on 2026-10-04 (its hikes sit in the Gorge's), so no row is placed there.

    An item that is not that line raises, and so does a set of region blocks other than the four, so a reworded
    list refuses the run. 'varies' is the page's word for a distance or a gain it does not state, and lands as text
    with no number; so does a gain written ambiguously ('1.300 feet' on Augspurger Mountain-Dog Mountain: 1,300 or
    1.3 thousand, no guess). Driving miles are measured from the park-and-ride the page names for the region, or
    from Durham P&R where the coast's figure carries an asterisk ('varies' again where it states none). No item links a page of its own ('Coming soon,
    clickable hike links!'), so `link` is the list's own URL.
    """
    line = re.compile(
        r"(?P<name>.+?)\s+(?P<miles>[\d.]+|varies)\s+(?:miles?\s+)?(?P<gain>[\d.,]+|varies)\s+(?:feet\s+)?"
        r"(?:(?P<drive>[\d.]+)\s+miles(?P<star>\*)?|varies),\s*(?P<fee>yes|no)",
        re.IGNORECASE,
    )
    rows = []
    for block in page.root.find_all("article", cls="block-richtextblock"):
        title = block.find("h3", cls="block--title")
        if title is None or "List includes:" not in block.text():
            continue
        region = fact(title.text())
        if region not in MAZAMAS_DRIVING_FROM:
            raise LayoutChanged(f"mazamas: a hike list is titled {region!r}, which is not one of the regions it had")
        for item in block.find_all("li"):
            text = fact(item.text()) or ""
            match = line.fullmatch(text)
            if not match:
                raise LayoutChanged(f"mazamas: a {region} item is not 'name miles feet drive, fee': {text!r}")
            name = fact(match["name"])
            starred = bool(match["star"])
            rows.append(
                {
                    "name": name,
                    "section": region,
                    "distance_mi": number(match["miles"]),
                    "distance_text": match["miles"] if match["miles"].lower() == "varies" else f"{match['miles']} miles",
                    "elevation_gain_ft": number(match["gain"]),
                    "elevation_gain_text": match["gain"] if match["gain"].lower() == "varies" else f"{match['gain']} feet",
                    "route_type": "one way" if re.search(r"\b1-way\b", name, re.IGNORECASE) else "round trip",
                    "driving_mi": number(match["drive"]),
                    "driving_from": MAZAMAS_COAST_ASTERISK if starred else MAZAMAS_DRIVING_FROM[region],
                    "trailhead_fee": match["fee"].lower() == "yes",
                    "link": page.url,
                    "source_url": page.url,
                }
            )
    found = {row["section"] for row in rows}
    if found != set(MAZAMAS_DRIVING_FROM):
        raise LayoutChanged(f"mazamas: the list's regions are now {sorted(found)}, not {sorted(MAZAMAS_DRIVING_FROM)}")
    return rows


#: The four region blocks the Hike List View holds on 2026-10-04, as their titles spell them, and the park-and-ride
#: the page's 'Hike Details' block says each region's driving miles are measured from.
MAZAMAS_DRIVING_FROM = {
    "Columbia River Gorge Hikes": "Gateway P&R (I-84 Exit 7)",
    "Mt. Hood": "Gateway P&R (I-84 Exit 7)",
    "Clackamas River": "Gateway P&R (I-84 Exit 7)",
    "Oregon Coast": "Tanasborne (185th & Hwy. 26)",
}
MAZAMAS_COAST_ASTERISK = "Durham P&R (I-5 Exit 290)"


def route_type(text: str | None) -> str | None:
    """The route's shape where the text names one in so many words: round trip, out and back, loop or one way."""
    for pattern, name in (
        (r"round[- ]trip|\bRT\b", "round trip"),
        (r"out[- ]and[- ]back", "out and back"),
        (r"\bloop\b", "loop"),
        (r"one[- ]way|\b1-way\b|point[- ]to[- ]point|\bshuttle\b", "one way"),
    ):
        if text and re.search(pattern, text, re.IGNORECASE):
            return name
    return None


def _tahoe_rim_day_hikes(page: Page, fetch) -> list[dict]:
    """The Tahoe Rim Trail Association's Day Hike Itineraries: four theme pages linked from tahoerimtrail.org/day-hiking/.

    The index links each theme's page through a card whose h4 names it ('Alpine Lakes', 'Wildflower Hikes', 'Peaks
    & Vistas', 'Waterfall Hikes', 2026-10-04: 4 pages, 15 hikes). On a theme page each hike is an h3 ('Lake Aloha
    Hike') followed by one paragraph a fact, each opening with its label in bold: Classification, Distance
    ('12 miles round trip'), Highlights, Location (the trailhead), Bike(s) Allowed, Access from, Description and,
    for some, Permit Required. Highlights and Description are the association's wording and land nowhere; the rest
    are facts. A theme page whose h3s carry no Distance and no Classification raises, and so does an index that
    links no theme page. The page's footer h3s (Office, Mailing, Contact Us and the rest) carry neither, and are
    skipped by that same test. No hike has a page of its own, so `link` is its theme page.
    """
    themes = []
    for anchor in page.root.find_all("a"):
        heading = anchor.find("h4")
        href = page.link(anchor.get("href"))
        if heading is not None and href and urlparse(href).path.startswith("/") and href != page.url:
            themes.append((fact(heading.text()), href))
    if not themes:
        raise LayoutChanged("tahoe_rim: the day-hiking page links no itinerary card (an <a> holding an <h4>)")
    rows = []
    for theme, href in themes:
        theme_page = fetch(href)
        hikes = 0
        for heading, body in sections(blocks(theme_page.root), 3):
            facts = labelled(body)
            if "distance" not in facts and "classification" not in facts:
                continue
            hikes += 1
            distance, distance_text = miles(facts.get("distance"))
            rows.append(
                {
                    "name": fact(heading.text),
                    "section": theme,
                    "difficulty": fact(facts.get("classification")),
                    "distance_mi": distance,
                    "distance_text": distance_text,
                    "route_type": route_type(facts.get("distance")),
                    "place": fact(facts.get("location")),
                    "bikes_allowed": fact(facts.get("bikes allowed") or facts.get("bike allowed")),
                    "access_from": fact(facts.get("access from")),
                    "link": theme_page.url,
                    "source_url": theme_page.url,
                }
            )
        if not hikes:
            raise LayoutChanged(f"tahoe_rim: {href} has no h3 with a Distance or a Classification")
    return rows


#: Every site's parser, by the registry key (or the `site`) its resource names.
SITE_PARSERS: dict[str, SiteParser] = {
    "mazamas_hike_list": SiteParser(
        _mazamas_hikelist, columns={"driving_mi": "double", "driving_from": "text", "trailhead_fee": "bool"}
    ),
    "tahoe_rim_day_hikes": SiteParser(_tahoe_rim_day_hikes, columns={"bikes_allowed": "text", "access_from": "text"}),
}
