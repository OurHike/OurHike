"""Reading a nominated organization's public pages, and stopping in time.

`urlguard.py` decides what may be opened; this decides what happens after it
says yes, and carries the three limits a guard cannot: how many bytes, how
long, and how many pages.

**THE PEER CHECK IS THE HALF THE GUARD CANNOT DO.** The guard resolves a
name and approves the addresses behind it. Between that moment and the
socket, DNS can answer differently - and whoever runs that DNS picks the
moment. So this opens the connection, asks it what it actually reached, and
refuses before reading a byte of the body if the answer is not one the guard
approved. `peer_is_expected` returning False for `None` is the load-bearing
line: a check that passes when it cannot run is not a check.

**AN EGRESS PROXY MAKES THE PEER CHECK IMPOSSIBLE, AND THAT IS A REFUSAL
RATHER THAN A SHRUG.** Through a proxy the socket's peer is the proxy, and
the name is resolved by something we are not asking - so the rebinding
window this check exists to close is wide open and invisible. Deployments
behind one have to say so deliberately; there is no silent degradation.

**WE READ, WE DO NOT CRAWL.** One organization's own site, `MAX_PAGES` of
it, the pages whose links say maps or data or contact. Following outward
would turn one hiker's nomination into a crawl of the web on somebody else's
behalf, which is not a thing this project has any business doing.

**NOTHING WE HOLD LEAVES WITH THE REQUEST.** No cookie, no Authorization
header, no credential of any kind. We are a stranger reading a public page,
and `tests/test_sitefetch.py` keeps it that way across two fetches on a
shared client - a jar picked up on one organization's site and sent to
another's is the kind of leak nobody goes looking for.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Callable
from urllib import robotparser
from urllib.parse import urljoin, urlsplit

import httpx

from app.core.urlguard import Resolver, SafeTarget, UrlRefused, follow, inspect, system_resolver

# A club's home page is tens of kilobytes. A megabyte is generous enough that
# no real page is cut, and small enough that a server streaming forever costs
# a second rather than the process.
MAX_BYTES = 1_000_000

# The home page plus five. Enough for maps, data, contact, about and
# volunteering - the five the nominate flow actually needs - and short of
# anything that reads as a crawl.
MAX_PAGES = 6

# Per request, not per site. A site slower than this is a site we report
# nothing about rather than one we wait for.
TIMEOUT = 10.0

# What we can turn into text. A PDF is deliberately absent: the nominate
# page already tells a hiker we do not take them, because a PDF cannot be
# re-read and is stale the day it is uploaded.
READABLE_TYPES = frozenset(
    {
        "text/html",
        "application/xhtml+xml",
        "text/plain",
        "text/xml",
        "application/xml",
        "application/json",
        "application/ld+json",
        "application/geo+json",
    }
)

# Identifies us and says where to complain, because a webmaster seeing this
# in a log deserves both. The URL is the page that caused the fetch.
USER_AGENT = "OurHikeSiteReader/1.0 (+https://ourhike.org/for-orgs/nominate/)"

# Words in a link, or in the words of a link, that make a page worth the
# second request. Ordered by how much the nominate flow wants them.
WORTH_FOLLOWING = (
    "gis",
    "arcgis",
    "featureserver",
    "geojson",
    "shapefile",
    "data",
    "download",
    "map",
    "trail",
    "contact",
    "volunteer",
    "get-involved",
    "getinvolved",
    "about",
    "staff",
    "board",
    "join",
    "member",
    "donate",
    "support",
)

# Tags whose content is markup rather than words.
_SILENT = frozenset({"script", "style", "noscript", "template", "svg"})

# Tags that separate one thought from the next.
_BLOCK = frozenset(
    {
        "p",
        "div",
        "br",
        "li",
        "tr",
        "section",
        "article",
        "header",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "td",
        "th",
        "nav",
        "aside",
        "main",
    }
)

# THE LOOKBEHIND AND THE BOUNDS ARE THE WHOLE POINT, not tidiness. The first
# version of this pattern was `[A-Za-z0-9._%+-]+@...`, which starts a match at
# every character of a run and consumes the whole run before failing on the
# missing `@` - quadratic in the length of the page. A megabyte of one
# repeated letter, which is exactly what MAX_BYTES lets through, took longer
# than the test suite's timeout. The lookbehind means a run can only be
# entered at its first character, and the bounds cap what one attempt costs:
# 64 is RFC 5321's local-part limit, 255 the domain's.
_EMAIL = re.compile(r"(?<![A-Za-z0-9._%+\-])[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]{1,63}(?:\.[A-Za-z0-9\-]{1,63}){1,8}")
_WHITESPACE = re.compile(r"\s+")


class FetchRefused(Exception):
    """We opened it, or tried to, and are not going to report what was there."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(frozen=True)
