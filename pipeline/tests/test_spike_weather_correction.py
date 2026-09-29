"""Tests for spike_weather_correction.py (#1056, build step 2).

The spike's answer came from NOAA's archives, which a test must not fetch.
What is pinned here is the arithmetic the answer rests on - the correction
the phone will run, which run scores which day, and how a height is read
from the app's terrain tiles - against cases worked by hand."""

from datetime import UTC, date, datetime, timedelta

import pytest

import spike_weather_correction as spike


def test_going_up_from_the_models_height_is_colder_by_the_lapse_rate():
    # Mount Washington: HRRR's cell is 1,306 m, the summit 1,910 m.
    assert spike.correct(8.3, 1306, 1910) == pytest.approx(8.3 - 6.5 * 0.604)


def test_going_down_is_warmer_and_level_is_unchanged():
    assert spike.correct(10.0, 1000, 500) == pytest.approx(13.25)
    assert spike.correct(10.0, 700, 700) == 10.0


def test_the_lapse_rate_is_a_parameter_so_sensitivity_can_be_scored():
    assert spike.correct(0.0, 0, 1000, lapse_c_per_km=8.0) == pytest.approx(-8.0)


def test_celsius_to_fahrenheit():
    assert spike.c_to_f(0.0) == 32.0 and spike.c_to_f(100.0) == 212.0 and spike.c_to_f(-40.0) == -40.0


def test_each_local_day_is_scored_from_the_12z_run_of_the_day_before():
    run_list = spike.runs(date(2026, 7, 24), date(2026, 7, 26))

    assert run_list == [datetime(2026, 7, d, 12, tzinfo=UTC) for d in (23, 24, 25)]
    assert [spike.scored_day(r) for r in run_list] == [date(2026, 7, d) for d in (24, 25, 26)]


@pytest.mark.parametrize("offset_hours", [-4, -6, -7])
def test_forecast_hours_13_to_44_cover_the_whole_scored_day_at_every_stations_offset(offset_hours):
    run = datetime(2026, 7, 23, 12, tzinfo=UTC)
    valid = [run + timedelta(hours=h) for h in spike.FORECAST_HOURS]
    local = [v + timedelta(hours=offset_hours) for v in valid]

    hours_of_day = {t.hour for t in local if t.date() == spike.scored_day(run)}

    assert hours_of_day == set(range(24))


def test_the_days_either_side_of_the_scored_day_are_too_short_to_score():
    # At UTC-4, hours 13-44 from 12Z are 21:00 on the 23rd to 04:00 on the
    # 25th local: 3 hours of the day before and 5 of the day after, both
    # under MIN_HOURS_PER_DAY, so only the 24th can ever be scored.
    run = datetime(2026, 7, 23, 12, tzinfo=UTC)
    readings = [(run + timedelta(hours=h), float(h)) for h in spike.FORECAST_HOURS]

    # 12Z on the 23rd is 08:00 EDT, so the 24th's local hours 00-23 are
    # forecast hours 16-39, and each reading's value is its own hour.
    assert spike.extremes_for_day(readings, -4 * 3600, date(2026, 7, 24)) == (39.0, 16.0)
    assert spike.extremes_for_day(readings, -4 * 3600, date(2026, 7, 23)) is None
    assert spike.extremes_for_day(readings, -4 * 3600, date(2026, 7, 25)) is None


def test_terrarium_decodes_and_floors_to_the_apps_half_metre():
    # (R*256 + G + B/256) - 32768: 128*256 + 0 + 0 = 32768 -> 0 m.
    assert spike.terrarium_metres(128, 0, 0) == 0.0
    # 135*256 + 118 + 200/256 - 32768 = 1910.78 -> floored to 1910.5
    assert spike.terrarium_metres(135, 118, 200) == 1910.5


def test_a_point_lands_in_the_web_mercator_tile_that_contains_it():
    # Zoom 1 splits the world in four: (-90, 45) is the north-west tile.
    tx, ty, px, py = spike.tile_pixel(-90.0, 45.0, zoom=1)

    assert (tx, ty) == (0, 0)
    assert px == 128 and 0 < py < 256


def test_the_first_cache_layout_migrates_hour_by_hour():
    run = "2026-07-23T12:00:00+00:00"
    old = {
        run: {
            "MWN": [["2026-07-24T01:00:00+00:00", 8.3], ["2026-07-24T02:00:00+00:00", 8.1]],
            "BML": [["2026-07-24T01:00:00+00:00", 15.0]],
        }
    }

    assert spike.migrate(old) == {run: {"13": {"MWN": 8.3, "BML": 15.0}, "14": {"MWN": 8.1}}}


def test_a_missing_archive_file_is_a_missing_hour_not_a_filled_one():
    run = datetime(2026, 9, 14, 12, tzinfo=UTC)
    cached = {run.isoformat(): {"13": None, "14": {"MWN": 50.0, "BML": None}, "15": {"MWN": 51.0}}}

    assert spike.series(cached, run, "MWN") == [(run + timedelta(hours=14), 50.0), (run + timedelta(hours=15), 51.0)]
    assert spike.series(cached, run, "BML") == []
    assert spike.missing_files(cached) == [f"{run.isoformat()} +13h"]
