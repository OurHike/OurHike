"""Tests for fetch_wayback_hike_pages.py - recovering NYNJTC's hike write-ups
from the Internet Archive so a photograph's hike can be READ rather than
scored (#1450).

All HTTP is mocked (TESTING.md: real network calls never fire in tests).

Two groups here are load-bearing:

  - **A rewritten href is not the original URL.** The archive serves hrefs in
    its own `/web/<timestamp>/<original>` form. Following those would ask the
    archive to archive its own archive, and the hike page would never be
    reached.
  - **Backing off is the feature.** On 2026-09-15 a few hundred reads at one
    per second earned 429s, then 503s, then connection resets that outlasted
    half an hour - at which point the listing itself could not be re-read. The
    retry ladder and the throttle are what make this job finishable, so they
    are pinned rather than left to be "tuned" later by someone who has not met
    the rate limiter.
"""

import json

import pytest
import requests

import fetch_wayback_hike_pages as pages
from lib import wayback_rate

CDX = pages.CDX_API


@pytest.fixture(autouse=True)
def _unthrottled(monkeypatch):
    """Give every test its own limiter on a clock that never really waits.

    The shared `lib.wayback_rate.ARCHIVE` is real: ten requests a minute, on
    the real clock with a real sleep. Correct in production and intolerable in
    a suite - a file issuing eleven mocked requests would block for up to a
    real minute, and CI would look hung rather than slow. That happened here
    before this fixture existed.

    Autouse rather than opt-in because forgetting it does not FAIL a test, it
    STALLS one, and a stalled test is the kind of slowness that gets a whole
    suite called flaky instead of fixed.
    """
    monkeypatch.setattr(
        pages,
        "ARCHIVE",
        wayback_rate.RateLimit(max_requests=10_000, clock=lambda: 0.0, sleep=lambda _s: None),
    )


def _session():
    return requests.Session()


def _no_sleep(monkeypatch):
    monkeypatch.setattr(pages.time, "sleep", lambda _s: None)


def _cdx(*rows):
    return [["original", "timestamp"], *[list(r) for r in rows]]


# --- the index, and getting real URLs out of it --------------------------------


def test_an_archive_rewritten_href_yields_the_original_url():
    """THE parsing test. The archive writes hrefs as
    /web/20190419182814/https://www.nynjtc.org/hike/foo - taking that verbatim
    would send the next request back into the archive's own namespace."""
    markup = '<a href="/web/20190419182814/https://www.nynjtc.org/hike/terrace-pond-north">Terrace Pond</a>'

    assert pages.hike_links(markup) == ["https://www.nynjtc.org/hike/terrace-pond-north"]


def test_a_site_relative_href_is_made_absolute():
    assert pages.hike_links('<a href="/hike/bearfort-ridge">x</a>') == ["https://www.nynjtc.org/hike/bearfort-ridge"]


def test_node_paths_count_as_hike_pages_too():
    """Drupal serves the same write-up at /node/<id> as well as its alias, and
    the index uses both."""
    assert pages.hike_links('<a href="/node/1231">x</a>') == ["https://www.nynjtc.org/node/1231"]


def test_links_are_deduped_and_query_strings_dropped():
    markup = """
      <a href="/hike/a">one</a><a href="/hike/a?sort=asc">one again</a>
      <a href="/hike/a/">trailing slash</a><a href="/hike/b">two</a>
    """

    assert pages.hike_links(markup) == ["https://www.nynjtc.org/hike/a", "https://www.nynjtc.org/hike/b"]


def test_links_that_are_not_hikes_are_ignored():
    markup = '<a href="/membership">join</a><a href="/books/circuit-hikes-harriman">a book</a>'

    assert pages.hike_links(markup) == []


# --- the location, which is the point of reading the page ----------------------


@pytest.mark.parametrize(
    "markup",
    [
        '{"latitude":"41.2069","longitude":"-74.2592"}',
        '<div data-lat="41.2069" data-lon="-74.2592"></div>',
        '<a href="https://maps.google.com/?q=41.2069,-74.2592">map</a>',
        '<a href="https://maps.google.com/maps?ll=41.2069,-74.2592&z=14">map</a>',
    ],
)
def test_a_coordinate_is_read_from_whichever_shape_the_page_uses(markup):
    """The maintainer's point - the location is in the text or a link. A hike
    with a coordinate can be matched to a photograph by distance, which is a
    stronger claim than string overlap."""
    found = pages.coordinates(markup)

    assert found is not None
    assert found[0] == pytest.approx(41.2069)
    assert found[1] == pytest.approx(-74.2592)


