"""export_places.py - the places a hiker can name before anything is downloaded (#1371).

Synthetic geometry in a temp directory, never the real layers (TESTING.md).
Every fixture is a few points and lines around (-74, 41), which is close
enough to Harriman for the metre projection to behave and nowhere near any
real row.

What is pinned: which rows ship and which do not (a park behind its licence
gate, a line whose steward is held back, an unnamed lot, a trailhead with no
published line near it), what each row carries (one row per park UNIT over
the polygons the layer holds, a measured `trailMiles` over the lines this
run publishes, a state code only where the source says it, the park a point
sits inside), and the one absence that must never read as a number - no
lines at all means `trailMiles` is omitted everywhere and the document says so.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import export_places as exporter
import publish
from lib.hashing import sha256_file
from lib.poi_schema import poi_output_name

LON, LAT = -74.0, 41.0
#: One mile in degrees at 41 N, to three figures - close enough for fixtures.
MILE_LON, MILE_LAT = 0.0192, 0.01447
WHEN = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)

#: A unit id, as OPRHP's `MasterAreaID` is: a number the layer carries as one.
UNIT = 127


def feature(geometry: dict | None, properties: dict) -> dict:
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def write(path, *features: dict) -> None:
    """A FeatureCollection of `features` at `path` - none for an empty artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "FeatureCollection", "features": list(features)}))


def registry(parks_reach: bool = True) -> dict:
    """The registry the exporter reads: the park layer with its declared
    fields, a shipped line source, a held-back one, the town layer saying it
    is one, and the organization that publishes New York."""
    return {
        "organizations": {"orgs": {"org:nysoprhp": {"provider": "NYS OPRHP", "state": "NY"}}},
        "sources": [
            {
                "key": exporter.PARKS_KEY,
                "provider": "NYS OPRHP",
                "kind": "external_arcgis_layer",
                "reaches_hikers": parks_reach,
                **exporter.PARK_FIELDS,
            },
            {"key": "oprhp_facilities", "provider": "NYS OPRHP", "kind": "external_arcgis_layer", "reaches_hikers": True},
            {"key": "usfs_rec_sites", "provider": "USFS", "kind": "external_arcgis_layer", "reaches_hikers": True},
            {"key": "communities", "provider": "ATC", "reaches_hikers": True, "place_kind": "town"},
            {"key": "centerline", "provider": "ATC", "reaches_hikers": True, "owns_route_names": ["Appalachian Trail"]},
            {
                "key": "oprhp_trails",
                "provider": "NYS OPRHP",
                "kind": "external_arcgis_layer",
                "blaze_default": "Blue",
                "reaches_hikers": True,
            },
            {
                "key": "held_trails",
                "provider": "Held Org",
                "kind": "external_arcgis_layer",
                "blaze_default": "Red",
                "reaches_hikers": False,
            },
        ],
    }


def square(west: float, south: float, miles: float) -> dict:
    east, north = west + miles * MILE_LON, south + miles * MILE_LAT
    return {"type": "Polygon", "coordinates": [[[west, south], [east, south], [east, north], [west, north], [west, south]]]}


def line(west: float, south: float, miles: float) -> dict:
    """A straight east-west line `miles` long."""
    return {"type": "LineString", "coordinates": [[west, south], [west + miles * MILE_LON, south]]}


def point(lon: float, lat: float) -> dict:
    return {"type": "Point", "coordinates": [lon, lat]}


def park(west: float, south: float, miles: float, global_id: str, name: str, **properties) -> dict:
    return feature(square(west, south, miles), {"GlobalID": global_id, "Name": name, **properties})


def trail(west: float, south: float, miles: float, source: str = "oprhp_trails", name: str = "T") -> dict:
    return feature(line(west, south, miles), {"source": source, "name": name})


def poi(poi_id: str, poi_type: str, source: str, name: str | None, lon: float, lat: float, **extra) -> dict:
    return feature(
        point(lon, lat),
        {"id": poi_id, "poi_type": poi_type, "source": source, "name": name, "lon": lon, "lat": lat, **extra},
    )


def town(poi_id: str, name: str, lon: float, lat: float, community: str = "c1") -> dict:
    return poi(poi_id, "resupply", "atc_communities", name, lon, lat, source_feature_id=community)


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
        write(paths["poi_dir"] / poi_output_name(poi_type))
    for path in (paths["nearby"], paths["parks"], paths["communities"], *paths["lines"]):
        write(path)
    return paths


