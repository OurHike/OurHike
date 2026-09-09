"""A cache key that cannot repeat is a cache that only ever evicts.

`actions/cache/save` stores one entry per distinct key. A key ending in
`${{ github.run_id }}` is distinct on every run by construction, so the step
never overwrites - it adds. GitHub's per-repository cache is 10 GB and evicts
least-recently-used, which means a workflow saving large entries under
unrepeatable keys spends the whole repository's cache on itself and pushes
every other workflow's entry out.

publish-conditions.yml is what made this worth a test rather than a fix. It
runs on `cron: "40 * * * *"` with a two-way matrix, three saves a leg, and one
of those three carried a 27.6 MB USDM release plus a 12 MB centerline, 18.6 MB
of them compressed, saved fresh every run under a key that could not be hit
(measured on run #342, 2026-09-09). Its header has the full
arithmetic and the hypothesis it leads to: that this, rather than the 7-day
idle eviction publish-vector-data.yml's comment blames, is what leaves the
vector build's ~400 MB fetch-outputs entry cold. THAT HYPOTHESIS IS REASONED
AND UNMEASURED, and this test does not assert it - it asserts the cheaper,
checkable thing underneath it: a save key names its contents.

What this does NOT check, and deliberately:

- The SHAPE of a restore step. `key: <prefix>-${{ github.run_id }}` with
  `restore-keys: <prefix>-` is the documented idiom for "never hit exactly,
  take the most recent match", and it costs nothing because a restore stores
  nothing. Every restore in this directory is written that way and should
  stay that way. What IS checked is that a save's key still begins with
  something a restore looks up - see the pairing test below for why that one
  is worth a test and the shape is not.
- Whether a content hash actually stops a given entry churning. It does not,
  for two of publish-conditions.yml's three: both fetchers stamp this run's
  clock into the payload they cache, so the bytes move hourly and the hash
  moves with them. That is a defect in those scripts, recorded where it lives
  (the save steps' comments), and not something a workflow parser can see.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = REPO_ROOT / ".github" / "workflows"

# One exemption, by file and step name, with its reason - because a rule with
# a general escape hatch is not a rule.
#
# publish-vector-data.yml's "Save fetched data" saves ONCE PER RUN, from a
# workflow that runs on dispatch and on no schedule, so its key being unique
# per run adds one entry per publish rather than 48 a day. Its comment argues
# the coarse key deliberately: the fetchers decide what is stale, the restore
# takes the most recent entry by prefix, and a miss costs time rather than
# correctness. It is also the entry this rule exists to protect, which is the
# neat part - it is not the churn, it is what the churn evicts.
EXEMPT_SAVES = {
    ("publish-vector-data.yml", "Save fetched data"),
}

RUN_ID = "github.run_id"


def _workflows() -> list[Path]:
    return sorted(p for p in WORKFLOW_DIR.iterdir() if p.suffix in (".yml", ".yaml"))


def _steps(workflow: dict):
    """(job id, step) for every step of every job, skipping anything that is
    not shaped like a job or a step - a malformed workflow is CI's problem to
    report, not this test's to crash on."""
    for job_id, job in (workflow.get("jobs") or {}).items():
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if isinstance(step, dict):
                yield job_id, step


def _saves_a_cache(step: dict) -> bool:
    """Both spellings that write an entry.

    `actions/cache/save` is the explicit one this repository uses everywhere,
    for the reason publish-vector-data.yml records: the bundled action's post
    step is skipped when the job fails, which discards the work on exactly the
    runs a cache exists to rescue. The bundled `actions/cache@vN` is matched
    anyway, because it saves too and a workflow that adopted it would
    otherwise walk straight past this rule.
    """
    uses = str(step.get("uses", ""))
    if uses.startswith("actions/cache/restore"):
        return False
    return uses.startswith("actions/cache/save") or uses.startswith("actions/cache@")


def cache_saves() -> list[tuple[str, str, dict]]:
    found = []
    for path in _workflows():
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(workflow, dict):
            continue
        for job_id, step in _steps(workflow):
            if _saves_a_cache(step):
                found.append((path.name, job_id, step))
    return found


