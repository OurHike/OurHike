"""What the server may and may not fetch, decided before anything is opened.

`app/core/urlguard.py` is the whole of the maintainer's 2026-09-17 decision
on the nominate flow: a hiker types an organization's website and this
backend goes and reads it. That is a server fetching an address a stranger
supplied, which is server-side request forgery in its plainest form, and the
guard is the thing standing between it and every service that trusts its own
network.

**The case that has to be named is `169.254.169.254`.** On AWS, GCP and
Azure that address answers with the instance's own credentials over plain
HTTP with no authentication. A fetcher that follows a hiker's URL to it
hands out the keys to the account. It is in this file by name rather than
only by range, because a range is a thing a future edit can loosen without
noticing what it let through.

Every refusal here is a test that goes red if the guard ever starts saying
yes. None of them reach the network: the resolver is injected, because the
point is what the guard decides given an answer, not what DNS says today.
"""

import pytest

from app.core.urlguard import (
    MAX_REDIRECTS,
    SafeTarget,
    UrlRefused,
    follow,
    inspect,
)


def fixed(*addresses: str):
    """A resolver that answers the same way every time, for every host."""

    def resolve(host: str) -> list[str]:
        return list(addresses)

    return resolve


def refusing(exc: Exception):
    def resolve(host: str) -> list[str]:
        raise exc

    return resolve


# One public address that is genuinely globally routable, so the "this is
# fine" tests are not quietly passing for the wrong reason. 8.8.8.8 is
# Google's resolver and is as public as an address gets.
OK = fixed("8.8.8.8")


class TestTheShapeOfTheUrl:
    def test_a_plain_public_https_url_is_accepted(self):
        target = inspect("https://carolinamountainclub.org/", resolve=OK)
        assert isinstance(target, SafeTarget)
        assert target.host == "carolinamountainclub.org"
        assert target.url.startswith("https://")
        assert target.addresses == ("8.8.8.8",)

    def test_an_http_url_is_retried_as_https_rather_than_refused(self):
        """A hiker types what is on the club's business card, not a scheme.

        Upgrading is friendlier than refusing and is not a security
        relaxation: the fetch that follows is https either way.
        """
        target = inspect("http://carolinamountainclub.org/maps", resolve=OK)
        assert target.url == "https://carolinamountainclub.org/maps"
        assert target.upgraded_from_http is True

    def test_a_bare_hostname_is_read_as_https(self):
        target = inspect("carolinamountainclub.org", resolve=OK)
        assert target.url == "https://carolinamountainclub.org/"

    @pytest.mark.parametrize(
        "raw",
        [
            "file:///etc/passwd",
            "ftp://example.org/pub",
            "gopher://example.org:70/1",
            "data:text/html,<h1>hi",
            "javascript:alert(1)",
            "jar:https://example.org/a.zip!/b",
            "blob:https://example.org/uuid",
            "ws://example.org/socket",
        ],
    )
    def test_only_the_web_schemes_are_read(self, raw):
        with pytest.raises(UrlRefused):
            inspect(raw, resolve=OK)

    def test_a_url_carrying_credentials_is_refused(self):
        """`https://user:pass@host/` is both a credential and a confusion trick.

        The trick half matters more: a reader skimming
        `https://carolinamountainclub.org@evil.example/` sees the club.
        """
        with pytest.raises(UrlRefused):
            inspect("https://someone:secret@carolinamountainclub.org/", resolve=OK)

    def test_a_url_whose_userinfo_impersonates_a_host_is_refused(self):
        with pytest.raises(UrlRefused):
            inspect("https://carolinamountainclub.org@evil.example/", resolve=OK)

    @pytest.mark.parametrize("port", [80, 8080, 8443, 22, 3306, 6379, 9200, 11211])
    def test_a_port_other_than_443_is_refused(self, port):
        """Port sweeping is most of what an SSRF is worth to somebody.

        443 only, so the guard cannot be pointed at a database, a cache or an
        admin panel that happens to be listening on the same host.
        """
        with pytest.raises(UrlRefused):
            inspect(f"https://carolinamountainclub.org:{port}/", resolve=OK)

    def test_port_443_written_out_is_accepted(self):
        target = inspect("https://carolinamountainclub.org:443/", resolve=OK)
        assert target.host == "carolinamountainclub.org"

    def test_a_single_label_host_is_refused(self):
        """`https://intranet/` is not an organization's website."""
        with pytest.raises(UrlRefused):
            inspect("https://intranet/", resolve=OK)

    @pytest.mark.parametrize(
        "host",
        [
            "wiki.local",
            "files.internal",
            "db.localhost",
            "printer.home.arpa",
            "market.onion",
            "service.intranet",
            "box.lan",
        ],
    )
    def test_the_private_suffixes_are_refused_before_dns_is_asked(self, host):
        """These never resolve publicly, so a resolver that answers is lying.

        Refused on the name rather than the address, because a split-horizon
        resolver inside somebody's network answers these with real internal
        addresses and the answer would look ordinary.
        """
        with pytest.raises(UrlRefused):
            inspect(f"https://{host}/", resolve=fixed("8.8.8.8"))

    @pytest.mark.parametrize("host", ["8.8.8.8", "[2606:4700:4700::1111]", "0x7f000001", "2130706433"])
    def test_an_address_literal_is_refused_even_when_it_is_public(self, host):
        """A club's website has a name. A literal is somebody probing.

        The decimal and hex spellings are here because they are the two that
        read as ordinary text and resolve to 127.0.0.1.
        """
        with pytest.raises(UrlRefused):
            inspect(f"https://{host}/", resolve=OK)

    def test_a_host_with_a_trailing_dot_is_normalised(self):
        target = inspect("https://carolinamountainclub.org./", resolve=OK)
        assert target.host == "carolinamountainclub.org"

    def test_the_host_is_lowercased(self):
        target = inspect("https://CarolinaMountainClub.ORG/", resolve=OK)
        assert target.host == "carolinamountainclub.org"

    def test_an_internationalised_host_is_punycoded_before_it_is_resolved(self):
        asked: list[str] = []

        def resolve(host: str) -> list[str]:
            asked.append(host)
            return ["8.8.8.8"]

        target = inspect("https://klätterklubben.se/", resolve=resolve)
        assert asked == ["xn--kltterklubben-cfb.se"]
        assert target.host == "xn--kltterklubben-cfb.se"

    def test_an_absurdly_long_url_is_refused_without_being_resolved(self):
        asked: list[str] = []

        def resolve(host: str) -> list[str]:
            asked.append(host)
            return ["8.8.8.8"]

        with pytest.raises(UrlRefused):
            inspect("https://a.example/" + "x" * 4000, resolve=resolve)
        assert asked == []

    def test_a_fragment_is_dropped(self):
        """It never reaches a server, so carrying it would only mislead a log."""
        target = inspect("https://carolinamountainclub.org/maps#trails", resolve=OK)
        assert "#" not in target.url

    @pytest.mark.parametrize("raw", ["", "   ", "https://", "https:///path", "::::"])
    def test_nonsense_is_refused_rather_than_raising_something_else(self, raw):
        with pytest.raises(UrlRefused):
            inspect(raw, resolve=OK)


