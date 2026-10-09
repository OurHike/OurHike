"""robots.txt, read once per host a run, and obeyed by every request the extract sends.

THE RULE is the dlt skill's, "Terms are never routed around": robots.txt is
never routed around, and a robots refusal is UNKNOWN. Before this module the
extract kept it by hand. extract/_notices.py's QUERY_DISALLOWED_HOSTS lists
two hosts whose robots.txt forbids a query string, and each sources.json
row's `crawl_delay` holds the Crawl-delay somebody read when the row was
registered; only extract/_geofabrik.py read robots.txt as it ran (review of
PR #1805 — dlt → dbt re-platform as one go/no-go change, finding 2). A host
that added a Disallow, or lengthened its Crawl-delay, after its row was
registered was not obeyed.

So extract/_kinds.py's session(), which every reader's requests pass
through, reads an origin's robots.txt (scheme, host and port: RFC 9309,
section 2.3) the first time a run asks that origin anything, under
lib/user_agent.py's USER_AGENT, and keeps it for the run: extract/_run.py's
run_pipeline() calls forget() as each run starts. Then, for every request:
- A URL the rules disallow for our agent raises RobotsRefused, and nothing
  is sent. The URL checked is the one requests will send, `params` included,
  so `Disallow: /*?` refuses a query built from them. RobotsRefused is a
  requests RequestException, so a change check reads it as UNKNOWN, and a
  NoticeUnreadable, so the notice readers refuse it as they refuse a wall;
  the read raises it, and the run leaves the resource out with its last
  committed rows standing (extract/_run.py's read_each()). Nothing is
  emptied.
- The host's Crawl-delay is kept between requests to it, end to start, the
  robots.txt fetch counted as one: extract/_notices.py's polite() keeps the
  larger of it and the gap its caller asked for (the registry's
  `crawl_delay`), and a session nobody made polite keeps the robots.txt's
  own, through the same per-host gate. Counting the fetch costs a run one
  more Crawl-delay per host that asks one: 60 s at most among the delays
  sources.json and the club files hold (bmta's, wta's and tta's hosts;
  Reasoned from those numbers, 2026-10-09).
- /robots.txt itself is always allowed (RFC 9309, section 2.2.2).
A redirect that requests follows inside one request is not checked again:
it is the host's own answer, and one to another host is refused anyway
(extract/_notices.py's refuse_other_hosts()).

WHAT AN ANSWER MEANS is what extract/_geofabrik.py chose before it read
through this module (RFC 9309, section 2.3.1): a 2xx is the rules; a 4xx
other than 429 is no rules at all; a 5xx, a 429 or no answer, after
lib/http_retry.py's retries, is a host that cannot be read, which disallows
every URL on it for the rest of the run. So an unreachable robots.txt never
stops a run: that one host's resources are UNKNOWN and left out with their
last rows, and every other host is read. `arcgisserver.digital.mass.gov`'s
robots.txt answered 502 twice on 2026-10-03 (pipeline/ELT.md), which would
leave MassGIS's layers out of any run where that recurs.

THE MATCHING IS RFC 9309's, written here rather than taken from
urllib.robotparser, whose answer depends on the interpreter. Measured
2026-10-09 in this sandbox: under `Disallow: /*?`, CPython 3.12.3 allowed
`/page?x=1` and 3.13.14 refused it; under `Disallow: /` then
`Allow: /api/`, 3.12.3 refused `/api/x` (the first rule wins) and 3.13.14
allowed it (the longest rule wins). The extract jobs run on Python 3.12
(their setup-python steps) and the tests on 3.13 and 3.14, so with a 3.12
like this one the stdlib would pass the tests and ignore every wildcard in
production; which 3.12 setup-python installs, and whether it has the newer
parser, was not checked. Here: `*`
matches any run of characters and a final `$` the end of the URL; the
longest matching rule wins, and an Allow wins a tie; an empty Disallow is
no rule. The group obeyed is the one naming our product token,
`OurHike-pipeline`, most closely, matched without case: the token itself,
else a hyphen-ended prefix of it such as `OurHike`, since a site writing
rules for `OurHike` means this project; groups naming it equally closely
are merged, and with none the `*` group is obeyed. RFC 9309 asks for the
token itself; taking the prefix too obeys more groups, never fewer. No
robots.txt that earlier sessions here read names either: two reads, of 56
hosts on 2026-10-04 and of 25 on 2026-10-03, some hosts in both, searched
2026-10-09 (Measured); the registry's resources ask 147 hosts.

ONE RULING OVERRIDES A DISALLOW (RULED_HOSTS): decision 85, the maintainer's
poll of 2026-10-05, for api.weather.gov, whose robots.txt reads
`User-agent: *` / `Disallow: /` while NWS documents the API for applications.
Its robots.txt is still read, and a Crawl-delay it ever asks is still kept.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from urllib.parse import quote, urlsplit

import requests

from extract._notices import NoticeUnreadable, _held, _site, mark_gate_used
from lib.http_retry import request_with_retry
from lib.user_agent import USER_AGENT

#: Our product token, USER_AGENT before its first "/", `OurHike-pipeline`: the name a robots.txt group addresses (RFC
#: 9309, section 2.2.1), and one a group may also address by its hyphen-ended prefix `OurHike` (_naming()).
PRODUCT_TOKEN = USER_AGENT.split("/", 1)[0]

#: The most of a robots.txt that is read. RFC 9309, section 2.5, asks a crawler to parse at least 500 kibibytes.
MAX_BYTES = 500 * 1024

#: Hosts whose robots.txt Disallow the maintainer has ruled on, each with the ruling (the module docstring).
RULED_HOSTS = {
    "api.weather.gov": (
        "decision 85, the maintainer's poll of 2026-10-05: NWS documents the API for application clients, so the "
        "host-wide `Disallow: /` is read as aimed at crawlers of the host"
    ),
}

#: The characters RFC 3986 leaves unreserved: a percent-escape of one is decoded before rules and URLs are compared.
_UNRESERVED = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
#: Every printable ASCII character but the space: kept as written when a rule or a URL is percent-encoded.
_PRINTABLE = "".join(chr(code) for code in range(0x21, 0x7F))


class RobotsRefused(NoticeUnreadable, requests.RequestException):
    """A request robots.txt disallows for our agent, refused before it was sent: UNKNOWN, never an empty answer."""

    def __init__(self, message: str):
        requests.RequestException.__init__(self, message)


def _normalized(path: str) -> str:
    """`path` with every character outside printable ASCII percent-encoded, and each escape of an unreserved character
    decoded and every other escape's hex upper-cased, so a rule and a URL compare octet for octet (RFC 9309, 2.2.2)."""

    def escape(match: re.Match) -> str:
        character = chr(int(match.group(1), 16))
        return character if character in _UNRESERVED else f"%{match.group(1).upper()}"

    return re.sub(r"%([0-9A-Fa-f]{2})", escape, quote(path, safe=_PRINTABLE))


