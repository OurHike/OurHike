"""state_base: whether CI's dbt job builds a pull request from main's last build, by dbt state.

    python state_base.py --matched-key KEY --base-dir DIR --head-manifest dbt/target/manifest.json \\
        --warehouse data/warehouse.duckdb [--github-output "$GITHUB_OUTPUT"]

The maintainer, 2026-10-15: on 2a826f01 the dbt job's build step, "dbt build, the Python
steps and the pub_ writers (build_marts.py)", took 16 min 7 s (Pipeline tests
run 38773605297), and every pull request paid it whole. So a push to main
keeps its fixture build, and a pull request starts from it and rebuilds only
what changed (build_marts.py --state-base, its docstring's "A PULL REQUEST
BUILDS ONLY WHAT CHANGED SINCE MAIN'S LAST BUILD").

WHAT MAIN KEEPS. pipeline-tests.yml's dbt job, on a push to main and after a
build that passed, copies the fixture warehouse and the manifest it was built
with into $RUNNER_TEMP/dbt-ci-base/ (warehouse.duckdb, target/manifest.json)
and saves that to the Actions cache under KEY_PREFIX and the commit. Nothing
else saves it: not a pull request, not a merge-queue entry.

WHAT A PULL REQUEST DECIDES, here, before the fixture load: a state build only
when every one of these holds, and today's full build otherwise, said in one
`::notice` and in the log (decide()):
1. the cache step matched an entry, and its key names a commit;
2. the entry holds both files;
3. that commit can be fetched, and `git diff --name-only --no-renames` from it
   to HEAD (the pull request's merge commit) lists only paths RULES lets
   through. The warehouse was built from that commit's code over that
   commit's fixtures, so this diff is everything the state build must see;
4. no macro differs between the cached manifest and this checkout's (the dbt
   job's "dbt parse" step leaves it at dbt/target/manifest.json), below,
   "MACROS ARE COMPARED BY CONTENT".
Then the cached warehouse moves to --warehouse, where the fixture load writes
its raw tables over the cached ones, and `dir=` names the cached target/ for
the build step's --state-base.

THE RULES (RULES): the first pattern a changed path matches decides it, and a
path none matches forces the full build. A rule lets a path through only when
dbt's state:modified sees its change, or when no build reads it at all. dbt
2.0.6 was measured seeing three kinds on 2026-10-15 (`dbt ls -s
state:modified --state` between two parses of this project at 2a826f01, the
build's own environment): a comment added to stg_atc__shelters.sql selected
that model and its 6 tests; one character added to notice_words.csv selected
that seed; and a comment added inside row_history_mart() selected the 11 marts
that call it. A snapshot's or a singular test's file is compared the same way
as a model's (Reasoned: each is a node with a checksum of its own file, as the
model was). pipeline/tests/ and the documents at pipeline/'s top go through
because no build reads them. Everything else under pipeline/ forces the full
build, because it can change what no node's checksum holds:
- the raw tables: the fixture generator (make_dbt_fixtures.py), the extract
  (extract/, lib/, .dlt/, sources.json, reference/), and what they import;
- the generated models (generate_dbt.py and its two generators);
- a Python step, build_marts.py itself, row_history.py;
- how dbt runs: dbt_project.yml (state:modified reads no var), packages.yml,
  package-lock.yml, profiles.yml, the requirements files;
- a macro or a generic test (a generic test is a macro), below.
Outside pipeline/ the dbt job reads only its own workflow and the
changed-paths action, which its scope list in pipeline-tests.yml says and
.github/tests/test_dbt_state_build.py holds to these rules; both force the
full build, and every other path outside pipeline/ goes through.

MACROS ARE COMPARED BY CONTENT. dbt 2.0.6 does mark a model modified when a
macro it calls changes (the row_history_mart() probe above), but a probe of
2026-10-08 (build_marts.py's docstring, "A PULL REQUEST RUNS
THE CHECKS ITS CHANGE REACHES") found a comment in a dispatched override,
macros/elementary_overrides.sql, and one in Elementary's own
test_volume_anomalies.sql each selecting nothing. And two of the generated
files are macros (macros/generated_regions.sql and
macros/generated_notice_regions.sql) whose generators read files a rule lets
through: generate_notice_models.py reads seeds/notice_source_fields.csv and
seeds/notice_steward_areas.csv. So every macro's text, the packages' and the
generated ones' included, is compared here, and one that differs forces the
full build whichever path changed it. A parse with Elementary's switch on and
one with it off hold the same 2,052 macros, each with the same text (measured
2026-10-15 at 2a826f01), so the "dbt parse" step's manifest, parsed with it
off, compares with the cached one, parsed with it on.

NEVER A FAILURE. Whatever this cannot answer is a full build, with the reason:
a state build is an optimisation, and a pull request must never go red
because main's build could not be found.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

#: The Actions cache key's head; pipeline-tests.yml's save writes KEY_PREFIX + the commit, and its restore looks the
#: prefix up. .github/tests/test_dbt_state_build.py holds the workflow to it.
KEY_PREFIX = "dbt-ci-base-"
#: The cached directory's two files, as the save step writes them.
WAREHOUSE_NAME = "warehouse.duckdb"
MANIFEST_IN_BASE = Path("target") / "manifest.json"

STATE, FULL = "state", "full"
#: (pattern, verdict, why). The first pattern a changed path matches decides it; `**` is any run of characters,
#: slashes included, and `*` any run within one folder. A path no pattern matches forces the full build. The module
#: docstring, "THE RULES", has the measurements.
RULES: tuple[tuple[str, str, str], ...] = (
    (
        "pipeline/dbt/tests/generic/**",
        FULL,
        "a generic test, which is a macro, and macros are compared by content, not by dbt's state comparison",
    ),
    ("pipeline/dbt/models/**", STATE, "a model's SQL, YAML or docs, which dbt's state:modified compares"),
    ("pipeline/dbt/seeds/**", STATE, "a seed or its YAML, which dbt's state:modified compares"),
    ("pipeline/dbt/snapshots/**", STATE, "a snapshot, which dbt's state:modified compares"),
    ("pipeline/dbt/tests/**", STATE, "a singular test, which dbt's state:modified compares"),
    ("pipeline/tests/**", STATE, "a pytest file, which no build reads"),
    ("pipeline/*.md", STATE, "a document, which no build reads"),
    (
        "pipeline/**",
        FULL,
        "it can change the raw tables, the generated models, a Python step, a macro or how dbt runs, none of which "
        "dbt's state:modified sees",
    ),
    (".github/workflows/pipeline-tests.yml", FULL, "the workflow that runs the build"),
    (".github/actions/**", FULL, "an action the workflow runs"),
    ("**", STATE, "outside pipeline/, which no build reads"),
)


def _pattern(glob: str) -> re.Pattern[str]:
    """`glob` as a whole-path regex: `**` any characters, `*` any but a slash, everything else itself."""
    parts = []
    for index, piece in enumerate(glob.split("**")):
        if index:
            parts.append(".*")
        parts.append("[^/]*".join(re.escape(each) for each in piece.split("*")))
    return re.compile("".join(parts) + r"\Z")


_COMPILED = tuple((_pattern(glob), verdict, why) for glob, verdict, why in RULES)


def verdict(path: str) -> tuple[str, str]:
    """(STATE or FULL, why) for one changed path, by the first rule it matches; FULL when none does."""
    for pattern, answer, why in _COMPILED:
        if pattern.match(path):
            return answer, why
    return FULL, "no rule names it"


def path_problems(paths: list[str]) -> list[str]:
    """Each changed path that forces the full build, with why; none when every one goes through."""
    found = []
    for path in paths:
        answer, why = verdict(path)
        if answer == FULL:
            found.append(f"{path} changed: {why}")
    return found


def _macro_sql(manifest: dict) -> dict[str, str | None]:
    return {uid: (macro or {}).get("macro_sql") for uid, macro in (manifest.get("macros") or {}).items()}


def macro_problems(head: dict, base: dict) -> list[str]:
    """One sentence when any macro's text differs between two manifests (the module docstring, "MACROS ARE COMPARED
    BY CONTENT"), or when either holds none to compare; none when every macro is the same."""
    mine, theirs = _macro_sql(head), _macro_sql(base)
    if not mine or not theirs:
        return [f"{'this checkout' if not mine else 'the cached build'}'s manifest holds no macro to compare"]
    changed = sorted(uid for uid in mine.keys() | theirs.keys() if mine.get(uid) != theirs.get(uid))
    if not changed:
        return []
    shown = ", ".join(changed[:3]) + (f" and {len(changed) - 3} more" if len(changed) > 3 else "")
    return [
        f"{len(changed)} macro(s) differ from the cached build's ({shown}), and dbt's state comparison does not see every macro"
    ]


