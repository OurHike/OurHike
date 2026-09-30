"""Tests for spike_weather_sources.py's scoring (#1056).

The spike's findings came from fetching real observations and archived
forecasts, which a test must not do - but every number in WEATHER.md's
accuracy table rests on two small functions, the local-day extremes and the
error score, so those are pinned against cases worked by hand."""

from datetime import UTC, date, datetime, timedelta

import spike_weather_sources as spike


def hourly(start: datetime, values: list[float]) -> list[tuple[datetime, float]]:
    return [(start + timedelta(hours=i), v) for i, v in enumerate(values)]


def test_daily_extremes_uses_the_local_day_not_the_utc_one():
    # 24 readings from 04:00 UTC = midnight to 23:00 at UTC-4, so they are
    # one local day even though they straddle two UTC dates.
    readings = hourly(datetime(2026, 8, 1, 4, tzinfo=UTC), [float(i) for i in range(24)])

    days = spike.daily_extremes(readings, -4 * 3600)

    assert days == {date(2026, 8, 1): (23.0, 0.0)}


def test_daily_extremes_drops_a_day_with_too_few_hours():
    short = spike.MIN_HOURS_PER_DAY - 1
    readings = hourly(datetime(2026, 8, 1, 0, tzinfo=UTC), [50.0] * short)

    assert spike.daily_extremes(readings, 0) == {}


def test_daily_extremes_counts_distinct_hours_not_reports():
    # AWOS reports every 20 minutes: three reports in one hour are one hour.
    t0 = datetime(2026, 8, 1, 0, tzinfo=UTC)
    readings = [(t0 + timedelta(minutes=20 * i), 60.0) for i in range(3 * (spike.MIN_HOURS_PER_DAY - 1))]

    assert spike.daily_extremes(readings, 0) == {}


def test_score_is_mean_absolute_error_and_signed_bias():
    fc = {date(2026, 8, 1): (70.0, 50.0), date(2026, 8, 2): (60.0, 40.0)}
    obs = {date(2026, 8, 1): (72.0, 49.0), date(2026, 8, 2): (57.0, 40.0)}

    s = spike.score(fc, obs)

    assert s is not None
    assert s.n == 2
    assert s.high_mae == 2.5  # |70-72| and |60-57|
    assert s.high_bias == 0.5  # (-2 + 3) / 2
    assert s.low_mae == 0.5
    assert s.low_bias == 0.5


def test_score_uses_only_days_both_sides_have():
    fc = {date(2026, 8, 1): (70.0, 50.0), date(2026, 8, 2): (99.0, 99.0)}
    obs = {date(2026, 8, 1): (70.0, 50.0), date(2026, 8, 3): (0.0, 0.0)}

    s = spike.score(fc, obs)

    assert s is not None and s.n == 1 and s.high_mae == 0.0


def test_score_is_none_with_no_shared_day():
    assert spike.score({date(2026, 8, 1): (1.0, 0.0)}, {}) is None


def test_parse_iem_csv_skips_blank_and_missing_readings():
    text = "station,valid,tmpf\nMWN,2026-09-20 00:50,42.80\nMWN,2026-09-20 01:51,\nMWN,2026-09-20 02:50,M\n"

    assert spike.parse_iem_csv(text) == [(datetime(2026, 9, 20, 0, 50, tzinfo=UTC), 42.8)]


def test_parse_open_meteo_skips_nulls_rather_than_reading_them_as_zero():
    payload = {
        "hourly": {
            "time": ["2026-09-20T00:00", "2026-09-20T01:00"],
            "temperature_2m_previous_day1": [None, 41.5],
        }
    }

    got = spike.parse_open_meteo(payload, "temperature_2m_previous_day1")

    assert got == [(datetime(2026, 9, 20, 1, 0, tzinfo=UTC), 41.5)]
