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
        return " ".join("".join(parts).replace("\u200b", "").replace("\ufeff", "").split())

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

    def lines(self) -> list[str]:
        """The element's visible text as lines: a <br> and a block boundary each end one, whitespace folded in each."""
        parts: list[str] = []
        self._lines(parts)
        joined = "".join(parts).replace("\u200b", "").replace("\ufeff", "")
        return [line for line in (" ".join(chunk.split()) for chunk in joined.split("\n")) if line]

    def _lines(self, parts: list[str]) -> None:
        for child in self.children:
            if isinstance(child, str):
                parts.append(child.replace("\n", " "))
            elif child.tag == "br":
                parts.append("\n")
            elif child.tag not in HIDDEN_ELEMENTS:
                boundary = "" if child.tag in INLINE_ELEMENTS else "\n"
                parts.append(boundary)
                child._lines(parts)
                parts.append(boundary)

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


def table_rows(table: Node) -> tuple[list[str], list[list[str]]]:
    """A table's header cells and its body rows' cells, as text: the first row whose cells are th, or the first row."""
    rows = [
        [cell.text().replace("\ufeff", "") for cell in tr.find_all() if cell.tag in ("td", "th")] for tr in table.find_all("tr")
    ]
    rows = [row for row in rows if any(row)]
    if not rows:
        return [], []
    return rows[0], rows[1:]


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
    gate and returns it as a Page, and `fetch(url, missing_ok=True)` returns None for a 404 or 410, for a page the
    parser builds from a pattern rather than follows from a link (a park with no trails page). `queries` is True only
    where the host's robots.txt, read at registration, allows a URL with a query string, which no parser asks for
    otherwise.
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

    def _fetch(self, url: str, missing_ok: bool = False) -> Page | None:
        """Another page of the same site, through the same gate and the same refusals as the first.

        With `missing_ok`, a 404 or 410 is None rather than a raise: only for a URL the parser built from a pattern,
        never one the site linked, where a missing page is a moved page and the run must say so.
        """
        if not same_site(self.url, url):
            raise LayoutChanged(f"{self.key}: the page links {url}, off {urlparse(self.url).hostname}, which is not read")
        if urlparse(url).query and not self.parser.queries:
            raise LayoutChanged(f"{self.key}: {url} carries a query string, which this site's parser does not ask")
        try:
            response = guarded_get(self, url)
            return self._page(response.url or url, response)  # a same-host redirect's target, as the link
        except NoticeUnreadable as error:
            if missing_ok and re.search(r"answered HTTP (404|410)\b", str(error)):
                return None
            raise

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
        (r"round[- ]?trip|\bRT\b", "round trip"),
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


#: NC State Parks' trail-table headers, lower-cased, as the 42 parks' tables spelled them (2026-10-04, nine header
#: sets), and the column each lands in. A 'Description', 'Descriptions' or 'Additional Information' column is the
#: park's prose and lands nowhere; a header this does not name raises.
NC_PARKS_COLUMNS = {
    "trail name": "name",
    "trail": "name",
    "blaze": "blaze",
    "length": "distance_text",
    "difficulty": "difficulty",
    "trail use": "trail_use",
    "accessible": "accessible",
    "ada accessible": "accessible",
    "access": "access",
    "access location": "access",
    "description": None,
    "descriptions": None,
    "additional information": None,
}


def _nc_parks_trails(page: Page, fetch) -> list[dict]:
    """NC State Parks' trail tables: ncparks.gov/state-parks lists each park, and each park's /trails page a table.

    The index links 46 parks (`/state-parks/<park>`, 2026-10-04); the trails page is that URL plus `/trails`, built
    from the pattern rather than linked, so a park with none (Bob's Creek State Natural Area answers 404) has no row
    and no refusal. A table's header row names its columns, which vary by park ('Trail Name | Blaze | Length |
    Difficulty | Trail Use | Accessible' at Crowders Mountain; 'ADA Accessible' and a 'Description' column at
    Carolina Beach), and each body row is one trail ('Backside Trail | orange | 0.8-mile | Strenuous | Hiking only |
    No'). Columns are read by their header through NC_PARKS_COLUMNS; a header it does not name, a table with no
    trail name or length, an index that links no park and a read where no park has a table each raise. The park is
    named from the page's <title>, because 35 of the 42 pages' h1 is 'Trails' alone.
    """
    parks = sorted(
        {
            page.link(anchor.get("href"))
            for anchor in page.root.find_all("a")
            if re.fullmatch(r"/state-parks/[a-z0-9-]+/?", urlparse(page.link(anchor.get("href")) or "").path or "")
        }
        - {None}
    )
    if not parks:
        raise LayoutChanged("nc_parks: the index links no /state-parks/<park> page")
    rows = []
    for park in parks:
        trails = fetch(park.rstrip("/") + "/trails", missing_ok=True)
        if trails is None:
            continue
        # The park's name is its <title>'s ('Crowders Mountain: Trails | NC State Parks'): the h1 is 'Trails' on most.
        title = trails.root.find("title")
        name = re.sub(r": Trails \| NC State Parks$", "", fact(title.text()) or "") if title is not None else ""
        if not name or "|" in name:
            raise LayoutChanged(f"nc_parks: {trails.url}'s <title> is not '<park>: Trails | NC State Parks'")
        for table in trails.root.find_all("table"):
            head, body = table_rows(table)
            names = [cell.strip().lower() for cell in head]
            unknown = [cell for cell in names if cell not in NC_PARKS_COLUMNS]
            if unknown or "name" not in [NC_PARKS_COLUMNS[cell] for cell in names] or "length" not in names:
                raise LayoutChanged(f"nc_parks: {trails.url}'s table heads {head}, which NC_PARKS_COLUMNS does not read")
            for cells in body:
                if len(cells) != len(head):
                    raise LayoutChanged(f"nc_parks: {trails.url} has a row of {len(cells)} cells under {len(head)}: {cells}")
                row = {
                    NC_PARKS_COLUMNS[cell]: fact(value)
                    for cell, value in zip(names, cells, strict=True)
                    if NC_PARKS_COLUMNS[cell]
                }
                if not row.get("name"):
                    continue
                distance, _ = miles(row.get("distance_text"))
                rows.append(
                    {
                        **row,
                        "place": name,
                        "section": name,
                        "distance_mi": distance,
                        "route_type": route_type(row.get("distance_text")),
                        "link": trails.url,
                        "source_url": trails.url,
                    }
                )
    if not rows:
        raise LayoutChanged("nc_parks: no park's trails page held a trail table")
    return rows


_CVATC_LEAD = re.compile(r"(?P<name>Hike [Tt]o .+?) - (?P<facts>\d[^.]*?)\.\s")


def _cvatc_foliage_hikes(page: Page, fetch) -> list[dict]:
    """The Cumberland Valley A.T. Club's 'Great Fall Foliage Hikes In South Central PA', four hikes, read 2026-10-04.

    Each hike is one paragraph that opens with its facts in one clause before the first full stop: 'Hike to Pole
    Steeple - 6 miles, moderate.', 'Hike To Flat Rock - 5 miles, out and back, strenuous in places.' The name and
    that clause are read; the rest of the paragraph is the club's directions and lands nowhere. A page with no such
    paragraph raises.
    """
    rows = []
    for line in page.root.lines():
        match = _CVATC_LEAD.match(line + " ")
        if not match:
            continue
        clauses = [fact(part) for part in match["facts"].split(",")]
        distance, distance_text = miles(clauses[0])
        shape = next((route_type(clause) for clause in clauses[1:] if route_type(clause)), None)
        difficulty = next((clause for clause in clauses[1:] if clause and not route_type(clause)), None)
        rows.append(
            {
                "name": fact(match["name"]),
                "distance_mi": distance,
                "distance_text": distance_text,
                "route_type": shape,
                "difficulty": difficulty,
                "link": page.url,
                "source_url": page.url,
            }
        )
    return rows


#: A Foothills section page's labels, and the shape a following paragraph has when it continues that label rather than
#: being the conservancy's own note: the other direction's difficulty ('A2 to A1 – moderate to strenuous', 'A11 to A10
#: easy to moderate', 'Foothills Trail to Frozen Creek – strenuous') or the other end's trailhead ('A2 Sassafras
#: Mountain, SC Hwy 178, ...').
FOOTHILLS_CONTINUES = {
    "distance": None,
    "difficulty": re.compile(r"[AS] ?\d+ to [AS] ?\d+\b.*|.+ to .+ [–-] .+"),
    "blazes": None,
    "trail head": re.compile(r"[AS] ?\d+\b.*"),
}


