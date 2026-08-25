"""Tests for the one-off sweep of orphaned Cloudflare Pages previews (#1004).

`scripts/sweep-pages-previews.sh` is the half of the preview cleanup that
reaches backwards. The action in `.github/actions/delete-pages-previews`
only ever looks at the alias of the pull request closing right now, so
everything orphaned while that action could not list anything at all - from
2026-08-19, when it shipped with a manifest that would not parse, to
2026-08-25, when the `per_page` it sent was finally removed - is still
reachable and nothing on the closed path will ever look at it again.

This runs the sweep against stand-ins for all three things it talks to:
Cloudflare's Pages API, GitHub's pull requests, and the preview hostnames
themselves. Against the real ones the only honest test would delete
somebody's live preview, and the third of those is the whole point - #1004
established that Cloudflare accepting a deletion and the URL going quiet are
two different events, so a suite that modelled deletion as "it stops
answering" would assert the thing that turned out to be false.

Most of what follows is about what must NOT be deleted: an open pull
request's preview, a `pr-<n>` GitHub has no pull request for, a deployment
carrying no pull request identity at all, and - the safety this script
deliberately does not own - anything the alias filter in delete.sh would not
select. That filter is not reimplemented here, so `test_it_delegates_the_
filter_to_delete_sh` is checking a real end-to-end pass through it.
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

# One home for "what a Pages deployment looks like on the wire". If Cloudflare
# ever changes that shape, both suites should move together rather than one of
# them going on passing against a record the other no longer produces.
from test_pages_preview_cleanup import PROJECT, deployment, preview

REPO_ROOT = Path(__file__).resolve().parents[2]
SWEEP = REPO_ROOT / "scripts" / "sweep-pages-previews.sh"
DELETE_SCRIPT = REPO_ROOT / ".github" / "actions" / "delete-pages-previews" / "delete.sh"

ACCOUNT = "acct-1234"
TOKEN = "cf-token-value"
GH_TOKEN = "gh-token-value"
REPOSITORY = "OurHike/OurHike"


def pull(number: int, state: str, closed_at: str | None = None) -> dict:
    return {"number": number, "state": state, "closed_at": closed_at}


@dataclass
class FakeState:
    deployments: list[dict] = field(default_factory=list)
    # number -> pull request, or absent for a number GitHub does not have.
    pulls: dict[int, dict] = field(default_factory=dict)
    live_aliases: set[str] = field(default_factory=set)
    # #1004's measured case: Cloudflare answers success and the alias goes on
    # serving. Off by default so the ordinary tests describe the ordinary
    # outcome, and on for the one test that pins what the sweep does about it.
    alias_survives_deletion: bool = False
    undeletable: set[str] = field(default_factory=set)
    # Small enough that the listing really pages. The script sends no page
    # size, so this figure is the double's alone - and the script reports back
    # whatever it was handed, which is the only way anybody here learns what
    # Cloudflare's own default is.
    page_size: int = 4
    list_calls: list[dict] = field(default_factory=list)
    delete_calls: list[str] = field(default_factory=list)
    pull_calls: list[int] = field(default_factory=list)
    preview_calls: list[str] = field(default_factory=list)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D102 - silence the default stderr spam
        pass

    @property
    def state(self) -> FakeState:
        return self.server.state

    def _json(self, payload: dict, code: int = 200) -> None:
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/__preview/"):
            alias = path[len("/__preview/") :].strip("/")
            self.state.preview_calls.append(alias)
            live = alias in self.state.live_aliases
            body = b"<!doctype html><title>a preview</title>" if live else b"not found"
            self.send_response(200 if live else 404)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path.startswith(f"/gh/repos/{REPOSITORY}/pulls/"):
            number = int(path.rsplit("/", 1)[-1])
            self.state.pull_calls.append(number)
            found = self.state.pulls.get(number)
            if found is None:
                self._json({"message": "Not Found"}, code=404)
            else:
                self._json(found)
            return

        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        self.state.list_calls.append(query)
        # Refuses `per_page` exactly as the real API does (#1001), so a
        # regression that starts sending one fails here rather than in
        # production six days later.
        if "per_page" in query:
            self._json(
                {
                    "success": False,
                    "errors": [{"message": "Invalid list options provided. Review the `page` or `per_page` parameter."}],
                    "result": None,
                }
            )
            return
        page = int(query.get("page", "1"))
        start = (page - 1) * self.state.page_size
        self._json(
            {
                "success": True,
                "errors": [],
                "result": self.state.deployments[start : start + self.state.page_size],
            }
        )

    def do_DELETE(self) -> None:
        target = urlparse(self.path).path.rsplit("/", 1)[-1]
        self.state.delete_calls.append(target)

        if target in self.state.undeletable:
            self._json({"success": False, "errors": [{"message": f"deployment {target} is protected"}], "result": None})
            return

        going = [item for item in self.state.deployments if item["id"] == target]
        self.state.deployments = [item for item in self.state.deployments if item["id"] != target]
        if not self.state.alias_survives_deletion:
            for item in going:
                branch = item.get("deployment_trigger", {}).get("metadata", {}).get("branch")
                if branch and not any(
                    other.get("deployment_trigger", {}).get("metadata", {}).get("branch") == branch
                    for other in self.state.deployments
                ):
                    self.state.live_aliases.discard(branch)
        self._json({"success": True, "errors": [], "result": None})


@pytest.fixture
def world():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.state = FakeState()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class Result:
    def __init__(self, completed: subprocess.CompletedProcess[str]):
        self.returncode = completed.returncode
        self.stdout = completed.stdout
        self.output = completed.stdout + completed.stderr


def sweep(server, *args: str, repository: str = REPOSITORY) -> Result:
    host, port = server.server_address[0], server.server_address[1]
    base = f"http://{host}:{port}"
    env = {
        **os.environ,
        "CLOUDFLARE_API_TOKEN": TOKEN,
        "CLOUDFLARE_ACCOUNT_ID": ACCOUNT,
        "CLOUDFLARE_PAGES_PROJECT": PROJECT,
        "GITHUB_TOKEN": GH_TOKEN,
        "GITHUB_REPOSITORY": repository,
        "API_BASE": f"{base}/cf",
        "GITHUB_API_BASE": f"{base}/gh",
        "PREVIEW_URL_TEMPLATE": f"{base}/__preview/%s",
        "DELETE_SCRIPT": str(DELETE_SCRIPT),
        # The sandbox routes outbound HTTPS through a proxy. Without this the
        # loopback stand-in would be reached through it, or not at all.
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    }
    completed = subprocess.run(
        ["bash", str(SWEEP), "--settle-seconds", "0", *args],
        env=env,
        capture_output=True,
        text=True,
    )
    return Result(completed)


def remaining(server) -> set[str]:
    return {item["id"] for item in server.state.deployments}


class TestTheScriptItself:
    def test_it_parses(self):
        subprocess.run(["bash", "-n", str(SWEEP)], check=True)

    def test_help_works_without_any_credentials(self):
        """The person deciding whether to ask for the token reads this first."""
        env = {key: value for key, value in os.environ.items() if not key.startswith(("CLOUDFLARE_", "GITHUB_"))}
        completed = subprocess.run(["bash", str(SWEEP), "--help"], env=env, capture_output=True, text=True)
        assert completed.returncode == 0
        assert "CLOUDFLARE_API_TOKEN" in completed.stdout


class TestWhatItPlans:
    def test_the_plan_alone_deletes_nothing(self, world):
        """The default, because the plan is the part a human has to read."""
        world.state.deployments = [preview(281, "a"), preview(281, "b")]
        world.state.pulls = {281: pull(281, "closed", "2026-08-01T00:00:00Z")}

        result = sweep(world)

        assert result.returncode == 0
        assert world.state.delete_calls == []
        assert remaining(world) == {"pr-281-a", "pr-281-b"}
        assert "Nothing was deleted" in result.output

    def test_an_open_pull_requests_preview_is_never_due(self, world):
        """The one keep that is not a judgement call."""
        world.state.deployments = [preview(281, "a"), preview(282, "a")]
        world.state.pulls = {281: pull(281, "open"), 282: pull(282, "closed", "2026-08-01T00:00:00Z")}

        result = sweep(world, "--delete", "--limit", "all")

        assert result.returncode == 0
        assert remaining(world) == {"pr-281-a"}

    def test_a_number_github_has_no_pull_request_for_is_kept(self, world):
        """Kept and flagged, not swept.

        A `pr-<n>` alias only ever comes from a pull request event, so a
        deployment carrying one GitHub does not recognise is a thing nobody
        here can explain - and "delete what I cannot explain" is the wrong
        direction on the only irreversible step in this script.
        """
        world.state.deployments = [preview(281, "a")]
        world.state.pulls = {}

        result = sweep(world, "--delete", "--limit", "all")

        assert result.returncode == 0
        assert remaining(world) == {"pr-281-a"}
        assert "needs a human" in result.output

    def test_a_deployment_with_no_pull_request_identity_is_listed_and_left(self, world):
        """Including the production deployment, if the project ever has one."""
        world.state.deployments = [
            deployment("live", branch="main", aliases=[f"https://{PROJECT}.pages.dev"]),
            preview(281, "a"),
        ]
        world.state.pulls = {281: pull(281, "closed", "2026-08-01T00:00:00Z")}

        result = sweep(world, "--delete", "--limit", "all")

        assert result.returncode == 0
        assert remaining(world) == {"live"}
        # Named in the output, so leaving it is a decision somebody can see
        # rather than a silence.
        assert "no pr-<n> identity" in result.output
        assert "live" in result.output

    def test_a_recent_closure_can_be_kept_by_asking(self, world):
        """The judgement call #1004 names, made explicitly rather than in a loop.

        The default window is zero: a closed pull request's preview is exactly
        what this exists to remove. Keeping the last few days of them is a
        thing you ask for, and it shows up in the plan when you do.
        """
        world.state.deployments = [preview(281, "a"), preview(282, "a")]
        world.state.pulls = {
            281: pull(281, "closed", "2001-01-01T00:00:00Z"),
            282: pull(282, "closed", "2099-01-01T00:00:00Z"),
        }

        result = sweep(world, "--delete", "--limit", "all", "--keep-closed-within-days", "7")

        assert result.returncode == 0
        assert remaining(world) == {"pr-282-a"}
        assert "inside the 7-day window" in result.output

    def test_only_narrows_the_sweep_to_named_aliases(self, world):
        world.state.deployments = [preview(281, "a"), preview(282, "a"), preview(283, "a")]
        world.state.pulls = {n: pull(n, "closed", "2026-08-01T00:00:00Z") for n in (281, 282, 283)}

        result = sweep(world, "--only", "pr-282", "--delete", "--limit", "all")

        assert result.returncode == 0
        assert remaining(world) == {"pr-281-a", "pr-283-a"}


class TestHowItDeletes:
    def test_delete_on_its_own_stops_at_one_alias(self, world):
        """And says how many it left, because a silent cap reads as "done".

        Deleting is irreversible and the state it is meant to produce - a URL
        that stops answering - has been observed not to follow. A first batch
        of one settles that for a minute's work; a first batch of hundreds
        cannot be taken back if it does not.
        """
        world.state.deployments = [preview(n, "a") for n in (281, 282, 283)]
        world.state.pulls = {n: pull(n, "closed", "2026-08-01T00:00:00Z") for n in (281, 282, 283)}

        result = sweep(world, "--delete")

        assert result.returncode == 0
        assert len(remaining(world)) == 2
        assert "Deleting 1 of 3 due alias(es); 2 left for a later run" in result.output

    def test_limit_all_takes_the_backlog(self, world):
        world.state.deployments = [preview(n, push) for n in (281, 282) for push in "abc"]
        world.state.pulls = {n: pull(n, "closed", "2026-08-01T00:00:00Z") for n in (281, 282)}

        result = sweep(world, "--delete", "--limit", "all")

        assert result.returncode == 0
        assert remaining(world) == set()
        assert len(world.state.delete_calls) == 6

    def test_it_delegates_the_filter_to_delete_sh(self, world):
        """`pr-28` must not select `pr-281`, end to end through the real thing.

        The exact-match rule is not reimplemented in the sweep - it shells out
        to delete.sh once per alias precisely so there is one copy of it. This
        is that copy being exercised through the sweep, on the case that would
        catch a prefix comparison.
        """
        world.state.deployments = [preview(28, "a"), preview(281, "a"), preview(2810, "a")]
        world.state.pulls = {n: pull(n, "closed", "2026-08-01T00:00:00Z") for n in (28, 281, 2810)}

        result = sweep(world, "--delete", "--only", "pr-28", "--limit", "all")

        assert result.returncode == 0
        assert remaining(world) == {"pr-281-a", "pr-2810-a"}

    def test_a_refused_deletion_fails_the_run(self, world):
        world.state.deployments = [preview(281, "a"), preview(281, "b")]
        world.state.pulls = {281: pull(281, "closed", "2026-08-01T00:00:00Z")}
        world.state.undeletable = {"pr-281-b"}

        result = sweep(world, "--delete", "--limit", "all")

        assert result.returncode == 1
        assert "could not be deleted" in result.output
        assert remaining(world) == {"pr-281-b"}

    def test_deleted_but_still_serving_is_a_distinct_failure(self, world):
        """#1004's finding, and the reason the batch is small by default.

        Cloudflare accepted every deletion and the URL kept answering. Exit 2
        rather than 1 because nothing was refused and re-running would not
        help: what is wrong is the assumption, not the request.
        """
        world.state.deployments = [preview(281, "a")]
        world.state.pulls = {281: pull(281, "closed", "2026-08-01T00:00:00Z")}
        world.state.live_aliases = {"pr-281"}
        world.state.alias_survives_deletion = True

        result = sweep(world, "--delete", "--limit", "all")

        assert result.returncode == 2
        assert remaining(world) == set()
        assert "still answering 200" in result.output
        assert "Do not widen this run" in result.output

    def test_an_alias_that_goes_quiet_is_reported_as_done(self, world):
        world.state.deployments = [preview(281, "a")]
        world.state.pulls = {281: pull(281, "closed", "2026-08-01T00:00:00Z")}
        world.state.live_aliases = {"pr-281"}

        result = sweep(world, "--delete", "--limit", "all")

        assert result.returncode == 0
        assert "Every alias in this batch stopped answering" in result.output

    def test_the_plan_is_printed_before_anything_is_deleted(self, world):
        """So a human reading the output can stop it, and so a run that died
        half way still says what it was going to do."""
        world.state.deployments = [preview(281, "a")]
        world.state.pulls = {281: pull(281, "closed", "2026-08-01T00:00:00Z")}

        result = sweep(world, "--delete", "--limit", "all")

        assert result.stdout.index("DECISION") < result.stdout.index("Deleting all")


class TestTheRequestsItMakes:
    def test_it_pages_without_ever_asking_for_a_page_size(self, world):
        """#1001 again: the fault that made the backlog is a regression risk
        in every new caller of this endpoint, not just in delete.sh."""
        world.state.deployments = [preview(n, "a") for n in range(300, 320)]
        world.state.pulls = {n: pull(n, "open") for n in range(300, 320)}

        result = sweep(world)

        assert result.returncode == 0
        assert all("per_page" not in call for call in world.state.list_calls)
        assert len(world.state.list_calls) > 1

    def test_it_reports_the_page_size_cloudflare_chose(self, world):
        """The open question #1001 could not settle without a token, answered
        as a side effect of the first real run rather than guessed at."""
        world.state.page_size = 4
        world.state.deployments = [preview(n, "a") for n in range(300, 310)]
        world.state.pulls = {n: pull(n, "open") for n in range(300, 310)}

        result = sweep(world)

        assert "sent none, was 4" in result.output

    def test_it_probes_the_url_before_and_after_deleting(self, world):
        """Reachability is measured at both ends, never inferred from the API.

        Without the "before" there is nothing to compare the "after" against -
        an alias that was already quiet would look like a success this run had
        produced.
        """
        world.state.deployments = [preview(281, "a")]
        world.state.pulls = {281: pull(281, "closed", "2026-08-01T00:00:00Z")}
        world.state.live_aliases = {"pr-281"}

        sweep(world, "--delete", "--limit", "all")

        assert world.state.preview_calls.count("pr-281") >= 2

    def test_no_probe_skips_the_reachability_column(self, world):
        world.state.deployments = [preview(281, "a")]
        world.state.pulls = {281: pull(281, "open")}

        result = sweep(world, "--no-probe")

        assert world.state.preview_calls == []
        assert "Reachability not probed" in result.output

    def test_it_asks_github_once_per_alias_not_once_per_deployment(self, world):
        """Twelve builds of one pull request is one question about its state."""
        world.state.deployments = [preview(281, push) for push in "abcdefghijkl"]
        world.state.pulls = {281: pull(281, "open")}

        sweep(world)

        assert world.state.pull_calls == [281]