def anchor_line(paths, west: float = LON, south: float = LAT, miles: float = 1) -> None:
    """Some published line, so measurement runs - what most cases need and none asserts on."""
    write(paths["lines"][0], trail(west, south, miles))


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
        write(sandbox["parks"], park(LON, LAT, 4, "g1", "Pine State Park", Category="State Park"))
        write(
            sandbox["lines"][0],
            trail(LON + 0.5 * MILE_LON, LAT + 2 * MILE_LAT, 3, name="Pine Trail"),
            trail(LON + 10 * MILE_LON, LAT, 2, name="Far Trail"),
        )

        output, report = build(sandbox)

        [row] = by_kind(output, "park")
        assert row["id"] == f"{exporter.PARKS_KEY}:g1"
        assert row["name"] == "Pine State Park"
        assert row["category"] == "State Park"
        assert row["state"] == "NY"
        assert row["trailMiles"] == pytest.approx(3.0, abs=0.1)
        assert output["trailMilesMeasured"] is True
        assert report["parks_held_back"] is None
        assert report["sources"][exporter.PARKS_KEY]["reaches_hikers"] is True

    def test_a_park_centres_on_its_centroid_and_carries_its_bbox(self, sandbox):
        write(sandbox["parks"], park(LON, LAT, 2, "g1", "Square Park"))
        anchor_line(sandbox)

        output, _ = build(sandbox)

        [row] = by_kind(output, "park")
        assert row["lon"] == pytest.approx(LON + MILE_LON, abs=1e-4)
        assert row["lat"] == pytest.approx(LAT + MILE_LAT, abs=1e-4)
        assert row["bbox"] == pytest.approx([LON, LAT, LON + 2 * MILE_LON, LAT + 2 * MILE_LAT], abs=1e-4)

    def test_a_park_is_one_row_however_many_polygons_the_layer_holds(self, sandbox):
        # OPRHP's layer is one polygon per PARCEL: two parcels of one unit,
        # a mile apart, each with a line through it. One row, the unit's
        # own id, the bbox spanning both, the miles summed.
        write(
            sandbox["parks"],
            park(LON, LAT, 2, "g1", "Hudson Highlands", MasterAreaID=UNIT),
            park(LON + 3 * MILE_LON, LAT, 2, "g2", "Hudson Highlands", MasterAreaID=UNIT),
        )
        write(
            sandbox["lines"][0],
            trail(LON, LAT + MILE_LAT, 2),
            trail(LON + 3 * MILE_LON, LAT + MILE_LAT, 2),
        )

        output, report = build(sandbox)

        [row] = by_kind(output, "park")
        assert row["id"] == f"{exporter.PARKS_KEY}:{UNIT}"
        assert row["trailMiles"] == pytest.approx(4.0, abs=0.1)
        assert row["bbox"] == pytest.approx([LON, LAT, LON + 5 * MILE_LON, LAT + 2 * MILE_LAT], abs=1e-4)
        assert report["counts"]["park"] == 1

    def test_two_parks_sharing_a_name_stay_two_rows(self, sandbox):
        # "Robert Moses" is two parks on the live layer (units 127 and 270).
        write(
            sandbox["parks"],
            park(LON, LAT, 2, "g1", "Robert Moses", MasterAreaID=127),
            park(LON + 10 * MILE_LON, LAT, 2, "g2", "Robert Moses", MasterAreaID=270),
        )
        anchor_line(sandbox)

        output, _ = build(sandbox)

        assert sorted(row["id"] for row in by_kind(output, "park")) == [
            f"{exporter.PARKS_KEY}:127",
            f"{exporter.PARKS_KEY}:270",
        ]

    def test_a_unit_takes_the_name_most_of_its_polygons_wear(self, sandbox):
        # Unit 270 on the live layer carries "Captree/Robert Moses" on one
        # parcel and "Robert Moses" on the rest.
        write(
            sandbox["parks"],
            park(LON, LAT, 1, "g1", "Captree/Robert Moses", MasterAreaID=UNIT),
            park(LON + 2 * MILE_LON, LAT, 1, "g2", "Robert Moses", MasterAreaID=UNIT),
            park(LON + 4 * MILE_LON, LAT, 1, "g3", "Robert Moses", MasterAreaID=UNIT),
        )
        anchor_line(sandbox)

        output, _ = build(sandbox)

        [row] = by_kind(output, "park")
        assert row["name"] == "Robert Moses"

    def test_a_polygon_with_no_unit_id_joins_the_unit_that_shares_its_name(self, sandbox):
        # One of Allegany's parcels has no MasterAreaID on the live layer.
        write(
            sandbox["parks"],
            park(LON, LAT, 2, "g1", "Allegany", MasterAreaID=159),
            park(LON + 3 * MILE_LON, LAT, 2, "g2", "Allegany"),
            park(LON + 20 * MILE_LON, LAT, 2, "g3", "Loner"),
        )
        anchor_line(sandbox)

        output, _ = build(sandbox)

        assert sorted(row["id"] for row in by_kind(output, "park")) == [
            f"{exporter.PARKS_KEY}:159",
            f"{exporter.PARKS_KEY}:g3",
        ]
        [allegany] = [row for row in by_kind(output, "park") if row["name"] == "Allegany"]
        assert allegany["bbox"][2] == pytest.approx(LON + 5 * MILE_LON, abs=1e-4)

    def test_the_fields_are_the_registry_entry_s(self, sandbox):
        # A layer whose name and id columns are spelled differently ships
        # through a registry edit, not a code change.
        reg = registry()
        entry = next(source for source in reg["sources"] if source["key"] == exporter.PARKS_KEY)
        entry.update({"name_field": "PARKNAME", "id_field": "OBJECTID", "unit_field": "AreaId"})
        write(sandbox["parks"], feature(square(LON, LAT, 2), {"PARKNAME": "Other Park", "OBJECTID": 7, "AreaId": 9}))
        anchor_line(sandbox)

        output, _ = build(sandbox, reg)

        [row] = by_kind(output, "park")
        assert (row["id"], row["name"]) == (f"{exporter.PARKS_KEY}:9", "Other Park")

    def test_a_park_with_no_published_line_reads_zero_not_absent(self, sandbox):
        # Measured zero is a fact about what a phone would download there.
        write(sandbox["parks"], park(LON, LAT, 2, "g1", "Golf Course"))
        anchor_line(sandbox, west=LON + 20 * MILE_LON)

        output, _ = build(sandbox)

        [row] = by_kind(output, "park")
        assert row["trailMiles"] == 0.0

    def test_parks_ship_behind_their_own_reaches_hikers(self, sandbox):
        write(sandbox["parks"], park(LON, LAT, 2, "g1", "Held Park"))
        anchor_line(sandbox)

        output, report = build(sandbox, registry(parks_reach=False))

        assert by_kind(output, "park") == []
        assert "reaches_hikers false" in report["parks_held_back"]
        assert report["sources"][exporter.PARKS_KEY] == {
            "steward": None,
            "attribution": None,
            "reaches_hikers": False,
            "rows": 0,
        }

    def test_an_unfetched_park_layer_is_a_reason_not_an_error(self, sandbox):
        sandbox["parks"].unlink()

        output, report = build(sandbox)

        assert by_kind(output, "park") == []
        assert "not been fetched" in report["parks_held_back"]

    def test_a_park_with_no_name_or_no_geometry_is_not_a_place(self, sandbox):
        write(
            sandbox["parks"],
            park(LON, LAT, 2, "g1", "  "),
            feature(None, {"GlobalID": "g2", "Name": "Ghost"}),
        )

        output, _ = build(sandbox)

        assert by_kind(output, "park") == []


