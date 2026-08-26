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


class StreamedResponse:
    """A response whose BODY can fail, which requests_mock cannot stage: the
    faults download_with_retry exists for land inside iter_content, after the
    request call already returned (#1063)."""

    def __init__(self, *, status=200, chunks=(b"",), fail_after=None):
        self.status_code = status
        self.headers = {}
        self._chunks = chunks
        self._fail_after = fail_after

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_content(self, chunk_size):
        for index, chunk in enumerate(self._chunks):
            if index == self._fail_after:
                raise requests.exceptions.ChunkedEncodingError("connection reset mid-body")
            yield chunk

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))


class ScriptedSession:
    """One scripted answer per attempt - a response, or an exception to raise
    from the request call itself (a handshake that never completed)."""

    def __init__(self, script):
        self.script = list(script)

    def request(self, method, url, **kwargs):
        step = self.script.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


class TestDownloadWithRetry:
    def test_the_reset_that_killed_run_33005545820_is_survived(self, tmp_path, naps):
        """Attempt 1 of that run: ConnectionResetError mid-body on the seventh
        state extract, ~1.7 GB in. The transfer should have been re-pulled -
        the same mirror served the file whole on the next day's run."""
        dest = tmp_path / "pennsylvania-latest.osm.pbf"
        session = ScriptedSession(
            [
                StreamedResponse(chunks=(b"first-", b"half"), fail_after=1),
                StreamedResponse(chunks=(b"whole-", b"file")),
            ]
        )

        result = download_with_retry("https://geofabrik.example/pa.pbf", dest, session=session, sleep=naps.append)

        assert result == dest
        assert dest.read_bytes() == b"whole-file"
        assert naps == [DEFAULT_BACKOFF_SECONDS[0]]
        assert not dest.with_suffix(".part").exists()

    def test_a_handshake_that_never_completed_is_retried(self, tmp_path, naps):
        """Attempt 2 of the same run: the TLS handshake timed out and surfaced
        as a ReadTimeout before any byte arrived."""
        dest = tmp_path / "north-carolina-latest.osm.pbf"
        session = ScriptedSession(
            [
                requests.exceptions.ReadTimeout("Read timed out. (read timeout=600)"),
                StreamedResponse(chunks=(b"extract",)),
            ]
        )

        download_with_retry("https://geofabrik.example/nc.pbf", dest, session=session, sleep=naps.append)

        assert dest.read_bytes() == b"extract"
        assert naps == [DEFAULT_BACKOFF_SECONDS[0]]

    def test_the_budget_spent_leaves_no_file_at_all(self, tmp_path, naps):
        """dest is only ever a completed transfer: a caller that finds it on
        disk must be able to trust it, so a spent budget leaves neither dest
        nor a .part for skip-if-present to mistake for one."""
        dest = tmp_path / "vermont-latest.osm.pbf"
        session = ScriptedSession(
            [StreamedResponse(chunks=(b"x",), fail_after=0) for _ in range(len(DEFAULT_BACKOFF_SECONDS) + 1)]
        )

        with pytest.raises(requests.exceptions.ChunkedEncodingError):
            download_with_retry("https://geofabrik.example/vt.pbf", dest, session=session, sleep=naps.append)

        assert not dest.exists()
        assert not dest.with_suffix(".part").exists()
        assert naps == list(DEFAULT_BACKOFF_SECONDS)

    def test_a_retryable_status_waits_and_asks_again(self, tmp_path, naps):
        dest = tmp_path / "maine-latest.osm.pbf"
        session = ScriptedSession([StreamedResponse(status=503), StreamedResponse(chunks=(b"data",))])

        download_with_retry("https://geofabrik.example/me.pbf", dest, session=session, sleep=naps.append)

        assert dest.read_bytes() == b"data"
        assert naps == [DEFAULT_BACKOFF_SECONDS[0]]

    def test_a_refusal_raises_immediately_and_writes_nothing(self, tmp_path, naps):
        dest = tmp_path / "georgia-latest.osm.pbf"
        session = ScriptedSession([StreamedResponse(status=404)])

        with pytest.raises(requests.HTTPError):
            download_with_retry("https://geofabrik.example/ga.pbf", dest, session=session, sleep=naps.append)

        assert naps == []
        assert not dest.exists()

    def test_an_orphaned_part_is_truncated_never_resumed(self, tmp_path, naps):
        """#1063's own scoping: no Range resume. Against a source that
        republishes daily, a resume straddling a republish would splice two
        different files into one archive - so a stale .part is overwritten,
        never appended to."""
        dest = tmp_path / "georgia-latest.osm.pbf"
        dest.with_suffix(".part").write_bytes(b"stale-half-of-yesterdays-file")
        session = ScriptedSession([StreamedResponse(chunks=(b"fresh",))])

        download_with_retry("https://geofabrik.example/ga.pbf", dest, session=session, sleep=naps.append)

        assert dest.read_bytes() == b"fresh"
