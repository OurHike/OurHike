#!/usr/bin/env bash
#
# Which data publishes does this branch stale, and what does each one need?
#
# The counterpart to scripts/test.sh, for the half of a change the suites
# cannot cover: the published bytes. A pull request that changes what an
# exporter produces merges green and leaves the bucket describing the code
# before the change, until somebody reruns the publishing workflow that
# carries it - and "somebody" has repeatedly turned out to be nobody, because
# the session that knew ended before the merge happened (#1123).
#
#   scripts/pipelines.sh             the verdict for this branch against origin/main
#   scripts/pipelines.sh --since X   compare against X instead
#   scripts/pipelines.sh --scopes    each publishing path's derived scope, no verdict
#
# The verdict is one line per publishing path - STALE with the files that did
# it and what to do about it, or fresh - plus an `unclaimed` line for any
# pipeline .py this model cannot place and a `migrations` line when the diff
# carries Alembic revisions. scripts/pipeline_scopes.py derives the scopes
# from the workflow files themselves and its docstring is the design record;
# CLAUDE.md ("A pipeline change is not finished at the merge") is what a
# session does with the answer.
#
# UNCERTAINTY FAILS LOUDLY HERE, unlike test.sh. test.sh answers every
# uncertain case by running everything, because a suite costs a minute.
# A publish costs a production-environment approval and hours of fetching,
# so "when unsure, dispatch all five" is not a kindness - this script instead
# exits non-zero with the reason, and the answer is worked out by hand.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Shared interpreter selection (scripts/pick_python.sh - one home, #859).
# The scope reader needs PyYAML, which the session-start hook installs under
# the interpreter CI uses; bare `python` here is the exact drift #859 was.
. scripts/pick_python.sh
SCOPE_PY="$(python_with yaml || true)"
if [ -z "$SCOPE_PY" ]; then
  echo "pipelines.sh: no interpreter with PyYAML - cannot read the workflow scopes." >&2
  echo "Answer by hand: .github/workflows/{publish-vector-data,build-basemap,build-dem}.yml" >&2
  exit 2
fi

base_ref=""
mode="verdict"
while [ $# -gt 0 ]; do
  case "$1" in
    --since)
      shift
      base_ref="${1:?--since needs a ref}"
      ;;
    --scopes)
      mode="scopes"
      ;;
    *)
      echo "usage: scripts/pipelines.sh [--since REF] [--scopes]" >&2
      exit 2
      ;;
  esac
  shift
done

if [ "$mode" = "scopes" ]; then
  exec "$SCOPE_PY" scripts/pipeline_scopes.py
fi

# Same refusal as test.sh: an explicit --since naming nothing is a typo, and
# answering anyway would hide it behind a plausible-looking verdict.
if [ -n "$base_ref" ] && ! git rev-parse --verify --quiet "$base_ref^{commit}" >/dev/null; then
  echo "--since: no such commit: $base_ref" >&2
  exit 2
fi

if [ -z "$base_ref" ]; then
  if git rev-parse --verify --quiet origin/main >/dev/null; then
    base_ref="origin/main"
  elif git rev-parse --verify --quiet main >/dev/null; then
    base_ref="main"
  else
    echo "pipelines.sh: no origin/main or main to diff against - answer by hand." >&2
    exit 2
  fi
fi

# Committed work plus the working tree plus untracked files, --no-renames so a
# rename reports both paths - the same reasoning, argued in full, at
# test.sh's changed_files().
{
  git diff --name-only --no-renames "$base_ref"...HEAD
  git diff --name-only --no-renames HEAD
  git ls-files --others --exclude-standard
} | sort -u | "$SCOPE_PY" scripts/pipeline_scopes.py --changed