class Link:
    """One anchor: where it points, and the words somebody wrote on it.

    The words are half the value. `mailto:maps@cmc.example` labelled
    "Priya Raghavan" is the only place a club's site says whose address that
    is, and the contacts step has nowhere else to learn it.
    """

    href: str
    text: str


@dataclass(frozen=True)
class Page:
    """One page, as much of it as we read, in the shape a model can use."""

    url: str
    title: str
    text: str
    links: tuple[Link, ...]
    emails: tuple[str, ...]
    truncated: bool = False


#: Given an open response, the address it actually reached. Injected so the
#: fetcher's decisions can be tested without a socket.
PeerReader = Callable[[httpx.Response], "str | None"]


def reader(*, trust_env: bool = False) -> httpx.Client:
    """The client this module is meant to be driven with.

    **`trust_env` IS FALSE BY DEFAULT AND THAT IS A SECURITY DECISION, not a
    convenience.** With it on, httpx picks up `HTTPS_PROXY` from the
    environment and hands the URL to the proxy - which then resolves the
    hostname itself. Every address decision `urlguard.py` made is discarded at
    that moment, and the peer this module checks becomes the proxy rather than
    the site. A deployment that genuinely must egress through a proxy turns
    this on and turns `site_fetch_require_peer_match` off, and knows it has
    traded away the rebinding guarantee.

    Redirects are not followed by the client, because `read_page` follows them
    itself through `urlguard.follow` - a client that followed them would check
    the first address and open the rest.
    """
    return httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=False,
        trust_env=trust_env,
        headers={"user-agent": USER_AGENT},
    )


def peer_unchecked(response: httpx.Response) -> str | None:
    """Deliberately reports the peer as unknown, which `read_page` refuses.

    Here so that the name appears in a grep for what turns the check off, and
    so that turning it off cannot be done by passing `None` and hoping. It is
    not a bypass: `peer_is_expected` treats an unknown peer as a failure, so
    this makes the fetcher refuse rather than proceed unchecked.
    """
    return None


def peer_from_response(response: httpx.Response) -> str | None:
    """What this connection really reached, or None when we cannot tell.

    None is a real answer and the common one behind an egress proxy. It is
    handled as a refusal upstream rather than as a missing value.
    """
    stream = response.extensions.get("network_stream")
    if stream is None:
        return None
    try:
        address = stream.get_extra_info("server_addr")
    except Exception:  # pragma: no cover - transport-specific
        return None
    if not address:
        return None
    if isinstance(address, (tuple, list)):
        return str(address[0]) if address else None
    return str(address)


def _as_address(raw: str | None):
    """One address, however the socket layer spelled it."""
    import ipaddress

    if not raw:
        return None
    text = str(raw).split("%", 1)[0].strip().strip("[]")
    try:
        address = ipaddress.ip_address(text)
    except ValueError:
        return None
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        return address.ipv4_mapped
    return address


def peer_is_expected(target: SafeTarget, peer: str | None) -> bool:
    """Whether the connection reached one of the addresses the guard approved.

    Compared as addresses rather than as strings, because a dual-stack socket
    reports a v4 peer as `::ffff:8.8.8.8` and a string compare would refuse
    every such fetch while looking like it was working.
    """
    reached = _as_address(peer)
    if reached is None:
        return False
    approved = {_as_address(address) for address in target.addresses}
    approved.discard(None)
    return reached in approved


