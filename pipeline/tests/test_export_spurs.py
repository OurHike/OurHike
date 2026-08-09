"""Tests for export_spurs.py - publishing what each spur leads to.

Why this exists
---------------
The join itself is tested in test_lib_spurs.py. This is about the wiring
around it, where the failures are less about geometry and more about two
artifacts having to agree:

- The spur record's key must be the id `trails.geojson` uses, or the app holds
  two files that cannot be joined.
- The destination id must be the id export_poi.py publishes, or the link
  points at a POI the device has never heard of.

Both are silent when wrong. A mismatched key produces a perfectly valid file
in which nothing resolves, which looks identical to a trail network where
nothing leads anywhere.

That is not hypothetical, and this file is why it survived. Every fixture
below used to hand-spell the POI filename as `poi_shelter.geojson` - the R2
key, not the name on disk - which is precisely the mistake export_spurs.py
was making, so the suite agreed with the bug and 784 spurs shipped with a
null destination (#469). A fixture that restates the reader's assumption can
only ever confirm it. So the filename is now asked for once, from
lib/poi_schema.py, and the contract test at the bottom of this section runs
the real writer into a directory and the real reader back out of it - the
only arrangement here in which a disagreement between the two ends fails.
"""

import json

import duckdb
import pytest

import export_poi
import export_spurs
from lib.poi_schema import POI_TYPES, poi_output_name

TRAIL_LAT, TRAIL_LON = 40.0, -75.0
TYPE_DOMAIN = {"0": "Access (eg Parking)", "1": "Alternate Route", "3": "Spur (eg View, Camp)"}


def north(meters):
    return TRAIL_LAT + meters / 111_320.0


CENTERLINE = [
    {
        "geometry": {
            "type": "LineString",
            "coordinates": [[TRAIL_LON + i * 0.0001, TRAIL_LAT] for i in range(20)],
        }
    }
]


def side_trail(feature_id, type_code, *, name="Spur Trail", length_ft=385, far=300):
    return {
        "properties": {
            "GlobalID": feature_id,
            "Type": type_code,
            "Name": name,
            "Length_Ft": length_ft,
        },
        "geometry": {
            "type": "LineString",
            "coordinates": [[TRAIL_LON, TRAIL_LAT], [TRAIL_LON, north(far)]],
        },
    }


def shelter(poi_id, far=300):
    return {"id": poi_id, "lat": north(far), "lon": TRAIL_LON}


# --- The join the two artifacts have to agree on ---------------------------


def test_a_spur_is_keyed_the_way_trails_geojson_keys_it():
    """export_trails.py builds ids as `{source_key}:{feature_id}`. A different
    key here produces a valid file in which nothing joins - and nothing about
    that looks like an error."""
    records = export_spurs.build_spur_records([side_trail("abc-123", "3")], CENTERLINE, [], TYPE_DOMAIN)

    assert list(records) == ["side_trails:abc-123"]


def test_a_null_global_id_resolves_to_the_same_id_on_both_sides():
    """The drift this test exists to prevent: this file used to build ids
    from a LOCAL copy of the fallback chain (`GlobalID or OBJECTID or
    index`), and a feature with an explicit "GlobalID": null - a real shape
    in ArcGIS exports - got `generated-{index}` in trails.geojson but its
    OBJECTID here. Both files were valid; the spur just never joined. The
    chain now has one home, lib/feature_id.py, so both sides are asked
    rather than assumed."""
    from lib.feature_id import resolve_feature_id

    feature = side_trail(None, "3")
    feature["properties"]["OBJECTID"] = 7

    records = export_spurs.build_spur_records([feature], CENTERLINE, [], TYPE_DOMAIN)

    trails_side = resolve_feature_id("side_trails", feature, feature["properties"], 0)
    assert list(records) == [f"side_trails:{trails_side}"]
    assert list(records) == ["side_trails:generated-0"]