def test_a_number_pair_outside_the_region_is_not_a_coordinate():
    """A Drupal page is full of numbers. A regex that took any pair would put
    a NYNJTC hike in the Atlantic, and the failure would look like data rather
    than like a bug."""
    assert pages.coordinates('{"latitude":"1.5","longitude":"103.8"}') is None


def test_a_page_with_no_coordinate_says_so_rather_than_guessing():
    assert pages.coordinates("<p>A nice walk in the woods.</p>") is None


# --- the page itself -----------------------------------------------------------


REAL_SHAPED_PAGE = """
<html><head><title>Hike: Terrace Pond North Loop | New York-New Jersey Trail Conference</title></head>
<body>
  <div class="field-name-field-park"><div class="field-item">Wawayanda State Park</div></div>
  <div class="field-name-field-region"><div class="field-item">North Jersey</div></div>
  <a href="https://maps.google.com/?q=41.1604,-74.4012">directions</a>
  <img src="/sites/default/files/u26/Beaver%20Lodge%20in%20swamp%20on%20Terrace%20Pond%20South%20Trail%20250.jpg">
  <p>Climbs the Terrace Pond South Trail past a beaver lodge.</p>
</body></html>
"""


def test_a_write_up_yields_name_park_location_photo_and_prose():
    """All four things the match needs, from one document written by the
    people who walked it."""
    page = pages.parse_page(REAL_SHAPED_PAGE, "https://www.nynjtc.org/hike/terrace-pond", "20190419182814")

    assert page.name == "Terrace Pond North Loop"
    assert page.park == "Wawayanda State Park"
    assert page.region == "North Jersey"
    assert page.lat == pytest.approx(41.1604)
    assert [photo.filename for photo in page.photos] == ["Beaver Lodge in swamp on Terrace Pond South Trail 250.jpg"]
    assert "beaver lodge" in page.description.lower()


def test_the_photo_filename_matches_what_the_photo_fetcher_stores():
    """THE JOIN. fetch_wayback_hike_photos.py keys its recovery on this same
    unquoted filename, so a page naming it identifies that photograph's hike
    without any scoring at all."""
    page = pages.parse_page(REAL_SHAPED_PAGE, "https://www.nynjtc.org/hike/x", "20190419182814")

    assert page.photos[0].filename.startswith("Beaver Lodge in swamp on Terrace Pond South Trail")
    assert "%20" not in page.photos[0].filename


def test_the_site_name_is_taken_off_the_title():
    page = pages.parse_page(
        "<title>Hike: Bearfort Ridge Loop - New York-New Jersey Trail Conference</title>", "u", "20190419182814"
    )

    assert page.name == "Bearfort Ridge Loop"


def test_a_page_with_no_title_is_not_a_hike():
    assert pages.parse_page("<html><body>nothing</body></html>", "u", "20190419182814") is None


def test_a_page_carrying_no_photo_is_still_recovered():
    """Its name, location and prose are what the fallback matcher scores
    against, so a write-up without a picture is still worth having."""
    page = pages.parse_page("<title>A Loop | New York-New Jersey Trail Conference</title>", "u", "20190419182814")

    assert page is not None
    assert page.photos == []


# --- backing off is the feature ------------------------------------------------


def test_every_request_passes_the_shared_ceiling(monkeypatch, requests_mock):
    """Pacing is not a sleep in this module - `lib/wayback_rate.ARCHIVE` is a
    hard rolling-window cap, and `get()` takes from it INSIDE the retry loop so
    a retry is counted too.

    Asserted as behaviour rather than object identity: one failed attempt plus
    one success must consume two slots. Pinned so a later edit cannot quietly
    return to a sleep, which is what let one request a second become an egress
    IP refused outright on 2026-09-15."""
    _no_sleep(monkeypatch)
    taken = []
    monkeypatch.setattr(pages.ARCHIVE, "take", lambda: taken.append(1) or 0.0)
    requests_mock.get("https://example.test/x", [{"status_code": 503}, {"text": "ok"}])

    pages.get(_session(), "https://example.test/x")

    assert len(taken) == 2
    assert wayback_rate.MAX_REQUESTS_PER_MINUTE <= 10
    assert max(pages.RETRY_BACKOFF_SECONDS) >= 300


