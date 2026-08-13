"""Tests for check_deployment.py.

The centrepiece is `test_the_outage_that_started_this_is_caught`: it stands up
a bucket that behaves exactly the way R2 behaved during #427 - answering
everything perfectly to a caller that sends no `Origin`, and refusing the
production origin - and asserts this check calls it. Every other check in the
repository was green against that bucket for eight days, so a test that only
proved the happy path would be proving the wrong thing.

`requests_mock` throughout rather than a live bucket: this file is about what
the script concludes from a set of responses, and the responses are the input.
Whether the real bucket is configured correctly is what the scheduled workflow
asks, daily, and no test can answer it from a checkout.
"""

from __future__ import annotations

import json

import pytest
import requests

import check_deployment
from check_deployment import (
    FAILED,
    OK,
    UNREACHABLE,
    check_all,
    check_artifact_present,
    check_exposed_headers,
    check_origin_allowed,
    check_preflight,
    check_range_request,
    cors_policy,
    hiker_facing_failures,
    load_manifest,
    verdict_document,
)

BASE = "https://data.example.org"

PRODUCTION = {
    "pattern": "https://ourhike.github.io",
    "probe": "https://ourhike.github.io",
    "serves": "production",
    "hiker_facing": True,
}
PREVIEW = {
    "pattern": "https://*.ourhike-preview.pages.dev",
    "probe": "https://pr-1.ourhike-preview.pages.dev",
    "serves": "previews",
    "hiker_facing": False,
}

MANIFEST = {
    "request_headers": ["range", "if-range"],
    "expose_headers": ["accept-ranges", "content-length", "content-range", "etag"],
    "methods": ["GET", "HEAD"],
    "max_age_seconds": 3600,
    "origins": [PRODUCTION, PREVIEW],
}

# What the bucket sends when it is behaving. Header names spelled the way R2
# spells them, which is not the way the manifest lists them - see the
# case-folding test.
GOOD_CORS = {
    "Access-Control-Allow-Origin": PRODUCTION["probe"],
    "Access-Control-Expose-Headers": "content-length, content-range, etag, accept-ranges",
}

PUBLISHED = {
    "version": "abc",
    "artifacts": {
        "background.pmtiles": {"sha256": "aaa"},
        "trails.geojson": {"sha256": "bbb"},
    },
}


@pytest.fixture
def mock(requests_mock):
    return requests_mock


# ------------------------------------------------------- the declared manifest


def test_the_real_manifest_declares_the_headers_the_client_actually_sends():
    """The drift that made #431 worth building. LAUNCH_CHECKLIST.md's embedded
    copy allowed `if-match` - which nothing in this repository has ever sent -
    and not `if-range`, which every resumed archive download sends.

    A resume is the only thing that sends it, so a policy missing it works
    perfectly until a hiker's 1.18 GB download is interrupted, which is exactly
    when it cannot be debugged.
    """
    manifest = load_manifest()

    assert "if-range" in manifest["request_headers"]
    assert "if-match" not in manifest["request_headers"]


def test_the_real_manifest_declares_production_as_the_hiker_facing_origin():
    """The origin that went missing. If this list ever loses it again, the
    daily check has nothing to notice."""
    manifest = load_manifest()
    hiker_facing = [origin["pattern"] for origin in manifest["origins"] if origin.get("hiker_facing")]

    assert hiker_facing == ["https://ourhike.github.io"]


def test_every_declared_origin_has_a_concrete_probe():
    """A wildcard cannot be sent as an `Origin` - no browser would ever send
    `*.pages.dev` - so every pattern needs a real hostname to test it with, or
    the rule covering pull requests that do not exist yet is never exercised.
    """
    for origin in load_manifest()["origins"]:
        assert "*" not in origin["probe"], origin["pattern"]


def test_the_cors_policy_is_generated_from_the_declaration():
    """One home per item. The policy pasted into Cloudflare and the policy this
    check enforces are the same object, so they cannot drift the way the
    hand-kept copy did."""
    [policy] = cors_policy(MANIFEST)

    assert policy["AllowedOrigins"] == [PRODUCTION["pattern"], PREVIEW["pattern"]]
    assert policy["AllowedHeaders"] == ["range", "if-range"]
    assert policy["ExposeHeaders"] == ["accept-ranges", "content-length", "content-range", "etag"]
    assert policy["AllowedMethods"] == ["GET", "HEAD"]
    assert policy["MaxAgeSeconds"] == 3600


