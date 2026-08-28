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
import re

import pytest
import requests

import verify_release
from verify_release import (
    FAILED,
    OK,
    SKIPPED,
    advertised_sizes,
    archive_keys,
    check_all,
    check_client_keys,
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
    withdrawn_tier_keys,
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

# The hiking sheet as hikingDetail.ts declares it: two artifacts per level,
# a DEM shared between two of them, and one level not yet in the bucket.
HIKING_TS = """
export const HIKING_DETAIL_LEVELS: HikingDetail[] = [
  {
    level: 'light',
    artifact: 'at_basemap_package_z12.pmtiles',
    basemapSizeBytes: null,
    demArtifact: 'dem_light.pmtiles',
    demSizeBytes: null,
    recommended: false,
    published: false,
  },
  {
    level: 'standard',
    artifact: 'at_basemap_package_z13.pmtiles',
    basemapSizeBytes: 182_774_166,
    demArtifact: 'dem.pmtiles',
    demSizeBytes: 275_601_483,
    recommended: true,
    published: true,
  },
  {
    level: 'fine',
    artifact: 'at_basemap_package.pmtiles',
    basemapSizeBytes: 533_926_586,
    demArtifact: 'dem.pmtiles',
    demSizeBytes: 275_601_483,
    recommended: false,
    published: true,
  },
]
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


PACKAGES_TS = """
export const USGS_SHEET: BackgroundSheet = {
  id: 'usgs-sheet',
  title: 'USGS sheet',
  summary: 'The official government topo, as an optional second map.',
  packages: [CORRIDOR_BACKGROUND_PACKAGE],
  withdrawn: true,
}
"""

PACKAGES_TS_NOTHING_WITHDRAWN = """
export const USGS_SHEET: BackgroundSheet = {
  id: 'usgs-sheet',
  packages: [CORRIDOR_BACKGROUND_PACKAGE],
}
"""


class TestAWithdrawnSheetIsASkipNotAFailure:
    """#854's part 1, in the shape its 2026-08-20 comment settled: check 2 was
    conflating "the app will request this" with "the app can still resolve
    this for someone who already has it". A withdrawn sheet (#855) is only the
    second, so its absence from a release is a NAMED skip - never OK, which
    would erase the declaration, and never the failure that made every UA run
    un-passable."""

    def test_the_withdrawn_sheets_keys_are_read_from_the_clients_own_source(self):
        assert withdrawn_tier_keys(PACKAGES_TS, CONFIG_TS) == {
            "background_z11.pmtiles",
            "background.pmtiles",
            "background_z13.pmtiles",
        }

    def test_no_withdrawal_means_no_keys(self):
        assert withdrawn_tier_keys(PACKAGES_TS_NOTHING_WITHDRAWN, CONFIG_TS) == set()

    def test_a_withdrawn_sheet_this_check_cannot_map_raises_rather_than_guessing(self):
        withdrawn_other = PACKAGES_TS.replace("CORRIDOR_BACKGROUND_PACKAGE", "SOME_NEW_PACKAGE")
        with pytest.raises(ValueError, match="SOME_NEW_PACKAGE"):
            withdrawn_tier_keys(withdrawn_other, CONFIG_TS)

    def test_a_missing_withdrawn_key_skips_and_names_the_declaration(self):
        manifest = {"artifacts": {key: {"sha256": "x"} for key in ["trails.geojson", "poi_shelter.geojson", "poi_water.geojson"]}}

        reports = {r["key"]: r for r in check_client_keys(manifest, CONFIG_TS, PACKAGES_TS, HIKING_TS)}

        assert reports["background_z13.pmtiles"]["state"] == SKIPPED
        assert "packages.ts" in reports["background_z13.pmtiles"]["detail"]
        assert reports["trails.geojson"]["state"] == OK

    def test_a_missing_key_nobody_withdrew_still_fails_loudly(self):
        manifest = {"artifacts": {"trails.geojson": {"sha256": "x"}}}

        reports = {r["key"]: r for r in check_client_keys(manifest, CONFIG_TS, PACKAGES_TS, HIKING_TS)}

        assert reports["poi_shelter.geojson"]["state"] == FAILED

    def test_a_published_withdrawn_key_is_still_ok(self):
        """Publishing bytes a phone may be carrying is exactly right - the
        withdrawal changes what absence means, not what presence means."""
        manifest = {"artifacts": {key: {"sha256": "x"} for key in expected_client_keys(CONFIG_TS)}}

        reports = {r["key"]: r for r in check_client_keys(manifest, CONFIG_TS, PACKAGES_TS, HIKING_TS)}

        assert reports["background_z13.pmtiles"]["state"] == OK


ACKNOWLEDGEMENTS = [
    {
        "artifact": "poi_water.geojson",
        "from_release": "2026-08-18",
        "max_drop": 0.75,
        "authority": "#749",
        "reason": "The reachability gate reaching production.",
    },
    {
        "artifact": "at_basemap_stretch_*.pmtiles",
        "from_release": "2026-08-18",
        "max_drop": 0.65,
        "authority": "#1118",
        "reason": "The layer strip, on every per-stretch cut.",
    },
]


class TestADeliberateCullCanBeSignedFor:
    """#1143. Check 17's only exemption was an upstream that changed, which a
    pipeline cull is not - so every one of the five failures in the 2026-08-26
    run against production was a shrinkage somebody had decided on purpose,
    the gate stayed red, and the verdict lived nowhere. What keeps this from
    becoming a place checks go to die is that an entry covers exactly one pair
    of releases and carries a ceiling."""

    def _sized(self, requests_mock, previous_bytes, current_bytes):
        requests_mock.head(f"{BASE}/releases/2026-08-18/poi_water.geojson", headers=_headers(length=str(previous_bytes)))
        requests_mock.head(f"{BASE}/releases/2026-08-26/poi_water.geojson", headers=_headers(length=str(current_bytes)))

    def _run(self, previous_id="2026-08-18"):
        manifest = {"artifacts": {"poi_water.geojson": {"sha256": "x"}}}
        return check_release_regression(BASE, previous_id, "2026-08-26", manifest, manifest, acknowledgements=ACKNOWLEDGEMENTS)

    def test_a_signed_cull_passes_and_names_who_signed_for_it(self, requests_mock):
        self._sized(requests_mock, 1_000_000, 350_000)

        (report,) = self._run()

        assert report["state"] == OK
        # Never a silent pass: a reader of the verdict has to be able to find
        # the decision, which is the whole difference between this and raising
        # DROP_THRESHOLD.
        assert "acknowledged_drops.json" in report["detail"]
        assert "#749" in report["detail"]

    def test_a_drop_past_the_ceiling_still_fails_and_says_the_row_exists(self, requests_mock):
        """Acknowledging "water will shrink by about two thirds" must not also
        acknowledge water vanishing."""
        self._sized(requests_mock, 1_000_000, 50_000)

        (report,) = self._run()

        assert report["state"] == FAILED
        assert "does not cover this much" in report["detail"]
        assert "75%" in report["detail"]

    def test_an_acknowledgement_expires_when_a_newer_release_takes_that_place(self, requests_mock):
        """THE SAFETY PROPERTY. An entry names the predecessor its drop was
        measured against, so it cannot silence a second comparison - and
        nobody has to remember to delete it."""
        requests_mock.head(f"{BASE}/releases/2026-08-25/poi_water.geojson", headers=_headers(length="1000000"))
        requests_mock.head(f"{BASE}/releases/2026-08-26/poi_water.geojson", headers=_headers(length="350000"))

        (report,) = self._run(previous_id="2026-08-25")

        assert report["state"] == FAILED

    def test_an_unsigned_artifact_fails_exactly_as_before(self, requests_mock):
        manifest = {"artifacts": {"poi_shelter.geojson": {"sha256": "x"}}}
        requests_mock.head(re.compile(".*"), headers=_headers(length="100000"))
        requests_mock.head(f"{BASE}/releases/2026-08-18/poi_shelter.geojson", headers=_headers(length="1000000"))

        (report,) = check_release_regression(
            BASE, "2026-08-18", "2026-08-26", manifest, manifest, acknowledgements=ACKNOWLEDGEMENTS
        )

        assert report["state"] == FAILED
        assert "acknowledged_drops.json" not in report["detail"]

    def test_a_pattern_covers_one_family_cut_by_one_extract(self):
        assert (
            verify_release.acknowledgement_for("at_basemap_stretch_28.pmtiles", "2026-08-18", ACKNOWLEDGEMENTS)["authority"]
            == "#1118"
        )
        # And does not reach past its own family.
        assert verify_release.acknowledgement_for("at_basemap_package.pmtiles", "2026-08-18", ACKNOWLEDGEMENTS) is None

    def test_a_missing_or_malformed_file_acknowledges_nothing(self, tmp_path):
        """Failing open would turn the gate off by deleting a file."""
        assert verify_release.acknowledged_drops(tmp_path / "absent.json") == []
        broken = tmp_path / "broken.json"
        broken.write_text("{ not json")
        assert verify_release.acknowledged_drops(broken) == []

    def test_the_committed_file_parses_and_every_row_carries_its_evidence(self):
        """The reviewed file itself, held to what its README promises a row
        owes a reader: a row without evidence turns a safety gate off on
        somebody's say-so."""
        rows = verify_release.acknowledged_drops()

        assert rows, "reference/acknowledged_drops.json should hold the live acknowledgements"
        for row in rows:
            assert row["from_release"], row
            assert 0 < row["max_drop"] <= 1, row
            assert row["authority"].startswith("#"), row
            assert row["reason"], row
            assert row["measured"], row


class TestTheSheetHikersActuallyDownload:
    """#1144. Checks 2 and 18 knew only downloadDetail.ts's raster tiers - the
    sheet #855 WITHDREW - so nothing held the hiking sheet's five artifacts or
    their advertised sizes to the bucket, while two comments claimed
    otherwise. These are the app's real downloads."""

    def test_every_level_is_read_out_of_the_clients_own_table(self):
        levels = verify_release.hiking_sheet_levels(HIKING_TS)

        assert [level["level"] for level in levels] == ["light", "standard", "fine"]
        assert levels[1]["artifacts"] == {
            "at_basemap_package_z13.pmtiles": 182_774_166,
            "dem.pmtiles": 275_601_483,
        }
        # An unpublished level carries nulls rather than a projection, which is
        # what hikingDetail.ts's `published` gate means.
        assert levels[0]["published"] is False
        assert levels[0]["artifacts"] == {
            "at_basemap_package_z12.pmtiles": None,
            "dem_light.pmtiles": None,
        }

    def test_a_restructured_table_raises_rather_than_checking_fewer_artifacts(self):
        """The same failure `expected_client_keys` guards: a regex that stopped
        matching would check fewer downloads than the app offers and report a
        clean release."""
        with pytest.raises(ValueError, match="HIKING_DETAIL_LEVELS"):
            verify_release.hiking_sheet_levels("const LEVELS = []")

    def test_a_level_that_lost_a_field_raises_rather_than_reading_its_neighbour(self):
        """Non-greedy matching across a missing field would silently pair one
        level's artifact with the next level's size."""
        broken = HIKING_TS.replace("    demArtifact: 'dem_light.pmtiles',\n", "")
        with pytest.raises(ValueError, match="3 level\\(s\\) declared, 2 fully parsed"):
            verify_release.hiking_sheet_levels(broken)

    def test_an_offered_levels_missing_artifact_is_the_404_on_a_mountain(self):
        manifest = {"artifacts": {key: {"sha256": "x"} for key in expected_client_keys(CONFIG_TS)}}

        reports = {r["key"]: r for r in check_client_keys(manifest, CONFIG_TS, PACKAGES_TS, HIKING_TS)}

        assert reports["dem.pmtiles"]["state"] == FAILED
        assert "404 on a mountain" in reports["dem.pmtiles"]["detail"]

    def test_an_unpublished_levels_absence_is_a_named_skip(self):
        """`offeredHikingDetails()` keeps that level off the picker, so nothing
        requests it - the same weaker claim a withdrawn sheet carries."""
        manifest = {"artifacts": {key: {"sha256": "x"} for key in expected_client_keys(CONFIG_TS)}}

        reports = {r["key"]: r for r in check_client_keys(manifest, CONFIG_TS, PACKAGES_TS, HIKING_TS)}

        assert reports["dem_light.pmtiles"]["state"] == SKIPPED
        assert "published: false" in reports["dem_light.pmtiles"]["detail"]

    def test_a_shared_dem_is_asked_after_once(self):
        """Standard and Fine name the same DEM; asking twice would say one fact
        twice and double-count it in the verdict."""
        manifest = {"artifacts": {key: {"sha256": "x"} for key in expected_client_keys(CONFIG_TS)}}

        reports = check_client_keys(manifest, CONFIG_TS, PACKAGES_TS, HIKING_TS)

        assert [r["key"] for r in reports].count("dem.pmtiles") == 1

    def test_a_present_artifact_reports_ok_and_names_the_level(self):
        manifest = {
            "artifacts": {
                **{key: {"sha256": "x"} for key in expected_client_keys(CONFIG_TS)},
                "dem.pmtiles": {"sha256": "x"},
            }
        }

        reports = {r["key"]: r for r in check_client_keys(manifest, CONFIG_TS, PACKAGES_TS, HIKING_TS)}

        assert reports["dem.pmtiles"]["state"] == OK
        assert "standard" in reports["dem.pmtiles"]["detail"]


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

    def test_a_release_without_the_background_tiers_skips_9_12_and_18_by_name(self, tmp_path, monkeypatch, requests_mock):
        """#854's part 2, the same defect #653 fixed for checks 6 and 11 by
        another route: the tier loop used to `continue` past a missing tier,
        so checks 9, 12 and 18 emitted no report at all - and they exist to
        interrogate exactly the tiers that go absent, which since #855's
        withdrawal is every ordinary release. Nine reports silently not
        existing is the "did not ask" that reads as "asked and was
        satisfied", and --strict cannot escalate a report that is not there."""
        ledger = tmp_path / "poi_identity.json"
        ledger.write_text(json.dumps({"pois": {}}))
        monkeypatch.setattr(verify_release, "IDENTITY_LEDGER_PATH", ledger)
        requests_mock.head(re.compile(".*"), headers=_headers())
        requests_mock.get(re.compile(".*"), status_code=404)
        requests_mock.get(
            f"{BASE}/latest.json",
            json={"artifacts": {"trails.geojson": {"sha256": "x", "size": 1}}},
        )

        reports = check_all(BASE, hash_artifacts=False)

        background = {"background_z11.pmtiles", "background.pmtiles", "background_z13.pmtiles"}
        tier_reports = [r for r in reports if r["check"] in (9, 12, 18) and r["key"] in background]
        assert {r["key"] for r in tier_reports} == background
        assert {r["state"] for r in tier_reports} == {SKIPPED}
        # Three tiers x checks 9 and 12, plus 18 for every tier the client
        # advertises a size for - nine on the real contract.
        assert len(tier_reports) == 9

        # And the same rule for the sheet hikers actually download (#1144):
        # absent from this release, so every one of its artifacts is a NAMED
        # skip on check 18 rather than a report that never existed.
        hiking = {key for level in verify_release.hiking_sheet_levels() for key in level["artifacts"]}
        hiking_reports = [r for r in reports if r["check"] == 18 and r["key"] in hiking]
        assert {r["key"] for r in hiking_reports} == hiking
        assert {r["state"] for r in hiking_reports} == {SKIPPED}


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

        # Two reports now: the live half and the tombstone half (#673,
        # check_retired_poi). The second passes rather than skipping - this
        # fixture has retired nothing and publishes no tombstones, which is
        # the two agreeing, not the check failing to run. A SKIP would fail
        # the gate under --strict on every healthy release.
        assert [r["state"] for r in reports] == [OK, OK]

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

    def test_a_numeric_source_key_is_not_a_disagreement(self, tmp_path, monkeypatch, requests_mock):
        """#847. opentrail's `dbid` is a number, so the ledger keeps
        `source_feature_id` as an int while the published GeoJSON carries a
        string. Compared raw, that reported a mismatch between two values
        that are the same - 174 of 4,158 features in the first release this
        check ever ran against, each printing `1573` against `1573`.

        The check had never executed before then: the gate could not start
        (#845), so this shipped unexercised."""
        from verify_release import check_poi_identity

        self._ledger(tmp_path, monkeypatch, {"opentrail_at:1573": self._row(source="opentrail_at", sfid=1573)})
        self._serve(requests_mock, [self._feature(poi_id="opentrail_at:1573", source="opentrail_at", sfid="1573")])

        reports = check_poi_identity(BASE, self._manifest())

        assert [r["state"] for r in reports] == [OK, OK]

    def test_a_real_rekey_still_fails_when_the_types_match(self, tmp_path, monkeypatch, requests_mock):
        """The other half: normalising types must not stop the check
        catching the drift it exists for."""
        from verify_release import check_poi_identity

        self._ledger(tmp_path, monkeypatch, {"opentrail_at:1573": self._row(source="opentrail_at", sfid=1573)})
        self._serve(requests_mock, [self._feature(poi_id="opentrail_at:1573", source="opentrail_at", sfid="9999")])

        reports = check_poi_identity(BASE, self._manifest())

        assert reports[0]["state"] == FAILED
        assert "9999" in reports[0]["detail"]

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

    # --- The tombstone half (#673) -------------------------------------
    #
    # Check 21's first half holds every LIVE id to a live ledger row. That
    # leaves the design's actual property - "every id ever published resolves
    # to something" - only half checked, because it says nothing about the ids
    # that stopped being live.

    def _serve_tombstones(self, requests_mock, features):
        requests_mock.get(f"{BASE}/retired_poi.geojson", json={"type": "FeatureCollection", "features": features})

    def _with_tombstones(self):
        return {"artifacts": {"poi_shelter.geojson": {"sha256": "a" * 64}, "retired_poi.geojson": {"sha256": "b" * 64}}}

    def _tombstone(self, poi_id="atc_shelters:gone", superseded_by=None, source="atc_shelters"):
        properties = {"id": poi_id, "poi_type": "shelter", "retired": "2027-09-14"}
        if source is not None:
            properties["source"] = source
        if superseded_by:
            properties["superseded_by"] = superseded_by
        return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-74.0, 41.0]}, "properties": properties}

    def test_a_tombstone_with_no_source_fails(self, tmp_path, monkeypatch, requests_mock):
        """The card's whole sentence is built from `source` (#831), and a
        phone can rebuild it from nothing else: the ledger is not published,
        and splitting the id names the source a place came from years ago
        rather than the one it has now (POI_IDENTITY.md section 5's source
        swap). A tombstone without it parses to nothing on the client - which
        is the "renders nothing at all" this artifact exists to end."""
        from verify_release import check_poi_identity

        self._ledger(
            tmp_path,
            monkeypatch,
            {
                "atc_shelters:glob-1": self._row(),
                "atc_shelters:gone": self._row(sfid="gone", retired="2027-09-14"),
            },
        )
        self._serve(requests_mock, [self._feature()])
        self._serve_tombstones(requests_mock, [self._tombstone(source=None)])

        reports = check_poi_identity(BASE, self._with_tombstones())

        assert reports[1]["state"] == FAILED
        assert "no source" in reports[1]["detail"]

    def test_a_kept_tombstone_promise_passes(self, tmp_path, monkeypatch, requests_mock):
        from verify_release import check_poi_identity

        self._ledger(
            tmp_path,
            monkeypatch,
            {
                "atc_shelters:glob-1": self._row(),
                "atc_shelters:gone": self._row(sfid="gone", retired="2027-09-14"),
            },
        )
        self._serve(requests_mock, [self._feature()])
        self._serve_tombstones(requests_mock, [self._tombstone()])

        reports = check_poi_identity(BASE, self._with_tombstones())

        assert [r["state"] for r in reports] == [OK, OK]

    def test_a_retired_row_missing_from_the_tombstones_fails(self, tmp_path, monkeypatch, requests_mock):
        """Tombstones publish forever (lib/poi_identity.retired_rows), so a
        missing one is a card that renders nothing for whoever's photos are
        anchored to it."""
        from verify_release import check_poi_identity

        self._ledger(
            tmp_path,
            monkeypatch,
            {
                "atc_shelters:glob-1": self._row(),
                "atc_shelters:gone": self._row(sfid="gone", retired="2027-09-14"),
            },
        )
        self._serve(requests_mock, [self._feature()])
        self._serve_tombstones(requests_mock, [])

        reports = check_poi_identity(BASE, self._with_tombstones())

        assert reports[1]["state"] == FAILED
        assert "missing from the tombstones" in reports[1]["detail"]

    def test_a_live_row_published_as_a_tombstone_fails(self, tmp_path, monkeypatch, requests_mock):
        """The mirror of test_a_retired_id_published_live_fails: telling a
        hiker a place is gone while the map still draws it."""
        from verify_release import check_poi_identity

        self._ledger(tmp_path, monkeypatch, {"atc_shelters:glob-1": self._row()})
        self._serve(requests_mock, [self._feature()])
        self._serve_tombstones(requests_mock, [self._tombstone(poi_id="atc_shelters:glob-1")])

        reports = check_poi_identity(BASE, self._with_tombstones())

        assert reports[1]["state"] == FAILED
        assert "a LIVE ledger row" in reports[1]["detail"]

    def test_a_superseded_by_that_is_not_live_fails(self, tmp_path, monkeypatch, requests_mock):
        """The edge is what a hiker's photos follow. One pointing at another
        tombstone strands them somewhere the card cannot explain."""
        from verify_release import check_poi_identity

        self._ledger(
            tmp_path,
            monkeypatch,
            {
                "atc_shelters:glob-1": self._row(),
                "atc_shelters:gone": self._row(sfid="gone", retired="2027-09-14"),
            },
        )
        self._serve(requests_mock, [self._feature()])
        self._serve_tombstones(requests_mock, [self._tombstone(superseded_by="atc_shelters:also-gone")])

        reports = check_poi_identity(BASE, self._with_tombstones())

        assert reports[1]["state"] == FAILED
        assert "not a live ledger row" in reports[1]["detail"]

    def test_a_ledger_with_retired_rows_and_no_published_tombstones_fails(self, tmp_path, monkeypatch, requests_mock):
        from verify_release import check_poi_identity

        self._ledger(
            tmp_path,
            monkeypatch,
            {
                "atc_shelters:glob-1": self._row(),
                "atc_shelters:gone": self._row(sfid="gone", retired="2027-09-14"),
            },
        )
        self._serve(requests_mock, [self._feature()])

        reports = check_poi_identity(BASE, self._manifest())

        assert reports[1]["state"] == FAILED
        assert "publishes no tombstones" in reports[1]["detail"]
