"""Tests for lib/http_retry.py.

The centrepiece is `test_the_504_that_threw_away_a_publish_is_survived`: it
reproduces the exact response that killed run 31592776758 - a 504 from
tnmaccess.nationalmap.gov on the first of 51 corridor cells, 35 seconds into a
publish that had already fetched sources and exported trails, POIs and spurs
(#536).

`sleep` is injected throughout rather than patched globally, so the ladder can
be asserted exactly without a test that waits two minutes to prove it waits
two minutes.
"""

from __future__ import annotations

import io

import pytest
import requests

from lib.http_retry import (
    DEFAULT_BACKOFF_SECONDS,
    DEFAULT_RETRYABLE_STATUSES,
    MAX_RETRY_AFTER_SECONDS,
    download_with_retry,
    request_with_retry,
    retry_after_seconds,
)

URL = "https://tnmaccess.nationalmap.gov/api/v1/products"


@pytest.fixture
def naps():
    """Every sleep the helper asked for, in order."""
    recorded: list[float] = []
    return recorded


class TestTheFaultThisExistsFor:
    def test_the_504_that_threw_away_a_publish_is_survived(self, requests_mock, naps):
        """USGS answered 504 on the first cell and the run died. It should
        have waited and asked again - the same endpoint answered 200 an hour
        either side."""
        requests_mock.get(
            URL,
            [
                {"status_code": 504, "text": "Gateway Timeout"},
                {"json": {"items": [{"downloadURL": "https://example/tile.tif"}], "total": 1}},
            ],
        )

        response = request_with_retry(URL, sleep=naps.append)

        assert response.json()["total"] == 1
        assert naps == [DEFAULT_BACKOFF_SECONDS[0]]

    def test_a_flake_on_every_attempt_still_raises(self, requests_mock, naps):
        """Retrying is not pretending. Once the budget is spent the run stops,
        because an artifact built on a fetch that never succeeded is worse
        than no artifact."""
        requests_mock.get(URL, status_code=504)

        with pytest.raises(requests.HTTPError, match="504"):
            request_with_retry(URL, sleep=naps.append)

        assert naps == list(DEFAULT_BACKOFF_SECONDS)

    def test_a_connection_fault_is_retried_too(self, requests_mock, naps):
        requests_mock.get(URL, [{"exc": requests.ConnectionError}, {"json": {"items": []}}])

        assert request_with_retry(URL, sleep=naps.append).json() == {"items": []}
        assert naps == [DEFAULT_BACKOFF_SECONDS[0]]


class TestWhatMustNotBeRetried:
    @pytest.mark.parametrize("status", [400, 401, 403, 404, 410])
    def test_a_refusal_raises_immediately_rather_than_spending_the_budget(self, requests_mock, naps, status):
        """A 4xx that is not 429 is the host answering, not flaking. Asking
        four more times would delay a real failure by two minutes and change
        nothing."""
        requests_mock.get(URL, status_code=status)

        with pytest.raises(requests.HTTPError):
            request_with_retry(URL, sleep=naps.append)

        assert naps == []

    def test_429_is_retried_because_it_means_ask_again(self, requests_mock, naps):
        requests_mock.get(URL, [{"status_code": 429}, {"json": {}}])

        request_with_retry(URL, sleep=naps.append)

        assert naps == [DEFAULT_BACKOFF_SECONDS[0]]
        assert 429 in DEFAULT_RETRYABLE_STATUSES


class TestRetryAfter:
    def test_a_server_sent_wait_wins_over_the_local_ladder(self, requests_mock, naps):
        requests_mock.get(URL, [{"status_code": 503, "headers": {"Retry-After": "7"}}, {"json": {}}])

        request_with_retry(URL, sleep=naps.append)

        assert naps == [7]

    def test_an_errant_header_cannot_park_the_build_for_an_hour(self, requests_mock, naps):
        requests_mock.get(URL, [{"status_code": 503, "headers": {"Retry-After": "99999"}}, {"json": {}}])

        request_with_retry(URL, sleep=naps.append)

        assert naps == [MAX_RETRY_AFTER_SECONDS]

    def test_an_http_date_falls_back_to_the_ladder_rather_than_crashing(self):
        response = requests.Response()
        response.headers["Retry-After"] = "Wed, 21 Oct 2026 07:28:00 GMT"

        assert retry_after_seconds(response) is None


