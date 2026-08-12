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
from lib import freshness_state


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


def test_recorded_atc_markers_keeps_a_null_edit_date_as_none_not_dropped(tmp_path, monkeypatch):
    """fetch_all.py tolerates a failed edit-date lookup and still fetches
    and records the layer, with a null date, rather than failing the whole
    run (see fetch_all.py). This used to filter such entries out via an
    `is not None` guard, which silently dropped them instead of surfacing
    them - a null-dated layer never reached check_all()'s comparison loop
    at all, so the rollup could report "atc: FRESH" while that layer was
    never actually checked."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "centerline": {"data_last_edit_date": 1723739016398},
                "shelters": {"data_last_edit_date": None},
            }
        )
    )
    monkeypatch.setattr(check_freshness, "ATC_MANIFEST", manifest)

    assert check_freshness.recorded_atc_markers() == {
        "centerline": "1723739016398",
        "shelters": None,
    }


def test_a_null_recorded_atc_marker_rolls_up_as_unknown_not_a_false_fresh(tmp_path, monkeypatch, requests_mock):
    """The failure that actually matters here, not just the dict in
    isolation: prove check_all()'s rollup no longer reports "atc: FRESH"
    when one layer's edit date was never recorded. Every other source is
    pointed at a nonexistent path (or stubbed) so this test exercises only
    the ATC path."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "centerline": {
                    "url": "https://example.com/centerline",
                    "data_last_edit_date": 1723739016398,
                },
                "shelters": {
                    "url": "https://example.com/shelters",
                    "data_last_edit_date": None,
                },
            }
        )
    )
    monkeypatch.setattr(check_freshness, "ATC_MANIFEST", manifest)
    monkeypatch.setattr(check_freshness, "OPENTRAIL_STATE", tmp_path / "absent_opentrail.json")
    monkeypatch.setattr(check_freshness, "TOPO_MANIFEST", tmp_path / "absent_topo.json")
    monkeypatch.setattr(check_freshness, "ELEVATION_INDEX", tmp_path / "absent_elevation.json")
    monkeypatch.setattr(check_freshness, "ATC_UPDATES_FILE", tmp_path / "absent_atc_updates.json")
    monkeypatch.setattr(check_freshness, "upstream_opentrail_marker", lambda: None)
    monkeypatch.setattr(check_freshness, "upstream_elevation_marker", lambda: None)
    monkeypatch.setattr(check_freshness, "upstream_atc_updates_marker", lambda: None)

    requests_mock.get(
        "https://example.com/centerline?f=json",
        json={"editingInfo": {"dataLastEditDate": 1723739016398}},
    )
    # "shelters" (the null-dated layer) is deliberately left unmocked: a
    # null recorded marker must be classified unknown without even
    # attempting an upstream request, so a stray request here would fail
    # this test loudly (NoMockAddress) instead of silently passing.

    reports = check_freshness.check_all()

    atc_report = next(r for r in reports if r["source"] == "atc")
    assert atc_report["freshness"] is Freshness.UNKNOWN
    assert "1 unknown" in atc_report["detail"]


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


# --- Topo quad sampling -----------------------------------------------------
#
# sorted(manifest)[:TOPO_SAMPLE_SIZE] (the old implementation) sorts full S3
# manifest URLs, which sorts by state code before anything else in the path -
# so a flat slice was always the same alphabetically-first state's quads,
# every run, forever. topo_sample() replaces it with a sample stratified
# across states and rotated day to day.


def _quad_manifest(counts: dict[str, int]) -> dict:
    """A synthetic topo-quad manifest with `count` quads per state, keyed
    the same way the real manifest is - full S3 URLs with the state as the
    path segment immediately before the filename (see
    fetch_topo_quads.py's BUCKET_URL/GEOTIFF_PREFIX/<state>/<filename>)."""
    manifest = {}
    for state, count in counts.items():
        for i in range(count):
            url = f"https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/USTopo/GeoTIFF/{state}/{state}_quad_{i:03}.tif"
            manifest[url] = {"last_modified": "Thu, 19 Sep 2024 21:20:18 GMT"}
    return manifest


def test_topo_quad_state_reads_the_state_segment_from_a_manifest_url():
    url = "https://prd-tnm.s3.amazonaws.com/StagedProducts/Maps/USTopo/GeoTIFF/CT/CT_Ansonia_20240815_TM_geo.tif"

    assert check_freshness.topo_quad_state(url) == "CT"


def test_topo_quad_state_falls_back_to_the_whole_string_when_unparseable():
    """Mirrors edition_key()'s own defensive fallback: an unparseable key
    must not crash sampling or silently vanish from it."""
    assert check_freshness.topo_quad_state("not_a_url") == "not_a_url"