# ------------------------------------------------------------ the origin check


def test_an_allowed_origin_passes(mock):
    mock.get(f"{BASE}/latest.json", headers=GOOD_CORS)

    assert check_origin_allowed(BASE, PRODUCTION)["state"] == OK


def test_a_refused_origin_fails_and_says_what_to_do(mock):
    """#427 in one assertion: the bucket answers 200 with the body intact and
    simply does not say the origin may read it."""
    mock.get(f"{BASE}/latest.json", headers={})

    report = check_origin_allowed(BASE, PRODUCTION)

    assert report["state"] == FAILED
    assert "may not read this bucket" in report["detail"]
    assert "--print-cors-policy" in report["detail"]


def test_an_origin_allowed_for_somebody_else_is_still_a_failure(mock):
    """The precise shape of #427: the policy was not empty, it covered the
    previews and localhost. A check that only asked "is there a CORS header"
    would have passed throughout the outage."""
    mock.get(f"{BASE}/latest.json", headers={"Access-Control-Allow-Origin": PREVIEW["probe"]})

    report = check_origin_allowed(BASE, PRODUCTION)

    assert report["state"] == FAILED
    assert PREVIEW["probe"] in report["detail"]


def test_a_wildcard_answer_is_accepted(mock):
    """`*` is a legal way to allow everyone. Refusing it would be this check
    enforcing a tightening nobody asked for."""
    mock.get(f"{BASE}/latest.json", headers={"Access-Control-Allow-Origin": "*"})

    assert check_origin_allowed(BASE, PRODUCTION)["state"] == OK


def test_a_wildcard_pattern_is_probed_with_a_concrete_hostname(mock):
    """The only way to learn whether the rule covers a pull request that does
    not exist yet."""
    mock.get(f"{BASE}/latest.json", headers={"Access-Control-Allow-Origin": PREVIEW["probe"]})

    report = check_origin_allowed(BASE, PREVIEW)

    assert report["state"] == OK
    assert mock.last_request.headers["Origin"] == "https://pr-1.ourhike-preview.pages.dev"


def test_a_bucket_that_cannot_be_reached_is_not_reported_as_a_refusal(mock):
    """#431: a flaky third party must not be able to declare an outage. "Could
    not ask" and "was told no" are different answers and only one of them is
    about the CORS policy."""
    mock.get(f"{BASE}/latest.json", exc=requests.ConnectionError)

    assert check_origin_allowed(BASE, PRODUCTION)["state"] == UNREACHABLE


# --------------------------------------------------------- the preflight check


def test_a_preflight_allowing_the_resume_headers_passes(mock):
    mock.options(f"{BASE}/latest.json", headers={"Access-Control-Allow-Headers": "range, if-range"})

    report = check_preflight(BASE, PRODUCTION, MANIFEST["request_headers"])

    assert report["state"] == OK
    assert mock.last_request.headers["Access-Control-Request-Headers"] == "range, if-range"


def test_a_policy_missing_if_range_fails_and_explains_what_breaks(mock):
    """The live defect this file found. `range` alone is CORS-safelisted, so a
    FIRST download works against this policy and only a RESUME breaks - which
    is why nothing noticed, and why the message has to say so rather than
    naming a header and leaving the reader to work it out."""
    mock.options(f"{BASE}/latest.json", headers={"Access-Control-Allow-Headers": "range, if-match, content-type"})

    report = check_preflight(BASE, PRODUCTION, MANIFEST["request_headers"])

    assert report["state"] == FAILED
    assert "if-range" in report["detail"]
    assert "RESUME" in report["detail"]


