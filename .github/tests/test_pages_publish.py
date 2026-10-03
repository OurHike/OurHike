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

import json
import os
import re
import stat
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

    def test_a_preview_is_built_for_the_same_path_production_serves_the_app_at(self):
        """A base path that disagrees with the serving path is a blank screen.

        A preview uploads the site and the app together now, laid out as
        pages.yml lays them out - site at `/`, app at `/app/` - so the base is
        production's, and for the stronger reason as well as the obvious one.
        The obvious one is that a bundle built for `/` and served under `/app/`
        asks for assets nothing answers. The stronger one is
        client/src/lib/orgRoute.ts: it reads its basename from
        `import.meta.env.BASE_URL` because a router taking it from anywhere
        else "breaks deep links in exactly one environment - the one nobody
        tests", and a preview built for `/` made this that environment.
        """

        def base_path(workflow: str) -> str:
            build = next(step for step in self._steps(self._workflow(workflow)) if step.get("name") == "Build the app")
            return build["env"]["VITE_BASE_PATH"]

        assert base_path("pr-preview.yml") == "/app/"
        assert base_path("pr-preview.yml") == base_path("pages.yml"), (
            "a preview that disagrees with production is the environment nobody tests"
        )

    def test_a_preview_uploads_the_site_and_the_app_together(self):
        """The half of the layout that a base path alone cannot buy.

        `wrangler pages deploy client/dist` uploads the app and nothing else,
        so `/for-orgs/` and the three pages under it were unreachable in a
        preview - and did not 404, because Cloudflare Pages answers an
        unmatched path with the root index.html. Measured on pr-1547,
        2026-09-17: `/for-orgs/` answered 200 with the app's index.html.
        """
        steps = self._steps(self._workflow("pr-preview.yml"))
        names = [step.get("name") for step in steps]
        assert "Build the site" in names, "the marketing site has to be built before it can be uploaded"
        assemble = next(step for step in steps if step.get("name") == "Assemble the preview")
        # The same two copies pages.yml makes, in the same direction.
        assert "cp -r site/dist/. _site/" in assemble["run"]
        assert "cp -r client/dist/. _site/app/" in assemble["run"]
        deploy = next(step for step in steps if "wrangler-action" in step.get("uses", ""))
        assert "pages deploy _site" in deploy["with"]["command"]
        assert "pages deploy client/dist" not in deploy["with"]["command"]
        assert names.index("Assemble the preview") < names.index("Publish the preview")
        # The camera writes into client/dist, so a copy taken before it would
        # upload an app with no pictures and a comment linking at them.
        assert names.index("Photograph the build") < names.index("Assemble the preview")

    def test_a_preview_can_still_open_a_console_address(self):
        """The one line that keeps the org surface reviewable at all.

        With the site at the root, a path Pages holds no file for falls back to
        the SITE's landing page - so `/app/org/<slug>/setup` and `/app/my/tread`
        would serve marketing copy. Those addresses are the only way the console
        is reached (client/src/lib/orgRoute.ts: a welcome email, an org's
        members area, a bookmark), so a preview without this fallback is a
        preview of a console nobody can review.

        `_redirects` is read by Cloudflare Pages and ignored by GitHub Pages, so
        this changes nothing about how a hiker is served. Production answers
        those URLs with a 404 today - measured against the live site
        2026-09-17, and written up in features/ORG_ONBOARDING.md's Known gaps.
        """
        steps = self._steps(self._workflow("pr-preview.yml"))
        assemble = next(step for step in steps if step.get("name") == "Assemble the preview")
        assert "_site/_redirects" in assemble["run"], "a preview needs the app's deep links to resolve"
        assert "/app/index.html  200" in assemble["run"]
        # The one that actually fires. Pages resolves a not-found path against
        # its own fallback before reading `_redirects` - measured on run
        # 8d649163, where the rule was uploaded and did nothing - and a
        # `404.html` is what displaces that fallback.
        assert "cp _site/app/index.html _site/404.html" in assemble["run"]
        # And production keeps its own answer, whatever that turns out to be.
        assert "_redirects" not in (WORKFLOW_DIR / "pages.yml").read_text(encoding="utf-8")

    def test_the_advertised_preview_url_is_the_one_deployed_to(self):
        """Both come from the same step, so they cannot drift apart.

        A comment linking somewhere the upload did not go is a reviewer looking
        at someone else's change, or at a 404, and believing either.

        The comment names `steps.links` rather than the deploy directly: with
        the site at `/` and the app at `/app/` there are several links to
        build, and the trailing slash has to come off the base once rather
        than once per link. So this follows the seam - the links step reads
        the deploy, and every link in the comment reads the links step.
        """
        steps = self._steps(self._workflow("pr-preview.yml"))
        deploy = next(step for step in steps if "wrangler-action" in step.get("uses", ""))
        links = next(step for step in steps if step.get("name") == "Work out where to link")
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
        assert "steps.deploy.outputs.pages-deployment-alias-url" in links["env"]["BASE"]
        assert "steps.preview.outputs.url" in links["env"]["BASE"]
        # Off once, in the step every link is built from: the two candidates
        # disagree about a trailing slash and `https://host//app/` is a 404.
        assert 'BASE="${BASE%/}"' in links["run"]
        assert "steps.links.outputs.app" in comment["with"]["message"]

    def test_the_comment_offers_the_marketing_site_as_well_as_the_app(self):
        """The reviewer-facing half of uploading both.

        A preview that holds `/for-orgs/` and never says so is a preview
        nobody opens it in: the pull request comment is the only place the
        URL ever appears.
        """
        steps = self._steps(self._workflow("pr-preview.yml"))
        links = next(step for step in steps if step.get("name") == "Work out where to link")
        comment = next(
            step
            for step in steps
            if "sticky-pull-request-comment" in step.get("uses", "") and step.get("if", "").strip().endswith("!= 'closed'")
        )
        assert "for-orgs" in links["run"]
        assert "steps.links.outputs.orgs" in comment["with"]["message"]


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

    def test_a_refused_release_post_prints_githubs_reason_instead_of_a_bare_exit(self):
        """#1717. `curl -f` turned a 403 into an exit code and discarded the
        body, so the cause of the 2026-09-29 refusals was never seen. The step
        reads the status itself, as release-notes.yml does for its own POST."""
        run = self._draft_step()["run"]
        post = run.split("response=", 1)[1].split("-d @payload.json", 1)[0]
        assert "curl -sS -w" in post
        assert "-fsS" not in post
        assert "%{http_code}" in post
        assert "::error::Drafting" in run
        assert ".message" in run


