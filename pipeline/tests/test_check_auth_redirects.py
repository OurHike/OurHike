"""Tests for check_auth_redirects.py.

Two of these are the ones that matter, and both are regressions of faults this
check has already had or already found:

- `test_the_migration_that_broke_sign_in_is_caught` stands up a project
  behaving exactly as production did on 2026-08-09 - allow-list and Site URL
  still naming the pre-migration Pages host - and asserts this calls it. That
  fault was live, and no other check in the repository could see it.
- `test_a_wide_open_allow_list_is_caught` stands up a project that accepts
  every redirect. It passes every positive assertion in the file, which is the
  whole reason the negative ones exist.

`requests_mock` throughout, for the reason test_check_deployment.py gives: this
file is about what the script concludes from a set of responses. Whether the
real projects are configured correctly is what the scheduled workflow asks.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from check_auth_redirects import (
    FAILED,
    OK,
    SKIPPED,
    UNREACHABLE,
    app_url,
    check_all,
    lookalike_of,
    project_origins,
    redirect_globs,
    site_origin,
    site_url,
    verdict_document,
)

PROD_BASE = "https://project.supabase.co"
UA_BASE = "https://ua-project.supabase.co"

PAGES = {
    "pattern": "https://ourhike.github.io",
    "probe": "https://ourhike.github.io",
    "app_path": "/OurHike/app/",
    "supabase": ["production"],
    "hiker_facing": True,
}
PREVIEW = {
    "pattern": "https://*.ourhike-preview.pages.dev",
    "probe": "https://pr-1.ourhike-preview.pages.dev",
    "app_path": "/",
    "supabase": ["production"],
    "hiker_facing": False,
}
UA = {
    "pattern": "https://ua.ourhike-preview.pages.dev",
    "probe": "https://ua.ourhike-preview.pages.dev",
    "app_path": "/",
    "supabase": ["ua"],
    "cors": False,
    "hiker_facing": False,
}

MANIFEST = {
    "supabase_projects": {
        "production": {
            "url_var": "SUPABASE_URL",
            "key_var": "SUPABASE_ANON_KEY",
            "site_url_origin": "https://ourhike.github.io",
            "serves": "hikers",
        },
        "ua": {
            "url_var": "UA_SUPABASE_URL",
            "key_var": "UA_SUPABASE_ANON_KEY",
            "site_url_origin": "https://ua.ourhike-preview.pages.dev",
            "serves": "testers",
        },
    },
    "origins": [PAGES, PREVIEW, UA],
}

ENV = {
    "SUPABASE_URL": PROD_BASE,
    "SUPABASE_ANON_KEY": "anon-key",
    "UA_SUPABASE_URL": UA_BASE,
    "UA_SUPABASE_ANON_KEY": "ua-anon-key",
}

ERROR_FRAGMENT = "#error=access_denied&error_code=otp_expired"


def fake_project(requests_mock, base, *, allowed, site, status=303):
    """A Supabase project that honours `allowed` and falls back to `site`.

    The real behaviour, not an approximation of it: a junk token always fails,
    and the only thing that varies is WHERE the failure is delivered - the
    requested URL when the redirect was accepted, the Site URL when it was not.
    """

    def respond(request, context):
        target = parse_qs(urlparse(request.url).query).get("redirect_to", [""])[0]
        context.status_code = status
        landing = target if any(target.startswith(prefix) for prefix in allowed) else site
        context.headers["Location"] = f"{landing}{ERROR_FRAGMENT}"
        return ""

    requests_mock.get(f"{base}/auth/v1/verify", text=respond)


PROD_ALLOWED = [
    "https://ourhike.github.io/OurHike/",
    "https://pr-1.ourhike-preview.pages.dev/",
]
PROD_SITE = "https://ourhike.github.io/OurHike/app/"
UA_ALLOWED = ["https://ua.ourhike-preview.pages.dev/"]
UA_SITE = "https://ua.ourhike-preview.pages.dev/"


def states(reports, check=None, project=None):
    return {
        report["state"]
        for report in reports
        if (check is None or report["check"] == check) and (project is None or report["project"] == project)
    }


class TestTheDeclarationItself:
    def test_an_origin_belongs_only_to_the_projects_that_name_it(self):
        # The whole reason this is a mapping rather than one list: UA must not
        # inherit the preview wildcard, because previews sign in against
        # production and would otherwise reach the UA user pool.
        assert [origin["pattern"] for origin in project_origins(MANIFEST, "ua")] == [UA["pattern"]]
        assert PREVIEW["pattern"] in [origin["pattern"] for origin in project_origins(MANIFEST, "production")]

    def test_the_app_url_carries_the_path_the_app_is_served_at(self):
        # A redirect to the bare origin lands on the landing page with the code
        # in its URL and nothing there to read it.
        assert app_url(PAGES) == "https://ourhike.github.io/OurHike/app/"

    def test_a_wildcard_is_probed_with_a_concrete_hostname(self):
        # `*` is not a hostname a browser would ever send, so a rule covering
        # no real hostname covers nothing. Same call tier 1 makes.
        assert app_url(PREVIEW) == "https://pr-1.ourhike-preview.pages.dev/"

    def test_the_printed_allow_list_is_generated_per_project(self):
        assert redirect_globs(MANIFEST, "ua") == ["https://ua.ourhike-preview.pages.dev/**"]
        assert "https://ourhike.github.io/OurHike/app/**" in redirect_globs(MANIFEST, "production")

    def test_the_site_url_is_an_origin_plus_its_app_path(self):
        assert site_url(MANIFEST, "production") == PROD_SITE

    def test_a_site_url_naming_an_undeclared_origin_is_an_error_not_a_guess(self):
        broken = {**MANIFEST, "supabase_projects": {"production": {"site_url_origin": "https://nowhere.example"}}}
        with pytest.raises(KeyError):
            site_url(broken, "production")


class TestTheLookalikeProbe:
    def test_it_suffixes_the_host_and_not_the_path(self):
        # The bug the first version of this file shipped with, caught by
        # running it against the real projects rather than by a test.
        # Suffixing the app URL produces a PATH on the real host, which a
        # correct `/OurHike/**` entry allows and should allow - so the check
        # reported production as wide open when it was not.
        assert lookalike_of(site_origin(MANIFEST, "production")) == "https://ourhike.github.io.probe.invalid/"
        assert "/OurHike/app.probe.invalid" not in lookalike_of(site_origin(MANIFEST, "production"))

    def test_it_cannot_name_a_real_host(self):
        # `.invalid` is reserved by RFC 2606, so this can never resolve to
        # somebody's actual server.
        assert lookalike_of(site_origin(MANIFEST, "ua")).split("/")[2].endswith(".invalid")


class TestAHealthyProject:
    def test_every_declared_origin_passes(self, requests_mock):
        fake_project(requests_mock, PROD_BASE, allowed=PROD_ALLOWED, site=PROD_SITE)
        fake_project(requests_mock, UA_BASE, allowed=UA_ALLOWED, site=UA_SITE)

        reports = check_all(MANIFEST, env=ENV)

        assert states(reports) == {OK}
        assert verdict_document(reports)["failed"] == []

    def test_a_broader_existing_entry_still_passes(self, requests_mock):
        # Production really is configured with `/OurHike/**` while this file
        # prints `/OurHike/app/**`. The check asserts the app URL is ACCEPTED,
        # not that the glob text matches, so nobody has to re-paste a working
        # allow-list to make a new check go green.
        broader = ["https://ourhike.github.io/OurHike/", "https://pr-1.ourhike-preview.pages.dev/"]
        fake_project(requests_mock, PROD_BASE, allowed=broader, site=PROD_SITE)

        reports = check_all(MANIFEST, only="production", env=ENV)

        assert states(reports, check="redirect") == {OK}


class TestTheFaultsThisExistsFor:
    def test_the_migration_that_broke_sign_in_is_caught(self, requests_mock):
        # Production on 2026-08-09, exactly: the allow-list and the Site URL
        # both still naming the pre-org-migration Pages host, which by then
        # answered 404, while hikers were on ourhike.github.io. Every sign-in
        # was redirecting to a dead host with the auth code in the URL.
        old_host = "https://jaimito-asuntos-gringuenos.github.io/OurHike/app/"
        fake_project(
            requests_mock,
            PROD_BASE,
            allowed=["https://jaimito-asuntos-gringuenos.github.io/OurHike/", "http://localhost:5173/"],
            site=old_host,
        )
        fake_project(requests_mock, UA_BASE, allowed=UA_ALLOWED, site=UA_SITE)

        reports = check_all(MANIFEST, only="production", env=ENV)
        failed = verdict_document(reports)["failed"]

        assert states(reports, check="redirect") == {FAILED}
        assert states(reports, check="site-url") == {FAILED}
        # The message has to name where the hiker actually ends up, because
        # that is the only clue the fault leaves anywhere.
        assert any(old_host in report["detail"] for report in failed)

    def test_a_wide_open_allow_list_is_caught(self, requests_mock):
        # Accepts everything. Passes every POSITIVE assertion in this file,
        # which is the entire argument for the negative ones: an allow-list of
        # `**` means anyone who can get a hiker to follow a link can have the
        # auth code delivered to a host they control.
        fake_project(requests_mock, PROD_BASE, allowed=[""], site=PROD_SITE)
        fake_project(requests_mock, UA_BASE, allowed=UA_ALLOWED, site=UA_SITE)

        reports = check_all(MANIFEST, only="production", env=ENV)

        assert states(reports, check="redirect") == {OK}
        assert states(reports, check="refuses") == {FAILED}

    def test_the_site_url_is_not_reported_twice_when_the_list_is_wide_open(self, requests_mock):
        # A project accepting everything also "accepts" the Site URL probe, so
        # the fallback cannot be read. That is the `refuses` finding, already
        # reported - repeating it as a bogus Site URL would put one fault in
        # two rows of the tracking issue and point the second at a fiction.
        fake_project(requests_mock, PROD_BASE, allowed=[""], site=PROD_SITE)

        assert states(check_all(MANIFEST, only="production", env=ENV), check="site-url") == {OK}

    def test_a_lookalike_host_is_refused_separately_from_an_unrelated_one(self, requests_mock):
        # An allow-list matching on prefix rather than on origin accepts
        # `ourhike.github.io.attacker.example` while refusing everything
        # unrelated, so one negative probe would not find it.
        fake_project(
            requests_mock,
            PROD_BASE,
            allowed=["https://ourhike.github.io"],  # prefix match, no trailing boundary
            site=PROD_SITE,
        )

        reports = [r for r in check_all(MANIFEST, only="production", env=ENV) if r["check"] == "refuses"]
        by_target = {report["origin"]: report["state"] for report in reports}

        assert by_target["https://not-ourhike.probe.invalid/"] == OK
        assert by_target["https://ourhike.github.io.probe.invalid/"] == FAILED

    def test_a_glob_widened_to_the_shared_parent_domain_is_caught(self, requests_mock):
        """#659: a paste one token too wide - `https://*.pages.dev/**` -
        accepts every Pages site anyone can register. The unrelated-host
        probe shares no suffix with anything declared and the Site-URL
        lookalike appends to the real host, so both stayed green against
        exactly this state; the per-origin sibling probe is what sees it."""

        def widened(request, context):
            target = parse_qs(urlparse(request.url).query).get("redirect_to", [""])[0]
            host = urlparse(target).netloc
            accepted = host.endswith(".pages.dev") or target.startswith("https://ourhike.github.io/OurHike/")
            context.status_code = 303
            context.headers["Location"] = f"{target if accepted else PROD_SITE}{ERROR_FRAGMENT}"
            return ""

        requests_mock.get(f"{PROD_BASE}/auth/v1/verify", text=widened)

        reports = [r for r in check_all(MANIFEST, only="production", env=ENV) if r["check"] == "refuses"]
        by_target = {report["origin"]: report["state"] for report in reports}

        assert by_target["https://not-ourhike.probe.invalid/"] == OK, "the widened glob is invisible to this probe"
        assert by_target["https://ourhike.github.io.probe.invalid/"] == OK, "and to this one"
        assert by_target["https://ourhike-allowlist-probe-not-ours.ourhike-preview.pages.dev/"] == FAILED

    def test_sibling_probes_are_deduplicated_across_origins_sharing_a_parent(self, requests_mock):
        fake_project(requests_mock, PROD_BASE, allowed=PROD_ALLOWED, site=PROD_SITE)

        reports = [r for r in check_all(MANIFEST, only="production", env=ENV) if r["check"] == "refuses"]
        targets = [report["origin"] for report in reports]

        assert len(targets) == len(set(targets)), "one refusal answers for every origin sharing that parent"


class TestWhatMustNotBeCalledAFailure:
    def test_an_unconfigured_project_is_skipped_rather_than_failed(self):
        # ua.yml uses UA's Supabase pair or neither: unset means UA signs in
        # against production's project, which RELEASING.md 3d permits. Calling
        # that red would make the daily check cry wolf over a supported state.
        reports = check_all(MANIFEST, only="ua", env={k: v for k, v in ENV.items() if not k.startswith("UA_")})

        assert states(reports) == {SKIPPED}
        assert verdict_document(reports)["failed"] == []

    def test_a_project_that_cannot_be_reached_is_not_a_refusal(self, requests_mock):
        # #431's rule, and tier 1 holds the same line: a flaky third party must
        # not be able to declare an outage. Unreachable is reported and does
        # not open the tracking issue.
        import requests as _requests

        requests_mock.get(f"{PROD_BASE}/auth/v1/verify", exc=_requests.ConnectionError)

        reports = check_all(MANIFEST, only="production", env=ENV)

        assert states(reports) == {UNREACHABLE}
        assert verdict_document(reports)["failed"] == []

    def test_the_probe_token_is_junk_and_says_so(self, requests_mock):
        # It lands in the project's auth logs. Whoever reads them should be
        # able to tell at a glance that this is a health check and not somebody
        # attacking the verify endpoint.
        seen = {}

        def respond(request, context):
            query = parse_qs(urlparse(request.url).query)
            seen["token"] = query.get("token", [""])[0]
            seen["type"] = query.get("type", [""])[0]
            context.status_code = 303
            context.headers["Location"] = f"{PROD_SITE}{ERROR_FRAGMENT}"
            return ""

        requests_mock.get(f"{PROD_BASE}/auth/v1/verify", text=respond)
        check_all(MANIFEST, only="production", env=ENV)

        assert "probe" in seen["token"]
        assert "not-a-real-token" in seen["token"]
        assert seen["type"] == "magiclink"