class TestLines:
    def test_a_line_whose_steward_is_held_back_measures_nothing_and_is_counted(self, sandbox):
        # publish.py holds nearby_trails.geojson back while any source in it
        # is false; a park measured over that file would print miles no
        # phone receives. The gate is applied here, one file earlier.
        write(sandbox["parks"], park(LON, LAT, 4, "g1", "Pine State Park"))
        write(
            sandbox["lines"][0],
            trail(LON + MILE_LON, LAT + 2 * MILE_LAT, 2, source="held_trails", name="Unlicensed Trail"),
            trail(LON + 10 * MILE_LON, LAT, 1),
        )

        output, report = build(sandbox)

        [row] = by_kind(output, "park")
        assert row["trailMiles"] == 0.0
        assert report["lines_held_back"] == {"held_trails": 1}
        assert report["lines_measured"] == 1

    def test_a_trailhead_near_only_a_held_back_line_is_dropped(self, sandbox):
        write(sandbox["nearby"], poi("oprhp_facilities:7", "trailhead", "oprhp_facilities", "Reeves Meadow", LON, LAT))
        write(sandbox["lines"][0], trail(LON, LAT, 1, source="held_trails"), trail(LON + 30 * MILE_LON, LAT, 1))

        output, report = build(sandbox)

        assert by_kind(output, "trailhead") == []
        assert report["dropped_far_from_any_line"] == {"oprhp_facilities/trailhead": 1}

    def test_the_centerline_always_measures(self, sandbox):
        # Its own export, behind its own gate: never in the network's manifest.
        write(sandbox["parks"], park(LON, LAT, 4, "g1", "Pine State Park"))
        write(sandbox["lines"][1], trail(LON + MILE_LON, LAT + 2 * MILE_LAT, 2, source=exporter.AT_SOURCE, name="Georgia"))

        output, report = build(sandbox)

        assert by_kind(output, "park")[0]["trailMiles"] == pytest.approx(2.0, abs=0.1)
        assert report["lines_held_back"] == {}


