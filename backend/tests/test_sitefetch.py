"""Reading a nominated organization's public pages, and stopping in time.

`app/core/urlguard.py` decides what may be opened. This is what happens
after it says yes, and it carries the three limits that a guard cannot: how
many bytes, how long, and how many pages.

**THE PEER CHECK IS THE HALF THE GUARD CANNOT DO.** The guard resolves a
name and approves the addresses. Between that moment and the socket, DNS can
answer differently, and whoever runs the DNS picks the moment. So the
fetcher opens the connection, asks it what it actually connected to, and
refuses before reading a byte of the body if the answer is not one the guard
approved. Neither half is sufficient alone, which is why both are here and
why "we could not tell" is a refusal rather than a shrug.

Nothing in this file reaches the network. The transport is an
`httpx.MockTransport` and the peer is injected, because what is under test
is the fetcher's own decisions.
"""

import httpx
import pytest

from app.core.sitefetch import (
    MAX_BYTES,
    MAX_PAGES,
    FetchRefused,
    Page,
    extract,
    peer_is_expected,
    read_page,
    read_site,
)
from app.core.urlguard import SafeTarget, UrlRefused

PUBLIC = "8.8.8.8"


def only_public(host: str) -> list[str]:
    return [PUBLIC]


def saying(peer: str | None):
    def read_peer(response: httpx.Response) -> str | None:
        return peer

    return read_peer


AT_THE_RIGHT_PLACE = saying(PUBLIC)


def transport(handler):
    return httpx.MockTransport(handler)


def page_of(body: str, *, content_type: str = "text/html; charset=utf-8", status: int = 200, headers=None):
    def handler(request: httpx.Request) -> httpx.Response:
        merged = {"content-type": content_type}
        merged.update(headers or {})
        return httpx.Response(status, headers=merged, content=body.encode("utf-8"))

    return handler


def routes(**by_path):
    """A tiny site: path -> handler, and 404 for anything not named."""

    def handler(request: httpx.Request) -> httpx.Response:
        key = request.url.path.strip("/").replace("/", "_").replace(".", "_") or "root"
        made = by_path.get(key)
        if made is None:
            return httpx.Response(404, headers={"content-type": "text/plain"}, content=b"no")
        return made(request)

    return handler


class TestThePeerCheck:
    def test_an_approved_address_passes(self):
        target = SafeTarget(url="https://a.org/", host="a.org", addresses=("8.8.8.8", "1.1.1.1"))
        assert peer_is_expected(target, "1.1.1.1") is True

    def test_an_address_the_guard_never_saw_fails(self):
        """This is DNS rebinding arriving, and the only place it is visible."""
        target = SafeTarget(url="https://a.org/", host="a.org", addresses=("8.8.8.8",))
        assert peer_is_expected(target, "10.0.0.5") is False

    def test_not_knowing_is_not_the_same_as_yes(self):
        """A check that passes when it cannot run is not a check.

        `None` is what an egress proxy produces - the socket's peer is the
        proxy, and the name was resolved by something we are not asking.
        """
        target = SafeTarget(url="https://a.org/", host="a.org", addresses=("8.8.8.8",))
        assert peer_is_expected(target, None) is False

    def test_a_scope_id_on_a_v6_peer_is_ignored(self):
        target = SafeTarget(url="https://a.org/", host="a.org", addresses=("2606:4700::1111",))
        assert peer_is_expected(target, "2606:4700::1111%eth0") is True

    def test_the_peer_is_compared_as_an_address_and_not_as_a_string(self):
        """`::ffff:8.8.8.8` and `8.8.8.8` are the same machine.

        A dual-stack socket reports the first spelling for a v4 connection,
        and a string compare would refuse every such fetch.
        """
        target = SafeTarget(url="https://a.org/", host="a.org", addresses=("8.8.8.8",))
        assert peer_is_expected(target, "::ffff:8.8.8.8") is True

    def test_a_peer_that_is_not_an_address_at_all_fails(self):
        target = SafeTarget(url="https://a.org/", host="a.org", addresses=("8.8.8.8",))
        assert peer_is_expected(target, "somewhere") is False