def test_a_preflight_refused_outright_names_the_header_responsible(mock):
    """What the real bucket actually does, measured 2026-08-09 against
    `pub-31203373f21e449194a97b681bc24b91.r2.dev`.

    R2 answers a preflight naming a disallowed header with a bare **403 and no
    CORS headers at all** - not a 200 listing the subset it permits. The first
    version of this check read the empty allow-list off that 403 and reported
    every requested header as refused, which said `range` was disallowed when
    `range` is allowed and only `if-range` is not. An alarm that names the
    wrong header is worse than one that names none.

    So a refusal is re-asked header by header. Here `range` alone is answered
    normally and `if-range` alone is refused, exactly as production behaves.
    """

    def by_header(request, context):
        asked = request.headers.get("Access-Control-Request-Headers", "")
        if "if-range" in asked:
            context.status_code = 403
            return ""
        context.headers["Access-Control-Allow-Headers"] = asked
        return ""

    mock.options(f"{BASE}/latest.json", text=by_header)

    report = check_preflight(BASE, PRODUCTION, MANIFEST["request_headers"])

    assert report["state"] == FAILED
    assert "403" in report["detail"]
    assert "if-range is why" in report["detail"]
    # The header that is genuinely fine must not be blamed.
    assert "range, if-range is why" not in report["detail"]


def test_a_bucket_refusing_every_preflight_blames_every_header(mock):
    """CORS off entirely, or a rule matching no origin. Every header really is
    refused here, so naming them all is the true answer rather than an
    over-broad one."""
    mock.options(f"{BASE}/latest.json", status_code=403)

    report = check_preflight(BASE, PRODUCTION, MANIFEST["request_headers"])

    assert report["state"] == FAILED
    assert "range, if-range is why" in report["detail"]


def test_a_refusal_no_single_header_explains_is_not_blamed_on_one(mock):
    """Each header is fine alone and the combination is still refused - some
    limit on the request rather than on any one name. Naming a header here
    would send somebody to edit a policy that is already correct, so it
    doesn't."""

    def only_combinations_fail(request, context):
        asked = request.headers.get("Access-Control-Request-Headers", "")
        if "," in asked:
            context.status_code = 403
            return ""
        context.headers["Access-Control-Allow-Headers"] = asked
        return ""

    mock.options(f"{BASE}/latest.json", text=only_combinations_fail)

    report = check_preflight(BASE, PRODUCTION, MANIFEST["request_headers"])

    assert report["state"] == FAILED
    assert "no single header explains it" in report["detail"]


def test_allowed_headers_are_compared_case_insensitively(mock):
    """Header names are case-insensitive, so a bucket answering `If-Range` is
    correct and failing it would be this check inventing a rule."""
    mock.options(f"{BASE}/latest.json", headers={"Access-Control-Allow-Headers": "Range, If-Range"})

    assert check_preflight(BASE, PRODUCTION, MANIFEST["request_headers"])["state"] == OK


# ---------------------------------------------------- the exposed-header check


def test_exposed_headers_are_checked_for_readability_not_presence(mock):
    """R2 sent all four of these throughout the outage and a browser still
    could not see them. curl cannot tell the difference; this is the assertion
    that can."""
    mock.get(f"{BASE}/latest.json", headers={"Access-Control-Expose-Headers": "content-length, etag"})

    report = check_exposed_headers(BASE, PRODUCTION, MANIFEST["expose_headers"])

    assert report["state"] == FAILED
    assert "accept-ranges" in report["detail"]
    assert "content-range" in report["detail"]


def test_all_exposed_headers_present_passes(mock):
    mock.get(f"{BASE}/latest.json", headers=GOOD_CORS)

    assert check_exposed_headers(BASE, PRODUCTION, MANIFEST["expose_headers"])["state"] == OK


# -------------------------------------------------------------- the range check


def test_a_honoured_range_passes(mock):
    mock.get(f"{BASE}/background.pmtiles", status_code=206, headers={"Content-Range": "bytes 0-0/1000"})

    assert check_range_request(BASE, "background.pmtiles")["state"] == OK


def test_a_range_answered_with_the_whole_object_fails(mock):
    """A 200 in reply to a Range request means the server ignored it. On a
    1.18 GB archive that is the difference between resuming and starting
    again."""
    mock.get(f"{BASE}/background.pmtiles", status_code=200)

    report = check_range_request(BASE, "background.pmtiles")

    assert report["state"] == FAILED
    assert "cannot resume" in report["detail"]


