#!/usr/bin/env python3
"""Generate a release notes draft from the merges between two refs.

RELEASING.md §7: the notes are derived and then edited, never maintained. A
hand-kept CHANGELOG.md is the half that goes stale, and this repository already
has the thing that makes generation reliable - `pr-issue-link.yml` fails any
pull request that closes no issue, so every merged change carries a linked issue
or an explicit `no-issue` label.

Two halves, split by what touches the world:

  * The pure half - `pull_request_numbers`, `linked_issues`, `area_of`,
    `hiker_facing`, `render_notes` - takes data and returns text. That is what
    `.github/tests/test_release_notes.py` covers, per TESTING.md's preference
    for pure functions over end-to-end runs of a script.
  * The I/O half - `git log`, and the GitHub API through urllib - is a thin
    seam at the bottom of the file. It is not exercised by the suite, so it is
    kept small enough to read.

Standard library only, deliberately. The suite this is tested by installs
pytest, PyYAML and ruff, and there is no argument for a release script to be the
thing that adds an HTTP dependency to it.

What this produces is a **draft**. The name, the historical figure and the
paragraph that makes it a release rather than a diff are written by a human on
top of it (RELEASING.md §5, §6) - that is the part worth a person's time, and
the only part.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

API_ROOT = "https://api.github.com"

# The area labels CONTRIBUTING.md defines, in the order they are worth reading:
# what a hiker touches first, what builds the data second, what only a
# contributor sees last.
AREAS = ["client", "backend", "pipeline", "data", "ops", "docs"]

# A change whose labels are entirely within this set is not something a hiker
# can observe. Everything else is offered to the hiker-facing section, including
# a change with no area labels at all - erring toward including is deliberate,
# because an extra line a human deletes costs a moment and a missed one ships a
# release that does not mention what it changed.
INTERNAL_ONLY = {"docs", "ops", "no-issue"}

# Two of the three spellings of a merged pull request. GitHub writes the
# first for a merge commit and the second into the subject of a squash, and
# this repository has used both - so a generator that knew only one would
# silently produce short notes rather than fail. The THIRD spelling is no
# spelling at all (#660): a rebase merge replays the branch's own commits
# with their original subjects, so nothing in `git log --format=%s` names
# the pull request. Commits neither regex matches are resolved through the
# commit->pulls API in main() instead of being silently dropped - a
# rebase-configured merge queue (BRANCHING.md leaves the method open) would
# otherwise generate "No merged pull requests in this range." for a fully
# active release.
MERGE_SUBJECT = re.compile(r"^Merge pull request #(\d+) from ")
SQUASH_SUBJECT = re.compile(r"\(#(\d+)\)\s*$")

# The closing keywords GitHub itself honours. A bare `#42` deliberately does not
# match: CONTRIBUTING.md draws the distinction that referring to an issue and
# resolving it are different claims, and `pr-issue-link.yml` enforces it.
CLOSES = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)\b", re.IGNORECASE)


@dataclass
class Change:
    """One merged pull request, as much of it as the notes need."""

    number: int
    title: str
    labels: list[str] = field(default_factory=list)
    issues: list[int] = field(default_factory=list)

    @property
    def area(self) -> str:
        return area_of(self.labels)


def pull_request_numbers(log: str) -> list[int]:
    """Every pull request number in a `git log --format=%s` block, in order, deduplicated."""
    numbers: list[int] = []
    for line in log.splitlines():
        line = line.strip()
        match = MERGE_SUBJECT.match(line) or SQUASH_SUBJECT.search(line)
        if match:
            number = int(match.group(1))
            if number not in numbers:
                numbers.append(number)
    return numbers


def unmatched_commits(log_with_shas: str) -> list[str]:
    """The commit shas whose subject names no pull request - the rebase-merge
    residue (#660), for main() to resolve through the API. Input is
    `git log --format=%H%x09%s`, one tab-separated line per commit."""
    shas: list[str] = []
    for line in log_with_shas.splitlines():
        sha, _, subject = line.partition("\t")
        subject = subject.strip()
        if not sha or not subject:
            continue
        if MERGE_SUBJECT.match(subject) or SQUASH_SUBJECT.search(subject):
            continue
        shas.append(sha.strip())
    return shas


def linked_issues(text: str) -> list[int]:
    """The issues a pull request body closes, in order, deduplicated."""
    issues: list[int] = []
    for match in CLOSES.finditer(text or ""):
        number = int(match.group(1))
        if number not in issues:
            issues.append(number)
    return issues


def area_of(labels: list[str]) -> str:
    """The first area label a change carries, or `other` when it carries none."""
    for area in AREAS:
        if area in labels:
            return area
    return "other"


def group_by_area(changes: list[Change]) -> dict[str, list[Change]]:
    """Changes bucketed by area, in AREAS order, with empty buckets omitted."""
    grouped: dict[str, list[Change]] = {}
    for area in [*AREAS, "other"]:
        matching = [change for change in changes if change.area == area]
        if matching:
            grouped[area] = matching
    return grouped


def hiker_facing(changes: list[Change]) -> list[Change]:
    """The changes a hiker could notice - everything not purely internal.

    The `not change.labels` half is load-bearing rather than defensive: the empty
    set is a subset of every set, so an unlabelled change would otherwise be
    classified as internal and silently left out of the notes. That is exactly
    backwards from the rule above, and it is the direction that under-reports a
    release.
    """
    return [change for change in changes if not change.labels or not set(change.labels).issubset(INTERNAL_ONLY)]


def slug(name: str) -> str:
    """`Springer Mountain` -> `springer-mountain`, for the notes filename."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _issue_link(number: int, repo: str) -> str:
    return f"[#{number}](https://github.com/{repo}/issues/{number})"


def render_notes(
    version: str,
    name: str,
    changes: list[Change],
    repo: str,
    previous: str | None = None,
    data_release: str | None = None,
    unvalidated: list[Change] | None = None,
) -> str:
    """The release notes draft. Everything a machine can know, and a TODO everywhere it cannot."""
    lines: list[str] = [f"# {version} — {name}", ""]

    if previous:
        lines += [f"_{len(changes)} changes since {previous}._", ""]
    else:
        lines += [f"_{len(changes)} changes. The first release._", ""]

    lines += [
        "<!-- TODO (human): the paragraph that makes this a release rather than a diff.",
        f"     Why {name} is this release's landmark, and what the release is actually for. -->",
        "",
        "## Named beside",
        "",
        "<!-- TODO (human): one figure from the trail's or hiking's history, per RELEASING.md §6.",
        "     Every claim cited. An invented anecdote here is the same class of defect as a water",
        "     source in the wrong place - do not write from memory. -->",
        "",
        "## What changed for a hiker",
        "",
    ]

    visible = hiker_facing(changes)
    if visible:
        lines += [
            "<!-- TODO (human): rewrite these in plain language, and delete any a hiker cannot see.",
            "     Generated from pull request titles, which are written for reviewers. -->",
            "",
        ]
        lines += [f"- {change.title}" for change in visible]
    else:
        lines.append("Nothing a hiker can observe. This release is internal work only.")
    lines.append("")

    lines += ["## What changed in the repository", ""]
    grouped = group_by_area(changes)
    if grouped:
        for area, items in grouped.items():
            lines += [f"### {area}", ""]
            for change in items:
                closes = ", ".join(_issue_link(issue, repo) for issue in change.issues)
                suffix = f" — {closes}" if closes else ""
                lines.append(f"- {change.title} ([#{change.number}](https://github.com/{repo}/pull/{change.number})){suffix}")
            lines.append("")
    else:
        lines += ["No merged pull requests in this range.", ""]

    lines += ["## Map data", ""]
    if data_release:
        lines += [f"This build reads the `{data_release}` data release.", ""]
    else:
        lines += [
            "No data release is pinned yet — `DATA_RELEASE` does not exist in the client "
            "(pipeline/DATA_RELEASES.md §4 is designed, not built).",
            "",
        ]

    lines += [
        "## What is not validated",
        "",
        "<!-- RELEASING.md §8d: this section is never empty, and a release whose author believes",
        "     it is has not looked. A hiker deciding whether to trust a direction cue is entitled",
        "     to know the thresholds behind it have never been tested under tree canopy. -->",
        "",
    ]
    if unvalidated:
        for change in unvalidated:
            lines.append(f"- {change.title} ({_issue_link(change.number, repo)})")
    else:
        lines.append("<!-- TODO (human): no issue carries `needs-field-testing`. Confirm that is true rather than unlabelled. -->")
    lines.append("")

    lines += [
        "## Compatibility",
        "",
        "<!-- TODO (human): anything a hiker must do — re-download, re-install, sign in again —",
        "     or the sentence saying nothing. RELEASING.md §8c. -->",
        "",
    ]

    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------------------
# The I/O half. Kept below the line, and kept short.
# --------------------------------------------------------------------------


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def _api(path: str, token: str) -> object:
    request = urllib.request.Request(
        f"{API_ROOT}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ourhike-release-notes",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed host, built above
        return json.load(response)


def _fetch_change(number: int, repo: str, token: str) -> Change | None:
    try:
        payload = _api(f"/repos/{repo}/pulls/{number}", token)
    except urllib.error.HTTPError as error:
        # A number parsed out of a commit subject that is not a pull request in
        # this repository. Worth saying rather than dropping silently, since the
        # symptom is otherwise a release note with a change missing from it.
        print(f"::warning::Could not read pull request #{number}: {error}", file=sys.stderr)
        return None
    assert isinstance(payload, dict)
    return Change(
        number=number,
        title=str(payload.get("title", "")).strip(),
        labels=[str(label["name"]) for label in payload.get("labels", [])],
        issues=linked_issues(str(payload.get("body") or "")),
    )


def _pulls_for_commit(sha: str, repo: str, token: str) -> list[int]:
    """The pull requests GitHub associates with one commit - how a
    rebase-merged change is found when its subject names nothing (#660)."""
    try:
        payload = _api(f"/repos/{repo}/commits/{sha}/pulls", token)
    except urllib.error.HTTPError as error:
        print(f"::warning::Could not read pull requests for {sha[:10]}: {error}", file=sys.stderr)
        return []
    assert isinstance(payload, list)
    return [int(item["number"]) for item in payload if isinstance(item, dict) and "number" in item]


def _fetch_unvalidated(repo: str, token: str) -> list[Change]:
    try:
        payload = _api(f"/repos/{repo}/issues?state=open&labels=needs-field-testing&per_page=100", token)
    except urllib.error.HTTPError as error:
        print(f"::warning::Could not list needs-field-testing issues: {error}", file=sys.stderr)
        return []
    assert isinstance(payload, list)
    return [
        Change(number=int(item["number"]), title=str(item["title"]).strip())
        for item in payload
        if isinstance(item, dict) and "pull_request" not in item
    ]


def _data_release() -> str | None:
    """The dataset this build pins, if the constant DATA_RELEASES.md §4 designs exists yet."""
    source = Path("client/src/lib/dataRelease.ts")
    if not source.exists():
        return None
    match = re.search(r"DATA_RELEASE\s*=\s*['\"]([^'\"]+)['\"]", source.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def resolve_span(version: str, previous: str | None) -> tuple[str | None, str]:
    """The commit range the notes describe: (previous, until).

    `until` is the version's own tag when that tag exists, and HEAD
    otherwise. The ordinary order is notes first, tag second (RELEASING.md
    §7), where HEAD is right; the other order is #860's incident - a tag
    with no notes - and there the notes must describe exactly what the tag
    contains, not whatever main has accumulated since it was cut (#905
    measured six merges' worth of drift in one evening).

    The `previous` default excludes the version's own tag for the same
    reason: for an already-tagged version, "the most recent tag" IS the
    version, and v1.0.1..HEAD is notes for a release containing none of
    the release.
    """
    tags = _git("tag", "--list", "v*", "--sort=-v:refname").split()
    until = version if version in tags else "HEAD"
    if not previous:
        candidates = [tag for tag in tags if tag != version]
        previous = candidates[0] if candidates else None
    return previous, until


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True, help="the version being released, e.g. v1.0.0")
    parser.add_argument("--name", required=True, help="its landmark name, e.g. 'Springer Mountain'")
    parser.add_argument("--previous", help="the previous tag. Defaults to the most recent one, if there is one.")
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", ""), help="owner/name")
    parser.add_argument("--out", help="where to write. Defaults to releases/<version>-<slug>.md")
    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        print("::error::GITHUB_TOKEN is not set, so pull request titles and labels cannot be read.", file=sys.stderr)
        return 1
    if not args.repo:
        print("::error::--repo or GITHUB_REPOSITORY is required.", file=sys.stderr)
        return 1

    previous, until = resolve_span(args.version, args.previous)

    span = f"{previous}..{until}" if previous else until
    log = _git("log", "--format=%H%x09%s", span)
    subjects = "\n".join(line.partition("\t")[2] for line in log.splitlines())
    numbers = pull_request_numbers(subjects)

    # Rebase merges leave commits whose subject names no pull request
    # (#660); the commit->pulls API is the record that still does. Only
    # numbers not already found by subject are added, in commit order.
    for sha in unmatched_commits(log):
        for number in _pulls_for_commit(sha, args.repo, token):
            if number not in numbers:
                numbers.append(number)

    print(f"{len(numbers)} pull requests in {span}.", file=sys.stderr)

    changes = [change for change in (_fetch_change(number, args.repo, token) for number in numbers) if change]
    notes = render_notes(
        version=args.version,
        name=args.name,
        changes=changes,
        repo=args.repo,
        previous=previous,
        data_release=_data_release(),
        unvalidated=_fetch_unvalidated(args.repo, token),
    )

    out = Path(args.out) if args.out else Path("releases") / f"{args.version}-{slug(args.name)}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(notes, encoding="utf-8")
    print(f"Wrote {out}.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