def test_the_destination_is_a_published_poi_id():
    records = export_spurs.build_spur_records(
        [side_trail("abc-123", "3")], CENTERLINE, [shelter("shelter:rocky-run")], TYPE_DOMAIN
    )

    assert records["side_trails:abc-123"]["destination_poi_id"] == "shelter:rocky-run"


def test_destination_pois_are_read_from_the_published_files_not_the_raw_ones(tmp_path):
    """The ordering constraint, made concrete. Resolving against raw ATC
    points would publish ids that match nothing on the device."""
    poi_dir = tmp_path / "poi"
    poi_dir.mkdir()
    (poi_dir / poi_output_name("shelter")).write_text(
        json.dumps({"features": [{"properties": {"id": "shelter:rocky-run", "lat": 40.0, "lon": -75.0}}]})
    )

    pois = export_spurs.load_destination_pois(poi_dir, ("shelter",))

    assert [p["id"] for p in pois] == ["shelter:rocky-run"]


def test_the_real_exporter_writes_what_the_real_reader_looks_for(tmp_path, monkeypatch):
    """The one test here that could have caught #469, and the only one that
    can catch its successor.

    Every other test in this file supplies the POI file itself, so it proves
    what load_destination_pois does with a directory the test invented. This
    one never names a file: export_poi.write_poi_type puts it there and
    load_destination_pois goes looking, and if those two ever disagree about
    the spelling again the assert below returns an empty list. That is what
    an integration point deserves when both sides of it fail silently -
    a missing POI file is a legal empty result, so nothing else in this
    pipeline will raise when the contract breaks.

    Deliberately not parameterised over every poi_type: the failure mode is a
    naming convention, which is either right for all of them or wrong for all
    of them, and one round trip through DuckDB's GDAL writer is enough to
    prove it while staying cheap.
    """
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    poi_dir = tmp_path / "poi"
    poi_dir.mkdir()
    monkeypatch.setattr(export_poi, "OUT_DIR", poi_dir)

    export_poi.write_poi_type(
        con,
        "shelter",
        [
            {
                "id": "atc_shelters:rocky-run",
                "poi_type": "shelter",
                "trail_id": "AT",
                "source": "atc_shelters",
                "source_feature_id": "rocky-run",
                "name": "Rocky Run",
                "lat": TRAIL_LAT,
                "lon": TRAIL_LON,
                "confidence": "high",
            }
        ],
    )

    pois = export_spurs.load_destination_pois(poi_dir, ("shelter",))

    assert [p["id"] for p in pois] == ["atc_shelters:rocky-run"], (
        f"export_poi wrote {sorted(p.name for p in poi_dir.iterdir())}, export_spurs read {poi_dir / poi_output_name('shelter')}"
    )


def test_a_poi_type_that_was_never_exported_is_skipped_not_fatal(tmp_path):
    """A partial export is a state this pipeline supports. The honest cost is
    fewer resolved spurs, not a failed run."""
    poi_dir = tmp_path / "poi"
    poi_dir.mkdir()

    assert export_spurs.load_destination_pois(poi_dir, ("shelter", "water")) == []


# --- Which POI types count as a destination --------------------------------
#
# The list is a subset of POI_TYPES and should stay one - features/
# SPUR_TRAILS.md's restraint is real, and "everything is a destination" would
# put a privy on the line detail sheet. What it must not be is a subset by
# OMISSION, which is what it was until #492: a sixth POI category would have
# been silently ineligible, and the spurs leading to it would publish a null
# destination with no error, no warning and nothing failing.
#
# That silence is the shape of #469 reached through a different hole. So the
# two lists are asserted to PARTITION POI_TYPES, and the failure names the
# type nobody has classified.


