"""Tests for the parse and the arithmetic in spike_guide_water_check.py.

A spike's findings are worth exactly what its parse and its arithmetic are
worth, and this one's produced a number that is now quoted on #97 and in
WATER_SOURCES.md as evidence that OurHike's stream crossings are real water.
Three of the four things tested here are things that parse got WRONG on the
way to that number, each one silently: it dropped every seasonal source, then
two thirds of the whole table, then most of the shelters. None of those
failures raised anything. Each showed up only as a count that did not match
the book's own advertised total.

**Every row in this file is invented.** The A.T. Guide is copyright
AntiGravityGear, LLC and nothing from it is committed - which happens to
agree with TESTING.md's rule that a fixture is synthetic and readable rather
than a slice of the real input, so there is no tension to resolve. The rows
below reproduce the *layout* the text layer produces, with fake places at
fake miles.
"""

import math

import pytest

from spike_guide_water_check import (
    MATCH_MI,
    WATER_CODES,
    describes,
    nearest_gap,
    offset_at,
    parse_page,
    results_payload,
    share,
    trail_mile,
)

#: Two rows run together, the way pypdf hands them over: the first row's
#: elevation and the second row's mile arrive as one token, with no line break
#: anywhere. A line-anchored pattern reads row one and never sees row two.
RUN_TOGETHER = (
    "2000.0 197.4 Fictional Gap, view north . . . . . . . 34 .5000,-84 .1000 vw 31001999.1 198.3 "
    "Nowhere Brook . . . . . . . w 2870"
)

#: A shelter row, which is the row most likely to carry water and the one the
#: code pattern used to stop dead on: `t(4)` and `s(7)` are capacities, and a
#: pattern of bare letters ends at the first bracket with `pw` - or, before
#: that, matched nothing at all and dropped the row.
SHELTER_ROW = "1900.5 296.9 Invented Lean-to, spring 100 yds behind . . . . . . . pwt(4)s(7)/ 3560"

#: The three water codes the book's legend gives, and the case distinction
#: that cost this parse every seasonal source on its first run.
CODE_ROWS = (
    "1800.0 397.4 Made-up Creek . . . . . . . w 2100",
    "1700.0 497.4 Imaginary Seep . . . . . . . W 2400",
    "1600.0 597.4 Pretend Picnic Area . . . . . . . J 1800",
    "1500.0 697.4 Fabricated Overlook . . . . . . . v 3900",
)


def water_kinds(row) -> list[str]:
    """What read_guide() derives from a parsed row's codes."""
    return sorted(WATER_CODES[code] for code in set(row["codes"]) if code in WATER_CODES)


def test_both_rows_are_found_when_the_text_layer_runs_them_together():
    rows = parse_page(RUN_TOGETHER)

    assert [row["nobo_mile"] for row in rows] == [197.4, 198.3]
    assert water_kinds(rows[1]) == ["reliable"]


def test_a_coordinate_row_keeps_its_position_and_still_reads_its_codes():
    """Coordinates sit exactly where the codes would otherwise start, so they
    are stripped first - and the decimals arrive with spaces in them."""
    row = parse_page(RUN_TOGETHER)[0]

    assert row["lat"] == pytest.approx(34.5)
    assert row["lon"] == pytest.approx(-84.1)
    assert row["codes"] == "vw"


def test_a_shelter_rows_codes_survive_its_bracketed_capacities():
    row = parse_page(SHELTER_ROW)[0]

    assert water_kinds(row) == ["reliable"]
    # The digits inside t(4) and s(7) are capacities, not codes of their own.
    assert row["codes"] == "pwts"


@pytest.mark.parametrize(
    ("text", "expected"),
    zip(CODE_ROWS, (["reliable"], ["seasonal"], ["potable_tap"], [])),
    ids=["reliable w", "seasonal W", "potable J", "no water"],
)
def test_the_three_water_codes_stay_apart_and_case_decides_which(text, expected):
    """`w` and `W` are different promises to a hiker - a source that is there
    in August and one that might not be - and collapsing them would make this
    cross-check agree with us for the wrong reason."""
    assert water_kinds(parse_page(text)[0]) == expected


def test_a_row_whose_halves_do_not_sum_is_left_for_the_caller_to_drop():
    """parse_page does not judge; read_guide() drops on `length_check`. The
    field has to be there for that to work, which is what this pins."""
    row = parse_page("1800.0 397.4 Made-up Creek . . . . . . . w 2100")[0]

    assert row["length_check"] == 2197.4


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("Nowhere Brook", "stream"),
        ("Made-up Creek, footbridge", "stream"),
        ("Rock Run", "stream"),
        ("Two Forks of the invented river", "stream"),
        ("Piped spring 50 yds west", "spring"),
        # A spring row that also names a stream is a spring row: it is the
        # water the guide is pointing at, and a crossing cannot find it.
        ("Spring, 200 yds down blue blaze to creek", "spring"),
        ("Fabricated Overlook", "other"),
        ("Gravel road, parking", "other"),
    ],
)
def test_what_the_row_describes(description, expected):
    assert describes(description) == expected


# --- placing a coordinate on ATC's ruler ------------------------------------

#: Four mileposts half a mile apart, running due north from an invented
#: origin. Half a mile is 804.672 m, which at this latitude is what the
#: latitude steps below come to.
HALF_MILE_DEG = 804.672 / 111_132.0
POSTS = [(100.0 + 0.5 * index, 40.0 + HALF_MILE_DEG * index, -75.0) for index in range(4)]


