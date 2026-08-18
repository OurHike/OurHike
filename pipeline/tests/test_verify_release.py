"""Tests for verify_release.py.

The battery itself runs as a workflow step against a real release, per
TESTING.md - what this file covers is what the script CONCLUDES from a set of
responses, which is the half a checkout can answer.

Two groups carry most of the weight:

`TestTheContractIsReadNotRestated` covers the TypeScript parsing. It is the
ugliest part of the script and the part whose silent failure would be worst: a
regex that stopped matching would check fewer keys than the client asks for and
report a clean release, which is the exact shape of #427.

`TestASkipIsNeverAPass` covers what still cannot run - one check now, down from
four since #374's item 3 wrote 3, 17 and 19. A skip that reads like a pass is
the failure this repository keeps finding, so the skips are asserted to be
present, to name their reason, and to fail the gate under `--strict`.

The last four groups cover those three new checks, and most of their weight is
on a bucket MID-MIGRATION rather than on the happy path - a release published
before #500 has no index, and one published before the `release` field has an
index nothing points into. Both are states a real bucket passes through.
"""

from __future__ import annotations

import hashlib
import json

import pytest
import requests

from verify_release import (
    FAILED,
    OK,
    SKIPPED,
    advertised_sizes,
    archive_keys,
    check_all,
    check_cors,
    check_fetchable,
    check_full_hash,
    check_manifest,
    check_nothing_lost,
    check_release_regression,
    check_released_folder,
    check_vector,
    expected_client_keys,
    previous_release_id,
    release_checks,
    skipped_checks,
    verdict_document,
)

BASE = "https://data.example.org"

CONFIG_TS = """
const BACKGROUND_ARCHIVES: Record<DetailLevel, string> = {
  light: 'background_z11.pmtiles',
  standard: 'background.pmtiles',
  fine: 'background_z13.pmtiles',
}
export const TRAILS_KEY = 'trails.geojson'
export const POI_TYPES = ['shelter', 'water'] as const
export function poiKey(type: PoiType): string {
  return `poi_${type}.geojson`
}
"""

DETAIL_TS = """
  { level: 'light', zoom: 11, sizeBytes: 68_900_000, recommended: false },
  { level: 'standard', zoom: 12, sizeBytes: 300_300_000, recommended: true },
"""


def _headers(length="100", etag='"abc"', ranges="bytes", expose=None):
    headers = {"Content-Length": length}
    if etag:
        headers["ETag"] = etag
    if ranges:
        headers["Accept-Ranges"] = ranges
    if expose is not None:
        headers["Access-Control-Expose-Headers"] = expose
    return headers


class TestTheContractIsReadNotRestated:
    def test_every_key_the_client_asks_for_is_derived(self):
        assert expected_client_keys(CONFIG_TS) == [
            "trails.geojson",
            "poi_shelter.geojson",
            "poi_water.geojson",
            "background_z11.pmtiles",
            "background.pmtiles",
            "background_z13.pmtiles",
        ]

    def test_a_restructured_config_raises_rather_than_checking_fewer_keys(self):
        """The failure mode that matters. A regex quietly matching nothing
        would produce a short list, every key on it would be present, and the
        release would pass while missing what the app actually fetches - which
        is #427's shape, arrived at from the other direction."""
        with pytest.raises(ValueError, match="could not read the key contract"):
            expected_client_keys("export const SOMETHING_ELSE = 1")

    def test_advertised_sizes_survive_numeric_separators(self):
        # `68_900_000` is how the client writes it, and int() will not take it.
        assert advertised_sizes(DETAIL_TS) == {"light": 68_900_000, "standard": 300_300_000}

    def test_a_restructured_detail_table_raises(self):
        with pytest.raises(ValueError, match="DOWNLOAD_DETAIL_LEVELS"):
            advertised_sizes("const LEVELS = []")

    def test_tiers_map_to_the_keys_the_bucket_holds(self):
        assert archive_keys(CONFIG_TS)["fine"] == "background_z13.pmtiles"


