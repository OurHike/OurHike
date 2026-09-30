"""`pipeline/reference/trail_marks.json` had no test at all, and that is why its
counts went stale.

WHAT THIS GUARDS AND WHY IT DID NOT EXIST. The manifest carries a row per trail
mark - the URL it was fetched from, its pixel size, its aspect, its measured ink
at 18px - plus a `_not_found` block grouping the through-routes with no mark by
the reason each has none. Until 2026-09-30 nothing read the file: `test_org_marks.py`
and `test_trail_name_aliases.py` both read `sources.json` and `trail_emblems.json`
instead. So `_row_count`, `_clears_the_at`, the `_comment`'s own arithmetic and
the identity below were prose, maintained by hand, in a file set whose recorded
history is stale counts - a review on 2026-09-30 found the headline still arguing
that no image bytes ship while 34 of them sat in the tree.

THE IDENTITY IS THE POINT OF IT. Every trail in `trail_emblems.json` either has a
mark here or is in `_not_found` saying why - exactly one of the two, never both,
never neither. That is what makes "31 not found" mean something rather than being
a number somebody typed, and it is the invariant a session adding a mark is most
likely to half-do: move the row into `marks` and leave the slug in its old
`_not_found` group.
"""

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
MARKS = json.loads((REPO / "pipeline" / "reference" / "trail_marks.json").read_text())
EMBLEMS = json.loads((REPO / "pipeline" / "reference" / "trail_emblems.json").read_text())

ROWS = MARKS["marks"]
NOT_FOUND = MARKS["_not_found"]


def _not_found_slugs() -> list[str]:
    """Every slug in a `_not_found` group, as a list so duplicates survive."""
    return [slug for key, group in NOT_FOUND.items() if isinstance(group, dict) and "trails" in group for slug in group["trails"]]


def test_the_row_count_is_the_number_of_rows():
    assert MARKS["_row_count"] == len(ROWS)


def test_clears_the_at_counts_the_rows_that_say_so():
    assert MARKS["_clears_the_at"] == sum(1 for row in ROWS if row.get("clears_the_at"))


def test_every_catalogued_long_trail_either_has_a_mark_or_says_why_not():
    """The identity this file rests on. A trail in neither list has silently
    stopped being accounted for; a trail in both is a row somebody moved and
    did not finish moving."""
    catalogued = {trail["slug"] for trail in EMBLEMS["trails"]}
    marked = {row["trail"] for row in ROWS}
    unmarked = set(_not_found_slugs())

    assert marked & unmarked == set(), f"in `marks` and in `_not_found` at once: {sorted(marked & unmarked)}"
    assert marked | unmarked == catalogued, (
        f"catalogued with no row either way: {sorted(catalogued - (marked | unmarked))}; "
        f"recorded here but not a catalogued trail: {sorted((marked | unmarked) - catalogued)}"
    )


def test_no_trail_is_listed_twice_in_the_not_found_groups():
    """The groups are reasons, and a trail has one. Two would mean a sweep
    re-filed it without taking it out of its old group."""
    slugs = _not_found_slugs()
    duplicated = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    assert duplicated == [], f"listed under more than one reason: {duplicated}"


def test_no_two_rows_describe_the_same_trail():
    slugs = [row["trail"] for row in ROWS]
    duplicated = sorted({slug for slug in slugs if slugs.count(slug) > 1})
    assert duplicated == [], f"more than one mark row: {duplicated}"


@pytest.mark.parametrize("row", ROWS, ids=[row["trail"] for row in ROWS])
def test_a_row_carries_what_a_later_session_would_need_to_refetch_it(row: dict):
    for field in ("trail", "name", "steward", "found_at", "fetched", "pixels"):
        assert str(row.get(field, "")).strip(), f"{row['trail']}: no {field}"
    assert row["found_at"].startswith("http"), f"{row['trail']}: found_at has to be the URL it was fetched from"


@pytest.mark.parametrize("row", ROWS, ids=[row["trail"] for row in ROWS])
def test_the_recorded_aspect_is_the_recorded_pixels(row: dict):
    """`aspect` is what the badge's fit arithmetic reads, so it must follow
    `pixels` rather than being typed beside it. Two decimal places, because
    that is the precision the rows are written to."""
    width, height = (float(n) for n in row["pixels"].lower().split("x"))
    assert row["aspect"] == pytest.approx(width / height, abs=0.005), (
        f"{row['trail']}: aspect {row['aspect']} against {row['pixels']}"
    )


@pytest.mark.parametrize("row", ROWS, ids=[row["trail"] for row in ROWS])
def test_ink_is_a_share_and_contrast_is_a_ratio(row: dict):
    """Both are measurements against a stated method (`_ink_at_18px`), so the
    check is that they are in range rather than that they are any value: ink is
    a share of 324 pixels and contrast is a WCAG ratio, which cannot exceed 21."""
    assert 0.0 <= row["ink_at_18px"] <= 1.0, f"{row['trail']}: ink is a share"
    assert 1.0 <= row["peak_contrast"] <= 21.0, f"{row['trail']}: contrast is a WCAG ratio"


def test_clears_the_at_agrees_with_the_bar_the_file_states():
    """`_ink_at_18px` names the A.T.'s own mark as the bar. A row claiming to
    clear a bar it does not clear is the kind of thing this file records
    honestly everywhere else."""
    bar = next(row["ink_at_18px"] for row in ROWS if row["trail"] == "at")
    wrong = sorted(row["trail"] for row in ROWS if row.get("clears_the_at") != (row["ink_at_18px"] >= bar))
    assert wrong == [], f"rows whose clears_the_at disagrees with the {bar} bar: {wrong}"