class TestPointPlaces:
    def test_a_trailhead_near_a_line_ships_with_its_waypoint_id_and_the_park_it_sits_in(self, sandbox):
        write(sandbox["parks"], park(LON, LAT, 4, "g1", "Pine State Park"))
        write(
            sandbox["nearby"],
            poi("oprhp_facilities:7", "trailhead", "oprhp_facilities", "Reeves Meadow", LON + MILE_LON, LAT + MILE_LAT),
        )
        write(sandbox["lines"][0], trail(LON, LAT + 2 * MILE_LAT, 3, name="Pine Trail"))

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
            sandbox["nearby"], poi("usfs_rec_sites:9", "trailhead", "usfs_rec_sites", "Somewhere Far", LON + 40 * MILE_LON, LAT)
        )
        anchor_line(sandbox)

        output, report = build(sandbox)

        assert by_kind(output, "trailhead") == []
        assert report["dropped_far_from_any_line"] == {"usfs_rec_sites/trailhead": 1}

    def test_a_trailhead_with_a_short_line_near_it_is_kept_though_it_prints_zero(self, sandbox):
        # Eighty metres of trail rounds to 0.0 mi on the row; the drop rule
        # reads the metres, not the figure.
        write(sandbox["nearby"], poi("oprhp_facilities:7", "trailhead", "oprhp_facilities", "Stub", LON, LAT))
        anchor_line(sandbox, miles=0.05)

        output, report = build(sandbox)

        [trailhead] = by_kind(output, "trailhead")
        assert trailhead["trailMiles"] == 0.0
        assert report["dropped_far_from_any_line"] == {}

    def test_a_town_with_nothing_published_near_it_is_kept_reading_zero(self, sandbox):
        # "no trail data held" is the row a hiker who lives there should find.
        write(sandbox["poi_dir"] / poi_output_name("resupply"), town("atc_communities:c1", "Harriman", LON + 40 * MILE_LON, LAT))
        anchor_line(sandbox)

        output, report = build(sandbox)

        [row] = by_kind(output, "town")
        assert row["trailMiles"] == 0.0
        assert report["dropped_far_from_any_line"] == {}

    @pytest.mark.parametrize(
        ("written", "published"),
        [("NY", "NY"), ("New York", "NY"), ("virginia", "VA"), ("Virgnia", None), (" ", None), (None, None)],
    )
    def test_a_town_s_state_is_a_code_whatever_the_communities_layer_wrote(self, sandbox, written, published):
        # The live layer writes full names, one misspelling and fourteen
        # blanks (2026-09-10); the artifact speaks one vocabulary and never
        # guesses at a typo.
        write(sandbox["poi_dir"] / poi_output_name("resupply"), town("atc_communities:c1", "Unionville", LON, LAT))
        write(sandbox["communities"], feature(point(LON, LAT), {"GlobalID": "c1", "NAME": "Unionville", "STATE": written}))
        anchor_line(sandbox)

        output, _ = build(sandbox)

        [row] = by_kind(output, "town")
        assert row.get("state") == published

    def test_a_resupply_point_whose_layer_is_not_a_town_layer_is_not_a_town(self, sandbox):
        write(
            sandbox["poi_dir"] / poi_output_name("resupply"),
            poi("opentrail_at:r1", "resupply", "opentrail_at", "Outfitter", LON, LAT),
        )
        anchor_line(sandbox)

        output, _ = build(sandbox)

        assert by_kind(output, "town") == []

    def test_a_source_whose_organization_declares_no_state_gets_none(self, sandbox):
        write(sandbox["nearby"], poi("usfs_rec_sites:9", "trailhead", "usfs_rec_sites", "Notch", LON, LAT))
        anchor_line(sandbox)

        output, _ = build(sandbox)

        [trailhead] = by_kind(output, "trailhead")
        assert "state" not in trailhead

    def test_an_unnamed_lot_is_not_searchable_and_does_not_ship(self, sandbox):
        write(sandbox["nearby"], poi("dec_parking_areas:3", "parking", "dec_parking_areas", None, LON, LAT))
        anchor_line(sandbox)

        output, _ = build(sandbox)

        assert by_kind(output, "parking") == []

    def test_the_same_waypoint_in_two_artifacts_ships_once(self, sandbox):
        write(sandbox["poi_dir"] / poi_output_name("parking"), poi("atc_parking:p1", "parking", "atc_parking", "Lot", LON, LAT))
        write(sandbox["nearby"], poi("atc_parking:p1", "parking", "atc_parking", "Lot", LON, LAT))
        anchor_line(sandbox)

        output, _ = build(sandbox)

        assert len(by_kind(output, "parking")) == 1


