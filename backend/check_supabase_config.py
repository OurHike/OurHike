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

Read-only: it reads the project's public settings and its published keys, and
writes nothing. Stdlib only, so running it costs no dependency install.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# What backend/app/core/auth.py will actually accept. Duplicated here rather
# than imported so this stays a stdlib-only script with nothing to install -
# tests/test_supabase_config_check.py asserts the two lists agree, which is
# what stops the copy drifting into a lie.
BACKEND_ACCEPTS = ("ES256", "RS256", "HS256")

TIMEOUT_SECONDS = 15


def _get(url: str, api_key: str) -> tuple[int, dict]:
    request = urllib.request.Request(url, headers={"apikey": api_key})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, {}


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

    offered = {name.strip().lower() for name in configured.split(",") if name.strip()}
    if not offered:
        offered = {"google", "email"}
        report.warn("AUTH_PROVIDERS is unset; the client's default of google,email applies.")

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

    # Not checked HERE, but no longer unchecked. The redirect allow-list is
    # not in the settings document this script reads - the public API does not
    # publish it - but it is observable in behaviour, and
    # pipeline/check_auth_redirects.py asks it that way, daily. It found the
    # allow-list still naming the pre-org-migration Pages host on its first
    # run, which is what stopped this being a manual step.
    print("\nNot checked here: the redirect allow-list - pipeline/check_auth_redirects.py asks it, daily.")

    print("\nFAILED - see above." if report.failed else "\nAll checks passed.")
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
