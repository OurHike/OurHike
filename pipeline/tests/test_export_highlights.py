"""The highlight exporter (#595).

lib/highlights.py holds the join and is tested there. What is left here is the
plumbing that has actually gone wrong in this pipeline before: reading the
published POIs under the names export_poi.py really writes, and never letting a
curated list shrink quietly.
"""

from __future__ import annotations

import json

import pytest

import export_highlights
from lib.poi_schema import poi_output_name


def write_pois(poi_dir, poi_type: str, records: list[dict]) -> None:
    poi_dir.mkdir(parents=True, exist_ok=True)
    (poi_dir / poi_output_name(poi_type)).write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [{"type": "Feature", "properties": r} for r in records],
            }
        )
    )


CURATED = [
    {
        "id": "mcafee-knob",
        "name": "McAfee Knob",
        "basis": "named",
        "note": "The most photographed spot on the A.T.",
        "reviewed": "2026-08-20",
        "legs": [{"trail": "AT", "from_poi": "atc_parking:p", "to_poi": "atc_viewpoints:s"}],
    }
]

CLUB_RUNS = [
    {"acronym": "RATC", "stretches": [{"start_mile": 700.0, "end_mile": 720.0}]},
    {"acronym": "GATC", "stretches": [{"start_mile": 0.0, "end_mile": 77.0}]},
]


class TestReadingThePublishedPois:
    def test_reads_every_type_under_the_names_export_poi_writes(self, tmp_path):
        # The bug this guards is #469's shape: export_poi.py had run, green,
        # and the reader was asking for names it does not write. An anchor can
        # be any named thing ATC carries, so every type is read.
        poi_dir = tmp_path / "poi"
        write_pois(poi_dir, "parking", [{"id": "atc_parking:p", "mile": 705.6}])
        write_pois(poi_dir, "viewpoint", [{"id": "atc_viewpoints:s", "mile": 709.1}])

        pois = export_highlights.load_published_pois(poi_dir)

        assert {p["id"] for p in pois} == {"atc_parking:p", "atc_viewpoints:s"}

    def test_a_missing_type_file_is_skipped_rather_than_fatal(self, tmp_path):
        # A partial export is a real state this pipeline supports.
        poi_dir = tmp_path / "poi"
        write_pois(poi_dir, "parking", [{"id": "atc_parking:p", "mile": 705.6}])

        assert len(export_highlights.load_published_pois(poi_dir)) == 1

    def test_an_absent_directory_yields_nothing_rather_than_raising(self, tmp_path):
        assert export_highlights.load_published_pois(tmp_path / "nope") == []

    def test_the_default_is_followed_when_the_module_constant_moves(self, tmp_path, monkeypatch):
        # A plain `=POI_DIR` default binds once at import, so a test pointing
        # the constant elsewhere would still read the real path - the trap
        # export_spurs.py's own loader documents.
        poi_dir = tmp_path / "poi"
        write_pois(poi_dir, "parking", [{"id": "atc_parking:p", "mile": 1.0}])
        monkeypatch.setattr(export_highlights, "POI_DIR", poi_dir)

        assert len(export_highlights.load_published_pois()) == 1


class TestBuildingTheOutput:
    def test_publishes_the_range_the_pois_give_it(self, tmp_path):
        pois = [
            {"id": "atc_parking:p", "mile": 705.6},
            {"id": "atc_viewpoints:s", "mile": 709.1},
        ]
        output, dropped, _ = export_highlights.build_output(CURATED, pois, CLUB_RUNS)

        assert dropped == []
        assert output["highlights"][0]["legs"] == [{"trail": "AT", "start_mile": 705.6, "end_mile": 709.1}]

    def test_records_which_club_the_walk_starts_in(self, tmp_path):
        pois = [
            {"id": "atc_parking:p", "mile": 705.6},
            {"id": "atc_viewpoints:s", "mile": 709.1},
        ]
        output, _, gaps = export_highlights.build_output(CURATED, pois, CLUB_RUNS)

        assert output["highlights"][0]["club"] == "RATC"
        # Reported on every run, and not a failure: a club with no well-known
        # stretch is a fact about the trail.
        assert gaps == ["GATC"]

    def test_an_entry_it_cannot_place_is_reported_not_just_absent(self):
        # A curated list quietly shrinking is the failure nobody notices.
        output, dropped, _ = export_highlights.build_output(CURATED, [], [])

        assert output["highlights"] == []
        assert len(dropped) == 1
        assert dropped[0][0] == "mcafee-knob"

    def test_names_the_file_the_judgement_lives_in(self):
        # So a reader of the artifact can find the rows somebody reviewed.
        output, _, _ = export_highlights.build_output([], [], [])
        assert output["source"] == "reference/highlights.json"


class TestTheCuratedInput:
    def test_an_absent_curated_file_is_fatal(self, tmp_path):
        # This script has nothing true to say without it, and an empty
        # highlights.json looks exactly like a trail with nothing on it.
        with pytest.raises(SystemExit):
            export_highlights.load_curated(tmp_path / "gone.json")

    def test_reads_the_real_reference_file(self):
        curated = export_highlights.load_curated()
        assert curated, "reference/highlights.json should carry the curated list"
        assert all(row.get("id") for row in curated)


def test_the_real_curated_file_publishes_when_its_anchors_exist():
    """End to end against the committed list, with the POIs stubbed.

    The miles are invented here and the assertion is not about them - it is
    that every row in the file somebody reviewed is well formed enough to
    reach the artifact once export_poi.py has run.
    """
    curated = export_highlights.load_curated()
    anchors = sorted({poi_id for row in curated for leg in row["legs"] for poi_id in (leg["from_poi"], leg["to_poi"])})
    pois = [{"id": poi_id, "mile": float(i * 10)} for i, poi_id in enumerate(anchors)]

    output, dropped, _ = export_highlights.build_output(curated, pois, [])

    assert dropped == []
    assert len(output["highlights"]) == len(curated)
    # Nothing derived is stored - the phone computes length, ascent and time.
    for record in output["highlights"]:
        assert set(record) == {"id", "name", "bases", "citations", "legs", "club"}
