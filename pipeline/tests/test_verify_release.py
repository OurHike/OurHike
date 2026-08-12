"""Tests for verify_release.py.

The battery itself runs as a workflow step against a real release, per
TESTING.md - what this file covers is what the script CONCLUDES from a set of
responses, which is the half a checkout can answer.

Two groups carry most of the weight:

`TestTheContractIsReadNotRestated` covers the TypeScript parsing. It is the
ugliest part of the script and the part whose silent failure would be worst: a
regex that stopped matching would check fewer keys than the client asks for and
report a clean release, which is the exact shape of #427.

`TestASkipIsNeverAPass` covers the four checks that cannot run yet. A skip that
reads like a pass is the failure this repository keeps finding, so the skips
are asserted to be present, to name their reason, and to fail the gate under
`--strict`.
"""

from __future__ import annotations

import hashlib

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
    check_if_range,
    check_manifest,
    check_vector,
    expected_client_keys,
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


class TestIfRange:
    def test_a_bucket_that_honours_it_passes(self, requests_mock):
        requests_mock.head(f"{BASE}/a.pmtiles", headers=_headers())
        requests_mock.get(
            f"{BASE}/a.pmtiles",
            [{"status_code": 206}, {"status_code": 200}],
        )

        assert check_if_range(BASE, "a.pmtiles")["state"] == OK

    def test_a_bucket_that_ignores_it_fails_and_says_what_is_left(self, requests_mock):
        """Measured against the real r2.dev endpoint: a stale ETag is answered
        206 with the range served. It stays a FAILURE (#506) - a gate taught to
        expect the breakage cannot notice it was fixed - but the message must
        not overstate what is at risk. `archiveDownload.ts` makes the same
        comparison client-side against the ETag on the 206, so what is missing
        is the server-side half of a defence rather than the whole of one."""
        requests_mock.head(f"{BASE}/a.pmtiles", headers=_headers())
        requests_mock.get(f"{BASE}/a.pmtiles", [{"status_code": 206}, {"status_code": 206}])

        verdict = check_if_range(BASE, "a.pmtiles")

        assert verdict["state"] == FAILED
        assert "ignoring If-Range" in verdict["detail"]
        assert "does not depend on it" in verdict["detail"]
        assert "server-side half" in verdict["detail"]

    def test_no_etag_means_the_question_cannot_be_asked(self, requests_mock):
        requests_mock.head(f"{BASE}/a.pmtiles", headers=_headers(etag=None))

        assert check_if_range(BASE, "a.pmtiles")["state"] == FAILED


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
        assert {report["check"] for report in skipped_checks()} == {3, 10, 17, 19}

    def test_each_one_says_why_rather_than_just_being_absent(self):
        for report in skipped_checks():
            assert report["state"] == SKIPPED
            assert report["detail"].strip()

    def test_the_release_blocking_ones_name_their_dependency(self):
        by_number = {report["check"]: report for report in skipped_checks()}
        for number in (3, 17, 19):
            assert "#500" in by_number[number]["detail"]

    def test_strict_turns_a_skip_into_a_failed_gate(self):
        """What a release gate should use once #500 lands. Without it, a
        battery that quietly did not ask reads identically to one that asked
        and was satisfied."""
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
        assert {r["check"] for r in reports if r["state"] == SKIPPED} == {3, 10, 17, 19}
