"""Tests for check_supabase_config.py, the live-project diagnostic.

The script itself talks to a real Supabase project, which is exactly why it
cannot be trusted to be correct on the day it is needed - it runs manually,
rarely, and usually when something is already broken. These tests exercise
its judgement without a network.

The first test is the important one: it is what stops the script's copy of
the accepted algorithm list from drifting away from the list the backend
actually enforces, which would turn a passing diagnostic into a lie.
"""

import check_supabase_config as check
from app.core.auth import ASYMMETRIC_ALGORITHMS


def test_the_script_knows_exactly_what_the_backend_accepts():
    # BACKEND_ACCEPTS is duplicated rather than imported so the script stays
    # stdlib-only. That is a reasonable trade only while something guarantees
    # the copy is honest, and this is that something.
    assert set(check.BACKEND_ACCEPTS) == set(ASYMMETRIC_ALGORITHMS) | {"HS256"}


def test_an_algorithm_the_backend_cannot_verify_fails_the_check():
    # The mismatch that shipped: the project signed ES256, the backend
    # verified HS256 only, and every signed-in request would have 401'd.
    report = check.Report()

    check.check_signing_keys({"EdDSA"}, report)

    assert report.failed


def test_the_algorithm_a_hosted_project_uses_passes():
    report = check.Report()

    check.check_signing_keys({"ES256"}, report)

    assert not report.failed


def test_no_published_keys_is_a_warning_rather_than_a_failure():
    # How a self-hosted or legacy project looks. It is a real configuration,
    # not a broken one - the backend verifies its HS256 tokens against the
    # shared secret.
    report = check.Report()

    check.check_signing_keys(set(), report)

    assert not report.failed


def test_a_provider_offered_without_credentials_fails_the_check():
    # The silent broken button. Nothing else in the system compares these two
    # lists, and the client cannot discover the difference at runtime.
    report = check.Report()

    check.check_providers({"external": {"email": True, "google": False}}, "google,email", report)

    assert report.failed


def test_providers_that_are_all_enabled_pass():
    report = check.Report()

    check.check_providers({"external": {"email": True, "google": True}}, "google,email", report)

    assert not report.failed


def test_a_provider_enabled_but_not_offered_is_only_a_warning():
    # Deliberate deferral, not breakage: Apple can be configured in the
    # project long before a build chooses to show its button.
    report = check.Report()

    check.check_providers({"external": {"email": True, "apple": True}}, "email", report)

    assert not report.failed


def test_an_unset_provider_list_is_checked_against_the_clients_default():
    # An unset variable reaches the build as an empty string, and the client
    # falls back to google,email. The check has to make the same assumption or
    # it would pass a build whose real buttons it never looked at.
    report = check.Report()

    check.check_providers({"external": {"email": True, "google": False}}, "", report)

    assert report.failed
