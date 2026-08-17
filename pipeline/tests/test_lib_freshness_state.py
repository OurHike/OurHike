"""Tests for lib/freshness_state.py - the recorded half of "is this stale?".

Why this exists
---------------
`check_freshness.py` was fully built, fully tested, and could not run anywhere
except the machine that had done the fetching. Its recorded side read
`pipeline/data/raw/*`, which is gitignored, so on a hosted runner it reported
every source STALE for the trivial reason that a fresh checkout has never
fetched anything. That is the single thing that stood between a working check
and a scheduled one.

Splitting the recorded side out lets a build capture its markers and publish
them, and lets a scheduled job read that capture back over plain HTTPS and
hold no credentials at all. These tests are mostly about the ways that split
could go quietly wrong:

- a state that half-loads, so the sources that survived compare as FRESH and
  the ones that did not simply are not mentioned;
- a state published by a build that only ran half the pipeline, claiming a
  verdict about the half it never touched;
- "we looked and found nothing" flattened together with "nobody looked".

All three end the same way - a green check over stale data - which is the one
outcome this module exists to prevent.
"""

import json

import pytest
import requests

from lib import freshness_state
from lib.freshness_state import (
    Freshness,
    StateUnavailable,
    capture_state,
    compare_state,
    drop_unrecorded,
    load_state,
    state_age_days,
)


def topo(reports):
    return next(r for r in reports if r["source"] == "topo_quads")


def write(path, payload):
    path.write_text(json.dumps(payload))
    return path


@pytest.fixture
def raw(tmp_path):
    """A checkout that has fetched everything, in the shapes the real
    fetchers write."""
    write(
        tmp_path / "manifest.json",
        {
            "centerline": {"url": "https://arcgis.test/centerline", "data_last_edit_date": 1723739016398},
            "shelters": {"url": "https://arcgis.test/shelters", "data_last_edit_date": 1723739016399},
        },
    )
    write(tmp_path / "opentrail_state.json", {"etag": 'W/"abc123"'})
    write(
        tmp_path / "topo.json",
        {
            "https://s3.test/GeoTIFF/CT/one.tif": {"last_modified": "Mon, 01 Jan 2024 00:00:00 GMT"},
            "https://s3.test/GeoTIFF/VA/two.tif": {"last_modified": "Tue, 02 Jan 2024 00:00:00 GMT"},
        },
    )
    write(
        tmp_path / "tile_index.json",
        [{"url": "https://tnm.test/USGS_13_n35w084_20230215.tif"}],
    )
    return tmp_path


@pytest.fixture
def paths(raw):
    return {
        "atc_manifest": raw / "manifest.json",
        "opentrail_state": raw / "opentrail_state.json",
        "topo_manifest": raw / "topo.json",
        "elevation_index": raw / "tile_index.json",
    }


# --- Capture ---------------------------------------------------------------


def test_capture_carries_each_source_s_marker(paths):
    state = capture_state(**paths)

    assert state["atc"]["centerline"]["marker"] == "1723739016398"
    assert state["opentrail"] == 'W/"abc123"'
    assert state["topo_quads"]["https://s3.test/GeoTIFF/CT/one.tif"] == "Mon, 01 Jan 2024 00:00:00 GMT"
    assert state["elevation"] == "n35w084:20230215"


def test_capture_carries_each_atc_layer_s_url_not_just_its_marker(paths):
    """The checking job has the state and nothing else - no manifest, no
    sources.json. Without the URL it would know a layer needs comparing and
    have nowhere to ask."""
    state = capture_state(**paths)

    assert state["atc"]["centerline"]["url"] == "https://arcgis.test/centerline"


def test_capture_keeps_an_atc_layer_whose_edit_date_was_never_recorded(tmp_path, paths):
    """fetch_all.py tolerates a failed dataLastEditDate lookup and records the
    layer anyway. Dropping such a layer here is how a rollup ends up printing
    "atc: FRESH" for a set containing a layer nobody ever checked."""
    paths["atc_manifest"] = write(
        tmp_path / "partial.json",
        {"shelters": {"url": "https://arcgis.test/shelters", "data_last_edit_date": None}},
    )

    state = capture_state(**paths)

    assert state["atc"]["shelters"]["marker"] is None


def test_capture_records_every_source_even_ones_never_fetched(tmp_path):
    """On the machine that does the fetching, "we have nothing" is a real
    answer rather than an absence of one, and the caller needs to see it."""
    state = capture_state(
        atc_manifest=tmp_path / "absent.json",
        opentrail_state=tmp_path / "absent.json",
        topo_manifest=tmp_path / "absent.json",
        elevation_index=tmp_path / "absent.json",
    )

    assert set(freshness_state.SOURCES) <= set(state)
    assert state["atc"] == {}
    assert state["elevation"] is None