class _Reader(HTMLParser):
    """Words, links and addresses out of whatever markup a club's site has.

    `convert_charrefs` is the default and is what decodes `&amp;`. Broken
    markup does not raise: HTMLParser is forgiving by design, which is the
    property that matters for pages nobody validates.
    """

    def __init__(self, base: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base = base
        self.chunks: list[str] = []
        self.links: list[Link] = []
        self._silent = 0
        self._href: str | None = None
        self._anchor: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SILENT:
            self._silent += 1
            return
        if tag in _BLOCK:
            self.chunks.append("\n")
        if tag == "a":
            href = dict(attrs).get("href")
            self._href = href.strip() if href else None
            self._anchor = []
        if tag == "title":
            self.chunks.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _SILENT:
            self._silent = max(0, self._silent - 1)
            return
        if tag in _BLOCK:
            self.chunks.append("\n")
        if tag == "a":
            if self._href:
                words = _WHITESPACE.sub(" ", "".join(self._anchor)).strip()
                self.links.append(Link(href=_absolute(self.base, self._href), text=words))
            self._href = None
            self._anchor = []

    def handle_data(self, data: str) -> None:
        if self._silent:
            return
        # Collapsed here rather than at the end, because the newlines inside
        # one paragraph's source are layout and the ones between blocks are
        # meaning, and after joining nothing can tell them apart.
        text = _WHITESPACE.sub(" ", data)
        if text.strip():
            self.chunks.append(text)
            if self._href is not None:
                self._anchor.append(text)


def _absolute(base: str, href: str) -> str:
    """A link as an address, unless it is a scheme that has no address."""
    if href.lower().startswith(("mailto:", "tel:", "javascript:", "data:")):
        return href
    return urljoin(base, href)


def _title_of(markup: str) -> str:
    found = re.search(r"<title[^>]*>(.*?)</title>", markup, re.IGNORECASE | re.DOTALL)
    if not found:
        return ""
    import html as html_module

    return _WHITESPACE.sub(" ", html_module.unescape(found.group(1))).strip()


def extract(url: str, body: str, *, markup: bool = True) -> Page:
    """One page's words, links and addresses, from its source.

    Separated from the fetching so it can be tested on markup rather than on
    a network, and so a page cached anywhere else can be read the same way.
    """
    if not markup:
        # LINES SURVIVE IN PLAIN TEXT, and collapsing them was a real defect:
        # robots.txt is line-oriented, so a `Disallow:` folded onto the
        # `User-agent:` line above it parses as no rules at all and the whole
        # site reads as open. Runs of spaces and tabs still collapse; the
        # newline is the only whitespace carrying meaning here.
        text = "\n".join(re.sub(r"[ \t\f\v]+", " ", line).strip() for line in body.replace("\r\n", "\n").split("\n")).strip()
        return Page(
            url=url,
            title="",
            text=text,
            links=(),
            emails=_addresses_in(text, ()),
        )

    reader = _Reader(url)
    reader.feed(body)
    reader.close()
    text = "".join(reader.chunks)
    text = re.sub(r" *\n[ \n]*", "\n", text).strip()
    return Page(
        url=url,
        title=_title_of(body),
        text=text,
        links=tuple(reader.links),
        emails=_addresses_in(text, tuple(reader.links)),
    )


def _addresses_in(text: str, links: tuple[Link, ...]) -> tuple[str, ...]:
    """Every address on the page, each once, linked ones first.

    Both spellings matter: half a club's contact page links `mailto:` and the
    other half writes the address out in a sentence.
    """
    found: list[str] = []
    for link in links:
        if link.href.lower().startswith("mailto:"):
            address = link.href[7:].split("?", 1)[0].strip()
            if address and address.lower() not in {a.lower() for a in found}:
                found.append(address)
    for match in _EMAIL.finditer(text):
        address = match.group(0)
        if address.lower() not in {a.lower() for a in found}:
            found.append(address)
    return tuple(found)


def _read_body(response: httpx.Response) -> tuple[str, bool]:
    """The body, capped, with whether we stopped early.

    The cap is enforced while reading and not only against Content-Length,
    because Content-Length is the server's claim rather than a fact, and a
    server that says ten bytes and sends forever is what the cap is for.
    """
    collected = bytearray()
    truncated = False
    for chunk in response.iter_bytes():
        collected.extend(chunk)
        if len(collected) >= MAX_BYTES:
            del collected[MAX_BYTES:]
            truncated = True
            break
    encoding = response.encoding or "utf-8"
    try:
        return collected.decode(encoding, errors="replace"), truncated
    except LookupError:
        return collected.decode("utf-8", errors="replace"), truncated


def read_page(
    where: str | SafeTarget,
    *,
    client: httpx.Client,
    resolve: Resolver = system_resolver,
    read_peer: PeerReader = peer_from_response,
    obey_robots: bool = False,
    _robots: robotparser.RobotFileParser | None = None,
) -> Page:
    """Open one page, through every check, and come back with its words.

    Raises `UrlRefused` for an address we will not open and `FetchRefused`
    for one we opened and will not report. Two exceptions rather than one
    because the first is the hiker's to fix by typing a different address and
    the second is not.
    """
    target = inspect(where, resolve=resolve) if isinstance(where, str) else where

    if obey_robots or _robots is not None:
        rules = _robots if _robots is not None else _robots_for(target, client=client, resolve=resolve, read_peer=read_peer)
        if rules is not None and not rules.can_fetch(USER_AGENT, target.url):
            raise FetchRefused(f"{target.host} asks robots not to read {urlsplit(target.url).path}.")

    while True:
        request = httpx.Request(
            "GET",
            target.url,
            headers={
                "user-agent": USER_AGENT,
                "accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.1",
                "accept-language": "en",
            },
        )
        try:
            response = client.send(request, stream=True, follow_redirects=False)
        except httpx.HTTPError as exc:
            raise FetchRefused(f"We could not reach {target.host}.") from exc

        # Before the body. Every hop, not only the first: a chain whose first
        # host is real and whose second has rebound is the shape this catches.
        if not peer_is_expected(target, read_peer(response)):
            response.close()
            raise FetchRefused(
                f"The connection to {target.host} did not reach the address it resolved to, so we stopped without reading it."
            )

        if response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("location", "")
            response.close()
            target = follow(target, location, resolve=resolve)
            continue

        if response.status_code >= 400:
            status = response.status_code
            response.close()
            raise FetchRefused(f"{target.host} answered {status}.", status=status)

        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type not in READABLE_TYPES:
            response.close()
            raise FetchRefused(f"{target.host} sent {content_type or 'something with no type'}, which we cannot read.")

        declared = response.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_BYTES:
            response.close()
            raise FetchRefused(f"{target.host} offered {declared} bytes, which is more than we read.")

        try:
            body, truncated = _read_body(response)
        except httpx.HTTPError as exc:
            raise FetchRefused(f"We lost the connection to {target.host}.") from exc
        finally:
            response.close()
            # A shared client must not accumulate a jar. See the module
            # header: a cookie picked up on one organization's site has no
            # business reaching another's.
            client.cookies.clear()

        markup = content_type in ("text/html", "application/xhtml+xml")
        page = extract(target.url, body, markup=markup)
        return Page(
            url=page.url,
            title=page.title,
            text=page.text,
            links=page.links,
            emails=page.emails,
            truncated=truncated,
        )


def _robots_for(
    target: SafeTarget,
    *,
    client: httpx.Client,
    resolve: Resolver,
    read_peer: PeerReader,
) -> robotparser.RobotFileParser | None:
    """What this host's robots.txt permits, read once per site.

    RFC 9309's two answers, both of them deliberate: a 4xx means there are no
    rules and the site is open, and a 5xx means the site is closed. A server
    too broken to say whether we may read it has not said we may.
    """
    parser = robotparser.RobotFileParser()
    try:
        page = read_page(
            f"https://{target.host}/robots.txt",
            client=client,
            resolve=resolve,
            read_peer=read_peer,
            obey_robots=False,
        )
    except FetchRefused as exc:
        if exc.status is not None and 500 <= exc.status < 600:
            raise FetchRefused(f"{target.host} could not tell us whether we may read it, so we did not.") from exc
        return None
    except UrlRefused:
        return None
    parser.parse(page.text.splitlines())
    return parser


def _same_site(base_host: str, candidate: str) -> bool:
    """Whether a link stays on the organization's own site.

    Subdomains of the host we were given count - a club's maps often live on
    `gis.` or `data.` - and nothing else does.

    **The root is the nominated host with a leading `www.` removed, and no
    more of it than that.** Taking the last two labels instead, which this
    did until the review of #1547, makes the root of `ramblers.org.uk` into
    `org.uk`: every UK charity is then "the organization's own site", and
    one nomination becomes a crawl that reads and harvests addresses from
    organizations nobody nominated. The same hole is open under `.co.uk`,
    `.com.au`, `.gov.uk` and every other two-label suffix.

    @unvalidated that stripping `www.` is the only widening worth making.
    It is the one alias common enough to be worth the line, but no public
    suffix list is consulted here, so an org whose pages sit under a
    different second host (`cmc.org` linking `cmcfoundation.org`) has those
    links passed over. That is the safe direction to be wrong in - a page
    not read costs a nomination some coverage, a page wrongly read costs
    somebody else their inbox - and what would settle it is a count of how
    often real nominations link a genuine sibling host, which nobody has.
    """
    try:
        host = (urlsplit(candidate).hostname or "").lower()
    except ValueError:
        return False
    if not host:
        return False
    root = base_host[len("www.") :] if base_host.startswith("www.") else base_host
    return host == base_host or host == root or host.endswith("." + root)


def _worth_following(link: Link) -> int:
    """How much a link's own words say it leads somewhere useful.

    Zero means do not follow. A number rather than a boolean so a home page
    with forty links spends its budget on the maps page rather than the first
    five in the markup.
    """
    haystack = f"{link.href.lower()} {link.text.lower()}"
    return sum(1 for word in WORTH_FOLLOWING if word in haystack)


def read_site(
    url: str,
    *,
    client: httpx.Client,
    resolve: Resolver = system_resolver,
    read_peer: PeerReader = peer_from_response,
    obey_robots: bool = True,
    max_pages: int = MAX_PAGES,
) -> tuple[Page, ...]:
    """The home page, and up to `max_pages - 1` of its most promising links.

    A page that refuses does not lose the others - one 500 on a contact page
    is not a reason to report nothing about an organization. The home page is
    the exception: if we could not read that, we have nothing to report and
    say so rather than returning an empty success.
    """
    home_target = inspect(url, resolve=resolve)
    rules = _robots_for(home_target, client=client, resolve=resolve, read_peer=read_peer) if obey_robots else None

    home = read_page(home_target, client=client, resolve=resolve, read_peer=read_peer, _robots=rules)
    pages = [home]
    seen = {(home_target.host, urlsplit(home.url).path.rstrip("/") or "/")}

    candidates = sorted(
        (link for link in home.links if _worth_following(link) and _same_site(home_target.host, link.href)),
        key=_worth_following,
        reverse=True,
    )
    for link in candidates:
        if len(pages) >= max_pages:
            break
        parts = urlsplit(link.href)
        key = ((parts.hostname or "").lower(), parts.path.rstrip("/") or "/")
        if key in seen:
            continue
        seen.add(key)
        try:
            pages.append(read_page(link.href, client=client, resolve=resolve, read_peer=read_peer, _robots=rules))
        except (FetchRefused, UrlRefused):
            continue
    return tuple(pages)
