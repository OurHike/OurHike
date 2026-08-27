"""Tests for how the production site gets published, and for what deploys it.

`.github/actions/publish-to-pages/publish.sh` replaces the whole `gh-pages`
branch with a built directory, and does it with a push that can lose a race and
recover. `pages.yml` is its only caller: pull request previews moved to
Cloudflare Pages (`pr-preview.yml`) precisely so that this branch would have one
writer instead of one per open pull request.

The contention tests still matter with a single writer, because "single" is a
statement about the normal case rather than a guarantee - `workflow_dispatch`
and a merge can overlap, and a cancelled run is not stopped mid-push. They pass
by outcome rather than by timing: nothing waits a fixed time for something to
settle, and nothing asserts an attempt count that the interleaving is free to
change. Where a deterministic answer about the retry machinery is wanted
(`TestRetryMechanics`), contention is manufactured with a `pre-receive` hook
that declines a set number of pushes, so "it retried three times and then
succeeded" is a fact rather than a race that happened to go that way.

`TestTheDeployWorkflows` is the static half, and each assertion there stands
for something that was wrong before: a publisher that pushes once, a preview
system that queued every pull request behind the same git ref, or a
concurrency group that looks like queueing and is not.
"""

from __future__ import annotations

import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ACTION_DIR = REPO_ROOT / ".github" / "actions" / "publish-to-pages"
SCRIPT = ACTION_DIR / "publish.sh"
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"


def _bare_remote(tmp_path: Path, name: str = "remote.git") -> Path:
    remote = tmp_path / name
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    return remote


def _source(tmp_path: Path, name: str, files: dict[str, str]) -> Path:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return root


class Result:
    def __init__(self, completed: subprocess.CompletedProcess[str], outputs: dict[str, str]):
        self.returncode = completed.returncode
        self.output = completed.stdout + completed.stderr
        self.outputs = outputs

    @property
    def pushed(self) -> bool:
        return self.outputs.get("pushed") == "true"

    @property
    def attempts(self) -> int:
        return int(self.outputs["attempts"])


def publish(
    tmp_path: Path,
    remote: Path,
    *,
    source_dir: Path | str,
    message: str = "deploy",
    max_attempts: int = 20,
    backoff_base: int = 0,
    backoff_cap: int = 0,
    branch: str = "gh-pages",
    output_name: str = "step-output",
) -> Result:
    """Run publish.sh the way the composite action runs it."""
    # In a directory of their own: these share tmp_path with the source trees,
    # and a step-output file named after the thing it describes is one careless
    # choice away from colliding with that thing's directory.
    step_output = tmp_path / "step-outputs" / output_name
    step_output.parent.mkdir(parents=True, exist_ok=True)
    step_output.write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "SOURCE_DIR": str(source_dir),
        "BRANCH": branch,
        "COMMIT_MESSAGE": message,
        "REMOTE_URL": str(remote),
        "MAX_ATTEMPTS": str(max_attempts),
        "BACKOFF_BASE_SECONDS": str(backoff_base),
        "BACKOFF_CAP_SECONDS": str(backoff_cap),
        "GITHUB_OUTPUT": str(step_output),
    }
    completed = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, cwd=tmp_path)
    outputs = dict(line.split("=", 1) for line in step_output.read_text(encoding="utf-8").splitlines() if "=" in line)
    return Result(completed, outputs)


def tree(remote: Path, branch: str = "gh-pages") -> set[str]:
    """Every path on the branch, or an empty set if the branch is not there."""
    listing = subprocess.run(
        ["git", "--git-dir", str(remote), "ls-tree", "-r", "--name-only", branch],
        capture_output=True,
        text=True,
    )
    if listing.returncode != 0:
        return set()
    return set(listing.stdout.split())


