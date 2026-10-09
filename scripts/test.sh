#!/usr/bin/env bash
#
# Run the suites this branch actually affects, the way CI decides it.
#
# CONTRIBUTING.md asks for every suite before every push, and that is the
# right instruction for a rule nobody can automate away - a push that fails on
# formatting spends a full CI round trip learning something ruff would have
# said in a second. What it costs is 294s, measured, for a change that could
# only have broken one part, which is most changes here. CI already solved
# this: .github/actions/changed-paths asks which files a pull request touches
# and skips the suites none of them reach. This is that same decision, made
# locally, before the push rather than after it.
#
# The same four suites through here are 174s, and a change to one of the
# Python parts is 20 to 50 seconds.
#
#   scripts/test.sh             the suites this branch's changes affect
#   scripts/test.sh --all       every suite, the way a push to main runs them
#   scripts/test.sh --no-flow   skip the browser-driven flow suite
#   scripts/test.sh --list      what would run and why, without running it
#   scripts/test.sh --since X   compare against X rather than origin/main
#   scripts/test.sh --coverage  measure coverage too, as CI does
#   scripts/test.sh --no-dbt-deps  use pipeline/dbt/dbt_packages/ as it is
#
# THE DBT SUITE is pipeline-tests.yml's `dbt` job: SQLFluff and dbt lint,
# then dbt against fixtures, the evaluator enforced. It needs a toolchain
# this script does not install - the dbt version requirements-dbt.txt pins,
# first on PATH, with that environment's python and sqlfluff beside it - and is
# SKIPPED, said in the last line, without one. --no-dbt-deps is for a
# sandbox whose proxy cannot fetch dbt's package tarballs: put the packages
# in dbt_packages/ by hand (the dbt skill has the clone commands) and skip
# the step that would empty it.
#
# COVERAGE IS OFF UNLESS ASKED FOR, and that is a saving rather than a
# shortcut: it is visibility-only in all four suites by deliberate decision -
# no threshold, nothing that can fail - so leaving it out cannot change a
# green run into a red one or the reverse. It is not free, though. Measured
# here, as this script runs them: 148s against 100s for the client, 20s
# against 16s for the backend. CI still measures it on every run, which is
# where the report is actually read.
#
# THE SCOPE LISTS ARE READ, NOT COPIED. Each suite's paths come out of its own
# workflow YAML at run time, so this script cannot drift from CI by being
# forgotten - that is CONTRIBUTING.md's one-home-per-item rule applied to the
# one place where a second copy would be invisible until it was wrong. Adding
# a path to a workflow changes what this runs, in the same edit.
#
# THE UNCERTAIN ANSWER IS ALWAYS "RUN". The changed-paths action says why, and
# it holds here for the same reason: running a suite that did not need to run
# costs a minute, and skipping one that did costs a merge, quietly. No git
# base, no PyYAML, an unreadable workflow, a detached head - every one of them
# runs everything rather than guessing.
#
# WHAT IT DOES NOT DO. It does not select individual tests. TESTING.md's CI
# section rules that out on purpose: inferring which test covers which source
# file can be wrong in the direction of not running a test that would have
# failed, and at these suite sizes there is nothing left to win. Per part is
# the whole of the mapping, here as in CI.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# WHICH INTERPRETER RUNS THE PYTHON SUITES (#859). This script used to shell
# out to bare `python` and `python3` ten times with no selection at all, while
# .claude/hooks/session-start.sh went to real trouble to install everything
# under the interpreter CI uses - so on a web session the hook provisioned
# 3.13 and this script ran Debian's 3.11, and the one command CLAUDE.md names
# died on its first step with "No module named ruff". Worse than a failure:
# that message reads as a missing package, and `pip install ruff` into 3.11
# cannot satisfy the pins, so the actionable-looking diagnosis is the wrong
# one.
#
# The selection is shared with the hook (scripts/pick_python.sh - one home,
# so the install side and the run side cannot decide differently again), and
# probed rather than inferred: bare `python` first, because a developer's
# activated venv is exactly the interpreter they installed into and must win.
# Two answers, because the needs differ - the suites need ruff and pytest,
# while reading the workflow scope lists needs only yaml (which the web
# image's 3.11 does have, as a Debian dist-package). One combined probe would
# fail the scope reading for want of tools it never uses.
. scripts/pick_python.sh
PY="$(python_with ruff pytest || true)"
SCOPE_PY="$(python_with yaml || echo python3)"