def test_every_poi_type_is_classified_as_a_destination_or_explicitly_not():
    """The partition, which is what turns a new category into a decision.

    Both directions are a defect. A type in neither list is the silent
    ineligibility this exists to stop. A type in a list that POI_TYPES does
    not have is a classification for something nothing publishes, which reads
    as coverage while resolving nothing.
    """
    classified = set(export_spurs.DESTINATION_POI_TYPES) | set(export_spurs.NOT_A_DESTINATION_POI_TYPES)
    published = set(POI_TYPES)

    assert classified == published, (
        "export_spurs.py and lib/poi_schema.POI_TYPES disagree about the POI "
        "categories. A type in neither list is not an error anywhere - the "
        "spurs leading to it just publish a null destination, and the line "
        "detail sheet says nothing about where that trail goes.\n"
        f"  published but unclassified: {sorted(published - classified)}\n"
        f"  classified but not published: {sorted(classified - published)}"
    )


def test_the_two_lists_do_not_overlap():
    """A type in both is not a partition, and the reader would win silently -
    `load_destination_pois` iterates DESTINATION_POI_TYPES and never consults
    the other list, so the exclusion would be documentation rather than fact."""
    both = set(export_spurs.DESTINATION_POI_TYPES) & set(export_spurs.NOT_A_DESTINATION_POI_TYPES)

    assert not both, f"classified as both a destination and not one: {sorted(both)}"


def test_an_excluded_type_is_not_read_even_when_its_file_is_there(tmp_path):
    """The classification has to be the one that actually runs.

    `load_destination_pois` takes a `types` argument that every test above
    supplies, so its DEFAULT is the only place the decision reaches the real
    export - and a default that drifted from the constant would make the
    partition above a statement about a list nothing uses.

    Asserted by putting a file there for every published type, including the
    excluded one, and calling with no `types` at all. A `crossing` id coming
    back would mean the exclusion is documentation rather than behaviour.
    """
    poi_dir = tmp_path / "poi"
    poi_dir.mkdir()
    for poi_type in POI_TYPES:
        (poi_dir / poi_output_name(poi_type)).write_text(
            json.dumps({"features": [{"properties": {"id": f"{poi_type}:one", "lat": 40.0, "lon": -75.0}}]})
        )

    found = {poi["id"] for poi in export_spurs.load_destination_pois(poi_dir)}

    assert found == {f"{poi_type}:one" for poi_type in export_spurs.DESTINATION_POI_TYPES}
    for poi_type in export_spurs.NOT_A_DESTINATION_POI_TYPES:
        assert f"{poi_type}:one" not in found


# --- Which side trails count -----------------------------------------------


def test_only_type_three_side_trails_are_published():
    """Access approaches and alternate routes are real and are not spurs.
    ATC codes them separately, so this is a filter rather than a judgement."""
    records = export_spurs.build_spur_records(
        [side_trail("spur", "3"), side_trail("parking", "0"), side_trail("alternate", "1")],
        CENTERLINE,
        [],
        TYPE_DOMAIN,
    )

    assert list(records) == ["side_trails:spur"]


def test_an_undecodable_type_is_warned_about_not_silently_dropped(capsys):
    """Same convention as the blaze decode and the corrupted-quad check. A
    count that quietly moved is how a data regression survives."""
    export_spurs.build_spur_records([side_trail("mystery", "not a code")], CENTERLINE, [], TYPE_DOMAIN)

    assert "undecodable" in capsys.readouterr().out


def test_a_side_trail_with_no_type_at_all_is_not_warned_about():
    """Absent is not the same as unrecognised, and warning about every
    untyped feature would bury the ones that mean something."""
    untyped = side_trail("untyped", None)

    records = export_spurs.build_spur_records([untyped], CENTERLINE, [], TYPE_DOMAIN)

    assert records == {}


# --- What each record carries ----------------------------------------------


def test_length_is_atc_s_own_survey_not_a_recomputation():
    """They measured it with GNSS. Recomputing from the simplified geometry
    would be a worse number arrived at with more work."""
    records = export_spurs.build_spur_records([side_trail("abc", "3", length_ft=23_918)], CENTERLINE, [], TYPE_DOMAIN)

    assert records["side_trails:abc"]["length_ft"] == 23_918


