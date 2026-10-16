"""step_section_closures.py: decision 212's rule over a published notices.json and the warehouse's network lines,
landed as derived.section_closures."""

from __future__ import annotations

import json

import duckdb
import pytest

import step_section_closures as step

DOLL_RIDGE_TITLE = (
    "The Tuscarora Trail section just west of Massanutten Mountain is closed due to loss of landowner permission. "
    "… This is the Doll Ridge section from Three Top Mountain to Riverview Drive."
)


def _notice(notice_id, title, *, closing=True, place="unplaced", provider="PATC", source_key="patc_tuscarora_updates"):
    return {
        "notice_id": notice_id,
        "source_key": source_key,
        "provider": provider,
        "steward_kind": "club",
        "title": title,
        "obstructs_trail": closing,
        "place": {"kind": place},
    }


@pytest.fixture
def warehouse(tmp_path):
    path = tmp_path / "warehouse.duckdb"
    with duckdb.connect(str(path)) as con:
        con.execute("install spatial; load spatial; create schema intermediate")
        con.execute("""
            create table intermediate.int_trail_lines__network_area_closures as
            select * from (values
                ('usfs:1', 'usfs_trails', 'TUSCARORA - DOLL RIDGE', 'open', 'LINESTRING (-78.5 38.9, -78.49 38.91)'),
                ('usfs:2', 'usfs_trails', 'TUSCARORA - DOLL RIDGE', 'open', 'LINESTRING (-78.49 38.91, -78.48 38.92)'),
                ('usfs:3', 'usfs_trails', 'TUSCARORA - THREE TOP', 'open', 'LINESTRING (-78.48 38.92, -78.47 38.93)'),
                ('usfs:4', 'usfs_trails', 'TUSCARORA - BIG BLUE', 'closed', 'LINESTRING (-78.4 38.9, -78.39 38.91)')
            ) as t (trail_segment_key, source_key, name, trail_status, geom_wkt)
        """)
    return path


def _landed(path):
    with duckdb.connect(str(path)) as con:
        return con.execute(
            "select trail_segment_key, closure_source, closure_reason from derived.section_closures order by 1"
        ).fetchall()


def test_a_clubs_closing_sentence_naming_doll_ridge_closes_both_of_its_lines_with_its_words(warehouse, tmp_path):
    notices = tmp_path / "notices.json"
    notices.write_text(json.dumps({"notices": [_notice("patc:1", DOLL_RIDGE_TITLE)]}))

    assert step.main(["--warehouse", str(warehouse), "--notices", str(notices)]) == 0

    assert _landed(warehouse) == [
        ("usfs:1", "patc_tuscarora_updates", DOLL_RIDGE_TITLE),
        ("usfs:2", "patc_tuscarora_updates", DOLL_RIDGE_TITLE),
    ]


def test_a_notice_with_its_own_geometry_is_never_read(warehouse, tmp_path):
    """The maintainer's "No, own geometry wins (Recommended)", 2026-10-15."""
    notices = tmp_path / "notices.json"
    notices.write_text(json.dumps({"notices": [_notice("patc:1", DOLL_RIDGE_TITLE, place="geometry")]}))

    step.main(["--warehouse", str(warehouse), "--notices", str(notices)])

    assert _landed(warehouse) == []


def test_a_line_already_closed_is_not_read_so_keeps_its_own_closure(warehouse, tmp_path):
    notices = tmp_path / "notices.json"
    notices.write_text(json.dumps({"notices": [_notice("patc:2", "The Tuscarora Trail Big Blue section is closed.")]}))

    step.main(["--warehouse", str(warehouse), "--notices", str(notices)])

    assert _landed(warehouse) == []


def test_no_notices_lands_an_empty_table_and_never_stops_the_build(warehouse, tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("DATA_BASE_URL", raising=False)
    monkeypatch.setenv("OURHIKE_DATA_ENV", "ua")

    assert step.main(["--warehouse", str(warehouse), "--from-bucket"]) == 0
    assert step.main(["--warehouse", str(warehouse), "--notices", str(tmp_path / "absent.json")]) == 0

    assert _landed(warehouse) == []
    assert "no section closes this build" in capsys.readouterr().out