run_all=false
list_only=false
with_coverage=false
skip_flow=false
skip_dbt_deps=false
base_ref=""
while [ $# -gt 0 ]; do
  case "$1" in
    --all) run_all=true ;;
    --list) list_only=true ;;
    --coverage) with_coverage=true ;;
    --no-flow) skip_flow=true ;;
    --no-dbt-deps) skip_dbt_deps=true ;;
    # The missing-value case checked here, not left to `shift` (#660): a
    # trailing `--since` used to hit the loop's own shift with nothing
    # left, and `set -e` killed the script with exit 1 and no output - the
    # silent failure the --since block below promises not to have.
    --since)
      shift
      [ $# -gt 0 ] || { echo "--since needs a ref (try --help)" >&2; exit 2; }
      base_ref="$1"
      ;;
    # The header block, however long it happens to be - printed by walking
    # from the shebang to the first line that is not a comment, rather than
    # from a line range that silently starts truncating the help the next time
    # a paragraph is added. It already had.
    -h|--help) awk 'NR==1{next} /^#/{sub(/^# ?/,""); print; next} {exit}' "$0"; exit 0 ;;
    *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
  shift
done

# An explicit --since that names nothing is the one uncertainty this script
# does NOT answer by running everything. The rest are conditions a checkout can
# arrive in on its own; this one is a typo, and quietly running all four suites
# would hide it behind three minutes of green. Checked here rather than inside
# resolve_base, because that is called from a command substitution and an
# `exit` there would end the subshell and let the caller carry on regardless.
if [ -n "$base_ref" ] && ! git rev-parse --verify --quiet "$base_ref^{commit}" >/dev/null; then
  echo "--since: no such commit: $base_ref" >&2
  exit 2
fi

# ---------------------------------------------------------------------------
# What changed
# ---------------------------------------------------------------------------

# Committed work on this branch, plus everything not committed yet. The second
# half is the point of running locally at all: the change being tested is
# usually still in the working tree, and a diff against the merge base alone
# would miss the edit that is about to break something. Untracked files count
# too - a new test file is exactly the kind of thing that decides a suite.
changed_files() {
  local base="$1"
  # --no-renames so a rename reports BOTH paths (#660). With detection on -
  # git's default - a rename lists only the new path, while CI's
  # changed-paths action deliberately maps old+new: a file renamed OUT of a
  # suite's scope would run that suite in CI and not here.
  {
    if [ -n "$base" ]; then
      git diff --name-only --no-renames "$base"...HEAD
    fi
    git diff --name-only --no-renames HEAD
    git ls-files --others --exclude-standard
  } | sort -u
}

# origin/main if it is there, main if not, and nothing if neither - which the
# caller turns into "run everything" rather than into an empty file list. A
# fresh clone with no main, or a repository mid-rebase, must not read as "no
# files changed, nothing to do".
resolve_base() {
  if [ -n "$base_ref" ]; then
    echo "$base_ref"
    return 0
  fi
  local candidate
  for candidate in origin/main main; do
    if git rev-parse --verify --quiet "$candidate^{commit}" >/dev/null; then
      echo "$candidate"
      return 0
    fi
  done
  return 0
}

# ---------------------------------------------------------------------------
# What each suite covers
# ---------------------------------------------------------------------------

# The `paths:` handed to .github/actions/changed-paths in a suite's
# workflow, read by scripts/suite_scopes.py - the one home for that reading
# since #660, shared with scripts/threads.sh so the two cannot drift from
# each other any more than from CI.
scope_for_suite_workflows() {
  "${SCOPE_PY}" scripts/suite_scopes.py "$1" 2>/dev/null || true
}

# The three test workflows carry a machine-readable scope; the settings
# suite runs on ANY change, mirroring CI, which runs it unfiltered on every
# pull request by design (TESTING.md, "Repository settings"). This used to
# be a hand-written ".github/" prefix with a sentence claiming a suite
# whose subject is .github/ "cannot quietly start depending on something
# outside it" - which had already happened when the sentence was written
# down (#660): test_status_page.py reads site/status/index.html,
# test_privacy_policy.py scans client/src/, and test_no_committed_data.py
# walks every tracked path. The honest local mirror of "CI runs it on
# every PR" is "run it whenever anything changed", and the suite is cheap
# enough to carry that.

suite_names=(client backend pipeline dbt settings)

scope_for_suite() {
  scope_for_suite_workflows "$1"
}

# Which of `files` sit under any prefix in `scope`, as literal prefixes.
matched_files() {
  local files="$1" scope="$2" file prefix
  while IFS= read -r file; do
    [ -n "$file" ] || continue
    for prefix in $scope; do
      case "$file" in
        "$prefix"*) printf '%s\n' "$file"; break ;;
      esac
    done
  done <<< "$files"
}