def test_capture_records_all_quads_not_a_sample(paths):
    """Sampling belongs to the asking side and is redrawn every run. A state
    that froze one run's 25 quads would pin the check to whichever ones
    happened to be picked the day it was built."""
    state = capture_state(**paths)

    assert len(state["topo_quads"]) == 2


def test_elevation_marker_ignores_the_order_tnm_happened_to_return(tmp_path, paths):
    urls = ["https://tnm.test/USGS_13_n35w084_20230215.tif", "https://tnm.test/USGS_13_n36w081_20220101.tif"]
    paths["elevation_index"] = write(tmp_path / "a.json", [{"url": u} for u in urls])
    forwards = capture_state(**paths)["elevation"]

    paths["elevation_index"] = write(tmp_path / "b.json", [{"url": u} for u in reversed(urls)])
    backwards = capture_state(**paths)["elevation"]

    assert forwards == backwards


# --- Publishing a partial build --------------------------------------------


def test_a_source_with_no_record_is_dropped_before_publishing(tmp_path, paths):
    """The vector publish never fetches topo quads or DEM tiles - they are a
    different workflow. A state it published carrying empty entries for them
    would report a daily STALE for the raster half forever."""
    paths["topo_manifest"] = tmp_path / "absent.json"
    paths["elevation_index"] = tmp_path / "absent.json"

    published = drop_unrecorded(capture_state(**paths))

    assert "topo_quads" not in published
    assert "elevation" not in published
    assert "atc" in published


def test_dropping_unrecorded_sources_keeps_the_state_s_own_metadata(paths):
    published = drop_unrecorded(capture_state(**paths))

    assert published["version"] == freshness_state.STATE_VERSION
    assert published["captured_at"]


def test_an_unmentioned_source_is_unknown_not_stale():
    """The distinction the whole split turns on. "Nobody checked" must not be
    reported as "we checked and it moved" - the second sends someone to
    refetch data that may be perfectly current, and after enough false alarms
    nobody reads the real one."""
    reports = compare_state({"atc": {}}, {})

    by_source = {r["source"]: r for r in reports}
    assert by_source["topo_quads"]["freshness"] is Freshness.UNKNOWN
    assert by_source["elevation"]["freshness"] is Freshness.UNKNOWN
    assert by_source["opentrail"]["freshness"] is Freshness.UNKNOWN


def test_a_source_that_was_checked_and_holds_nothing_is_still_stale():
    """The other half of that distinction: present-and-empty means the fetcher
    ran and came back with nothing, which does need a refetch."""
    reports = compare_state({"atc": {}, "opentrail": None, "topo_quads": {}, "elevation": None}, {})

    by_source = {r["source"]: r for r in reports}
    assert by_source["atc"]["freshness"] is Freshness.STALE
    assert by_source["topo_quads"]["freshness"] is Freshness.STALE


# --- Load ------------------------------------------------------------------


def test_a_state_round_trips_through_a_file(tmp_path, paths):
    path = tmp_path / "build_state.json"
    path.write_text(json.dumps(capture_state(**paths)))

    assert load_state(path)["opentrail"] == 'W/"abc123"'


def test_a_state_loads_over_plain_https(requests_mock, paths):
    """The whole point of the split: this is the one call a scheduled check
    makes to learn what the last build recorded, and it needs no credentials
    to make it - the same public object a phone reads."""
    requests_mock.get("https://data.ourhike.org/build_state.json", json=capture_state(**paths))

    assert load_state("https://data.ourhike.org/build_state.json")["opentrail"] == 'W/"abc123"'


def test_a_missing_published_state_is_its_own_outcome_not_an_empty_one(requests_mock):
    """A 404 must not become `{}`. An empty state compares as "nothing
    recorded", which reads as a data emergency rather than as a bucket that
    has simply never published one."""
    requests_mock.get("https://data.ourhike.org/build_state.json", status_code=404)

    with pytest.raises(StateUnavailable):
        load_state("https://data.ourhike.org/build_state.json")


def test_an_unreachable_host_raises_rather_than_returning_a_partial_state(requests_mock):
    requests_mock.get("https://data.ourhike.org/build_state.json", exc=requests.ConnectionError)

    with pytest.raises(StateUnavailable):
        load_state("https://data.ourhike.org/build_state.json")


def test_a_state_url_off_the_allowlist_is_refused_before_any_fetch(requests_mock):
    """#173's SSRF half: a dispatched run with a crafted state_url, or a
    poisoned workflow variable, must not turn the runner into a GET proxy.
    No mock is registered, so a fetch attempt would fail loudly as an
    unmatched request rather than quietly passing this test."""
    with pytest.raises(StateUnavailable, match="not a place a published state lives"):
        load_state("https://internal.example.net/build_state.json")