def read_blob(remote: Path, path: str, branch: str = "gh-pages") -> str:
    return subprocess.run(
        ["git", "--git-dir", str(remote), "show", f"{branch}:{path}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def commit_count(remote: Path, branch: str = "gh-pages") -> int:
    return int(
        subprocess.run(
            ["git", "--git-dir", str(remote), "rev-list", "--count", branch],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )


def decline_pushes(remote: Path, count: int) -> None:
    """Make the remote reject the next `count` pushes, then accept.

    A `pre-receive` hook declining a push is reported by git as
    `[remote rejected]`, the same shape as losing a race to another writer - so
    this manufactures contention that arrives on schedule instead of when the
    scheduler feels like it.
    """
    hook = remote / "hooks" / "pre-receive"
    counter = remote / "declines"
    counter.write_text("0", encoding="utf-8")
    hook.write_text(
        "#!/usr/bin/env bash\n"
        f'seen=$(cat "{counter}")\n'
        f'echo $((seen + 1)) > "{counter}"\n'
        f'if [ "$seen" -lt "{count}" ]; then\n'
        '  echo "declined on purpose" >&2\n'
        "  exit 1\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
    )
    hook.chmod(0o755)


class TestPublishing:
    def test_it_creates_the_branch_when_there_is_not_one(self, tmp_path):
        remote = _bare_remote(tmp_path)
        source = _source(tmp_path, "site", {"index.html": "hello"})

        result = publish(tmp_path, remote, source_dir=source)

        assert result.returncode == 0
        assert result.pushed
        assert tree(remote) == {"index.html"}

    def test_it_publishes_nested_files_and_dotfiles(self, tmp_path):
        """`.nojekyll` is one of these, and Pages behaves differently without it."""
        remote = _bare_remote(tmp_path)
        source = _source(
            tmp_path,
            "site",
            {"index.html": "hello", "app/assets/app.js": "console.log(1)", ".nojekyll": ""},
        )

        publish(tmp_path, remote, source_dir=source)

        assert tree(remote) == {"index.html", "app/assets/app.js", ".nojekyll"}

    def test_republishing_the_same_build_pushes_nothing(self, tmp_path):
        """A rebuild producing byte-identical output is ordinary.

        A re-run, a retried job, a merge that changed only the backend - none
        of them needs a commit saying nothing changed, and the cheapest push is
        the one that never happens.
        """
        remote = _bare_remote(tmp_path)
        source = _source(tmp_path, "site", {"index.html": "hello"})

        first = publish(tmp_path, remote, source_dir=source)
        before = commit_count(remote)
        second = publish(tmp_path, remote, source_dir=source, output_name="second")

        assert first.pushed
        assert not second.pushed
        assert second.returncode == 0
        assert commit_count(remote) == before

    def test_a_changed_build_replaces_the_branch_wholesale(self, tmp_path):
        """Including deleting what the new build stopped emitting.

        A leftover from an older deploy is how a site ends up serving a mix of
        two builds, and how the previews that used to live on this branch would
        otherwise linger after moving to Cloudflare.
        """
        remote = _bare_remote(tmp_path)
        first = _source(tmp_path, "one", {"index.html": "v1", "pr-preview/pr-3/index.html": "stale"})
        publish(tmp_path, remote, source_dir=first)

        second = _source(tmp_path, "two", {"index.html": "v2"})
        publish(tmp_path, remote, source_dir=second, output_name="second")

        assert tree(remote) == {"index.html"}
        assert read_blob(remote, "index.html") == "v2"

    def test_a_missing_source_directory_is_refused(self, tmp_path):
        remote = _bare_remote(tmp_path)
        source = _source(tmp_path, "site", {"index.html": "hello"})
        publish(tmp_path, remote, source_dir=source)

        result = publish(tmp_path, remote, source_dir=tmp_path / "never-built", output_name="missing")

        assert result.returncode == 1
        assert "does not exist" in result.output
        assert tree(remote) == {"index.html"}

    def test_an_empty_source_directory_is_refused(self, tmp_path):
        """Publishing nothing would replace the whole branch with nothing.

        A build step that failed in a way that still produced a directory would
        otherwise take the site down, which is not an outcome a silent failure
        should be able to reach.
        """
        remote = _bare_remote(tmp_path)
        source = _source(tmp_path, "site", {"index.html": "hello"})
        publish(tmp_path, remote, source_dir=source)

        empty = tmp_path / "empty"
        empty.mkdir()
        result = publish(tmp_path, remote, source_dir=empty, output_name="empty")

        assert result.returncode == 1
        assert "empty" in result.output
        assert tree(remote) == {"index.html"}


class TestRetryMechanics:
    def test_it_retries_a_rejected_push_until_it_lands(self, tmp_path):
        remote = _bare_remote(tmp_path)
        decline_pushes(remote, 3)
        source = _source(tmp_path, "site", {"index.html": "hello"})

        result = publish(tmp_path, remote, source_dir=source, max_attempts=10)

        assert result.returncode == 0
        assert result.pushed
        assert result.attempts == 4
        assert tree(remote) == {"index.html"}

    def test_it_gives_up_with_a_clear_message_rather_than_hanging(self, tmp_path):
        remote = _bare_remote(tmp_path)
        decline_pushes(remote, 99)
        source = _source(tmp_path, "site", {"index.html": "hello"})

        result = publish(tmp_path, remote, source_dir=source, max_attempts=3)

        assert result.returncode == 1
        assert result.attempts == 3
        assert "after 3 attempts" in result.output
        assert "max-attempts" in result.output

    def test_an_error_that_is_not_contention_fails_immediately(self, tmp_path):
        """A bad token does not improve on the nineteenth attempt.

        Retrying it only buries the message that would have explained it.
        """
        source = _source(tmp_path, "site", {"index.html": "hello"})

        result = publish(
            tmp_path,
            tmp_path / "not-a-repository.git",
            source_dir=source,
            max_attempts=20,
        )

        assert result.returncode == 1
        assert result.attempts == 1
        assert "not contention" in result.output

    def test_the_backoff_ceiling_doubles_and_then_stops(self, tmp_path):
        """Full jitter, so what is bounded is the ceiling, not the sample.

        Asserting a delay equals anything would be asserting the value of a
        random draw. What the implementation promises is that each wait is
        drawn from [0, ceiling] and that the ceiling doubles per attempt until
        it caps - checkable without pinning randomness.
        """
        remote = _bare_remote(tmp_path)
        decline_pushes(remote, 4)
        source = _source(tmp_path, "site", {"index.html": "hello"})

        result = publish(
            tmp_path,
            remote,
            source_dir=source,
            max_attempts=10,
            backoff_base=1,
            backoff_cap=2,
        )

        assert result.returncode == 0
        delays = [int(match) for match in re.findall(r"retrying in (\d+)s", result.output)]
        # base 1, cap 2: ceilings are 1, 2, 2, 2 for the four declined pushes.
        assert len(delays) == 4
        for delay, ceiling in zip(delays, [1, 2, 2, 2], strict=True):
            assert 0 <= delay <= ceiling


class TestUnderContention:
    @pytest.mark.parametrize("run", range(3))
    def test_concurrent_publishers_all_land_and_one_of_them_wins_cleanly(self, tmp_path, run):
        """Repeated, because a concurrency test that passed once proves little.

        Two things are asserted, and they are different claims. That every
        publisher exits 0 is the one the retry loop exists for - a push that
        lost a race must not fail the deploy. That the branch ends up matching
        exactly one publisher's directory is the one the rebuild-from-tip
        design exists for: a publisher that had merged its work into whatever
        it found would leave a tree that was nobody's build, which is a worse
        outcome than failing and much harder to notice.
        """
        remote = _bare_remote(tmp_path)
        sources = {
            number: _source(
                tmp_path,
                f"site-{number}",
                {"index.html": f"build {number}", f"marker-{number}.txt": "x"},
            )
            for number in range(1, 9)
        }

        def deploy(number: int) -> Result:
            return publish(
                tmp_path,
                remote,
                source_dir=sources[number],
                message=f"build {number}",
                output_name=f"out-{run}-{number}",
            )

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(deploy, sources))

        assert [result.returncode for result in results] == [0] * 8

        published = tree(remote)
        expected = {number: {"index.html", f"marker-{number}.txt"} for number in sources}
        assert published in expected.values(), f"the branch is nobody's build: {sorted(published)}"
        winner = next(number for number, files in expected.items() if files == published)
        assert read_blob(remote, "index.html") == f"build {winner}"


class TestTheDeployWorkflows:
    """Static checks, so the reasoning above cannot be undone by an edit."""

    @staticmethod
    def _workflow(name: str) -> dict:
        return yaml.safe_load((WORKFLOW_DIR / name).read_text(encoding="utf-8"))

    @staticmethod
    def _steps(workflow: dict) -> list[dict]:
        return [step for job in workflow["jobs"].values() for step in job["steps"]]

    def test_the_action_and_its_script_are_both_there(self):
        assert (ACTION_DIR / "action.yml").is_file()
        assert SCRIPT.is_file()

    def test_the_site_deploy_goes_through_the_action(self):
        uses = [step.get("uses", "") for step in self._steps(self._workflow("pages.yml"))]
        assert "./.github/actions/publish-to-pages" in uses

    def test_the_site_deploy_no_longer_uses_a_publisher_that_pushes_once(self):
        """peaceiris/actions-gh-pages pushes once and fails on a rejection.

        Back in this workflow it would reintroduce that quietly - the deploy
        stays green until the day two pushes overlap.
        """
        uses = " ".join(step.get("uses", "") for step in self._steps(self._workflow("pages.yml")))
        assert "peaceiris/actions-gh-pages" not in uses

    def test_the_default_attempt_limit_leaves_room_for_an_overlap(self):
        action = yaml.safe_load((ACTION_DIR / "action.yml").read_text(encoding="utf-8"))
        assert int(action["inputs"]["max-attempts"]["default"]) >= 15

    def test_previews_deploy_to_cloudflare_and_not_to_the_pages_branch(self):
        """The whole point of the move.

        A preview publishing to `gh-pages` again would put every open pull
        request back in a queue behind the same git ref, which is the failure
        this change exists to remove.
        """
        workflow = self._workflow("pr-preview.yml")
        uses = " ".join(step.get("uses", "") for step in self._steps(workflow))
        assert "cloudflare/wrangler-action" in uses
        assert "rossjrw/pr-preview-action" not in uses
        assert "./.github/actions/publish-to-pages" not in uses
        # The parsed jobs rather than the file, because the header comment
        # explains the move and so says "gh-pages" for entirely good reasons.
        # Parsing drops comments, which leaves only configuration that acts.
        assert "gh-pages" not in yaml.safe_dump(workflow["jobs"])

    def test_a_preview_cannot_write_to_the_repository(self):
        """It uploads to Cloudflare now, so it has no reason to hold write.

        The old workflow needed `contents: write` to push the preview onto a
        branch. Leaving that behind after the push went away would be handing
        out a permission nothing in the job uses.
        """
        assert self._workflow("pr-preview.yml")["permissions"]["contents"] == "read"

    def test_previews_are_not_queued_behind_one_shared_group(self):
        """The trap this change is most likely to be "simplified" into.

        GitHub keeps one pending run per concurrency group and cancels the
        rest, so a group shared across pull requests does not take turns - it
        discards. The group has to vary per pull request.
        """
        group = self._workflow("pr-preview.yml")["concurrency"]["group"]
        assert "github.event.number" in group

    def test_a_preview_is_built_for_the_root_of_its_own_hostname(self):
        """A base path that disagrees with the serving path is a blank screen.

        A Cloudflare preview is served from `https://pr-<n>.<project>.pages.dev`
        with the app at its root, so the old `/OurHike/pr-preview/pr-<n>/` base
        would be wrong in a way that builds and deploys perfectly well.
        """
        build = next(step for step in self._steps(self._workflow("pr-preview.yml")) if step.get("name") == "Build the app")
        assert build["env"]["VITE_BASE_PATH"] == "/"

    def test_the_advertised_preview_url_is_the_one_deployed_to(self):
        """Both come from the same step, so they cannot drift apart.

        A comment linking somewhere the upload did not go is a reviewer looking
        at someone else's change, or at a 404, and believing either.
        """
        steps = self._steps(self._workflow("pr-preview.yml"))
        deploy = next(step for step in steps if "wrangler-action" in step.get("uses", ""))
        comment = next(
            step
            for step in steps
            if "sticky-pull-request-comment" in step.get("uses", "") and step.get("if", "").strip().endswith("!= 'closed'")
        )
        assert "steps.preview.outputs.alias" in deploy["with"]["command"]
        # The alias URL the deploy reported, preferred over the one this
        # workflow works out for itself. Both should name the same host, but
        # only one of them is evidence rather than inference - and a comment
        # linking somewhere the upload did not go is a reviewer looking at a
        # 404, or at someone else's change, and believing it.
        assert "steps.deploy.outputs.pages-deployment-alias-url" in comment["with"]["message"]


class TestTheCustomDomainAndTheBuildAgree:
    """Three files decide where the production app is, and all three must say it.

    `site/CNAME` moves the GitHub Pages site onto `ourhike.org`, `pages.yml`
    builds the bundle for the path it will be served at, and
    `.github/expected-origins.yml` is what the R2 CORS allow-list and both
    Supabase redirect lists are pasted from. #733 moved all three together.

    Any one of them moving alone is a failure that deploys perfectly well.
    A base path that disagrees with the serving path is a blank screen; an
    origin declaration that disagrees with either is #427 again - the eight
    days the deployed app drew a topo sheet with no Appalachian Trail on it,
    because an allow-list did not move when the origin did.

    These are string comparisons rather than live requests on purpose. The
    live half already exists and runs daily against the real services
    (`pipeline/check_deployment.py`, `pipeline/check_auth_redirects.py`); what
    it cannot do is fail in a pull request, before the mismatch is deployed.
    """

    CNAME = REPO_ROOT / "site" / "CNAME"
    ORIGINS = REPO_ROOT / ".github" / "expected-origins.yml"

    @classmethod
    def _host(cls) -> str:
        return cls.CNAME.read_text(encoding="utf-8").strip()

    @classmethod
    def _origins(cls) -> dict:
        return yaml.safe_load(cls.ORIGINS.read_text(encoding="utf-8"))

    @classmethod
    def _base_path(cls) -> str:
        workflow = yaml.safe_load((WORKFLOW_DIR / "pages.yml").read_text(encoding="utf-8"))
        steps = [step for job in workflow["jobs"].values() for step in job["steps"]]
        build = next(step for step in steps if step.get("name") == "Build the app")
        return build["env"]["VITE_BASE_PATH"]

    def test_the_cname_holds_exactly_one_bare_hostname(self):
        """GitHub Pages reads this file literally, and forgives nothing.

        A scheme, a path, a trailing comment or a second line is not a
        hostname, and Pages responds by serving the site at a domain nobody
        asked for - or at none.
        """
        raw = self.CNAME.read_text(encoding="utf-8")
        assert raw.strip().splitlines() == [self._host()], "CNAME must hold one line"
        assert "://" not in self._host()
        assert "/" not in self._host()

    def test_the_app_is_built_for_a_subpath_of_the_custom_domain_root(self):
        """The apex serves the landing page; the app lives under it.

        `/OurHike/app/` was right while this was a project site and is wrong
        now, in the specific way that builds, deploys and then asks for its
        assets at a path nothing answers.
        """
        assert self._base_path() == "/app/"
        assert self._base_path().startswith("/")
        assert self._base_path().endswith("/"), "Vite joins this to asset paths directly"

    def test_the_repository_name_no_longer_decides_the_serving_path(self):
        """It did, and following a repository rename would now be wrong.

        The serving path is a property of the domain, and the domain does not
        change when somebody renames the repository.
        """
        raw = (WORKFLOW_DIR / "pages.yml").read_text(encoding="utf-8")
        assert "VITE_BASE_PATH: /${{ github.event.repository.name }}" not in raw

    def test_the_domain_the_cname_names_is_declared_and_hiker_facing(self):
        """The origin declaration is what the allow-lists are pasted from.

        If this drifts from `site/CNAME`, the bucket and Supabase are told to
        trust a host the app is not served from - and the host it IS served
        from is refused by both.

        `in`, not `==`: the pre-#733 origin is deliberately still blocking too,
        because an install made before the move keeps its storage there. That
        is the origins file's judgement to make and its comment to justify;
        this test only insists the domain being deployed to is among them.
        """
        hiker_facing = [origin["pattern"] for origin in self._origins()["origins"] if origin.get("hiker_facing")]
        assert f"https://{self._host()}" in hiker_facing

    def test_the_declared_app_path_is_the_one_the_bundle_is_built_for(self):
        """`app_path` is where an auth redirect is sent back to.

        Supabase returns a hiker to this exact path after a provider round
        trip. Pointing it anywhere but the built base lands them on a page
        with the auth code in its URL and nothing there to read it - which
        looks like a sign-in that silently did nothing.
        """
        origin = next(o for o in self._origins()["origins"] if o["pattern"] == f"https://{self._host()}")
        assert origin["app_path"] == self._base_path()

    def test_the_site_url_falls_back_to_the_domain_the_app_is_on(self):
        """The Site URL is where a REFUSED redirect goes, so it is the quiet one.

        A wrong one turns "this redirect is not allowed" into a silent trip
        somewhere else, which is how the pre-org-migration host went unnoticed
        while every sign-in from production redirected to a dead 404.
        """
        production = self._origins()["supabase_projects"]["production"]
        assert production["site_url_origin"] == f"https://{self._host()}"

    def test_the_old_project_site_origin_is_kept_and_still_blocking(self):
        """Removing it is the change most likely to look like tidying up.

        A browser arriving there is redirected, which reads as "nothing uses
        this any more" - but an install made before the move keeps its service
        worker and its downloaded archive on that origin, and would still be
        fetching from R2 with it. Dropping the entry drops it from the
        generated CORS policy, which is #427 narrowed to whoever installed
        early: a map that stops downloading, for a subset of hikers, with
        every check green.
        """
        github_io = next(
            (o for o in self._origins()["origins"] if o["pattern"] == "https://ourhike.github.io"),
            None,
        )
        assert github_io is not None, "removing this is a separate change - see #733"
        assert github_io.get("hiker_facing") is True


class TestDraftingWithoutDeploying:
    """`draft_only` exists because RELEASING.md §12 promised what pages.yml did not.

    §12 says an agent "may ... create the GitHub release as a draft" and may not
    publish. But the only thing that drafts one is the `release` job, which
    `needs: build`, and build deploys production - so the draft appeared only
    after hikers already had the build, and the human-reserved action had to
    happen first. Every assertion here stands for one half of inverting that,
    and each fails against the workflow as it was before `draft_only`.

    The one exception is `test_the_release_job_still_only_ever_drafts`, which
    passes against both and is here to stay that way: this change moves WHEN a
    release is drafted and must never touch the fact that it is only ever a
    draft. Measured rather than asserted - run against the pre-`draft_only`
    workflow, nine of these ten fail and that one passes.

    `test_a_non_tag_dispatch_that_is_not_a_draft_is_still_refused` is the #644
    guard restated for the new shape: #644 was a non-tag dispatch that DEPLOYED
    with both gates skipped, and the exemption added here must stay narrow
    enough not to widen back into it.
    """

    WORKFLOW = WORKFLOW_DIR / "pages.yml"

    @classmethod
    def _workflow(cls) -> dict:
        return yaml.safe_load(cls.WORKFLOW.read_text(encoding="utf-8"))

    @classmethod
    def _build_steps(cls) -> list[dict]:
        return cls._workflow()["jobs"]["build"]["steps"]

    @classmethod
    def _step(cls, name: str) -> dict:
        for step in cls._build_steps():
            if step.get("name") == name:
                return step
        raise AssertionError(f"pages.yml has no build step named {name!r}")

    def test_a_draft_never_reaches_the_publish_step(self):
        """The deploy is the promotion §12 reserves for a human."""
        condition = self._step("Publish to GitHub Pages").get("if", "")
        assert "draft_only" in condition, "the publish step must be skipped for a draft"

    def test_a_draft_runs_the_notes_gate(self):
        """Gate 12 skipped on a non-tag ref, which is exactly what #644 exploited.

        A draft is a non-tag ref, so inheriting that guard would draft a release
        for a version with no notes committed beside it.
        """
        assert "draft_only" in self._step("Confirm this tag has its release notes")["if"]

    def test_a_draft_runs_the_version_gate(self):
        """A draft disagreeing with package.json becomes a tag that disagrees
        with it the moment somebody presses publish."""
        assert "draft_only" in self._step("Confirm this tag matches the app's version")["if"]

    def test_a_non_tag_dispatch_that_is_not_a_draft_is_still_refused(self):
        """#644's fix, which the draft exemption must not widen."""
        condition = self._step("Refuse a dispatch that is not a tag")["if"]
        assert "workflow_dispatch" in condition
        assert "refs/tags/" in condition
        assert "!inputs.draft_only" in condition, "only a draft may be exempt from the refusal"

    def test_a_draft_with_no_version_is_refused(self):
        condition = self._step("Refuse a draft with nothing to draft")["if"]
        assert "draft_only" in condition and "inputs.version" in condition

    def test_the_release_job_drafts_for_a_draft_run(self):
        assert "draft_only" in self._workflow()["jobs"]["release"]["if"]

    def test_the_release_job_still_only_ever_drafts(self):
        """The half of §12 this change must not touch."""
        raw = self.WORKFLOW.read_text(encoding="utf-8")
        assert "draft: true" in raw
        assert "draft: false" not in raw

    def test_a_draft_and_a_deploy_cannot_cancel_each_other(self):
        """`cancel-in-progress` is right for two deploys and a disaster shared
        with drafts: asking for a draft would kill a deploy mid-push."""
        group = self._workflow()["concurrency"]["group"]
        assert "draft_only" in group, "drafting and deploying must not share a concurrency group"

    def test_the_draft_says_which_commit_to_tag(self):
        """A draft's tag does not exist yet - publishing creates it - so the
        release has to name the commit or GitHub picks the default branch."""
        raw = self.WORKFLOW.read_text(encoding="utf-8")
        assert "target_commitish" in raw

    def test_the_version_is_resolved_once_rather_than_per_job(self):
        """Two places deriving the version is two places to disagree, which is
        the argument §4 already makes about package.json."""
        assert self._workflow()["jobs"]["build"]["outputs"]["version"]
        raw = self.WORKFLOW.read_text(encoding="utf-8")
        assert "needs.build.outputs.version" in raw

    # --- what publishing the draft would actually tag ------------------------
    #
    # The three below are the sharp edge `draft_only` introduced, found by
    # walking into it: v1.1.1 was drafted from a pull-request branch on
    # 2026-08-27, so its target_commitish was the branch head rather than a
    # commit on main. Publishing it then would have created the tag on unmerged
    # work, and §4's immutable releases make that permanent. It was saved only
    # by the branch merging with a merge commit, which put the target on main's
    # history; a squash merge would not have.

    def _draft_step(self) -> dict:
        steps = self._workflow()["jobs"]["release"]["steps"]
        return next(step for step in steps if step.get("name") == "Draft the release")

    def test_the_draft_says_which_commit_publishing_would_tag(self):
        """The step summary is the only place a person sees this before
        pressing publish, and `target_commitish` is not shown in the release UI
        next to the button."""
        assert "Publishing this draft would tag" in self._draft_step()["run"]

    def test_a_draft_from_a_branch_warns_that_it_is_not_the_default_branch(self):
        """A warning rather than a refusal, deliberately: drafting from a branch
        is the useful case - it is how a release is prepared before it lands -
        so what must not happen quietly is publishing, not drafting."""
        run = self._draft_step()["run"]
        assert '"$REF_NAME" != "$DEFAULT_BRANCH"' in run
        assert "::warning::" in run

    def test_the_branch_comparison_reaches_the_script_through_env(self):
        """#660. Both values are GitHub-controlled rather than user input, but
        the rule is not "inputs that look dangerous" - it is inputs."""
        env = self._draft_step()["env"]
        assert env["REF_NAME"] == "${{ github.ref_name }}"
        assert env["DEFAULT_BRANCH"] == "${{ github.event.repository.default_branch }}"
