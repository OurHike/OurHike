"""Tests for lib/concurrency.py - the shared-ground pairing behind the map's
two-tone treatment of concurrent trails (#1384). Synthetic lines laid out in
metres and projected to lon/lat, the way test_export_trails.py builds its
fixtures; never real data.
"""

import pytest
from pyproj import Transformer
from shapely import wkt as shapely_wkt
from shapely.geometry import LineString
from shapely.ops import transform as shapely_transform

from lib import concurrency
from lib.corridor import GEOGRAPHIC_CRS, PROJECTED_CRS

_TO_GEOGRAPHIC = Transformer.from_crs(PROJECTED_CRS, GEOGRAPHIC_CRS, always_xy=True).transform
_TO_METRIC = Transformer.from_crs(GEOGRAPHIC_CRS, PROJECTED_CRS, always_xy=True).transform

# Somewhere in Harriman's neighbourhood in EPSG:5070 metres, so the
# projection's distortion is the one real data sees.
ORIGIN_X, ORIGIN_Y = 1_800_000.0, 2_200_000.0


def _record(record_id, coords_m, name, *, source="oprhp_trails", blaze="Red", status="open"):
    """A record whose line is `coords_m` (metres from ORIGIN), as the export
    would hold it: lon/lat WKT and the client's five properties."""
    line = LineString([(ORIGIN_X + x, ORIGIN_Y + y) for x, y in coords_m])
    return {
        "id": record_id,
        "source": source,
        "name": name,
        "blaze_color": blaze,
        "trail_status": status,
        "wkt": shapely_transform(_TO_GEOGRAPHIC, line).wkt,
    }


def _length_m(record):
    return shapely_transform(_TO_METRIC, shapely_wkt.loads(record["wkt"])).length


def _sides(pairs):
    return sorted((p["name"], p["concurrent_with"], p["concurrent_side"]) for p in pairs)


def test_a_shared_stretch_becomes_two_features_on_one_geometry_with_opposite_sides():
    # Trail A runs 1 km east; trail B joins it 8 m to the north for its
    # middle 300 m and leaves again.
    a = _record("oprhp:1", [(0, 0), (1000, 0)], "Ramapo-Dunderberg Trail", blaze="Red")
    b = _record(
        "oprhp:2",
        [(300, 200), (350, 8), (650, 8), (700, 200)],
        "Suffern-Bear Mountain Trail",
        blaze="Yellow",
    )

    pairs, stats = concurrency.find_shared_ground([a, b])

    assert stats["stretches"] == 1 and stats["features"] == 2
    assert _sides(pairs) == [
        ("Ramapo-Dunderberg Trail", "Suffern-Bear Mountain Trail", 1),
        ("Suffern-Bear Mountain Trail", "Ramapo-Dunderberg Trail", -1),
    ]
    donor, partner = pairs
    # Same chord, so the client's offset by sign lands them on opposite
    # sides without either knowing which way the other was digitised.
    assert donor["wkt"] == partner["wkt"]
    # Each half is painted in its own blaze.
    assert (donor["blaze_color"], partner["blaze_color"]) == ("Red", "Yellow")
    # The stretch is the 300 m they share, plus the buffer's overshoot at
    # each end (up to one tolerance), and no more.
    length = _length_m(donor)
    assert 300 <= length <= 300 + 2 * concurrency.SHARED_GROUND_TOLERANCE_M + 1
    assert stats["shared_m"] == round(length, 1)


def test_a_crossing_is_not_a_shared_stretch():
    # Square-on, the piece within 10 m of the other line is ~20 m long -
    # the crossing signature the minimum length exists to drop.
    a = _record("oprhp:1", [(0, 0), (1000, 0)], "Ramapo-Dunderberg Trail")
    b = _record("oprhp:2", [(500, -300), (500, 300)], "Long Path")

    pairs, stats = concurrency.find_shared_ground([a, b])

    assert pairs == []
    assert stats["stretches"] == 0 and stats["dropped_short"] >= 1


def test_the_same_trail_from_two_organizations_is_never_a_pair():
    nynjtc = _record("nynjtc_long_path:3", [(0, 0), (1000, 0)], "Long Path", source="nynjtc_long_path", blaze="Aqua")
    oprhp = _record("oprhp:4", [(0, 3), (1000, 3)], " long  path ", source="oprhp_trails", blaze="Aqua")

    pairs, stats = concurrency.find_shared_ground([nynjtc, oprhp])

    assert pairs == []
    assert stats["trails"] == 1


def test_a_nameless_record_is_skipped_and_counted():
    named = _record("oprhp:1", [(0, 0), (1000, 0)], "Ramapo-Dunderberg Trail")
    nameless = _record("oprhp:2", [(0, 5), (1000, 5)], None)
    blank = _record("oprhp:3", [(0, -5), (1000, -5)], "   ")

    pairs, stats = concurrency.find_shared_ground([named, nameless, blank])

    assert pairs == []
    assert stats["nameless_skipped"] == 2


