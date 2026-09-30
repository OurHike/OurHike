"""Tests for fetch_hrrr.py (#1056, the HRRR slice): which run is used, what
"complete" means, and that a failed run leaves no record behind."""

from datetime import UTC, datetime

import pytest

import fetch_hrrr


def keys_for(run: datetime, hours) -> list[str]:
    return [f"{fetch_hrrr.run_prefix(run)}{h:02d}.grib2.idx" for h in hours] + [
        f"{fetch_hrrr.run_prefix(run)}{h:02d}.grib2" for h in hours
    ]


RUN = datetime(2026, 9, 29, 6, tzinfo=UTC)


def test_only_the_four_48_hour_runs_are_candidates_newest_first():
    runs = fetch_hrrr.long_runs(datetime(2026, 9, 29, 13, 40, tzinfo=UTC))

    assert [r.strftime("%d %H") for r in runs] == ["29 12", "29 06", "29 00", "28 18"]


def test_just_after_midnight_the_newest_candidate_is_that_midnight():
    runs = fetch_hrrr.long_runs(datetime(2026, 9, 29, 0, 5, tzinfo=UTC), back=2)

    assert [r.strftime("%d %H") for r in runs] == ["29 00", "28 18"]


def test_a_run_with_all_48_hours_is_complete():
    assert fetch_hrrr.complete(RUN, keys_for(RUN, range(0, 49)))


def test_a_run_missing_one_hour_is_not_complete():
    assert not fetch_hrrr.complete(RUN, keys_for(RUN, [h for h in range(0, 49) if h != 37]))


def test_a_file_without_its_index_does_not_count():
    keys = keys_for(RUN, range(0, 48))  # hour 48 missing entirely
    keys.append(f"{fetch_hrrr.run_prefix(RUN)}48.grib2")  # the GRIB, but no .idx yet

    assert not fetch_hrrr.complete(RUN, keys)


INDEX = [
    "70:44000000:d=2026092906:TMP:surface:24 hour fcst:",
    "71:44429262:d=2026092906:TMP:2 m above ground:24 hour fcst:",
    "72:45647979:d=2026092906:POT:2 m above ground:24 hour fcst:",
]


def test_the_forecast_hour_in_the_index_line_must_match_the_file():
    fetch_hrrr.check_index_hour(INDEX, 44429262, 24)

    with pytest.raises(RuntimeError, match="forecast hour 23"):
        fetch_hrrr.check_index_hour(INDEX, 44429262, 23)


def test_hour_10_is_not_mistaken_for_hour_1():
    line = ["71:100:d=2026092906:TMP:2 m above ground:10 hour fcst:", "72:200:x:y:z:10 hour fcst:"]

    with pytest.raises(RuntimeError):
        fetch_hrrr.check_index_hour(line, 100, 1)


def test_a_failed_run_removes_the_last_record(tmp_path, monkeypatch):
    record = tmp_path / "hrrr_cycle.json"
    record.write_text("{}")
    monkeypatch.setattr(fetch_hrrr, "HRRR_CYCLE_PATH", record)

    def stalled(session, now=None):
        raise RuntimeError("no complete 48-hour HRRR run")

    monkeypatch.setattr(fetch_hrrr, "find_run", stalled)

    with pytest.raises(RuntimeError):
        fetch_hrrr.main()
    assert not record.exists()  # so export_weather.py publishes hrrr: null, not an old run
