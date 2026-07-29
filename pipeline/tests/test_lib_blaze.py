"""Unit tests for lib/blaze.py - pure blaze-color normalization, no I/O, no
setup needed (see TESTING.md's "pure functions get zero-setup tests").

Guards the real data gotchas named in features/TRAIL_BLAZE_COLORS.md:
side_trails' real `Blaze` field has 24 features with no value at all, 9 with
the literal string "Unknown", and 3 with "Gold" - none of which are actual
codes in its 0-9 coded domain - plus the trickier case that codes 0 ("None")
and 9 ("Other") are themselves real, successful decodes, not fallbacks.
"""

from lib.blaze import normalize_blaze_color

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
