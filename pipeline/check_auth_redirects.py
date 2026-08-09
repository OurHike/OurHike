"""Ask, as a browser would, whether a hiker can still finish signing in.

Tier 3 of #431, tracked in #467. The sibling of `check_deployment.py`, against
a different vendor and the same declaration:
[.github/expected-origins.yml](../.github/expected-origins.yml).

    check_deployment.py     R2's CORS allow-list    can a browser READ the data
    this                    Supabase's redirect     can a browser FINISH a sign-in
                            allow-list

WHY THE SECOND READER IS THE POINT

The origins file exists because two allow-lists have to move together and
prose could not make them. LAUNCH_CHECKLIST.md said so, in words, before #427:
previews moved to `pages.dev`, both lists gained the wildcard, one of them lost
production, and nothing disagreed. A declaration with one reader is still
prose with extra steps - it only becomes a contract when something else has to
satisfy it too.

It earned that on its first run. Production's allow-list and Site URL still
named `jaimito-asuntos-gringuenos.github.io`, the pre-org-migration Pages host,
which by then answered 404 - while hikers were on `ourhike.github.io`. Every
sign-in round trip from production was redirecting to a dead host with the auth
code in the URL. Nothing else in the repository could see it: the app builds,
the map draws, the bucket answers, and only the last hop of an OAuth round trip
is wrong.

HOW IT READS A LIST THE API DOES NOT PUBLISH

#467 expected this to be "declare and diff what we can", because the public API
does not expose the allow-list. It does not - `GET /auth/v1/settings` returns
providers, signup and mailer flags and nothing about redirects. But the list is
observable in BEHAVIOUR, which is better than reading it anyway, for the same
reason tier 1 sends a real `Origin` instead of reading a policy document:

    GET /auth/v1/verify?token=<junk>&type=magiclink&redirect_to=<url>

answers 303. When `<url>` is on the allow-list the `Location` is `<url>` with
an `#error=access_denied&error_code=otp_expired` fragment - the token is junk,
which is the point, and being rejected for the token means the redirect was
accepted. When it is NOT on the list, Supabase silently falls back to the
project's **Site URL**. So one request per origin reads whether that origin is
allowed, and any refused probe reads back the Site URL for nothing.

`/auth/v1/authorize` cannot do this. Measured: it echoes any `redirect_to`,
including `https://evil.example.com/`, and defers validation to the callback.
A check built on it would have passed while production was broken.

Read-only, and it holds no credential beyond the anon key that already ships
inside the client bundle. A junk token verifies as expired; nothing is sent,
nothing is written, no account is touched.

THE NEGATIVE PROBES ARE NOT DECORATION

An allow-list widened to `**` passes every positive assertion here while being
precisely the thing you do not want - anyone who can get a victim to click a
link can have the auth code delivered to a host they control. So this also
asserts that two URLs are REFUSED: an unrelated host, and a lookalike built by
suffixing the real one, which is what catches an allow-list matching on prefix
rather than on origin.

    python check_auth_redirects.py --project production
    python check_auth_redirects.py --print-redirects
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote

import requests

from check_deployment import FAILED, OK, UNREACHABLE, load_manifest

HTTP_TIMEOUT = 30

# Deliberately not a real token, and deliberately readable in a log: whoever
# finds this in Supabase's auth logs should be able to tell at a glance that it
# is a health check rather than someone attacking the verify endpoint.
PROBE_TOKEN = "ourhike-allow-list-probe-not-a-real-token"

# A project whose variables are unset. Distinct from a failure: `ua.yml` uses
# UA's Supabase pair or neither, so an unconfigured UA project means UA signs
# in against production's - a supported fallback (RELEASING.md 3d), not a
# fault. Reporting it as FAILED would make the daily check red for a state the
# repository explicitly permits.
SKIPPED = "skipped"

# `.invalid` can never resolve (RFC 2606), so a probe built on it cannot
# accidentally name somebody's real host.
_UNRELATED_PROBE = "https://not-ourhike.probe.invalid/"


def app_url(origin: dict) -> str:
    """The concrete URL an auth redirect for this origin actually targets.

    `probe` rather than `pattern`, for the reason tier 1 gives: a wildcard is
    not a hostname a browser would ever send, so a rule covering no real
    hostname has to be tested with a real one.
    """
    return f"{origin['probe'].rstrip('/')}{origin['app_path']}"


def project_origins(manifest: dict, project: str) -> list[dict]:
    """The origins this project's allow-list has to accept."""
    return [origin for origin in manifest["origins"] if project in (origin.get("supabase") or [])]


def site_url(manifest: dict, project: str) -> str:
    """The one exact URL the project falls back to when a redirect is refused."""
    declared = manifest["supabase_projects"][project]["site_url_origin"]
    for origin in manifest["origins"]:
        if origin["pattern"] == declared:
            return app_url(origin)
    raise KeyError(f"{project}'s site_url_origin names {declared}, which is not a declared origin")