def test_topo_sample_is_not_permanently_limited_to_one_state():
    """The exact bug, reproduced: a manifest shaped like the real one (one
    state - Connecticut in production - with fewer quads than the sample
    size, others with far more) used to make every quad outside that one
    state permanently invisible, no matter how many times the check ran."""
    manifest = _quad_manifest({"CT": 40, "GA": 76, "VA": 316, "WV": 65})

    sample = check_freshness.topo_sample(manifest, size=25, seed="2026-07-30")

    assert {check_freshness.topo_quad_state(u) for u in sample} == {"CT", "GA", "VA", "WV"}


def test_topo_sample_gives_every_state_an_equal_share_when_the_sample_allows_it():
    manifest = _quad_manifest({"CT": 5, "GA": 5, "VA": 5})

    sample = check_freshness.topo_sample(manifest, size=6, seed="2026-07-30")

    counts = {}
    for url in sample:
        state = check_freshness.topo_quad_state(url)
        counts[state] = counts.get(state, 0) + 1
    assert counts == {"CT": 2, "GA": 2, "VA": 2}


def test_topo_sample_rotates_which_quads_it_picks_across_different_seeds():
    """Breadth across states in one run isn't enough on its own - a state
    with more quads than its round-robin share must also get different
    quads checked on different days, not the same ones forever."""
    manifest = _quad_manifest({"CT": 40, "GA": 5})

    today = check_freshness.topo_sample(manifest, size=6, seed="2026-07-30")
    tomorrow = check_freshness.topo_sample(manifest, size=6, seed="2026-07-31")

    assert set(today) != set(tomorrow)


def test_topo_sample_is_deterministic_for_a_given_seed():
    """Same seed, same sample - a real run must not be flaky, and a test
    asserting on sample contents must not be either."""
    manifest = _quad_manifest({"CT": 40, "GA": 20, "VA": 30})

    first = check_freshness.topo_sample(manifest, size=25, seed="2026-07-30")
    second = check_freshness.topo_sample(manifest, size=25, seed="2026-07-30")

    assert first == second


def test_topo_sample_size_respects_a_monkeypatched_module_constant(monkeypatch):
    """Regression guard for the default-bound-at-import-time gotcha: `size`
    must resolve TOPO_SAMPLE_SIZE inside the function body via a None
    sentinel, not as a plain `=TOPO_SAMPLE_SIZE` signature default, or this
    monkeypatch would silently stop taking effect."""
    manifest = _quad_manifest({"CT": 10, "GA": 10})
    monkeypatch.setattr(check_freshness, "TOPO_SAMPLE_SIZE", 3)

    sample = check_freshness.topo_sample(manifest, seed="2026-07-30")

    assert len(sample) == 3


def test_topo_sample_never_exceeds_what_the_manifest_actually_has():
    manifest = _quad_manifest({"CT": 2, "GA": 1})

    sample = check_freshness.topo_sample(manifest, size=25, seed="2026-07-30")

    assert set(sample) == set(manifest)


def test_topo_sample_of_an_empty_manifest_is_empty():
    assert check_freshness.topo_sample({}, size=25, seed="2026-07-30") == []


# --- Running somewhere other than the machine that fetched -----------------
#
# The check was fully built and could only ever run beside a real fetch: its
# recorded side read data/raw/*, which is gitignored, so a hosted runner
# reported everything STALE for the trivial reason that a fresh checkout has
# never fetched anything. These cover the seam that fixed it - see
# test_lib_freshness_state.py for the state format itself.


def _published_state(**overrides):
    state = {
        "version": freshness_state.STATE_VERSION,
        "captured_at": "2026-07-01T00:00:00+00:00",
        "atc": {"centerline": {"url": "https://arcgis.test/centerline", "marker": "1"}},
        "opentrail": 'W/"abc"',
    }
    state.update(overrides)
    return state


def test_a_published_state_is_compared_without_any_local_data(tmp_path, monkeypatch, requests_mock):
    """The whole point: no data/raw/, no credentials, still a real verdict.
    Every local path is pointed at a nonexistent file to prove none is read."""
    for name in ("ATC_MANIFEST", "OPENTRAIL_STATE", "TOPO_MANIFEST", "ELEVATION_INDEX"):
        monkeypatch.setattr(check_freshness, name, tmp_path / "absent.json")
    requests_mock.get("https://arcgis.test/centerline?f=json", json={"editingInfo": {"dataLastEditDate": 1}})
    requests_mock.head("https://opentrail.org/api/getData?trail=AT", headers={"ETag": 'W/"abc"'})

    reports = check_freshness.check_all(_published_state())

    assert {r["source"]: r["freshness"] for r in reports}["atc"] is Freshness.FRESH