class TestTheManifest:
    def test_an_unreadable_manifest_fails_rather_than_reporting_nothing(self):
        assert check_manifest(None)["state"] == FAILED

    def test_a_manifest_with_no_artifacts_fails(self):
        assert check_manifest({"version": 1})["state"] == FAILED

    def test_an_artifact_with_no_sha256_fails(self):
        """Check 5 is the whole point of the battery and it is driven off these
        hashes. An artifact published without one is not verifiable at all."""
        verdict = check_manifest({"artifacts": {"trails.geojson": {}}})

        assert verdict["state"] == FAILED
        assert "sha256" in verdict["detail"]


class TestBytes:
    def test_a_missing_accept_ranges_fails_because_a_resume_needs_it(self, requests_mock):
        requests_mock.head(f"{BASE}/a.pmtiles", headers=_headers(ranges=None))

        verdict = check_fetchable(BASE, "a.pmtiles")

        assert verdict["state"] == FAILED
        assert "resume" in verdict["detail"]

    def test_a_missing_etag_fails_because_if_range_is_compared_against_it(self, requests_mock):
        requests_mock.head(f"{BASE}/a.pmtiles", headers=_headers(etag=None))

        assert check_fetchable(BASE, "a.pmtiles")["state"] == FAILED

    def test_the_published_bytes_are_hashed_whole(self, requests_mock):
        body = b"x" * 4096
        requests_mock.get(f"{BASE}/a.bin", content=body)

        verdict = check_full_hash(BASE, "a.bin", hashlib.sha256(body).hexdigest())

        assert verdict["state"] == OK
        assert "4096" in verdict["detail"]

    def test_bytes_that_are_not_the_built_bytes_fail_loudly(self, requests_mock):
        """The one check nothing else in the repository performs. A published
        object that is not the object that was built and quality-checked has to
        stop a release, and the message has to say that plainly."""
        requests_mock.get(f"{BASE}/a.bin", content=b"tampered")

        verdict = check_full_hash(BASE, "a.bin", hashlib.sha256(b"original").hexdigest())

        assert verdict["state"] == FAILED
        assert "NOT the object that was built" in verdict["detail"]

    def test_a_download_cut_off_partway_is_a_failure_not_a_pass(self, requests_mock):
        requests_mock.get(f"{BASE}/a.bin", exc=requests.ConnectionError)

        assert check_full_hash(BASE, "a.bin", "whatever")["state"] == FAILED


class TestCors:
    def test_headers_present_but_unreadable_still_fails(self, requests_mock):
        """R2 sent all four throughout #427 and a browser still could not see
        them. Presence is not the question; `Access-Control-Expose-Headers` is."""
        requests_mock.get(f"{BASE}/a.pmtiles", headers=_headers(expose="etag"), status_code=206)

        verdict = check_cors(BASE, "a.pmtiles")

        assert verdict["state"] == FAILED
        assert "content-range" in verdict["detail"]

    def test_the_full_expose_list_passes(self, requests_mock):
        requests_mock.get(
            f"{BASE}/a.pmtiles",
            headers=_headers(expose="accept-ranges, content-length, content-range, etag"),
            status_code=206,
        )

        assert check_cors(BASE, "a.pmtiles")["state"] == OK

    def test_a_wildcard_expose_answer_passes_too(self, requests_mock):
        """#659: `Access-Control-Expose-Headers: *` exposes everything to a
        request without credentials - a host answering it would otherwise
        fail this check while every browser could read all four headers,
        blocking a good release candidate."""
        requests_mock.get(f"{BASE}/a.pmtiles", headers=_headers(expose="*"), status_code=206)

        assert check_cors(BASE, "a.pmtiles")["state"] == OK