def redirect_globs(manifest: dict, project: str) -> list[str]:
    """The allow-list to paste into Supabase, generated from the declaration.

    Generated for the reason `--print-cors-policy` is: a stored copy is a
    second home for one fact, and LAUNCH_CHECKLIST.md's hand-kept copy is what
    drifted last time.

    Note these are what to paste, not what the check enforces. The check asks
    whether each app URL is *accepted*, so an existing entry broader than the
    one printed here - `/OurHike/**` where this prints `/OurHike/app/**` -
    satisfies it too, and nobody has to re-paste a working list to make a new
    check go green.
    """
    return sorted(f"{origin['pattern'].rstrip('/')}{origin['app_path']}**" for origin in project_origins(manifest, project))


def site_origin(manifest: dict, project: str) -> str:
    """The concrete ORIGIN of the project's Site URL, with no path."""
    declared = manifest["supabase_projects"][project]["site_url_origin"]
    for origin in manifest["origins"]:
        if origin["pattern"] == declared:
            return origin["probe"].rstrip("/")
    raise KeyError(f"{project}'s site_url_origin names {declared}, which is not a declared origin")


def lookalike_of(origin: str) -> str:
    """A HOSTNAME that starts with a real one but is not it.

    The probe for an allow-list matching on prefix rather than on origin, which
    is the mistake that turns an allow-list into a redirect to an attacker.

    It must be built from the origin and never from the app URL. Suffixing the
    full URL produces a PATH on the real host - `https://ourhike.github.io`
    `/OurHike/app.probe.invalid/` - which a correct `/OurHike/**` entry allows
    and should allow. The first version of this did exactly that and reported
    production as wide open; running it against the real projects is what said
    otherwise. A negative assertion that cries wolf is worse than none, because
    it is the one nobody can safely ignore.
    """
    return f"{origin.rstrip('/')}.probe.invalid/"


def _verify_redirect(base: str, api_key: str, target: str, session: requests.Session | None = None) -> str | None:
    """Where the project sends a browser asking to be returned to `target`.

    `None` when the question could not be asked at all - which is reported as
    UNREACHABLE rather than as a refusal, per #431's rule that a flaky third
    party must not be able to declare an outage.
    """
    getter = (session or requests).get
    url = f"{base}/auth/v1/verify?token={PROBE_TOKEN}&type=magiclink&redirect_to={quote(target, safe='')}"
    try:
        response = getter(url, headers={"apikey": api_key}, timeout=HTTP_TIMEOUT, allow_redirects=False)
    except requests.RequestException:
        return None
    return response.headers.get("Location")


def _landed_at(location: str | None) -> str:
    """The redirect target with the error fragment stripped.

    The fragment is always there on a junk token and always says the same
    thing; the part before `#` is the only half that answers the question.
    """
    return (location or "").split("#", 1)[0]


def check_allowed(base: str, api_key: str, origin: dict, project: str, session=None) -> dict:
    """Is a sign-in from this origin allowed to come back to it?"""
    target = app_url(origin)
    location = _verify_redirect(base, api_key, target, session)
    common = {"check": "redirect", "project": project, "origin": origin["pattern"]}

    if location is None:
        return {**common, "state": UNREACHABLE, "detail": f"could not ask about {target}"}

    if _landed_at(location) == target:
        return {**common, "state": OK, "detail": f"a sign-in returns to {target}"}

    return {
        **common,
        "state": FAILED,
        "detail": (
            f"a sign-in from {target} is sent to {_landed_at(location)!r} instead - the origin is not on "
            f"{project}'s redirect allow-list, so the hiker never arrives back at the app. Add it under "
            "Authentication -> URL Configuration; `check_auth_redirects.py --print-redirects` prints what to paste."
        ),
    }


def check_refused(base: str, api_key: str, target: str, project: str, why: str, session=None) -> dict:
    """Is a host that must NOT be allowed actually refused?

    The assertion that stops "make the check pass" and "make the project safe"
    coming apart: an allow-list of `**` satisfies every check above.
    """
    location = _verify_redirect(base, api_key, target, session)
    common = {"check": "refuses", "project": project, "origin": target}

    if location is None:
        return {**common, "state": UNREACHABLE, "detail": f"could not ask about {target}"}

    if _landed_at(location) != target:
        return {**common, "state": OK, "detail": f"{why} is refused"}

    return {
        **common,
        "state": FAILED,
        "detail": (
            f"{target} is ACCEPTED as a redirect target, which it must never be ({why}). The allow-list is "
            "wider than it looks - check for a `**` or a bare wildcard entry under Authentication -> URL "
            "Configuration. Anyone who can get a hiker to follow a link can have their auth code delivered."
        ),
    }


