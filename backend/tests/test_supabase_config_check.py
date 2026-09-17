"""Tests for check_supabase_config.py, the live-project diagnostic.

The script itself talks to a real Supabase project, which is exactly why it
cannot be trusted to be correct on the day it is needed - it runs manually,
rarely, and usually when something is already broken. These tests exercise
its judgement without a network.

The first test is the important one: it is what stops the script's copy of
the accepted algorithm list from drifting away from the list the backend
actually enforces, which would turn a passing diagnostic into a lie.
"""

import re
from pathlib import Path

import check_supabase_config as check
from app.core.auth import ASYMMETRIC_ALGORITHMS

CLIENT_SUPABASE_TS = Path(__file__).resolve().parents[2] / "client" / "src" / "lib" / "supabase.ts"


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
    # falls back to CLIENT_DEFAULT_PROVIDERS. The check has to make the same
    # assumption or it would pass a build whose real buttons it never looked at.
    report = check.Report()

    check.check_providers({"external": {"email": True, "google": False}}, "", report)

    assert report.failed


def test_CLIENT_DEFAULT_PROVIDERS_matches_the_default_in_lib_supabase_ts():
    # The copy said google,email for a month after #397 changed the client to
    # google, so an unset variable was checked against buttons the build did
    # not have. Read the default out of the client's source, the same way
    # .github/tests/test_privacy_policy.py does, so the two cannot part again.
    source = CLIENT_SUPABASE_TS.read_text(encoding="utf-8")
    match = re.search(r"CONFIGURED_PROVIDERS\.trim\(\) === ''\s*\?\s*'([^']+)'", source)
    assert match is not None, "could not read the default provider set out of client/src/lib/supabase.ts"

    assert set(check.CLIENT_DEFAULT_PROVIDERS) == {name.strip() for name in match.group(1).split(",")}


def test_offered_providers_reads_the_variable_or_falls_back_to_the_clients_default():
    assert check.offered_providers("google, GitHub ,email") == {"google", "github", "email"}
    assert check.offered_providers("") == set(check.CLIENT_DEFAULT_PROVIDERS)
    assert check.offered_providers("  ") == set(check.CLIENT_DEFAULT_PROVIDERS)


def test_project_ref_is_the_first_label_of_the_project_host():
    assert check.project_ref("https://fehctqdwdjwryzgxzywc.supabase.co") == "fehctqdwdjwryzgxzywc"
    assert check.project_ref("https://fehctqdwdjwryzgxzywc.supabase.co/") == "fehctqdwdjwryzgxzywc"


# A project configured the way LAUNCH_CHECKLIST.md 4.3c and 4.3d ask for -
# the fields as GET /v1/projects/{ref}/config/auth names them.
CONFIGURED_AUTH = {
    "smtp_host": "smtp.resend.com",
    "smtp_sender_name": "OurHike",
    "mailer_templates_magic_link_content": "<p>Your OurHike sign-in code is {{ .Token }}</p>",
    "mailer_templates_confirmation_content": "<p>Your OurHike sign-in code is {{ .Token }}</p>",
    "mailer_otp_length": check.EMAIL_CODE_LENGTH,
    "mailer_otp_exp": check.EMAIL_CODE_MAX_EXPIRY_SECONDS,
    "rate_limit_email_sent": 100,
    "external_google_enabled": True,
    "external_google_client_id": "123.apps.googleusercontent.com",
    "external_github_enabled": True,
    "external_github_client_id": "Iv1.0123456789abcdef",
}

ALL_THREE = {"google", "github", "email"}


def test_check_auth_config_passes_a_project_with_a_sender_and_the_code_in_both_templates():
    report = check.Report()

    check.check_auth_config(CONFIGURED_AUTH, ALL_THREE, report)

    assert not report.failed


def test_check_auth_config_fails_email_offered_with_no_smtp_host():
    # The failure #397 named: enabled, offered, and Supabase's built-in mailer
    # refusing every address outside the project's team.
    report = check.Report()

    check.check_auth_config({**CONFIGURED_AUTH, "smtp_host": ""}, ALL_THREE, report)

    assert report.failed


def test_check_auth_config_fails_a_confirmation_template_that_carries_a_link_and_no_code():
    # The template a NEW address receives. A code in Magic Link alone is a
    # sign-in that works for everyone but a new hiker.
    report = check.Report()
    config = {
        **CONFIGURED_AUTH,
        "mailer_templates_confirmation_content": '<a href="{{ .ConfirmationURL }}">Confirm</a>',
    }

    check.check_auth_config(config, ALL_THREE, report)

    assert report.failed


def test_check_auth_config_fails_a_magic_link_template_left_at_supabases_default():
    # The dashboard reports a never-edited template as null, and the default
    # it then sends carries a link.
    report = check.Report()

    check.check_auth_config({**CONFIGURED_AUTH, "mailer_templates_magic_link_content": None}, ALL_THREE, report)

    assert report.failed


def test_TOKEN_PLACEHOLDER_reads_the_token_whatever_spacing_the_dashboard_kept():
    assert check.TOKEN_PLACEHOLDER.search("{{ .Token }}")
    assert check.TOKEN_PLACEHOLDER.search("{{.Token}}")
    assert check.TOKEN_PLACEHOLDER.search("{{  .Token  }}")
    assert not check.TOKEN_PLACEHOLDER.search("{{ .ConfirmationURL }}")


def test_check_auth_config_fails_a_code_length_other_than_EMAIL_CODE_LENGTH():
    # screens/EmailSignIn.tsx asks for six digits; an eight-digit code cannot
    # be typed into it.
    report = check.Report()

    check.check_auth_config({**CONFIGURED_AUTH, "mailer_otp_length": 8}, ALL_THREE, report)

    assert report.failed


def test_check_auth_config_only_warns_on_an_expiry_over_EMAIL_CODE_MAX_EXPIRY_SECONDS():
    report = check.Report()

    check.check_auth_config({**CONFIGURED_AUTH, "mailer_otp_exp": 7200}, ALL_THREE, report)

    assert not report.failed


def test_check_auth_config_fails_a_provider_enabled_with_no_client_id():
    report = check.Report()

    check.check_auth_config({**CONFIGURED_AUTH, "external_github_client_id": ""}, ALL_THREE, report)

    assert report.failed


def test_check_auth_config_leaves_a_provider_that_is_not_enabled_to_check_providers():
    # check_providers has already failed it from the public settings; a second
    # failure here would bury the findings only this function can make.
    report = check.Report()

    check.check_auth_config({**CONFIGURED_AUTH, "external_github_enabled": False}, ALL_THREE, report)

    assert not report.failed


def test_check_auth_config_does_not_demand_a_sender_when_email_is_not_offered():
    # A Google-only build is a working build, whatever the mailer is.
    report = check.Report()

    check.check_auth_config({"external_google_enabled": True, "external_google_client_id": "x"}, {"google"}, report)

    assert not report.failed


def test_EMAIL_CODE_TEMPLATES_are_the_one_a_returning_address_gets_and_the_one_a_new_one_gets():
    assert [key for key, _ in check.EMAIL_CODE_TEMPLATES] == [
        "mailer_templates_magic_link_content",
        "mailer_templates_confirmation_content",
    ]