class TestVectorContent:
    def _collection(self, features):
        return {"type": "FeatureCollection", "features": features}

    def _point(self, lon=-77.0, lat=39.0, **properties):
        return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": properties}

    def test_a_geometry_off_the_trail_is_caught(self, requests_mock):
        """(0, 0) is what a projection bug produces, and it parses perfectly."""
        requests_mock.get(f"{BASE}/poi_shelter.geojson", json=self._collection([self._point(0.0, 0.0)]))

        states = {r["check"]: r["state"] for r in check_vector(BASE, ["poi_shelter.geojson"])}

        assert states[15] == FAILED

    def test_a_feature_with_no_geometry_is_caught(self, requests_mock):
        requests_mock.get(
            f"{BASE}/poi_shelter.geojson",
            json=self._collection([{"type": "Feature", "geometry": None, "properties": {}}]),
        )

        assert {r["check"]: r["state"] for r in check_vector(BASE, ["poi_shelter.geojson"])}[15] == FAILED

    def test_an_empty_type_fails_its_minimum_but_crossing_may_be_empty(self, requests_mock):
        """export_poi.py's own exception, kept in step: every POI type must be
        non-empty except `crossing`, which legitimately is for the real AT."""
        requests_mock.get(f"{BASE}/poi_crossing.geojson", json=self._collection([]))
        requests_mock.get(f"{BASE}/poi_water.geojson", json=self._collection([]))

        states = [r for r in check_vector(BASE, ["poi_crossing.geojson"]) if r["check"] == 14]
        assert states[0]["state"] == OK

        states = [r for r in check_vector(BASE, ["poi_water.geojson"]) if r["check"] == 14]
        assert states[0]["state"] == FAILED

    def test_a_trail_without_a_blaze_colour_is_caught(self, requests_mock):
        requests_mock.get(f"{BASE}/trails.geojson", json=self._collection([self._point()]))

        assert {r["check"]: r["state"] for r in check_vector(BASE, ["trails.geojson"])}[16] == FAILED

    def test_a_trail_with_one_passes(self, requests_mock):
        requests_mock.get(f"{BASE}/trails.geojson", json=self._collection([self._point(blaze_color="#ffffff")]))

        assert {r["check"]: r["state"] for r in check_vector(BASE, ["trails.geojson"])}[16] == OK

    def test_something_that_is_not_a_feature_collection_is_caught(self, requests_mock):
        requests_mock.get(f"{BASE}/trails.geojson", json={"type": "Topology"})

        assert {r["check"]: r["state"] for r in check_vector(BASE, ["trails.geojson"])}[13] == FAILED


class TestASkipIsNeverAPass:
    def test_the_checks_that_cannot_run_are_listed_by_number(self):
        """Three: 10, and since #653, 6 and 11. The two newcomers were not
        skipped before - they were ABSENT, unmentioned by a file whose header
        says a skip is never silent, and this very test pinned the absence in
        place by asserting the set was exactly {10}. The set is the honest
        roster now; shrinking it means BUILDING a check, not deleting a row."""
        assert {report["check"] for report in skipped_checks()} == {6, 10, 11}

    def test_each_one_says_why_rather_than_just_being_absent(self):
        for report in skipped_checks():
            assert report["state"] == SKIPPED
            assert report["detail"].strip()

    def test_strict_turns_a_skip_into_a_failed_gate(self):
        """Without it, a battery that quietly did not ask reads identically to
        one that asked and was satisfied."""
        reports = skipped_checks()

        assert verdict_document(BASE, reports, strict=False)["gate"] == "pass"
        assert verdict_document(BASE, reports, strict=True)["gate"] == "fail"

    def test_a_real_failure_fails_the_gate_either_way(self):
        reports = [{"check": 5, "key": "a", "state": FAILED, "detail": "bad"}]

        assert verdict_document(BASE, reports, strict=False)["gate"] == "fail"