class TestTheDataDocs:
    """The dbt docs at `/data/` (pipeline/ELT.md, "Docs and charts at https://ourhike.org/data/").

    Stage 7 of **#1793 — Rebuild the data platform as dlt → dbt: seven
    contracted marts, a monthly refresh, published docs, and lighter phone
    downloads**. Production and every preview serve the page beside the app,
    built by `.github/actions/dbt-docs-site` and checked by
    `pipeline/check_docs_site.py` as copied; UA has no site and gets none. The
    first three tests are the three assertions ELT.md names; the fourth is
    its "the docs step needs no secret".
    """

    ACTION = REPO_ROOT / ".github" / "actions" / "dbt-docs-site"
    CHECKER = REPO_ROOT / "pipeline" / "check_docs_site.py"
    SITE_BUILDS = [("pages.yml", "Assemble the site"), ("pr-preview.yml", "Assemble the preview")]

    @staticmethod
    def _steps(workflow: str) -> list[dict]:
        parsed = yaml.safe_load((WORKFLOW_DIR / workflow).read_text(encoding="utf-8"))
        return [step for job in parsed["jobs"].values() for step in job["steps"]]

    @pytest.mark.parametrize(("workflow", "assemble"), SITE_BUILDS)
    def test_both_site_builds_assemble_the_docs_at_data_index_html(self, workflow, assemble):
        """Built before the assembly, copied into `_site/data/` by it, and checked there.

        The check is on the copy because the copy is what ships, and it is the
        only thing between a preview and its trap: `_site/404.html` is the app
        shell, so a missing `_site/data/index.html` would be answered with the
        app rather than with a failure.
        """
        steps = self._steps(workflow)
        names = [step.get("name") for step in steps]
        build = next(step for step in steps if step.get("uses") == "./.github/actions/dbt-docs-site")
        step = next(step for step in steps if step.get("name") == assemble)
        assert names.index(build["name"]) < names.index(assemble)
        assert step["env"]["DOCS_DIR"] == "${{ steps.%s.outputs.dir }}" % build["id"]
        assert 'cp -r "$DOCS_DIR"/. _site/data/' in step["run"]
        assert "python pipeline/check_docs_site.py _site/data" in step["run"]
        # And the checker is what refuses a site with no index.html.
        assert 'site / "index.html"' in self.CHECKER.read_text(encoding="utf-8")

    @pytest.mark.parametrize(("workflow", "assemble"), SITE_BUILDS)
    def test_nothing_lands_under_the_apps_data_path(self, workflow, assemble):
        """`/app/` is the app's base path and its PWA scope, so docs there would be the installed app's.

        Everything copied under `_site/app/` is the app's own build, and
        client/public, which Vite copies into that build, holds no `data/`.
        """
        steps = self._steps(workflow)
        run = next(step for step in steps if step.get("name") == assemble)["run"]
        copies = [line.split() for line in run.splitlines() if line.strip().startswith("cp ")]
        into_app = [words for words in copies if words[-1].startswith("_site/app")]
        assert into_app and all(words[-2] == "client/dist/." for words in into_app), into_app
        docs = [words for words in copies if '"$DOCS_DIR"/.' in words]
        assert [words[-1] for words in docs] == ["_site/data/"]
        assert "_site/app/data" not in yaml.safe_dump(steps)
        assert not (REPO_ROOT / "client" / "public" / "data").exists()

    def test_ua_still_deploys_client_dist_alone(self):
        """UA has no site, and giving it one is a separate decision (ELT.md)."""
        steps = self._steps("ua.yml")
        deploy = next(step for step in steps if "wrangler-action" in step.get("uses", ""))
        assert "pages deploy client/dist" in deploy["with"]["command"]
        assert "_site" not in yaml.safe_dump(steps)
        assert all(step.get("uses") != "./.github/actions/dbt-docs-site" for step in steps)
        assert "check_docs_site" not in yaml.safe_dump(steps)

    def test_the_docs_build_reads_no_secret_and_passes_no_vars(self):
        """`dbt_rt.invocations` publishes `args` and `vars_override` with the page.

        So the build holds no secret to leak, and nothing reaches dbt through
        `--vars`; check_docs_site.py refuses a page that records one anyway.
        """
        action = (self.ACTION / "action.yml").read_text(encoding="utf-8")
        assert "secrets." not in action
        for workflow, _ in self.SITE_BUILDS:
            build = next(step for step in self._steps(workflow) if step.get("uses") == "./.github/actions/dbt-docs-site")
            assert "secrets." not in yaml.safe_dump(build)
        script = (self.ACTION / "build.sh").read_text(encoding="utf-8")
        commands = [line for line in script.splitlines() if not line.strip().startswith("#")]
        assert not [line for line in commands if "--vars" in line]
        assert "DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS=false" in script

    def test_the_deploy_job_leaves_no_write_token_on_disk_for_the_docs_build(self):
        """pages.yml's build job holds `contents: write` and replaces gh-pages,
        and the docs step installs dbt, runs `dbt deps` and downloads a native
        driver, none of them hash-pinned. A checkout that persists its token
        leaves that token in .git/config for every one of them to read.

        The publish needs no persisted token: it pushes from a fresh `git init`
        through a remote URL carrying the token it is handed, so the checkout
        can keep none.
        """
        parsed = yaml.safe_load((WORKFLOW_DIR / "pages.yml").read_text(encoding="utf-8"))
        steps = parsed["jobs"]["build"]["steps"]
        checkouts = [step for step in steps if str(step.get("uses", "")).startswith("actions/checkout@")]
        assert checkouts, "the build job checks the repository out"
        assert all(step.get("with", {}).get("persist-credentials") is False for step in checkouts)
        publish = next(step for step in steps if step.get("uses") == "./.github/actions/publish-to-pages")
        assert publish["with"]["token"] == "${{ secrets.GITHUB_TOKEN }}"
        assert "x-access-token:${{ inputs.token }}@" in (ACTION_DIR / "action.yml").read_text(encoding="utf-8")
        script = SCRIPT.read_text(encoding="utf-8")
        assert 'git init -q "$WORK"' in script
        assert 'git -C "$WORK" remote add origin "$REMOTE_URL"' in script


