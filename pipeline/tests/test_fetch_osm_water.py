"""Tests for fetch_osm_water.py - OSM water point sources from the Geofabrik
state extracts (#529). Synthetic rows throughout, never a real extract: the
smallest state file is 45 MB, and everything decision-shaped here - the
classification, the feature shape, the two write guards - is pure or
monkeypatchable without one (TESTING.md).
"""

import json

import pytest

import fetch_osm_water
from fetch_osm_water import (
    MAX_FEATURE_DROP_RATIO,
    MIN_FEATURES,
    POINT_SOURCE_TAGS,
    classify_tags,
    feature,
    water_node_query,
)


def _row(node_id=1, kind="spring", **tags):
    """A classified row as scan_states builds them."""
    return {"id": node_id, "lat": 41.0, "lon": -74.0, "kind": kind, **tags}


def test_classify_tags_knows_all_four_point_source_classes():
    assert classify_tags("spring", None, None) == "spring"
    assert classify_tags(None, "drinking_water", None) == "drinking_water"
    assert classify_tags(None, None, "water_tap") == "water_tap"
    assert classify_tags(None, None, "water_well") == "water_well"


def test_classify_tags_rejects_other_values_of_the_same_keys():
    """`natural=tree` and `man_made=tower` carry the right KEYS and must not
    classify - the value is the claim, and the census's comparability with
    the shipped numbers rests on this exact clause set."""
    assert classify_tags("tree", None, None) is None
    assert classify_tags("water", None, None) is None  # the pond question stays undecided
    assert classify_tags(None, "shelter", None) is None
    assert classify_tags(None, None, "tower") is None
    assert classify_tags(None, None, None) is None


def test_the_sql_filter_is_derived_from_the_same_clause_set():
    """The WHERE clause names each (tag, value) pair exactly - derived from
    POINT_SOURCE_TAGS, so a class added there reaches the SQL without a
    second edit, which is the drift this assertion pins."""
    query = water_node_query(fetch_osm_water.OUT_PATH)  # any path; only the text is read
    for tag, value in POINT_SOURCE_TAGS:
        assert f"tags['{tag}'] = '{value}'" in query


def test_feature_stringifies_the_node_id_and_carries_only_present_tags():
    built = feature(_row(node_id=8675309, name="Piped Spring", intermittent="yes"))

    assert built["properties"]["osm_id"] == "8675309"
    assert built["properties"]["kind"] == "spring"
    assert built["properties"]["name"] == "Piped Spring"
    assert built["properties"]["intermittent"] == "yes"
    # Absent tags are absent, not null: absence is the normal state and must
    # not be exportable as a value somebody might read as a claim.
    assert "seasonal" not in built["properties"]
    assert "drinking_water" not in built["properties"]
    assert built["geometry"] == {"type": "Point", "coordinates": [-74.0, 41.0]}


@pytest.fixture
def fetch_to_tmp(tmp_path, monkeypatch):
    """Redirect the output and neutralise the network/scan halves, so main()
    exercises only the guards and the write."""
    out_path = tmp_path / "osm_water.geojson"
    monkeypatch.setattr(fetch_osm_water, "OUT_PATH", out_path)
    monkeypatch.setattr(fetch_osm_water, "fetch_states", lambda states, dest, refetch=False: [])
    return out_path


def test_a_scan_below_the_floor_refuses_to_write(fetch_to_tmp, monkeypatch):
    """A first run has no previous file to compare against, so the floor is
    the only thing standing between a broken scan and an empty 'success'."""
    monkeypatch.setattr(fetch_osm_water, "scan_states", lambda paths: [_row(node_id=i) for i in range(MIN_FEATURES - 1)])

    assert fetch_osm_water.main([]) == 1
    assert not fetch_to_tmp.exists()


def test_a_halved_result_refuses_to_overwrite_the_previous_one(fetch_to_tmp, monkeypatch):
    """The opentrail guard, applied here: community editing never deletes
    half the water points in fourteen states between runs, so a drop past
    the ratio is a broken scan and the good file stays."""
    previous = [_row(node_id=i) for i in range(4 * MIN_FEATURES)]
    fetch_to_tmp.write_text(json.dumps({"type": "FeatureCollection", "features": [feature(r) for r in previous]}))

    shrunken = previous[: int(len(previous) * MAX_FEATURE_DROP_RATIO) - 1]
    monkeypatch.setattr(fetch_osm_water, "scan_states", lambda paths: shrunken)

    assert fetch_osm_water.main([]) == 1
    assert len(json.loads(fetch_to_tmp.read_text())["features"]) == len(previous)