class TestWhereItMayNotConnect:
    @pytest.mark.parametrize(
        "address,what",
        [
            ("169.254.169.254", "the cloud metadata service"),
            ("127.0.0.1", "loopback"),
            ("127.1.2.3", "loopback, the whole /8"),
            ("10.1.2.3", "RFC 1918"),
            ("172.16.5.4", "RFC 1918"),
            ("192.168.1.1", "RFC 1918"),
            ("100.64.0.1", "RFC 6598 carrier-grade NAT"),
            ("100.127.255.254", "RFC 6598, the far end"),
            ("0.0.0.0", "this host"),
            ("0.1.2.3", "this network"),
            ("169.254.1.1", "link-local"),
            ("192.0.0.1", "IETF protocol assignments"),
            ("192.0.2.1", "TEST-NET-1"),
            ("198.51.100.1", "TEST-NET-2"),
            ("203.0.113.1", "TEST-NET-3"),
            ("198.18.0.1", "benchmarking"),
            ("192.88.99.1", "the deprecated 6to4 relay anycast"),
            ("224.0.0.1", "multicast"),
            ("240.0.0.1", "reserved"),
            ("255.255.255.255", "broadcast"),
        ],
    )
    def test_a_v4_address_off_the_public_internet_is_refused(self, address, what):
        with pytest.raises(UrlRefused):
            inspect("https://carolinamountainclub.org/", resolve=fixed(address))

    @pytest.mark.parametrize(
        "address,what",
        [
            ("::1", "loopback"),
            ("::", "unspecified"),
            ("fe80::1", "link-local"),
            ("fc00::1", "unique local"),
            ("fd12:3456::1", "unique local"),
            ("ff02::1", "multicast"),
            ("::ffff:127.0.0.1", "IPv4-mapped loopback"),
            ("::ffff:169.254.169.254", "IPv4-mapped metadata"),
            ("::ffff:10.0.0.1", "IPv4-mapped RFC 1918"),
            ("::ffff:100.64.0.1", "IPv4-mapped carrier NAT"),
            ("2002:7f00:1::", "6to4 wrapping loopback"),
            ("2002:a00:1::", "6to4 wrapping RFC 1918"),
            ("2002:a9fe:a9fe::", "6to4 wrapping the metadata address"),
            ("2001:0:0:0:0:0:a9fe:a9fe", "Teredo"),
            ("64:ff9b::7f00:1", "NAT64 wrapping loopback"),
            ("64:ff9b::a9fe:a9fe", "NAT64 wrapping the metadata address"),
            ("100::1", "discard-only"),
            ("2001:db8::1", "documentation"),
        ],
    )
    def test_a_v6_address_off_the_public_internet_is_refused(self, address, what):
        with pytest.raises(UrlRefused):
            inspect("https://carolinamountainclub.org/", resolve=fixed(address))

    def test_one_bad_address_among_good_ones_refuses_the_whole_host(self):
        """This is the DNS-rebinding case and the reason it is not `any()`.

        A name that answers with a public address and a private one lets the
        client pick, and something will eventually pick the private one. The
        host is refused rather than narrowed, because a name that resolves
        inside somebody's network is not a name we have any business reading.
        """
        with pytest.raises(UrlRefused):
            inspect("https://carolinamountainclub.org/", resolve=fixed("8.8.8.8", "10.0.0.5"))

    def test_a_host_that_resolves_to_nothing_is_refused_with_a_reason(self):
        with pytest.raises(UrlRefused):
            inspect("https://carolinamountainclub.org/", resolve=fixed())

    def test_a_resolver_failure_is_a_refusal_and_not_a_crash(self):
        with pytest.raises(UrlRefused):
            inspect("https://nope.example/", resolve=refusing(OSError("NXDOMAIN")))

    def test_every_accepted_address_is_carried_so_the_fetch_can_check_the_peer(self):
        """The guard's answer has to survive DNS changing its mind.

        Validating a name and then letting a client re-resolve it is a race
        somebody wins by running the DNS. `addresses` is what the fetcher
        compares the socket's real peer against.
        """
        target = inspect("https://carolinamountainclub.org/", resolve=fixed("8.8.8.8", "1.1.1.1"))
        assert set(target.addresses) == {"8.8.8.8", "1.1.1.1"}