class TestTheUploadedPointer:
    """Both deploy guards hold the committed channels.json to the copy phones read.

    Phones read `${base}/channels.json`, which only the release train's
    `publish.py --channels` uploads (RELEASING.md §10), and the guard used to
    read only `../channels.json`, so a deploy went green while phones followed
    another release. That was the first defect in the client review of
    **#1805 — dlt → dbt re-platform as one go/no-go change: every club through
    dlt, eleven contracted marts writing every phone file, and the hourly and
    monthly lanes**. The step's own script runs here against a stub `curl`
    serving a fake bucket, because the refusal is in the shell.
    """

    STEP = "Confirm channels.json's release exists"
    BASE = "https://data.example.org"
    WORKFLOWS = ["pages.yml", "ua.yml"]
    # The base each environment's build is given (lib/dataRelease.ts's
    # environmentOf): production is the bucket root, UA is its prefix.
    PREFIXES = {"production": "", "ua": "/environments/ua"}

    @classmethod
    def _script(cls, workflow: str) -> str:
        parsed = yaml.safe_load((WORKFLOW_DIR / workflow).read_text(encoding="utf-8"))
        steps = [step for job in parsed["jobs"].values() for step in job["steps"]]
        return next(step for step in steps if step.get("name") == cls.STEP)["run"]

    @staticmethod
    def _committed() -> dict:
        return json.loads((REPO_ROOT / "channels.json").read_text(encoding="utf-8"))

    @staticmethod
    def _stub_curl(directory: Path) -> None:
        """A `curl` answering from `$STUB_BUCKET`: 200 with the file's bytes,
        404 for a missing one, or the code in a `<file>.status` beside it.
        Honours `-o`, `-w '%{http_code}'` and `-f` as the real one does."""
        script = r"""#!/usr/bin/env bash
out=""; fmt=""; fail=false; url=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    -w) fmt="$2"; shift 2 ;;
    --retry|--max-time) shift 2 ;;
    -f*) fail=true; shift ;;
    -*) shift ;;
    *) url="$1"; shift ;;
  esac
done
path="$STUB_BUCKET/${url#"$STUB_BASE"/}"
if [ -f "$path.status" ]; then code=$(cat "$path.status"); elif [ -f "$path" ]; then code=200; else code=404; fi
if [ "$code" = 200 ] && [ -n "$out" ]; then cp "$path" "$out"; fi
if [ -n "$fmt" ]; then printf '%s' "$code"; fi
if [ "$code" != 200 ] && $fail; then echo "curl: (22) The requested URL returned error: $code" >&2; exit 22; fi
exit 0
"""
        path = directory / "curl"
        path.write_text(script, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def _run(self, tmp_path: Path, workflow: str, environment: str, uploaded: dict | None, *, status: int | None = None):
        """The step against `environment`'s base, where the committed entry's
        manifest is published and `uploaded` (None for no copy) is at the root."""
        prefix = self.PREFIXES[environment]
        root = tmp_path / "bucket" / prefix.strip("/")
        release = self._committed()[environment]["v1"]
        manifest = root / "releases" / release / "manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text('{"artifacts": {}}', encoding="utf-8")
        if uploaded is not None:
            (root / "channels.json").write_text(json.dumps(uploaded), encoding="utf-8")
        if status is not None:
            (root / "channels.json.status").write_text(str(status), encoding="utf-8")
        stubs = tmp_path / "stubs"
        stubs.mkdir()
        self._stub_curl(stubs)
        runner_temp = tmp_path / "runner-temp"
        runner_temp.mkdir()
        return subprocess.run(
            # How Actions runs a `run:` block under bash.
            ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", self._script(workflow)],
            cwd=REPO_ROOT / "client",
            env={
                **os.environ,
                "PATH": f"{stubs}{os.pathsep}{os.environ['PATH']}",
                "DATA_URL": f"{self.BASE}{prefix}",
                "RUNNER_TEMP": str(runner_temp),
                "STUB_BUCKET": str(tmp_path / "bucket"),
                "STUB_BASE": self.BASE,
            },
            capture_output=True,
            text=True,
        )

    @pytest.mark.parametrize("workflow", WORKFLOWS)
    @pytest.mark.parametrize("environment", ["production", "ua"])
    def test_an_uploaded_copy_naming_the_committed_release_passes(self, tmp_path, workflow, environment):
        completed = self._run(tmp_path, workflow, environment, self._committed())

        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "The uploaded channels.json at" in completed.stdout

    @pytest.mark.parametrize("workflow", WORKFLOWS)
    @pytest.mark.parametrize("environment", ["production", "ua"])
    def test_an_uploaded_copy_naming_another_release_fails_and_names_the_fix(self, tmp_path, workflow, environment):
        """The regression: the committed entry resolves, and phones follow another."""
        uploaded = self._committed()
        uploaded[environment]["v1"] = "2026-01-01"

        completed = self._run(tmp_path, workflow, environment, uploaded)

        assert completed.returncode != 0
        assert "::error::" in completed.stdout
        assert "publish.py --channels" in completed.stdout
        # The uploaded entry is remote text, and never reaches a workflow command.
        assert "2026-01-01" not in completed.stdout

    @pytest.mark.parametrize("workflow", WORKFLOWS)
    def test_an_uploaded_copy_with_no_entry_for_this_environment_fails(self, tmp_path, workflow):
        uploaded = self._committed()
        del uploaded["ua"]

        completed = self._run(tmp_path, workflow, "ua", uploaded)

        assert completed.returncode != 0
        assert "publish.py --channels" in completed.stdout

    @pytest.mark.parametrize("workflow", WORKFLOWS)
    def test_no_uploaded_copy_passes_with_a_notice(self, tmp_path, workflow):
        """A 404: phones then read the compiled DATA_RELEASE, checked one step earlier."""
        completed = self._run(tmp_path, workflow, "production", None)

        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "::notice::" in completed.stdout
        assert "DATA_RELEASE" in completed.stdout

    @pytest.mark.parametrize("workflow", WORKFLOWS)
    def test_an_unreadable_uploaded_copy_fails(self, tmp_path, workflow):
        """Neither a copy nor a 404, so nothing says which release phones follow."""
        completed = self._run(tmp_path, workflow, "production", self._committed(), status=503)

        assert completed.returncode != 0
        assert "answered 503" in completed.stdout