def publishing_workflows() -> list[tuple[str, dict]]:
    """The workflows that run publish.py.

    Matched on the literal command on its own line, which is
    test_publish_concurrency.py's idiom and carries its reasoning: a substring
    search for "publish.py" also finds a diagnostic step that imports from it
    and writes nothing.
    """
    found = []
    for path in _workflows():
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(workflow, dict):
            continue
        for _job_id, step in _steps(workflow):
            lines = (line.strip() for line in str(step.get("run", "")).splitlines())
            if "python publish.py" in lines:
                found.append((path.name, workflow))
                break
    return found


def test_no_cache_save_key_changes_every_run():
    offenders = []
    for name, job_id, step in cache_saves():
        if (name, step.get("name")) in EXEMPT_SAVES:
            continue
        key = str((step.get("with") or {}).get("key", ""))
        if RUN_ID in key:
            offenders.append(f"{name}:{job_id} - step {step.get('name')!r} saves under {key!r}")
    assert not offenders, (
        "These steps save a cache entry under a key that is different on every run, so they can only ever add entries "
        "and never hit one. On a scheduled workflow that is a standing eviction of everything else in the "
        "repository's 10 GB. Key them on hashFiles() over what is being saved instead, and guard the save with "
        "`hashFiles(...) != ''` over the same files, so a run that fetched nothing cannot compute the bare prefix "
        "itself as the key:\n  " + "\n  ".join(offenders)
    )


def test_the_exemption_still_names_a_real_step():
    """A guard on the escape hatch above.

    If "Save fetched data" is renamed or content-addressed, this exemption
    stops matching anything and silently protects nothing - and the test above
    goes on passing. Failing here forces the next person to delete the
    exemption along with its reasoning, or to fix the name.
    """
    named = {(name, step.get("name")) for name, _job_id, step in cache_saves()}
    missing = EXEMPT_SAVES - named
    assert not missing, (
        f"These exemptions no longer name a cache-saving step: {sorted(missing)}. Either the step was renamed - point "
        "the exemption at the new name - or it no longer saves under a per-run key, in which case delete the "
        "exemption and its comment rather than leaving a rule with a hole in it."
    )


def test_the_rule_has_something_to_check():
    """Five saves today, counted 2026-09-09: three in publish-conditions.yml,
    one in shard-seam-spike.yml, and publish-vector-data.yml's exempt one.
    Without this, a change to how caches are declared - or to
    `_saves_a_cache` - would turn the assertions above into a pass over an
    empty list, which is the vacuous green the rest of this directory guards
    against. The number is a floor rather than an equality: a sixth cache is
    somebody's ordinary work, a fifth that vanished is this file's business.
    """
    assert len(cache_saves()) >= 5


def _restore_lookups(workflow: dict) -> set[str]:
    """Every literal string a restore step in this workflow would find a key by.

    Both halves, because the two restores in this directory are written
    differently. `restore-keys` is a prefix search - the one publish-
    conditions.yml and publish-vector-data.yml use - and the exact `key` is
    how shard-seam-spike.yml's fixed-literal cache is found, with no
    restore-keys at all.
    """
    lookups: set[str] = set()
    for _job_id, step in _steps(workflow):
        if not str(step.get("uses", "")).startswith("actions/cache/restore"):
            continue
        with_block = step.get("with") or {}
        raw = with_block.get("restore-keys") or ""
        entries = raw if isinstance(raw, list) else str(raw).splitlines()
        lookups.update(entry.strip() for entry in map(str, entries) if entry.strip())
        key = str(with_block.get("key", "")).strip()
        if key:
            lookups.add(key)
    return lookups


def test_every_save_key_starts_with_something_a_restore_looks_up():
    """A save whose key no restore searches for is a cache that only writes.

    This is the failure mode content addressing introduces and that nothing
    else here would catch, because it is silent in both directions: the save
    step goes green, the restore step goes green reporting a miss, and the
    only symptom is the work the cache existed to avoid being done again -
    for publish-conditions.yml's ATC leg, its own comment puts that at 99
    requests an hour to ATC, hourly, forever.

    HONESTLY: this would pass against the `github.run_id` keys it was written
    alongside, so it is not evidence for that change. It is a standing
    invariant, of the kind this directory keeps, and the edit it is waiting
    for is somebody renaming one half of a pair.
    """
    offenders = []
    for path in _workflows():
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(workflow, dict):
            continue
        lookups = _restore_lookups(workflow)
        for job_id, step in _steps(workflow):
            if not _saves_a_cache(step):
                continue
            key = str((step.get("with") or {}).get("key", ""))
            # The literal head of the key: everything before the first
            # expression, which is the only part a prefix search can match on
            # because `${{ ... }}` is whatever this run evaluates it to.
            literal = key.split("${{")[0]
            if literal and (literal in lookups or key.strip() in lookups):
                continue
            offenders.append(
                f"{path.name}:{job_id} - step {step.get('name')!r} saves under {key!r}, and no restore step in that "
                f"workflow looks up {literal!r}. Restores search: {sorted(lookups)}"
            )
    assert not offenders, (
        "These cache entries are written and never read. Either the save key's prefix or the restore's "
        "`restore-keys` was changed without the other, which is invisible at runtime - both steps stay green and the "
        "cache simply stops working:\n  " + "\n  ".join(offenders)
    )