class TestTheWholeRun:
    def test_an_unreadable_manifest_stops_the_run_without_pretending(self, requests_mock):
        """Nothing downstream means anything without the manifest, and the run
        must not report a short clean list as though it had checked."""
        requests_mock.get(f"{BASE}/latest.json", status_code=404)

        reports = check_all(BASE, hash_artifacts=False)

        assert reports[0]["state"] == FAILED
        # 3, 17, 19, 20 and 21 read a release out of the manifest, so they
        # cannot run either - and must still APPEAR rather than vanishing,
        # or a reader counting checks finds a short clean run. 6 and 11 are
        # the standing skips (#653), present in every run until somebody
        # builds them.
        assert {r["check"] for r in reports if r["state"] == SKIPPED} == {3, 6, 10, 11, 17, 19, 20, 21}


# ---------------------------------------------------------------------------
# F. The releases hikers are already on still work (#374's item 3)
#
# These three were skipped by construction until the layout existed. What they
# are worth is entirely in what they catch that nothing else does: every other
# check here asks whether the thing just built is good, and these ask whether
# the thing people are already using is still there.
#
# The awkward case is the one most of this covers: a bucket MID-MIGRATION. A
# release built before #500 has no index, and one built before the `release`
# field has an index but no pointer into it. Both have to skip with a reason
# naming which half is missing, because both are states a real bucket passes
# through and neither is a fault.
# ---------------------------------------------------------------------------


def _index(*ids):
    return {"releases": [{"id": name, "created_at": f"{name}T00:00:00+00:00", "version": name} for name in ids]}


def _release_manifest(release_id, artifacts):
    return {
        "version": release_id,
        "release": release_id,
        "artifacts": {name: {"sha256": digest} for name, digest in artifacts.items()},
    }


class TestNothingLostSinceTheLastRelease:
    def test_an_artifact_that_vanished_fails(self):
        """The failure a hiker meets as a 404 partway through a download, and
        the one every other check here is blind to - they all ask about what
        IS published rather than what used to be."""
        before = _release_manifest("2026-08-12", {"trails.geojson": "a", "poi_water.geojson": "b"})
        now = _release_manifest("2026-08-13", {"trails.geojson": "a"})

        report = check_nothing_lost("2026-08-12", before, now)

        assert report["state"] == FAILED
        assert "poi_water.geojson" in report["detail"]

    def test_carrying_everything_forward_passes(self):
        before = _release_manifest("2026-08-12", {"trails.geojson": "a"})
        now = _release_manifest("2026-08-13", {"trails.geojson": "a", "poi_water.geojson": "b"})

        assert check_nothing_lost("2026-08-12", before, now)["state"] == OK

    def test_a_new_artifact_is_not_a_loss(self):
        """Additions are the normal shape of a release and must not read as a
        regression, or the check is an alarm that is always on."""
        before = _release_manifest("2026-08-12", {"trails.geojson": "a"})
        now = _release_manifest("2026-08-13", {"trails.geojson": "a", "club_sections.json": "c"})

        assert check_nothing_lost("2026-08-12", before, now)["state"] == OK


class TestTheReleaseBeforeThisOne:
    def test_it_is_the_one_written_before_it_rather_than_the_lexically_smaller(self):
        index = _index("2026-08-12", "2026-08-13", "2026-08-13-2")

        assert previous_release_id(index, "2026-08-13-2") == "2026-08-13"

    def test_the_first_release_has_nothing_before_it(self):
        assert previous_release_id(_index("2026-08-13"), "2026-08-13") is None

    def test_a_release_the_index_never_heard_of_has_no_predecessor(self):
        """A pointer naming a folder the index does not list is a real
        inconsistency, and guessing a predecessor for it would compare against
        an arbitrary release."""
        assert previous_release_id(_index("2026-08-12"), "2026-08-99") is None