def test_a_spur_with_no_destination_still_publishes_a_record():
    """It is still drawn, and the sheet still has its name, length and blaze
    to show. Omitting the record would make an unresolved spur indistinguish-
    able from one that is not a spur."""
    records = export_spurs.build_spur_records([side_trail("lonely", "3")], CENTERLINE, [], TYPE_DOMAIN)

    assert records["side_trails:lonely"]["destination_poi_id"] is None
    assert records["side_trails:lonely"]["name"] == "Spur Trail"


def test_the_match_distance_travels_with_the_link():
    """The open question this defers rather than answers: 150 m captures 88%
    of spurs, 50 m captures 77% with far higher confidence, and the client
    picks. Dropping the distance here would settle it by accident."""
    records = export_spurs.build_spur_records(
        [side_trail("abc", "3", far=300)], CENTERLINE, [shelter("shelter:x", far=380)], TYPE_DOMAIN
    )

    assert records["side_trails:abc"]["destination_distance_m"] == pytest.approx(80, abs=3)


def test_a_null_geometry_feature_survives_the_run():
    """One real side_trails feature ("Alec Kennedy Tent Pad Spur Trail #s 2 &
    3") has null geometry. The export already survives it for rendering and
    must survive it here."""
    broken = {"properties": {"GlobalID": "broken", "Type": "3"}, "geometry": None}

    records = export_spurs.build_spur_records([broken], CENTERLINE, [], TYPE_DOMAIN)

    assert records["side_trails:broken"]["destination_poi_id"] is None


def test_the_output_is_keyed_by_id_so_the_client_can_look_one_up(tmp_path, monkeypatch, capsys):
    """A list would make the client scan for every tap. A map is the shape the
    only consumer actually needs."""
    monkeypatch.setattr(export_spurs, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(export_spurs, "POI_DIR", tmp_path / "poi")
    monkeypatch.setattr(export_spurs, "OUT_PATH", tmp_path / "spurs.json")
    monkeypatch.setattr(export_spurs, "MANIFEST_PATH", tmp_path / "spurs_manifest.json")
    monkeypatch.setattr(export_spurs, "SOURCES_PATH", tmp_path / "sources.json")

    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "side_trails.geojson").write_text(json.dumps({"features": [side_trail("abc", "3")]}))
    (tmp_path / "raw" / "centerline.geojson").write_text(json.dumps({"features": CENTERLINE}))
    (tmp_path / "poi").mkdir()
    (tmp_path / "poi" / poi_output_name("shelter")).write_text(
        json.dumps({"features": [{"properties": shelter("shelter:rocky-run")}]})
    )

    manifest = export_spurs.main()

    published = json.loads((tmp_path / "spurs.json").read_text())
    assert published["side_trails:abc"]["destination_poi_id"] == "shelter:rocky-run"
    assert manifest["spur_count"] == 1
    assert manifest["resolved_count"] == 1
    capsys.readouterr()


def test_a_run_with_no_published_pois_warns_rather_than_resolving_nothing_quietly(tmp_path, monkeypatch, capsys):
    """Every spur resolving to nothing looks exactly like a trail network
    where nothing leads anywhere, and that is not a thing to publish
    silently."""
    monkeypatch.setattr(export_spurs, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(export_spurs, "POI_DIR", tmp_path / "missing")
    monkeypatch.setattr(export_spurs, "OUT_PATH", tmp_path / "spurs.json")
    monkeypatch.setattr(export_spurs, "MANIFEST_PATH", tmp_path / "spurs_manifest.json")
    monkeypatch.setattr(export_spurs, "SOURCES_PATH", tmp_path / "sources.json")

    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "side_trails.geojson").write_text(json.dumps({"features": [side_trail("abc", "3")]}))
    (tmp_path / "raw" / "centerline.geojson").write_text(json.dumps({"features": CENTERLINE}))

    export_spurs.main()

    assert "no published POIs" in capsys.readouterr().out