def test_a_plain_http_state_url_is_refused_even_on_an_allowed_host():
    with pytest.raises(StateUnavailable, match="must be https"):
        load_state("http://data.ourhike.org/build_state.json")


def test_an_r2_dev_state_url_is_allowed(requests_mock, paths):
    """The UA bucket has no custom domain, so its r2.dev hostname is a
    legitimate place a state lives."""
    requests_mock.get("https://pub-abc123.r2.dev/build_state.json", json=capture_state(**paths))

    assert load_state("https://pub-abc123.r2.dev/build_state.json")["version"] == 1


def test_a_missing_local_state_file_raises(tmp_path):
    with pytest.raises(StateUnavailable):
        load_state(tmp_path / "never_written.json")


def test_a_truncated_state_raises_rather_than_loading_what_parsed(tmp_path):
    """A half-read state is the dangerous case: the sources that survived the
    parse compare as FRESH and the ones that did not are never mentioned, so
    the run is green and quieter than a run that found nothing at all."""
    path = tmp_path / "build_state.json"
    path.write_text('{"version": 1, "atc": {')

    with pytest.raises(StateUnavailable):
        load_state(path)


def test_a_state_from_a_newer_pipeline_is_refused_not_half_understood(tmp_path):
    path = tmp_path / "build_state.json"
    path.write_text(json.dumps({"version": freshness_state.STATE_VERSION + 1, "atc": {}}))

    with pytest.raises(StateUnavailable):
        load_state(path)


def test_a_json_document_that_is_not_a_state_object_is_refused(tmp_path):
    path = tmp_path / "build_state.json"
    path.write_text("[1, 2, 3]")

    with pytest.raises(StateUnavailable):
        load_state(path)


# --- Compare ---------------------------------------------------------------


def test_a_matching_marker_is_fresh():
    recorded = {"atc": {"centerline": {"url": "https://arcgis.test/c", "marker": "1"}}}

    reports = compare_state(recorded, {"atc": {"centerline": "1"}})

    assert reports[0]["freshness"] is Freshness.FRESH


def test_a_changed_marker_names_which_layer_moved():
    """ "Something changed" and "the centerline changed" are different amounts
    of help at 6am when someone is deciding whether to rebuild."""
    recorded = {
        "atc": {
            "centerline": {"url": "https://arcgis.test/c", "marker": "1"},
            "shelters": {"url": "https://arcgis.test/s", "marker": "9"},
        }
    }

    reports = compare_state(recorded, {"atc": {"centerline": "2", "shelters": "9"}})

    assert reports[0]["freshness"] is Freshness.STALE
    assert reports[0]["changed"] == ["centerline"]


def test_an_atc_layer_upstream_never_answered_for_is_unknown_not_fresh():
    recorded = {"atc": {"centerline": {"url": "https://arcgis.test/c", "marker": "1"}}}

    reports = compare_state(recorded, {"atc": {}})

    assert reports[0]["freshness"] is Freshness.UNKNOWN
    assert "1 unknown" in reports[0]["detail"]


def test_a_null_recorded_atc_marker_rolls_up_as_unknown():
    recorded = {"atc": {"shelters": {"url": "https://arcgis.test/s", "marker": None}}}

    reports = compare_state(recorded, {"atc": {}})

    assert reports[0]["freshness"] is Freshness.UNKNOWN


def test_topo_compares_only_the_quads_that_were_sampled():
    recorded = {"topo_quads": {f"https://s3.test/q{i}.tif": "Mon, 01 Jan 2024 00:00:00 GMT" for i in range(100)}}

    report = topo(compare_state(recorded, {"topo_quads": {"https://s3.test/q3.tif": "Mon, 01 Jan 2024 00:00:00 GMT"}}))

    assert report["freshness"] is Freshness.FRESH
    assert report["detail"] == "sampled 1 of 100 quads"


def test_a_sample_of_zero_is_unknown_rather_than_a_clean_bill_of_health():
    """An empty verdict list must not fall through to FRESH. Nothing was
    compared, so nothing is known - and `all([])` style reasoning is exactly
    how a check that asked no questions reports a pass."""
    recorded = {"topo_quads": {"https://s3.test/q1.tif": "Mon, 01 Jan 2024 00:00:00 GMT"}}

    report = topo(compare_state(recorded, {"topo_quads": {}}))

    assert report["freshness"] is Freshness.UNKNOWN


def test_one_moved_quad_makes_the_whole_sample_stale():
    recorded = {"topo_quads": {"https://s3.test/a.tif": "old", "https://s3.test/b.tif": "old"}}

    report = topo(compare_state(recorded, {"topo_quads": {"https://s3.test/a.tif": "old", "https://s3.test/b.tif": "new"}}))

    assert report["freshness"] is Freshness.STALE