def test_the_at_centerline_is_the_donor_whatever_order_the_records_arrive_in():
    at = _record(
        "centerline:9",
        [(0, 0), (1000, 0)],
        "Appalachian National Scenic Trail",
        source="centerline",
        blaze="White",
    )
    # A name that sorts before "Appalachian" - and still not the donor.
    park = _record("oprhp:1", [(0, 6), (1000, 6)], "Anthony Wayne Trail", blaze="Blue")

    for order in ([at, park], [park, at]):
        pairs, _ = concurrency.find_shared_ground(order)
        donor = next(p for p in pairs if p["concurrent_side"] == 1)
        assert donor["source"] == "centerline"
        assert donor["concurrent_with"] == "Anthony Wayne Trail"
        assert next(p for p in pairs if p["concurrent_side"] == -1)["concurrent_with"] == at["name"]


def test_a_partner_published_in_short_segments_still_shares_its_ground_in_one_piece():
    # OPRHP-style 40 m segments, each under the 50 m minimum on its own.
    a = _record("nynjtc:1", [(0, 0), (1000, 0)], "Long Path", source="nynjtc_long_path", blaze="Aqua")
    segments = [
        _record(f"oprhp:{n}", [(200 + 40 * n, 5), (240 + 40 * n, 5)], "Arden-Surebridge Trail", blaze="Red") for n in range(10)
    ]

    pairs, stats = concurrency.find_shared_ground([a, *segments])

    assert stats["stretches"] == 1
    # The segments are the donor here (their name sorts first), so the
    # stretch is exactly their 400 m: nothing to overshoot into.
    assert abs(_length_m(pairs[0]) - 400) < 1


def test_two_features_of_one_trail_do_not_pair_with_each_other():
    first = _record("oprhp:1", [(0, 0), (500, 0)], "Ramapo-Dunderberg Trail")
    second = _record("oprhp:2", [(500, 0), (1000, 0)], "Ramapo-Dunderberg Trail")
    overlap = _record("oprhp:3", [(400, 4), (600, 4)], "Ramapo-Dunderberg Trail")

    pairs, _ = concurrency.find_shared_ground([first, second, overlap])

    assert pairs == []


def test_each_half_carries_its_own_status_and_nothing_it_does_not_know():
    at = _record("centerline:1", [(0, 0), (1000, 0)], "A.T.", source="centerline", blaze="White")
    del at["trail_status"]  # export_trails.py records carry none
    closed = _record("oprhp:2", [(0, 4), (1000, 4)], "Closed Loop", status="closed")
    closed["closure_kind"] = "long_term"
    closed["closure_reason"] = "bridge out"

    pairs, _ = concurrency.find_shared_ground([at, closed])

    donor, partner = pairs
    assert "trail_status" not in donor  # absent means unknown, never invented
    assert partner["trail_status"] == "closed"
    # Closure prose stays with the record it was written about.
    assert "closure_reason" not in partner and "closure_kind" not in partner


def test_two_halves_in_the_same_paint_are_one_line_spelled_twice():
    # The Whites: USFS's "Garfield Ridge Trail" in White on the A.T.'s own
    # White ground - measured, the shape of most of what the first real run
    # found. Nothing to paint two-tone, so nothing is published.
    at = _record("centerline:1", [(0, 0), (1000, 0)], "Appalachian National Scenic Trail", source="centerline", blaze="White")
    copy = _record("usfs:2", [(0, 3), (1000, 3)], "Garfield Ridge Trail", source="usfs_trails", blaze="White")

    pairs, stats = concurrency.find_shared_ground([at, copy])

    assert pairs == []
    assert stats["dropped_same_blaze"] == 1 and stats["stretches"] == 0


@pytest.mark.parametrize("blaze", ["Unknown", "None", "Other", None])
def test_a_half_with_no_paint_to_show_is_not_published(blaze):
    at = _record("centerline:1", [(0, 0), (1000, 0)], "Appalachian National Scenic Trail", source="centerline", blaze="White")
    unpainted = _record("granit:2", [(0, 3), (1000, 3)], "MOOSE MTN", source="granit_trails", blaze=blaze)

    pairs, stats = concurrency.find_shared_ground([at, unpainted])

    assert pairs == []
    assert stats["dropped_unpainted"] == 1


def test_ids_are_unique_and_name_both_records():
    a = _record("oprhp:1", [(0, 0), (1000, 0)], "Ramapo-Dunderberg Trail")
    b = _record("oprhp:2", [(0, 5), (1000, 5)], "Suffern-Bear Mountain Trail", blaze="Yellow")

    pairs, _ = concurrency.find_shared_ground([a, b])

    ids = [p["id"] for p in pairs]
    assert len(set(ids)) == 2
    assert all("oprhp:1" in i and "oprhp:2" in i for i in ids)


def test_output_is_deterministic_across_input_order():
    a = _record("oprhp:1", [(0, 0), (1000, 0)], "Ramapo-Dunderberg Trail")
    b = _record("oprhp:2", [(0, 5), (600, 5)], "Suffern-Bear Mountain Trail", blaze="Yellow")
    c = _record("oprhp:3", [(400, -30), (1000, -30)], "Long Path")  # near neither

    forward, _ = concurrency.find_shared_ground([a, b, c])
    backward, _ = concurrency.find_shared_ground([c, b, a])

    assert forward == backward
    assert len(forward) == 2  # R-D with S-BM only


def test_the_two_measured_numbers_are_the_ones_the_docstring_argues_for():
    assert concurrency.SHARED_GROUND_TOLERANCE_M == 10.0
    assert concurrency.SHARED_GROUND_MIN_LENGTH_M == 50.0
