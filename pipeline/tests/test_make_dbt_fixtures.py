"""The CI dbt job's fixtures stay loadable and stay honest (#100).

Two properties matter: load_raw.py can actually load what this writes (a
fixture that drifted from the loader is a green CI step proving nothing),
and the opentrail fixture covers ICON_LEGEND's whole domain so the dbt-side
accepted_values test exercises every documented code.
"""

import duckdb
import pytest

import fetch_opentrail
import load_raw
import make_dbt_fixtures


def test_fixtures_load_through_the_real_loader(tmp_path):
    make_dbt_fixtures.write_fixtures(tmp_path)
    con = duckdb.connect()
    try:
        loaded, _skipped = load_raw.load_raw(con, tmp_path)
        assert set(loaded) == {"raw_atc__shelters", "raw_atc__campsites", "raw_opentrail__at"}
        icons = {row[0] for row in con.execute("select icon from raw.raw_opentrail__at").fetchall()}
    finally:
        con.close()

    assert icons == set(fetch_opentrail.ICON_LEGEND), (
        "the fixture must cover every documented icon, or the dbt accepted_values test runs against a subset of its domain"
    )


def test_refuses_to_overwrite_a_real_fetch(tmp_path):
    (tmp_path / "shelters.geojson").write_text("{}")

    with pytest.raises(SystemExit, match="Refusing to overwrite"):
        make_dbt_fixtures.write_fixtures(tmp_path)