class TestPolicyStaysTheCallers:
    def test_a_caller_can_be_more_patient(self, requests_mock, naps):
        """fetch_elevation.py is, and says why: this call runs after four
        expensive steps, so giving up costs the whole publish."""
        requests_mock.get(URL, [{"status_code": 504}, {"status_code": 504}, {"json": {}}])

        request_with_retry(URL, backoff=(1, 2, 3), sleep=naps.append)

        assert naps == [1, 2]

    def test_a_caller_can_retry_connection_faults_only(self, requests_mock, naps):
        """fetch_topo_quads.py's documented posture: it persists each quad as
        it lands, so a mid-run stop loses almost nothing and a 5xx is better
        surfaced than absorbed."""
        requests_mock.get(URL, status_code=503)

        with pytest.raises(requests.HTTPError):
            request_with_retry(URL, retryable_statuses=(), sleep=naps.append)

        assert naps == []

    def test_the_throttle_only_runs_on_success(self, requests_mock, naps):
        """Politeness is about the pace of successful calls; adding it to a
        retry would double-count the wait the ladder already imposed."""
        requests_mock.get(URL, [{"status_code": 504}, {"json": {}}])

        request_with_retry(URL, backoff=(2,), throttle_seconds=0.5, sleep=naps.append)

        assert naps == [2, 0.5]


class TestItSaysWhatItIsDoing:
    def test_a_retry_is_announced_with_the_label(self, requests_mock, naps, capsys):
        """A publish that pauses for a minute with no output looks hung. The
        label names the cell so a reader can tell which of 51 is struggling."""
        requests_mock.get(URL, [{"status_code": 504}, {"json": {}}])

        request_with_retry(URL, label="TNM cell -84.73,34.20", sleep=naps.append)

        printed = capsys.readouterr().out
        assert "TNM cell -84.73,34.20" in printed
        assert "504" in printed
        assert "1/3" in printed


