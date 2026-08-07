#!/usr/bin/env bash
#
# What is in flight, and which of it actually needs a hand.
#
# The question this answers is "which branches need me to do something", and
# the only answer that costs anything to get wrong is "does this conflict with
# main". Everyone guesses at that one, because the obvious way to find out is
# to merge main in and see - which is the very work worth avoiding. `git
# merge-tree` answers it against the object store without touching the working
# tree, the index, or the branch, in about a millisecond.
#
# Read-only in the strict sense: no checkout, no merge, no fetch, no write of
# any kind. Safe to run mid-rebase, on a dirty tree, in another worktree.
# `--fetch` is the one exception and it is opt-in.
#
#   scripts/threads.sh              live branches and what each needs
#   scripts/threads.sh --fetch      refresh remotes first, then report
#   scripts/threads.sh --stale      also list merged branches worth deleting
#   scripts/threads.sh --all        both
#
# See BRANCHING.md for what to do with the answer. The short version is that
# `clean` means leave it alone: GitHub merges the pull request against main as
# it is at the moment you press the button, not against the copy of main your
# branch happens to contain.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

show_stale=false
do_fetch=false
for arg in "$@"; do
  case "$arg" in
    --stale) show_stale=true ;;
    --fetch) do_fetch=true ;;
    --all) show_stale=true; do_fetch=true ;;
    -h|--help) sed -n '2,24p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "unknown option: $arg (try --help)" >&2; exit 2 ;;
  esac
done

# merge-tree's --write-tree mode landed in 2.38. Without it there is no way to
# test a merge without performing one, and a tool that silently downgraded to
# "everything is probably fine" would be worse than one that says it cannot
# tell.
if ! git merge-tree --write-tree HEAD HEAD >/dev/null 2>&1; then
  echo "threads.sh needs git 2.38 or newer for 'merge-tree --write-tree'." >&2
  echo "Found: $(git --version)" >&2
  exit 1
fi

if $do_fetch; then
  echo "fetching..." >&2
  git fetch origin --prune --quiet
fi

base=origin/main
git rev-parse --verify --quiet "$base" >/dev/null || base=main
git rev-parse --verify --quiet "$base" >/dev/null || {
  echo "no main branch found locally or on origin" >&2; exit 1
}

bold=$'\033[1m'; dim=$'\033[2m'; red=$'\033[31m'; green=$'\033[32m'; off=$'\033[0m'
[ -t 1 ] || { bold=""; dim=""; red=""; green=""; off=""; }