def _foothills_facts(found: list[Block]) -> dict[str, list[str]]:
    """A section page's labelled paragraphs, each with the paragraphs that continue it (FOOTHILLS_CONTINUES)."""
    facts: dict[str, list[str]] = {}
    current = None
    for block in found:
        match = re.fullmatch(r"(?P<label>[A-Z][A-Za-z ]{1,20}):\s*(?P<value>.*)", block.text)
        if match:
            label = match["label"].strip().lower()
            current = label if label in FOOTHILLS_CONTINUES else None
            if current is not None and match["value"]:
                facts.setdefault(current, []).append(match["value"].strip())
            continue
        continues = FOOTHILLS_CONTINUES.get(current) if current else None
        if continues is not None and continues.fullmatch(block.text):
            facts[current].append(block.text)
        else:
            current = None
    return facts


def _foothills_sections(page: Page, fetch) -> list[dict]:
    """The Foothills Trail Conservancy's 'Section By Section': the index's 19 /portfolio/ pages, each one section.

    The index (foothillstrail.org/section-by-section-2/) links each section's page from a gallery card above an h2
    with its name: 13 sections A1 to A14 and 6 spurs, 2026-10-04. A section's page states its name in its h1, then
    one paragraph a fact, the label first: 'Distance: 9.7 miles', 'Difficulty: A1 to A2 – strenuous (ascends 2,000
    feet in three miles)' with the other direction on the next paragraph, 'Blazes: Yellow', 'Trail Head:' with each
    end on a paragraph of its own, then 'Features:' as a list. Distance, difficulty (both directions, joined by
    '; '), blazes and trailheads (both ends) are read, a paragraph continuing a label only where it has that label's
    shape (FOOTHILLS_CONTINUES); the page's notes ('*At Frozen Creek Access, campers are asked to ...') and the
    features list are not. A section page with no
    Distance raises. foothillstrail.org's robots.txt disallows every URL with a query string (`Disallow: /*?`) and
    asks `Crawl-delay: 10`, so the WordPress REST list, which pages by query string, is not asked.
    """
    sections_found = []
    for anchor in page.root.find_all("a"):
        href = page.link(anchor.get("href"))
        if href and "/portfolio/" in urlparse(href).path and href not in sections_found:
            sections_found.append(href)
    if not sections_found:
        raise LayoutChanged("foothills: the section-by-section page links no /portfolio/ page")
    rows = []
    for href in sections_found:
        section = fetch(href)
        heading = section.root.find("h1")
        found = blocks(section.root)
        start = next((i for i, block in enumerate(found) if block.node is heading), None)
        if heading is None or start is None:
            raise LayoutChanged(f"foothills: {href} has no h1")
        body = []
        for block in found[start + 1 :]:
            if block.level is not None:
                break
            body.append(block)
        facts = _foothills_facts(body)
        if "distance" not in facts:
            raise LayoutChanged(f"foothills: {href} states no Distance")
        distance, distance_text = miles(facts["distance"][0])
        rows.append(
            {
                "name": fact(heading.text()),
                "distance_mi": distance,
                "distance_text": distance_text,
                "difficulty": fact("; ".join(facts.get("difficulty", []))),
                "blazes": fact("; ".join(facts.get("blazes", []))),
                "place": fact("; ".join(facts.get("trail head", []))),
                "link": section.url,
                "source_url": section.url,
            }
        )
    return rows


def _cohos_day_hikes(page: Page, fetch) -> list[dict]:
    """The Cohos Trail Association's day hikes (cohostrail.org/day-hike/): the table of more suggestions, 22 rows.

    The page lists twelve favourites as paragraphs of the association's prose, then 'Looking for even more day hikes
    on the Cohos Trail? Check out these suggestions:' and a table headed 'Trail or Destination | Where | Rank |
    Feature' ('Davis Path, Mt. Crawford | Notchland | Tough | Mt. Views'). The table is read, one row a hike; the
    favourites' prose is not. A table whose header differs raises.
    """
    header = ["Trail or Destination", "Where", "Rank", "Feature"]
    rows = []
    for table in page.root.find_all("table"):
        head, body = table_rows(table)
        if head != header:
            raise LayoutChanged(f"cohos: the day-hike table heads {head}, not {header}")
        for cells in body:
            if len(cells) != len(header):
                raise LayoutChanged(f"cohos: a day-hike row has {len(cells)} cells: {cells}")
            rows.append(
                {
                    "name": fact(cells[0]),
                    "place": fact(cells[1]),
                    "difficulty": fact(cells[2]),
                    "feature": fact(cells[3]),
                    "link": page.url,
                    "source_url": page.url,
                }
            )
    return rows


_TUSCARORA_SECTION = re.compile(r"Section (?P<number>\d+):? (?P<name>.+)")
_TUSCARORA_SPAN = re.compile(r"(?P<span>.+?), (?P<miles>\d+(?:\.\d+)?) miles\.?")
_TUSCARORA_ELEVATION = re.compile(r"Max Elevation: (?P<max>[\d,]+) ft\.? Min Elevation: (?P<min>[\d,]+) ft\.?")


def _tuscarora_sections(page: Page, fetch) -> list[dict]:
    """PATC's Tuscarora Trail section guides (hikethetuscarora.org): seven pages, 22 sections, read 2026-10-04.

    The home page's menu links each page of sections ('Section 1-3' to 'Section 20-22'). On a page each section is
    a run of lines: 'Section 1: Sterretts Gap' (section 8's has no colon, 'Section 8 The Lockings', and lands as
    'Section 8: The Lockings'), then 'Appalachian Trail to Waggoners Gap, 12 miles.', the PATC map
    that covers it ('PATC Map J, Guide to the North Half of the Tuscarora Trail'), 'Max Elevation: 1620 ft. Min
    Elevation: 930 ft.', and labelled Highlights, Access, Advisory, Camping and Links. The name, the span, the
    miles, the map and the two elevations are read. The Access, Camping and Advisory lines are PATC's own words and
    land nowhere here, though they carry parking and shelter coordinates (a points-of-interest reader's, not a
    suggested hike's). The elevations land as the page states them: section 10's maximum, 395 ft, is below its
    minimum, 415 ft, on 2026-10-04. A section whose span line or elevation line is not that shape raises.
    """
    pages = []
    for anchor in page.root.find_all("a"):
        href = page.link(anchor.get("href"))
        if href and re.fullmatch(r"/section-\d+-\d+/?", urlparse(href).path) and href not in pages:
            pages.append(href)
    if not pages:
        raise LayoutChanged("tuscarora: the home page links no /section-N-M page")
    rows = []
    for href in pages:
        lines = fetch(href).root.lines()
        for index, line in enumerate(lines):
            section = _TUSCARORA_SECTION.fullmatch(line)
            if not section:
                continue
            span = _TUSCARORA_SPAN.fullmatch(lines[index + 1] if index + 1 < len(lines) else "")
            if not span:
                raise LayoutChanged(f"tuscarora: section {section['number']}'s span line is not 'A to B, N miles'")
            after = lines[index + 2 : index + 8]
            elevation = next((m for m in (_TUSCARORA_ELEVATION.fullmatch(text) for text in after) if m), None)
            if elevation is None:
                raise LayoutChanged(f"tuscarora: section {section['number']} states no 'Max Elevation ... Min Elevation'")
            rows.append(
                {
                    "name": f"Section {section['number']}: {fact(section['name'])}",
                    "section": f"Section {section['number']}",
                    "place": fact(span["span"]),
                    "distance_mi": float(span["miles"]),
                    "distance_text": f"{span['miles']} miles",
                    "route_type": "one way",
                    "map": next((fact(text) for text in after if text.startswith("PATC Map")), None),
                    "max_elevation_ft": number(elevation["max"]),
                    "min_elevation_ft": number(elevation["min"]),
                    "link": href,
                    "source_url": href,
                }
            )
    return rows


