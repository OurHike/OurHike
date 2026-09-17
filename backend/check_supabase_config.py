"""Confirm a real Supabase project is configured the way this code assumes.

The companion to pipeline/check_r2_connection.py, and it exists for the same
reason: several things about a deployment can only be wrong at runtime, and
each of them fails as a hiker being unable to sign in rather than as anything
a test suite can see.

Every failure mode below is one that actually happened or was one setting
away from happening while this was being built:

- The repository variables were named `VITE_SUPABASE_URL` rather than
  `SUPABASE_URL`. The build inlined empty strings, the app said it had no
  project, and nothing anywhere named the cause.
- `backend/app/core/auth.py` verified HS256 only. The project issues ES256.
  Every signed-in request would have come back 401 with a perfectly valid
  token - and no test could have caught it, because the tests minted the
  algorithm the code expected.
- `VITE_AUTH_PROVIDERS` can name a provider whose credentials do not exist in
  the dashboard. That is a button which reaches an error page, and nothing
  else in the system compares those two lists.
- The email provider can be enabled with no sender behind it. Supabase's
  built-in mailer sends 2 messages an hour, to the project's own team
  members only, and answers everyone else `Email address not authorized`
  (#397, #1572) - a button that is enabled, offered, and cannot finish.
- The email templates can carry a link where the app asks for a code.
  `screens/EmailSignIn.tsx` asks for the 6 digits `{{ .Token }}` puts in the
  email; a template without it sends a link that opens the browser rather
  than the installed app (#279).

The last two are not in the public settings document. They are in the
project's auth config, which the management API serves to a personal access
token - so this reads them only when `SUPABASE_ACCESS_TOKEN` is set, and says
plainly what it could not check when it is not. A fine-grained token with
`auth_config_read` and nothing else is enough, and is the one to mint.

Read-only either way: it reads the project's public settings, its published
keys and (with the token) its auth config, and writes nothing. Stdlib only,
so running it costs no dependency install.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

# What backend/app/core/auth.py will actually accept. Duplicated here rather
# than imported so this stays a stdlib-only script with nothing to install -
# tests/test_supabase_config_check.py asserts the two lists agree, which is
# what stops the copy drifting into a lie.
BACKEND_ACCEPTS = ("ES256", "RS256", "HS256")

# What client/src/lib/supabase.ts offers when VITE_AUTH_PROVIDERS is blank.
# Duplicated for the same stdlib-only reason as BACKEND_ACCEPTS, and held to
# the client's source by tests/test_supabase_config_check.py - which is what
# this copy needed all along: it said `google,email` for a month after #397
# changed the client to `google`, so an unset variable was checked against
# buttons the build did not have.
CLIENT_DEFAULT_PROVIDERS = ("google",)

# How many digits screens/EmailSignIn.tsx asks for (CODE_LENGTH there).
EMAIL_CODE_LENGTH = 6

# Supabase's own ceiling before its advisor flags the expiry as too long.
EMAIL_CODE_MAX_EXPIRY_SECONDS = 3600

MANAGEMENT_API = "https://api.supabase.com/v1"

# `{{ .Token }}` in a Go template, with whatever spacing the dashboard kept.
TOKEN_PLACEHOLDER = re.compile(r"\{\{\s*\.Token\s*\}\}")

# The templates a code has to be in, and why both: a returning address gets
# "Magic Link" and a new one gets "Confirm sign up", and
# `verifyOtp({ type: 'email' })` accepts either token. One template carrying
# the code and the other a link is a sign-in that works for everyone but a
# new hiker - the worst half to lose.
EMAIL_CODE_TEMPLATES = (
    ("mailer_templates_magic_link_content", "Magic Link"),
    ("mailer_templates_confirmation_content", "Confirm sign up"),
)

TIMEOUT_SECONDS = 15


def _get(url: str, api_key: str) -> tuple[int, dict]:
    request = urllib.request.Request(url, headers={"apikey": api_key})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, {}


def _get_as_owner(url: str, access_token: str) -> tuple[int, dict]:
    """A management API read, which takes a personal access token rather than the anon key."""
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, {}


def project_ref(project_url: str) -> str:
    """`fehctqdwdjwryzgxzywc` out of `https://fehctqdwdjwryzgxzywc.supabase.co`.

    The management API addresses a project by this ref, and the URL is the
    only place the repository variables carry it.
    """
    host = urllib.parse.urlparse(project_url).hostname or ""
    return host.split(".")[0]


def offered_providers(configured: str) -> set[str]:
    """The buttons a build shows, from the AUTH_PROVIDERS variable it was built with.

    Blank means the client's default, not "none": an unset repository variable
    reaches the build as an empty string, and lib/supabase.ts falls back to
    CLIENT_DEFAULT_PROVIDERS for exactly that case.
    """
    offered = {name.strip().lower() for name in configured.split(",") if name.strip()}
    return offered or set(CLIENT_DEFAULT_PROVIDERS)


class Report:
    """Collects findings so every problem is reported in one run.

    Exiting at the first failure would mean fixing one setting, re-running,
    and finding the next - which for something gated behind a dashboard round
    trip is a genuinely slow way to work.
    """

    def __init__(self) -> None:
        self.failed = False

    def ok(self, message: str) -> None:
        print(f"  OK      {message}")

    def warn(self, message: str) -> None:
        print(f"  WARN    {message}")

    def fail(self, message: str) -> None:
        print(f"  FAIL    {message}")
        self.failed = True


def check_providers(settings: dict, configured: str, report: Report) -> None:
    """Compare the providers this build offers with the ones that can work.

    Nothing else compares these. A name in AUTH_PROVIDERS without credentials
    behind it is a button that reaches an error page rather than an account,
    and the app cannot discover the difference at runtime - Supabase's client
    does not expose which providers a project has enabled.
    """
    external = settings.get("external") or {}
    enabled = {name for name, on in external.items() if on}

    offered = offered_providers(configured)
    if not configured.strip():
        report.warn(f"AUTH_PROVIDERS is unset; the client's default of {','.join(CLIENT_DEFAULT_PROVIDERS)} applies.")

    for provider in sorted(offered):
        if provider in enabled:
            report.ok(f"Provider '{provider}' is offered and enabled in the project.")
        else:
            report.fail(
                f"Provider '{provider}' is in AUTH_PROVIDERS but is NOT enabled in the "
                "project - its button would reach an error page. Enable it under "
                "Authentication -> Providers, or drop it from AUTH_PROVIDERS."
            )

    for provider in sorted(enabled - offered - {"phone", "anonymous"}):
        report.warn(f"Provider '{provider}' is enabled in the project but not offered by this build.")


def check_auth_config(config: dict, offered: set[str], report: Report) -> None:
    """The dashboard state the public settings endpoint cannot show.

    `check_providers` can see that email is enabled; it cannot see whether
    anything will deliver the email, or what the email says. Both fail as a
    hiker on the code step of screens/EmailSignIn.tsx waiting for a message -
    one that was refused at the project's own mailer, or one that carries a
    link where they were told to expect six digits. This is the half of the
    check that can only be made with the owner's token, against the same
    settings LAUNCH_CHECKLIST.md 4.3c and 4.3d tell a maintainer to set.
    """
    if "email" in offered:
        host = (config.get("smtp_host") or "").strip()
        if host:
            sender = (config.get("smtp_sender_name") or "").strip() or "no sender name"
            report.ok(f"Email is sent through custom SMTP at {host} ({sender}).")
        else:
            report.fail(
                "Email is offered but the project has no custom SMTP host. Supabase's built-in "
                "mailer sends 2 messages an hour, to the project's own team members only, and "
                "answers everyone else 'Email address not authorized' - so the code step waits for "
                "an email that was refused. Configure a sender under Authentication -> Emails -> "
                "SMTP Settings (LAUNCH_CHECKLIST.md 4.3c)."
            )

        for key, template in EMAIL_CODE_TEMPLATES:
            if TOKEN_PLACEHOLDER.search(config.get(key) or ""):
                report.ok(f"The '{template}' email template carries {{{{ .Token }}}}, the code the app asks for.")
            else:
                report.fail(
                    f"The '{template}' email template has no {{{{ .Token }}}}, so that email carries a "
                    "link and no code - and screens/EmailSignIn.tsx asks for a code. Edit it under "
                    "Authentication -> Emails -> Templates (LAUNCH_CHECKLIST.md 4.3d)."
                )

        length = config.get("mailer_otp_length")
        if isinstance(length, int) and length != EMAIL_CODE_LENGTH:
            report.fail(
                f"Email codes are {length} digits, and screens/EmailSignIn.tsx asks for {EMAIL_CODE_LENGTH} "
                "(CODE_LENGTH). Set the length back under Authentication -> Providers -> Email."
            )

        expiry = config.get("mailer_otp_exp")
        if isinstance(expiry, int):
            if expiry > EMAIL_CODE_MAX_EXPIRY_SECONDS:
                report.warn(
                    f"Email codes stay valid for {expiry} s, longer than the {EMAIL_CODE_MAX_EXPIRY_SECONDS} s "
                    "Supabase's security advisor allows before flagging it."
                )
            else:
                report.ok(f"Email codes stay valid for {expiry} s.")

        rate = config.get("rate_limit_email_sent")
        if isinstance(rate, int):
            report.ok(f"The project sends at most {rate} emails an hour (Authentication -> Rate Limits).")

    for provider in sorted(offered - {"email", "phone", "anonymous"}):
        if not config.get(f"external_{provider}_enabled"):
            # check_providers has already failed this one from the public
            # settings; saying it twice would bury the findings only this
            # function can make.
            continue
        if (config.get(f"external_{provider}_client_id") or "").strip():
            report.ok(f"Provider '{provider}' has a client id, so its round trip can start.")
        else:
            report.fail(
                f"Provider '{provider}' is enabled with no client id, so its button starts a round "
                "trip the provider will refuse. Paste the OAuth client's id and secret under "
                "Authentication -> Providers (LAUNCH_CHECKLIST.md 4.3)."
            )


def check_signing_keys(algorithms: set[str], report: Report) -> None:
    """The check that would have caught the HS256/ES256 mismatch."""
    if not algorithms:
        report.warn(
            "The project publishes no asymmetric signing keys. That is how a self-hosted "
            "or legacy project looks; the backend will verify its HS256 tokens against "
            "SUPABASE_JWT_SECRET, which must then be set in the backend's environment."
        )
        return

    for algorithm in sorted(algorithms):
        if algorithm in BACKEND_ACCEPTS:
            report.ok(f"Tokens are signed with {algorithm}, which the backend accepts.")
        else:
            report.fail(
                f"Tokens are signed with {algorithm}, which backend/app/core/auth.py does "
                "NOT accept - every signed-in request would come back 401 with a valid "
                "token. Add it to ASYMMETRIC_ALGORITHMS there."
            )


def main() -> int:
    url = (os.environ.get("SUPABASE_URL") or "").rstrip("/")
    api_key = os.environ.get("SUPABASE_ANON_KEY") or ""
    configured_providers = os.environ.get("AUTH_PROVIDERS") or ""

    report = Report()

    print("Configuration")
    if not url or not api_key:
        report.fail(
            "SUPABASE_URL and SUPABASE_ANON_KEY must both be set as repository variables. "
            "Note the names carry no VITE_ prefix - the workflows add that when handing "
            "them to the build. See LAUNCH_CHECKLIST.md 4.3a."
        )
        return 1
    report.ok(f"Project URL: {url}")

    if api_key.startswith("eyJ"):
        report.warn(
            "The anon key is a legacy JWT. It works, but Supabase deprecates these at the "
            "end of 2026 - prefer the publishable key (sb_publishable_...)."
        )
    else:
        report.ok("Using a publishable key rather than the legacy anon JWT.")

    print("\nProject reachability")
    status, settings = _get(f"{url}/auth/v1/settings", api_key)
    if status != 200:
        report.fail(f"GET /auth/v1/settings returned {status}. The URL or the key is wrong, or the project is paused.")
        return 1
    report.ok("Auth settings endpoint answered - the URL and key are both valid.")

    print("\nProviders")
    check_providers(settings, configured_providers, report)

    print("\nToken signing")
    status, jwks = _get(f"{url}/auth/v1/.well-known/jwks.json", api_key)
    if status != 200:
        report.warn(f"JWKS endpoint returned {status}; cannot confirm the signing algorithm.")
    else:
        check_signing_keys({key.get("alg") for key in jwks.get("keys", []) if key.get("alg")}, report)

    print("\nThe sender and the templates")
    access_token = os.environ.get("SUPABASE_ACCESS_TOKEN") or ""
    if not access_token:
        print(
            "  Not checked: custom SMTP, {{ .Token }} in the email templates, the code's length and "
            "expiry, and each provider's client id. Those are in the project's auth config, which only "
            "a personal access token can read - set SUPABASE_ACCESS_TOKEN (fine-grained, "
            "auth_config_read and nothing more) to check them. LAUNCH_CHECKLIST.md 4.5."
        )
    else:
        status, config = _get_as_owner(f"{MANAGEMENT_API}/projects/{project_ref(url)}/config/auth", access_token)
        if status != 200:
            report.fail(
                f"GET /v1/projects/{project_ref(url)}/config/auth returned {status}. The token is wrong, "
                "lacks auth_config_read, or belongs to an account that cannot see this project."
            )
        else:
            check_auth_config(config, offered_providers(configured_providers), report)

    # Not checked HERE, but no longer unchecked. The redirect allow-list is
    # not in either document this script reads - the public API does not
    # publish it - but it is observable in behaviour, and
    # pipeline/check_auth_redirects.py asks it that way, daily. It found the
    # allow-list still naming the pre-org-migration Pages host on its first
    # run, which is what stopped this being a manual step.
    print("\nNot checked here: the redirect allow-list - pipeline/check_auth_redirects.py asks it, daily.")

    print("\nFAILED - see above." if report.failed else "\nAll checks passed.")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