class TestTrails:
    def test_a_named_trail_over_the_threshold_ships_with_its_length_and_bbox(self, sandbox):
        long_miles = exporter.NAMED_TRAIL_THRESHOLD_MILES + 10
        write(
            sandbox["lines"][0],
            trail(LON, LAT, long_miles, name="Long Path"),
            trail(LON, LAT + MILE_LAT, 3, name="Short Spur"),
        )

        output, _ = build(sandbox)

        [row] = by_kind(output, "trail")
        assert row["id"] == "trail:oprhp_trails:Long Path"
        assert row["name"] == "Long Path"
        assert row["trailMiles"] == pytest.approx(long_miles, abs=0.5)
        assert row["bbox"] == pytest.approx([LON, LAT, LON + long_miles * MILE_LON, LAT], abs=1e-4)
        assert row["lon"] == pytest.approx(LON + long_miles * MILE_LON / 2, abs=1e-4)
        assert "poiId" not in row

    def test_the_centerline_is_one_trail_under_the_route_name_its_source_owns(self, sandbox):
        half = exporter.NAMED_TRAIL_THRESHOLD_MILES * 0.6
        write(
            sandbox["lines"][1],
            trail(LON, LAT, half, source=exporter.AT_SOURCE, name="Georgia section"),
            trail(LON, LAT + MILE_LAT, half, source=exporter.AT_SOURCE, name="Carolina section"),
        )

        output, _ = build(sandbox)

        [row] = by_kind(output, "trail")
        assert row["name"] == "Appalachian Trail"
        assert row["trailMiles"] == pytest.approx(2 * half, abs=0.5)


class TestNoLinesAtAll:
    def test_trail_miles_is_omitted_everywhere_and_the_document_says_so(self, sandbox):
        write(sandbox["parks"], park(LON, LAT, 2, "g1", "Pine State Park"))
        write(
            sandbox["nearby"],
            poi("oprhp_facilities:7", "trailhead", "oprhp_facilities", "Reeves Meadow", LON + MILE_LON, LAT + MILE_LAT),
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
    def test_rows_carry_no_nulls_and_no_working_state(self, sandbox):
        write(sandbox["parks"], park(LON, LAT, 2, "g1", "Pine State Park"))
        write(sandbox["nearby"], poi("oprhp_facilities:7", "trailhead", "oprhp_facilities", "Reeves Meadow", LON, LAT))
        anchor_line(sandbox)

        output, _ = build(sandbox)

        for place in output["places"]:
            assert None not in place.values()
            assert not {"parts", "names", "categories", "_metres"} & place.keys()

    def test_the_radius_is_published_beside_the_figures_it_bounds(self, sandbox):
        output, _ = build(sandbox, radius=3.0)

        assert output["trailRadiusMiles"] == 3.0
        assert output["generated_at"] == "2026-09-10T12:00:00Z"

    def test_rows_sort_by_kind_then_name_for_a_stable_diff(self, sandbox):
        write(sandbox["parks"], park(LON, LAT, 2, "g1", "Zebra Park"), park(LON + 5 * MILE_LON, LAT, 2, "g2", "Apple Park"))
        write(sandbox["nearby"], poi("oprhp_facilities:7", "trailhead", "oprhp_facilities", "Reeves Meadow", LON, LAT))
        anchor_line(sandbox)

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
        assert manifest["sha256"] == sha256_file(tmp_path / "places.json")
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
