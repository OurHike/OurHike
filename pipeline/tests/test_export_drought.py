"""The drought clip: what it publishes, and the two things it refuses to.

Both guards exist because their failures are quiet ones. A corridor buffer
that loses trail still produces a valid map of something, and a release that
nests its classes still produces bands that draw - they just stop meaning what
`trail_miles` says they mean. Neither would show up as an error anywhere
downstream, which is why they are assertions here rather than comments.

The geometry in these tests is deliberately toy-sized and axis-aligned: what
is being tested is the export's reasoning, not shapely's.
"""

from __future__ import annotations

import json
from datetime import date

import pytest
from shapely.geometry import MultiLineString, box, mapping

import export_drought


def polygon_feature(dm: int, bounds: tuple[float, float, float, float]) -> dict:
    return {
        "type": "Feature",
        "properties": {"DM": dm},
        "geometry": mapping(box(*bounds)),
    }


@pytest.fixture
def run_export(tmp_path, monkeypatch):
    """Point the export at a temp release, centerline and outputs."""

    def run(features: list[dict], line: list[list[float]] | None = None, stamp: str = "20260811"):
        raw_dir = tmp_path / "raw" / "drought"
        raw_dir.mkdir(parents=True)
        (raw_dir / f"usdm_{stamp}.json").write_text(json.dumps({"type": "FeatureCollection", "features": features}))

        centerline = tmp_path / "centerline.geojson"
        coords = line if line is not None else [[0.0, 0.0], [0.0, 1.0]]
        centerline.write_text(
            json.dumps(
                {
                    "type": "FeatureCollection",
                    "features": [{"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords}}],
                }
            )
        )

        out_dir = tmp_path / "processed" / "conditions"
        monkeypatch.setattr(export_drought, "RAW_DIR", raw_dir)
        monkeypatch.setattr(export_drought, "CENTERLINE_PATH", centerline)
        monkeypatch.setattr(export_drought, "OUT_DIR", out_dir)
        monkeypatch.setattr(export_drought, "OUT_PATH", out_dir / "drought.json")
        monkeypatch.setattr(export_drought, "MANIFEST_PATH", tmp_path / "processed" / "drought_manifest.json")
        export_drought.main()
        return json.loads((out_dir / "drought.json").read_text())

    return run


class TestWhatItPublishes:
    def test_the_week_travels_with_the_bands(self, run_export):
        document = run_export([polygon_feature(0, (-1, -1, 1, 2))])
        assert document["valid_start"] == "2026-08-11"
        assert document["valid_end"] == "2026-08-17"
        assert document["generated_at"].endswith("Z")

    def test_each_band_carries_its_class_label_and_mileage(self, run_export):
        document = run_export([polygon_feature(2, (-1, -1, 1, 2))])
        (band,) = document["drought"]
        assert band["properties"]["dm"] == 2
        assert band["properties"]["label"] == "Severe drought"
        # The toy line is one degree of latitude, about 69 miles, and it lies
        # wholly inside the band.
        assert band["properties"]["trail_miles"] == pytest.approx(69.0, abs=0.5)

    def test_the_mileages_sum_rather_than_nest(self, run_export):
        """The reading that was wrong the first time round.

        Two disjoint boxes covering the northern and southern halves of the
        line must report about half its length each - NOT one of them
        reporting the whole thing because it "contains" the other.
        """
        document = run_export(
            [
                polygon_feature(0, (-1, -0.1, 1, 0.5)),
                polygon_feature(2, (-1, 0.5, 1, 1.1)),
            ]
        )
        miles = {f["properties"]["dm"]: f["properties"]["trail_miles"] for f in document["drought"]}
        assert miles[0] == pytest.approx(34.5, abs=1.0)
        assert miles[2] == pytest.approx(34.5, abs=1.0)
        assert sum(miles.values()) == pytest.approx(69.0, abs=1.0)

    def test_a_class_that_misses_the_corridor_is_not_published(self, run_export):
        document = run_export(
            [
                polygon_feature(0, (-1, -1, 1, 2)),
                polygon_feature(3, (40, 40, 41, 41)),
            ]
        )
        assert [f["properties"]["dm"] for f in document["drought"]] == [0]

    def test_a_trail_with_no_drought_publishes_an_empty_band_set(self, run_export):
        """Not a missing file: absent renders as "no layer", which is a
        different claim from "no drought"."""
        document = run_export([polygon_feature(0, (40, 40, 41, 41))])
        assert document["drought"] == []
        assert document["valid_start"] == "2026-08-11"


class TestTheGuards:
    def test_overlapping_classes_are_refused(self, run_export):
        """A release that nests its classes would silently change what
        `trail_miles` means, and stack translucent fills darkest where the
        polygons pile up rather than where the drought is worst."""
        with pytest.raises(SystemExit) as exit_info:
            run_export(
                [
                    polygon_feature(0, (-1, -1, 1, 2)),
                    polygon_feature(1, (-0.5, -0.5, 0.5, 1.5)),
                ]
            )
        assert "nests its classes" in str(exit_info.value)

    def test_a_corridor_that_does_not_cover_the_trail_is_refused(self, run_export, monkeypatch):
        """The simplification is what this guards, not the buffer.

        A buffer contains the geometry it grew from at any radius, so no
        buffer setting alone can fail this - the first version of this test
        shrank the buffer to a nanodegree and the export cheerfully succeeded.
        What CAN lose trail is simplifying the line before buffering it:
        trimming a switchback by more than the buffer's width leaves that
        corner outside the corridor. So this simplifies harder than it
        buffers, over a zigzag with corners to lose.
        """
        monkeypatch.setattr(export_drought, "CORRIDOR_SIMPLIFY_DEG", 0.3)
        monkeypatch.setattr(export_drought, "CORRIDOR_BUFFER_DEG", 0.01)
        monkeypatch.setattr(export_drought, "CORRIDOR_SMOOTH_DEG", 1e-9)
        zigzag = [[0.0, 0.0], [0.5, 0.1], [0.0, 0.2], [0.5, 0.3], [0.0, 0.4]]
        with pytest.raises(SystemExit) as exit_info:
            run_export([polygon_feature(0, (-1, -1, 1, 2))], line=zigzag)
        assert "outside" in str(exit_info.value)

    def test_the_shipped_settings_keep_the_trail_inside_the_corridor(self, run_export):
        """The other half: the same zigzag passes at the real settings, so the
        guard above is discriminating rather than merely strict."""
        zigzag = [[0.0, 0.0], [0.5, 0.1], [0.0, 0.2], [0.5, 0.3], [0.0, 0.4]]
        document = run_export([polygon_feature(0, (-1, -1, 1, 2))], line=zigzag)
        assert document["drought"][0]["properties"]["dm"] == 0

    def test_a_missing_release_says_to_run_the_fetcher(self, tmp_path, monkeypatch):
        monkeypatch.setattr(export_drought, "RAW_DIR", tmp_path / "empty")
        (tmp_path / "empty").mkdir()
        with pytest.raises(SystemExit) as exit_info:
            export_drought.newest_release()
        assert "fetch_drought.py" in str(exit_info.value)

    def test_the_newest_release_wins(self, tmp_path, monkeypatch):
        raw = tmp_path / "raw"
        raw.mkdir()
        for stamp in ("20260728", "20260811", "20260804"):
            (raw / f"usdm_{stamp}.json").write_text("{}")
        monkeypatch.setattr(export_drought, "RAW_DIR", raw)
        path, stamp = export_drought.newest_release()
        assert stamp == date(2026, 8, 11)
        assert path.name == "usdm_20260811.json"


class TestTheCenterline:
    def test_parts_are_kept_apart(self):
        """Joining the parts measures the A.T. at 108,000 miles instead of
        2,172 - the one mistake this loader exists to make impossible."""
        far_apart = MultiLineString([[(0, 0), (0, 0.1)], [(0, 10), (0, 10.1)]])
        assert export_drought.line_miles(far_apart) == pytest.approx(13.8, abs=0.5)

    def test_a_centerline_with_no_lines_is_refused(self, tmp_path, monkeypatch):
        path = tmp_path / "centerline.geojson"
        path.write_text(json.dumps({"type": "FeatureCollection", "features": []}))
        monkeypatch.setattr(export_drought, "CENTERLINE_PATH", path)
        with pytest.raises(SystemExit) as exit_info:
            export_drought.load_centerline()
        assert "no line geometry" in str(exit_info.value)
