"""Unit tests for lib/blaze.py - pure blaze-color normalization, no I/O, no
setup needed (see TESTING.md's "pure functions get zero-setup tests").

Guards the real data gotchas named in features/TRAIL_BLAZE_COLORS.md:
side_trails' real `Blaze` field has 24 features with no value at all, 9 with
the literal string "Unknown", and 3 with "Gold" - none of which are actual
codes in its 0-9 coded domain - plus the trickier case that codes 0 ("None")
and 9 ("Other") are themselves real, successful decodes, not fallbacks.
"""

import json
from pathlib import Path

import pytest

from lib.blaze import (
    NEUTRAL_MEMBERS,
    PALETTE,
    UnknownPaint,
    map_source_blaze,
    normalize_blaze_color,
)

# Mirrors side_trails' real ArcGIS coded domain on the `Blaze` field.
SIDE_TRAILS_BLAZE_DOMAIN = {
    0: "None",
    1: "Blue",
    2: "White",
    3: "Red",
    4: "Orange",
    5: "Yellow",
    6: "Green",
    7: "Purple",
    8: "Black",
    9: "Other",
}


def test_normalize_blaze_color_decodes_a_real_coded_value():
    assert normalize_blaze_color(1, SIDE_TRAILS_BLAZE_DOMAIN) == ("Blue", True)


def test_normalize_blaze_color_decodes_code_zero_to_none_not_a_fallback():
    color, decoded = normalize_blaze_color(0, SIDE_TRAILS_BLAZE_DOMAIN)
    assert color == "None"
    assert decoded is True  # code 0 is a confirmed "unblazed" decode, not the Unknown fallback


def test_normalize_blaze_color_decodes_code_nine_to_other_cleanly():
    color, decoded = normalize_blaze_color(9, SIDE_TRAILS_BLAZE_DOMAIN)
    assert color == "Other"
    assert decoded is True


def test_normalize_blaze_color_falls_back_on_literal_unknown_string():
    assert normalize_blaze_color("Unknown", SIDE_TRAILS_BLAZE_DOMAIN) == ("Unknown", False)


def test_normalize_blaze_color_falls_back_on_literal_gold_string():
    assert normalize_blaze_color("Gold", SIDE_TRAILS_BLAZE_DOMAIN) == ("Unknown", False)


def test_normalize_blaze_color_falls_back_on_out_of_range_code():
    """A code outside the real 0-9 domain (e.g. bad/stale data) must not decode."""
    assert normalize_blaze_color(99, SIDE_TRAILS_BLAZE_DOMAIN) == ("Unknown", False)


def test_normalize_blaze_color_uses_flat_source_default_when_value_is_missing():
    # centerline has no Blaze field at all - sources.json carries a flat
    # per-source default ("White") instead, passed here as source_default.
    assert normalize_blaze_color(None, None, source_default="White") == ("White", True)


def test_normalize_blaze_color_falls_back_on_missing_value_with_no_default():
    assert normalize_blaze_color(None, None, source_default=None) == ("Unknown", False)


# --- The reviewed mapping tables (#782) ------------------------------------


class TestMapSourceBlaze:
    """`map_source_blaze`, the judgement half.

    `normalize_blaze_color` above decodes an ArcGIS coded domain, which is
    mechanical. This is the half that applies decisions a person made in
    `reference/blaze_mapping.json` - and its three dispositions are the point,
    because two of them render identically and mean opposite things.
    """

    TABLE = {
        "mapped": {"Aqua": "Aqua", "Teal": "Aqua", "Blue": "Blue"},
        "deferred": {"Pink": {"count": 171, "why": "no member yet"}},
    }

    def test_a_reviewed_row_names_its_palette_member(self):
        assert map_source_blaze("Aqua", self.TABLE) == ("Aqua", "mapped")

    def test_two_spellings_of_one_paint_land_on_one_member(self):
        """OPRHP writes both Aqua and Teal on Long Path segments (107 and 28
        rows, #771). They are one paint on the ground, and a hiker at a
        junction should see one colour."""
        assert map_source_blaze("Teal", self.TABLE) == ("Aqua", "mapped")

    def test_a_deferred_value_is_a_decision_and_says_so(self):
        """Renders the same neutral as an unmapped one, and is not the same
        event. Somebody looked at Pink, wrote down why it is not painted yet,
        and what would settle it - collapsing that into "unmapped" is how an
        oversight hides inside a docket."""
        assert map_source_blaze("Pink", self.TABLE) == ("Unknown", "deferred")

    def test_a_value_nobody_has_looked_at_is_the_loud_one(self):
        assert map_source_blaze("Chartreuse", self.TABLE) == ("Unknown", "unmapped")

    def test_a_source_with_no_reviewed_table_maps_nothing(self):
        """Not an error. A source's first release should say out loud that
        none of its values have been reviewed."""
        assert map_source_blaze("Aqua", None) == ("Unknown", "unmapped")

    def test_a_row_may_name_a_neutral_on_purpose(self):
        """ "This source's blank string means confirmed-unblazed" is a real
        reviewed decision, distinct from a failure to decode."""
        table = {"mapped": {"": "None"}}
        assert map_source_blaze("", table) == ("None", "mapped")

    def test_a_row_naming_a_paint_the_client_cannot_draw_is_refused(self):
        """Raised rather than warned, and deliberately.

        A warning would let a release ship every trail wearing that paint as
        neutral grey - indistinguishable from "this source had no blaze data",
        which is the silent-wrong the loud warning exists to prevent, arriving
        by the one path the warning cannot see. This is a file a person
        edited; the failure belongs at the edit.
        """
        with pytest.raises(UnknownPaint, match="Chartreuse"):
            map_source_blaze("x", {"mapped": {"x": "Chartreuse"}})


def test_the_shipped_mapping_table_only_names_paints_the_client_has():
    """The reviewed file itself, run through the guard.

    The unit tests above prove the check works; this proves the real docket
    passes it. Without this, `reference/blaze_mapping.json` could name a
    member nobody admitted and nothing would notice until a release.
    """
    tables = json.loads((Path(__file__).resolve().parents[1] / "reference" / "blaze_mapping.json").read_text())
    for source_key, table in tables["sources"].items():
        for raw_value in table.get("mapped", {}):
            member, disposition = map_source_blaze(raw_value, table)
            assert disposition == "mapped", f"{source_key}: {raw_value}"
            assert member in PALETTE or member in NEUTRAL_MEMBERS


def test_every_deferred_value_says_why_and_what_would_settle_it():
    """A docket entry with no reason is an oversight wearing a decision's
    clothes - which is the exact thing this file was added to prevent, so it
    is worth a test rather than a convention."""
    tables = json.loads((Path(__file__).resolve().parents[1] / "reference" / "blaze_mapping.json").read_text())
    for source_key, table in tables["sources"].items():
        for raw_value, entry in (table.get("deferred") or {}).items():
            assert entry.get("why"), f"{source_key}: {raw_value} is deferred with no reason"
            assert entry.get("settles_it"), f"{source_key}: {raw_value} is deferred with no way out"


def test_a_deferred_value_is_never_also_mapped():
    """The two dictionaries are answers to one question, and a value in both
    would make the answer depend on lookup order."""
    tables = json.loads((Path(__file__).resolve().parents[1] / "reference" / "blaze_mapping.json").read_text())
    for source_key, table in tables["sources"].items():
        overlap = set(table.get("mapped") or {}) & set(table.get("deferred") or {})
        assert overlap == set(), f"{source_key}: {sorted(overlap)} is both mapped and deferred"
