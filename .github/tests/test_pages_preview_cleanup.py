"""Tests for deleting a closed pull request's Cloudflare Pages previews.

`.github/actions/delete-pages-previews/delete.sh` issues DELETEs against a
live API, which is the one kind of function that cannot be tested against the
real thing: an honest test would destroy something. So these run it against a
stand-in that speaks the same protocol, records every request, and can be told
to refuse - which is what `API_BASE` exists to be pointed at.

Most of what follows is about what must *not* be deleted. The happy path is
one test; the rest pin down that `pr-28` never selects `pr-281`, that a
production deployment is never in scope, and that a malformed alias stops the
run before a single request goes out. Deletion is the one thing here that
cannot be undone, and a filter one character too loose would pass a test that
only checked the happy path.
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
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ACTION_DIR = REPO_ROOT / ".github" / "actions" / "delete-pages-previews"
SCRIPT = ACTION_DIR / "delete.sh"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "pr-preview.yml"

ACCOUNT = "acct-1234"
PROJECT = "ourhike-preview"
TOKEN = "cf-token-value"


def deployment(name: str, branch: str | None = None, aliases: list[str] | None = None) -> dict:
    """One deployment as the Pages API reports it.

    `branch` is omitted rather than nulled when absent, because that is the
    shape the script has to survive - the alias URLs are the fallback for
    exactly this case.
    """
    metadata = {"branch": branch} if branch is not None else {}
    return {
        "id": name,
        "aliases": aliases if aliases is not None else [],
        "deployment_trigger": {"metadata": metadata},
    }


def preview(number: int, push: str) -> dict:
    """A preview as pr-preview.yml really creates it: `--branch=pr-<n>`."""
    alias = f"pr-{number}"
    return deployment(f"{alias}-{push}", branch=alias, aliases=[f"https://{alias}.{PROJECT}.pages.dev"])


@dataclass
class FakeState:
    deployments: list[dict] = field(default_factory=list)
    undeletable: set[str] = field(default_factory=set)
    list_failure: dict | None = None
    # Cloudflare's own default, whatever it turns out to be, is not published
    # either - so this is a stand-in figure chosen small enough that the
    # paging tests below really page. The script sends no page size, so this
    # is the double's business alone and nothing depends on it being right.
    page_size: int = 25
    delete_calls: list[tuple[str, dict]] = field(default_factory=list)
    list_calls: list[dict] = field(default_factory=list)
    auth_seen: set[str] = field(default_factory=set)


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # noqa: D102 - silence the default stderr spam
        pass

    @property
    def state(self) -> FakeState:
        return self.server.state

    def _json(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        self.state.list_calls.append(query)
        self.state.auth_seen.add(self.headers.get("Authorization", ""))

        if self.state.list_failure is not None:
            self._json(self.state.list_failure)
            return

        # REFUSES `per_page` AT ALL, and that is the point of #1001 rather
        # than an oversight. This stand-in used to honour whatever it was
        # sent, so the suite passed green while the real API rejected every
        # list the script issued and the action deleted nothing for weeks.
        #
        # It does not model the real cap because there is no real cap to
        # model from here: the Pages limits page does not state one, and
        # Cloudflare's OpenAPI schema declares `per_page` as a bare integer
        # with no `maximum`. Refusing the parameter outright is the one
        # faithful thing available - it pins the script to the behaviour that
        # can be verified without a token, which is not sending a page size
        # nobody here can check. Anyone who later wants one has to come
        # through this line, and should arrive with a figure they measured.
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
        parsed = urlparse(self.path)
        query = {key: values[0] for key, values in parse_qs(parsed.query).items()}
        target = parsed.path.rsplit("/", 1)[-1]
        self.state.delete_calls.append((target, query))
        self.state.auth_seen.add(self.headers.get("Authorization", ""))

        if target in self.state.undeletable:
            self._json({"success": False, "errors": [{"message": f"deployment {target} is protected"}], "result": None})
            return

        # Really removed, so that the collection shifts underneath anything
        # that tried to delete while paging through it. That is the bug the
        # script's collect-then-delete order exists to avoid, and a test that
        # left the collection intact could not tell the two apart.
        self.state.deployments = [item for item in self.state.deployments if item["id"] != target]
        self._json({"success": True, "errors": [], "result": None})


@pytest.fixture
def cloudflare():
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
    def __init__(self, completed: subprocess.CompletedProcess[str], outputs: dict[str, str]):
        self.returncode = completed.returncode
        self.output = completed.stdout + completed.stderr
        self.outputs = outputs

    def count(self, name: str) -> int:
        return int(self.outputs[name])


def run(server, tmp_path: Path, alias: str, *, project: str = PROJECT, output_name: str = "out") -> Result:
    step_output = tmp_path / "outputs" / output_name
    step_output.parent.mkdir(parents=True, exist_ok=True)
    step_output.write_text("", encoding="utf-8")
    host, port = server.server_address[0], server.server_address[1]
    env = {
        **os.environ,
        "API_TOKEN": TOKEN,
        "ACCOUNT_ID": ACCOUNT,
        "PROJECT": project,
        "ALIAS": alias,
        "API_BASE": f"http://{host}:{port}",
        "GITHUB_OUTPUT": str(step_output),
        # The sandbox routes outbound HTTPS through a proxy. Without this the
        # loopback stand-in would be reached through it, or not at all.
        "NO_PROXY": "127.0.0.1,localhost",
        "no_proxy": "127.0.0.1,localhost",
    }
    completed = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True)
    outputs = dict(line.split("=", 1) for line in step_output.read_text(encoding="utf-8").splitlines() if "=" in line)
    return Result(completed, outputs)


def remaining(server) -> set[str]:
    return {item["id"] for item in server.state.deployments}


class TestItDeletesTheRightThings:
    def test_it_removes_every_deployment_for_the_alias(self, cloudflare, tmp_path):
        """One per push, not one per pull request - so there are several."""
        cloudflare.state.deployments = [preview(281, "a"), preview(281, "b"), preview(281, "c")]

        result = run(cloudflare, tmp_path, "pr-281")

        assert result.returncode == 0
        assert result.count("found") == 3
        assert result.count("deleted") == 3
        assert result.count("failed") == 0
        assert remaining(cloudflare) == set()

    def test_it_leaves_other_pull_requests_alone(self, cloudflare, tmp_path):
        cloudflare.state.deployments = [preview(281, "a"), preview(282, "a"), preview(300, "a")]

        result = run(cloudflare, tmp_path, "pr-281")

        assert result.count("deleted") == 1
        assert remaining(cloudflare) == {"pr-282-a", "pr-300-a"}

    def test_it_never_touches_the_production_deployment(self, cloudflare, tmp_path):
        """The one deletion that would actually hurt."""
        production = deployment("live", branch="main", aliases=[f"https://{PROJECT}.pages.dev"])
        cloudflare.state.deployments = [production, preview(281, "a")]

        result = run(cloudflare, tmp_path, "pr-281")

        assert result.returncode == 0
        assert remaining(cloudflare) == {"live"}

    def test_a_shorter_alias_does_not_select_a_longer_one(self, cloudflare, tmp_path):
        """`pr-28` must not match `pr-281`, which a prefix comparison would.

        Nothing about this is hypothetical: pull request numbers here are
        already three digits, so every two-digit pull request has several
        longer numbers it is a prefix of.
        """
        cloudflare.state.deployments = [preview(28, "a"), preview(281, "a"), preview(2810, "a")]

        result = run(cloudflare, tmp_path, "pr-28")

        assert result.count("found") == 1
        assert remaining(cloudflare) == {"pr-281-a", "pr-2810-a"}

    def test_it_finds_deployments_by_alias_url_when_the_branch_is_missing(self, cloudflare, tmp_path):
        """Only one of the two markers is guaranteed to be populated."""
        cloudflare.state.deployments = [
            deployment("no-branch", aliases=[f"https://pr-281.{PROJECT}.pages.dev"]),
            deployment("unrelated", aliases=[f"https://pr-99.{PROJECT}.pages.dev"]),
        ]

        result = run(cloudflare, tmp_path, "pr-281")

        assert result.count("deleted") == 1
        assert remaining(cloudflare) == {"unrelated"}

    def test_it_finds_matches_spread_across_pages(self, cloudflare, tmp_path):
        """A project accumulates deployments; the matches are not on page one.

        This is also what would catch a rewrite that deleted while paging:
        the stand-in really removes what it deletes, so anything relying on
        page boundaries staying still would skip whatever shifted into a slot
        it had already passed.
        """
        others = [preview(number, "a") for number in range(400, 640)]
        cloudflare.state.deployments = [*others[:120], preview(281, "a"), *others[120:], preview(281, "b")]

        result = run(cloudflare, tmp_path, "pr-281")

        assert result.count("found") == 2
        assert result.count("deleted") == 2
        assert {"pr-281-a", "pr-281-b"} & remaining(cloudflare) == set()
        assert len(remaining(cloudflare)) == len(others)

    def test_nothing_to_delete_is_not_a_failure(self, cloudflare, tmp_path):
        """A pull request closed without ever deploying, or closed twice."""
        cloudflare.state.deployments = [preview(282, "a")]

        result = run(cloudflare, tmp_path, "pr-281")

        assert result.returncode == 0
        assert result.count("found") == 0
        assert result.count("deleted") == 0
        assert cloudflare.state.delete_calls == []


class TestItRefusesWhatItCannotDoSafely:
    @pytest.mark.parametrize("alias", ["", "main", "pr-", "pr-281-extra", "*", "pr-28*", "../pr-281", "PR-281"])
    def test_a_malformed_alias_stops_before_any_request(self, cloudflare, tmp_path, alias):
        """Checked before listing, not before deleting.

        The alias is the entire filter. If it is not the shape this action
        deletes by, there is no safe request to make with it - including the
        read, which is what would decide the scope.
        """
        cloudflare.state.deployments = [preview(281, "a")]

        result = run(cloudflare, tmp_path, alias, output_name=f"bad-{alias or 'empty'}")

        assert result.returncode == 1
        assert "Refusing to delete anything" in result.output
        assert cloudflare.state.list_calls == []
        assert cloudflare.state.delete_calls == []
        assert remaining(cloudflare) == {"pr-281-a"}

    def test_it_fails_loudly_when_a_deletion_is_refused(self, cloudflare, tmp_path):
        """Half a cleanup reported as a whole one is worse than none.

        The previews are still reachable either way; the difference is whether
        the pull request says so.
        """
        cloudflare.state.deployments = [preview(281, "a"), preview(281, "b")]
        cloudflare.state.undeletable = {"pr-281-b"}

        result = run(cloudflare, tmp_path, "pr-281")

        assert result.returncode == 1
        assert result.count("found") == 2
        assert result.count("deleted") == 1
        assert result.count("failed") == 1
        assert "still reachable" in result.output
        assert remaining(cloudflare) == {"pr-281-b"}

    def test_it_says_what_to_fix_when_the_token_is_refused(self, cloudflare, tmp_path):
        cloudflare.state.list_failure = {
            "success": False,
            "errors": [{"message": "Authentication error"}],
            "result": None,
        }

        result = run(cloudflare, tmp_path, "pr-281")

        assert result.returncode == 1
        assert "Cloudflare Pages: Edit" in result.output
        assert cloudflare.state.delete_calls == []

    def test_the_refusal_says_what_cloudflare_actually_said(self, cloudflare, tmp_path):
        """#1001: the annotation used to name a cause Cloudflare had not given.

        Every refusal was reported as a token-permission problem, so the run
        that finally exposed this said the token needed "Cloudflare Pages:
        Edit" while the body it had just parsed said the list options were
        invalid. Anyone acting on that re-issues a working token. An
        annotation that names the wrong cause is worse than one that names
        none, because it reads as a diagnosis.
        """
        cloudflare.state.list_failure = {
            "success": False,
            "errors": [{"message": "Invalid list options provided. Review the `page` or `per_page` parameter."}],
            "result": None,
        }

        result = run(cloudflare, tmp_path, "pr-281")

        assert result.returncode == 1
        assert "Invalid list options provided" in result.output
        # The token stays on offer as a possibility, not as the answer.
        assert "If that is a permissions problem" in result.output
        assert cloudflare.state.delete_calls == []

    def test_it_reports_counts_even_when_it_fails(self, cloudflare, tmp_path):
        """So the comment on the pull request can say how many are left."""
        cloudflare.state.deployments = [preview(281, "a")]
        cloudflare.state.undeletable = {"pr-281-a"}

        result = run(cloudflare, tmp_path, "pr-281")

        assert result.returncode == 1
        assert result.outputs["found"] == "1"
        assert result.outputs["deleted"] == "0"
        assert result.outputs["failed"] == "1"


class TestTheRequestsItMakes:
    def test_it_authenticates_every_request(self, cloudflare, tmp_path):
        cloudflare.state.deployments = [preview(281, "a")]

        run(cloudflare, tmp_path, "pr-281")

        assert cloudflare.state.auth_seen == {f"Bearer {TOKEN}"}

    def test_it_forces_the_delete(self, cloudflare, tmp_path):
        """The newest deployment is the one holding the alias.

        Without `force` that is precisely the one that survives - leaving the
        live URL serving, which is the whole thing this was meant to stop.
        """
        cloudflare.state.deployments = [preview(281, "a")]

        run(cloudflare, tmp_path, "pr-281")

        assert [query.get("force") for _, query in cloudflare.state.delete_calls] == ["true"]

    def test_it_asks_only_for_preview_deployments(self, cloudflare, tmp_path):
        cloudflare.state.deployments = [preview(281, "a")]

        run(cloudflare, tmp_path, "pr-281")

        assert cloudflare.state.list_calls[0]["env"] == "preview"

    def test_it_asks_for_no_page_size_at_all(self, cloudflare, tmp_path):
        """#1001, stated directly rather than only enforced by the stand-in.

        Asking for 100 got every list refused, and the ceiling that would
        have made some other number safe is published nowhere - not in the
        Pages limits, not in Cloudflare's OpenAPI schema, and not reachable
        by probing, since auth is checked before query parameters. Sending
        none is the only page size that can be justified from here.
        """
        cloudflare.state.deployments = [preview(281, "a")]

        run(cloudflare, tmp_path, "pr-281")

        assert all("per_page" not in query for query in cloudflare.state.list_calls)


class TestTheWorkflowUsesIt:
    """Static checks, so the wiring cannot quietly come undone."""

    @staticmethod
    def _steps() -> list[dict]:
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        return [step for job in workflow["jobs"].values() for step in job["steps"]]

    def test_the_action_and_its_script_are_both_there(self):
        assert (ACTION_DIR / "action.yml").is_file()
        assert SCRIPT.is_file()

    def test_the_manifest_parses_at_all(self):
        """The gap that let #990 run for six days.

        Everything else in this file tests `delete.sh`, hard - the happy
        path, that `pr-28` never selects `pr-281`, that a malformed alias
        stops the run before a request goes out. None of it runs if the
        manifest that invokes the script cannot be loaded, and the only
        assertion about action.yml was that it exists as a file.

        It did exist. It also carried `description: Cloudflare API token with
        "Cloudflare Pages: Edit".` - an unquoted YAML scalar containing a
        colon-space, which is a parse error - so the runner reported "Failed
        to load ... action.yml" and every teardown since 2026-08-19 left its
        preview reachable, built against the real Supabase project. A
        thoroughly tested script behind a manifest nobody parses is a script
        that never runs.
        """
        manifest = yaml.safe_load((ACTION_DIR / "action.yml").read_text(encoding="utf-8"))
        assert manifest["runs"]["using"] == "composite"
        # The three the workflow reads back to decide whether anything
        # outlived its pull request. A rename here goes red rather than
        # silently making that check compare empty strings.
        assert set(manifest["outputs"]) == {"found", "deleted", "failed"}
        assert set(manifest["inputs"]) == {"api-token", "account-id", "project", "alias"}

    def test_the_closed_path_can_resolve_the_local_action_it_runs(self):
        """`uses: ./…` is resolved out of the workspace at step time, so the
        teardown needs a checkout that still happens when the pull request
        closes. The checkout used to skip on `closed`, which failed every
        teardown on the only event that triggers one - while the comment
        below it told the pull request the previews had been removed (#643).
        Every step between that checkout and the teardown must skip on close
        for the same reason in reverse: the close has no build to do."""
        steps = self._steps()
        teardown_at = next(i for i, step in enumerate(steps) if step.get("uses") == "./.github/actions/delete-pages-previews")
        survives_close = [
            step
            for step in steps[:teardown_at]
            if str(step.get("uses", "")).startswith("actions/checkout") and "closed" not in str(step.get("if", ""))
        ]
        assert survives_close, "no checkout on the closed path precedes the local-action teardown"

    def test_closing_a_pull_request_removes_its_previews(self):
        teardown = next(step for step in self._steps() if step.get("uses") == "./.github/actions/delete-pages-previews")
        assert "closed" in teardown["if"]
        # The same step that named the alias for the deploy names it for the
        # deletion, so the two cannot come to disagree about which pull
        # request's previews these are.
        assert teardown["with"]["alias"] == "${{ steps.preview.outputs.alias }}"

    def test_a_failed_teardown_still_posts_the_comment_and_still_fails_the_job(self):
        """Both, because either alone hides it.

        A red check on a closed pull request is not read by anyone, and a
        comment nobody is subscribed to is not either - but together the
        outcome is somewhere it will be seen.
        """
        steps = self._steps()
        teardown = next(step for step in steps if step.get("uses") == "./.github/actions/delete-pages-previews")
        assert teardown.get("continue-on-error") is True

        guard = next(step for step in steps if step.get("name") == "Fail if any preview outlived its pull request")
        assert steps.index(guard) > steps.index(teardown)
        assert "steps.teardown.outputs.failed" in yaml.safe_dump(guard)
        assert "steps.teardown.outcome" in yaml.safe_dump(guard)