class TestDownloadWithRetry:
    """`download_with_retry`, added for #1063.

    The failure it exists for: a 600-second read timeout against
    download.geofabrik.de, ten minutes into a 3.5 GB state extract, which
    ended a production publish at step 15 of 39 with nothing uploaded
    (run 33005545820).
    """

    PBF = "https://download.geofabrik.de/north-america/us/new-york-latest.osm.pbf"

    def test_the_read_timeout_that_threw_away_a_publish_is_survived(self, requests_mock, naps, tmp_path):
        requests_mock.get(
            self.PBF,
            [
                {"exc": requests.exceptions.ReadTimeout},
                {"content": b"osm-pbf-bytes"},
            ],
        )
        dest = tmp_path / "new-york-latest.osm.pbf"

        assert download_with_retry(self.PBF, dest, sleep=naps.append) == dest
        assert dest.read_bytes() == b"osm-pbf-bytes"
        assert naps == [DEFAULT_BACKOFF_SECONDS[0]]

    def test_a_flake_on_every_attempt_still_raises(self, requests_mock, naps, tmp_path):
        """Same posture as request_with_retry: retrying is not pretending. A
        run that carried on would clip and merge an extract it never got."""
        requests_mock.get(self.PBF, exc=requests.exceptions.ReadTimeout)
        dest = tmp_path / "new-york-latest.osm.pbf"

        with pytest.raises(requests.exceptions.ReadTimeout):
            download_with_retry(self.PBF, dest, sleep=naps.append)
        assert naps == list(DEFAULT_BACKOFF_SECONDS)

    def test_a_failed_transfer_leaves_neither_the_file_nor_a_part(self, requests_mock, naps, tmp_path):
        """The half-written-file rule, and the leak the hand-written loop had.

        fetch_states skips a state when `dest.exists()`, so a truncated file
        left at `dest` would be read as a complete extract on the next run.
        And the old loop's `.part` was orphaned on every failure - harmless,
        but nobody cleaned it up.
        """
        requests_mock.get(self.PBF, exc=requests.exceptions.ReadTimeout)
        dest = tmp_path / "new-york-latest.osm.pbf"

        with pytest.raises(requests.exceptions.ReadTimeout):
            download_with_retry(self.PBF, dest, sleep=naps.append)

        assert not dest.exists()
        assert list(tmp_path.iterdir()) == []

    def test_a_retryable_status_waits_and_asks_again(self, requests_mock, naps, tmp_path):
        requests_mock.get(
            self.PBF,
            [{"status_code": 503}, {"content": b"osm-pbf-bytes"}],
        )
        dest = tmp_path / "new-york-latest.osm.pbf"

        download_with_retry(self.PBF, dest, sleep=naps.append)

        assert dest.read_bytes() == b"osm-pbf-bytes"
        assert naps == [DEFAULT_BACKOFF_SECONDS[0]]

    def test_a_404_is_an_answer_and_is_not_retried(self, requests_mock, naps, tmp_path):
        """Geofabrik renaming an extract is not a flake, and asking twice
        will not change its mind - so the budget is not spent on it."""
        assert 404 not in DEFAULT_RETRYABLE_STATUSES
        requests_mock.get(self.PBF, status_code=404)
        dest = tmp_path / "new-york-latest.osm.pbf"

        with pytest.raises(requests.exceptions.HTTPError):
            download_with_retry(self.PBF, dest, sleep=naps.append)
        assert naps == []
        assert not dest.exists()

    def test_a_fault_partway_through_the_body_is_survived_too(self, requests_mock, naps, tmp_path):
        """The case a request-only retry cannot reach, and the reason the
        retry unit is the whole transfer rather than the call.

        The measured Geofabrik failure was NOT this - its traceback came out
        of `requests.get` via `adapters.send`, with no `iter_content` frame.
        This is the other half of the argument, so it is tested rather than
        asserted: here the headers arrive, iteration starts, and the body
        dies partway. `request_with_retry` has already returned by this
        point and could do nothing about it.
        """

        class DiesPartway(io.IOBase):
            def __init__(self):
                self.reads = 0

            def read(self, size=-1):
                self.reads += 1
                if self.reads == 1:
                    return b"first-chunk"
                raise requests.exceptions.ChunkedEncodingError("connection broken")

        body = DiesPartway()
        requests_mock.get(
            self.PBF,
            [{"body": body}, {"content": b"osm-pbf-bytes"}],
        )
        dest = tmp_path / "new-york-latest.osm.pbf"

        download_with_retry(self.PBF, dest, sleep=naps.append)

        # Pins this as the mid-body case rather than the request-time one:
        # the first attempt got a chunk out before it died. Without this the
        # test passes either way and proves nothing the test above did not.
        assert body.reads >= 2

        # The retry's bytes, not the dead attempt's partial ones appended to
        # them - each attempt truncates the .part rather than resuming it.
        assert dest.read_bytes() == b"osm-pbf-bytes"
        assert naps == [DEFAULT_BACKOFF_SECONDS[0]]

    def test_headers_ride_every_attempt(self, requests_mock, naps, tmp_path):
        """The second caller (#1066): fetch_trail_water.py's NHD downloads
        identify themselves with a User-Agent, and moving them onto this
        retry must not cost USGS that courtesy - on the retry either."""
        requests_mock.get(
            self.PBF,
            [{"status_code": 503}, {"content": b"osm-pbf-bytes"}],
        )
        dest = tmp_path / "new-york-latest.osm.pbf"

        download_with_retry(self.PBF, dest, headers={"User-Agent": "OurHike-pipeline"}, sleep=naps.append)

        sent = [request.headers.get("User-Agent") for request in requests_mock.request_history]
        assert sent == ["OurHike-pipeline", "OurHike-pipeline"]