# ---------------------------------------------------------------------------
# Deciding
# ---------------------------------------------------------------------------

base="$(resolve_base)"
reason=""
selected=()
# What could not run, for the closing line - see its note.
skipped=()

if $run_all; then
  reason="--all"
  selected=("${suite_names[@]}")
elif [ -z "$base" ]; then
  reason="no base branch to compare against"
  selected=("${suite_names[@]}")
else
  files="$(changed_files "$base")"
  if [ -z "$files" ]; then
    # Nothing to test is a real answer, and a different one from "we could not
    # tell". Reported rather than turned into a full run.
    reason="nothing changed against $base"
  else
    for suite in "${suite_names[@]}"; do
      if [ "$suite" = "settings" ]; then
        # Any change at all selects the settings suite - the local mirror
        # of CI running it unfiltered on every pull request. See the note
        # above scope_for_workflow (#660).
        selected+=("settings")
        continue
      fi
      scope="$(scope_for_suite "$suite")"
      if [ -z "$scope" ]; then
        # An unreadable scope is not evidence the suite is unnecessary.
        echo "warning: could not read the scope list for the $suite suite - running it." >&2
        selected+=("$suite")
        continue
      fi
      # Matched as literal prefixes, not as patterns. `grep "^$prefix"` reads
      # naturally and is wrong: every scope list here contains `.github/...`,
      # whose leading dot is a regex wildcard, so it would also match a file
      # called `xgithub/...`. Over-matching only ever adds a suite, so this
      # would never have shown up as a failure - it would have shown up as
      # this script quietly being less useful than it claims.
      if [ -n "$(matched_files "$files" "$scope")" ]; then
        selected+=("$suite")
      fi
    done
    reason="changed against $base ($(printf '%s\n' "$files" | wc -l | tr -d ' ') files)"
  fi
fi

