"""Tests for fetch_wayback_hike_photos.py - the one-time recovery of NYNJTC's
hike photographs from the Internet Archive (#1450).

All HTTP is mocked (TESTING.md: real network calls never fire in tests).

Three tests here are load-bearing, and each pins a mistake that was actually
made rather than one imagined for the occasion:

  - **The latest capture, not the first.** A CDX query with `collapse=urlkey`
    returns the FIRST capture of each URL. The first pass at this work read
    2019 for the whole corpus without noticing, and older captures of a site
    that has since changed are exactly what the maintainer asked to avoid.
  - **HTML is not a JPEG.** The archive answers a missing capture with an
    error page at HTTP 200 often enough that trusting the status would store
    web pages under `.jpg` names, which publish.py would then upload.
  - **A failed request is not an absent photograph.** This run's output is a
    count of what survived, so a fault reported as "not archived" would turn a
    network problem into a finding about the world.
"""

import json
import struct

import pytest
import requests

import fetch_wayback_hike_photos as fetch
from lib import wayback_rate

CDX = fetch.CDX_API


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
        fetch,
        "ARCHIVE",
        wayback_rate.RateLimit(max_requests=10_000, clock=lambda: 0.0, sleep=lambda _s: None),
    )


def _session():
    return requests.Session()


def _no_sleep(monkeypatch):
    monkeypatch.setattr(fetch.time, "sleep", lambda _s: None)


def _cdx(*rows):
    """A CDX answer in the real shape: a header row, then the data."""
    return [["original", "timestamp", "length"], *[list(r) for r in rows]]


def jpeg_bytes(width=250, height=188):
    """The smallest thing that parses as a JPEG with a readable frame size."""
    return b"\xff\xd8" + b"\xff\xc0" + struct.pack(">H", 17) + b"\x08" + struct.pack(">HH", height, width) + b"\x00" * 8


# --- the latest capture, not the first -----------------------------------------


def test_the_most_recent_capture_of_each_url_wins(monkeypatch, requests_mock):
    """THE test of this module. Same URL, three captures: the 2024 one is the
    answer. Taking the first would pin a changed site to its oldest state."""
    _no_sleep(monkeypatch)
    url = "https://www.nynjtc.org/sites/default/files/u26/Awosting%20Falls.jpg"
    requests_mock.get(
        CDX,
        json=_cdx(
            (url, "20190419182814", "58086"),
            (url, "20240103091500", "58090"),
            (url, "20211019214326", "58088"),
        ),
    )

    captures = fetch.latest_captures(_session())

    assert len(captures) == 1
    assert captures[0].timestamp == "20240103091500"


def test_collapse_urlkey_is_not_asked_for(monkeypatch, requests_mock):
    """`collapse=digest` is fine and is asked for - it drops repeat captures of
    identical bytes. `collapse=urlkey` is the dangerous one: it collapses by
    URL and hands back each URL's FIRST capture, which is the bug this
    module's docstring opens with. So the guard is on the VALUE, not on the
    parameter's presence.

    This test caught its own obsolescence when digest collapsing was added,
    which is the behaviour wanted from it."""
    _no_sleep(monkeypatch)
    requests_mock.get(CDX, json=_cdx())

    fetch.latest_captures(_session())

    assert requests_mock.request_history[0].qs.get("collapse") != ["urlkey"]