def test_the_range_check_asks_for_one_byte(mock):
    """It must not download the artifacts. ~1.6 GB of egress a day against a
    rate-limited subdomain, to learn what one byte already said."""
    mock.get(f"{BASE}/background.pmtiles", status_code=206, headers={"Content-Range": "bytes 0-0/1000"})

    check_range_request(BASE, "background.pmtiles")

    assert mock.last_request.headers["Range"] == "bytes=0-0"


# ----------------------------------------------------------- the artifact check


def test_a_present_artifact_passes(mock):
    mock.head(f"{BASE}/trails.geojson", headers={"Content-Length": "12345", "Accept-Ranges": "bytes"})

    report = check_artifact_present(BASE, "trails.geojson")

    assert report["state"] == OK
    assert "12345 bytes" in report["detail"]


def test_a_deleted_artifact_fails(mock):
    """The lifecycle rule, the accidental delete, the permissions change - the
    ways a good release stops being reachable with nobody publishing
    anything."""
    mock.head(f"{BASE}/trails.geojson", status_code=404)

    report = check_artifact_present(BASE, "trails.geojson")

    assert report["state"] == FAILED
    assert "404" in report["detail"]


def test_an_artifact_that_cannot_be_ranged_fails(mock):
    mock.head(f"{BASE}/trails.geojson", headers={"Content-Length": "12345"})

    report = check_artifact_present(BASE, "trails.geojson")

    assert report["state"] == FAILED
    assert "cannot be resumed" in report["detail"]


def test_a_zero_length_artifact_fails(mock):
    """Served, and empty. A 200 is not the same as an answer."""
    mock.head(f"{BASE}/trails.geojson", headers={"Content-Length": "0", "Accept-Ranges": "bytes"})

    assert check_artifact_present(BASE, "trails.geojson")["state"] == FAILED


def test_the_artifact_check_never_downloads_anything(mock):
    """HEAD, not GET. The whole cost argument rests on this."""
    mock.head(f"{BASE}/trails.geojson", headers={"Content-Length": "1", "Accept-Ranges": "bytes"})

    check_artifact_present(BASE, "trails.geojson")

    assert mock.last_request.method == "HEAD"


# ------------------------------------------------------------- the whole battery


def _healthy_bucket(mock, *, allow_origins=True):
    """A bucket behaving correctly, or behaving correctly to everyone except a
    browser - which is the distinction this whole module exists to draw.

    The allow-origin header is ECHOED from the request rather than fixed,
    because that is what S3-compatible storage actually does when a rule
    matches: a wildcard rule answers with the concrete origin that matched it,
    never with the pattern. A fixture returning one hard-coded origin would
    pass the production check and fail every other declared origin, which is a
    bucket nobody has ever run.
    """

    def latest(request, context):
        origin = request.headers.get("Origin")
        if allow_origins and origin:
            context.headers["Access-Control-Allow-Origin"] = origin
        context.headers["Access-Control-Expose-Headers"] = "content-length, content-range, etag, accept-ranges"
        return PUBLISHED

    mock.get(f"{BASE}/latest.json", json=latest)
    mock.options(f"{BASE}/latest.json", headers={"Access-Control-Allow-Headers": "range, if-range"})
    # A healthy bucket also serves each tier at the size the app advertises
    # (#505). Toy lengths here would make `check_advertised_sizes` report a
    # 100% drift on a fixture whose whole job is to be correct.
    from verify_release import advertised_sizes, archive_keys

    tier_sizes = {key: advertised_sizes()[tier] for tier, key in archive_keys().items()}
    for key in PUBLISHED["artifacts"]:
        length = tier_sizes.get(key, 999)
        mock.head(f"{BASE}/{key}", headers={"Content-Length": str(length), "Accept-Ranges": "bytes"})
    mock.get(f"{BASE}/background.pmtiles", status_code=206, headers={"Content-Range": "bytes 0-0/999"})
    return mock