class TestASizeRegressionAgainstTheLastRelease:
    def test_an_artifact_that_shrank_past_the_threshold_fails(self, requests_mock):
        requests_mock.head(f"{BASE}/releases/2026-08-12/trails.geojson", headers={"Content-Length": "1000"})
        requests_mock.head(f"{BASE}/releases/2026-08-13/trails.geojson", headers={"Content-Length": "500"})
        before = _release_manifest("2026-08-12", {"trails.geojson": "a"})
        now = _release_manifest("2026-08-13", {"trails.geojson": "b"})

        [report] = check_release_regression(BASE, "2026-08-12", "2026-08-13", before, now)

        assert report["state"] == FAILED
        assert "50%" in report["detail"]

    def test_a_small_change_passes(self, requests_mock):
        requests_mock.head(f"{BASE}/releases/2026-08-12/trails.geojson", headers={"Content-Length": "1000"})
        requests_mock.head(f"{BASE}/releases/2026-08-13/trails.geojson", headers={"Content-Length": "980"})
        before = _release_manifest("2026-08-12", {"trails.geojson": "a"})
        now = _release_manifest("2026-08-13", {"trails.geojson": "b"})

        assert check_release_regression(BASE, "2026-08-12", "2026-08-13", before, now)[0]["state"] == OK

    def test_growth_is_never_a_regression(self, requests_mock):
        requests_mock.head(f"{BASE}/releases/2026-08-12/trails.geojson", headers={"Content-Length": "100"})
        requests_mock.head(f"{BASE}/releases/2026-08-13/trails.geojson", headers={"Content-Length": "9000"})
        before = _release_manifest("2026-08-12", {"trails.geojson": "a"})
        now = _release_manifest("2026-08-13", {"trails.geojson": "b"})

        assert check_release_regression(BASE, "2026-08-12", "2026-08-13", before, now)[0]["state"] == OK

    def test_an_artifact_only_in_the_new_release_is_not_measured(self, requests_mock):
        """Nothing to compare against is not a drop. Check 3 is what notices a
        LOST artifact; this one is only about the ones in both."""
        before = _release_manifest("2026-08-12", {"trails.geojson": "a"})
        now = _release_manifest("2026-08-13", {"trails.geojson": "a", "club_sections.json": "c"})
        requests_mock.head(f"{BASE}/releases/2026-08-12/trails.geojson", headers={"Content-Length": "100"})
        requests_mock.head(f"{BASE}/releases/2026-08-13/trails.geojson", headers={"Content-Length": "100"})

        reports = check_release_regression(BASE, "2026-08-12", "2026-08-13", before, now)

        assert [report["key"] for report in reports] == ["trails.geojson"]

    def test_a_size_that_cannot_be_read_skips_rather_than_passing(self, requests_mock):
        """Never OK on a failure to ask. A missing Content-Length reported as
        no-drop is the false-clean this whole battery is against."""
        requests_mock.head(f"{BASE}/releases/2026-08-12/trails.geojson", status_code=404)
        requests_mock.head(f"{BASE}/releases/2026-08-13/trails.geojson", headers={"Content-Length": "500"})
        before = _release_manifest("2026-08-12", {"trails.geojson": "a"})
        now = _release_manifest("2026-08-13", {"trails.geojson": "b"})

        assert check_release_regression(BASE, "2026-08-12", "2026-08-13", before, now)[0]["state"] == SKIPPED


class TestTheFolderHikersArePinnedTo:
    def test_a_deleted_object_in_the_released_folder_fails(self, requests_mock):
        """The headline property: this fails for a reason no candidate can
        cause - a lifecycle rule, an accidental delete, a permissions change on
        data people are using today."""
        requests_mock.head(f"{BASE}/releases/2026-08-13/trails.geojson", status_code=404)
        manifest = _release_manifest("2026-08-13", {"trails.geojson": "a"})

        reports = check_released_folder(BASE, "2026-08-13", manifest, hash_artifacts=False)

        assert [report["check"] for report in reports] == [19]
        assert reports[0]["state"] == FAILED

    def test_an_intact_folder_passes(self, requests_mock):
        requests_mock.head(
            f"{BASE}/releases/2026-08-13/trails.geojson",
            headers={"Content-Length": "10", "Accept-Ranges": "bytes", "ETag": '"x"'},
        )
        manifest = _release_manifest("2026-08-13", {"trails.geojson": "a"})

        reports = check_released_folder(BASE, "2026-08-13", manifest, hash_artifacts=False)

        assert all(report["state"] == OK for report in reports)

    def test_an_empty_manifest_fails_rather_than_passing_vacuously(self):
        """Zero artifacts iterated is zero failures, which would report a
        released folder as intact having looked at nothing in it."""
        report = check_released_folder(BASE, "2026-08-13", {"artifacts": {}}, hash_artifacts=False)[0]

        assert report["state"] == FAILED