def test_distinct_urls_are_all_kept(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    requests_mock.get(
        CDX,
        json=_cdx(
            ("https://www.nynjtc.org/sites/default/files/u26/a.jpg", "20190419182814", "100"),
            ("https://www.nynjtc.org/sites/default/files/u26/b.jpg", "20190419182815", "200"),
        ),
    )

    assert len(fetch.latest_captures(_session())) == 2


def test_a_row_without_a_length_is_dropped_rather_than_crashing(monkeypatch, requests_mock):
    """CDX writes '-' for a length it does not have."""
    _no_sleep(monkeypatch)
    requests_mock.get(
        CDX,
        json=_cdx(
            ("https://www.nynjtc.org/sites/default/files/u26/a.jpg", "20190419182814", "-"),
            ("https://www.nynjtc.org/sites/default/files/u26/b.jpg", "20190419182815", "200"),
        ),
    )

    captures = fetch.latest_captures(_session())

    assert [c.filename for c in captures] == ["b.jpg"]


def test_an_empty_archive_answer_is_not_a_crash(monkeypatch, requests_mock):
    _no_sleep(monkeypatch)
    requests_mock.get(CDX, json=[])

    assert fetch.latest_captures(_session()) == []


def test_the_fetch_url_asks_for_the_original_bytes():
    """`id_` is what separates the image from the archive's page furniture."""
    capture = fetch.Capture("https://www.nynjtc.org/sites/default/files/u26/a.jpg", "20240103091500", 100)

    assert (
        capture.fetch_url == "https://web.archive.org/web/20240103091500id_/https://www.nynjtc.org/sites/default/files/u26/a.jpg"
    )


# --- HTML is not a JPEG --------------------------------------------------------


def test_an_archive_error_page_is_refused_even_at_http_200(monkeypatch, requests_mock, tmp_path):
    """The archive really does serve HTML at 200 for a capture it cannot
    produce. Storing it would put a web page in the content-addressed store
    under a name ending .jpg, and publish.py uploads whatever is there."""
    _no_sleep(monkeypatch)
    capture = fetch.Capture("https://www.nynjtc.org/sites/default/files/u26/a.jpg", "20240103091500", 100)
    requests_mock.get(capture.fetch_url, content=b"<html><body>Not in archive</body></html>")

    assert fetch.recover(_session(), capture, tmp_path) is None
    assert list(tmp_path.rglob("*.jpg")) == []


def test_a_real_jpeg_lands_in_the_content_addressed_store(monkeypatch, requests_mock, tmp_path):
    _no_sleep(monkeypatch)
    capture = fetch.Capture("https://www.nynjtc.org/sites/default/files/u26/a.jpg", "20240103091500", 100)
    requests_mock.get(capture.fetch_url, content=jpeg_bytes(250, 188))

    got = fetch.recover(_session(), capture, tmp_path)

    assert got is not None
    assert got.width == 250 and got.height == 188
    assert fetch.local_photo_path(tmp_path, got.digest).exists()


def test_a_failed_request_is_one_missing_photo_rather_than_a_dead_run(monkeypatch, requests_mock, tmp_path):
    """A fault must not be reported as "the archive does not have it"."""
    _no_sleep(monkeypatch)
    capture = fetch.Capture("https://www.nynjtc.org/sites/default/files/u26/a.jpg", "20240103091500", 100)
    requests_mock.get(capture.fetch_url, status_code=404)

    assert fetch.recover(_session(), capture, tmp_path) is None


def test_the_same_bytes_are_written_once(monkeypatch, requests_mock, tmp_path):
    """Content addressing dedupes by construction; this pins that a second
    capture of an unchanged image costs no second file."""
    _no_sleep(monkeypatch)
    one = fetch.Capture("https://www.nynjtc.org/sites/default/files/u26/a.jpg", "20240103091500", 100)
    two = fetch.Capture("https://www.nynjtc.org/sites/default/files/u26/b.jpg", "20240103091501", 100)
    requests_mock.get(one.fetch_url, content=jpeg_bytes())
    requests_mock.get(two.fetch_url, content=jpeg_bytes())

    first = fetch.recover(_session(), one, tmp_path)
    second = fetch.recover(_session(), two, tmp_path)

    assert first.digest == second.digest
    assert len(list(tmp_path.rglob("*.jpg"))) == 1


def test_no_part_file_is_left_behind(monkeypatch, requests_mock, tmp_path):
    _no_sleep(monkeypatch)
    capture = fetch.Capture("https://www.nynjtc.org/sites/default/files/u26/a.jpg", "20240103091500", 100)
    requests_mock.get(capture.fetch_url, content=jpeg_bytes())

    fetch.recover(_session(), capture, tmp_path)

    assert list(tmp_path.rglob("*.part")) == []


# --- dimensions, which decide the frame the card gives it ----------------------


@pytest.mark.parametrize(("width", "height"), [(250, 188), (4000, 3000), (155, 207), (1938, 479)])
def test_dimensions_are_read_off_the_jpeg_itself(width, height):
    """The phone picks a hero box or a crisp inset from these, so a dimension
    the pipeline does not know is a decision the card cannot make."""
    assert fetch.jpeg_dimensions(jpeg_bytes(width, height)) == (width, height)


def test_a_jpeg_with_no_readable_frame_gives_none_rather_than_a_guess():
    assert fetch.jpeg_dimensions(b"\xff\xd8" + b"\x00" * 20) is None


# --- the filename as a description of the photograph ---------------------------


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        # The real ones, read off the archive 2026-09-15.
        (
            "Ashokan Reservoir from the viewpoint on Cross Mountain 250 IMG_1574.jpg",
            "Ashokan Reservoir from the viewpoint on Cross Mountain",
        ),
        ("Balsam Lake Mountain fire tower 2 155 IMG_5794.jpg", "Balsam Lake Mountain fire tower 2"),
        (
            "Beaver Lodge in swamp on Terrace Pond South Trail  250 x 188 MG_8444.jpg",
            "Beaver Lodge in swamp on Terrace Pond South Trail",
        ),
        ("Awosting Falls. Photo by Keith Shane. 250 0105151418a.jpg", "Awosting Falls"),
    ],
)
def test_the_subject_survives_and_the_file_noise_does_not(filename, expected):
    """These filenames are why this corpus can be matched at all - NYNJTC
    named each file after the thing in it. What has to go is the rendition
    width and the camera serial, which describe the file rather than a place."""
    assert fetch.subject_from(filename) == expected


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("Awosting Falls. Photo by Keith Shane. 250 0105151418a.jpg", "Keith Shane"),
        ("Some View photo by jane doe 250.jpg", "jane doe"),
        ("Balsam Lake Mountain fire tower 2 155 IMG_5794.jpg", None),
    ],
)
def test_a_credit_in_the_filename_is_read_and_absence_is_not_invented(filename, expected):
    """The credit is the licence's condition (#1450). One found here is
    measured; absence means this filename does not say, which is a different
    thing from "no photographer" and is recorded as None."""
    assert fetch.credit_from(filename) == expected