def check_site_url(base: str, api_key: str, manifest: dict, project: str, session=None) -> dict:
    """Where a REFUSED redirect lands - which is the project's Site URL.

    Worth an assertion of its own precisely because it is the fallback. A
    wrong Site URL turns "this redirect is not allowed" into a silent trip
    somewhere else, and silence is how the pre-migration host survived a
    migration.
    """
    expected = site_url(manifest, project)
    location = _verify_redirect(base, api_key, _UNRELATED_PROBE, session)
    common = {"check": "site-url", "project": project, "origin": expected}

    if location is None:
        return {**common, "state": UNREACHABLE, "detail": "could not ask"}

    landed = _landed_at(location)
    if landed.rstrip("/") == expected.rstrip("/"):
        return {**common, "state": OK, "detail": f"Site URL is {landed}"}

    if landed == _UNRELATED_PROBE:
        # Reported by check_refused as the real finding; saying it twice here
        # would put the same fault in two rows of the tracking issue.
        return {**common, "state": OK, "detail": "not read - the allow-list accepted the probe (see `refuses`)"}

    return {
        **common,
        "state": FAILED,
        "detail": (
            f"Site URL is {landed!r}, not {expected!r}. That is where every refused redirect goes, so a wrong "
            "one sends a hiker somewhere quietly rather than telling anybody."
        ),
    }


def check_project(manifest: dict, project: str, base: str, api_key: str, session=None) -> list[dict]:
    reports = [check_allowed(base, api_key, origin, project, session) for origin in project_origins(manifest, project)]

    reports.append(check_site_url(base, api_key, manifest, project, session))
    reports.append(check_refused(base, api_key, _UNRELATED_PROBE, project, "an unrelated host", session))
    reports.append(
        check_refused(
            base,
            api_key,
            lookalike_of(site_origin(manifest, project)),
            project,
            "a lookalike built by suffixing the real host",
            session,
        )
    )
    return reports


def check_all(manifest: dict, only: str | None = None, env: dict | None = None, session=None) -> list[dict]:
    environ = os.environ if env is None else env
    reports: list[dict] = []

    for project, config in manifest["supabase_projects"].items():
        if only is not None and project != only:
            continue

        base = (environ.get(config["url_var"]) or "").strip().rstrip("/")
        api_key = (environ.get(config["key_var"]) or "").strip()
        if not base or not api_key:
            reports.append(
                {
                    "check": "project",
                    "project": project,
                    "origin": "",
                    "state": SKIPPED,
                    "detail": f"{config['url_var']} and {config['key_var']} are not both set, so this project was not checked.",
                }
            )
            continue

        reports.extend(check_project(manifest, project, base, api_key, session))

    return reports


def verdict_document(reports: list[dict]) -> dict:
    return {
        "checked_at": date.today().isoformat(),
        "checks": reports,
        "failed": [report for report in reports if report["state"] == FAILED],
        "unreachable": [report for report in reports if report["state"] == UNREACHABLE],
        "skipped": [report for report in reports if report["state"] == SKIPPED],
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", metavar="KEY", help="Check only this project from the declaration.")
    parser.add_argument(
        "--origins", metavar="PATH", type=Path, help="Origins manifest. Defaults to .github/expected-origins.yml."
    )
    parser.add_argument("--json", metavar="OUT", type=Path, help="Also write the verdict to OUT as JSON.")
    parser.add_argument(
        "--print-redirects",
        action="store_true",
        help="Print the Site URL and redirect allow-list each project implies, to paste into Supabase. Asks nothing.",
    )
    parser.add_argument("--exit-zero", action="store_true", help="Exit 0 even when something failed.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = load_manifest(args.origins)

    if args.print_redirects:
        for project, config in manifest["supabase_projects"].items():
            if args.project is not None and project != args.project:
                continue
            print(f"# {project} - {config['serves']}")
            print(f"# Authentication -> URL Configuration, in the project reached by {config['url_var']}.")
            print(f"Site URL: {site_url(manifest, project)}")
            print("Redirect URLs:")
            for glob in redirect_globs(manifest, project):
                print(f"  {glob}")
            print()
        return 0

    reports = check_all(manifest, args.project)
    if not reports:
        print(f"No project named {args.project!r} in the declaration.", file=sys.stderr)
        return 2

    for report in reports:
        print(
            f"  {report['state'].upper():12} {report['check']:10} {report['project']:11} {report['origin']:48} {report['detail']}"
        )

    document = verdict_document(reports)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(document, indent=2))

    failed = document["failed"]
    if failed:
        print(f"\n{len(failed)} check(s) failed - a hiker cannot finish signing in from at least one origin.")
    elif document["unreachable"]:
        print(f"\n{len(document['unreachable'])} check(s) could not be made at all - reported, not counted as a refusal.")
    else:
        print("\nEvery declared origin can complete a sign-in, and nothing else can.")

    if args.exit_zero:
        return 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