class TestABucketMidMigration:
    def test_no_index_skips_all_three_and_says_which_half_is_missing(self, requests_mock):
        requests_mock.get(f"{BASE}/releases/index.json", status_code=404)

        reports = release_checks(BASE, {"release": "2026-08-13", "artifacts": {}}, hash_artifacts=False)

        assert {report["check"] for report in reports} == {3, 17, 19}
        assert all(report["state"] == SKIPPED for report in reports)
        assert all("#500" in report["detail"] for report in reports)

    def test_a_manifest_with_no_release_field_skips_all_three(self, requests_mock):
        """`latest.json` written before #500 added the field. The index may
        exist and still be unusable, because nothing says which folder holds
        these bytes."""
        requests_mock.get(f"{BASE}/releases/index.json", json=_index("2026-08-13"))

        reports = release_checks(BASE, {"artifacts": {}}, hash_artifacts=False)

        assert {report["check"] for report in reports} == {3, 17, 19}
        assert all(report["state"] == SKIPPED for report in reports)

    def test_a_pointer_at_a_folder_with_no_manifest_FAILS(self, requests_mock):
        """Not a skip. The pointer every client fetches first names a release
        that is not there, which is the one state #500's write ordering exists
        to make impossible - so meeting it means something is actually wrong."""
        requests_mock.get(f"{BASE}/releases/index.json", json=_index("2026-08-13"))
        requests_mock.get(f"{BASE}/releases/2026-08-13/manifest.json", status_code=404)

        reports = release_checks(BASE, {"release": "2026-08-13", "artifacts": {}}, hash_artifacts=False)

        assert all(report["state"] == FAILED for report in reports)

    def test_the_first_ever_release_still_gets_its_folder_verified(self, requests_mock):
        """Nothing to compare against does not mean nothing to check. 3 and 17
        skip; 19 - the headline one - still runs."""
        requests_mock.get(f"{BASE}/releases/index.json", json=_index("2026-08-13"))
        requests_mock.get(
            f"{BASE}/releases/2026-08-13/manifest.json",
            json=_release_manifest("2026-08-13", {"trails.geojson": "a"}),
        )
        requests_mock.head(
            f"{BASE}/releases/2026-08-13/trails.geojson",
            headers={"Content-Length": "10", "Accept-Ranges": "bytes", "ETag": '"x"'},
        )

        reports = release_checks(BASE, {"release": "2026-08-13", "artifacts": {}}, hash_artifacts=False)

        by_check = {report["check"]: report for report in reports}
        assert by_check[3]["state"] == SKIPPED
        assert by_check[17]["state"] == SKIPPED
        assert by_check[19]["state"] == OK


