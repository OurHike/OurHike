"""An artifact handed between jobs comes back where the next job looks for it.

`actions/upload-artifact@v4` does not store the paths you give it. It roots
the archive at the LEAST COMMON ANCESTOR of its search paths and stores
everything relative to that, so the archive's shape depends on the whole path
list rather than on any one entry. The matching `download-artifact` must
therefore extract to exactly that ancestor for the files to land back where
they started.

WHAT GETTING IT WRONG COST (#1347). publish-vector-data.yml uploaded

    pipeline/data/processed/
    pipeline/data/raw/poi_images_atc.json          (and five more raw/ files)

whose least common ancestor is `pipeline/data`, and extracted it to
`pipeline/`. The exports landed at `pipeline/processed/`, publish.py found
nothing under `pipeline/data/processed/`, returned normally, and the workflow
reported "Published to <env>" having uploaded not one byte. Runs #93, #94 -
that one against production - and #98 all did this, every run that reached the
publish job between the job split in #1267 and the fix.

Nothing caught it because each half is locally correct. The upload names real
files; the download names a real directory; only their *agreement* is wrong,
and no single file contains it. That is what this test is for, and it is why
the check lives here rather than in either workflow.

The rule: a download must RECONSTRUCT what the upload archived, so its `path:`
equals the least common ancestor of the upload's paths. `RELOCATIONS` holds
the pairs that deliberately do not, each with the reason.
"""

from __future__ import annotations

import posixpath
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

GLOB_CHARS = set("*?[")

# Pairs whose download deliberately puts the files somewhere other than where
# they were built. Each needs a reason: an entry here is an assertion that the
# consumer knows the new location, not a way to quiet the test.
RELOCATIONS = {
    # pages.yml builds the app at `_site/app` and consumes it as a directory
    # named `app-dist`, which it then assembles into the deployed site. The
    # rename is the point; nothing downstream refers to `_site/app`.
    ("pages.yml", "app-dist"),
}


def _workflows():
    return sorted(p for p in WORKFLOW_DIR.iterdir() if p.suffix in (".yml", ".yaml"))


def _steps(doc):
    for job in (doc.get("jobs") or {}).values():
        if isinstance(job, dict):
            yield from (job.get("steps") or [])


def _search_paths(raw) -> list[str]:
    """The upload's `path:` as a list, minus blanks and `!` exclusions.

    An exclusion narrows what is collected but never deepens the archive
    root, so it cannot move the least common ancestor and is dropped here.
    """
    lines = raw.splitlines() if isinstance(raw, str) else [raw]
    return [line.strip() for line in lines if line.strip() and not line.strip().startswith("!")]


def _root_candidate(path: str) -> str:
    """What one search path contributes to the least common ancestor.

    A glob contributes the deepest directory above the first globbed
    component - `data/processed/*.pmtiles` matches only inside
    `data/processed`, so that is as deep as the root can go.
    """
    parts = posixpath.normpath(path).split("/")
    for index, part in enumerate(parts):
        if GLOB_CHARS & set(part):
            return "/".join(parts[:index])
    return "/".join(parts)


def _least_common_ancestor(paths: list[str]) -> str:
    candidates = [_root_candidate(p) for p in paths]
    if len(candidates) == 1:
        only, raw = candidates[0], paths[0].strip()
        # One search path is its own root when it names a directory, and its
        # parent when it names a single file. A trailing slash settles it; a
        # suffix is the fallback signal, since a bare `dist` is a directory
        # and `cells.json` is not.
        if raw.endswith("/") or not posixpath.splitext(only)[1]:
            return only
        return posixpath.dirname(only)
    return posixpath.commonpath(candidates)


def _handoffs():
    """Every (workflow, artifact name) uploaded in one job and downloaded in
    another, with the upload's paths and the download's destination."""
    found = []
    for path in _workflows():
        doc = yaml.safe_load(path.read_text()) or {}
        uploads, downloads = {}, {}
        for step in _steps(doc):
            uses = step.get("uses")
            if not isinstance(uses, str):
                continue
            with_ = step.get("with") or {}
            name = with_.get("name")
            if uses.startswith("actions/upload-artifact") and name:
                uploads[name] = _search_paths(with_.get("path"))
            elif uses.startswith("actions/download-artifact") and name:
                downloads[name] = with_.get("path")
        for name in sorted(set(uploads) & set(downloads), key=str):
            # A download with no `path:` extracts into the workspace root,
            # which is its own shape of decision and not this rule's business.
            if downloads[name] and uploads[name]:
                found.append((path.name, name, uploads[name], downloads[name]))
    return found


HANDOFFS = _handoffs()


def test_there_are_handoffs_to_check():
    """A rename that made this file silently vacuous would be worse than the
    bug it exists for, so the fixture asserts itself."""
    assert HANDOFFS, "no upload/download artifact pairs found - has the parsing drifted?"


@pytest.mark.parametrize(
    ("workflow", "name", "uploaded", "destination"),
    HANDOFFS,
    ids=[f"{w}:{n}" for w, n, _, _ in HANDOFFS],
)
def test_download_reconstructs_the_upload(workflow, name, uploaded, destination):
    if (workflow, name) in RELOCATIONS:
        pytest.skip(f"{workflow}:{name} deliberately relocates - see RELOCATIONS")

    ancestor = _least_common_ancestor(uploaded)
    landed = posixpath.normpath(destination)

    assert landed == ancestor, (
        f"{workflow}: artifact {name!r} is uploaded from paths whose least common\n"
        f"ancestor is {ancestor!r}, so the archive holds everything relative to that -\n"
        f"but it is extracted to {landed!r}. The files will land at\n"
        f"{posixpath.join(landed, posixpath.basename(ancestor))!r} rather than back where\n"
        f"they were built, and whatever reads them next will find an empty directory.\n"
        f"Set the download's `path:` to {ancestor!r}, or add ({workflow!r}, {name!r}) to\n"
        f"RELOCATIONS with the reason the move is deliberate.\n"
        f"Uploaded paths: {uploaded}"
    )