def _kta_favorite_hikes(page: Page, fetch) -> list[dict]:
    """The Keystone Trails Association's 'Favorite Hikes in Pennsylvania' (kta-hike.org), read 2026-10-04.

    Seven h2 groups (beginner's, backpacking, universally accessible, trail running, dog friendly, streamside and
    children's hikes, each titled in English and Spanish), and in each the hikes as runs of lines in a Weebly
    paragraph: the hike's name in bold, then its county ('Monroe County', 'Cameron, Clearfield, Elk Counties'),
    for some a town and a forest, the URL of the page that describes it (another organisation's, linked and never
    fetched), and a description in English and Spanish, which lands nowhere. A bold line is a hike only where a
    county line follows it; the first URL after it is its link. A group with no hike, or a page with no group,
    raises.
    """
    rows = []
    section = None
    for node in page.root.iter():
        if node.tag == "h2":
            text = fact(node.text()) or ""
            section = text.split(" - ")[0].strip() if text.startswith("Favorite ") else None
            continue
        if section is None or node.tag != "div" or "paragraph" not in node.classes:
            continue
        bold = {
            fact(span.text())
            for span in node.iter()
            if span.tag in ("strong", "b") or "font-weight:700" in (span.get("style") or "").replace(" ", "")
        }
        lines = node.lines()
        starts = [i for i, line in enumerate(lines) if line in bold]
        for position, start in enumerate(starts):
            end = starts[position + 1] if position + 1 < len(starts) else len(lines)
            item = lines[start + 1 : end]
            county = next((line for line in item[:4] if re.search(r"\bCount(?:y|ies)\b", line, re.IGNORECASE)), None)
            if county is None:
                continue
            link = next((line for line in item if line.startswith(("http://", "https://"))), None)
            rows.append(
                {
                    "name": lines[start],
                    "section": section,
                    "place": fact(county),
                    "link": link or page.url,
                    "source_url": page.url,
                }
            )
    if not rows:
        raise LayoutChanged("kta: no 'Favorite ...' group holds a bold hike with its county")
    return rows


def _amc_itineraries(page: Page, fetch) -> list[dict]:
    """The Appalachian Mountain Club's 'Outdoor Itineraries & Trip Ideas' (outdoors.org/resources/itineraries/).

    Three h2 regions (the White Mountains, the North Maine Woods, the Northeast and Mid-Atlantic) and in each an h5 a
    trip, then for most a 'Difficulty | Duration' line ('Strenuous | 3-4 Days') and a link to the trip's own page under
    /resources/itineraries/. Eleven trips on 2026-10-04, ski, gravel-bike and paddling trips among them as the page
    lists them. A trip is read where its first link after the h5 is an itinerary page, its name, difficulty,
    duration and link; the paragraph about it is AMC's and lands nowhere.
    """
    rows = []
    section = None
    for node in page.root.iter():
        if node.tag == "h2":
            section = fact(node.text())
            continue
        if node.tag != "h5" or section is None:
            continue
        name = fact(" ".join(node.lines()))
        difficulty = duration = link = None
        for after in node.following():
            if after.tag in ("h2", "h5"):
                break
            if after.tag == "p" and difficulty is None:
                match = re.fullmatch(r"(?P<difficulty>[^|]+?)\s*\|\s*(?P<duration>.+)", after.text())
                if match:
                    difficulty, duration = fact(match["difficulty"]), fact(match["duration"])
            if after.tag == "a" and link is None:
                href = page.link(after.get("href"))
                if href:
                    link = href
        if link and "/resources/itineraries/" in urlparse(link).path:
            rows.append(
                {
                    "name": name,
                    "section": section,
                    "difficulty": difficulty,
                    "duration": duration,
                    "link": link,
                    "source_url": page.url,
                }
            )
    return rows


_ATA_COORDINATES = re.compile(
    r"GPS Coordinates:\s*(?P<lat>\d+(?:\.\d+)?)°?\s*(?P<ns>[NS]),\s*(?P<lon>\d+(?:\.\d+)?)°?\s*(?P<ew>[EW])"
)


def _coordinates(text: str | None) -> tuple[float | None, float | None]:
    """'GPS Coordinates: 31.33367° N, 110.28276° W' as (31.33367, -110.28276), or (None, None)."""
    found = _ATA_COORDINATES.search(text or "")
    if not found:
        return None, None
    lat, lon = float(found["lat"]), float(found["lon"])
    return (-lat if found["ns"] == "S" else lat), (-lon if found["ew"] == "W" else lon)


def _ata_passages(page: Page, fetch) -> list[dict]:
    """The Arizona Trail Association's passages: aztrail.org/explore/passages/ links one page a passage, 44 on 2026-10-04.

    A passage's page names it in its h1 ('Passage 1: Huachuca Mountains') and states its facts under h3 headings:
    Location ('Mexico Border to Parker Canyon Lake Trailhead'), Length ('20.3 miles'), Difficulty ('Moderate to
    Difficult.'; 'Distance' on some), Season(s), and one h3 for each end, 'Southern Trailhead: <name>' (22 pages),
    'Southern Access Point: <name>' (21) or 'Southern Terminus: <name>' (1), and the same three for the north, each
    followed by 'GPS Coordinates: 31.33367° N, 110.28276° W'. Those are read,
    the ends' coordinates as the page states them; the Access, Trail Route Description, Water and Notes/Warnings
    sections are the association's prose and land nowhere here. A passage page with no Length raises. aztrail.org's
    robots.txt asks `Crawl-delay: 10`, so the 45 requests take about eight minutes.
    """
    passages = []
    for anchor in page.root.find_all("a"):
        href = page.link(anchor.get("href"))
        if href and re.search(r"/explore/passages/passage-[^/]+/?$", urlparse(href).path) and href not in passages:
            passages.append(href)
    if not passages:
        raise LayoutChanged("ata: the passages page links no /explore/passages/passage-... page")
    rows = []
    for href in passages:
        passage = fetch(href)
        heading = passage.root.find("h1")
        facts: dict[str, list[str]] = {}
        current = None
        for block in blocks(passage.root):
            if block.level == 3:
                current = block.text
                facts[current] = []
            elif block.level is not None:
                current = None
            elif current is not None:
                facts[current].append(block.text)

        def first(label: str) -> str | None:
            return next((fact(" ".join(facts[name][:1])) for name in facts if name.lower() == label), None)

        def end(prefixes: tuple[str, ...]) -> tuple[str | None, float | None, float | None]:
            for name, lines in facts.items():
                if name.startswith(prefixes) and ":" in name:
                    lat, lon = _coordinates(" ".join(lines))
                    return fact(name.split(":", 1)[1]), lat, lon
            return None, None, None

        length = first("length") or first("distance")
        if heading is None or length is None:
            raise LayoutChanged(f"ata: {href} has no h1 or no Length")
        distance, distance_text = miles(length)
        south, south_lat, south_lon = end(("Southern Terminus", "Southern Trailhead", "Southern Access Point"))
        north, north_lat, north_lon = end(("Northern Terminus", "Northern Trailhead", "Northern Access Point"))
        rows.append(
            {
                "name": fact(heading.text()),
                "place": first("location"),
                "distance_mi": distance,
                "distance_text": distance_text,
                "route_type": "one way",
                "difficulty": (first("difficulty") or "").rstrip(".") or None,
                "seasons": first("season(s)"),
                "south_end": south,
                "south_latitude": south_lat,
                "south_longitude": south_lon,
                "north_end": north,
                "north_latitude": north_lat,
                "north_longitude": north_lon,
                "link": passage.url,
                "source_url": passage.url,
            }
        )
    return rows


def single_miles(text: str | None) -> tuple[float | None, str | None]:
    """`text`'s distance where it states one figure ('1.8 miles, one way'), else (None, the text).

    A text with two figures states a range or two routes ('2 to 4 miles', '0.4-mile east loop and 0.7-mile west
    loop', '0.6 miles, 0.4 paved'), and which is the hike's the text does not say, so no number is read from it: its
    words land as distance_text, and distance_mi stays unknown.
    """
    text = fact(text)
    if not text:
        return None, None
    if len(re.findall(r"\d+(?:[.,]\d+)*\s*[½¼¾⅓⅔]?|\.\d+|[½¼¾⅓⅔]", text)) != 1:
        return None, text
    distance, _ = miles(text)
    return distance, text


def sitemap_locations(page: Page) -> list[str]:
    """Every <loc> a sitemap (or a sitemap index) lists, in its order."""
    return [loc.text() for loc in page.root.find_all("loc") if loc.text()]


def _cfpa_trails(page: Page, fetch) -> list[dict]:
    """CFPA's 'Find a Trail' (ctwoodlands.org/trails/): the Blue-Blazed Hiking Trail System, 57 trails on 2026-10-04.

    div#trails-list holds one link a trail, to its page under /trails/, wrapping an h3 with the trail's name and a p
    with its mileage ('56.6 miles', '4 miles'). The index alone is read, the name, the mileage and the link: the
    trail pages carry the association's prose, and ctwoodlands.org's robots.txt asks `Crawl-delay: 10`.
    """
    listing = page.root.find("div", id="trails-list")
    if listing is None:
        raise LayoutChanged("cfpa: /trails/ has no div#trails-list")
    rows = []
    for anchor in listing.find_all("a"):
        heading = anchor.find("h3")
        if heading is None:
            continue
        mileage = anchor.find("p")
        distance, distance_text = single_miles(mileage.text() if mileage is not None else None)
        rows.append(
            {
                "name": fact(heading.text()),
                "distance_mi": distance,
                "distance_text": distance_text,
                "link": page.link(anchor.get("href")),
                "source_url": page.url,
            }
        )
    return rows


