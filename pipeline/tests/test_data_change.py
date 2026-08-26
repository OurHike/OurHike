"""Tests for lib/data_change.py - what a phone is told changed, and #919's
rule that a change nobody could read is never the reassuring grade.

Tiny hand-built documents rather than real artifacts, per ../../TESTING.md:
what is under test is the classification, and a fixture large enough to be
realistic would make it harder to see which feature moved.
"""

import json

from lib import data_change
from lib.data_change import CONSEQUENTIAL, ROUTINE, classify, combine


def _fc(*features):
    return json.dumps({"type": "FeatureCollection", "features": list(features)}).encode()


def _poi(identity, lon=-74.0, lat=41.0, **properties):
    return {
        "type": "Feature",
        "properties": {"id": identity, **properties},
        "geometry": {"type": "Point", "coordinates": [lon, lat]},
    }


# --- the two grades ---------------------------------------------------------


def test_nothing_changed_is_routine_and_counts_nothing():
    same = _fc(_poi("osm_water:1"))
    assert classify(same, same) == {"severity": ROUTINE, "added": 0, "removed": 0, "moved": 0, "edited": 0}


def test_an_added_feature_is_routine():
    """A new privy disturbs nothing a hiker was relying on."""
    change = classify(_fc(_poi("a")), _fc(_poi("a"), _poi("b")))
    assert change["severity"] == ROUTINE
    assert change["added"] == 1


def test_an_attribute_edit_is_routine():
    change = classify(_fc(_poi("a")), _fc(_poi("a", name="Big Spring")))
    assert change["severity"] == ROUTINE
    assert change["edited"] == 1
    assert change["moved"] == 0


def test_a_removed_feature_is_consequential():
    """The case this grade exists for: a hiker who planned around a water point
    is the person most affected by its deletion and least likely to notice."""
    change = classify(_fc(_poi("a"), _poi("b")), _fc(_poi("a")))
    assert change["severity"] == CONSEQUENTIAL
    assert change["removed"] == 1


def test_a_moved_feature_is_consequential():
    change = classify(_fc(_poi("a")), _fc(_poi("a", lat=41.5)))
    assert change["severity"] == CONSEQUENTIAL
    assert change["moved"] == 1


def test_a_move_is_a_move_at_any_distance():
    """No threshold, deliberately - nothing simplifies a point, so a coordinate
    that changed at all changed for a reason. See the module docstring."""
    change = classify(_fc(_poi("a")), _fc(_poi("a", lat=41.000001)))
    assert change["moved"] == 1
    assert change["severity"] == CONSEQUENTIAL


def test_a_feature_that_moved_is_not_also_counted_as_edited():
    """One feature, one verdict: the geometry is the more serious of the two
    and counting it twice would inflate every total a prompt shows."""
    change = classify(_fc(_poi("a", name="Old")), _fc(_poi("a", 74.0, 41.5, name="New")))
    assert change["moved"] == 1
    assert change["edited"] == 0


def test_additions_and_a_removal_together_are_consequential():
    """The rollup must not average: a release that added four and deleted one
    is a release that deleted one."""
    change = classify(_fc(_poi("a"), _poi("b")), _fc(_poi("a"), _poi("c"), _poi("d")))
    assert change["severity"] == CONSEQUENTIAL
    assert (change["added"], change["removed"]) == (2, 1)


# --- what it cannot read ----------------------------------------------------


def test_a_first_publication_is_routine_and_says_so():
    """No previous version is not a change to warn about - there is nothing on
    a phone for it to disturb."""
    change = classify(None, _fc(_poi("a")))
    assert change["severity"] == ROUTINE
    assert change["first_publication"] is True


def test_bytes_that_are_not_json_are_consequential_with_a_reason():
    change = classify(b"\x00\x01binary", _fc(_poi("a")))
    assert change["severity"] == CONSEQUENTIAL
    assert change["unreadable"]


def test_a_document_that_is_not_a_feature_collection_is_consequential():
    """spurs.json and elevation_profile.json land here, and always will until
    somebody decides what 'changed' means for an elevation profile."""
    change = classify(json.dumps({"a": 1}).encode(), json.dumps({"a": 2}).encode())
    assert change["severity"] == CONSEQUENTIAL
    assert "FeatureCollection" in change["unreadable"]


def test_features_without_ids_are_consequential_rather_than_all_added_and_removed():
    """The failure this guards: with no identity, every feature reads as both
    added and removed, which is a confident and completely wrong answer."""
    anonymous = json.dumps({"type": "FeatureCollection", "features": [{"properties": {}, "geometry": None}]}).encode()
    change = classify(anonymous, anonymous)
    assert change["severity"] == CONSEQUENTIAL
    assert change["added"] == 0


def test_an_unreadable_previous_version_never_reads_as_nothing_changed():
    """The direction that matters. A publisher that could not fetch the old
    bytes must not tell a phone the release is routine."""
    assert data_change.unreadable("could not fetch")["severity"] == CONSEQUENTIAL


# --- the rollup -------------------------------------------------------------


def test_combine_sums_the_counts():
    total = combine([classify(_fc(_poi("a")), _fc(_poi("a"), _poi("b"))), classify(_fc(_poi("c")), _fc(_poi("c"), _poi("d")))])
    assert total["added"] == 2
    assert total["severity"] == ROUTINE


def test_one_consequential_artifact_makes_the_release_consequential():
    total = combine(
        [
            classify(_fc(_poi("a")), _fc(_poi("a"), _poi("b"))),
            classify(_fc(_poi("c"), _poi("d")), _fc(_poi("c"))),
        ]
    )
    assert total["severity"] == CONSEQUENTIAL
    assert total["removed"] == 1


def test_combining_nothing_is_routine():
    assert combine([])["severity"] == ROUTINE
