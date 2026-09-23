"""The preview's Content-Security-Policy is written where Cloudflare reads it.

WHY A TEST AND NOT A COMMENT. A `_headers` file in the wrong directory is the
one mistake here that leaves no trace. Cloudflare Pages reads `_headers` from
the ROOT of the uploaded directory and nowhere else, so a copy that lands under
`_site/app/` is not a rule at all - it is a static file that nobody requests,
served with a 200, while every response goes out with no policy on it. The
deploy succeeds, the preview works, the reviewer sees the app, and the only
symptom is the absence of something invisible.

That is not a hypothetical. The first version of
#1602 - "The app ships no Content-Security-Policy, so the link gate added in
#1583 is the only thing standing between a bad URL and the WebView" - proposed
exactly that path, `client/public/_headers`, which the assembly step copies
into `_site/app/`. The policy would have shipped, looked right in the diff, and
done nothing.

WHAT THIS DOES NOT CHECK. Whether the app can actually live inside the policy
is a question for a browser on a build with real map data, which is what the
preview deployment is for and why the header goes out report-only. This file
checks only that the policy is written, from one place, where it is read.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
PREVIEW = REPO / ".github" / "workflows" / "pr-preview.yml"
POLICY_MODULE = REPO / "client" / "scripts" / "csp.mjs"
VITE_CONFIG = REPO / "client" / "vite.config.ts"

#: The step that builds the directory wrangler uploads. Named rather than
#: searched for by content, so a rename is a loud failure here instead of a
#: silently skipped test.
ASSEMBLY_STEP = "Assemble the preview"

#: The step that drives the built app with a browser - `vite preview` serves the
#: policy there, so it needs the same hosts the deployment's file names.
CAMERA_STEP = "Photograph the build"


def _jobs() -> dict:
    return yaml.safe_load(PREVIEW.read_text())["jobs"]


def _step(name: str) -> dict:
    for job in _jobs().values():
        for step in job.get("steps", []):
            if step.get("name") == name:
                return step
    pytest.fail(
        f"pr-preview.yml has no step named {name!r}. If it was renamed, rename "
        "the constant at the top of this file too - these tests are the only "
        "thing holding the policy to the root of the upload and to the hosts "
        "the build actually uses."
    )


def _assembly_step() -> dict:
    return _step(ASSEMBLY_STEP)


def test_the_assembly_step_writes_a_headers_file_at_the_root_of_the_upload() -> None:
    """`_site/_headers`, which Pages reads, and not `_site/app/_headers`, which it ignores."""
    run = _assembly_step()["run"]
    assert "> _site/_headers" in run, (
        "The preview assembly no longer writes _site/_headers. Cloudflare Pages "
        "reads the file at the root of the uploaded directory only, so without "
        "it every preview response goes out with no Content-Security-Policy."
    )
    assert "_site/app/_headers" not in run, (
        "_site/app/_headers is not a rule - Pages reads only the root file, and "
        "a copy under app/ is served as a static file instead."
    )


def test_no_headers_file_is_committed_under_client_public() -> None:
    """The shelf that looks right and is not: client/public lands under _site/app/."""
    stray = REPO / "client" / "public" / "_headers"
    assert not stray.exists(), (
        "client/public/_headers is copied into client/dist and then into "
        "_site/app/, where Cloudflare Pages ignores it. The policy belongs at "
        "_site/_headers, written by the assembly step in pr-preview.yml."
    )


def test_the_policy_is_written_by_the_one_module_rather_than_spelled_out_in_yaml() -> None:
    """Two copies of a policy is a policy that is wrong in one of them."""
    run = _assembly_step()["run"]
    assert "client/scripts/csp.mjs --headers" in run, (
        "The assembly step should write _site/_headers with "
        "`node client/scripts/csp.mjs --headers`. vite.config.ts serves the "
        "same module's policy to `vite preview`, which is what the preview "
        "camera drives, so a second copy written in YAML would let the shot "
        "recipes and the deployment disagree about what is allowed."
    )
    # The directives themselves must not appear in the workflow - that is the
    # shape a second copy would take.
    assert "default-src" not in run, (
        "A directive is spelled out in pr-preview.yml. The policy has one home, "
        "client/scripts/csp.mjs, so that the served policy and the rehearsed "
        "one cannot drift apart."
    )


@pytest.mark.parametrize("step_name", [ASSEMBLY_STEP, CAMERA_STEP])
def test_every_step_that_serves_the_policy_is_given_the_hosts_it_names(step_name: str) -> None:
    """A policy written with the variables unset names fewer hosts than the build talks to.

    Both steps read the same two variables and both would fail quietly without
    them, in different directions. The assembly step writes `_site/_headers`, so
    a missing host means the DEPLOYED preview enforces nothing about it. The
    camera step serves the policy through `vite preview`, and there the bundle
    already has the host baked in from build time - so a missing variable at
    serve time makes every legitimate data and sign-in request report as a
    violation. Report-only means the second costs nothing but belief, which is
    the only thing a rehearsal has to spend.
    """
    env = _step(step_name).get("env") or {}
    for variable in ("VITE_DATA_BASE_URL", "VITE_SUPABASE_URL"):
        assert variable in env, (
            f"{variable} is not passed to the {step_name!r} step, so the policy "
            "it serves omits that host. See this test's docstring for which of "
            "the two failures that is."
        )
    # VITE_API_BASE_URL is deliberately absent, matching the build step, and
    # csp.mjs omits the source rather than naming a host nobody owns.
    assert "VITE_API_BASE_URL" not in env, (
        f"pr-preview.yml deliberately does not set VITE_API_BASE_URL for the "
        f"build, so setting it on the {step_name!r} step would make the policy "
        "describe a host the app in this preview was not built to call."
    )


def test_the_preview_server_serves_the_same_policy_as_the_deployment() -> None:
    """The camera in CI must drive the app under the policy the deployment will serve."""
    config = VITE_CONFIG.read_text()
    assert "policyFromEnv" in config and "scripts/csp.mjs" in config, (
        "vite.config.ts no longer serves the policy from client/scripts/csp.mjs. "
        "`vite preview` is what screenshot.mjs spawns for --dist, so this is the "
        "one place in CI where a browser drives the real build under the real "
        "policy - and a violation there is a console message in the job log."
    )
    assert "Content-Security-Policy-Report-Only" in config, (
        "The preview server should serve the policy report-only. An enforced "
        "policy here would turn a wrong directive into a blank screenshot "
        "instead of a line in the log."
    )


def test_the_policy_is_report_only_everywhere_it_is_served() -> None:
    """The preview is a rehearsal; enforcing is #1602 step 3 and the maintainer's call."""
    module = POLICY_MODULE.read_text()
    assert "export const HEADER_NAME = 'Content-Security-Policy-Report-Only'" in module, (
        "csp.mjs no longer exports the report-only header name. Enforcing the "
        "policy is a decision about what a hiker's phone refuses to load, which "
        "#1602 leaves with the maintainer - it is not a tidy-up."
    )