_MRATC_HIKE = re.compile(r"\d+\s*/\s*(?P<name>.+)")


def _mratc_suggested_hikes(page: Page, fetch) -> list[dict]:
    """The Mount Rogers A.T. Club's Suggested Hikes (mratc.org/suggested-hikes), a Wix page: 7 hikes on 2026-10-04.

    Each h2 is a kind of hike ('Appalachian Trail Hikes', 'Iron Mountain and Linked Trail Hikes'); under it each h5
    numbers a hike ('1 / Fox Creek to Dickey Gap') and the paragraph after it opens with its facts, 'distance | shape
    | difficulty' ('8 miles | One way | Moderate'). Four h2s (High Points, Damascus, Grayson Highlands, Backpacking)
    hold no hike. The turn-by-turn paragraph after the facts is the club's, and carries coordinates written without
    a sign ('(36.72036, 81.46151)' for a point at 81° W), which are not read: a coordinate lands only where the page's
    own data states it, and these are prose. A numbered hike whose facts line is not three parts raises.
    """
    found = blocks(page.root)
    rows = []
    section = None
    for i, block in enumerate(found):
        if block.level == 2:
            section = fact(block.text)
            continue
        match = _MRATC_HIKE.fullmatch(block.text) if block.level == 5 else None
        if match is None:
            continue
        after = found[i + 1] if i + 1 < len(found) else None
        first = after.node.lines()[0] if after is not None and after.level is None and after.node.lines() else ""
        parts = [part.strip() for part in first.split("|")]
        if len(parts) != 3:
            raise LayoutChanged(f"mratc: {block.text!r} is not followed by a 'distance | shape | difficulty' line")
        distance, distance_text = single_miles(parts[0])
        rows.append(
            {
                "name": fact(match["name"]),
                "section": section,
                "distance_mi": distance,
                "distance_text": distance_text,
                "route_type": route_type(parts[1]),
                "difficulty": fact(parts[2]),
                "link": page.url,
                "source_url": page.url,
            }
        )
    return rows


_FTA_LENGTH = re.compile(r"(?:Length|Round trip distance of hike)\s*:\s*(?P<value>.*)", re.IGNORECASE)


def _fta_route(text: str | None) -> str | None:
    """A Florida hike's shape where its line names one: '1.7 mile loop + 1.2 mile spur' and '10.2 miles loop/linear'
    name two, and 'linear' alone says the trail's shape, not whether the hike is one way or out and back."""
    if not text or re.search(r"linear|spur|connector|/|\+|,|\band\b", text, re.IGNORECASE):
        return None
    return route_type(text)


def _fta_day_hikes(page: Page, fetch) -> list[dict]:
    """The Florida Trail Association's 'Day & Section Hike' page (floridatrail.org/day-hike/): two hotspot maps.

    The page's two maps, under the h3s 'Grab-And-Go FT Hikes:' and 'Other Trail Hikes:', hold one tooltip a hike
    (span.uael-tooltip-text): 16 and 35 on 2026-10-04, each map's container stating its own count (data-length),
    which this parser holds the tooltips to. A tooltip's first line names the hike; the Grab-and-Go ones then give a
    place on a line of its own ('Blackwater River Forest'), a distance line ('8.1 miles linear') and a link to the
    hike's grab-and-go PDF, and the others a 'Length:' line ('Length: 4.8 mile loop'). The name, the place, the
    distance (a number only where the line states one figure, single_miles) and the PDF link are read; every
    paragraph after them is the association's and lands nowhere. Five of the Grab-and-Go tooltips (2026-10-04) open
    with 'Location: ...' and name no hike at all; they are left out, a hike with no name being nothing a hiker can
    look for. A coordinate inside a tooltip's prose ('(28.116917, -80.932467)') is not read.
    """
    rows = []
    heading = None
    containers = 0
    for node in page.root.iter():
        if node.tag == "h3":
            heading = fact(node.text().rstrip(": "))
        if "uael-hotspot-container" not in node.classes:
            continue
        containers += 1
        tips = node.find_all("span", cls="uael-tooltip-text")
        stated = node.get("data-length")
        if stated is None or not stated.isdigit() or int(stated) != len(tips):
            raise LayoutChanged(f"fta: a map states {stated} hikes and holds {len(tips)} tooltips")
        for tip in tips:
            anchors = {fact(a.text()) for a in tip.find_all("a")}
            lines = [line for line in tip.lines() if not re.fullmatch(r"\d+ of \d+|« Previous|Next »", line)]
            if not lines or ":" in lines[0]:
                continue  # 'Location: ...': a tooltip that names no hike
            name, rest = lines[0], lines[1:]
            distance = distance_text = place = None
            for i, line in enumerate(rest[:3]):
                length = _FTA_LENGTH.fullmatch(line)
                if length or (len(line) <= 40 and re.search(r"\bmiles?\b", line, re.IGNORECASE)):
                    distance, distance_text = single_miles(length["value"] if length else line)
                    candidate = rest[0] if i == 1 else None
                    if candidate and candidate not in anchors and ":" not in candidate and len(candidate) <= 60:
                        place = candidate
                    break
            pdf = next(
                (
                    page.link(a.get("href"))
                    for a in tip.find_all("a")
                    if (a.get("href") or "").lower().endswith(".pdf") and same_site(page.url, page.link(a.get("href")))
                ),
                None,
            )
            rows.append(
                {
                    "name": fact(name),
                    "section": heading,
                    "place": fact(place),
                    "distance_mi": distance,
                    "distance_text": distance_text,
                    "route_type": _fta_route(distance_text),
                    "link": pdf or page.url,
                    "source_url": page.url,
                }
            )
    if containers != 2:
        raise LayoutChanged(f"fta: the page holds {containers} hotspot maps, not the two this parser reads")
    return rows


# '58.2 total miles / 14.1 off-road miles (24.2%)', as 25 of the 26 pages write it on 2026-10-04; Shawnee's 'Total
# Miles / ... Off Road Miles', Norwalk's '66.1total miles' and one page's leading 'Miles: ' are the same line.
_BUCKEYE_MILES = re.compile(
    r"(?:Miles:\s*)?(?P<total>[\d.]+)\s*total miles\s*/\s*(?P<off_road>[\d.]+)\s*off[- ]road miles.*", re.IGNORECASE
)


def _buckeye_sections(page: Page, fetch) -> list[dict]:
    """The Buckeye Trail Association's 26 sections (buckeyetrail.org/sections), each a page of its own.

    The index links each section's page (/sections/<name>); each page names the section in its h1 and states its
    facts as a definition list (dl.facts-table). 'Miles' ('58.2 total miles / 14.1 off-road miles (24.2%)') and
    'Counties' are read; the list's 'Section supervisor' and 'Contact' entries are a volunteer's name, e-mail and
    telephone number and are never read, and nor is the page's prose (what to expect, towns, points of interest). A
    section page with no Miles raises.
    """
    sections_found = []
    for anchor in page.root.find_all("a"):
        href = page.link(anchor.get("href"))
        if href and re.fullmatch(r"/sections/[a-z0-9-]+/?", urlparse(href).path) and href not in sections_found:
            sections_found.append(href)
    if not sections_found:
        raise LayoutChanged("buckeye: /sections links no /sections/<name> page")
    rows = []
    for href in sections_found:
        section = fetch(href)
        heading = section.root.find("h1")
        table = section.root.find("dl", cls="facts-table")
        facts: dict[str, str] = {}
        if table is not None:
            label = None
            for node in table.children:
                if not isinstance(node, Node):
                    continue
                if node.tag == "dt":
                    label = fact(node.text())
                elif node.tag == "dd" and label in ("Miles", "Counties"):
                    facts[label] = fact(node.text())
        mileage = _BUCKEYE_MILES.fullmatch(facts.get("Miles") or "")
        if heading is None or mileage is None:
            raise LayoutChanged(f"buckeye: {href} has no h1 or no 'N total miles / N off-road miles'")
        rows.append(
            {
                "name": fact(heading.text()),
                "place": facts.get("Counties"),
                "distance_mi": number(mileage["total"]),
                "distance_text": facts["Miles"],
                "off_road_mi": number(mileage["off_road"]),
                "link": section.url,
                "source_url": section.url,
            }
        )
    return rows