def test_a_429_is_waited_out_rather_than_hammered(monkeypatch, requests_mock):
    waits = []
    monkeypatch.setattr(pages.time, "sleep", lambda s: waits.append(s))
    requests_mock.get("https://example.test/x", [{"status_code": 429}, {"text": "ok"}])

    response = pages.get(_session(), "https://example.test/x")

    assert response.text == "ok"
    assert max(waits) >= 30


def test_the_archives_own_retry_after_wins_when_it_is_longer(monkeypatch, requests_mock):
    """It asked for up to 47s during the incident. Returning sooner than the
    host asked just spends another refusal."""
    waits = []
    monkeypatch.setattr(pages.time, "sleep", lambda s: waits.append(s))
    requests_mock.get("https://example.test/x", [{"status_code": 429, "headers": {"Retry-After": "600"}}, {"text": "ok"}])

    pages.get(_session(), "https://example.test/x")

    assert 600 in waits


def test_a_page_the_archive_will_not_serve_costs_that_page_and_not_the_run(monkeypatch, requests_mock):
    """Unlike its sibling, this returns None rather than raising: the job is
    hundreds of pages against a host that is the constraint, so one refusal is
    a page to come back for, not a reason to discard everything recovered."""
    _no_sleep(monkeypatch)
    requests_mock.get("https://example.test/x", status_code=503)

    assert pages.get(_session(), "https://example.test/x") is None


# --- the most recent capture ---------------------------------------------------


