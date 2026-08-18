"""Tests for the release process's machinery - the notes generator and the
workflows that gate a release.

Two halves, for the same reason `test_pages_publish.py` has two:

`TestTheGenerator` covers `.github/scripts/release_notes.py`'s pure functions.
The generator's I/O half - git and the GitHub API - is deliberately not covered:
this suite installs pytest, PyYAML and ruff, and a release script is not worth
adding an HTTP mocking dependency to it. The seam is kept small enough to read
instead.

`TestTheReleaseWorkflows` is the static half, and every assertion in it stands
for a way the design in RELEASING.md can be undone by a one-line edit that looks
harmless:

  * `pages.yml` triggering on `main` again turns production back into continuous
    deployment, which is the exact thing the whole process exists to stop, and
    nothing else would notice - the site would deploy perfectly well.
  * `ua.yml` reading `API_BASE_URL` gives UA the production backend, so a
    tester's report lands in the moderation queue a club works from.
  * `ua.yml` building for a subpath instead of its own origin puts UA on
    production's origin, where it shares one IndexedDB with the installed app
    and can evict a hiker's 1.18 GB archive.
  * The release being created without `draft: true` publishes it, which
    CLAUDE.md and RELEASING.md §12 both reserve for a human.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from release_notes import (
    Change,
    area_of,
    group_by_area,
    hiker_facing,
    linked_issues,
    pull_request_numbers,
    render_notes,
    slug,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"
REPO = "OurHike/OurHike"


def _workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOW_DIR / name).read_text(encoding="utf-8"))


def _triggers(workflow: dict) -> dict:
    """A workflow's `on:` block.

    PyYAML implements YAML 1.1, in which `on` is a boolean - so the key comes
    back as `True` rather than as the string every workflow file appears to
    contain. Reading `workflow["on"]` returns None, which would make every
    assertion below pass vacuously against a trigger nobody had checked.
    """
    return workflow.get(True, workflow.get("on"))


def _text(name: str) -> str:
    return (WORKFLOW_DIR / name).read_text(encoding="utf-8")


class TestTheGenerator:
    def test_reads_a_merge_commit_subject(self):
        assert pull_request_numbers("Merge pull request #364 from owner/branch") == [364]

    def test_reads_a_squashed_subject(self):
        """Both spellings are in this repository's history, so a generator that
        knew one would produce short notes rather than fail."""
        assert pull_request_numbers("Serve POI photos from our own bucket (#366)") == [366]

    def test_keeps_order_and_drops_duplicates(self):
        log = "Merge pull request #10 from a/b\nSomething (#7)\nMerge pull request #10 from a/b\n"
        assert pull_request_numbers(log) == [10, 7]

    def test_ignores_a_subject_that_merely_mentions_a_number(self):
        assert pull_request_numbers("Fix the thing described in #42") == []

    def test_ignores_ordinary_commits(self):
        assert pull_request_numbers("Give a report photo somewhere to go\nAnother commit\n") == []

    @pytest.mark.parametrize("word", ["Closes", "closes", "closed", "Fixes", "fixed", "resolve", "Resolves"])
    def test_reads_every_closing_keyword_github_honours(self, word):
        assert linked_issues(f"{word} #370") == [370]

    def test_a_bare_mention_does_not_close(self):
        """CONTRIBUTING.md draws this distinction and pr-issue-link.yml enforces
        it: referring to an issue and resolving it are different claims."""
        assert linked_issues("Related to #370, see also #12") == []

    def test_collects_several_issues_without_duplicates(self):
        assert linked_issues("Closes #1\nfixes #2\nCloses #1") == [1, 2]

    def test_area_follows_the_declared_order(self):
        assert area_of(["ops", "client"]) == "client"

    def test_area_of_an_unlabelled_change(self):
        assert area_of([]) == "other"
        assert area_of(["v1-mvp"]) == "other"

    def test_groups_in_area_order_and_omits_empty_buckets(self):
        changes = [Change(1, "a", ["docs"]), Change(2, "b", ["client"]), Change(3, "c", ["ops"])]
        assert list(group_by_area(changes)) == ["client", "ops", "docs"]

    def test_a_docs_only_change_is_not_hiker_facing(self):
        assert hiker_facing([Change(1, "Fix a typo", ["docs"])]) == []

    def test_an_internal_change_that_also_touches_the_client_is_hiker_facing(self):
        changes = [Change(1, "Retarget the deploy", ["ops", "client"])]
        assert len(hiker_facing(changes)) == 1

    def test_an_unlabelled_change_is_offered_rather_than_dropped(self):
        """Erring toward including is deliberate. An extra line a human deletes
        costs a moment; a missed one ships a release that does not mention what
        it changed."""
        assert len(hiker_facing([Change(1, "Something", [])])) == 1

    def test_slug_makes_a_filename_from_a_landmark(self):
        assert slug("Springer Mountain") == "springer-mountain"
        assert slug("Harpers Ferry") == "harpers-ferry"

    def test_the_notes_lead_with_the_version_and_its_name(self):
        notes = render_notes("v1.0.0", "Springer Mountain", [], REPO)
        assert notes.startswith("# v1.0.0 — Springer Mountain\n")

    def test_every_change_appears_with_its_pull_request_and_issue(self):
        notes = render_notes("v1.1.0", "Blood Mountain", [Change(366, "Serve POI photos", ["client"], [234])], REPO)
        assert "Serve POI photos" in notes
        assert f"https://github.com/{REPO}/pull/366" in notes
        assert f"https://github.com/{REPO}/issues/234" in notes

    def test_a_change_closing_no_issue_still_appears(self):
        """A `no-issue` change is a legitimate state, so leaving it out of the
        notes would quietly under-report a release."""
        notes = render_notes("v1.0.1", "Springer Mountain", [Change(9, "Bump a dependency", ["no-issue"])], REPO)
        assert "Bump a dependency" in notes

    def test_the_not_validated_section_is_present_even_with_nothing_to_put_in_it(self):
        """RELEASING.md §8d: this section is never empty, and a release whose
        author believes it is has not looked. An absent heading is how it would
        quietly become optional."""
        notes = render_notes("v1.0.0", "Springer Mountain", [], REPO, unvalidated=[])
        assert "## What is not validated" in notes

    def test_unvalidated_issues_are_listed_with_links(self):
        notes = render_notes("v1.0.0", "Springer Mountain", [], REPO, unvalidated=[Change(93, "Wrong-way thresholds")])
        assert "Wrong-way thresholds" in notes
        assert f"https://github.com/{REPO}/issues/93" in notes

    def test_a_release_with_nothing_hiker_visible_says_so(self):
        notes = render_notes("v1.0.1", "Springer Mountain", [Change(1, "Tidy a comment", ["docs"])], REPO)
        assert "internal work only" in notes

    def test_the_pinned_data_release_is_named_when_there_is_one(self):
        notes = render_notes("v1.2.0", "Fontana Dam", [], REPO, data_release="2026-08-07")
        assert "2026-08-07" in notes

    def test_an_unpinned_data_release_says_that_rather_than_nothing(self):
        notes = render_notes("v1.2.0", "Fontana Dam", [], REPO, data_release=None)
        assert "No data release is pinned" in notes

    def test_the_human_half_is_marked_rather_than_left_blank(self):
        """The name, the figure and the prose are the parts a generator cannot
        do. A draft that looked finished is one that ships with the generated
        pull request titles as its hiker-facing notes."""
        notes = render_notes("v1.0.0", "Springer Mountain", [Change(1, "A change", ["client"])], REPO)
        assert notes.count("TODO (human)") >= 3
        assert "## Named beside" in notes


class TestTheReleaseWorkflows:
    def test_production_deploys_from_a_tag(self):
        push = _triggers(_workflow("pages.yml"))["push"]
        assert push.get("tags") == ["v*"]

    def test_production_does_not_deploy_from_a_branch(self):
        """The single most important assertion in this file. Re-adding
        `branches: [main]` here turns production back into continuous deployment
        - every merge live to hikers, no gate, nowhere for a candidate to wait -
        and nothing else in the repository would report it, because the deploy
        would keep working perfectly."""
        push = _triggers(_workflow("pages.yml"))["push"]
        assert "branches" not in push

    def test_production_does_not_deploy_from_a_dispatch_off_a_branch(self):
        """The assertion above closes the front door; this is the back one.
        Both tag gates are steps that *skip* on a non-tag ref - deliberately,
        so a rollback dispatch does not re-assert paperwork - and the Run
        workflow button offers the default branch first. Without a refusal
        step, the default dispatch of Deploy Pages built main and pushed it
        to production with every gate silently skipped (#644)."""
        steps = _workflow("pages.yml")["jobs"]["build"]["steps"]
        guard = steps[0]
        assert guard.get("name") == "Refuse a dispatch that is not a tag"
        assert "workflow_dispatch" in guard["if"]
        assert "!startsWith(github.ref, 'refs/tags/')" in guard["if"]

    def test_ua_deploys_from_main(self):
        push = _triggers(_workflow("ua.yml"))["push"]
        assert push.get("branches") == ["main"]

    def test_ua_builds_for_its_own_origin(self):
        """IndexedDB is per-origin, not per-path. A UA build made for a subpath
        of the production host shares one IndexedDB with the installed app and
        can evict a hiker's 1.18 GB archive - so the base path being `/` is a
        storage-isolation assertion, not a cosmetic one."""
        steps = _workflow("ua.yml")["jobs"]["ua"]["steps"]
        build = next(step for step in steps if step.get("name") == "Build the app")
        assert build["env"]["VITE_BASE_PATH"] == "/"

    def test_ua_never_reaches_the_production_backend(self):
        """`API_BASE_URL` names the backend that writes the moderation queue a
        club works from. UA gets `UA_API_BASE_URL` or nothing - a fallback here
        would file test reports into real moderation work, which is the same
        reason pr-preview.yml sets no backend at all."""
        text = _text("ua.yml")
        assert "vars.UA_API_BASE_URL" in text
        assert not re.search(r"vars\.API_BASE_URL", text)

    def test_only_the_production_workflow_writes_the_pages_branch(self):
        """UA is a Cloudflare deployment precisely so that it is a different
        origin. Publishing it to `gh-pages` would put it back on production's
        origin however the paths were arranged.

        The census reads the CAPABILITY - step run/uses/with strings - not
        the helper action's name in the raw file text (#660): the old grep
        counted comments as writes (pr-preview.yml explains itself by
        naming the branch) and a raw `git push` to gh-pages that never
        mentioned the helper was invisible to it."""
        writers = []
        for path in sorted(WORKFLOW_DIR.glob("*.yml")):
            strings = []
            for job in (_workflow(path.name).get("jobs") or {}).values():
                for step in job.get("steps", []):
                    strings += [str(step.get("run") or ""), str(step.get("uses") or ""), str(step.get("with") or "")]
            if any("gh-pages" in s or "publish-to-pages" in s for s in strings):
                writers.append(path.name)
        assert writers == ["pages.yml"]

    def test_a_tag_without_notes_does_not_deploy(self):
        """Gate 12. The notes file is canonical (§7a), and the failure it
        guards is silent in the direction that matters: the site deploys and
        the release has no record.

        Asserted on the gate's BEHAVIOUR, not its step name (#660): the old
        assertion held any step whose name mentioned "release notes", which
        an `exit 0` edit satisfied. This one requires a tag-gated step that
        globs the notes path and fails the run when it matches nothing."""
        steps = _workflow("pages.yml")["jobs"]["build"]["steps"]
        gate = next((step for step in steps if 'releases/"$VERSION"-*.md' in (step.get("run") or "")), None)
        assert gate is not None, "no step checks for the tag's notes file at all"
        assert "exit 1" in gate["run"], "finding no notes must fail the deploy, not narrate it"
        assert str(gate.get("if", "")).startswith("startsWith(github.ref, 'refs/tags/')"), (
            "the gate must run exactly on tag deploys - a dispatch is a republish of something already released"
        )

    def test_the_github_release_is_only_ever_drafted(self):
        """CLAUDE.md and RELEASING.md §12: a workflow may prepare everything and
        may not publish. `draft: true` is the whole of that rule in machine-
        readable form."""
        release = _workflow("pages.yml")["jobs"]["release"]
        script = "\n".join(step.get("run", "") for step in release["steps"])
        assert "draft: true" in script
        assert '"draft": false' not in script

    def test_the_release_job_attaches_the_build_that_deployed(self):
        """A second build of the same commit is not the bytes that shipped - it
        is a build that agrees with them until one day it does not."""
        release = _workflow("pages.yml")["jobs"]["release"]
        assert any("download-artifact" in str(step.get("uses", "")) for step in release["steps"])
        assert release["needs"] == "build"

    def test_the_notes_workflow_is_never_automatic(self):
        """Drafting notes pushes a branch and opens a pull request. On a trigger
        it would do that on somebody else's schedule."""
        assert list(_triggers(_workflow("release-notes.yml"))) == ["workflow_dispatch"]

    def test_the_notes_pull_request_is_labelled_so_it_can_pass_ci(self):
        """`pr-issue-link.yml` fails a pull request that closes no issue, which
        is correct of it and wrong for release paperwork. Without the label
        every release pull request opens red for a reason the opener cannot
        fix."""
        assert "no-issue" in _text("release-notes.yml")

    def test_the_notes_workflow_refuses_to_reuse_a_tag(self):
        """Re-releasing a version would move a tag that installed builds and
        retention policy are both pinned to."""
        assert "already tagged" in _text("release-notes.yml")

    def test_the_release_gate_is_never_automatic(self):
        """Gate 11 is a question asked while deciding whether to ship. On a
        schedule it would ask on a day nobody is shipping, and the answer would
        be noise the next real run is read past."""
        assert list(_triggers(_workflow("release-gate.yml"))) == ["workflow_dispatch"]

    def test_the_release_gate_confirms_the_label_exists_before_trusting_an_empty_answer(self):
        """The trap RELEASING.md §8 names, and the reason gate 11 could not
        simply be a saved search: a query for a label that does not exist
        returns no issues, which reads exactly like a clean board. Asserting the
        label is there is what makes "no blockers" mean something."""
        text = _text("release-gate.yml")

        # The lookup, its 404 accounting, and the failure it must produce -
        # not the explanatory comment the old assertion pinned (#660):
        # deleting the failure while keeping the prose used to pass.
        assert "getLabel" in text
        assert "if (error.status === 404) missing.push(name)" in text
        assert "core.setFailed(`Missing label(s):" in text, (
            "an absent label must FAIL the gate - a query for it returns no issues, which reads exactly like a clean board"
        )

    def test_the_release_gate_fails_rather_than_reports(self):
        """Gate 11 is `hard` in RELEASING.md §8. A job that printed the blockers
        and exited green would leave the gate exactly as enforced as the
        procedure it replaces."""
        assert "core.setFailed" in _text("release-gate.yml")

    def test_the_release_gate_cannot_ship_anything(self):
        """RELEASING.md §12 and CLAUDE.md both reserve tagging, publishing and
        promoting for a human. A gate that could act on its own answer would be
        the one place that rule could be undone without anybody deciding to."""
        workflow = _workflow("release-gate.yml")
        text = _text("release-gate.yml")

        assert workflow["permissions"] == {"contents": "read", "issues": "read"}
        for forbidden in ("createRelease", "createRef", "git tag", "merge_pull_request"):
            assert forbidden not in text

    def test_a_follow_up_label_does_not_fail_the_gate(self):
        """`release-followup` existing and being applied is the §8b rule
        working. Failing on it would teach whoever runs this to stop applying
        the label, which is how `release-blocker` stops meaning anything."""
        text = _text("release-gate.yml")

        assert "Reported, never failed" in text

    def test_the_battery_is_never_automatic(self):
        """It downloads ~1.6 GB to answer a question somebody is waiting on.
        On a schedule it would spend that daily on a question nobody asked -
        and check-deployment.yml already answers the daily one for no bytes."""
        assert list(_triggers(_workflow("verify-release.yml"))) == ["workflow_dispatch"]

    def test_the_battery_fails_the_run_rather_than_reporting(self):
        """Its daily siblings are reporters with a tracking issue, because a
        real outage emailing every morning is how an alarm gets filtered. This
        one is dispatched by a person waiting for the answer, so the answer is
        the exit code - which means no `--exit-zero` and no `continue-on-error`."""
        text = _text("verify-release.yml")

        assert "--exit-zero" not in text
        assert "continue-on-error" not in text

    def test_the_battery_can_be_pointed_at_a_candidate_rather_than_production(self):
        """Once #500 exists, a release is verified BEFORE it is promoted. A
        workflow that could only read the live base would verify the thing
        hikers already have."""
        inputs = _triggers(_workflow("verify-release.yml"))["workflow_dispatch"]["inputs"]

        assert "base" in inputs
        assert "strict" in inputs

    def test_the_battery_holds_no_credentials(self):
        """Public HTTPS only is the property that makes it test what a phone
        fetches, through the same CDN and CORS policy. A credential here would
        let it read something a hiker cannot, and pass where they would fail."""
        workflow = _workflow("verify-release.yml")

        assert workflow["permissions"] == {"contents": "read"}
        assert "secrets." not in _text("verify-release.yml")