_SMD_HIKE = re.compile(r"\d+\.\s*\S.*")


def _smd_diablo_range_hikes(page: Page, fetch) -> list[dict]:
    """Save Mount Diablo's field guide 'Hikes in the Diablo Range' (savemountdiablo.org/experience/field-guides/...).

    Each h3 is a region ('Mount Diablo Region / North of Altamont Pass', 'South of Altamont Pass'), each h4 under it
    a part of it ('Mount Diablo—North', 'Alameda County'), and under each h4 one paragraph a hike, numbered and linked
    ('1. Black Point Trail' to the hike's post on savemountdiablo.org): 47 on 2026-10-04. The name, the region, the
    part and the link are read; the posts are Save Mount Diablo's writing and are not fetched. A hike two parts
    list (Marsh Creek Regional Trail, under North and East) is a row in each.
    """
    rows = []
    region = part = None
    for block in blocks(page.root):
        if block.level == 3:
            region, part = fact(block.text), None
            continue
        if block.level == 4:
            part = fact(block.text)
            continue
        if block.level is not None or part is None or not _SMD_HIKE.fullmatch(block.text):
            continue
        anchor = block.node.find("a")
        link = page.link(anchor.get("href")) if anchor is not None else None
        if link is None:
            continue
        rows.append(
            {
                "name": fact(anchor.text()),
                "place": region,
                "section": part,
                "link": link,
                "source_url": page.url,
            }
        )
    return rows


def _mohonk_suggested_hikes(page: Page, fetch) -> list[dict]:
    """Mohonk Preserve's Suggested Hikes (mohonkpreserve.org/visit/activities/suggested-hikes/), by trailhead.

    Each h4 is a trailhead ('From the West Trapps Trailhead') or 'Other Hikes'; the page lists its h4s twice, once as
    a table of contents linking in-page anchors, which holds no hike. Under a trailhead each h6 names a hike
    ('Millbrook Ridge Loops'), and the first PDF linked after it, before the next hike, is its printable trail map;
    an h6 ending in ':' ('From the Duck Pond Visitor Experience Booth:') is a sub-heading, not a hike. Under 'Other
    Hikes' each list item is a hike and links its map. 13 hikes on 2026-10-04. The name, the trailhead and the map's
    link are read. The page states distances for one hike only, as three return routes ('Return via Bayards Path –
    2.0 miles' and two more), which name no one distance for it, so no distance is read; the photographs' credits
    are people's names and are not read.
    """
    rows = []
    trailhead = None
    current = None
    for node in page.root.iter():
        if node.tag == "h4":
            trailhead, current = fact(node.text()), None
            continue
        if node.tag == "h6" and trailhead is not None:
            name = fact(node.text())
            current = None
            if name and not name.endswith(":") and not name.lower().startswith("click"):
                current = {"name": name, "section": trailhead, "link": None, "source_url": page.url}
                rows.append(current)
            continue
        if node.tag == "li" and trailhead == "Other Hikes":
            anchor = node.find("a")
            href = page.link(anchor.get("href")) if anchor is not None else None
            if href and href.lower().endswith(".pdf"):
                rows.append({"name": fact(node.text()), "section": trailhead, "link": href, "source_url": page.url})
            continue
        if node.tag == "a" and current is not None and current["link"] is None:
            href = page.link(node.get("href"))
            if href and href.lower().endswith(".pdf"):
                current["link"] = href
    for row in rows:
        row["link"] = row["link"] or page.url
    return rows


def _onda_hikes(page: Page, fetch) -> list[dict]:
    """The Oregon Natural Desert Association's hikes: hike-sitemap.xml lists 24 /hike/ pages, 2026-10-04.

    The registry row's URL is the sitemap, the one place every hike page is listed (the /hike/ archive pages by
    query string). Each hike's page names it in its h1 and states its facts as a list (li.hike-info__item), an h6
    label and a paragraph: Distance ('16 miles round-trip (10 miles one-way w/ shuttle option)'), Best Times To
    Visit, 'Dificulty' (spelt so; a number, '3'), Closest Town and Drive Time. Those are read; the Description, Notes
    and Driving Directions sections are ONDA's prose, and the hero photograph's credit is a person's name, and none
    of them is read. onda.org's robots.txt asks `Crawl-delay: 10`, so the 25 requests take about four minutes. A hike
    page with no fact list raises.
    """
    hikes = [loc for loc in sitemap_locations(page) if re.fullmatch(r"/hike/[^/]+/?", urlparse(loc).path)]
    if not hikes:
        raise LayoutChanged("onda: hike-sitemap.xml lists no /hike/<name>/ page")
    rows = []
    for href in hikes:
        hike = fetch(href)
        heading = hike.root.find("h1")
        facts: dict[str, str] = {}
        for item in hike.root.find_all("li", cls="hike-info__item"):
            label, value = item.find("h6"), item.find("p")
            if label is not None and value is not None:
                facts[fact(label.text()).lower()] = fact(value.text())
        if heading is None or not facts:
            raise LayoutChanged(f"onda: {href} has no h1 or no hike-info list")
        distance, distance_text = single_miles(facts.get("distance"))
        rows.append(
            {
                "name": fact(heading.text()),
                "place": facts.get("closest town"),
                "distance_mi": distance,
                "distance_text": distance_text,
                "route_type": route_type(facts.get("distance")),
                "difficulty": facts.get("dificulty") or facts.get("difficulty"),
                "seasons": facts.get("best times to visit"),
                "drive_time": facts.get("drive time"),
                "link": hike.url,
                "source_url": hike.url,
            }
        )
    return rows


_OTA_FACTS = {"Miles of Trail": "miles", "Difficulty": "difficulty", "N to S ascent": "north_to_south", "S to N ascent": "south_to_north"}  # fmt: skip


def _ota_feet(text: str | None) -> tuple[float | None, str | None]:
    """An OTA ascent as the page writes it, '4200′' (a prime, not an apostrophe), as (feet, the text)."""
    found = re.fullmatch(r"(?P<feet>[\d,]+)\s*[′']", fact(text) or "")
    return (number(found["feet"]), found.group(0)) if found else (None, fact(text))


def _ota_sections(page: Page, fetch) -> list[dict]:
    """The Ozark Trail Association's Trail Directory (ozarktrail.com/trail-directory/): 14 sections, 2026-10-04.

    The directory links each section from a card whose h1 names it, eight under 'Thru-Hike (North to South)'
    numbered in order ('1. Courtois') and six under 'Remaining Sections'. Thirteen of the links are WordPress
    '?page_id=N' links that redirect to the section's page; ozarktrail.com's robots.txt disallows only its shop's
    '?add-to-cart=' URLs, so the parser asks them (`queries`). A section's page states four figures, each an h1 over
    its label: the miles ('48' over 'Miles of Trail'), the difficulty ('MODERATE' over 'Difficulty') and the ascent
    each way ('4200′' over 'N to S ascent', and 'S to N ascent'). Those, the section's name as the directory writes
    it (its number left off) and the link are read; the Trail Conditions, Trail Geography and land-manager paragraphs
    are not (the conditions are decision 53's ota_*_conditions rows). A section page with no 'Miles of Trail' raises.
    """
    sections_found: list[tuple[str, str, str | None]] = []
    group = None
    for node in page.root.iter():
        if node.tag == "h3":
            group = fact(node.text())
        if node.tag != "a":
            continue
        heading = node.find("h1")
        href = page.link(node.get("href"))
        if heading is not None and href and same_site(page.url, href):
            name = re.sub(r"^\d+\.\s*", "", heading.text()).strip()
            sections_found.append((fact(name), href, group))
    if not sections_found:
        raise LayoutChanged("ota: the trail directory links no section card")
    rows = []
    for name, href, group in sections_found:
        section = fetch(href)
        found = blocks(section.root)
        facts: dict[str, str] = {}
        for i, block in enumerate(found[:-1]):
            label = found[i + 1].text
            if block.level == 1 and found[i + 1].level is None and label in _OTA_FACTS:
                facts.setdefault(_OTA_FACTS[label], block.text)
        if "miles" not in facts:
            raise LayoutChanged(f"ota: {href} states no 'Miles of Trail'")
        north, north_text = _ota_feet(facts.get("north_to_south"))
        south, south_text = _ota_feet(facts.get("south_to_north"))
        rows.append(
            {
                "name": name,
                "section": group,
                "distance_mi": number(facts["miles"]),
                "distance_text": f"{facts['miles']} Miles of Trail",
                "difficulty": fact(facts.get("difficulty")),
                "ascent_north_to_south_ft": north,
                "ascent_south_to_north_ft": south,
                "ascent_text": fact("; ".join(f"{v} {k}" for k, v in (("N to S", north_text), ("S to N", south_text)) if v)),
                "link": section.url,
                "source_url": section.url,
            }
        )
    return rows