@dataclass(frozen=True)
class Rule:
    """One Allow or Disallow line of the group our agent obeys: its path pattern, normalized, and that as a regex."""

    allow: bool
    pattern: str
    regex: re.Pattern

    @classmethod
    def of(cls, allow: bool, value: str) -> Rule:
        pattern = _normalized(value)
        anchored = pattern.endswith("$")
        body = pattern[:-1] if anchored else pattern
        regex = ".*".join(re.escape(part) for part in body.split("*")) + (r"\Z" if anchored else "")
        return cls(allow, pattern, re.compile(regex, re.DOTALL))


@dataclass(frozen=True)
class Robots:
    """One origin's robots.txt as this run read it: the rules our agent obeys, its Crawl-delay, what was read, whether
    it disallows everything (a robots.txt that could not be read), and whether a request was sent for it."""

    rules: tuple[Rule, ...] = ()
    delay: float = 0.0
    said: str = ""
    refuses_all: bool = False
    asked: bool = False

    def allows(self, url: str) -> bool:
        """Whether our agent may ask for `url`: the longest matching rule decides, an Allow winning a tie."""
        target = _target(url)
        if target == "/robots.txt":
            return True
        if self.refuses_all:
            return False
        best = None
        for rule in self.rules:
            if rule.regex.match(target):
                key = (len(rule.pattern), rule.allow)
                best = key if best is None or key > best else best
        return True if best is None else best[1]


def _target(url: str) -> str:
    """The part of `url` a rule is matched against: its path, `/` when empty, and its query, normalized."""
    parts = urlsplit(url)
    return _normalized((parts.path or "/") + (f"?{parts.query}" if parts.query else ""))


def _naming(agent: str, token: str) -> int | None:
    """How closely a group's user-agent value names our product token: the length of the name when it is the token or
    a hyphen-ended prefix of it (`OurHike` names `OurHike-pipeline`), matched without case and whatever version or
    comment follows it; None when it names another agent."""
    named = agent.strip().split("/", 1)[0].split()
    if not named:
        return None
    name, ours = named[0].lower(), token.lower()
    return len(name) if name == ours or ours.startswith(f"{name}-") else None


def parse(text: str, token: str = PRODUCT_TOKEN) -> tuple[tuple[Rule, ...], float]:
    """(the rules our agent obeys, its Crawl-delay) from a robots.txt's text (the module docstring, "THE MATCHING")."""
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    lines: list[tuple[str, str]] = []
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        key = key.lower()
        if key == "user-agent":
            if lines:  # a user-agent line after rules starts the next group
                groups.append((agents, lines))
                agents, lines = [], []
            agents.append(value)
        elif key in ("allow", "disallow", "crawl-delay") and agents:
            lines.append((key, value))
    if agents:
        groups.append((agents, lines))
    closeness = [max((_naming(agent, token) or 0 for agent in agents), default=0) for agents, _ in groups]
    closest = max(closeness, default=0)
    ours = [lines for (_, lines), close in zip(groups, closeness, strict=True) if closest and close == closest]
    chosen = ours or [lines for agents, lines in groups if any(agent.strip() == "*" for agent in agents)]
    rules, delays = [], []
    for lines in chosen:
        for key, value in lines:
            if key == "crawl-delay":
                try:
                    delays.append(float(value))
                except ValueError:
                    continue
            elif value:  # an empty Allow or Disallow is no rule
                rules.append(Rule.of(key == "allow", value))
    return tuple(rules), max((delay for delay in delays if delay >= 0), default=0.0)