def test_the_outage_that_started_this_is_caught(mock):
    """#427, reproduced rather than argued.

    The bucket answers everything perfectly to a caller that sends no `Origin`:
    `latest.json` parses, every artifact HEADs 200 with a length and
    `Accept-Ranges`, a one-byte range comes back 206 with `Content-Range`. That
    is precisely the bucket every existing check saw, green, for eight days.

    The one thing it does not do is tell a browser on `ourhike.github.io` that
    it may read any of it. This check has to be the one that says so.
    """
    _healthy_bucket(mock, allow_origins=False)

    reports = check_all(BASE, MANIFEST)
    document = verdict_document(BASE, reports, MANIFEST, published=True)

    # Every non-CORS assertion passes, exactly as it did during the outage.
    assert [r for r in reports if r["check"] == "artifact" and r["state"] != OK] == []
    assert [r for r in reports if r["check"] == "range" and r["state"] != OK] == []

    # And the map is still unreachable, which is the answer that matters.
    assert document["hiker_facing_failures"]
    assert any(r["check"] == "origin" and r["origin"] == PRODUCTION["pattern"] for r in document["hiker_facing_failures"])


def test_a_healthy_bucket_reports_nothing(mock):
    _healthy_bucket(mock)

    document = verdict_document(BASE, check_all(BASE, MANIFEST), MANIFEST, published=True)

    assert document["failed"] == []
    assert document["hiker_facing_failures"] == []


def test_every_published_artifact_is_checked(mock):
    _healthy_bucket(mock)

    reports = check_all(BASE, MANIFEST)

    checked = {r["key"] for r in reports if r["check"] == "artifact"}
    assert checked == set(PUBLISHED["artifacts"])


def test_a_bucket_with_nothing_published_checks_cors_and_says_so(mock):
    """The state this repository is in until LAUNCH_CHECKLIST.md 1.6 runs.
    Failing daily until then is how an alarm gets muted, so the absence of a
    publish is reported as an absence rather than as a fault. Since #651 the
    absence has a second witness: no manifest AND no release index."""
    mock.get(f"{BASE}/latest.json", status_code=404)
    mock.get(f"{BASE}/releases/index.json", status_code=404)
    mock.options(f"{BASE}/latest.json", headers={"Access-Control-Allow-Headers": "range, if-range"})

    reports = check_all(BASE, MANIFEST)

    assert not any(r["check"] == "artifact" for r in reports)
    assert any(r["check"] == "origin" for r in reports)
    assert not any(r["check"] == "manifest" for r in reports)


def test_a_missing_manifest_after_a_release_is_the_outage_not_the_calm(mock):
    """#651: delete latest.json from a bucket that has served hikers for
    months, and every check above this one carries on green - a 404 wears
    CORS headers too, and the artifact checks simply never run. The release
    index is the witness that separates that day from a genuinely unpublished
    one: every real release appends to it, and nothing deletes it."""
    mock.get(f"{BASE}/latest.json", status_code=404)
    mock.get(
        f"{BASE}/releases/index.json",
        json={"releases": [{"release": "2026-08-06", "version": "v", "created_at": "2026-08-06T00:00:00+00:00"}]},
    )
    mock.options(f"{BASE}/latest.json", headers={"Access-Control-Allow-Headers": "range, if-range"})

    reports = check_all(BASE, MANIFEST)

    [gone] = [r for r in reports if r["check"] == "manifest"]
    assert gone["state"] == FAILED
    assert "has published" in gone["detail"]
    # And it stops a hiker - the pointer every client fetches first is gone -
    # so the tracking issue opens rather than the run reporting a healthy day.
    assert gone in hiker_facing_failures(reports, MANIFEST)


def test_an_unreadable_release_index_reads_as_the_calm_absence(mock):
    """No evidence is not evidence of an outage: a 404 or an error on the
    index leaves the missing manifest reported exactly as before #651 - as an
    absence, not a fault - so pre-launch days stay quiet."""
    mock.get(f"{BASE}/latest.json", status_code=404)
    mock.get(f"{BASE}/releases/index.json", status_code=404)
    mock.options(f"{BASE}/latest.json", headers={"Access-Control-Allow-Headers": "range, if-range"})

    assert not any(r["check"] == "manifest" for r in check_all(BASE, MANIFEST))


def test_a_preview_only_failure_is_not_a_hiker_facing_one(mock):
    """#431's discipline: fail on "a browser cannot get the map", never on "a
    tile host was slow". A preview losing CORS costs a reviewer a preview."""
    reports = [
        {"check": "origin", "origin": PREVIEW["pattern"], "state": FAILED, "detail": "nope"},
        {"check": "origin", "origin": PRODUCTION["pattern"], "state": OK, "detail": "fine"},
    ]

    assert hiker_facing_failures(reports, MANIFEST) == []


