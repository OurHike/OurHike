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
#   scripts/test.sh --list      what would run and why, without running it
#   scripts/test.sh --since X   compare against X rather than origin/main
#   scripts/test.sh --coverage  measure coverage too, as CI does
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
base_ref=""
while [ $# -gt 0 ]; do
  case "$1" in
    --all) run_all=true ;;
    --list) list_only=true ;;
    --coverage) with_coverage=true ;;
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

suite_names=(client backend pipeline settings)

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
  step "pipeline tests" env -C pipeline "$PY" -m pytest -q "${PYTEST_PARALLEL[@]}" "${PYTEST_COVERAGE[@]}"
fi
if selected_has backend; then
  step "backend tests"  env -C backend "$PY" -m pytest -q "${PYTEST_PARALLEL[@]}" "${PYTEST_COVERAGE[@]}"
fi
if selected_has client; then
  # The build is part of the client's checks rather than an extra: npm run
  # build runs scripts/check-build-output.mjs, which is the only layer in this
  # repository that can see the class of bug TESTING.md's item 19 describes -
  # a suite that passes green while the shipped bundle draws a blank map.
  step "client tests"   "${CLIENT_TEST[@]}"
  step "client build"   npm --prefix client run build
fi

echo
echo "== all green: ${selected[*]}"