class TestReadingOnePage:
    def test_a_plain_page_comes_back_as_text(self):
        client = httpx.Client(transport=transport(page_of("<h1>Carolina Mountain Club</h1><p>Asheville</p>")))
        page = read_page(
            "https://cmc.org/",
            client=client,
            resolve=only_public,
            read_peer=AT_THE_RIGHT_PLACE,
        )
        assert isinstance(page, Page)
        assert "Carolina Mountain Club" in page.text
        assert "Asheville" in page.text

    def test_a_connection_to_an_address_the_guard_did_not_approve_is_refused(self):
        client = httpx.Client(transport=transport(page_of("<h1>hi</h1>")))
        with pytest.raises(FetchRefused):
            read_page(
                "https://cmc.org/",
                client=client,
                resolve=only_public,
                read_peer=saying("10.0.0.5"),
            )

    def test_a_connection_whose_peer_is_unknown_is_refused(self):
        client = httpx.Client(transport=transport(page_of("<h1>hi</h1>")))
        with pytest.raises(FetchRefused):
            read_page(
                "https://cmc.org/",
                client=client,
                resolve=only_public,
                read_peer=saying(None),
            )

    def test_the_body_is_not_read_when_the_peer_is_wrong(self):
        """Refusing after reading the body is refusing after the damage.

        The body is the part that can be enormous, and the part a rebound
        connection wants us to have.
        """
        read_bytes: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            def stream():
                read_bytes.append(1)
                yield b"<h1>secret</h1>"

            return httpx.Response(200, headers={"content-type": "text/html"}, content=stream())

        client = httpx.Client(transport=transport(handler))
        with pytest.raises(FetchRefused):
            read_page(
                "https://cmc.org/",
                client=client,
                resolve=only_public,
                read_peer=saying("10.0.0.5"),
            )
        assert read_bytes == []

    @pytest.mark.parametrize(
        "content_type",
        ["image/png", "application/pdf", "application/zip", "video/mp4", "application/octet-stream"],
    )
    def test_a_type_we_cannot_read_is_refused(self, content_type):
        client = httpx.Client(transport=transport(page_of("binary", content_type=content_type)))
        with pytest.raises(FetchRefused):
            read_page("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)

    @pytest.mark.parametrize(
        "content_type",
        ["text/html", "text/html; charset=iso-8859-1", "text/plain", "application/json", "application/xml"],
    )
    def test_the_types_a_club_publishes_are_read(self, content_type):
        client = httpx.Client(transport=transport(page_of("hello", content_type=content_type)))
        page = read_page("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)
        assert "hello" in page.text

    def test_a_declared_length_over_the_cap_is_refused_before_the_body(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200,
                headers={"content-type": "text/html", "content-length": str(MAX_BYTES * 10)},
                content=b"<h1>x</h1>",
            )

        client = httpx.Client(transport=transport(handler))
        with pytest.raises(FetchRefused):
            read_page("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)

    def test_a_body_that_lies_about_its_length_is_cut_at_the_cap(self):
        """Content-Length is the server's claim, not a fact.

        A server that says 10 bytes and sends forever is the whole reason the
        cap is enforced while reading rather than only before.
        """

        def handler(request: httpx.Request) -> httpx.Response:
            def stream():
                for _ in range(200):
                    yield b"a" * 50_000

            return httpx.Response(200, headers={"content-type": "text/plain"}, content=stream())

        client = httpx.Client(transport=transport(handler))
        page = read_page("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)
        assert page.truncated is True
        assert len(page.text) <= MAX_BYTES

    def test_a_server_error_is_a_refusal_with_the_status_in_it(self):
        client = httpx.Client(transport=transport(page_of("oops", status=500)))
        with pytest.raises(FetchRefused) as caught:
            read_page("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)
        assert "500" in str(caught.value)

    def test_a_transport_failure_is_a_refusal_and_not_a_crash(self):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route")

        client = httpx.Client(transport=transport(handler))
        with pytest.raises(FetchRefused):
            read_page("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)

    def test_a_refused_url_stays_refused_here(self):
        client = httpx.Client(transport=transport(page_of("<h1>hi</h1>")))
        with pytest.raises(UrlRefused):
            read_page("https://wiki.local/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)


class TestWhatWeSendAndDoNotSend:
    def test_the_request_says_who_we_are_and_where_to_complain(self):
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"hi")

        client = httpx.Client(transport=transport(handler))
        read_page("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)
        agent = seen[0].headers["user-agent"]
        assert "OurHike" in agent
        assert "http" in agent  # a URL a webmaster can open

    def test_no_cookie_and_no_authorization_ever_leave(self):
        """We are reading a stranger's site. We have no business there.

        Worth a standing test rather than a habit: the client this runs on is
        shared, and a cookie jar picked up on one fetch reaching another
        organization's site would be the kind of leak nobody looks for.
        """
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(
                200,
                headers={"content-type": "text/html", "set-cookie": "session=abc; Path=/"},
                content=b"hi",
            )

        client = httpx.Client(transport=transport(handler))
        read_page("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)
        read_page("https://cmc.org/again", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)
        for request in seen:
            assert "cookie" not in {name.lower() for name in request.headers}
            assert "authorization" not in {name.lower() for name in request.headers}

    def test_we_ask_for_a_page_rather_than_anything(self):
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"hi")

        client = httpx.Client(transport=transport(handler))
        read_page("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)
        assert seen[0].method == "GET"
        assert "text/html" in seen[0].headers["accept"]


class TestRedirects:
    def test_a_redirect_is_followed_through_the_guard(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/":
                return httpx.Response(301, headers={"location": "https://cmc.org/home"})
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<h1>arrived</h1>")

        client = httpx.Client(transport=transport(handler))
        page = read_page("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)
        assert "arrived" in page.text
        assert page.url == "https://cmc.org/home"

    def test_a_redirect_into_a_private_network_is_refused(self):
        def resolve(host: str) -> list[str]:
            return ["10.0.0.5"] if host == "internal.cmc.org" else [PUBLIC]

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "cmc.org":
                return httpx.Response(302, headers={"location": "https://internal.cmc.org/"})
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<h1>inside</h1>")

        client = httpx.Client(transport=transport(handler))
        with pytest.raises(UrlRefused):
            read_page("https://cmc.org/", client=client, resolve=resolve, read_peer=AT_THE_RIGHT_PLACE)

    def test_a_redirect_loop_ends(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(302, headers={"location": "https://cmc.org/round"})

        client = httpx.Client(transport=transport(handler))
        with pytest.raises((FetchRefused, UrlRefused)):
            read_page("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)

    def test_the_peer_is_checked_again_on_every_hop(self):
        """A first hop to a real host and a second to a rebound one.

        The peer check exists for exactly this, so it cannot be a thing that
        happens once at the start.
        """
        peers = iter([PUBLIC, "10.0.0.5"])

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/":
                return httpx.Response(301, headers={"location": "https://cmc.org/home"})
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<h1>arrived</h1>")

        client = httpx.Client(transport=transport(handler))
        with pytest.raises(FetchRefused):
            read_page(
                "https://cmc.org/",
                client=client,
                resolve=only_public,
                read_peer=lambda response: next(peers),
            )


class TestRobots:
    def test_a_path_robots_disallows_is_not_read(self):
        client = httpx.Client(
            transport=transport(
                routes(
                    robots_txt=page_of("User-agent: *\nDisallow: /members\n", content_type="text/plain"),
                    members=page_of("<h1>roster</h1>"),
                )
            )
        )
        with pytest.raises(FetchRefused):
            read_page(
                "https://cmc.org/members",
                client=client,
                resolve=only_public,
                read_peer=AT_THE_RIGHT_PLACE,
                obey_robots=True,
            )

    def test_a_path_robots_allows_is_read(self):
        client = httpx.Client(
            transport=transport(
                routes(
                    robots_txt=page_of("User-agent: *\nDisallow: /members\n", content_type="text/plain"),
                    maps=page_of("<h1>our maps</h1>"),
                )
            )
        )
        page = read_page(
            "https://cmc.org/maps",
            client=client,
            resolve=only_public,
            read_peer=AT_THE_RIGHT_PLACE,
            obey_robots=True,
        )
        assert "our maps" in page.text

    def test_no_robots_file_means_the_whole_site_is_open(self):
        client = httpx.Client(transport=transport(routes(maps=page_of("<h1>our maps</h1>"))))
        page = read_page(
            "https://cmc.org/maps",
            client=client,
            resolve=only_public,
            read_peer=AT_THE_RIGHT_PLACE,
            obey_robots=True,
        )
        assert "our maps" in page.text

    def test_a_robots_file_that_errors_closes_the_site(self):
        """RFC 9309: 4xx opens the site, 5xx closes it.

        A server too broken to say whether we may read it has not said yes.
        """
        client = httpx.Client(
            transport=transport(
                routes(
                    robots_txt=page_of("oh dear", content_type="text/plain", status=503),
                    maps=page_of("<h1>our maps</h1>"),
                )
            )
        )
        with pytest.raises(FetchRefused):
            read_page(
                "https://cmc.org/maps",
                client=client,
                resolve=only_public,
                read_peer=AT_THE_RIGHT_PLACE,
                obey_robots=True,
            )


class TestExtractingWhatMatters:
    def test_the_title_comes_back(self):
        page = extract("https://cmc.org/", "<html><head><title>Carolina Mountain Club</title></head><body>x</body></html>")
        assert page.title == "Carolina Mountain Club"

    def test_script_and_style_are_not_text(self):
        page = extract(
            "https://cmc.org/",
            "<body><script>var a=1</script><style>.b{color:red}</style><p>Trails</p></body>",
        )
        assert "var a" not in page.text
        assert "color:red" not in page.text
        assert "Trails" in page.text

    def test_links_carry_their_words(self):
        page = extract("https://cmc.org/", '<a href="/maps">Trail maps</a>')
        assert page.links[0].href == "https://cmc.org/maps"
        assert page.links[0].text == "Trail maps"

    def test_a_mailto_link_is_an_address_rather_than_a_link(self):
        page = extract("https://cmc.org/contact", '<a href="mailto:maps@cmc.org">Priya Raghavan</a>')
        assert "maps@cmc.org" in page.emails

    def test_an_address_written_as_words_is_found_too(self):
        """Half of a club's contact page writes them out rather than linking."""
        page = extract("https://cmc.org/contact", "<p>Reach the coordinator at volunteers@cmc.org</p>")
        assert "volunteers@cmc.org" in page.emails

    def test_the_same_address_is_not_reported_twice(self):
        page = extract(
            "https://cmc.org/contact",
            '<a href="mailto:maps@cmc.org">Maps</a><p>maps@cmc.org</p>',
        )
        assert page.emails.count("maps@cmc.org") == 1

    def test_entities_are_decoded(self):
        page = extract("https://cmc.org/", "<p>Trails &amp; Tread &mdash; 2026</p>")
        assert "Trails & Tread" in page.text

    def test_a_relative_link_is_made_absolute_against_the_page(self):
        page = extract("https://cmc.org/about/", '<a href="../maps">Maps</a>')
        assert page.links[0].href == "https://cmc.org/maps"

    def test_broken_markup_does_not_raise(self):
        page = extract("https://cmc.org/", "<p>unclosed <a href=>Trails")
        assert "unclosed" in page.text

    def test_whitespace_collapses_so_the_model_reads_prose(self):
        page = extract("https://cmc.org/", "<p>Trails\n\n\n      and  \t tread</p>")
        assert "Trails and tread" in page.text


class TestReadingASite:
    def test_the_home_page_and_the_pages_worth_following(self):
        client = httpx.Client(
            transport=transport(
                routes(
                    root=page_of('<a href="/maps">Trail maps</a><a href="/contact">Contact us</a><a href="/shop">Shop</a>'),
                    maps=page_of("<h1>ArcGIS FeatureServer</h1>"),
                    contact=page_of("<p>volunteers@cmc.org</p>"),
                )
            )
        )
        pages = read_site("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)
        reached = {page.url for page in pages}
        assert "https://cmc.org/" in reached
        assert "https://cmc.org/maps" in reached
        assert "https://cmc.org/contact" in reached

    def test_it_stops_at_the_page_budget(self):
        many = "".join(f'<a href="/maps-{n}">Trail maps {n}</a>' for n in range(50))

        def handler(request: httpx.Request) -> httpx.Response:
            body = many if request.url.path == "/" else "<h1>a page</h1>"
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body.encode())

        client = httpx.Client(transport=transport(handler))
        pages = read_site("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)
        assert len(pages) <= MAX_PAGES

    def test_it_never_leaves_the_organizations_own_site(self):
        """Following outward turns one nomination into a crawl of the web."""

        def handler(request: httpx.Request) -> httpx.Response:
            body = (
                '<a href="https://facebook.com/cmc">Facebook</a><a href="/maps">Maps</a>'
                if request.url.path == "/"
                else "<h1>a page</h1>"
            )
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body.encode())

        client = httpx.Client(transport=transport(handler))
        pages = read_site("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)
        assert all("cmc.org" in page.url for page in pages)

    def test_a_page_that_refuses_does_not_lose_the_others(self):
        """One 500 on a contact page is not a reason to report nothing."""

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/":
                body = b'<a href="/maps">Trail maps</a><a href="/contact">Contact</a>'
                return httpx.Response(200, headers={"content-type": "text/html"}, content=body)
            if request.url.path == "/contact":
                return httpx.Response(500, headers={"content-type": "text/html"}, content=b"no")
            return httpx.Response(200, headers={"content-type": "text/html"}, content=b"<h1>maps</h1>")

        client = httpx.Client(transport=transport(handler))
        pages = read_site("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)
        assert {page.url for page in pages} == {"https://cmc.org/", "https://cmc.org/maps"}

    def test_a_home_page_that_refuses_refuses_the_whole_read(self):
        client = httpx.Client(transport=transport(page_of("no", status=404)))
        with pytest.raises(FetchRefused):
            read_site("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)

    def test_the_same_page_is_not_read_twice(self):
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(str(request.url))
            body = (
                b'<a href="/maps">Maps</a><a href="/maps">Trail maps</a><a href="/maps?x=1">Maps again</a>'
                if request.url.path == "/"
                else b"<h1>maps</h1>"
            )
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body)

        client = httpx.Client(transport=transport(handler))
        read_site("https://cmc.org/", client=client, resolve=only_public, read_peer=AT_THE_RIGHT_PLACE)
        assert seen.count("https://cmc.org/maps") == 1