HASH_FILES_ARGS = re.compile(r"hashFiles\(([^)]*)\)")


def _same_call(args: str) -> str:
    return " ".join(args.split())


def test_a_content_addressed_save_guards_on_the_files_it_hashes():
    """`hashFiles()` returns '' when nothing matched, and '' interpolates.

    So `key: foo-${{ hashFiles('x') }}` on a run where `x` is missing is the
    key `foo-` - the bare prefix the restore beside it searches on. The guard
    that stops that has to hash the SAME files as the key: a step guarded on
    one path and keyed on another can still compute the bare prefix, and
    would read as protected.

    What it does not do is prevent an empty entry: the action refuses to save
    when no path resolves at all (`saveCache`'s Path Validation Error, read
    2026-09-09). publish-conditions.yml's ATC save carries that correction in
    full; this test is about the key being well formed either way, which is
    the part that is cheap to state and cheap to check.

    HONESTLY: vacuous against a key with no hashFiles in it, so this would
    also have passed before the change it was written for.
    """
    offenders = []
    for name, job_id, step in cache_saves():
        key = str((step.get("with") or {}).get("key", ""))
        hashed = [_same_call(args) for args in HASH_FILES_ARGS.findall(key)]
        if not hashed:
            continue
        guarded = {_same_call(args) for args in HASH_FILES_ARGS.findall(str(step.get("if", "")))}
        for call in hashed:
            if call not in guarded:
                offenders.append(
                    f"{name}:{job_id} - step {step.get('name')!r} keys on hashFiles({call}) but its `if` does not "
                    f"guard on the same call"
                )
    assert not offenders, (
        "These steps can compute a key that is the bare prefix, on any run where the files they hash are absent - a "
        "restore-keys lookup searches on exactly that string. Add `hashFiles(...) != ''` over the same files to the "
        "step's `if`:\n  " + "\n  ".join(offenders)
    )


def test_every_publishing_workflow_caches_pip():
    """`cache: pip` on setup-python, in the workflows that publish.

    Four of the five had it and publish-conditions.yml did not (checked across
    the directory 2026-09-09), which is why this is checked rather than
    remembered: it is one line, it is invisible when missing, and the workflow
    it was missing from installs pipeline/requirements.txt 48 times a day.

    `cache-dependency-path` is checked with it because `cache: pip` alone
    hashes every requirements file in the tree, so a pin in backend/ or
    .github/tests/ - neither of which any of these jobs installs - would move
    the key and discard the entry.
    """
    offenders = []
    for name, workflow in publishing_workflows():
        for job_id, step in _steps(workflow):
            if not str(step.get("uses", "")).startswith("actions/setup-python"):
                continue
            with_block = step.get("with") or {}
            if with_block.get("cache") != "pip":
                offenders.append(f"{name}:{job_id} - setup-python without `cache: pip`")
            elif not with_block.get("cache-dependency-path"):
                offenders.append(f"{name}:{job_id} - setup-python caches pip without a `cache-dependency-path`")
    assert not offenders, (
        "These publishing workflows install their dependencies from PyPI on every run. Add to the setup-python "
        "step:\n\n          cache: pip\n          cache-dependency-path: pipeline/requirements.txt\n\n  " + "\n  ".join(offenders)
    )


def test_there_are_publishing_workflows_to_check():
    """The same guard test_publish_concurrency.py keeps on the same matcher,
    for the same reason: five writers today, and a move of the publish step
    out of `run:` would otherwise make the test above pass over nothing."""
    assert len(publishing_workflows()) >= 5