class TestStretchCoverage:
    """Check 20 (#556): the stretch units tile the trail, and everything the
    index names is really published."""

    def _manifest(self, extra=None):
        artifacts = {
            "at_basemap_stretches.json": {"sha256": "a" * 64},
            "at_basemap_context.pmtiles": {"sha256": "b" * 64},
            "at_basemap_stretch_00.pmtiles": {"sha256": "c" * 64},
            "at_basemap_stretch_01.pmtiles": {"sha256": "d" * 64},
            **(extra or {}),
        }
        return {"artifacts": artifacts}

    def _index(self, stretches, context="at_basemap_context.pmtiles", top=100.0):
        return {
            "stretch_miles": 50.0,
            "axis_top_mile": top,
            "context": context,
            "stretches": stretches,
        }

    def test_a_complete_tiling_passes(self, requests_mock):
        from verify_release import check_stretch_coverage

        requests_mock.get(
            f"{BASE}/at_basemap_stretches.json",
            json=self._index(
                [
                    {"id": 0, "key": "at_basemap_stretch_00.pmtiles", "miles": [0.0, 50.0]},
                    {"id": 1, "key": "at_basemap_stretch_01.pmtiles", "miles": [50.0, 100.0]},
                ]
            ),
        )

        reports = check_stretch_coverage(BASE, self._manifest())
        by_key = {report["key"]: report for report in reports}

        assert by_key["at_basemap_stretches.json"]["state"] == "ok"
        assert by_key["dem_stretches.json"]["state"] == "skipped", "no dem index published is a skip, not a pass"

    def test_a_mile_gap_between_stretches_fails(self, requests_mock):
        """A gap is a slice of trail no unit covers - blank map on a ridge
        that every per-artifact check would wave through."""
        from verify_release import check_stretch_coverage

        requests_mock.get(
            f"{BASE}/at_basemap_stretches.json",
            json=self._index(
                [
                    {"id": 0, "key": "at_basemap_stretch_00.pmtiles", "miles": [0.0, 50.0]},
                    {"id": 1, "key": "at_basemap_stretch_01.pmtiles", "miles": [60.0, 100.0]},
                ]
            ),
        )

        reports = check_stretch_coverage(BASE, self._manifest())
        report = next(r for r in reports if r["key"] == "at_basemap_stretches.json")

        assert report["state"] == "failed"
        assert "gap" in report["detail"]

    def test_a_stretch_named_but_not_published_fails(self, requests_mock):
        from verify_release import check_stretch_coverage

        requests_mock.get(
            f"{BASE}/at_basemap_stretches.json",
            json=self._index(
                [
                    {"id": 0, "key": "at_basemap_stretch_00.pmtiles", "miles": [0.0, 50.0]},
                    {"id": 1, "key": "at_basemap_stretch_99.pmtiles", "miles": [50.0, 100.0]},
                ]
            ),
        )

        reports = check_stretch_coverage(BASE, self._manifest())
        report = next(r for r in reports if r["key"] == "at_basemap_stretches.json")

        assert report["state"] == "failed"
        assert "not published" in report["detail"]

    def test_coverage_stopping_short_of_the_axis_top_fails(self, requests_mock):
        from verify_release import check_stretch_coverage

        requests_mock.get(
            f"{BASE}/at_basemap_stretches.json",
            json=self._index(
                [{"id": 0, "key": "at_basemap_stretch_00.pmtiles", "miles": [0.0, 50.0]}],
                top=100.0,
            ),
        )

        reports = check_stretch_coverage(BASE, self._manifest())
        report = next(r for r in reports if r["key"] == "at_basemap_stretches.json")

        assert report["state"] == "failed"
        assert "short of the axis top" in report["detail"]


class TestManifestSizes:
    def test_a_content_length_disagreeing_with_size_bytes_fails(self, requests_mock):
        """Since #556 the manifest publishes size_bytes, and for the
        identity-uploaded binaries the served Content-Length must be exactly
        it - DATA_RELEASES.md §3's check, finally askable."""
        requests_mock.head(f"{BASE}/a.pmtiles", headers=_headers(length="100"))

        verdict = check_fetchable(BASE, "a.pmtiles", expected_size=90)

        assert verdict["state"] == FAILED
        assert "size_bytes" in verdict["detail"]

    def test_a_matching_content_length_passes(self, requests_mock):
        requests_mock.head(f"{BASE}/a.pmtiles", headers=_headers(length="100"))

        verdict = check_fetchable(BASE, "a.pmtiles", expected_size=100)

        assert verdict["state"] == OK


