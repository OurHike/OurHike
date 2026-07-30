"""Tests for check_freshness.py - "does any upstream data need refetching?"

Why this exists
---------------
Every fetcher in this pipeline already knows how to skip unchanged data, but
each only finds out *while fetching*. There was no way to ask the question
without starting the work - and the work is now genuinely expensive: a full
elevation export streams from 110 remote DEM tiles for ~25 minutes, and a
background rebuild re-tiles the whole corridor.

These sources also move slowly. ATC layers change a few times a year; USGS
topo quads and 3DEP elevation are re-flown on multi-year cycles. So the
common answer is "nothing changed", and finding that out should cost four
cheap metadata requests, not a re-download.

Each source keeps a different freshness marker, because each upstream exposes
a different one - an ArcGIS edit timestamp, an S3 Last-Modified, an HTTP
ETag, a date embedded in a filename. This module's job is to normalise those
into one answer per source, and to be honest when it cannot tell.

The failure that matters most is a FALSE "fresh". Reporting stale data as
current means the map silently keeps showing a closed trail or a moved
shelter, so anything unknown reports as unknown rather than being rounded
down to fine.
"""

import json

import pytest

import check_freshness
from check_freshness import Freshness, compare_marker, summarise


def test_a_matching_marker_is_fresh():
    assert compare_marker(recorded="abc", upstream="abc") is Freshness.FRESH


def test_a_changed_marker_is_stale():
    assert compare_marker(recorded="abc", upstream="def") is Freshness.STALE


def test_never_fetched_is_stale_not_unknown():
    """Nothing recorded locally means there is nothing to compare - but the
    action needed is clear, so this is stale rather than unknown."""
    assert compare_marker(recorded=None, upstream="abc") is Freshness.STALE


def test_an_unreachable_upstream_is_unknown_not_fresh():
    """The failure that matters. A network error must never be reported as
    'nothing changed' - that would let stale data sit unnoticed indefinitely,
    which for closures and reroutes is a safety problem, not an
    inconvenience."""
    assert compare_marker(recorded="abc", upstream=None) is Freshness.UNKNOWN


def test_both_missing_is_unknown():
    assert compare_marker(recorded=None, upstream=None) is Freshness.UNKNOWN


def test_markers_compare_as_strings_so_types_cannot_drift():
    """ArcGIS returns an epoch-millisecond int, S3 an HTTP date string. Both
    get normalised, so a JSON round trip (which turns 1723739016398 into an
    int and back) cannot produce a spurious 'stale'."""
    assert compare_marker(recorded="1723739016398", upstream=1723739016398) is Freshness.FRESH


# --- The overall summary ---------------------------------------------------


def _report(**states):
    return [{"source": k, "freshness": v} for k, v in states.items()]


def test_summary_is_clean_when_everything_matches():
    summary = summarise(_report(atc=Freshness.FRESH, topo=Freshness.FRESH))

    assert summary["needs_refetch"] == []
    assert summary["exit_code"] == 0


def test_summary_names_exactly_what_changed():
    summary = summarise(_report(atc=Freshness.STALE, topo=Freshness.FRESH))

    assert summary["needs_refetch"] == ["atc"]


def test_a_stale_source_exits_non_zero_so_ci_can_gate_on_it():
    assert summarise(_report(atc=Freshness.STALE))["exit_code"] != 0


def test_an_unknown_source_is_reported_separately_from_a_stale_one():
    """Not knowing and knowing-it-changed call for different responses -
    retry versus refetch - so they are not merged."""
    summary = summarise(_report(atc=Freshness.UNKNOWN, topo=Freshness.STALE))

    assert summary["unknown"] == ["atc"]
    assert summary["needs_refetch"] == ["topo"]


def test_an_unknown_source_also_exits_non_zero():
    """Silence about a source nobody could check is how stale data survives."""
    assert summarise(_report(atc=Freshness.UNKNOWN))["exit_code"] != 0


# --- Per-source markers ----------------------------------------------------


def test_atc_marker_comes_from_the_recorded_edit_date(tmp_path, monkeypatch):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"centerline": {"data_last_edit_date": 1723739016398}}))
    monkeypatch.setattr(check_freshness, "ATC_MANIFEST", manifest)

    assert check_freshness.recorded_atc_markers()["centerline"] == "1723739016398"


def test_atc_markers_are_empty_when_nothing_has_been_fetched(tmp_path, monkeypatch):
    monkeypatch.setattr(check_freshness, "ATC_MANIFEST", tmp_path / "absent.json")

    assert check_freshness.recorded_atc_markers() == {}


def test_elevation_marker_is_the_set_of_tile_editions(tmp_path, monkeypatch):
    """3DEP has no per-file timestamp worth trusting, but the catalog embeds
    an edition date in every filename - so the marker is which editions the
    index pinned. A newly published edition changes it."""
    index = tmp_path / "tile_index.json"
    index.write_text(
        json.dumps(
            [
                {"url": "https://x/USGS_13_n35w084_20230215.tif", "bounds": [0, 0, 1, 1]},
                {"url": "https://x/USGS_13_n36w084_20220504.tif", "bounds": [0, 0, 1, 1]},
            ]
        )
    )
    monkeypatch.setattr(check_freshness, "ELEVATION_INDEX", index)

    marker = check_freshness.recorded_elevation_marker()

    assert "20230215" in marker and "20220504" in marker


def test_elevation_marker_is_order_independent(tmp_path, monkeypatch):
    """TNM returns tiles in no guaranteed order; a reshuffle is not a change."""
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    entries = [
        {"url": "https://x/USGS_13_n35w084_20230215.tif", "bounds": [0, 0, 1, 1]},
        {"url": "https://x/USGS_13_n36w084_20220504.tif", "bounds": [0, 0, 1, 1]},
    ]
    a.write_text(json.dumps(entries))
    b.write_text(json.dumps(list(reversed(entries))))

    monkeypatch.setattr(check_freshness, "ELEVATION_INDEX", a)
    first = check_freshness.recorded_elevation_marker()
    monkeypatch.setattr(check_freshness, "ELEVATION_INDEX", b)

    assert check_freshness.recorded_elevation_marker() == first


def test_elevation_marker_is_none_when_no_index_exists(tmp_path, monkeypatch):
    monkeypatch.setattr(check_freshness, "ELEVATION_INDEX", tmp_path / "absent.json")

    assert check_freshness.recorded_elevation_marker() is None


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://x/USGS_13_n35w084_20230215.tif", "n35w084:20230215"),
        ("https://x/odd_name.tif", "odd_name.tif:"),
    ],
)
def test_elevation_edition_key_survives_an_unconventional_filename(url, expected):
    """An unparseable name must not crash the check or silently drop a tile
    from the marker - a dropped tile would read as 'unchanged'."""
    assert check_freshness.edition_key(url) == expected
