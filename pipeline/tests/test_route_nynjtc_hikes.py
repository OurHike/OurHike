"""route_nynjtc_hikes.py - measuring the reviewed rows against the graph and
rendering the sign-off sheet (#1290).

A synthetic graph (the same hand-placed one test_lib_trail_graph_route.py
uses), a two-hike cache and a reference file in a temp directory - never the
real network or the real rows (TESTING.md). What is pinned is the script's
promises: a held row is reported and never routed; a proposed row is
measured and drawn; an end the line has moved away from is a named problem,
not a route; a `reviewed` row that stops routing fails the run; and the
sheet says which figure is NYNJTC's and which is this build's.
"""

from __future__ import annotations

import json

import pytest

import route_nynjtc_hikes as script
from tests.test_lib_trail_graph_route import LAT, LON, STEP, graph_files


def reference(rows: dict) -> dict:
    return {"_README": ["synthetic"], "routes": rows}


def proposed_row(**overrides) -> dict:
    row = {
        "status": "proposed",
        "closed": True,
        "ends": [[LON + 0.5 * STEP, LAT], [LON + 2.5 * STEP, LAT]],
        "measured_miles": 0.21,
        "basis": "two points on Pine Meadow, out and back",
        "proposed": "2026-09-09",
        "reviewed": None,
    }
    row.update(overrides)
    return row


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    (tmp_path / "processed").mkdir()
    graph_dir = graph_files(tmp_path / "processed")
    cache_path = tmp_path / "raw" / "nynjtc_hikes.json"
    cache_path.parent.mkdir()
    cache_path.write_text(
        json.dumps(
            {
                "hikes": {
                    "hike-pine": {
                        "name": "Pine Meadow",
                        "difficulty": "easy",
                        "stated_miles": 0.2,
                        "source_url": "https://x/pine/",
                        "terms": {"route-type": [{"slug": "loop", "name": "Loop"}]},
                    },
                    "hike-far": {
                        "name": "Somewhere Else",
                        "difficulty": "easy",
                        "stated_miles": 5.0,
                        "source_url": "https://x/far/",
                        "terms": {},
                    },
                }
            }
        )
    )
    reference_path = tmp_path / "reference.json"
    monkeypatch.setattr(script, "CACHE_PATH", cache_path)
    monkeypatch.setattr(script, "REFERENCE_PATH", reference_path)
    monkeypatch.setattr(script, "PROCESSED_DIR", graph_dir)
    monkeypatch.setattr(script, "REVIEW_PATH", tmp_path / "review.html")
    return {"graph_dir": graph_dir, "reference_path": reference_path, "review": tmp_path / "review.html"}


def write_rows(sandbox, rows: dict) -> None:
    sandbox["reference_path"].write_text(json.dumps(reference(rows)))


def test_a_proposed_row_is_measured_drawn_and_left_proposed(sandbox, capsys):
    write_rows(sandbox, {"hike-pine": proposed_row()})

    assert script.main([]) == 0

    out = capsys.readouterr().out
    assert "proposed  hike-pine" in out
    assert "(NYNJTC 0.20)" in out
    sheet = sandbox["review"].read_text()
    assert "Pine Meadow" in sheet
    assert "<svg" in sheet
    assert "NYNJTC says 0.20 mi" in sheet
    assert "measured on this build" in sheet
    assert "1 proposed · 0 reviewed · 0 held" in sheet


def test_a_held_row_is_reported_and_never_routed(sandbox, capsys):
    write_rows(sandbox, {"hike-far": {"status": "held", "reason": "no lines within 2.5 km - #1293", "proposed": "2026-09-09"}})

    assert script.main([]) == 0
    assert "held      hike-far" in capsys.readouterr().out
    sheet = sandbox["review"].read_text()
    assert "HELD" in sheet
    assert "#1293" in sheet
    assert "<svg" not in sheet