_PALMETTO_FACTS = {"Region": "place", "Surface": "surface", "Pets": "pets", "Fees": "fees",
                   "Camping Allowed": "camping", "Trail on Hunting Grounds": "hunting_grounds"}  # fmt: skip


def _palmetto_passages(page: Page, fetch) -> list[dict]:
    """The Palmetto Trail's passages: palmettotrail.org's sitemap.xml lists 33 /trails/trail/ pages, 2026-10-04.

    The registry row's URL is the sitemap: the /trails index draws its list in the browser and its HTML links no
    passage. A passage's page names it in h2.Trail-h1 and states its length (span.Trail-length, '4.6 miles') and
    difficulty (span.Trail-difficulty, 'Moderate'), then a grid of facts, each a div.Trail-detailGridHeading and the
    div.Trail-detailGridData after it, whose first line is the answer ('Depends', 'Yes') and whose rest is the
    conservation foundation's explanation. The answers to Region, Surface, Pets, Fees, Camping Allowed and Trail on
    Hunting Grounds are read, first lines only, and the Activities icons' names ('Hiking', 'Biking'); the
    explanations, the description and the directions are not. The trailheads' coordinates the page lists are
    trailheads, a point of interest's, not a hike's, and are not read here. A passage page with no Trail-h1 raises.
    """
    passages = [loc for loc in sitemap_locations(page) if re.fullmatch(r"/trails/trail/[a-z0-9-]+/?", urlparse(loc).path)]
    if not passages:
        raise LayoutChanged("palmetto: sitemap.xml lists no /trails/trail/ page")
    rows = []
    for href in passages:
        passage = fetch(href)
        heading = passage.root.find("h2", cls="Trail-h1")
        if heading is None:
            raise LayoutChanged(f"palmetto: {href} has no h2.Trail-h1")
        length = passage.root.find("span", cls="Trail-length")
        difficulty = passage.root.find("span", cls="Trail-difficulty")
        row = {name: None for name in _PALMETTO_FACTS.values()}
        activities = None
        for label in passage.root.find_all("div", cls="Trail-detailGridHeading"):
            data = next((node for node in label.following() if "Trail-detailGridData" in node.classes), None)
            if data is None:
                continue
            name = fact(label.text())
            if name in _PALMETTO_FACTS:
                lines = data.lines()
                row[_PALMETTO_FACTS[name]] = fact(lines[0]) if lines else None
            elif name == "Activities":
                activities = fact(
                    ", ".join(n.get("data-tip-below-center") for n in data.find_all("span") if n.get("data-tip-below-center"))
                )
        distance, distance_text = single_miles(length.text() if length is not None else None)
        row.update(
            {
                "name": fact(heading.text()),
                "distance_mi": distance,
                "distance_text": distance_text,
                "difficulty": fact(difficulty.text()) if difficulty is not None else None,
                "activities": activities,
                "link": passage.url,
                "source_url": passage.url,
            }
        )
        rows.append(row)
    return rows


_WI_TRAIL = re.compile(
    r"(?P<name>[^()]+?)\s*(?:\((?P<paren>[^()]*?\d[^()]*?)\)|[—–]\s*(?P<dash>\d[^()]*?))"
    r"(?:\s*[-–—]\s*(?P<difficulty>[A-Za-z][A-Za-z ]*))?"
)


def _wi_dnr_hiking(page: Page, fetch) -> list[dict]:
    """The Wisconsin DNR's property hiking pages (dnr.wisconsin.gov/topic/<kind>/<property>/recreation/hiking).

    No page lists them, so the registry row's URL is the site's sitemap index: its ten pages (sitemap.xml?page=N;
    dnr.wisconsin.gov's robots.txt disallows no query string, so the parser asks them, `queries`) list 46 property
    hiking pages, 2026-10-04, beside the department-wide /topic/parks/recreation/hiking, which names no trail. A
    property's page names the property in the first h2 after its h1 'Hiking' and each trail in a heading of its
    own, 20 of the 46 with the trail's length in the heading: 'Balanced Rock trail (0.4 miles) - Most difficult',
    'Tom Roberts Trail — 0.55 miles', 'Eagle Trail (2.0-mile loop)', 170 trails in all. Those headings are read: the
    name, the property, the length (a number only where one figure is stated, single_miles), the shape and the
    difficulty after ' - '. A trail named in a heading with no length (Blue Mound's 'Flintrock Trail') has its length
    in the department's paragraph under it, which is not read, so the 26 pages written that way land no row: a gap
    this reader states rather than fills from prose.
    """
    pages = [loc for loc in sitemap_locations(page) if urlparse(loc).path.endswith("sitemap.xml")]
    if not pages:
        raise LayoutChanged("wi_dnr: sitemap.xml is no sitemap index")
    properties = []
    for href in pages:
        for loc in sitemap_locations(fetch(href)):
            path = urlparse(loc).path
            if re.fullmatch(r"/topic/\w+/\w+/recreation/hiking/?", path) and loc not in properties:
                properties.append(loc)
    if not properties:
        raise LayoutChanged("wi_dnr: the sitemap lists no /topic/<kind>/<property>/recreation/hiking page")
    rows = []
    for href in properties:
        hiking = fetch(href)
        found = blocks(hiking.root)
        start = next((i for i, block in enumerate(found) if block.level == 1), None)
        place = next((block.text for block in found[start + 1 :] if block.level == 2), None) if start is not None else None
        if place is None:
            raise LayoutChanged(f"wi_dnr: {href} has no h1 or no h2 naming the property")
        for block in found[start + 1 :]:
            if block.level not in (2, 3, 4) or block.text == place:
                continue
            match = _WI_TRAIL.fullmatch(block.text)
            facts = match and (match["paren"] or match["dash"])
            if not facts or not re.search(r"\bmiles?\b|-mile\b", facts, re.IGNORECASE):
                continue
            distance, distance_text = single_miles(facts)
            rows.append(
                {
                    "name": fact(match["name"]),
                    "place": fact(place),
                    "distance_mi": distance,
                    "distance_text": distance_text,
                    "route_type": route_type(facts),
                    "difficulty": fact(match["difficulty"]),
                    "link": hiking.url,
                    "source_url": hiking.url,
                }
            )
    return rows


def _mdhta_trails(page: Page, fetch) -> list[dict]:
    """The Maah Daah Hey Trail Association's trails (mdhta.com/trails/), a WordPress archive paged by 'Older posts'.

    Each archive page links its trails' pages from h2s (/trails/<name>/), and an 'Older posts' link to the next page
    (/trails/page/2/): 19 trails on two pages, 2026-10-04. A trail's page names it in its h1 and states its facts
    under h5 labels: Distance ('0.9 miles'), on 12 of the 19, is read. Campgrounds names camps, which are points of
    interest and not read here; Overview, and 'Ideal for:', which on most pages is a sentence ('hiking, biking and
    horse riding in all types of terrain ...'), are the association's prose. At most ten archive pages are followed.
    A trail page with no h1 raises.
    """
    trails: list[str] = []
    archive: Page | None = page
    for _ in range(10):
        for heading in archive.root.find_all("h2"):
            anchor = heading.find("a")
            href = archive.link(anchor.get("href")) if anchor is not None else None
            if href and re.fullmatch(r"/trails/[a-z0-9-]+/?", urlparse(href).path) and href not in trails:
                trails.append(href)
        older = next((a for a in archive.root.find_all("a") if fact(a.text()) == "Older posts"), None)
        href = archive.link(older.get("href")) if older is not None else None
        if not href:
            break
        archive = fetch(href)
    if not trails:
        raise LayoutChanged("mdhta: /trails/ links no /trails/<name>/ page")
    rows = []
    for href in trails:
        trail = fetch(href)
        heading = trail.root.find("h1")
        if heading is None:
            raise LayoutChanged(f"mdhta: {href} has no h1")
        facts: dict[str, list[str]] = {}
        current = None
        for block in blocks(trail.root):
            if block.level == 5:
                current = fact(block.text.rstrip(":")).lower()
                facts[current] = []
            elif block.level is not None:
                current = None
            elif current is not None:
                facts[current].append(block.text)
        distance, distance_text = single_miles(" ".join(facts.get("distance", [])[:1]) or None)
        rows.append(
            {
                "name": fact(heading.text()),
                "distance_mi": distance,
                "distance_text": distance_text,
                "link": trail.url,
                "source_url": trail.url,
            }
        )
    return rows


