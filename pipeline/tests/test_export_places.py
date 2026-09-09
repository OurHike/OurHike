"""export_places.py - the places a hiker can name before anything is downloaded (#1371).

Synthetic geometry in a temp directory, never the real layers (TESTING.md).
Every fixture is a few points and lines around (-74, 41), which is close
enough to Harriman for the metre projection to behave and nowhere near any
real row.

What is pinned: which rows ship and which do not (a park behind its licence
gate, an unnamed lot, a trailhead with no published line near it), what each
row carries (a measured `trailMiles` over the lines this run published, a
state only where the source says it, the park a point sits inside), and the
one absence that must never read as a number - no lines at all means
`trailMiles` is omitted everywhere and the document says so.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import export_places as exporter
import publish
from lib.poi_schema import poi_output_name

LON, LAT = -74.0, 41.0
#: Roughly a mile of longitude at 41 N, and a mile of latitude.
MILE_LON, MILE_LAT = 0.0192, 0.01447
WHEN = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)


def feature(geometry: dict, properties: dict) -> dict:
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": features}


def write(path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document))


def registry(parks_reach: bool = True) -> dict:
    return {
        "sources": [
            {"key": exporter.PARKS_KEY, "provider": "NYS OPRHP", "reaches_hikers": parks_reach},
            {"key": "oprhp_facilities", "provider": "NYS OPRHP", "reaches_hikers": True},
            {"key": "dec_parking_areas", "provider": "NYS DEC", "reaches_hikers": True},
            {"key": "usfs_rec_sites", "provider": "USFS", "reaches_hikers": True},
        ]
    }


def square(west: float, south: float, miles: float) -> dict:
    east, north = west + miles * MILE_LON, south + miles * MILE_LAT
    return {"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]]}


def line(west: float, south: float, miles: float) -> dict:
    """A straight east-west line `miles` long."""
    return {"type": "LineString", "coordinates": [[west, south], [west + miles * MILE_LON, south]]}


def point(lon: float, lat: float) -> dict:
    return {"type": "Point", "coordinates": [lon, lat]}


def poi(poi_id: str, poi_type: str, source: str, name: str | None, lon: float, lat: float, **extra) -> dict:
    return feature(
        point(lon, lat),
        {"id": poi_id, "poi_type": poi_type, "source": source, "name": name, "lon": lon, "lat": lat, **extra},
    )


@pytest.fixture
def sandbox(tmp_path):
    """A processed directory with the four artifacts the exporter reads,
    each written by a test as it needs it, and the paths handed to build_output."""
    processed = tmp_path / "processed"
    raw = tmp_path / "raw"
    paths = {
        "parks": raw / "external" / f"{exporter.PARKS_KEY}.geojson",
        "poi_dir": processed / "poi",
        "nearby": processed / "nearby_poi.geojson",
        "communities": raw / exporter.COMMUNITIES_RAW,
        "lines": [processed / name for name in exporter.LINE_ARTIFACTS],
    }
    for poi_type in exporter.POINT_PLACE_KINDS:
        write(paths["poi_dir"] / poi_output_name(poi_type), collection([]))
    write(paths["nearby"], collection([]))
    write(paths["parks"], collection([]))
    write(paths["communities"], collection([]))
    for path in paths["lines"]:
        write(path, collection([]))
    return paths


def build(paths, reg: dict | None = None, radius: float = exporter.PLACE_TRAIL_RADIUS_MILES):
    return exporter.build_output(
        reg or registry(),
        paths["parks"],
        paths["poi_dir"],
        paths["nearby"],
        paths["communities"],
        paths["lines"],
        WHEN,
        radius_miles=radius,
    )


def by_kind(output: dict, kind: str) -> list[dict]:
    return [place for place in output["places"] if place["kind"] == kind]


class TestParks:
    def test_a_park_carries_the_miles_of_published_line_inside_its_boundary(self, sandbox):
        # A 4 x 4 mile park with a 3-mile line inside it and a 2-mile line
        # entirely outside: the figure is the inside one, to a tenth.
        write(
            sandbox["parks"],
            collection([feature(square(LON, LAT, 4), {"GlobalID": "g1", "Name": "Pine State Park", "Category": "State Park"})]),
        )
        write(
            sandbox["lines"][0],
            collection(
                [
                    feature(line(LON + 0.5 * MILE_LON, LAT + 2 * MILE_LAT, 3), {"source": "oprhp_trails", "name": "Pine Trail"}),
                    feature(line(LON + 10 * MILE_LON, LAT, 2), {"source": "oprhp_trails", "name": "Far Trail"}),
                ]
            ),
        )

        output, report = build(sandbox)

        [park] = by_kind(output, "park")
        assert park["id"] == f"{exporter.PARKS_KEY}:g1"
        assert park["name"] == "Pine State Park"
        assert park["category"] == "State Park"
        assert park["state"] == "NY"
        assert park["trailMiles"] == pytest.approx(3.0, abs=0.1)
        assert output["trailMilesMeasured"] is True
        assert report["parks_held_back"] is None

    def test_a_park_centres_on_its_centroid_and_carries_its_bbox(self, sandbox):
        write(sandbox["parks"], collection([feature(square(LON, LAT, 2), {"GlobalID": "g1", "Name": "Square Park"})]))
        write(sandbox["lines"][0], collection([feature(line(LON, LAT, 1), {"source": "oprhp_trails", "name": "T"})]))

        output, _ = build(sandbox)

        [park] = by_kind(output, "park")
        assert park["lon"] == pytest.approx(LON + MILE_LON, abs=1e-4)
        assert park["lat"] == pytest.approx(LAT + MILE_LAT, abs=1e-4)
        assert park["bbox"] == pytest.approx([LON, LAT, LON + 2 * MILE_LON, LAT + 2 * MILE_LAT], abs=1e-4)

    def test_a_park_with_no_published_line_reads_zero_not_absent(self, sandbox):
        # Measured zero is a fact about what a phone would download there.
        write(sandbox["parks"], collection([feature(square(LON, LAT, 2), {"GlobalID": "g1", "Name": "Golf Course"})]))
        write(
            sandbox["lines"][0], collection([feature(line(LON + 20 * MILE_LON, LAT, 1), {"source": "oprhp_trails", "name": "T"})])
        )

        output, _ = build(sandbox)

        [park] = by_kind(output, "park")
        assert park["trailMiles"] == 0.0

    def test_parks_ship_behind_their_own_reaches_hikers(self, sandbox):
        write(sandbox["parks"], collection([feature(square(LON, LAT, 2), {"GlobalID": "g1", "Name": "Held Park"})]))
        write(sandbox["lines"][0], collection([feature(line(LON, LAT, 1), {"source": "oprhp_trails", "name": "T"})]))

        output, report = build(sandbox, registry(parks_reach=False))

        assert by_kind(output, "park") == []
        assert "reaches_hikers false" in report["parks_held_back"]

    def test_an_unfetched_park_layer_is_a_reason_not_an_error(self, sandbox):
        sandbox["parks"].unlink()

        output, report = build(sandbox)

        assert by_kind(output, "park") == []
        assert "not been fetched" in report["parks_held_back"]

    def test_a_park_with_no_name_or_no_geometry_is_not_a_place(self, sandbox):
        write(
            sandbox["parks"],
            collection(
                [
                    feature(square(LON, LAT, 2), {"GlobalID": "g1", "Name": "  "}),
                    {"type": "Feature", "geometry": None, "properties": {"GlobalID": "g2", "Name": "Ghost"}},
                ]
            ),
        )

        output, _ = build(sandbox)

        assert by_kind(output, "park") == []


class TestPointPlaces:
    def test_a_trailhead_near_a_line_ships_with_its_waypoint_id_and_the_park_it_sits_in(self, sandbox):
        write(sandbox["parks"], collection([feature(square(LON, LAT, 4), {"GlobalID": "g1", "Name": "Pine State Park"})]))
        write(
            sandbox["nearby"],
            collection(
                [poi("oprhp_facilities:7", "trailhead", "oprhp_facilities", "Reeves Meadow", LON + MILE_LON, LAT + MILE_LAT)]
            ),
        )
        write(
            sandbox["lines"][0],
            collection([feature(line(LON, LAT + 2 * MILE_LAT, 3), {"source": "oprhp_trails", "name": "Pine Trail"})]),
        )

        output, _ = build(sandbox)

        [trailhead] = by_kind(output, "trailhead")
        assert trailhead["id"] == trailhead["poiId"] == "oprhp_facilities:7"
        assert trailhead["within"] == "Pine State Park"
        assert trailhead["state"] == "NY"
        assert trailhead["trailMiles"] == pytest.approx(3.0, abs=0.1)
        assert trailhead["lon"] == LON + MILE_LON

    def test_a_trailhead_with_nothing_published_near_it_is_dropped_and_counted(self, sandbox):
        # #1231's Arizona trailhead: a place this app can put no trail under.
        write(
            sandbox["nearby"],
            collection([poi("usfs_rec_sites:9", "trailhead", "usfs_rec_sites", "Somewhere Far", LON + 40 * MILE_LON, LAT)]),
        )
        write(sandbox["lines"][0], collection([feature(line(LON, LAT, 1), {"source": "oprhp_trails", "name": "T"})]))

        output, report = build(sandbox)

        assert by_kind(output, "trailhead") == []
        assert report["dropped_far_from_any_line"] == {"usfs_rec_sites/trailhead": 1}

    def test_a_town_with_nothing_published_near_it_is_kept_reading_zero(self, sandbox):
        # "no trail data held" is the row a hiker who lives there should find.
        write(
            sandbox["poi_dir"] / poi_output_name("resupply"),
            collection(
                [
                    poi(
                        "atc_communities:c1",
                        "resupply",
                        "atc_communities",
                        "Harriman",
                        LON + 40 * MILE_LON,
                        LAT,
                        source_feature_id="c1",
                    )
                ]
            ),
        )
        write(sandbox["lines"][0], collection([feature(line(LON, LAT, 1), {"source": "oprhp_trails", "name": "T"})]))

        output, report = build(sandbox)

        [town] = by_kind(output, "town")
        assert town["trailMiles"] == 0.0
        assert report["dropped_far_from_any_line"] == {}

    def test_a_town_takes_its_state_from_the_raw_communities_layer(self, sandbox):
        write(
            sandbox["poi_dir"] / poi_output_name("resupply"),
            collection(
                [poi("atc_communities:c1", "resupply", "atc_communities", "Unionville", LON, LAT, source_feature_id="c1")]
            ),
        )
        write(
            sandbox["communities"],
            collection([feature(point(LON, LAT), {"GlobalID": "c1", "NAME": "Unionville", "STATE": "NY"})]),
        )
        write(sandbox["lines"][0], collection([feature(line(LON, LAT, 1), {"source": "oprhp_trails", "name": "T"})]))

        output, _ = build(sandbox)

        [town] = by_kind(output, "town")
        assert town["state"] == "NY"

    def test_a_resupply_point_that_is_not_a_community_is_not_a_town(self, sandbox):
        write(
            sandbox["poi_dir"] / poi_output_name("resupply"),
            collection([poi("opentrail_at:r1", "resupply", "opentrail_at", "Outfitter", LON, LAT)]),
        )
        write(sandbox["lines"][0], collection([feature(line(LON, LAT, 1), {"source": "oprhp_trails", "name": "T"})]))

        output, _ = build(sandbox)

        assert by_kind(output, "town") == []

    def test_a_source_the_registry_gives_no_state_gets_none(self, sandbox):
        write(sandbox["nearby"], collection([poi("usfs_rec_sites:9", "trailhead", "usfs_rec_sites", "Notch", LON, LAT)]))
        write(sandbox["lines"][0], collection([feature(line(LON, LAT, 1), {"source": "oprhp_trails", "name": "T"})]))

        output, _ = build(sandbox)

        [trailhead] = by_kind(output, "trailhead")
        assert "state" not in trailhead

    def test_an_unnamed_lot_is_not_searchable_and_does_not_ship(self, sandbox):
        write(sandbox["nearby"], collection([poi("dec_parking_areas:3", "parking", "dec_parking_areas", None, LON, LAT)]))
        write(sandbox["lines"][0], collection([feature(line(LON, LAT, 1), {"source": "oprhp_trails", "name": "T"})]))

        output, _ = build(sandbox)

        assert by_kind(output, "parking") == []

    def test_the_same_waypoint_in_two_artifacts_ships_once(self, sandbox):
        write(
            sandbox["poi_dir"] / poi_output_name("parking"),
            collection([poi("atc_parking:p1", "parking", "atc_parking", "Lot", LON, LAT)]),
        )
        write(sandbox["nearby"], collection([poi("atc_parking:p1", "parking", "atc_parking", "Lot", LON, LAT)]))
        write(sandbox["lines"][0], collection([feature(line(LON, LAT, 1), {"source": "oprhp_trails", "name": "T"})]))

        output, _ = build(sandbox)

        assert len(by_kind(output, "parking")) == 1


class TestTrails:
    def test_a_named_trail_over_the_threshold_ships_with_its_length_and_bbox(self, sandbox):
        long_miles = exporter.NAMED_TRAIL_THRESHOLD_MILES + 10
        write(
            sandbox["lines"][0],
            collection(
                [
                    feature(line(LON, LAT, long_miles / 2), {"source": "nynjtc_long_path", "name": "Long Path"}),
                    feature(line(LON, LAT + MILE_LAT, long_miles / 2), {"source": "nynjtc_long_path", "name": "Long Path"}),
                    feature(line(LON, LAT, 3), {"source": "oprhp_trails", "name": "Pine Trail"}),
                ]
            ),
        )

        output, _ = build(sandbox)

        [trail] = by_kind(output, "trail")
        assert trail["name"] == "Long Path"
        assert trail["id"] == "trail:nynjtc_long_path:Long Path"
        assert trail["trailMiles"] == pytest.approx(long_miles, abs=0.5)
        assert trail["bbox"][0] == pytest.approx(LON, abs=1e-4)
        assert trail["bbox"][3] == pytest.approx(LAT + MILE_LAT, abs=1e-4)

    def test_the_centerline_is_one_trail_whatever_its_segments_are_called(self, sandbox):
        half = exporter.NAMED_TRAIL_THRESHOLD_MILES * 0.6
        write(
            sandbox["lines"][1],
            collection(
                [
                    feature(
                        line(LON, LAT, half), {"source": exporter.AT_SOURCE, "name": "Georgia section", "blaze_color": "White"}
                    ),
                    feature(
                        line(LON, LAT + MILE_LAT, half),
                        {"source": exporter.AT_SOURCE, "name": "Carolina section", "blaze_color": "White"},
                    ),
                ]
            ),
        )

        output, _ = build(sandbox)

        [trail] = by_kind(output, "trail")
        assert trail["name"] == exporter.AT_NAME
        assert trail["trailMiles"] == pytest.approx(2 * half, abs=0.5)


class TestNoLinesAtAll:
    def test_trail_miles_is_omitted_everywhere_and_the_document_says_so(self, sandbox):
        write(sandbox["parks"], collection([feature(square(LON, LAT, 2), {"GlobalID": "g1", "Name": "Pine State Park"})]))
        write(
            sandbox["nearby"],
            collection(
                [poi("oprhp_facilities:7", "trailhead", "oprhp_facilities", "Reeves Meadow", LON + MILE_LON, LAT + MILE_LAT)]
            ),
        )

        output, report = build(sandbox)

        assert output["trailMilesMeasured"] is False
        assert all("trailMiles" not in place for place in output["places"])
        # Nothing is dropped for being far from a line nobody published.
        assert [place["kind"] for place in output["places"]] == ["park", "trailhead"]
        assert report["dropped_far_from_any_line"] == {}
        assert by_kind(output, "trailhead")[0]["within"] == "Pine State Park"

    def test_a_missing_line_artifact_reads_as_no_lines_not_as_a_failure(self, sandbox):
        for path in sandbox["lines"]:
            path.unlink()

        output, _ = build(sandbox)

        assert output["trailMilesMeasured"] is False


class TestTheDocument:
    def test_rows_carry_no_nulls_and_no_working_geometry(self, sandbox):
        write(sandbox["parks"], collection([feature(square(LON, LAT, 2), {"GlobalID": "g1", "Name": "Pine State Park"})]))
        write(sandbox["lines"][0], collection([feature(line(LON, LAT, 1), {"source": "oprhp_trails", "name": "T"})]))

        output, _ = build(sandbox)

        for place in output["places"]:
            assert None not in place.values()
            assert "geometry" not in place

    def test_the_radius_is_published_beside_the_figures_it_bounds(self, sandbox):
        output, _ = build(sandbox, radius=3.0)

        assert output["trailRadiusMiles"] == 3.0
        assert output["generated_at"] == "2026-09-10T12:00:00Z"

    def test_rows_sort_by_kind_then_name_for_a_stable_diff(self, sandbox):
        write(
            sandbox["parks"],
            collection(
                [
                    feature(square(LON, LAT, 2), {"GlobalID": "g1", "Name": "Zebra Park"}),
                    feature(square(LON + 5 * MILE_LON, LAT, 2), {"GlobalID": "g2", "Name": "Apple Park"}),
                ]
            ),
        )
        write(
            sandbox["nearby"], collection([poi("oprhp_facilities:7", "trailhead", "oprhp_facilities", "Reeves Meadow", LON, LAT)])
        )
        write(sandbox["lines"][0], collection([feature(line(LON, LAT, 1), {"source": "oprhp_trails", "name": "T"})]))

        output, _ = build(sandbox)

        assert [(place["kind"], place["name"]) for place in output["places"]] == [
            ("park", "Apple Park"),
            ("park", "Zebra Park"),
            ("trailhead", "Reeves Meadow"),
        ]


class TestWritingAndPublishing:
    def test_the_manifest_hashes_the_file_it_points_at(self, tmp_path, monkeypatch):
        monkeypatch.setattr(exporter, "OUT_PATH", tmp_path / "places.json")
        monkeypatch.setattr(exporter, "MANIFEST_PATH", tmp_path / "places_manifest.json")
        output = {"generated_at": "x", "trailRadiusMiles": 5.0, "trailMilesMeasured": True, "places": []}

        manifest = exporter.write_artifact(
            output, {"counts": {}, "lines_measured": 0, "dropped_far_from_any_line": {}, "parks_held_back": None}
        )

        assert manifest["path"].endswith("places.json")
        assert manifest["sha256"] == __import__("hashlib").sha256((tmp_path / "places.json").read_bytes()).hexdigest()
        assert json.loads((tmp_path / "places_manifest.json").read_text())["sha256"] == manifest["sha256"]

    def test_publish_collects_it_only_when_the_exporter_wrote_one(self, tmp_path, monkeypatch):
        monkeypatch.setattr(publish, "PROCESSED_DIR", tmp_path)

        assert publish.PLACES_KEY not in publish.collect_artifacts()

        artifact = tmp_path / "places.json"
        artifact.write_text("{}")
        recorded = exporter.to_manifest_path(artifact)
        (tmp_path / "places_manifest.json").write_text(json.dumps({"path": recorded, "sha256": "0" * 64}))

        collected = publish.collect_artifacts()[publish.PLACES_KEY]

        assert (collected["path"], collected["sha256"]) == (recorded, "0" * 64)
