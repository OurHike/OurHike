"""Whether this server may fetch an address a stranger typed, and where to.

See ../../../features/ORG_ONBOARDING.md's "Nominating an organization". The
maintainer decided on 2026-09-17 that the nominate flow really does read a
club's public site rather than letting a model answer from memory, which is
the honest version of what that page already claimed. This module is the
price of that decision paid in one file.

**THIS IS SERVER-SIDE REQUEST FORGERY, DESCRIBED PLAINLY.** A person we do
not know gives us a URL and we open it from inside our own network, with
whatever that network trusts. The reason it is worth doing anyway is that
the alternative shipped a page saying "we read the public site" over an
answer where nothing had been read.

**THE ADDRESS THAT MATTERS IS 169.254.169.254.** On AWS, GCP and Azure it
answers over plain HTTP, with no authentication, with credentials for the
instance asking. Every other rule here is general; this one is specific,
tested by name in tests/test_urlguard.py, and is the single failure that
turns a fetcher into a breach.

**EVERY RESOLVED ADDRESS MUST PASS, NOT THE FIRST ONE.** A name answering
with one public address and one private address is the ordinary shape of a
DNS-rebinding attack: the guard checks, the client re-resolves, and the
second answer is the one that gets connected to. So a mixed answer refuses
the host outright rather than narrowing to the good address - a name that
resolves into somebody's private network is not a club's website, whatever
else it also resolves to.

**AND THE ANSWER CARRIES THE ADDRESSES, because validating a name is not
enough.** Between this check and the socket, DNS can change its mind, and
whoever runs that DNS chooses when. `SafeTarget.addresses` is what
`sitefetch.py` compares the connection's real peer against, after the socket
is open and before a single byte of the body is read. Neither half is
sufficient alone.

**WE DO NOT DECIDE WITH `is_private`.** Measured 2026-09-17 on this
repository's own Pythons, 3.11.15 and 3.13.12 alike:
`ipaddress.ip_address("100.64.0.1").is_private` is **False**. That is RFC 6598
carrier-grade NAT - a hundred million real devices, none of them on the
public internet. `is_global` is False for it and is the predicate used here,
with an explicit table of networks underneath so that a future change in the
standard library's classification cannot quietly widen what we open.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Callable
from urllib.parse import urljoin, urlsplit, urlunsplit

# How many times a site may bounce us before we stop. Three is enough for the
# ordinary chain - apex to www, http to https, a trailing-slash fixup - and
# short enough that a redirect loop costs a moment rather than a timeout.
MAX_REDIRECTS = 3

# Long enough for any real page, short enough that a URL cannot itself be the
# payload. Nothing is resolved before this is checked.
MAX_URL_LENGTH = 2000

# The only port. Not a range, not "443 and 80": an SSRF is worth having
# mostly for what else is listening on the same host, and a guard that reads
# a port from the URL is a guard that will eventually be pointed at 6379.
ALLOWED_PORT = 443

# Names that never resolve on the public internet. Refused on the NAME, before
# DNS is asked, because a split-horizon resolver inside a private network
# answers these with real internal addresses and the answer looks ordinary.
PRIVATE_SUFFIXES = (
    ".local",
    ".localhost",
    ".internal",
    ".intranet",
    ".lan",
    ".home.arpa",
    ".onion",
    ".test",
    ".invalid",
    ".example",
)

# Written out rather than inferred. Every one of these is also caught by
# `is_global` on the Pythons measured above - the table is the belt to that
# braces, so that a standard-library reclassification shows up as a failing
# test rather than as a wider fetcher.
BLOCKED_V4 = tuple(
    ipaddress.ip_network(cidr)
    for cidr in (
        "0.0.0.0/8",  # this network
        "10.0.0.0/8",  # RFC 1918
        "100.64.0.0/10",  # RFC 6598 - the one is_private misses
        "127.0.0.0/8",  # loopback, the whole /8 and not just .0.1
        "169.254.0.0/16",  # link-local, and 169.254.169.254 within it
        "172.16.0.0/12",  # RFC 1918
        "192.0.0.0/24",  # IETF protocol assignments
        "192.0.2.0/24",  # TEST-NET-1
        "192.88.99.0/24",  # deprecated 6to4 relay anycast - is_global says True
        "192.168.0.0/16",  # RFC 1918
        "198.18.0.0/15",  # benchmarking
        "198.51.100.0/24",  # TEST-NET-2
        "203.0.113.0/24",  # TEST-NET-3
        "224.0.0.0/4",  # multicast
        "240.0.0.0/4",  # reserved, and 255.255.255.255 within it
    )
)

BLOCKED_V6 = tuple(
    ipaddress.ip_network(cidr)
    for cidr in (
        "::/128",  # unspecified
        "::1/128",  # loopback
        "64:ff9b::/96",  # NAT64 - unwrapped below as well
        "64:ff9b:1::/48",  # local-use NAT64
        "100::/64",  # discard-only
        "2001::/32",  # Teredo - unwrapped below as well
        "2001:db8::/32",  # documentation
        "2002::/16",  # 6to4 - unwrapped below as well
        "fc00::/7",  # unique local
        "fe80::/10",  # link-local
        "ff00::/8",  # multicast
    )
)

#: Given a hostname, every address it resolves to. Injected so the guard can
#: be tested on what it decides rather than on what DNS says this morning.
Resolver = Callable[[str], "list[str]"]


class UrlRefused(Exception):
    """Why we will not open this, in a sentence meant for the person who typed it.

    Deliberately carries no resolved address. A refusal that prints what a
    name resolved to turns the endpoint into a DNS oracle for whatever
    network this backend sits in - ask it about `db.internal.acme.example`
    and read the answer off the error message.
    """


@dataclass(frozen=True)
class SafeTarget:
    """One address this server has agreed to open, and how it got there."""

    url: str
    host: str
    #: Every address the host resolved to, all of them public. The fetcher
    #: checks the socket's actual peer against this set once connected.
    addresses: tuple[str, ...]
    hops: int = 0
    #: True when the hiker typed `http://` and we read `https://` instead.
    upgraded_from_http: bool = False


def system_resolver(host: str) -> list[str]:
    """Every A and AAAA the system resolver knows for this host."""
    infos = socket.getaddrinfo(host, ALLOWED_PORT, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


def _unwrap(address: ipaddress.IPv6Address) -> list[ipaddress.IPv4Address]:
    """Every IPv4 address hiding inside an IPv6 one.

    Four encodings put a v4 address inside a v6 one, and each is a way of
    writing `127.0.0.1` that does not look like `127.0.0.1`. The stdlib
    classifies most of them correctly today; unwrapping means the v4 table
    above decides, which is the table this file can reason about.
    """
    found: list[ipaddress.IPv4Address] = []
    if address.ipv4_mapped is not None:
        found.append(address.ipv4_mapped)
    if address.sixtofour is not None:
        found.append(address.sixtofour)
    if address.teredo is not None:
        found.extend(address.teredo)
    nat64 = ipaddress.ip_network("64:ff9b::/96")
    if address in nat64:
        found.append(ipaddress.IPv4Address(int(address) & 0xFFFFFFFF))
    return found


def _is_public(raw: str) -> bool:
    """Whether this is an address on the public internet and nothing else."""
    try:
        address = ipaddress.ip_address(raw)
    except ValueError:
        return False

    candidates: list[ipaddress._BaseAddress] = [address]
    if isinstance(address, ipaddress.IPv6Address):
        candidates.extend(_unwrap(address))

    for candidate in candidates:
        if candidate.is_multicast or not candidate.is_global:
            return False
        blocked = BLOCKED_V4 if candidate.version == 4 else BLOCKED_V6
        if any(candidate in network for network in blocked):
            return False
    return True


def _encode_host(host: str) -> str:
    """The name as DNS will be asked for it: lowercased, punycoded, no trailing dot."""
    host = host.strip().rstrip(".")
    if not host:
        raise UrlRefused("That does not have a website address in it.")
    if host.isascii():
        return host.lower()
    try:
        return host.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise UrlRefused(f"We could not read {host!r} as a website address.") from exc


def _check_name(host: str) -> None:
    """Everything decidable from the name alone, before DNS is asked."""
    if "." not in host:
        raise UrlRefused(
            f"{host} is a single name rather than a website address - we only read addresses on the public internet."
        )
    for suffix in PRIVATE_SUFFIXES:
        if host.endswith(suffix):
            raise UrlRefused(f"{host} is a private network name, so there is nothing there we could read.")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise UrlRefused(f"{host} is an address rather than a club's website. Give us the name they publish.")
    last = host.rsplit(".", 1)[-1]
    if not last or not last[0].isalpha() or not all(c.isalnum() or c == "-" for c in last):
        raise UrlRefused(f"{host} does not end in a domain name, so we cannot tell whose website it is.")


def inspect(raw: str, *, resolve: Resolver = system_resolver, hops: int = 0) -> SafeTarget:
    """Decide whether this server may open `raw`, and say no with a reason.

    Raises `UrlRefused` for everything it will not open. It never returns a
    partially-checked target: the only way out with a `SafeTarget` is through
    every rule in this module.
    """
    if not isinstance(raw, str) or not raw.strip():
        raise UrlRefused("We need a website address to read.")
    raw = raw.strip()
    if len(raw) > MAX_URL_LENGTH:
        raise UrlRefused(f"That address is {len(raw)} characters long. A club's website is not that far down.")

    # No scheme at all means a hiker typed what is on the business card.
    if "://" not in raw:
        if raw.split("/", 1)[0].count(":"):
            raise UrlRefused("We only read ordinary web addresses.")
        raw = f"https://{raw}"

    try:
        parts = urlsplit(raw)
    except ValueError as exc:
        raise UrlRefused("We could not read that as a website address.") from exc

    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        raise UrlRefused(f"We only read web pages, and {scheme or 'that'} is not one.")
    upgraded = scheme == "http"

    if "@" in parts.netloc:
        raise UrlRefused("That address carries a sign-in in front of the site name, which we do not follow.")

    try:
        hostname = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise UrlRefused("We could not read the site name in that address.") from exc

    if not hostname:
        raise UrlRefused("That address has no site name in it.")
    if port is not None and port != ALLOWED_PORT:
        raise UrlRefused(f"We only read websites on their ordinary address, and that one names port {port}.")

    host = _encode_host(hostname)
    _check_name(host)

    try:
        addresses = [str(address) for address in resolve(host)]
    except OSError as exc:
        raise UrlRefused(f"We could not find {host} on the internet.") from exc

    if not addresses:
        raise UrlRefused(f"We could not find {host} on the internet.")
    if not all(_is_public(address) for address in addresses):
        # The address itself is deliberately not in this message - see
        # UrlRefused's docstring.
        raise UrlRefused(f"{host} points somewhere inside a private network, so we will not open it.")

    path = parts.path or "/"
    url = urlunsplit(("https", host, path, parts.query, ""))
    return SafeTarget(
        url=url,
        host=host,
        addresses=tuple(addresses),
        hops=hops,
        upgraded_from_http=upgraded,
    )


def follow(previous: SafeTarget, location: str, *, resolve: Resolver = system_resolver) -> SafeTarget:
    """Check a redirect the same way the first address was checked.

    Every hop, not only the first. A guard that inspects what a hiker typed
    and then lets the client follow wherever it is sent has checked the one
    address the attacker did not care about.
    """
    if not isinstance(location, str) or not location.strip():
        raise UrlRefused(f"{previous.host} sent us onward without saying where.")
    if previous.hops + 1 > MAX_REDIRECTS:
        raise UrlRefused(f"{previous.host} sent us through more than {MAX_REDIRECTS} redirects, so we stopped.")
    return inspect(urljoin(previous.url, location.strip()), resolve=resolve, hops=previous.hops + 1)