# --- the run -------------------------------------------------------------------


def test_listing_fetches_no_images(monkeypatch, requests_mock, capsys):
    """--list must answer "what is there" without spending the archive's
    bandwidth on 403 downloads."""
    _no_sleep(monkeypatch)
    requests_mock.get(
        CDX,
        json=_cdx(("https://www.nynjtc.org/sites/default/files/u26/a.jpg", "20240103091500", "100")),
    )

    assert fetch.run(["--list"]) == 0
    assert len(requests_mock.request_history) == 1
    assert "2024" in capsys.readouterr().out


def test_an_archive_that_answers_nothing_exits_non_zero(monkeypatch, requests_mock, capsys):
    """Zero images is either the archive failing or the prefix being wrong.
    Either way it is not a successful recovery of nothing."""
    _no_sleep(monkeypatch)
    requests_mock.get(CDX, json=[])

    assert fetch.run(["--list"]) == 1
    assert "by hand before believing" in capsys.readouterr().out


def test_the_record_written_carries_what_a_matcher_and_a_card_both_need(monkeypatch, requests_mock, tmp_path, capsys):
    _no_sleep(monkeypatch)
    monkeypatch.setattr(fetch, "RAW_DIR", tmp_path)
    monkeypatch.setattr(fetch, "OUT_PATH", tmp_path / "wayback_hike_photos.json")
    url = "https://www.nynjtc.org/sites/default/files/u26/Awosting%20Falls.%20Photo%20by%20Keith%20Shane.%20250.jpg"
    requests_mock.get(CDX, json=_cdx((url, "20240103091500", "100")))
    requests_mock.get(f"https://web.archive.org/web/20240103091500id_/{url}", content=jpeg_bytes(250, 188))

    assert fetch.run([]) == 0

    written = json.loads((tmp_path / "wayback_hike_photos.json").read_text(encoding="utf-8"))
    assert written["one_time"] is True
    photo = written["photos"][0]
    assert photo["subject"] == "Awosting Falls"
    assert photo["credit"] == "Keith Shane"
    assert photo["width"] == 250
    assert photo["timestamp"] == "20240103091500"
    assert photo["digest"]