def test_an_artifact_failure_is_always_hiker_facing():
    """There is no such thing as an artifact only a developer downloads."""
    reports = [{"check": "artifact", "key": "trails.geojson", "state": FAILED, "detail": "404"}]

    assert len(hiker_facing_failures(reports, MANIFEST)) == 1


def test_the_verdict_is_json_serialisable(mock):
    """The workflow reads this back with JSON.parse, and the status page will
    too."""
    _healthy_bucket(mock)

    document = verdict_document(BASE, check_all(BASE, MANIFEST), MANIFEST, published=True)

    assert json.loads(json.dumps(document))["base"] == BASE


# ------------------------------------------------------------------ the CLI


def test_print_cors_policy_asks_nothing_and_prints_the_policy(capsys):
    """Runnable on a laptop with no network, because its whole job is to
    produce something to paste into a dashboard."""
    assert check_deployment.main(["--print-cors-policy"]) == 0

    [policy] = json.loads(capsys.readouterr().out)
    assert "if-range" in policy["AllowedHeaders"]


def test_no_base_is_reported_as_nothing_to_check_rather_than_a_failure(capsys, monkeypatch):
    monkeypatch.delenv("DATA_BASE_URL", raising=False)

    assert check_deployment.main([]) == 2


def test_exit_zero_reports_without_failing(mock, monkeypatch, tmp_path):
    """The reporter posture the sibling check-upstream-freshness.yml already
    keeps: the tracking issue is the signal, not a red X that arrives daily
    and teaches people to ignore it."""
    _healthy_bucket(mock, allow_origins=False)
    monkeypatch.setenv("DATA_BASE_URL", BASE)
    out = tmp_path / "deployment.json"

    assert check_deployment.main(["--exit-zero", "--json", str(out)]) == 0

    assert json.loads(out.read_text())["hiker_facing_failures"]


def test_without_exit_zero_a_failure_is_a_failure(mock, monkeypatch):
    _healthy_bucket(mock, allow_origins=False)
    monkeypatch.setenv("DATA_BASE_URL", BASE)

    assert check_deployment.main([]) == 1


def test_a_trailing_slash_on_the_base_does_not_double_up(mock, monkeypatch):
    """`DATA_BASE_URL` is pasted by hand into a settings page, so it arrives
    both ways. config.ts strips it for the same reason."""
    _healthy_bucket(mock)
    monkeypatch.setenv("DATA_BASE_URL", f"{BASE}/")

    assert check_deployment.main([]) == 0
    assert all("//latest.json" not in request.url for request in mock.request_history)


class TestTheAdvertisedSizesAreCheckedDaily:
    """#505: the app advertised 300.3 MB while the bucket served 315.1 MB, and
    nothing compared the two. `verify_release.py` asks this at release time;
    asking it here is the difference between noticing in a day and noticing at
    the next release."""

    def _bucket(self, requests_mock, sizes):
        for key, length in sizes.items():
            requests_mock.head(f"{BASE}/{key}", headers={"Content-Length": str(length)})

    def test_a_tier_that_has_drifted_is_caught(self, requests_mock):
        from verify_release import advertised_sizes, archive_keys

        keys = archive_keys()
        sizes = advertised_sizes()
        # Standard 5% larger than advertised - the direction that strands a
        # hiker who freed up exactly enough space.
        self._bucket(
            requests_mock,
            {key: int(sizes[tier] * (1.05 if tier == "standard" else 1.0)) for tier, key in keys.items()},
        )

        reports = check_deployment.check_advertised_sizes(BASE, list(keys.values()))
        by_key = {report["key"]: report["state"] for report in reports}

        assert by_key[keys["standard"]] == FAILED
        assert by_key[keys["light"]] == OK

    def test_tiers_the_bucket_does_not_hold_are_not_invented(self, requests_mock):
        """A release that has not published the archives yet must not report
        three failures about objects nobody claimed exist."""
        assert check_deployment.check_advertised_sizes(BASE, []) == []