def test_an_end_the_line_has_moved_away_from_is_a_named_problem(sandbox, capsys):
    """0.002° of latitude is ~222 m, past the phone's 150 ft radius."""
    write_rows(sandbox, {"hike-pine": proposed_row(ends=[[LON + 0.5 * STEP, LAT], [LON + 2.5 * STEP, LAT - 2 * STEP]])})

    assert script.main([]) == 0
    out = capsys.readouterr().out
    assert "DOES NOT ROUTE" in out
    assert "end 2" in out
    assert "more than 46 m from any line" in out


def test_a_reviewed_row_that_stops_routing_fails_the_run(sandbox, capsys):
    write_rows(
        sandbox,
        {
            "hike-pine": proposed_row(
                status="reviewed", reviewed="2026-09-10", ends=[[LON + 0.5 * STEP, LAT], [LON + 2.5 * STEP, LAT - 2 * STEP]]
            )
        },
    )

    assert script.main([]) == 1
    assert "1 reviewed row(s) no longer route" in capsys.readouterr().err


def test_a_measurement_that_drifted_from_the_placed_figure_is_called_out(sandbox, capsys):
    write_rows(sandbox, {"hike-pine": proposed_row(measured_miles=0.10)})

    assert script.main([]) == 0
    assert "moved +" in capsys.readouterr().out
    assert "since the row was placed" in sandbox["review"].read_text()


def test_the_published_miles_override_beats_the_parse(sandbox, capsys):
    write_rows(sandbox, {"hike-pine": proposed_row(published_miles=0.5, published_miles_note="the overview names two lengths")})

    assert script.main([]) == 0
    assert "(NYNJTC 0.50)" in capsys.readouterr().out
    assert "the overview names two lengths" in sandbox["review"].read_text()


def test_an_unknown_status_is_refused(sandbox):
    write_rows(sandbox, {"hike-pine": proposed_row(status="approved")})

    with pytest.raises(SystemExit, match="expected one of"):
        script.main([])


def test_a_proposed_row_with_one_end_is_refused(sandbox):
    write_rows(sandbox, {"hike-pine": proposed_row(ends=[[LON, LAT]])})

    with pytest.raises(SystemExit, match="fewer than two ends"):
        script.main([])


def test_a_missing_graph_is_an_exit_not_an_empty_sheet(sandbox, tmp_path):
    write_rows(sandbox, {"hike-pine": proposed_row()})

    with pytest.raises(SystemExit, match="run build_trail_graph.py first"):
        script.main(["--graph-dir", str(tmp_path / "nowhere")])


def test_climb_is_unknown_when_the_sidecar_does_not_fit_the_graph(sandbox, tmp_path, capsys):
    graph_files(sandbox["graph_dir"], misaligned=True)
    write_rows(sandbox, {"hike-pine": proposed_row()})

    assert script.main([]) == 0
    out = capsys.readouterr().out
    assert "different graph" in out
    assert "climb unknown" in out


def test_the_real_reference_rows_are_well_formed():
    """The committed file, read the way the script reads it: every status
    in the vocabulary, every non-held row with ends, every held row with a
    reason. The rows themselves are judgement and are reviewed as a diff."""
    routes = script.load_routes()

    assert len(routes) >= 20, "the twenty public hikes each have a row, whatever its status"
    for slug, row in routes.items():
        if row["status"] == script.STATUS_HELD:
            assert row.get("reason", "").strip(), f"{slug} is held with no reason"
        else:
            assert row.get("basis", "").strip(), f"{slug} carries ends with no basis"
            assert all(len(end) == 2 and -76.5 < end[0] < -72 and 39.5 < end[1] < 43.6 for end in row["ends"]), (
                f"{slug} has an end outside the region"
            )
            assert isinstance(row.get("measured_miles"), (int, float)), f"{slug} was never measured"


def test_a_reviewed_row_carries_the_date_it_was_signed_off():
    for slug, row in script.load_routes().items():
        if row["status"] == script.STATUS_REVIEWED:
            assert row.get("reviewed"), f"{slug} is reviewed but says not when"
