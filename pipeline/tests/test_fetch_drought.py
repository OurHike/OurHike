"""Which week the drought fetch asks for, and when it declines to ask at all.

Three behaviours carry the weight here, and none of them is the download:

  - **The stamp.** A USDM week is named by its Tuesday, so the whole fetch
    hangs on turning "today" into the right Tuesday and walking back from it.
  - **The walk.** A release lands on Thursday for the Tuesday just gone, so a
    404 on a Tuesday or Wednesday means "not published yet" and has to be an
    ordinary path rather than a failure.
  - **The skip.** A release is 27.6 MB and changes weekly. Anything above a
    daily cadence depends on the fetcher noticing it already has the week.
"""

from __future__ import annotations

import json
import urllib.error
from datetime import date

import pytest

import fetch_drought


@pytest.fixture
def out_dir(tmp_path, monkeypatch):
    directory = tmp_path / "drought"
    directory.mkdir()
    monkeypatch.setattr(fetch_drought, "OUT_DIR", directory)
    monkeypatch.setattr(fetch_drought.fetch_receipts, "record", lambda *args, **kwargs: None)
    return directory


def release(features: int = 3) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"DM": index}, "geometry": {"type": "Polygon", "coordinates": []}}
            for index in range(features)
        ],
    }


class TestReleaseStamp:
    @pytest.mark.parametrize(
        ("today", "expected"),
        [
            (date(2026, 8, 11), date(2026, 8, 11)),  # a Tuesday is its own stamp
            (date(2026, 8, 12), date(2026, 8, 11)),  # Wednesday, before Thursday's release
            (date(2026, 8, 13), date(2026, 8, 11)),  # release day
            (date(2026, 8, 17), date(2026, 8, 11)),  # the Monday the week ends on
            (date(2026, 8, 18), date(2026, 8, 18)),  # the next Tuesday starts a new week
        ],
    )
    def test_the_week_is_named_by_its_tuesday(self, today, expected):
        assert fetch_drought.release_stamp_for(today) == expected

    def test_candidates_walk_backwards_a_week_at_a_time(self):
        stamps = fetch_drought.candidate_stamps(date(2026, 8, 13))
        assert stamps[0] == date(2026, 8, 11)
        assert stamps[1] == date(2026, 8, 4)
        assert len(stamps) == fetch_drought.MAX_WEEKS_BACK + 1


class TestWalkingBack:
    def test_an_unpublished_week_is_not_an_error(self, out_dir, monkeypatch):
        """The Tuesday/Wednesday case, which is two days in every seven."""
        asked = []

        def fake(stamp):
            asked.append(stamp)
            return None if stamp == date(2026, 8, 11) else release()

        monkeypatch.setattr(fetch_drought, "fetch_release", fake)
        path = fetch_drought.main(today=date(2026, 8, 12))

        assert asked == [date(2026, 8, 11), date(2026, 8, 4)]
        assert path.name == "usdm_20260804.json"

    def test_running_out_of_weeks_refuses_rather_than_publishing_something_old(self, out_dir, monkeypatch):
        monkeypatch.setattr(fetch_drought, "fetch_release", lambda stamp: None)
        with pytest.raises(SystemExit) as exit_info:
            fetch_drought.main(today=date(2026, 8, 13))
        assert "a claim about this week" in str(exit_info.value)


class TestSkippingWhatIsAlreadyHere:
    def test_an_existing_release_is_not_downloaded_again(self, out_dir, monkeypatch):
        (out_dir / "usdm_20260811.json").write_text(json.dumps(release()))

        def refuse(stamp):
            raise AssertionError(f"downloaded {stamp} when the file was already on disk")

        monkeypatch.setattr(fetch_drought, "fetch_release", refuse)
        path = fetch_drought.main(today=date(2026, 8, 13))
        assert path == out_dir / "usdm_20260811.json"

    def test_a_stale_release_on_disk_does_not_satisfy_a_newer_week(self, out_dir, monkeypatch):
        """Last week's file must not stop this week's fetch - the failure that
        would turn an hourly job into one that never notices Thursday."""
        (out_dir / "usdm_20260804.json").write_text(json.dumps(release()))
        monkeypatch.setattr(fetch_drought, "fetch_release", lambda stamp: release())

        path = fetch_drought.main(today=date(2026, 8, 13))
        assert path.name == "usdm_20260811.json"


class TestRefusingBadBodies:
    def test_a_short_body_is_refused(self, monkeypatch):
        monkeypatch.setattr(fetch_drought, "MIN_PLAUSIBLE_BYTES", 1_000)
        monkeypatch.setattr(fetch_drought.urllib.request, "urlopen", _responding(b"nope"))
        with pytest.raises(SystemExit) as exit_info:
            fetch_drought.fetch_release(date(2026, 8, 11))
        assert "map of nothing" in str(exit_info.value)

    def test_a_body_with_no_features_is_refused(self, monkeypatch):
        body = json.dumps({"type": "FeatureCollection", "features": []}).encode()
        monkeypatch.setattr(fetch_drought, "MIN_PLAUSIBLE_BYTES", 1)
        monkeypatch.setattr(fetch_drought.urllib.request, "urlopen", _responding(body))
        with pytest.raises(SystemExit) as exit_info:
            fetch_drought.fetch_release(date(2026, 8, 11))
        assert "no features" in str(exit_info.value)

    def test_a_404_is_a_missing_week_and_not_a_crash(self, monkeypatch):
        def raise_404(url, timeout=None):
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

        monkeypatch.setattr(fetch_drought.urllib.request, "urlopen", raise_404)
        assert fetch_drought.fetch_release(date(2026, 8, 11)) is None

    def test_any_other_http_error_still_raises(self, monkeypatch):
        def raise_500(url, timeout=None):
            raise urllib.error.HTTPError(url, 500, "Server Error", {}, None)

        monkeypatch.setattr(fetch_drought.urllib.request, "urlopen", raise_500)
        with pytest.raises(urllib.error.HTTPError):
            fetch_drought.fetch_release(date(2026, 8, 11))


def _responding(body: bytes):
    class Response:
        def read(self):
            return body

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def urlopen(url, timeout=None):
        return Response()

    return urlopen
