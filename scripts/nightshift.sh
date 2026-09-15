#!/usr/bin/env bash
#
# What may an unattended session pick up tonight, and why not the rest?
#
# The third of this repository's three answer-one-question scripts.
# scripts/threads.sh says what is in flight, scripts/pipelines.sh says what a
# branch stales, and this one says what the backlog offers a session nobody is
# watching (#1463). The gate itself is scripts/night_queue.py - pure, and held
# by .github/tests/test_night_queue.py - so the rule can be re-checked without
# a token. This half only fetches.
#
#   scripts/nightshift.sh             tonight's queue, and every exclusion's reason
#   scripts/nightshift.sh --census    the bucket counts behind #1463's table
#   scripts/nightshift.sh --triage    the unlabeled issues, which no rule can route
#   scripts/nightshift.sh --json      the fetched issues, unjudged, for piping
#
# Read-only against GitHub: two GETs and no write of any kind. Safe to run at
# any time, on any branch, mid-rebase, on a dirty tree.
#
# .claude/skills/night-shift/SKILL.md is what a session DOES with the answer -
# the claim, the branch, the draft pull request, and the four things it must
# never do unattended. This script deliberately does not know any of that.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

REPO="${NIGHTSHIFT_REPO:-OurHike/OurHike}"
API="https://api.github.com/repos/${REPO}"

. scripts/pick_python.sh
PY="$(python_with json || true)"
if [ -z "${PY}" ]; then
  echo "nightshift.sh: no usable Python interpreter." >&2
  exit 2
fi

# GH_TOKEN or GITHUB_TOKEN - both are set in an agent session, and a developer
# is likelier to have exported the first. Failing loudly beats printing an
# empty queue, which reads exactly like "nothing to do tonight".
TOKEN="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
if [ -z "${TOKEN}" ]; then
  echo "nightshift.sh: no GH_TOKEN or GITHUB_TOKEN - cannot read the issue list." >&2
  echo "An empty queue and an unreadable one look identical, so this stops instead." >&2
  exit 2
fi

fetch() {
  # Pages until one comes back EMPTY, not until one comes back short.
  #
  # A short page reads like the end of the list and is not: the first run of
  # this script reported 102 open issues where a run three minutes later
  # reported 112, because page two arrived with 12 rows instead of 22 and the
  # loop believed it. A gate that silently drops ten issues is worse than one
  # that refuses to answer - the missing work looks exactly like work that was
  # already done. One extra request per call buys the difference.
  #
  # Rows are also de-duplicated by number, because a list that people are
  # filing into while it is being paged can hand out the same row twice.
  local path="$1" page=1 body count
  echo "["
  local first=1
  while :; do
    body="$(curl -fsSL \
      -H "Authorization: Bearer ${TOKEN}" \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "${API}/${path}&per_page=100&page=${page}")"
    count="$(printf '%s' "${body}" | "${PY}" -c 'import json,sys; print(len(json.load(sys.stdin)))')"
    [ "${count}" -eq 0 ] && break
    [ "${first}" -eq 1 ] || echo ","
    first=0
    printf '%s' "${body}" | "${PY}" -c 'import json,sys; print(",".join(json.dumps(i) for i in json.load(sys.stdin)))'
    page=$((page + 1))
    # A runaway guard, not a page count: 40 pages is 4,000 rows, far past any
    # plausible backlog, and reaching it means the loop is not terminating.
    if [ "${page}" -gt 40 ]; then
      echo "nightshift.sh: pagination did not terminate after 40 pages." >&2
      exit 2
    fi
  done
  echo "]"
}

WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT

fetch "issues?state=open" > "${WORK}/issues.json"
fetch "pulls?state=open" > "${WORK}/pulls.json"

# An issue an open pull request already closes is in flight, whatever its
# labels say. This is the mechanical half of CLAUDE.md's "Claim the issue
# before you branch"; the half that reads an issue's comments for a claim
# stays with the session, because a claim is prose and this is not.
"${PY}" - "${WORK}/issues.json" "${WORK}/pulls.json" > "${WORK}/annotated.json" <<'PYEOF'
import json
import re
import sys

seen = {}
for row in json.loads(open(sys.argv[1]).read()):
    seen[row["number"]] = row
issues = list(seen.values())
pulls = json.loads(open(sys.argv[2]).read())

closes = set()
for pull in pulls:
    body = pull.get("body") or ""
    for match in re.finditer(r"\b(?:closes|fixes|resolves)\s+#(\d+)\b", body, re.I):
        closes.add(int(match.group(1)))

for issue in issues:
    if issue.get("number") in closes:
        issue["has_open_pr"] = True
print(json.dumps(issues))
PYEOF

if [ "${1:-}" = "--json" ]; then
  cat "${WORK}/annotated.json"
  exit 0
fi

"${PY}" scripts/night_queue.py "$@" < "${WORK}/annotated.json"