def commit_of(matched_key: str) -> str | None:
    """The commit in a cache key KEY_PREFIX wrote: 40 lowercase hex digits, else None."""
    commit = matched_key.removeprefix(KEY_PREFIX) if matched_key.startswith(KEY_PREFIX) else ""
    return commit if re.fullmatch(r"[0-9a-f]{40}", commit) else None


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=False)


def changed_paths(commit: str) -> tuple[list[str] | None, str]:
    """Every path that differs between `commit` and HEAD, fetching `commit` alone when this shallow checkout lacks it:
    (paths, "") or (None, why not)."""
    if _git("cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
        fetched = _git("fetch", "--quiet", "--depth=1", "origin", commit)
        if fetched.returncode != 0:
            return None, f"its commit {commit[:12]} could not be fetched ({fetched.stderr.strip()[-200:] or fetched.returncode})"
    listed = _git("diff", "--name-only", "--no-renames", commit, "HEAD")
    if listed.returncode != 0:
        return None, f"git diff from {commit[:12]} failed ({listed.stderr.strip()[-200:] or listed.returncode})"
    return [line for line in listed.stdout.splitlines() if line.strip()], ""


def _read_manifest(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def decide(matched_key: str, base_dir: Path, head_manifest: Path) -> tuple[str, str, list[str]]:
    """(STATE or FULL, the one-line reason, the log's lines) for the cache entry `matched_key` restored into
    `base_dir` (the module docstring, "WHAT A PULL REQUEST DECIDES")."""
    if not matched_key:
        return FULL, "no build of main is cached for this pull request to start from", []
    commit = commit_of(matched_key)
    if commit is None:
        return FULL, f"the cache entry {matched_key!r} names no commit", []
    missing = [name for name in (WAREHOUSE_NAME, str(MANIFEST_IN_BASE)) if not (base_dir / name).is_file()]
    if missing:
        return FULL, f"main's cached build of {commit[:12]} lacks {' and '.join(missing)}", []
    paths, why = changed_paths(commit)
    if paths is None:
        return FULL, f"main's cached build of {commit[:12]} cannot be compared: {why}", []
    log = [f"{verdict(path)[0]:5}  {path}  ({verdict(path)[1]})" for path in paths]
    if problems := path_problems(paths):
        more = f" (and {len(problems) - 1} more path(s))" if len(problems) > 1 else ""
        return FULL, f"since main's cached build of {commit[:12]}, {problems[0]}{more}", log
    head, base = _read_manifest(head_manifest), _read_manifest(base_dir / MANIFEST_IN_BASE)
    if head is None or base is None:
        unread = head_manifest if head is None else base_dir / MANIFEST_IN_BASE
        return FULL, f"{unread} could not be read, so the macros cannot be compared", log
    if problems := macro_problems(head, base):
        return FULL, f"since main's cached build of {commit[:12]}, {problems[0]}", log
    return (
        STATE,
        f"{len(paths)} path(s) changed since main's cached build of {commit[:12]}, each one dbt's state:modified sees "
        "or no build reads, and no macro differs",
        log,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--matched-key", default="", help="the cache step's cache-matched-key output (empty: no entry)")
    parser.add_argument("--base-dir", type=Path, required=True, help="where the cache step restored main's build")
    parser.add_argument("--head-manifest", type=Path, required=True, help="this checkout's parsed manifest")
    parser.add_argument("--warehouse", type=Path, required=True, help="where the build reads its warehouse")
    parser.add_argument("--github-output", type=Path, help="$GITHUB_OUTPUT: `dir=` the cached target/, for a state build")
    args = parser.parse_args(argv)
    try:
        answer, reason, log = decide(args.matched_key, args.base_dir, args.head_manifest)
        if answer == STATE:
            args.warehouse.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(args.base_dir / WAREHOUSE_NAME), str(args.warehouse))
    except Exception as failed:  # noqa: BLE001 - the module docstring, "NEVER A FAILURE"
        answer, reason, log = FULL, f"the decision itself failed ({type(failed).__name__}: {failed})", []
    for line in log:
        print(f"-- state_base: {line}", flush=True)
    if answer == STATE:
        print(f"::notice title=State build::Only what changed and what it reaches is rebuilt: {reason}.", flush=True)
        if args.github_output:
            with args.github_output.open("a", encoding="utf-8") as output:
                output.write(f"dir={(args.base_dir / MANIFEST_IN_BASE).parent}\n")
    else:
        print(f"::notice title=Full fixture build::Every node is built: {reason}.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