def test_a_good_scan_writes_the_collection_and_a_receipt(fetch_to_tmp, monkeypatch):
    rows = [_row(node_id=i) for i in range(MIN_FEATURES)]
    monkeypatch.setattr(fetch_osm_water, "scan_states", lambda paths: rows)

    assert fetch_osm_water.main([]) == 0

    written = json.loads(fetch_to_tmp.read_text())
    assert len(written["features"]) == MIN_FEATURES
    # The receipt is the completion record check_output_quality.py re-hashes
    # (#542); conftest redirects the receipts dir, so load() reads what this
    # run just recorded.
    from lib import fetch_receipts

    receipt = fetch_receipts.load("fetch_osm_water")
    assert receipt is not None
    assert [out["path"] for out in receipt["outputs"]] == [str(fetch_to_tmp)]


# --- the early-out (#1065) --------------------------------------------------


def _boom(*args, **kwargs):
    raise AssertionError("the fetch/scan half must not run on this path")


def test_a_receipted_scan_already_on_disk_is_not_refetched(fetch_to_tmp, monkeypatch):
    """#1065: the run most likely to find its own output on disk is the retry
    of a failed publish, and re-downloading 3.5 GB of extracts to recompute a
    held file is what lost run 33005545820. The copy a verifying receipt
    stands behind is reused."""
    rows = [_row(node_id=i) for i in range(MIN_FEATURES)]
    monkeypatch.setattr(fetch_osm_water, "scan_states", lambda paths: rows)
    assert fetch_osm_water.main([]) == 0  # a real run: output plus receipt

    monkeypatch.setattr(fetch_osm_water, "fetch_states", _boom)
    monkeypatch.setattr(fetch_osm_water, "scan_states", _boom)
    before = fetch_to_tmp.read_bytes()

    assert fetch_osm_water.main([]) == 0
    assert fetch_to_tmp.read_bytes() == before


def test_refetch_still_forces_a_real_scan(fetch_to_tmp, monkeypatch):
    """The escape hatch: --refetch means current data, whatever is on disk."""
    rows = [_row(node_id=i) for i in range(MIN_FEATURES)]
    monkeypatch.setattr(fetch_osm_water, "scan_states", lambda paths: rows)
    assert fetch_osm_water.main([]) == 0

    fresh = [_row(node_id=i) for i in range(MIN_FEATURES + 7)]
    monkeypatch.setattr(fetch_osm_water, "scan_states", lambda paths: fresh)

    assert fetch_osm_water.main(["--refetch"]) == 0
    assert len(json.loads(fetch_to_tmp.read_text())["features"]) == MIN_FEATURES + 7


def test_a_copy_without_a_receipt_is_refetched_not_reused(fetch_to_tmp, monkeypatch):
    """A copy the workflow restored from the published bucket carries no
    receipt, and reusing it would fail check_output_quality's
    --fetched gate on the absence - no finished fetch stands behind it."""
    restored = [_row(node_id=i) for i in range(MIN_FEATURES)]
    fetch_to_tmp.write_text(json.dumps({"type": "FeatureCollection", "features": [feature(r) for r in restored]}))

    ran = []
    rows = [_row(node_id=i) for i in range(MIN_FEATURES)]
    monkeypatch.setattr(fetch_osm_water, "scan_states", lambda paths: ran.append(1) or rows)

    assert fetch_osm_water.main([]) == 0
    assert ran

    from lib import fetch_receipts

    assert fetch_receipts.load("fetch_osm_water") is not None


def test_a_drifted_copy_is_refetched_not_reused(fetch_to_tmp, monkeypatch):
    """A receipt that no longer matches the bytes describes a file nobody
    stands behind - the same re-hash check_output_quality applies (#542)."""
    rows = [_row(node_id=i) for i in range(MIN_FEATURES)]
    monkeypatch.setattr(fetch_osm_water, "scan_states", lambda paths: rows)
    assert fetch_osm_water.main([]) == 0

    fetch_to_tmp.write_text(fetch_to_tmp.read_text() + "\n")  # the bytes move under the receipt

    ran = []
    monkeypatch.setattr(fetch_osm_water, "scan_states", lambda paths: ran.append(1) or rows)

    assert fetch_osm_water.main([]) == 0
    assert ran