class TestPoiIdentity:
    """Check 21 (#672): every published POI id is a promise the identity
    ledger keeps - a live row whose provenance agrees, published once."""

    def _ledger(self, tmp_path, monkeypatch, pois):
        import verify_release

        path = tmp_path / "poi_identity.json"
        path.write_text(json.dumps({"pois": pois}))
        monkeypatch.setattr(verify_release, "IDENTITY_LEDGER_PATH", path)

    def _row(self, source="atc_shelters", sfid="glob-1", retired=None):
        row = {"poi_type": "shelter", "source": source, "source_feature_id": sfid, "name": "S", "lat": 41.0, "lon": -74.0}
        if retired:
            row["retired"] = retired
        return row

    def _feature(self, poi_id="atc_shelters:glob-1", source="atc_shelters", sfid="glob-1"):
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [-74.0, 41.0]},
            "properties": {"id": poi_id, "source": source, "source_feature_id": sfid},
        }

    def _serve(self, requests_mock, features):
        requests_mock.get(f"{BASE}/poi_shelter.geojson", json={"type": "FeatureCollection", "features": features})

    def _manifest(self):
        return {"artifacts": {"poi_shelter.geojson": {"sha256": "a" * 64}}}

    def test_a_kept_promise_passes(self, tmp_path, monkeypatch, requests_mock):
        from verify_release import check_poi_identity

        self._ledger(tmp_path, monkeypatch, {"atc_shelters:glob-1": self._row()})
        self._serve(requests_mock, [self._feature()])

        reports = check_poi_identity(BASE, self._manifest())

        assert [r["state"] for r in reports] == [OK]

    def test_an_id_with_no_ledger_row_fails(self, tmp_path, monkeypatch, requests_mock):
        from verify_release import check_poi_identity

        self._ledger(tmp_path, monkeypatch, {})
        self._serve(requests_mock, [self._feature()])

        reports = check_poi_identity(BASE, self._manifest())

        assert reports[0]["state"] == FAILED
        assert "no ledger row" in reports[0]["detail"]

    def test_a_retired_id_published_live_fails(self, tmp_path, monkeypatch, requests_mock):
        from verify_release import check_poi_identity

        self._ledger(tmp_path, monkeypatch, {"atc_shelters:glob-1": self._row(retired="2027-09-14")})
        self._serve(requests_mock, [self._feature()])

        reports = check_poi_identity(BASE, self._manifest())

        assert reports[0]["state"] == FAILED
        assert "RETIRED" in reports[0]["detail"]

    def test_provenance_disagreement_fails(self, tmp_path, monkeypatch, requests_mock):
        """The ledger carried the id onto a new key; an artifact still
        publishing the old key is a stale export, not a release."""
        from verify_release import check_poi_identity

        self._ledger(tmp_path, monkeypatch, {"atc_shelters:glob-1": self._row(sfid="rekeyed")})
        self._serve(requests_mock, [self._feature(sfid="glob-1")])

        reports = check_poi_identity(BASE, self._manifest())

        assert reports[0]["state"] == FAILED
        assert "ledger says" in reports[0]["detail"]

    def test_one_id_published_twice_fails(self, tmp_path, monkeypatch, requests_mock):
        from verify_release import check_poi_identity

        self._ledger(tmp_path, monkeypatch, {"atc_shelters:glob-1": self._row()})
        self._serve(requests_mock, [self._feature(), self._feature()])

        reports = check_poi_identity(BASE, self._manifest())

        assert reports[0]["state"] == FAILED
        assert "one id, one place, once" in reports[0]["detail"]

    def test_no_ledger_in_the_checkout_is_a_skip_not_a_pass(self, tmp_path, monkeypatch):
        import verify_release
        from verify_release import check_poi_identity

        monkeypatch.setattr(verify_release, "IDENTITY_LEDGER_PATH", tmp_path / "absent.json")

        reports = check_poi_identity(BASE, self._manifest())

        assert [r["state"] for r in reports] == [SKIPPED]