# Which suite each path prefix belongs to, mirroring the `paths:` given to
# .github/actions/changed-paths in each workflow. Kept in the order
# CONTRIBUTING.md lists the build commands, so the output reads as a to-run
# list rather than a set.
suites_for() {
  local files="$1" suites=()

  grep -qE '^client/'   <<<"$files" && suites+=("client")
  grep -qE '^pipeline/' <<<"$files" && suites+=("pipeline")
  grep -qE '^backend/'  <<<"$files" && suites+=("backend")
  grep -qE '^\.github/' <<<"$files" && suites+=("repo-settings")

  # A change to a gate has to prove the suite it gates - which is why each
  # workflow lists its own file and the shared action in its own paths. Marked
  # with ? because it is the gate being re-proven, not the suite's own code.
  if grep -qE '^\.github/(workflows/|actions/changed-paths/)' <<<"$files"; then
    grep -qE '^client/'   <<<"$files" || suites+=("client?")
    grep -qE '^pipeline/' <<<"$files" || suites+=("pipeline?")
    grep -qE '^backend/'  <<<"$files" || suites+=("backend?")
  fi

  if [ ${#suites[@]} -eq 0 ]; then echo "none (docs only)"; else echo "${suites[*]}"; fi
}

printf '\n%sOurHike threads%s  ·  base %s @ %s\n\n' \
  "$bold" "$off" "$base" "$(git rev-parse --short "$base")"

live=0 conflicted=0 clean=0
# Newline-delimited rather than an array: macOS still ships bash 3.2, where
# `mapfile` does not exist and an empty array trips `set -u`. Nothing here
# needs more than a list of names.
unrelated=""
unrelated_n=0

while read -r ref; do
  [ -z "$ref" ] && continue
  branch=${ref#origin/}

  # gh-pages is an orphan branch by construction - Pages deploys a built site
  # there, and it is supposed to share no history with main. Skipping it here
  # keeps it out of the litter list it would otherwise always head.
  [ "$branch" = "gh-pages" ] && continue

  # Anything else with no merge base shares no history with main at all. It is
  # not a thread that has drifted, it is a leftover from a different life of
  # the repository, and every number below would be meaningless for it.
  if ! git merge-base "$base" "$ref" >/dev/null 2>&1; then
    unrelated="${unrelated}${branch}"$'\n'
    unrelated_n=$((unrelated_n + 1))
    continue
  fi

  ahead=$(git rev-list --count "$base..$ref")
  behind=$(git rev-list --count "$ref..$base")
  last=$(git log -1 --format=%cr "$ref")
  files=$(git diff --name-only "$base...$ref")
  suites=$(suites_for "$files")

  if git merge-tree --write-tree --no-messages "$base" "$ref" >/dev/null 2>&1; then
    status="${green}clean${off}    "
    action="leave it - merges as-is, main's age is irrelevant"
    clean=$((clean + 1))
  else
    # Name the files rather than count them. Which file it is decides whether
    # this is thirty seconds or an afternoon.
    #
    # In --name-only mode the first line is the tree OID and the rest are the
    # conflicted paths, one per line. (`paste -d', '` would be the obvious
    # join and is wrong - that is a *cycling delimiter list*, so it alternates
    # comma and space rather than using ", " between every pair.)
    hits=$(git merge-tree --write-tree --name-only --no-messages \
             "$base" "$ref" 2>/dev/null | tail -n +2 | grep . || true)
    n_hits=$(printf '%s' "$hits" | grep -c . || true)
    shown=$(printf '%s' "$hits" | head -3 | tr '\n' '|' | sed 's/|$//; s/|/, /g')
    [ "$n_hits" -gt 3 ] && shown="$shown (+$(( n_hits - 3 )) more)"
    status="${red}CONFLICTS${off}"
    action="merge main in and resolve ${n_hits}: ${shown:-unknown}"
    conflicted=$((conflicted + 1))
  fi

  live=$((live + 1))
  printf '  %b  %s\n' "$status" "$branch"
  printf '             %s+%s/-%s · %s · suites: %s%s\n' "$dim" "$ahead" "$behind" "$last" "$suites" "$off"
  printf '             → %s\n\n' "$action"
done < <(git branch -r --no-merged "$base" --sort=-committerdate \
           | grep -v 'HEAD' | sed 's/^[ *]*//' | grep -v "^${base}$")

[ "$live" -eq 0 ] && printf '  nothing in flight.\n\n'

if [ "$unrelated_n" -gt 0 ]; then
  printf '%sunrelated history - shares no commit with main (%s)%s\n' "$bold" "$unrelated_n" "$off"
  printf '%s  Not threads. Left over from an earlier life of the repository;\n' "$dim"
  printf '  nothing here can be merged and nothing here needs watching.%s\n\n' "$off"
  printf '%s' "$unrelated" | head -8 | sed 's/^/  /'
  [ "$unrelated_n" -gt 8 ] && printf '  ... and %s more\n' "$(( unrelated_n - 8 ))"
  printf '\n'
fi

if $show_stale; then
  merged=$(git branch -r --merged "$base" \
    | grep -v 'HEAD' | sed 's/^[ *]*//' | grep -vE "^(origin/main|origin/gh-pages)$" \
    | sed 's|^origin/||' || true)
  merged_n=$(printf '%s' "$merged" | grep -c . || true)
  if [ "$merged_n" -gt 0 ]; then
    printf '%smerged into main - safe to delete (%s)%s\n\n' "$bold" "$merged_n" "$off"
    printf '%s' "$merged" | head -40 | sed 's/^/  /'
    [ "$merged_n" -gt 40 ] && printf '  ... and %s more\n' "$(( merged_n - 40 ))"
    printf '\n%s  git push origin --delete <branch> - or tick "Automatically delete head\n' "$dim"
    printf '  branches" in Settings once and stop doing this by hand.%s\n\n' "$off"
  fi
fi

printf '%s%s live · %s clean · %s conflicting%s\n' "$bold" "$live" "$clean" "$conflicted" "$off"
if [ "$conflicted" -eq 0 ] && [ "$live" -gt 0 ]; then
  printf 'No branch needs main merged into it. See BRANCHING.md.\n'
fi
printf '\n'
