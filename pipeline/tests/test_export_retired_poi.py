"""The tombstones, and the resolver that reads them (#673).

features/POI_IDENTITY.md states the property these hold: *every id ever
published resolves to something - a live POI, or a tombstone that says what
happened.* `check_poi_identity` already holds the live half. These hold the
other one, plus `lib/poi_identity.resolve`, which is the single
implementation the backend and client halves are meant to be ported from
rather than reinvented.
"""

import json
from pathlib import Path

import pytest

import export_retired_poi
from lib.poi_identity import live_rows, resolve, retired_rows


def _row(name="Test Shelter", lat=41.0, lon=-74.0, retired=None, superseded_by=None, poi_type="shelter"):
    row = {"poi_type": poi_type, "source": "atc_shelters", "source_feature_id": "k", "name": name, "lat": lat, "lon": lon}
    if retired:
        row["retired"] = retired
    if superseded_by:
        row["superseded_by"] = superseded_by
    return row


# --- The resolver ----------------------------------------------------------


def test_a_live_id_resolves_to_itself():
    pois = {"a": _row()}
    assert resolve(pois, "a") == "a"


def test_a_superseded_tombstone_resolves_to_its_survivor():
    """The whole point of the edge: a hiker's photos follow it home."""
    pois = {"gone": _row(retired="2027-09-14", superseded_by="here"), "here": _row()}
    assert resolve(pois, "gone") == "here"


def test_a_place_merged_twice_still_arrives_somewhere():
    pois = {
        "first": _row(retired="2027-09-14", superseded_by="second"),
        "second": _row(retired="2028-09-12", superseded_by="third"),
        "third": _row(),
    }
    assert resolve(pois, "first") == "third"


def test_a_bare_tombstone_resolves_to_nothing_rather_than_to_somewhere_near():
    """The honest unknown, and the reason this returns None instead of a
    best guess: "this place is gone and nothing took its place" is what the
    tombstone card exists to say. A nearby id here would be the confident
    wrong merge every threshold in this design is tuned away from."""
    pois = {"gone": _row(retired="2027-09-14"), "unrelated": _row(lat=41.001)}
    assert resolve(pois, "gone") is None


def test_an_id_this_ledger_never_held_resolves_to_nothing():
    assert resolve({"a": _row()}, "atc_shelters:never-published") is None


def test_a_cycle_returns_none_rather_than_hanging():
    """`merged_into` is a file a person edits, and "the resolver hung" is a
    bad way to learn two rows point at each other."""
    pois = {
        "a": _row(retired="2027-09-14", superseded_by="b"),
        "b": _row(retired="2027-09-14", superseded_by="a"),
    }
    assert resolve(pois, "a") is None


def test_live_and_retired_partition_the_ledger():
    pois = {"live": _row(), "gone": _row(retired="2027-09-14")}
    assert list(live_rows(pois)) == ["live"]
    assert list(retired_rows(pois)) == ["gone"]


# --- The artifact ----------------------------------------------------------


def test_a_tombstone_carries_the_design_s_fields():
    pois = {"gone": _row(name="Old Shelter", retired="2028-09-12", superseded_by="here"), "here": _row()}

    collection, dangling = export_retired_poi.build(pois)

    assert dangling == []
    (feature,) = collection["features"]
    assert collection["type"] == "FeatureCollection"
    assert feature["geometry"] == {"type": "Point", "coordinates": [-74.0, 41.0]}
    assert feature["properties"] == {
        "id": "gone",
        "poi_type": "shelter",
        "source": "atc_shelters",
        "retired": "2028-09-12",
        "name": "Old Shelter",
        "superseded_by": "here",
    }


def test_every_tombstone_says_who_dropped_the_place():
    """The card's sentence is built from this and cannot be built without it.

    features/POI_IDENTITY.md section 4: the copy "cannot hard-code 'No longer
    in ATC\'s data\'". Measured against the real ledger 2026-08-22, the 93
    retired rows come from two sources - `atc_csi` and `opentrail_at` - so a
    tombstone missing `source` is one the client can only describe vaguely.

    Deliberately NOT optional the way `name` and `superseded_by` are: those
    two have honest absent states, and "we do not know where this came from"
    is not one the ledger can produce.
    """
    pois = {
        "water": _row(retired="2028-09-12", poi_type="water"),
        "spring": dict(_row(retired="2028-09-12", poi_type="water"), source="opentrail_at"),
    }

    collection, _ = export_retired_poi.build(pois)

    assert {feature["properties"]["source"] for feature in collection["features"]} == {
        "atc_shelters",
        "opentrail_at",
    }


def test_the_source_published_is_the_ledgers_and_not_the_ids_prefix():
    """A source swap keeps the id and moves the column (section 5), so the
    prefix is history and the column is the fact.

    This is the shortcut that looks free - ids are minted
    `{source}:{source_feature_id}` - and would have the card name the source
    a place came from years ago, confidently and wrongly.
    """
    swapped = dict(_row(retired="2028-09-12"), source="atc_csi")

    (feature,) = export_retired_poi.build({"opentrail_at:9": swapped})[0]["features"]

    assert feature["properties"]["id"].startswith("opentrail_at:")
    assert feature["properties"]["source"] == "atc_csi"


def test_a_tombstone_with_no_successor_omits_superseded_by_rather_than_nulling_it():
    """Absent means "nothing took this place's place". A null would invite a
    reader to treat the two as one state, and most tombstones have no
    successor."""
    collection, _ = export_retired_poi.build({"gone": _row(retired="2028-09-12")})

    assert "superseded_by" not in collection["features"][0]["properties"]


