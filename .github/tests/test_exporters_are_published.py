"""Every exporter is run by something, or says why not (#940).

THE FAILURE THIS EXISTS TO CATCH is an exporter merging without its publish
leg, and nothing reporting the gap. It has now happened four times:

  - #729 and #735, the drought bands - rebuilt hourly, uploaded never.
  - #940 itself: `highlights.json` had an exporter, a reference file, tests
    and a place in `publish.py`'s manifest list, and no workflow ran the
    script. Three weeks passed before anybody noticed the curated stretches
    were not on anyone's phone.
  - `export_nynjtc_alerts.py`, found by the first run of this test:
    registered in sources.json with `reaches_hikers: true` and a maintainer's
    authorisation, exported to a manifest `publish.py` already collects, and
    invoked by nothing. `conditions/nynjtc_alerts.json` was 404 on production
    (measured 2026-08-27) while `conditions/atc_updates.json` beside it was
    200.

Each time the app degraded politely - `fetchOptionalArtifact` reads a 404 as
"this release has no such artifact", which is right for an older release and
indistinguishable from this - and each time it was found by somebody wondering
why a screen was empty.

WHY THE WIRING AND NOT THE BUCKET. #940 proposed the invariant as "every
artifact an exporter can write is either present in the bucket or explicitly
declared optional-and-absent". That check has to know WHICH ENVIRONMENT it is
judging, because absent from production while present in UA is a normal
mid-promotion state - which was the true cause of one of #940's three, and is
a thing this test would be wrong to call a defect. Reading two directories of
this repository has no such ambiguity, needs no credentials and no network,
and catches the cause all four instances actually shared: nothing ran the
script. The bucket-contents half is still worth having and is not this.

WHAT COUNTS AS "RUN". Any mention of the exporter's filename anywhere under
.github/workflows/ or .github/actions/, which is deliberately loose: a step
may invoke it as `python x.py`, through a venv path, inside a shell block, or
from a composite action, and pinning the form would make this test fail on a
refactor rather than on a defect. A filename appearing in a comment and
nowhere else would pass this and should not - the looseness is the trade, and
the alternative is a parser that is wrong in the other direction.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PIPELINE = REPO_ROOT / "pipeline"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
ACTIONS = REPO_ROOT / ".github" / "actions"

#: Exporters that deliberately have no runner, each with the reason. An entry
#: here is a decision somebody made, not a backlog item - a script that OUGHT
#: to run and does not belongs in a workflow, not on this list. Empty today,
#: and that is the honest state: every exporter in the checkout is wired.
#:
#: If you are adding a name here to make this test pass, that is the moment
#: the test is doing its job. Read the four instances in the module docstring
#: first.
UNWIRED: dict[str, str] = {}


def _exporters() -> list[Path]:
    return sorted(PIPELINE.glob("export_*.py"))


def _invocation_text() -> str:
    """Every workflow and composite action, as one blob to search."""
    parts = []
    for directory, pattern in ((WORKFLOWS, "*.yml"), (ACTIONS, "**/*.yml")):
        if not directory.exists():
            continue
        for path in sorted(directory.glob(pattern)):
            parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_there_are_exporters_to_check():
    """The guard on the guard.

    A glob that silently matched nothing would make every assertion below
    vacuously true, which is the shape of failure this repository keeps
    finding: a check that did not run reading exactly like a check that
    passed.
    """
    assert len(_exporters()) >= 15


def test_the_workflows_are_readable():
    text = _invocation_text()
    assert "runs-on" in text, "no workflow content was read"


def test_every_exporter_is_invoked_by_a_workflow():
    text = _invocation_text()
    missing = [path.name for path in _exporters() if path.name not in text and path.name not in UNWIRED]

    assert not missing, (
        "exporter(s) that nothing runs: "
        + ", ".join(missing)
        + ". An exporter no workflow invokes writes nothing, so publish.py "
        "uploads nothing and the app degrades politely and silently - see "
        "#940. Wire it into the workflow that should run it, or add it to "
        "UNWIRED above with the reason it deliberately has none."
    )


def test_the_allowlist_names_only_real_exporters():
    """A stale allowlist entry is a hole nobody can see.

    An exporter that was renamed or deleted leaves its excuse behind, and the
    next file to take that name inherits an exemption nobody granted.
    """
    names = {path.name for path in _exporters()}
    stale = sorted(set(UNWIRED) - names)

    assert not stale, f"UNWIRED names exporters that no longer exist: {stale}"


def test_every_allowlist_entry_carries_a_reason():
    empty = sorted(name for name, why in UNWIRED.items() if not why.strip())

    assert not empty, f"UNWIRED entries with no reason: {empty}"