def _blue_hills_hikes(page: Page, fetch) -> list[dict]:
    """The Friends of the Blue Hills' Suggested Hikes (friendsofthebluehills.org/hiking-near-boston/).

    Between the h2 'Hikes' and the next h2, each h4 names a hike and most link its page: 18 on 2026-10-04, one (St.
    Moritz to the former Civilian Conservation Corps camp) with no page of its own, whose link is this page. The
    names and links are read. Neither the paragraph under each h4 nor the hike pages state a distance as a fact (a
    hike's page is a paragraph or two of the Friends' prose), so no distance is read and none is fetched.
    """
    rows = []
    inside = False
    for block in blocks(page.root):
        if block.level == 2:
            inside = block.text == "Hikes"
            continue
        if not inside or block.level != 4:
            continue
        anchor = block.node.find("a")
        link = page.link(anchor.get("href")) if anchor is not None else None
        rows.append({"name": fact(block.text), "link": link or page.url, "source_url": page.url})
    return rows


_TRUSTEES_PLACE = re.compile(r"(?P<rank>\d+)\.\s*(?P<name>.+), (?P<town>[^,]+)")


def _trustees_hikers_top_ten(page: Page, fetch) -> list[dict]:
    """The Trustees' 'Hikers Top Ten' (thetrustees.org/program/the-trustee-hikers-top-ten/): ten properties.

    The Hike Trustees group's vote, read 2026-10-04: one h5 a property, numbered from 10 to 1 and linked to the
    property's page ('10. Monument Mountain, Great Barrington'). The rank, the property, its town and the link are
    read; the members' quotes under each are people's words, attributed by first name ('Trustee Hiker Simone said'),
    and the property's description is The Trustees', and neither is read. A list that is not ten raises.
    """
    rows = []
    for heading in page.root.find_all("h5"):
        match = _TRUSTEES_PLACE.fullmatch(fact(heading.text()) or "")
        anchor = heading.find("a")
        if match is None or anchor is None:
            continue
        rows.append(
            {
                "name": fact(match["name"]),
                "place": fact(match["town"]),
                "rank": int(match["rank"]),
                "link": page.link(anchor.get("href")),
                "source_url": page.url,
            }
        )
    if rows and sorted(row["rank"] for row in rows) != list(range(1, 11)):
        raise LayoutChanged(f"trustees: the top ten ranks {sorted(row['rank'] for row in rows)}, not 1 to 10")
    return rows


# --- Challenges: a challenge's own list of places, one row a place (decision 3: "a club's list of places") ------


_GATC_PEAK = re.compile(r"(?P<name>.+) - (?P<feet>[\d,]+) ft\.?")


def _gatc_georgia_4000(page: Page, fetch) -> list[dict]:
    """The Georgia Appalachian Trail Club's Georgia 4000 peaks (georgia-atclub.org/for-hikers/georgia-4000/...).

    The challenge's own page (/for-hikers/georgia-4000/) names it: climb all 32 North Georgia peaks of 4,000 feet or
    more and 'sport our patch'. Its peaks page, read 2026-10-04, gives each peak an h5, 'Brasstown Bald - 4,784 ft.',
    and labelled lines under it: 'Land Area: Brasstown Wilderness', 'Trail(s): Paved walking trail from parking lot.'
    ('Trail (s):' on one), then 'Notes:', the club's prose, not read. The name, the elevation as the page states it,
    the land area and the trails are read; 'Bushwhack' as a peak's trails is the page's word that no trail reaches it.
    """
    rows = []
    for heading in page.root.find_all("h5"):
        peak = _GATC_PEAK.fullmatch(fact(heading.text()) or "")
        if peak is None:
            continue
        facts: dict[str, str] = {}
        for node in heading.following():
            if node.tag == "h5":
                break
            if node.tag == "p" or node.tag == "li":
                label = LABEL.fullmatch(fact(node.text()) or "")
                if label:
                    facts.setdefault(re.sub(r"\s+", "", label["label"]).lower(), fact(label["value"]))
        elevation, elevation_text = feet(f"{peak['feet']} ft")
        rows.append(
            {
                "challenge": "Georgia 4000",
                "name": fact(peak["name"]),
                "item_type": "peak",
                "elevation_ft": elevation,
                "elevation_text": fact(f"{peak['feet']} ft."),
                "place": facts.get("landarea"),
                "trails": facts.get("trail(s)"),
                "link": page.url,
                "source_url": page.url,
            }
        )
    return rows


_AMC_LISTS = ("whitemountainfourk.html", "newenglandfourk.html", "newenglandhundredhighest.html")


def _amc_four_thousand_footer_lists(page: Page, fetch) -> list[dict]:
    """The AMC Four Thousand Footer Club's lists (amc4000footer.org/the-lists-we-recognize.html), as tables.

    The index names the lists the club recognizes and links three as pages (_AMC_LISTS), each one table: the White
    Mountain Four Thousand Footers (Rank, Name, Elev: 48 on 2026-10-04), the New England Four Thousand Footers (Rank,
    Name, State/Rank, Elevation: 67) and the New England Hundred Highest's peaks below 4,000 feet (the same and Trail:
    33, which with the 67 make the hundred). The fourth, the Northeast 111, is a PDF and is not read. Each row is a
    peak: its rank, name, state, elevation as written, and on the Hundred Highest whether a trail reaches it ('yes',
    'no', 'herd path'). An elevation marked '*' is, in the pages' words, 'estimated by adding half of the contour
    interval to the highest contour line', which `elevation_estimated` carries beside the number. The list's name is
    the index's link text. A list page whose table has no Name or no elevation column raises.
    """
    names: dict[str, str] = {}
    for anchor in page.root.find_all("a"):
        href = page.link(anchor.get("href"))
        text = fact(anchor.text()) or ""
        tail = urlparse(href or "").path.rsplit("/", 1)[-1]
        if tail in _AMC_LISTS and text.startswith("The "):
            names.setdefault(tail, (href, text.rstrip("*").strip()))
    if set(names) != set(_AMC_LISTS):
        raise LayoutChanged(f"amc4000: the index links {sorted(names)}, not the three list pages")
    rows = []
    for tail in _AMC_LISTS:
        href, challenge = names[tail]
        listing = fetch(href)
        table = listing.root.find("table")
        header, body = table_rows(table) if table is not None else ([], [])
        columns = {name.lower(): i for i, name in enumerate(header)}
        elevation_at = columns.get("elevation", columns.get("elev"))
        if "name" not in columns or elevation_at is None:
            raise LayoutChanged(f"amc4000: {href}'s table reads {header}, with no Name or elevation")
        for cells in body:
            text = cells[elevation_at]
            state = cells[columns["state/rank"]].split()[0] if "state/rank" in columns else None
            rows.append(
                {
                    "challenge": challenge,
                    "name": fact(cells[columns["name"]]),
                    "item_type": "peak",
                    "rank": int(cells[columns["rank"]]) if cells[columns["rank"]].isdigit() else None,
                    "elevation_ft": number(text.rstrip("*")),
                    "elevation_text": fact(text),
                    "elevation_estimated": text.endswith("*"),
                    "place": state,
                    "trail": fact(cells[columns["trail"]]) if "trail" in columns else None,
                    "link": listing.url,
                    "source_url": listing.url,
                }
            )
    return rows


def _sstc_sweet_16(page: Page, fetch) -> list[dict]:
    """The Standing Stone Trail Club's Sweet Sixteen Trail Challenge (standingstonetrail.org/sweet-16-trail-challenge).

    A Wix page: 'Visit each of the Standing Stone Trail's "Sweet Sixteen Trail Challenge" locations & answer a
    question about each point of interest.' After the h5 'POINTS OF INTEREST', each point is an h2 ('Cowans Gap')
    and, for most, a line continuing its name ('State Park Overlook'), which Wix sets as a paragraph of its own: 16 on
    2026-10-04. The name, joined, is read. The page's question for each point is in the printable form, not read.
    """
    found = blocks(page.root)
    start = next((i for i, block in enumerate(found) if block.text == "POINTS OF INTEREST"), None)
    if start is None:
        raise LayoutChanged("sstc: the page has no 'POINTS OF INTEREST' heading")
    rows = []
    current = None
    for block in found[start + 1 :]:
        if block.text.startswith("©"):
            break
        if block.level == 2:
            current = {"challenge": "Sweet Sixteen Trail Challenge", "name": block.text, "item_type": "point of interest",
                       "link": page.url, "source_url": page.url}  # fmt: skip
            rows.append(current)
        elif block.level is None and current is not None and len(block.text) <= 60:
            current["name"] = f"{current['name']} {block.text}"
    for row in rows:
        row["name"] = fact(row["name"])
    return rows