def test_a_source_the_published_state_omits_is_never_asked_about(tmp_path, monkeypatch, requests_mock):
    """A build that only ran the vector leg publishes no topo markers. Asking
    upstream about them anyway would spend requests to learn nothing, and any
    answer would have nothing to be compared against."""
    for name in ("ATC_MANIFEST", "OPENTRAIL_STATE", "TOPO_MANIFEST", "ELEVATION_INDEX"):
        monkeypatch.setattr(check_freshness, name, tmp_path / "absent.json")
    requests_mock.get("https://arcgis.test/centerline?f=json", json={"editingInfo": {"dataLastEditDate": 1}})
    requests_mock.head("https://opentrail.org/api/getData?trail=AT", headers={"ETag": 'W/"abc"'})

    # No mock is registered for TNM or S3: a request to either fails loudly
    # here rather than passing silently.
    reports = check_freshness.check_all(_published_state())

    verdicts = {r["source"]: r for r in reports}
    assert verdicts["topo_quads"]["freshness"] is Freshness.UNKNOWN
    assert verdicts["topo_quads"]["detail"] == "not in this state"


def test_capture_writes_a_state_and_asks_nothing_upstream(tmp_path, monkeypatch):
    """--capture runs inside a build, beside the fetch it is recording. A
    single upstream request here would be a request the build did not need."""
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"centerline": {"url": "https://x.test/c", "data_last_edit_date": 7}}))
    monkeypatch.setattr(check_freshness, "ATC_MANIFEST", manifest)
    for name in ("OPENTRAIL_STATE", "TOPO_MANIFEST", "ELEVATION_INDEX"):
        monkeypatch.setattr(check_freshness, name, tmp_path / "absent.json")
    out = tmp_path / "build_state.json"

    # requests is not mocked at all: any network call raises.
    assert check_freshness.main(["--capture", str(out)]) == 0

    state = json.loads(out.read_text())
    assert state["atc"]["centerline"]["marker"] == "7"
    assert "topo_quads" not in state


def test_a_state_that_cannot_be_loaded_exits_two_not_one(tmp_path):
    """Distinct from a stale verdict on purpose. "Nothing published yet" and
    "an upstream moved" want opposite responses, and a scheduled reporter that
    conflated them would raise an alarm about a bucket that has simply never
    published."""
    assert check_freshness.main(["--state", str(tmp_path / "never_written.json")]) == 2


def test_exit_zero_reports_staleness_without_failing_the_run(tmp_path, monkeypatch, requests_mock):
    """Staleness is the normal state between weekly builds. A red X every day
    for a legitimately-changed upstream trains people to ignore the signal."""
    for name in ("ATC_MANIFEST", "OPENTRAIL_STATE", "TOPO_MANIFEST", "ELEVATION_INDEX"):
        monkeypatch.setattr(check_freshness, name, tmp_path / "absent.json")
    state = tmp_path / "state.json"
    state.write_text(json.dumps(_published_state()))
    requests_mock.get("https://arcgis.test/centerline?f=json", json={"editingInfo": {"dataLastEditDate": 999}})
    requests_mock.head("https://opentrail.org/api/getData?trail=AT", headers={"ETag": 'W/"abc"'})

    assert check_freshness.main(["--state", str(state)]) == 1
    assert check_freshness.main(["--state", str(state), "--exit-zero"]) == 0


def test_the_json_verdict_names_which_layers_moved(tmp_path, monkeypatch, requests_mock):
    for name in ("ATC_MANIFEST", "OPENTRAIL_STATE", "TOPO_MANIFEST", "ELEVATION_INDEX"):
        monkeypatch.setattr(check_freshness, name, tmp_path / "absent.json")
    state = tmp_path / "state.json"
    state.write_text(json.dumps(_published_state()))
    out = tmp_path / "verdict.json"
    requests_mock.get("https://arcgis.test/centerline?f=json", json={"editingInfo": {"dataLastEditDate": 999}})
    requests_mock.head("https://opentrail.org/api/getData?trail=AT", headers={"ETag": 'W/"abc"'})

    check_freshness.main(["--state", str(state), "--json", str(out), "--exit-zero"])

    verdict = json.loads(out.read_text())
    assert verdict["needs_refetch"] == ["atc"]
    assert next(s for s in verdict["sources"] if s["source"] == "atc")["changed"] == ["centerline"]


def test_the_json_verdict_records_how_old_the_state_it_trusted_was(tmp_path, monkeypatch, requests_mock):
    """A FRESH verdict against a six-month-old capture means "nothing has
    changed since a build six months ago", which is not what a reader assumes
    it means. The age is published rather than left to be inferred."""
    for name in ("ATC_MANIFEST", "OPENTRAIL_STATE", "TOPO_MANIFEST", "ELEVATION_INDEX"):
        monkeypatch.setattr(check_freshness, name, tmp_path / "absent.json")
    state = tmp_path / "state.json"
    state.write_text(json.dumps(_published_state()))
    out = tmp_path / "verdict.json"
    requests_mock.get("https://arcgis.test/centerline?f=json", json={"editingInfo": {"dataLastEditDate": 1}})
    requests_mock.head("https://opentrail.org/api/getData?trail=AT", headers={"ETag": 'W/"abc"'})

    check_freshness.main(["--state", str(state), "--json", str(out), "--exit-zero"])

    verdict = json.loads(out.read_text())
    assert verdict["state_captured_at"] == "2026-07-01T00:00:00+00:00"
    assert verdict["state_age_days"] >= 0