class TestFollowingARedirect:
    def test_a_redirect_to_another_public_host_is_allowed(self):
        first = inspect("https://carolinamountainclub.org/", resolve=OK)
        second = follow(first, "https://www.carolinamountainclub.org/maps", resolve=OK)
        assert second.host == "www.carolinamountainclub.org"
        assert second.hops == 1

    def test_a_relative_redirect_resolves_against_the_previous_url(self):
        first = inspect("https://carolinamountainclub.org/a/b", resolve=OK)
        second = follow(first, "/maps", resolve=OK)
        assert second.url == "https://carolinamountainclub.org/maps"

    def test_a_redirect_into_a_private_address_is_refused(self):
        """The classic bypass: a public front door that points inward.

        The first hop passes every check, so a guard that only inspects the
        URL a hiker typed has already lost by the time this happens.
        """
        first = inspect("https://carolinamountainclub.org/", resolve=OK)
        with pytest.raises(UrlRefused):
            follow(first, "https://internal.carolinamountainclub.org/", resolve=fixed("10.0.0.5"))

    def test_a_redirect_to_the_metadata_address_is_refused(self):
        first = inspect("https://carolinamountainclub.org/", resolve=OK)
        with pytest.raises(UrlRefused):
            follow(first, "http://169.254.169.254/latest/meta-data/", resolve=fixed("169.254.169.254"))

    def test_a_redirect_to_another_scheme_is_refused(self):
        first = inspect("https://carolinamountainclub.org/", resolve=OK)
        with pytest.raises(UrlRefused):
            follow(first, "file:///etc/passwd", resolve=OK)

    def test_the_redirect_budget_is_finite(self):
        target = inspect("https://carolinamountainclub.org/", resolve=OK)
        for _ in range(MAX_REDIRECTS):
            target = follow(target, "https://carolinamountainclub.org/next", resolve=OK)
        with pytest.raises(UrlRefused):
            follow(target, "https://carolinamountainclub.org/next", resolve=OK)

    def test_an_empty_location_is_refused(self):
        first = inspect("https://carolinamountainclub.org/", resolve=OK)
        with pytest.raises(UrlRefused):
            follow(first, "", resolve=OK)


class TestWhatTheRefusalSays:
    def test_the_message_names_the_host_rather_than_the_rule(self):
        """A hiker reads this. "Refused by policy" tells them nothing."""
        with pytest.raises(UrlRefused) as caught:
            inspect("https://wiki.local/", resolve=OK)
        assert "wiki.local" in str(caught.value)

    def test_the_message_does_not_leak_the_resolved_address(self):
        """What a name resolves to inside somebody's network is not ours to echo.

        A refusal that prints `10.0.0.5` turns this endpoint into a DNS
        oracle for whatever network the backend is sitting in.
        """
        with pytest.raises(UrlRefused) as caught:
            inspect("https://carolinamountainclub.org/", resolve=fixed("10.0.0.5"))
        assert "10.0.0.5" not in str(caught.value)