echo "== $reason"
if [ ${#selected[@]} -eq 0 ]; then
  echo "== nothing to run"
  exit 0
fi
echo "== running: ${selected[*]}"
echo

# WHAT THE DBT SUITE LEAVES OUT OF CI'S dbt JOB, said rather than implied
# (WF8 of the PR #1805 review). These are the parity families its parity
# lines below run. CI's job runs 47, and its contract-versions step besides:
# most families' old sides read their inputs from pipeline/data/raw/
# (parity.py's RAW_DIR and the exporters' own), where CI's fixture build
# writes, and this script keeps its fixtures in a temporary directory
# instead (see the dbt suite's note). Which of the others could run from
# there has not been checked family by family. CI's list is read from its
# own step by scripts/dbt_ci_parity.py, so this line cannot drift from it;
# .github/tests/test_dev_scripts.py holds this array to the lines that run.
dbt_local_parity=(podcasts stewards registry elevation trail_graph_elevation trail_graph_profile)

# Sets dbt_ci_total and dbt_ci_left, CI's parity families this suite does not
# run; fails when CI's step cannot be read.
dbt_ci_left_out() {
  local ci family
  dbt_ci_left=()
  ci="$("${SCOPE_PY}" scripts/dbt_ci_parity.py 2>/dev/null)" || return 1
  dbt_ci_total="$(wc -l <<< "$ci" | tr -d ' ')"
  while IFS= read -r family; do
    [[ " ${dbt_local_parity[*]} " == *" ${family} "* ]] || dbt_ci_left+=("$family")
  done <<< "$ci"
}

dbt_ci_skips() {
  local contract="CI's contract-versions step (check_contract_versions.py against the base's manifest)"
  if dbt_ci_left_out; then
    echo "dbt suite: ${#dbt_ci_left[@]} of CI's ${dbt_ci_total} parity families not run here: ${dbt_ci_left[*]}; and ${contract}. CI's dbt job runs them regardless."
  else
    echo "dbt suite: CI's parity families could not be read (scripts/dbt_ci_parity.py), so how many it leaves out is unknown; and ${contract}."
  fi
}

if $list_only; then
  # The files, not just the scope list. "Why is the backend suite running for
  # a client-only change" has a real answer - one of the six contract modules
  # it reads as text - and printing the scope list alone leaves the reader to
  # find it by eye.
  for suite in "${selected[@]}"; do
    echo "$suite"
    if [ -n "${files:-}" ]; then
      matched_files "$files" "$(scope_for_suite "$suite")" | sed 's/^/    /'
    else
      echo "    (everything - $reason)"
    fi
    if [ "$suite" = "dbt" ]; then
      echo
      dbt_ci_skips
      echo
    fi
  done
  exit 0
fi

# ---------------------------------------------------------------------------
# Running
# ---------------------------------------------------------------------------

selected_has() {
  local needle="$1" item
  for item in "${selected[@]}"; do
    [ "$item" = "$needle" ] && return 0
  done
  return 1
}

step() {
  local label="$1"; shift
  local started=$SECONDS
  echo "-- $label"
  if ! "$@"; then
    echo
    echo "!! $label FAILED" >&2
    exit 1
  fi
  echo "   ok ($((SECONDS - started))s)"
}

# THE dbt GENERATORS' OUTPUT, which is not committed (pipeline/ELT.md
# decision 91), written once, before the first suite that reads it: the
# pipeline suite walks the models on disk (pipeline/tests/conftest.py refuses
# to start without them) and the dbt suite parses them. On the suites' own
# Python, which carries dlt as the generators need; CI's jobs give them the
# extract's venv, or the pytest job's own Python.
dbt_generated=false
generate_dbt_once() {
  $dbt_generated && return 0
  step "dbt generate models"   env -C pipeline "$PY" generate_dbt.py
  dbt_generated=true
}

# Said BEFORE the first step rather than left to `python -m ruff` to discover,
# and said with the real reason (#859): "No module named ruff" points at a
# package when the problem is an interpreter, and the fix it suggests makes
# things worse. Only the Python suites need this - a hypothetical client-only
# selection runs without any Python at all.
if [ -z "$PY" ] && { selected_has pipeline || selected_has backend || selected_has settings; }; then
  echo "!! no interpreter here can run the suites: \`python\` is $(python --version 2>&1)," >&2
  echo "   and neither it, \`python3\`, nor the newest python3.N on this machine can" >&2
  echo "   import ruff and pytest. The suites are installed under some interpreter -" >&2
  echo "   run .claude/hooks/session-start.sh (web sessions), or install the dev" >&2
  echo "   requirements into the one you mean to use, or put it first on PATH." >&2
  exit 1
fi

# THE DBT TOOLCHAIN, found rather than installed. CI's `dbt` job runs on its
# own Python with its own requirements file (requirements-dbt.txt), which
# shares nothing with the pytest suites' beyond duckdb, so it cannot borrow
# $PY. What counts is the `dbt` first on PATH, if it reports the dbt version
# that file pins (read from the file, one home), and the python and sqlfluff
# of the same environment beside it - a venv's bin/ always has both.
# Anything else is an environment gap and is said, never guessed around:
# another dbt on PATH is the dbt-core 1.x this project left, or the dbt-oss
# distribution decision 32 moved off (`dbt --version` names which: "dbt
# 2.0.6" for the full distribution, "dbt-oss 2.0.5" for the other).
DBT_PIN="$(sed -n 's/^dbt==\([^ ;]*\).*/\1/p' pipeline/requirements-dbt.txt | head -1)"
DBT_DIR=""
dbt_found="none"
if selected_has dbt && command -v dbt >/dev/null 2>&1; then
  dbt_found="$(dbt --version 2>/dev/null | head -1)"
  candidate="$(dirname "$(command -v dbt)")"
  if [ -n "$DBT_PIN" ] && [ "$dbt_found" = "dbt ${DBT_PIN}" ] &&
     [ -x "$candidate/python" ] && [ -x "$candidate/sqlfluff" ]; then
    DBT_DIR="$candidate"
  fi
fi

# Suites run one at a time, each using every core internally rather than four
# suites fighting over them. Measured on a four-core machine: run concurrently,
# the three big suites took 100s, 104s and 209s; run one after another with the
# same cores each, 22s, 16s and the client's own pool. Contention is not a
# saving, and interleaved output from four suites is unreadable besides.
#
# `-n auto` rather than a fixed number so this is not tuned to the machine it
# was written on. pytest-xdist reads the physical core count; vitest's pool
# does the same thing for the client without being asked.
PYTEST_PARALLEL=(-n auto)

# Both Python suites put `--cov` in their pyproject addopts, so switching it
# off is an explicit flag rather than an omission.
PYTEST_COVERAGE=(--no-cov)
# A named package script rather than `npm exec -- vitest run`, which was the
# first version of this line and was quietly wrong. `npm --prefix client run`
# executes the script with the working directory set to client/; `npm --prefix
# client exec` does not, so vitest took the repository root as its own root,
# globbed a different set of files and loaded none of client/vite.config.ts -
# no jsdom, no src/test/setup.ts. It reported a pass, on the wrong suite.
# Caught by running this script rather than by reading it, which is the whole
# argument for `--all` existing.
CLIENT_TEST=(npm --prefix client run test:nocov)
if $with_coverage; then
  PYTEST_COVERAGE=()
  CLIENT_TEST=(npm --prefix client test)
fi

# LINTERS AND FORMATTERS FIRST, ALL OF THEM, BEFORE ANY SUITE RUNS. This is
# the ordering CLAUDE.md asks for and the reason it asks: a quarter of every
# failure in this repository's CI history was formatting alone, and the job
# that catches it runs the formatter before the tests, so the suite never ran
# and the log said nothing about the change being made. Three seconds of ruff
# and prettier ahead of three minutes of tests turns that round trip into a
# line of output.
if selected_has pipeline; then
  step "pipeline ruff check"   "$PY" -m ruff check pipeline
  step "pipeline ruff format"  "$PY" -m ruff format --check pipeline
fi
if selected_has backend; then
  step "backend ruff check"    "$PY" -m ruff check backend
  step "backend ruff format"   "$PY" -m ruff format --check backend
fi
if selected_has settings; then
  step "settings ruff check"   "$PY" -m ruff check .github/tests
  step "settings ruff format"  "$PY" -m ruff format --check .github/tests
fi
if selected_has client; then
  step "client lint"           npm --prefix client run lint
  step "client format:check"   npm --prefix client run format:check
  step "client typecheck"      npm --prefix client run typecheck
fi

# Then the suites, cheapest first, so the common failure arrives soonest.
if selected_has settings; then
  step "settings tests" "$PY" -m pytest .github/tests -q "${PYTEST_PARALLEL[@]}"
fi
if selected_has pipeline; then
  generate_dbt_once
  step "pipeline tests" env -C pipeline "$PY" -m pytest -q "${PYTEST_PARALLEL[@]}" "${PYTEST_COVERAGE[@]}"
fi
if selected_has backend; then
  step "backend tests"  env -C backend "$PY" -m pytest -q "${PYTEST_PARALLEL[@]}" "${PYTEST_COVERAGE[@]}"
fi

# pipeline-tests.yml's `dbt` job, in its order, with four differences and
# each one on purpose:
#   - the fixtures and the warehouse go to a temporary directory, never to
#     pipeline/data/. make_dbt_fixtures.py refuses to write over a real
#     fetch, and fixture mode would replace a real warehouse; on a CI runner
#     pipeline/data/ is empty, here it may be somebody's afternoon of fetching;
#   - so it runs only dbt_local_parity's 6 of CI's 47 parity families, and
#     not CI's contract-versions step. `--list` names every one left out,
#     and the last line of a run counts them (dbt_ci_skips, above);
#   - nothing is installed: no pip. Fixture mode runs under the suites' own
#     Python rather than a venv of requirements-extract.txt;
#   - --no-dbt-deps can skip `dbt deps`, out loud.
# Telemetry is off for the same reason, and by the same documented opt-out,
# as in CI: the workflow's dbt job says why that variable and no other.
# The docs site is checked by pipeline/check_docs_site.py, as the workflow
# step checks it; that script is the home of what the site must contain.
#
# ELEMENTARY'S CHECKS, AS CI'S PULL REQUEST RUNS THEM (decision 111): only
# those on what this branch changed and below it, against the merge base
# with the base this script compares with (origin/main, or --since), which
# is what a pull request's merge commit changes against its base. That base
# is exported from git into the temporary directory (never a worktree),
# given this checkout's dbt packages when its pins are the same and its own
# generated models, and parsed with Elementary's switches on, against the
# same warehouse path the build uses, as the workflow's "Parse the base with
# Elementary's checks in it" step does. `--all`, the way a push to main
# runs, runs every check, as a push to main does; and so does a base this
# cannot prepare, said by name. build_marts.py says the rest.
checks_base=()
checks_base_for_dbt_suite() {
  local why="" merge_base="" exported="$dbt_tmp/base"
  if $run_all; then
    why="--all runs every check, as a push to main does"
  elif [ -z "$base" ] || ! merge_base="$(git merge-base "$base" HEAD 2>/dev/null)"; then
    why="there is no merge base with ${base:-a base branch} to compare with"
  else
    mkdir -p "$exported"
    if ! git archive "$merge_base" pipeline | tar -x -C "$exported"; then
      why="the merge base's pipeline/ could not be exported"
    elif [ ! -f "$exported/pipeline/check_contract_versions.py" ]; then
      why="the merge base predates check_contract_versions.py, and dbt ${DBT_PIN} cannot parse it"
    elif ! cmp -s pipeline/dbt/packages.yml "$exported/pipeline/dbt/packages.yml" ||
         ! cmp -s pipeline/dbt/package-lock.yml "$exported/pipeline/dbt/package-lock.yml"; then
      why="the merge base pins other dbt packages, which this script does not fetch"
    elif ! cp -R pipeline/dbt/dbt_packages "$exported/pipeline/dbt/dbt_packages"; then
      why="this checkout's dbt packages could not be copied to the merge base"
    elif [ -f "$exported/pipeline/generate_dbt.py" ] && ! env -C "$exported/pipeline" "$PY" generate_dbt.py >/dev/null; then
      why="the merge base's generate_dbt.py failed"
    elif ! env -C "$exported/pipeline/dbt" DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS=false OURHIKE_ELEMENTARY=true \
           OURHIKE_ELEMENTARY_CHECKS=true "OURHIKE_WAREHOUSE=$dbt_tmp/warehouse.duckdb" \
           "OURHIKE_PROCESSED_DIR=$dbt_tmp/processed" "$DBT_DIR/dbt" parse --profiles-dir . >/dev/null; then
      why="the merge base would not parse with Elementary's checks in it"
    fi
  fi
  if [ -n "$why" ]; then
    echo "-- dbt checks base: every Elementary check runs: $why"
    checks_base=()
  else
    echo "-- dbt checks base: only the Elementary checks on what changed since ${merge_base:0:12} and below it"
    checks_base=(--checks-base "$exported/pipeline/dbt")
  fi
}
if selected_has dbt; then
  if [ -z "$DBT_DIR" ]; then
    echo "-- dbt suite: SKIPPED, no dbt ${DBT_PIN:-?} first on PATH (found: ${dbt_found})."
    echo "   Make a venv outside the repository, install the pins, and put it first on PATH:"
    echo "     python3.12 -m venv ~/.venvs/ourhike-dbt"
    echo "     ~/.venvs/ourhike-dbt/bin/pip install -r pipeline/requirements-dbt.txt"
    echo "     PATH=~/.venvs/ourhike-dbt/bin:\$PATH scripts/test.sh"
    echo "   CI runs it regardless (.github/workflows/pipeline-tests.yml's dbt job)."
    skipped+=("dbt suite (no dbt ${DBT_PIN:-?} on PATH)")
  else
    dbt_tmp="$(mktemp -d)"
    trap 'rm -rf "$dbt_tmp"' EXIT
    dbt_cmd=(env -C pipeline/dbt DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS=false
             "OURHIKE_WAREHOUSE=$dbt_tmp/warehouse.duckdb"
             "OURHIKE_PROCESSED_DIR=$dbt_tmp/processed" "$DBT_DIR/dbt")
    generate_dbt_once
    if $skip_dbt_deps; then
      echo "-- dbt deps: skipped (--no-dbt-deps), using pipeline/dbt/dbt_packages/ as it is"
      skipped+=("dbt deps (--no-dbt-deps)")
    else
      step "dbt deps"            "${dbt_cmd[@]}" deps --profiles-dir .
    fi
    step "dbt parse"             "${dbt_cmd[@]}" parse --profiles-dir .
    step "dbt lint"              "${dbt_cmd[@]}" lint --profiles-dir .
    # Fixture mode, as CI runs it: the extract over the fixture files, under
    # the suites' own Python, which carries dlt (requirements-dev.in) where the
    # dbt venv does not. CI gives it a venv of requirements-extract.txt.
    step "dbt fixtures"          env -C pipeline "$PY" make_dbt_fixtures.py --raw-dir "$dbt_tmp/raw"
    step "dbt load warehouse"    env -C pipeline RUNTIME__DLTHUB_TELEMETRY=false "$PY" -m extract._fixtures --raw-dir "$dbt_tmp/raw" --warehouse "$dbt_tmp/warehouse.duckdb" --store "$dbt_tmp/store"
    # The seeds, the build in stages around the Python steps, and the pub_
    # writers last, in the order pipeline/build_marts.py owns, as CI runs it.
    # dbt is $DBT_DIR's; the steps run on $PY, the suites' own Python, which
    # carries requirements.txt's rasterio as CI's pipeline venv does. Its
    # Elementary checks are the ones CI's pull request runs (above).
    checks_base_for_dbt_suite
    step "dbt build_marts"       env -C pipeline DBT_ENGINE_SEND_ANONYMOUS_USAGE_STATS=false "$PY" build_marts.py --fixtures --dbt "$DBT_DIR/dbt" --warehouse "$dbt_tmp/warehouse.duckdb" --processed-dir "$dbt_tmp/processed" --raw-dir "$dbt_tmp/raw" "${checks_base[@]}"
    # Row dates across builds, as CI's dbt job runs it (decision 57): three
    # podcasts builds in fresh warehouses, the history restored between them.
    step "dbt row dates builds"  env -C pipeline OURHIKE_DBT="$DBT_DIR/dbt" "$PY" -m pytest -o addopts="" -q -p no:cacheprovider tests/test_dbt_row_dates_builds.py
    # A conditions build with no club notice table in the warehouse (decision 61), as CI's dbt job runs it.
    step "dbt notices absent"    env -C pipeline OURHIKE_DBT="$DBT_DIR/dbt" "$PY" -m pytest -o addopts="" -q -p no:cacheprovider tests/test_dbt_notice_tables_absent_builds.py
    # A club held for its rows, the rest published (decision 81), as CI's dbt job runs it.
    step "dbt held for its rows" env -C pipeline OURHIKE_DBT="$DBT_DIR/dbt" "$PY" -m pytest -o addopts="" -q -p no:cacheprovider tests/test_dbt_notice_source_held_for_its_rows_builds.py
    # A monthly build with no generated club layer in the warehouse (raw_or_empty()), as CI's dbt job runs it.
    step "dbt club layers absent" env -C pipeline OURHIKE_DBT="$DBT_DIR/dbt" "$PY" -m pytest -o addopts="" -q -p no:cacheprovider tests/test_dbt_club_tables_absent_builds.py
    # Notice source freshness from the run log (decision 100), as CI's dbt job runs it.
    step "dbt notice freshness"  env -C pipeline OURHIKE_DBT="$DBT_DIR/dbt" "$PY" -m pytest -o addopts="" -q -p no:cacheprovider tests/test_dbt_notice_source_freshness_runs.py
    # The data-quality page's two files from Elementary-shaped tables (decision 102), as CI's dbt job runs it.
    step "dbt data-quality files" env -C pipeline OURHIKE_DBT="$DBT_DIR/dbt" "$PY" -m pytest -o addopts="" -q -p no:cacheprovider tests/test_dbt_data_quality_builds.py
    # Every exceptions-seed row names a resource the parsed project has, as CI's dbt job checks it.
    step "dbt exceptions live"   env -C pipeline OURHIKE_DBT="$DBT_DIR/dbt" "$PY" -m pytest -o addopts="" -q -p no:cacheprovider tests/test_dbt_evaluator_exceptions.py
    for family in podcasts:podcasts_episodes stewards:stewards registry:registry; do
      step "dbt parity ${family%%:*}" env -C pipeline "$PY" parity.py "${family%%:*}" --new "$dbt_tmp/processed/${family#*:}.json"
    done
    step "dbt parity elevation"  env -C pipeline "$PY" parity.py elevation --new "$dbt_tmp/processed/elevation_profile.json" --raw-dir "$dbt_tmp/raw"
    for family in trail_graph_elevation trail_graph_profile; do
      step "dbt parity $family" env -C pipeline "$PY" parity.py "$family" --new "$dbt_tmp/processed/$family.json" --raw-dir "$dbt_tmp/raw" --warehouse "$dbt_tmp/warehouse.duckdb"
    done
    # The PDF notices left out, as CI's step leaves them (generate_notice_models.py's PDF_NOTICE_TAG).
    step "dbt source freshness"  "${dbt_cmd[@]}" source freshness --profiles-dir . --exclude tag:pdf_notice
    step "dbt docs generate"     "${dbt_cmd[@]}" docs generate --profiles-dir . --output-dir target/docs
    step "dbt docs site"         env -C pipeline "$PY" check_docs_site.py dbt/target/docs
    step "dbt project evaluator" env DBT_PROJECT_EVALUATOR_SEVERITY=error "${dbt_cmd[@]}" build -s package:dbt_project_evaluator --profiles-dir .
    # Last and on every core, as CI runs it (its step says why): the jinja
    # templater needs no warehouse, but dbt_utils' macros render from
    # dbt_packages/ (dbt/sqlfluff_libs/dbt_utils.py).
    step "dbt sqlfluff lint"     env -C pipeline "$DBT_DIR/sqlfluff" lint dbt/models dbt/tests --processes 0
    if dbt_ci_left_out; then
      skipped+=("${#dbt_ci_left[@]} of CI's ${dbt_ci_total} dbt parity families and its contract-versions step (--list names them)")
    else
      skipped+=("CI's dbt parity families past these ${#dbt_local_parity[@]}, uncounted, and its contract-versions step")
    fi
  fi
fi
if selected_has client; then
  # The build is part of the client's checks rather than an extra: npm run
  # build runs scripts/check-build-output.mjs, which is the only layer in this
  # repository that can see the class of bug TESTING.md's item 19 describes -
  # a suite that passes green while the shipped bundle draws a blank map.
  step "client tests"   "${CLIENT_TEST[@]}"
  step "client build"   npm --prefix client run build

  # site/'s own vitest suite, because client-tests.yml's `test` job runs it
  # (#1643). Skipped out loud without site/node_modules, for the flow layer's
  # reason below: a checkout that never ran `npm ci` in site/ is an
  # environment gap, not a defect in the change.
  if [ -d site/node_modules ]; then
    step "site tests"   npm --prefix site test
  else
    echo "-- site tests: SKIPPED, site/node_modules is missing."
    echo "   Run 'cd site && npm ci' once to turn them on. CI runs them"
    echo "   regardless (.github/workflows/client-tests.yml's test job)."
    skipped+=("site tests (no site/node_modules)")
  fi

  # The flow layer (features/FLOW_TESTING.md), last because it is the slowest
  # and because it drives the app the build above just proved can be built.
  #
  # HERE BECAUSE CI RUNS IT. This script's whole promise is "run what CI runs,
  # before pushing", and client-tests.yml grew a `flow` job on 2026-09-11; a
  # suite that gates a pull request and not this script is a round trip
  # somebody pays for one push later.
  #
  # SKIPPED RATHER THAN FAILED WITHOUT A BROWSER, and said out loud either
  # way. Playwright needs a Chromium it can find, which a fresh checkout does
  # not have until `npx playwright install chromium` has been run once - and a
  # contributor who has not is looking at an environment gap, not a defect in
  # their change. The repository's own rule for a check the environment cannot
  # run is to say so rather than to report a clean run nobody had, so that is
  # what this prints. --no-flow is the same skip, chosen rather than diagnosed,
  # for a loop where the browser is not the thing being changed.
  if [ "$skip_flow" = true ]; then
    echo "-- client flow tests: skipped (--no-flow)"
    skipped+=("client flow tests (--no-flow)")
  elif npm --prefix client exec -- playwright --version >/dev/null 2>&1 &&
       { [ -n "${CHROMIUM_PATH:-}" ] ||
         [ -d "${PLAYWRIGHT_BROWSERS_PATH:-/nonexistent}" ] ||
         [ -d "${HOME}/.cache/ms-playwright" ]; }; then
    # `npm --prefix client run`, not `npm --prefix client exec` - the same
    # distinction CLIENT_TEST's own note above was written for, walked into
    # again here. `run` executes the script with the working directory set to
    # client/; `exec` does not, so Playwright resolved no config, fell back to
    # scanning the repository from its root, and tried to parse App.css and a
    # PNG as test files. The suite it then reported on was not this one.
    #
    # WEBKIT IS ASKED ABOUT SEPARATELY (#1537). An agent sandbox ships Chromium
    # and nothing else, so `phone-webkit` failed all 147 of its specs at launch
    # while every Chromium project passed - an environment gap that read as a
    # catastrophic regression. Asked of Playwright itself, so this looks where
    # the pinned version will look. Only this project is left out; the rest of
    # the suite still runs, and the skip is printed here and in the last line.
    flow_env=()
    if ! (cd client && node -e "process.exit(require('fs').existsSync(require('@playwright/test').webkit.executablePath()) ? 0 : 1)") >/dev/null 2>&1; then
      echo "-- client flow tests: phone-webkit SKIPPED, no WebKit build on this machine."
      echo "   The other projects run. CI's flow job has WebKit and runs it regardless."
      flow_env=(FLOW_SKIP_WEBKIT=1)
      skipped+=("phone-webkit flow project (no WebKit)")
    fi
    step "client flow tests" env "${flow_env[@]}" npm --prefix client run test:e2e
  else
    echo "-- client flow tests: SKIPPED, no Playwright browser on this machine."
    echo "   Run 'cd client && npx playwright install chromium' once to turn"
    echo "   them on. CI runs them on every pull request regardless"
    echo "   (.github/workflows/client-tests.yml's flow job)."
    skipped+=("client flow tests (no browser)")
  fi
fi

echo
# A skip is part of the answer, so it is in the line a reader actually reads
# (#1537): "all green" with a browser's worth of coverage missing would be the
# quiet pass this script exists not to give.
if [ "${#skipped[@]}" -gt 0 ]; then
  echo "== all green: ${selected[*]} - but SKIPPED: $(IFS=';'; echo "${skipped[*]}" | sed 's/;/; /g')"
else
  echo "== all green: ${selected[*]}"
fi