def test_the_newest_capture_wins(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    requests_mock.get(
        CDX,
        json=_cdx(
            ("https://www.nynjtc.org/view/hike", "20190419182814"),
            ("https://www.nynjtc.org/view/hike", "20240103091500"),
            ("https://www.nynjtc.org/view/hike", "20211019214326"),
        ),
    )

    assert pages.latest_capture(_session(), "nynjtc.org/view/hike")[1] == "20240103091500"


def test_a_url_the_archive_never_captured_is_none(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    requests_mock.get(CDX, json=[])

    assert pages.latest_capture(_session(), "nynjtc.org/view/hike") is None


# --- resuming ------------------------------------------------------------------


def test_a_previous_runs_pages_are_carried_forward(tmp_path):
    """A long job over a rate-limited host WILL be interrupted, and a run that
    starts over is a run that puts the load on that host again."""
    path = tmp_path / "pages.json"
    path.write_text(
        json.dumps(
            {
                "format": pages.CACHE_FORMAT,
                "pages": [
                    {
                        "url": "https://www.nynjtc.org/hike/a",
                        "timestamp": "20190419182814",
                        "name": "A Loop",
                        "park": None,
                        "region": None,
                        "lat": None,
                        "lon": None,
                        "description": "x",
                        "photos": [],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    done = pages.load_done(path)

    assert "https://www.nynjtc.org/hike/a" in done
    assert done["https://www.nynjtc.org/hike/a"].name == "A Loop"


def test_an_unreadable_cache_costs_a_refetch_rather_than_a_crash(tmp_path):
    path = tmp_path / "pages.json"
    path.write_text("{ not json", encoding="utf-8")

    assert pages.load_done(path) == {}


def test_an_unknown_flag_is_rejected_rather_than_silently_ignored():
    """NOT "--index": argparse accepts any UNAMBIGUOUS PREFIX of a real flag,
    so "--index" is "--index-only" and this test used to run the whole job
    against the live archive while claiming to check argument parsing. It is
    the only test in this suite that ever reached the network, and it reached
    it by passing."""
    with pytest.raises(SystemExit) as excinfo:
        pages.run(["--indx"])

    assert excinfo.value.code == 2


# --- the probe (#1497) ----------------------------------------------------------
#
# The first full run recovered 439 write-ups and found a coordinate in NONE of
# them. That is either a fact about the corpus - and then the matcher's
# distance route can never fire - or `_LATLON_RES` misses the shape these
# pages use, which is a bug. Zero out of 439 is exactly what the second one
# looks like, and it could not be told apart from an agent sandbox because
# web.archive.org refuses that address.
#
# So the probe's job is NOT to find a coordinate. It is to make the two cases
# distinguishable in a log, which is why these tests care about what it prints
# rather than what it returns.


def _probe_mocks(requests_mock, markup):
    requests_mock.get(CDX, json=_cdx(("https://www.nynjtc.org/hike/x", "20230924170506")))
    requests_mock.get(
        pages.archived("https://www.nynjtc.org/hike/x", "20230924170506"),
        text=markup,
    )


def test_the_probe_reports_which_pattern_matched(monkeypatch, capsys, requests_mock):
    _no_sleep(monkeypatch)
    _probe_mocks(requests_mock, '<div data-lat="41.2" data-lon="-74.1">Claudius Smiths Rock</div>')

    assert pages.probe(_session(), "https://www.nynjtc.org/hike/x") == 0

    printed = capsys.readouterr().out
    assert "coordinates() -> (41.2, -74.1)" in printed
    assert "pattern 2: 1 hit" in printed


def test_a_page_with_no_coordinate_says_every_pattern_found_nothing(monkeypatch, capsys, requests_mock):
    """The finding case. Every pattern at zero AND no lat mention AND no bare
    pair is evidence the page carries none - which is a different claim from
    "the parser missed it", and the whole reason this prints three things."""
    _no_sleep(monkeypatch)
    _probe_mocks(requests_mock, "<p>Park at the lot on Route 17 and walk north.</p>")

    assert pages.probe(_session(), "https://www.nynjtc.org/hike/x") == 0

    printed = capsys.readouterr().out
    assert "coordinates() -> None" in printed
    assert "0 mention(s) of lat/latitude" in printed
    assert "0 bare decimal pair(s)" in printed


def test_the_probe_shows_a_coordinate_the_parser_missed(monkeypatch, capsys, requests_mock):
    """THE case this exists for. A page carrying a coordinate in a shape none
    of the four patterns match must come back as "coordinates() -> None" WITH
    the evidence beside it, or the run that found zero of 439 stays
    unexplained."""
    _no_sleep(monkeypatch)
    _probe_mocks(requests_mock, '<span class="geo">Latitude 41.2345678 / Longitude -74.1234567</span>')

    assert pages.probe(_session(), "https://www.nynjtc.org/hike/x") == 0

    printed = capsys.readouterr().out
    assert "coordinates() -> None" in printed
    # The mention is what says "look again at the patterns" rather than
    # "this page has no location".
    assert "1 mention(s) of lat/latitude" in printed
    assert "Latitude 41.2345678" in printed


def test_a_coordinate_outside_the_region_is_shown_as_matched_then_rejected(monkeypatch, capsys, requests_mock):
    """The third cause, and it reads like neither of the others: a pattern DID
    match and `coordinates()` threw it away for being outside the NY/NJ/PA
    box. Printing the raw hits beside the verdict is what separates a bounds
    rejection from a miss."""
    _no_sleep(monkeypatch)
    _probe_mocks(requests_mock, '<div data-lat="51.5" data-lon="-0.12">London</div>')

    assert pages.probe(_session(), "https://www.nynjtc.org/hike/x") == 0

    printed = capsys.readouterr().out
    assert "pattern 2: 1 hit" in printed
    assert "coordinates() -> None" in printed


def test_the_probe_names_the_photographs_the_page_shows(monkeypatch, capsys, requests_mock):
    """The other half of the join, checked in the same two requests: 154 of
    439 pages cited a photograph, and the probe is where a reader can see
    whether a page that cites none really shows none."""
    _no_sleep(monkeypatch)
    _probe_mocks(
        requests_mock,
        '<img src="https://www.nynjtc.org/sites/default/files/u26/Beaver_Lodge.jpg">',
    )

    assert pages.probe(_session(), "https://www.nynjtc.org/hike/x") == 0

    assert "Beaver_Lodge.jpg" in capsys.readouterr().out


def test_a_write_up_the_archive_never_captured_ends_the_probe(monkeypatch, capsys, requests_mock):
    _no_sleep(monkeypatch)
    requests_mock.get(CDX, json=_cdx())

    assert pages.probe(_session(), "https://www.nynjtc.org/hike/x") == 1

    assert "would not name a capture" in capsys.readouterr().out


def test_probe_is_not_prefix_matched_by_another_flag():
    """argparse accepts unambiguous prefixes, and a test that meant to check a
    flag once ran a whole archive job here because `--index` matched
    `--index-only`. `--probe` takes a URL, so a prefix collision would send a
    stage's worth of requests at the archive with the wrong argument."""
    with pytest.raises(SystemExit):
        pages.run(["--prob"])  # ambiguous only if a second --prob* flag ever appears


def coordinates(markup):
    return pages.coordinates(markup)


def coordinates_near(found, lat, lon, tolerance=1e-6):
    """Compared with a tolerance rather than by equality: the point is which
    place was parsed, not float repr."""
    return found is not None and abs(found[0] - lat) < tolerance and abs(found[1] - lon) < tolerance


# --- the coordinate the parser was throwing away (#1502) ------------------------
#
# The first full run reported a coordinate on NONE of 439 write-ups. The probe
# stage settled why: these pages publish the pair BARE -
# "41.195754000000,-74.184073000000" - and all four patterns only knew a
# coordinate that arrives labelled, behind a JSON key, a data- attribute or a
# Maps query parameter. So the matcher's distance route has never fired, and
# MAX_JOIN_METRES was not merely unvalidated but unvalidatable.


@pytest.mark.parametrize(
    "markup",
    [
        "41.195754000000,-74.184073000000",
        "41.195754, -74.184073",
        "41.195754,-74.184073",
    ],
)
def test_a_bare_pair_is_read_as_a_coordinate(markup):
    """The shape these pages actually use, in the three spellings the probe
    found on one capture of /hike/claudius-smiths-rock."""
    assert coordinates_near(coordinates(markup), 41.195754, -74.184073)


def test_a_labelled_coordinate_still_wins_over_a_bare_pair():
    """The bare pattern is LAST for this reason. A page that says which number
    is the latitude should be read by the pattern that knows the label, not by
    the one guessing from position."""
    markup = 'data-lat="41.500000" data-lon="-74.500000" and later 40.111111,-73.111111'

    assert coordinates_near(coordinates(markup), 41.5, -74.5)


def test_a_good_coordinate_below_a_bad_one_is_still_found():
    """THE second defect, and the one that was invisible. `coordinates()` used
    `search()`, so ONE match per pattern: a first match failing the region
    check moved on to the next PATTERN rather than the next match, discarding
    a good coordinate further down the page. Harmless while every pattern was
    a labelled shape appearing once, and live the moment a bare pair - which
    an 82 KB Drupal page has several of - joined the list."""
    markup = "map centred on 51.507400,-0.127800 ... trailhead at 41.195754,-74.184073"

    assert coordinates_near(coordinates(markup), 41.195754, -74.184073)


@pytest.mark.parametrize(
    ("markup", "why"),
    [
        ("51.507400,-0.127800", "London, outside the NY/NJ/PA box"),
        ("41.19,-74.18", "two decimals is a version string, not a geocode"),
        ("matrix(1.5000,2.0000)", "a CSS transform"),
        ("<p>Park at the lot on Route 17 and walk north.</p>", "no numbers at all"),
    ],
)
def test_what_a_bare_pair_must_not_accept(markup, why):
    """What makes an unlabelled pair safe at all. The region bounds do the real
    work - two decimals are only read as a place when they land in the corner
    of the world these hikes are in - and the three-digit fraction keeps this
    off stylesheet values."""
    assert coordinates(markup) is None, why


def test_the_bare_pattern_is_last_in_the_list():
    """Pinned as ORDER rather than as behaviour, because the behaviour test
    above passes for the wrong reason if somebody reorders these: a bare
    pattern earlier in the list would match the labelled page's own numbers
    before the labelled pattern ever ran."""
    assert pages._LATLON_RES[-1].pattern.startswith("(-?")
    assert "data-lat" in pages._LATLON_RES[1].pattern


class TestTheCreditIsTheLicencesCondition:
    """#1504. `sources.json`'s `nynjtc_hikes_licence` does not ask for a credit,
    it CONDITIONS the permission on one: "the attribution is a condition rather
    than a courtesy ... a photograph the page does not credit is not fetched at
    all". The recovery this parser feeds selects by directory prefix, which is
    wider than the permission, so whether a credit can be read off the page is
    the thing that decides what may ever ship.

    Every test here is about the DIRECTION of a wrong answer as much as the
    answer: a credit this parser misses withholds a photograph, and no case
    below may invent one or move one between photographs.
    """

    def test_a_credit_in_the_images_own_alt_text_is_read(self):
        found = pages.page_photos('<img src="/u26/a.jpg" alt="Sunfish Pond. Photo by Daniel Chazin">')

        assert [(p.filename, p.credit, p.credit_basis) for p in found] == [("a.jpg", "Daniel Chazin", "img")]

    def test_the_title_attribute_counts_too(self):
        found = pages.page_photos('<img title="Photo: Jane Daniels" src="/u26/a.jpg">')

        assert found[0].credit == "Jane Daniels"

    def test_a_credit_in_the_caption_under_the_image_is_read(self):
        """The shape that actually carried the credit on six of NYNJTC's twenty
        WordPress write-ups (measured 2026-09-09, lib/nynjtc_hikes.py at
        c3be84f8^): a paragraph under the figure, not an attribute on it."""
        found = pages.page_photos('<img src="/u26/a.jpg"><div class="caption"><p>Looking north. Photo: Jane Daniels</p></div>')

        assert (found[0].credit, found[0].credit_basis) == ("Jane Daniels", "caption")

    def test_a_credit_elsewhere_on_the_page_is_not_this_photographs_credit(self):
        """THE ROUTE THAT WAS REMOVED, kept as the case that must stay refused.

        A third route once read a credit from anywhere in the document when
        the page showed exactly one u26 image, on the argument that there was
        nothing else it could be about. There was: "sole" counted only u26
        images, so a news teaser elsewhere on the page handed ITS
        photographer's name to the article's photograph. Nothing measured
        supported the route, and attaching a real person's name to somebody
        else's picture is the worst thing this parser can do.
        """
        markup = (
            '<div class="teaser"><img src="/sites/default/files/news/bear.jpg">'
            "<p>Bears return to Harriman. Photo by Jane Daniels</p></div>"
            '<img src="/sites/default/files/u26/DSC00417.jpg">'
        )

        found = pages.page_photos(markup)

        assert [(p.filename, p.credit) for p in found] == [("DSC00417.jpg", None)]

    def test_a_credit_in_the_footer_is_not_the_last_photographs_caption(self):
        """The bound that two weaker ones missed. Stopping at the next u26
        image does nothing for the LAST image on a page, and counting text
        runs does not either - `</p></div><div id=footer><p>` yields no text
        at all, so the footer's credit is still the next run. What separates a
        caption from a footer is structure, so `enclosing_caption` stops at
        the first closing tag that leaves the image's own element."""
        markup = (
            '<div class="content"><img src="/u26/a.jpg"><p>A view north.</p></div>'
            '<div id="footer"><p>Photo by Daniel Chazin</p></div>'
        )

        found = pages.page_photos(markup)

        assert (found[0].credit, found[0].credit_basis) == (None, None)

    def test_an_image_inline_in_a_paragraph_still_gets_that_paragraphs_credit(self):
        """The other direction, because a bound that refuses everything is not
        a bound. Text already written before the closing tag is kept, so a
        picture set inside a paragraph reads its own paragraph."""
        markup = '<p>The view north <img src="/u26/a.jpg"> Photo by Daniel Chazin</p><div id="footer">x</div>'

        found = pages.page_photos(markup)

        assert (found[0].credit, found[0].credit_basis) == ("Daniel Chazin", "caption")

    def test_an_ampersand_in_a_name_survives_exactly_once(self):
        """`photo_credit` must not unescape what its callers already
        unescaped. `Photo by Smith &amp; Co` is a page that says "Smith & Co";
        unescaping twice would turn a page that says `Smith &amp;amp; Co` into
        one that does not, and inventing a credit is the one thing a licence
        conditioned on the credit cannot tolerate."""
        found = pages.page_photos('<img src="/u26/a.jpg"><p>Photo by Smith &amp; Co</p>')

        assert found[0].credit == "Smith & Co"

    def test_a_cache_an_older_parser_wrote_is_re_read_rather_than_resumed_onto(self, tmp_path):
        """A resumed run SKIPS every URL already cached, so a row an older
        parser wrote is never revisited - it is silently missing whatever the
        parser learned since. Two changes have done that (#1502's coordinate,
        #1504's credit). The cache declares its format so the run re-reads
        rather than reporting a corpus with no coordinates and no credits,
        which looks exactly like a corpus that has none."""
        path = tmp_path / "pages.json"
        path.write_text(
            json.dumps(
                {
                    "pages": [
                        {
                            "url": "https://www.nynjtc.org/hike/a",
                            "timestamp": "20190419182814",
                            "name": "A Loop",
                            "park": None,
                            "region": None,
                            "lat": None,
                            "lon": None,
                            "description": "x",
                            "photos": ["a.jpg"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )

        assert pages.load_done(path) == {}

    def test_the_cache_this_parser_writes_is_one_it_will_resume_onto(self):
        """...and the version it writes is the version it accepts, or every
        run re-reads 439 write-ups for ever."""
        assert pages.CACHE_FORMAT == 2

    def test_a_gallery_cannot_hand_one_photographs_credit_to_the_one_before_it(self):
        """The caption window stops at the NEXT u26 image, so a credit written
        under the second picture belongs to the second picture."""
        found = pages.page_photos('<img src="/u26/a.jpg"><img src="/u26/b.jpg"><p>Photo by Daniel Chazin</p>')

        assert [(p.filename, p.credit) for p in found] == [("a.jpg", None), ("b.jpg", "Daniel Chazin")]

    def test_an_uncredited_photograph_says_so_rather_than_guessing(self):
        found = pages.page_photos('<img src="/u26/a.jpg" alt="Bear Mountain from the south">')

        assert (found[0].credit, found[0].credit_basis) == (None, None)

    def test_a_name_that_runs_past_its_punctuation_is_refused_not_truncated(self):
        """_PHOTO_BY ends its capture at punctuation, so a credit in a sentence
        with none runs on into the body text. A capture that long is evidence
        the pattern never found the end of the name, and under a licence
        conditioned on the credit the honest answer is no credit at all."""
        markup = "<p>Photo credit: Daniela Wagstaff " + ("word " * 40) + '</p><img src="/u26/a.jpg">'

        assert pages.page_photos(markup)[0].credit is None

    def test_the_photographers_name_survives_an_html_entity(self):
        """Unescaped BEFORE matching: _PHOTO_BY stops at `;`, so matching the
        raw attribute returned a surname-less "Jos&eacute"."""
        found = pages.page_photos('<img src="/u26/a.jpg" alt="Photo by Jos&eacute; Ramos">')

        assert found[0].credit == "Jos\u00e9 Ramos"

    def test_the_credit_is_a_name_and_not_the_end_of_the_tag(self):
        """The regression the first version of this shipped: running _PHOTO_BY
        over raw tag markup captured `Daniel Chazin" />`, because the pattern
        stops at punctuation and a tag ends in none of it. Attributes are read
        as VALUES for this reason."""
        found = pages.page_photos('<img src="/u26/a.jpg" alt="Photo by Daniel Chazin" />')

        assert found[0].credit == "Daniel Chazin"

    def test_one_photograph_shown_twice_keeps_the_credited_reading(self):
        """A thumbnail and the full image are one photograph. The thumbnail
        comes first and carries nothing; dropping the credit with the duplicate
        would withhold a photograph the page does credit."""
        found = pages.page_photos('<img src="/u26/styles/thumbnail/a.jpg"><img src="/u26/a.jpg" alt="Photo by Daniel Chazin">')

        assert [(p.filename, p.credit) for p in found] == [("a.jpg", "Daniel Chazin")]

    def test_a_credit_split_across_a_tag_withholds_rather_than_mis_attributes(self):
        """A KNOWN MISS, asserted so it stays deliberate. Joining the text
        either side of the <a> would catch this AND would join two unrelated
        paragraphs elsewhere, which can name the wrong photographer. Withheld
        is the direction to fail in; `--probe` is what says whether these pages
        write it this way at all."""
        found = pages.page_photos('<img src="/u26/a.jpg"><p>Photo by <a href="/bio">Daniel Chazin</a></p>')

        assert found[0].credit is None

    def test_a_resumed_run_rebuilds_the_records_rather_than_dicts(self, tmp_path):
        """asdict() flattens PagePhoto on the way out. A resumed run that left
        them as dicts would carry pages whose credits nothing downstream could
        read - and the gate would then refuse photographs the page does credit.
        """
        cache = tmp_path / "pages.json"
        written = pages.parse_page(
            '<title>X</title><img src="/u26/a.jpg" alt="Photo by Daniel Chazin">',
            "https://www.nynjtc.org/hike/x",
            "20190419182814",
        )
        pages.write_cache([written], ["https://www.nynjtc.org/hike/x"], cache)

        read = pages.load_done(cache)["https://www.nynjtc.org/hike/x"]

        assert read.photos == [pages.PagePhoto(filename="a.jpg", credit="Daniel Chazin", credit_basis="img")]