def test_an_unknown_flag_is_rejected_rather_than_silently_ignored():
    with pytest.raises(SystemExit) as excinfo:
        fetch.run(["--lst"])

    assert excinfo.value.code == 2


# --- two defects the first run actually had ------------------------------------


def test_a_rendition_size_after_an_underscore_is_still_stripped():
    """`_` is a word character, so `\\b` does not fire between it and a digit.
    The first run of this left "Bridge_300x420" carrying its rendition size
    into the matcher as if it were part of the place's name. Separators are
    turned into spaces before any of the digit patterns run, which is the fix
    and the reason the order in subject_from() is not arbitrary."""
    assert (
        fetch.subject_from("AccessibleSectionIncludingWoodenBridge_300x420.jpg") == "Accessible Section Including Wooden Bridge"
    )


@pytest.mark.parametrize(
    ("filename", "contains"),
    [
        # The landmark is buried in the run and invisible without the split.
        ("AccessibleTrailAlongHugeBoulderJustBeforeMajorWelchJunction_420x300_0.jpg", "Major Welch Junction"),
        ("AlongTheManaticutPointTrail copy_0.jpg", "Manaticut Point Trail"),
        ("SplitRockOnTheWayToDennyMine_0.JPG", "Denny Mine"),
    ],
)
def test_a_landmark_buried_in_camel_case_is_recovered(filename, contains):
    """About a third of this corpus is named without separators. A matcher
    comparing words cannot see "Major Welch Junction" until the words exist,
    so this is what makes those rows matchable at all rather than a cosmetic
    tidy-up."""
    assert contains in fetch.subject_from(filename)


def test_an_acronym_is_split_off_its_following_word():
    """ "AT-IrisLoop" is the Appalachian Trail's Iris Loop, and "ATIris" is
    nothing."""
    assert fetch.subject_from("Apgar_AT-IrisLoop-HighPoint-2 250.jpg").startswith("Apgar AT Iris Loop High Point")


def test_the_camera_serial_survives_neither_spelling():
    """_split_camel_case runs first and turns "IMG_1574" into "IMG 1574", so
    the noise pattern has to allow the space it just introduced. Missing this
    put "IMG" and "1574" into the matcher's tokens."""
    assert (
        fetch.subject_from("Ashokan Reservoir from the viewpoint on Cross Mountain 250 IMG_1574.jpg")
        == "Ashokan Reservoir from the viewpoint on Cross Mountain"
    )
    assert (
        fetch.subject_from("Beaver Lodge in swamp on Terrace Pond South Trail  250 x 188 MG_8444.jpg")
        == "Beaver Lodge in swamp on Terrace Pond South Trail"
    )


# --- what the block on 2026-09-15 bought ---------------------------------------


def test_every_request_passes_the_shared_ceiling(monkeypatch, requests_mock):
    """THIS fetcher is the one that caused the block: one request a second over
    403 images - about 60 a minute - earning 429s, then 503s, then an outright
    refusal of the egress IP (curl returning 000, no HTTP status at all).
    Confirmed host-specific at the time, since iNaturalist answered 200 in the
    same minute.

    It no longer paces itself with a sleep. What is asserted is the BEHAVIOUR
    rather than which object it holds: a retry is a request, so a call that
    fails once and succeeds on the second attempt must take TWO slots. A
    sleep-based throttle counted one, which is how a polite-looking backoff
    ladder exceeds its own ceiling."""
    _no_sleep(monkeypatch)
    taken = []
    monkeypatch.setattr(fetch.ARCHIVE, "take", lambda: taken.append(1) or 0.0)
    requests_mock.get(CDX, [{"status_code": 503}, {"json": _cdx()}])

    fetch.latest_captures(_session())

    assert len(taken) == 2
    assert wayback_rate.MAX_REQUESTS_PER_MINUTE <= 10


def test_identical_captures_collapse_to_one_row(monkeypatch, requests_mock):
    """`collapse=digest` asks the archive not to send the same bytes twice.
    Distinct from `collapse=urlkey`, which collapses by URL and returns the
    FIRST capture - the bug this module's docstring opens with."""
    _no_sleep(monkeypatch)
    requests_mock.get(CDX, json=_cdx())

    fetch.latest_captures(_session())

    assert requests_mock.request_history[0].qs["collapse"] == ["digest"]
