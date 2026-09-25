"""Tests for fetch_weather.py (#1056): which cycle is used, and what "complete"
means, since a half-landed cycle is a card whose later hours are silently
another run's."""

from datetime import UTC, datetime, timedelta

import pytest

import fetch_weather

CYCLE = datetime(2026, 9, 25, 11, tzinfo=UTC)


def key(field: str, valid: datetime, cycle: datetime = CYCLE) -> str:
    return (
        f"blendv5.0/conus/{cycle:%Y/%m/%d/%H}00/{field}/blendv5.0_conus_{field}_{cycle:%Y-%m-%dT%H:%M}_{valid:%Y-%m-%dT%H:%M}.tif"
    )


def full_listing() -> dict[str, list[str]]:
    listings = {field: [key(field, CYCLE + timedelta(hours=h)) for h in range(0, 60)] for field in fetch_weather.HOURLY}
    for field in fetch_weather.PERIODS:
        listings[field] = [key(field, CYCLE + timedelta(hours=h)) for h in range(6, 24 * 9, 12)]
    return listings


def test_the_newest_blend_version_is_chosen_by_number_not_by_spelling():
    roots = ["blendv4.3/", "blendv10.0/", "blendv5.0/", "index.html/"]

    assert fetch_weather.newest_version(roots) == "blendv10.0"


def test_a_bucket_with_no_blend_prefix_is_an_error_not_a_guess():
    with pytest.raises(RuntimeError):
        fetch_weather.newest_version(["other/"])


def test_cycles_come_back_newest_first():
    prefixes = [f"blendv5.0/conus/2026/09/25/{h:02d}00/" for h in (9, 11, 10)]

    assert [t.hour for t in fetch_weather.cycle_times(prefixes)] == [11, 10, 9]


def test_a_files_valid_time_is_the_second_stamp_in_its_name():
    assert fetch_weather.valid_time(key("temp", CYCLE + timedelta(hours=3))) == CYCLE + timedelta(hours=3)
    assert fetch_weather.valid_time("blendv5.0/conus/index.html") is None


def test_a_complete_cycle_yields_exactly_the_hours_the_card_uses():
    chosen = fetch_weather.needed(CYCLE, full_listing())

    assert chosen is not None
    assert [t for t, _ in chosen["temp"]] == [CYCLE + timedelta(hours=h) for h in range(1, 49)]
    # Thunder probability stops at 36 hours, and nothing pads it to 48.
    assert len(chosen["tstm01"]) == 36


def test_period_fields_stop_at_a_week():
    chosen = fetch_weather.needed(CYCLE, full_listing())

    horizon = CYCLE + timedelta(hours=fetch_weather.PERIOD_HORIZON_HOURS)
    assert all(CYCLE < t <= horizon for t, _ in chosen["maxt"])
    assert max(t for t, _ in chosen["maxt"]) > horizon - timedelta(hours=12)


def test_a_cycle_missing_one_hourly_file_is_not_complete():
    listings = full_listing()
    listings["sky"] = [k for k in listings["sky"] if fetch_weather.valid_time(k) != CYCLE + timedelta(hours=30)]

    assert fetch_weather.needed(CYCLE, listings) is None


def test_a_cycle_missing_a_whole_period_field_is_not_complete():
    listings = full_listing()
    listings["mint"] = []

    assert fetch_weather.needed(CYCLE, listings) is None


class FakeResponse:
    def __init__(self, text):
        self.text = text


def test_listing_follows_continuation_tokens(monkeypatch):
    pages = [
        "<ListBucketResult><Prefix>p/</Prefix><Contents><Key>p/a.tif</Key></Contents>"
        "<NextContinuationToken>t1</NextContinuationToken></ListBucketResult>",
        "<ListBucketResult><Prefix>p/</Prefix><Contents><Key>p/b.tif</Key></Contents>"
        "<CommonPrefixes><Prefix>p/sub/</Prefix></CommonPrefixes></ListBucketResult>",
    ]
    seen = []

    def fake_request(url, *, session, params, label):
        seen.append(dict(params))
        return FakeResponse(pages[len(seen) - 1])

    monkeypatch.setattr(fetch_weather, "request_with_retry", fake_request)

    keys, prefixes = fetch_weather.list_bucket(None, "p/", delimiter="/")

    assert keys == ["p/a.tif", "p/b.tif"]
    assert prefixes == ["p/sub/"]  # the echoed request prefix is not a result
    assert seen[1]["continuation-token"] == "t1"