def test_a_point_between_two_mileposts_lands_between_their_miles():
    """The reason for interpolating rather than snapping: a snapped answer
    would quantise every feature to +/-0.25 mi, which is coarser than the
    0.1 mi the guide states its own rows to."""
    mile, offset = trail_mile(40.0 + HALF_MILE_DEG * 0.5, -75.0, POSTS)

    assert mile == pytest.approx(100.25, abs=0.01)
    assert offset == pytest.approx(0.0, abs=1.0)


def test_a_point_off_to_the_side_reports_how_far_off_it_is():
    """The second return value is what stops a road-junction coordinate being
    used to calibrate the two mileages, and what keeps a spring a kilometre
    down a side trail out of the point-source count."""
    east = 500.0 / (111_132.0 * math.cos(math.radians(40.0)))
    mile, offset = trail_mile(40.0 + HALF_MILE_DEG, -75.0 + east, POSTS)

    assert mile == pytest.approx(100.5, abs=0.01)
    assert offset == pytest.approx(500.0, rel=0.01)


def test_a_point_at_a_milepost_gets_that_mile():
    mile, offset = trail_mile(POSTS[2][1], POSTS[2][2], POSTS)

    assert mile == pytest.approx(101.0, abs=0.01)
    assert offset == pytest.approx(0.0, abs=1.0)


# --- the two mileages' disagreement ----------------------------------------

CONTROLS = [(10.0, 0.2), (20.0, 0.6), (30.0, -0.1)]


@pytest.mark.parametrize(
    ("mile", "expected"),
    [(15.0, 0.4), (10.0, 0.2), (20.0, 0.6), (25.0, 0.25)],
)
def test_the_offset_is_interpolated_between_control_points(mile, expected):
    """Measured rather than assumed, and interpolated rather than averaged:
    a single shift fitted to the middle of a 2,197-mile trail misplaces both
    ends, which is what the first run of this showed."""
    assert offset_at(mile, CONTROLS) == pytest.approx(expected)


@pytest.mark.parametrize(("mile", "expected"), [(0.0, 0.2), (5.0, 0.2), (40.0, -0.1), (2200.0, -0.1)])
def test_the_offset_holds_flat_past_the_outermost_control_points(mile, expected):
    """Beyond the last coordinate-bearing row there is nothing to interpolate
    towards. Holding flat says "the last thing we measured"; extrapolating the
    final segment's slope would invent a drift nobody observed, and over the
    ~30 miles past the outermost control that error would be larger than the
    match window."""
    assert offset_at(mile, CONTROLS) == pytest.approx(expected)


def test_no_control_points_means_no_alignment_rather_than_a_crash():
    assert offset_at(1000.0, []) == 0.0


def test_nearest_gap_of_nothing_is_infinite():
    """So a slice of the guide with no OurHike water anywhere near it scores
    zero rather than matching everything."""
    assert nearest_gap(100.0, []) == math.inf
    assert nearest_gap(100.0, [99.9, 200.0]) == pytest.approx(0.1)
    assert nearest_gap(100.0, [99.9]) <= MATCH_MI


def test_share_of_nothing_is_not_a_zero_division():
    assert share(0, 0) == "n/a"
    assert share(302, 460) == "66%"


# --- the rule this whole file is arranged around ---------------------------


def leaves(value, path="results"):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from leaves(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from leaves(item, f"{path}[{index}]")
    else:
        yield path, value


def test_the_results_file_can_only_hold_numbers():
    """The load-bearing test in this file, and the reason results_payload() is
    a function rather than a dict literal inside main().

    The guide is copyright AntiGravityGear, LLC; the statistics about our data
    are ours to publish and its rows are not. `data/spike/` is gitignored, so
    nothing here is a commit - but "gitignored" is the argument that already
    failed once in this repository (.github/tests/test_no_committed_data.py
    records how), and a file of guidebook rows sitting on disk under a name
    that reads like results is one `git add -f` from being permanent.

    So the payload is checked to be arithmetic. Any future field carrying a
    name, a description or a position fails here first.
    """
    payload = results_payload(
        features={"crossing": [1.0, 2.0], "site_water": [], "point_source": [3.0]},
        guide_rows=980,
        controls=CONTROLS,
        by_reliability={"all water rows": {"rows": 980, "any_water": 538, "crossing": 397}},
        by_description={"stream": {"rows": 460, "any_water": 320, "crossing": 302}},
        corroborated=455,
    )

    offenders = [
        f"{path}={value!r}"
        for path, value in leaves(payload)
        if path != "results._README" and not isinstance(value, (int, float, type(None)))
    ]

    assert offenders == [], (
        "spike_guide_water_check.py's results file must hold counts and percentages only - "
        f"a non-numeric field here is guidebook content leaving the process: {offenders}"
    )


def test_the_payload_reports_the_offset_it_was_given():
    payload = results_payload(
        features={"crossing": [], "site_water": [], "point_source": []},
        guide_rows=0,
        controls=CONTROLS,
        by_reliability={},
        by_description={},
        corroborated=0,
    )

    assert payload["mileage_offset_mi"] == {"control_points": 3, "median": 0.2, "min": -0.1, "max": 0.6}


def test_the_payload_survives_having_measured_nothing():
    payload = results_payload(
        features={"crossing": []},
        guide_rows=0,
        controls=[],
        by_reliability={},
        by_description={},
        corroborated=0,
    )

    assert payload["mileage_offset_mi"]["median"] is None