def test_markers_compare_as_strings_so_a_json_round_trip_cannot_manufacture_a_change():
    """ArcGIS hands back an epoch-millisecond int; json.load will give back
    either an int or a str depending on how it was written."""
    recorded = {"atc": {"centerline": {"url": "https://arcgis.test/c", "marker": 1723739016398}}}

    reports = compare_state(recorded, {"atc": {"centerline": "1723739016398"}})

    assert reports[0]["freshness"] is Freshness.FRESH


def test_every_source_gets_a_verdict_even_when_none_can_be_checked():
    """Silence about a source is how stale data survives. Every source in,
    the same number of verdicts out, always."""
    reports = compare_state({}, {})

    assert [r["source"] for r in reports] == [
        "atc",
        "opentrail",
        "topo_quads",
        "elevation",
        "atc_trail_updates",
        "usgs_3dhp",
    ]
    assert set(freshness_state.SOURCES) == {r["source"] for r in reports}


# --- State age -------------------------------------------------------------


def test_state_age_is_measured_from_when_it_was_captured():
    """ "Nothing changed" against a six-month-old capture is a different
    sentence from the one a reader assumes it is."""
    from datetime import date

    state = {"captured_at": "2026-01-01T00:00:00+00:00"}

    assert state_age_days(state, today=date(2026, 1, 31)) == 30


def test_state_age_is_none_when_the_state_does_not_say():
    assert state_age_days({}) is None
    assert state_age_days({"captured_at": "not a date"}) is None


# --- The 3DHP watch (#714) -------------------------------------------------
#
# The sixth source, and the second that no fetcher can clear. Its recorded
# side is a line in sources.json rather than a file on disk, because nothing
# in this pipeline fetches 3DHP at all - there is no artifact whose age could
# stand in for "somebody asked and was told NHD".


def _registry(tmp_path, recorded="NHD", key="usgs_3dhp"):
    path = tmp_path / "sources.json"
    path.write_text(json.dumps({"sources": [{"key": key, "freshness": {"recorded": recorded} if recorded else {}}]}))
    return path


def test_the_hydrography_marker_is_what_the_registry_records(tmp_path):
    assert freshness_state.hydrography_watch_marker(_registry(tmp_path)) == "NHD"


def test_a_registry_with_no_3dhp_entry_is_unknown_not_fresh(tmp_path):
    """A registry somebody edited the entry out of has not told us 3DHP is
    unchanged - it has told us nothing, and None is how this module says so."""
    assert freshness_state.hydrography_watch_marker(_registry(tmp_path, key="something_else")) is None


def test_an_entry_with_no_recorded_value_is_unknown_not_fresh(tmp_path):
    assert freshness_state.hydrography_watch_marker(_registry(tmp_path, recorded=None)) is None


def test_a_missing_or_unparseable_registry_is_unknown_rather_than_a_crash(tmp_path):
    """This marker is read during --capture, inside a build. A malformed
    registry must cost the build one UNKNOWN row, not the whole capture."""
    assert freshness_state.hydrography_watch_marker(tmp_path / "absent.json") is None
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    assert freshness_state.hydrography_watch_marker(broken) is None


def test_capture_leaves_the_hydrography_watch_out_when_no_registry_is_offered(tmp_path):
    """Same shape as `atc_updates_file`: a caller with no opinion gets the
    key present and None, which `drop_unrecorded` removes from a published
    state and `compare_state` reads as unchecked - never as current."""
    state = capture_state(
        atc_manifest=tmp_path / "absent.json",
        opentrail_state=tmp_path / "absent.json",
        topo_manifest=tmp_path / "absent.json",
        elevation_index=tmp_path / "absent.json",
    )

    assert state["usgs_3dhp"] is None
    assert "usgs_3dhp" not in freshness_state.drop_unrecorded(state)


def test_a_resurveyed_corridor_reads_as_stale_rather_than_as_a_refetch(tmp_path):
    """The verdict that is the whole point. STALE here does not mean the
    pipeline is behind; it means USGS has stopped republishing NHD for the
    corridor, which is the moment migrating off a frozen 2023 snapshot is
    worth costing (WATER_SOURCES.md §5)."""
    reports = compare_state({"usgs_3dhp": "NHD"}, {"usgs_3dhp": "3DHP_MA_01"})

    report = next(r for r in reports if r["source"] == "usgs_3dhp")
    assert report["freshness"] is Freshness.STALE
    assert "not that anything needs refetching" in report["detail"]


def test_an_unreachable_3dhp_is_unknown_not_fresh():
    """The asymmetry this whole module is built on, applied to the one source
    whose FRESH nobody would otherwise question - it has said the same word
    since 2023, so a silent failure to ask looks exactly like an answer."""
    reports = compare_state({"usgs_3dhp": "NHD"}, {"usgs_3dhp": None})

    assert next(r for r in reports if r["source"] == "usgs_3dhp")["freshness"] is Freshness.UNKNOWN