def test_live_rows_are_not_published_as_tombstones():
    pois = {"live": _row(), "gone": _row(retired="2028-09-12")}

    collection, _ = export_retired_poi.build(pois)

    assert [feature["properties"]["id"] for feature in collection["features"]] == ["gone"]


def test_a_ledger_that_has_retired_nothing_publishes_an_empty_collection():
    """The healthy state of a new bucket, and the reason check 14 gives this
    artifact a minimum of zero."""
    collection, dangling = export_retired_poi.build({"live": _row()})

    assert collection == {"type": "FeatureCollection", "features": []}
    assert dangling == []


def test_an_edge_that_leads_nowhere_is_reported_rather_than_published():
    """reconcile_poi_identity refuses to write such an edge, so one here
    came from a ledger edited by hand - which is the case a check is for.
    Publishing it would strand the photos it was supposed to carry."""
    pois = {"gone": _row(retired="2028-09-12", superseded_by="atc_shelters:not-a-row")}

    _, dangling = export_retired_poi.build(pois)

    assert len(dangling) == 1
    assert "resolves to no live row" in dangling[0]


def test_main_refuses_to_write_a_ledger_whose_edges_dangle(tmp_path, monkeypatch):
    ledger = tmp_path / "poi_identity.json"
    ledger.write_text(json.dumps({"pois": {"gone": _row(retired="2028-09-12", superseded_by="nowhere")}}))
    monkeypatch.setattr(export_retired_poi, "LEDGER_PATH", ledger)
    monkeypatch.setattr(export_retired_poi, "OUT_PATH", tmp_path / "retired_poi.geojson")
    monkeypatch.setattr(export_retired_poi, "MANIFEST_PATH", tmp_path / "retired_poi_manifest.json")

    with pytest.raises(SystemExit) as excinfo:
        export_retired_poi.main()

    assert "strands them" in str(excinfo.value)
    assert not (tmp_path / "retired_poi.geojson").exists()


def test_main_writes_the_artifact_and_a_manifest_that_hashes_it(tmp_path, monkeypatch):
    ledger = tmp_path / "poi_identity.json"
    ledger.write_text(json.dumps({"pois": {"gone": _row(retired="2028-09-12", superseded_by="here"), "here": _row()}}))
    out = tmp_path / "retired_poi.geojson"
    manifest_path = tmp_path / "retired_poi_manifest.json"
    monkeypatch.setattr(export_retired_poi, "LEDGER_PATH", ledger)
    monkeypatch.setattr(export_retired_poi, "OUT_PATH", out)
    monkeypatch.setattr(export_retired_poi, "MANIFEST_PATH", manifest_path)

    manifest = export_retired_poi.main()

    from lib.hashing import sha256_file

    assert manifest["retired_count"] == 1
    assert manifest["superseded_count"] == 1
    assert manifest["sha256"] == sha256_file(out)
    assert json.loads(out.read_text())["features"][0]["properties"]["id"] == "gone"


def test_no_ledger_is_the_pre_671_world_and_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(export_retired_poi, "LEDGER_PATH", tmp_path / "absent.json")
    monkeypatch.setattr(export_retired_poi, "OUT_PATH", tmp_path / "retired_poi.geojson")

    assert export_retired_poi.main() == {}
    assert not (tmp_path / "retired_poi.geojson").exists()


def test_the_artifact_name_stays_outside_the_live_poi_namespace():
    """`poi_*.geojson` means "live rows of one poi_type" to check 21, to
    publish.referenced_photo_keys and to the client's poiKey(). A tombstone
    file under that prefix would fail check 21 once per feature, and the
    name cannot be changed after the first publish (lib/r2_keys.py)."""
    assert not export_retired_poi.OUT_PATH.name.startswith("poi_")
    assert export_retired_poi.OUT_PATH.name == "retired_poi.geojson"


# --- The contract the two runtimes share ------------------------------------


def test_the_shared_cases_run_through_this_runtimes_resolver():
    """One resolver per runtime, held together by these cases (#831).

    features/POI_IDENTITY.md section 4 asks for "a resolver, in one place,
    used by the backend's serialisers and the client rather than implemented
    twice". Across Python and TypeScript with no shared package the
    achievable version is one implementation per runtime, each in one file,
    compared against shared fixtures - the pattern three tests in
    `backend/tests/` already use.

    This is the Python half. `client/src/lib/poiIdentity.contract.test.ts` is
    the other, over this same file, and the client workflow's scope list
    carries `pipeline/tests/fixtures/` so editing a case runs both suites.

    The cases are deliberately not restated here: a copy is the third place
    to keep in step, and the drift between copies is the bug the whole
    arrangement exists to catch.
    """
    cases = json.loads((Path(__file__).parent / "fixtures" / "poi_resolver_cases.json").read_text())["cases"]
    assert len(cases) >= 9, "the fixture lost cases - both runtimes are now checked against less"

    for case in cases:
        # `_row` supplies the fields the resolver ignores; the fixture
        # supplies the two it reads.
        pois = {
            poi_id: _row(retired=row.get("retired"), superseded_by=row.get("superseded_by"))
            for poi_id, row in case["ledger"].items()
        }
        assert resolve(pois, case["query"]) == case["expected"], case["name"]