def _ttc_scavenger_hunt(page: Page, fetch) -> list[dict]:
    """The Trail Conservancy's History of the Trail Scavenger Hunt (thetrailconservancy.org/programs/scavenger-hunt/).

    Under the h2 'Scavenger Hunt Clues' each clue location is a button linking its clue sheet, a PDF under
    /wp-content/uploads/ ('Johnson Creek Trailhead'): 15 on the Ann and Roy Butler Hike-and-Bike Trail, 2026-10-04.
    The location's name and its clue sheet's link are read; the sheets (a clue and a QR code each) are not.
    """
    rows = []
    inside = False
    for node in page.root.iter():
        if node.tag in HEADINGS:
            inside = fact(node.text()) == "Scavenger Hunt Clues" or (inside and node.tag not in ("h1", "h2"))
            continue
        if not inside or node.tag != "a" or "elementor-button" not in node.classes:
            continue
        href = page.link(node.get("href"))
        if href and href.lower().endswith(".pdf"):
            rows.append(
                {
                    "challenge": "History of the Trail Scavenger Hunt",
                    "name": fact(node.text()),
                    "item_type": "clue location",
                    "link": href,
                    "source_url": page.url,
                }
            )
    return rows


def _dcnr_geotrail(page: Page, fetch) -> list[dict]:
    """PA DCNR's GeoTrail for America's 250th (pa.gov/agencies/dcnr/recreation/what-to-do/geocaching/dcnr-geo-trail).

    One geocache a state park or environmental education center: each is an accordion item, its title the place
    ('Beltzville State Park') and its panel a 'Geocache Theme:' line, a paragraph of the department's prose and a
    link to the cache's page on geocaching.com ('https://www.geocaching.com/geocache/GCBJH8G'): 25 on 2026-10-04,
    two of them (Benjamin Rush and Ohiopyle) marking the theme line '♿', which lands as `accessible`. The place, the
    theme and the cache's link are read; the cache's coordinates are on geocaching.com, under its terms,
    and are not read, and the hike's length is inside the prose ('less than 0.5 miles') and is not either.
    """
    rows = []
    for item in page.root.find_all("div", cls="cmp-accordion__item"):
        title = item.find("span", cls="cmp-accordion__title")
        theme_line = next(
            (fact(p.text()) for p in item.find_all("p") if re.match(r"♿?\s*Geocache Theme:", fact(p.text()) or "")), None
        )
        theme = fact(theme_line.split(":", 1)[1]) if theme_line else None
        cache = next(
            (a.get("href") for a in item.find_all("a") if re.search(r"geocaching\.com/geocache/GC\w+", a.get("href") or "")),
            None,
        )
        if title is None or theme is None:
            continue
        rows.append(
            {
                "challenge": "DCNR GeoTrail: Celebrating America's 250th",
                "name": fact(title.text()),
                "item_type": "geocache",
                "theme": theme,
                "accessible": theme_line.startswith("♿") if theme_line else None,
                "link": cache or page.url,
                "source_url": page.url,
            }
        )
    return rows


def _cmc_lookout_towers(page: Page, fetch) -> list[dict]:
    """The Carolina Mountain Club's Lookout Tower Challenge (LTC): 23 fire lookout towers in western North Carolina.

    The challenge's page (carolinamountainclub.org/hiking/hiking-challenges/lookout-tower-challenge-ltc/) holds one
    accordion item a national forest or region, its title a p.title ('Nantahala National Forest'), and in it a
    'LOOKOUT TOWERS:' paragraph ('Lookout Towers' in the Smokies' item) followed by one paragraph of the towers'
    names, one a line: 23 in five items on 2026-10-04, the FAQ's items holding none. Each tower's own block
    after that is the club's prose and its routes with one-way miles ('Appalachian Trail from Wilson Lick Ranger
    Station (3.2)'), which are not read. The tower's name and its forest are read. The page names the challenge's
    coordinator and the towers' photographers, people, and neither is read.
    """
    rows = []
    for item in page.root.find_all("div", cls="accordion-item-container"):
        title = item.find("p", cls="title")
        paragraphs = item.find_all("p")
        marker = next(
            (i for i, p in enumerate(paragraphs) if re.fullmatch(r"lookout towers:?", fact(p.text()) or "", re.I)), None
        )
        if title is None or marker is None or marker + 1 >= len(paragraphs):
            continue
        for name in paragraphs[marker + 1].lines():
            rows.append(
                {
                    "challenge": "Lookout Tower Challenge",
                    "name": fact(name),
                    "item_type": "fire lookout tower",
                    "section": fact(title.text()),
                    "link": page.url,
                    "source_url": page.url,
                }
            )
    return rows


#: Every site's parser, by the registry key (or the `site`) its resource names.
SITE_PARSERS: dict[str, SiteParser] = {
    "mazamas_hike_list": SiteParser(
        _mazamas_hikelist, columns={"driving_mi": "double", "driving_from": "text", "trailhead_fee": "bool"}
    ),
    "tahoe_rim_day_hikes": SiteParser(_tahoe_rim_day_hikes, columns={"bikes_allowed": "text", "access_from": "text"}),
    "nc_parks_trails": SiteParser(
        _nc_parks_trails, columns={"blaze": "text", "trail_use": "text", "accessible": "text", "access": "text"}
    ),
    "cvatc_foliage_hikes": SiteParser(_cvatc_foliage_hikes),
    "foothills_sections": SiteParser(_foothills_sections, columns={"blazes": "text"}),
    "cohos_day_hikes": SiteParser(_cohos_day_hikes, columns={"feature": "text"}),
    "patc_tuscarora_sections": SiteParser(
        _tuscarora_sections, columns={"map": "text", "max_elevation_ft": "double", "min_elevation_ft": "double"}
    ),
    "kta_favorite_hikes": SiteParser(_kta_favorite_hikes),
    "amc_itineraries": SiteParser(_amc_itineraries, columns={"duration": "text"}),
    "ata_passages": SiteParser(
        _ata_passages,
        columns={
            "seasons": "text",
            "south_end": "text",
            "south_latitude": "double",
            "south_longitude": "double",
            "north_end": "text",
            "north_latitude": "double",
            "north_longitude": "double",
        },
    ),
    "cfpa_trails": SiteParser(_cfpa_trails),
    "mratc_suggested_hikes": SiteParser(_mratc_suggested_hikes),
    "fta_day_hikes": SiteParser(_fta_day_hikes),
    "buckeye_sections": SiteParser(_buckeye_sections, columns={"off_road_mi": "double"}),
    "smd_diablo_range_hikes": SiteParser(_smd_diablo_range_hikes),
    "mohonk_suggested_hikes": SiteParser(_mohonk_suggested_hikes),
    "onda_hikes": SiteParser(_onda_hikes, columns={"seasons": "text", "drive_time": "text"}),
    "ota_sections": SiteParser(
        _ota_sections,
        columns={"ascent_north_to_south_ft": "double", "ascent_south_to_north_ft": "double", "ascent_text": "text"},
        queries=True,
    ),
    "palmetto_passages": SiteParser(
        _palmetto_passages,
        columns={
            "surface": "text",
            "pets": "text",
            "fees": "text",
            "camping": "text",
            "hunting_grounds": "text",
            "activities": "text",
        },
    ),
    "wi_dnr_hiking": SiteParser(_wi_dnr_hiking, queries=True),
    "mdhta_trails": SiteParser(_mdhta_trails),
    "blue_hills_hikes": SiteParser(_blue_hills_hikes),
    "trustees_hikers_top_ten": SiteParser(_trustees_hikers_top_ten, columns={"rank": "bigint"}),
    "gatc_georgia_4000": SiteParser(_gatc_georgia_4000, columns={"trails": "text"}),
    "amc_four_thousand_footer_lists": SiteParser(
        _amc_four_thousand_footer_lists, columns={"rank": "bigint", "elevation_estimated": "bool", "trail": "text"}
    ),
    "sstc_sweet_16": SiteParser(_sstc_sweet_16),
    "ttc_scavenger_hunt": SiteParser(_ttc_scavenger_hunt),
    "dcnr_geotrail": SiteParser(_dcnr_geotrail, columns={"theme": "text", "accessible": "bool"}),
    "cmc_lookout_towers": SiteParser(_cmc_lookout_towers),
}