def read_from_host(origin: str) -> Robots:
    """`<origin>/robots.txt`, asked once under USER_AGENT through lib/http_retry.py's retries, as RFC 9309's
    statuses read it (the module docstring, "WHAT AN ANSWER MEANS")."""
    url = f"{origin}/robots.txt"
    http = requests.Session()
    http.headers["User-Agent"] = USER_AGENT
    try:
        response = request_with_retry(url, session=http, timeout=60, label="robots.txt")
    except requests.HTTPError as error:
        status = error.response.status_code if error.response is not None else None
        if status is not None and 400 <= status < 500 and status != 429:
            return Robots(said=f"{url} answered {status}: no rules", asked=True)
        return Robots(said=f"{url} answered {status}, read as disallowing every URL", refuses_all=True, asked=True)
    except requests.RequestException as error:
        said = f"{url} gave no answer ({type(error).__name__}), read as disallowing every URL"
        return Robots(said=said, refuses_all=True, asked=True)
    rules, delay = parse(response.content[:MAX_BYTES].decode("utf-8", errors="replace"))
    shown = f"{delay:g} s" if delay else "none"
    return Robots(rules, delay, f"{url} read ({len(response.content)} bytes, Crawl-delay {shown})", asked=True)


def no_rules(origin: str) -> Robots:
    """What fixture mode and the tests answer for every origin unless a test is about robots.txt: no rules, no request."""
    return Robots(said=f"{origin}/robots.txt not read: no host is asked here")


#: What robots_for() calls for an origin it has not read this run. read_from_host() in a real run; extract/_fixtures.py
#: and tests/conftest.py put no_rules() here, as fixture mode sets each host's Crawl-delay to 0.
read_robots_txt = read_from_host

_READ: dict[str, Robots] = {}
_READING: dict[str, threading.Lock] = {}
_LOCK = threading.Lock()


def forget() -> None:
    """Start a new run: each origin's robots.txt is read again the next time the run asks that origin anything."""
    with _LOCK:
        _READ.clear()
        _READING.clear()


def _origin(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}"


def robots_for(url: str) -> Robots:
    """`url`'s origin's robots.txt as this run reads it: read the first time, by one thread, and kept for the run."""
    origin = _origin(url)
    with _LOCK:
        if origin in _READ:
            return _READ[origin]
        reading = _READING.setdefault(origin, threading.Lock())
    with reading:
        with _LOCK:
            if origin in _READ:
                return _READ[origin]
        robots = read_robots_txt(origin)
        if robots.asked:
            # The fetch was a request to the host, so its Crawl-delay counts from it (the module docstring).
            mark_gate_used(_site(urlsplit(url).hostname))
        with _LOCK:
            _READ[origin] = robots
        return robots


def sent_url(method: str, url: str, params=None) -> str:
    """The URL requests will send for `url` and `params`, the query it builds included; `url` itself if it cannot say."""
    if not params:
        return url
    try:
        return requests.Request(method.upper(), url, params=params).prepare().url or url
    except (requests.RequestException, ValueError, TypeError):
        return url


def check(method: str, url: str, params=None) -> Robots:
    """The robots.txt `url`'s origin answers this run; RobotsRefused when it disallows the URL requests will send."""
    target = sent_url(method, url, params)
    robots = robots_for(target)
    if not robots.allows(target) and _site(urlsplit(target).hostname) not in RULED_HOSTS:
        raise RobotsRefused(f"{target} is disallowed for {PRODUCT_TOKEN} by {robots.said}; not asked")
    return robots


def obey(http: requests.Session) -> requests.Session:
    """`http`, every request it sends checked against its origin's robots.txt first, and held to that host's
    Crawl-delay through extract/_notices.py's per-host gate when robots.txt asks one. A session that polite() also
    holds is gated there, at the larger of the two delays, and this gate, inside that one, sends at once (_held())."""
    send = http.request

    def request(method, url, *args, **kwargs):
        if urlsplit(url).path == "/robots.txt":
            return send(method, url, *args, **kwargs)
        robots = check(method, url, kwargs.get("params"))
        if robots.delay <= 0:
            return send(method, url, *args, **kwargs)
        return _held(_site(urlsplit(url).hostname), robots.delay, lambda: send(method, url, *args, **kwargs))

    http.request = request
    return http
