#!/usr/bin/env bash
#
# Sweeps the Cloudflare Pages previews this project has orphaned - every one
# built for a pull request that has since closed, back to the first, rather
# than only the pull request closing right now (#1004).
#
# WHY THERE IS A BACKLOG AT ALL. `.github/actions/delete-pages-previews`
# selects deployments by the alias of the pull request being closed, so it
# only ever looks at one. It also could not list anything at all between
# 2026-08-19 and 2026-08-25 - first because its manifest would not parse, then
# because it asked for a `per_page` the API refuses (#990, #1001) - so nothing
# it was pointed at was removed either. Both faults are fixed forward and
# neither fix reaches backwards. This does.
#
# WHY A SCRIPT AND NOT A WORKFLOW. It runs once, it wants a human reading its
# output, and deleting is the one thing here that cannot be undone. A
# scheduled sweep would also be a second thing that can silently stop working,
# which is exactly how the backlog it exists to clear was built.
#
# WHAT IT NEEDS
#
#   CLOUDFLARE_API_TOKEN      "Cloudflare Pages: Edit" on the account below.
#   CLOUDFLARE_ACCOUNT_ID     The account holding the Pages project.
#   CLOUDFLARE_PAGES_PROJECT  The Pages project (this repository: the value of
#                             the CLOUDFLARE_PAGES_PROJECT repository
#                             variable, `ourhike-preview`).
#   GITHUB_TOKEN              Read access to pull requests on the repository
#                             below. Required rather than optional: which
#                             deployments may be deleted is decided from each
#                             pull request's state, and unauthenticated GitHub
#                             allows 60 requests an hour, which is fewer than
#                             the aliases this is expected to find.
#
#   GITHUB_REPOSITORY         Defaults to OurHike/OurHike.
#
# USAGE
#
#   scripts/sweep-pages-previews.sh                 the plan, and nothing else
#   scripts/sweep-pages-previews.sh --delete        the plan, then one alias
#   scripts/sweep-pages-previews.sh --delete --limit all
#
# `--delete` on its own removes ONE alias, and that default is the point
# rather than timidity. See the next paragraph.
#
# DELETED AND UNREACHABLE ARE NOT THE SAME STATE, AND THIS IS MEASURED.
# On 2026-08-25 the teardown for pull request #1003 listed one deployment for
# `pr-1003`, deleted it with `force=true`, and Cloudflare answered
# `"success": true` (run 32847903961). Thirty-two minutes later
# `https://pr-1003.ourhike-preview.pages.dev/` still answered 200, and it was
# still serving that deployment's own files rather than falling back to
# anything else: `/assets/main-BTYohYcr.js` returned 816,086 bytes there and
# the SPA fallback on `pr-994`, and `/__screenshot/first-run.png` returned
# 310,289 bytes. Cloudflare documents no retention or propagation delay for a
# deleted deployment's branch alias, so what happens after that is not known
# here.
#
# So this script measures reachability rather than inferring it, before and
# after every deletion, and a successful delete that leaves the URL answering
# is reported as the failure it is (exit 2). That is also why `--delete`
# defaults to one alias: deleting hundreds and discovering afterwards that
# hundreds are still serving would waste the only irreversible move available.
#
# THE FILTER IS NOT REIMPLEMENTED HERE. Choosing which *aliases* are due is
# this script's job; choosing which *deployments* belong to an alias stays
# `delete.sh`'s, and this shells out to it once per alias. Its exact-match
# rule - `pr-28` never selects `pr-281` - is the part most worth not writing
# twice, and it is the only thing between this and deleting something that
# matters. The cost is that `delete.sh` re-lists the whole project per alias:
# that listing took 16.4 seconds in run 32847903961, so a hundred aliases is
# something like half an hour. Slow and reusing the reviewed filter beats fast
# and having two of them.
#
# IT IS NOT COSTING ANYTHING TO LEAVE THEM UP, WHICH IS NOT A REASON TO.
# Cloudflare's Pages limits page states "You can have an unlimited number of
# preview deployments active on your project at a time" (read 2026-08-25), and
# the free plan's 20,000-file ceiling is per site rather than cumulative. The
# exposure is what this is about: unreviewed builds against the real Supabase
# project, reachable indefinitely at guessable URLs, vouched for by nothing.

set -euo pipefail

GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-OurHike/OurHike}"

# Overridable so the suite can point both at local stand-ins. There is no
# other way to exercise a script whose whole job is issuing DELETEs: against
# the real API the only honest test would destroy something.
API_BASE="${API_BASE:-https://api.cloudflare.com/client/v4}"
GITHUB_API_BASE="${GITHUB_API_BASE:-https://api.github.com}"

# Where a preview answers. `pr-preview.yml` works the same URL out the same
# way and documents the same assumption: that the project's pages.dev
# subdomain matches the project name, which is how Pages names them.
PREVIEW_URL_TEMPLATE="${PREVIEW_URL_TEMPLATE:-https://%s.${CLOUDFLARE_PAGES_PROJECT:-}.pages.dev/}"

DELETE_SCRIPT="${DELETE_SCRIPT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.github/actions/delete-pages-previews/delete.sh}"

do_delete=false
limit=""
keep_days=0
settle_seconds=60
probe_timeout=15
probe=true
only=""

usage() {
  sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed 's/^#\{1,2\} \{0,1\}//; $d'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --delete) do_delete=true ;;
    --limit) limit="${2:?--limit needs a number or 'all'}"; shift ;;
    --keep-closed-within-days) keep_days="${2:?--keep-closed-within-days needs a number}"; shift ;;
    --settle-seconds) settle_seconds="${2:?--settle-seconds needs a number}"; shift ;;
    --probe-timeout) probe_timeout="${2:?--probe-timeout needs a number}"; shift ;;
    --only) only="${2:?--only needs pr-<n>[,pr-<n>...]}"; shift ;;
    --no-probe) probe=false ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage >&2; exit 64 ;;
  esac
  shift
done

# One alias unless told otherwise, and only under --delete. Deleting is
# irreversible and the state it is supposed to produce - a URL that stops
# answering - has been observed not to follow (see the header). A first batch
# of one costs a minute and settles that for this project; a first batch of
# hundreds cannot be taken back if it does not.
if [ -z "$limit" ]; then
  if $do_delete; then limit=1; else limit=all; fi
fi
if [ "$limit" != "all" ] && ! [[ "$limit" =~ ^[0-9]+$ ]]; then
  echo "--limit takes a number or 'all', not '$limit'" >&2
  exit 64
fi
if ! [[ "$keep_days" =~ ^[0-9]+$ ]]; then
  echo "--keep-closed-within-days takes a number, not '$keep_days'" >&2
  exit 64
fi

# After the arguments, not before them, so that --help works for somebody who
# has not been given the token yet - which is most people reading this.
: "${CLOUDFLARE_API_TOKEN:?set CLOUDFLARE_API_TOKEN - see the header of this script}"
: "${CLOUDFLARE_ACCOUNT_ID:?set CLOUDFLARE_ACCOUNT_ID - see the header of this script}"
: "${CLOUDFLARE_PAGES_PROJECT:?set CLOUDFLARE_PAGES_PROJECT - see the header of this script}"
: "${GITHUB_TOKEN:?set GITHUB_TOKEN - the plan is decided from pull request states}"

for tool in curl jq; do
  command -v "$tool" >/dev/null || { echo "$tool is required" >&2; exit 69; }
done
[ -f "$DELETE_SCRIPT" ] || { echo "cannot find delete.sh at $DELETE_SCRIPT" >&2; exit 69; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

DEPLOYMENTS="$API_BASE/accounts/$CLOUDFLARE_ACCOUNT_ID/pages/projects/$CLOUDFLARE_PAGES_PROJECT/deployments"

cf_api() {
  # Deliberately not --fail, for the reason delete.sh gives: a Cloudflare
  # error arrives as a 200 carrying "success": false at least as often as it
  # arrives as a 4xx, and the message inside the body is the useful part of
  # either.
  curl -sS -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json" "$@"
}

probe_alias() {
  local alias="$1" url code
  # shellcheck disable=SC2059 - the template is ours, not user input.
  url="$(printf "$PREVIEW_URL_TEMPLATE" "$alias")"
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time "$probe_timeout" "$url" 2>/dev/null || echo 000)"
  printf '%s' "$code"
}

# ---------------------------------------------------------------- list them

echo "Listing every preview deployment in '$CLOUDFLARE_PAGES_PROJECT'."

: >"$WORK/deployments.jsonl"
page=1
page_sizes=""
while :; do
  # NO `per_page`, for #1001's reason: asking for 100 got every list refused,
  # and the ceiling that would make some other number safe is published
  # nowhere. Taking whatever Cloudflare defaults to is correct at any cap.
  if ! response="$(cf_api "$DEPLOYMENTS?env=preview&page=$page")"; then
    echo "::error::Could not reach the Cloudflare API to list deployments for '$CLOUDFLARE_PAGES_PROJECT'." >&2
    exit 1
  fi
  if [ "$(jq -r '.success // false' <<<"$response")" != "true" ]; then
    reason="$(jq -r '[.errors[]?.message] | join("; ")' <<<"$response" 2>/dev/null || true)"
    echo "::error::Cloudflare declined to list deployments for '$CLOUDFLARE_PAGES_PROJECT': ${reason:-no reason given}. If that is a permissions problem, the token needs \"Cloudflare Pages: Edit\" on this account." >&2
    exit 1
  fi
  count="$(jq '.result | length' <<<"$response")"
  [ "$count" -eq 0 ] && break
  jq -c '.result[]' <<<"$response" >>"$WORK/deployments.jsonl"
  page_sizes="$page_sizes $count"
  page=$(( page + 1 ))
done

total_deployments="$(wc -l <"$WORK/deployments.jsonl" | tr -d ' ')"
pages_read=$(( page - 1 ))

# The open question #1001 left behind, answered as a side effect rather than
# guessed at: whatever Cloudflare hands back when asked for no page size is
# its default, and it is the only figure about `per_page` anybody here has
# ever measured. Printed rather than hard-coded anywhere - a later reader
# should re-measure rather than trust this line.
first_page_size="$(printf '%s' "$page_sizes" | awk '{print $1}')"
echo "  $total_deployments preview deployment(s) over $pages_read page(s); Cloudflare's own page size, sent none, was ${first_page_size:-0}."

# Alias per deployment. Both markers, exactly as delete.sh matches them: the
# branch recorded against the deployment is what `--branch` set, the alias
# URLs are what it actually serves from, and only one of the two is
# guaranteed to be populated.
jq -r '
  ( .deployment_trigger.metadata.branch? // "" ) as $branch
  | ( [ .aliases[]? | capture("^https://(?<a>pr-[0-9]+)\\.") | .a ] | first // "" ) as $from_alias
  | ( if ($branch | test("^pr-[0-9]+$")) then $branch else $from_alias end ) as $alias
  | [ ( if $alias == "" then "-" else $alias end ), .id, ( .created_on // "" ) ]
  | @tsv
' "$WORK/deployments.jsonl" >"$WORK/aliased.tsv"

# Anything that is not a `pr-<n>` preview is listed and then left alone, never
# counted as swept. Nothing here infers "which deployments" from position,
# recency or count, and an unrecognised deployment is the case where that
# temptation is strongest.
awk -F'\t' '$1 == "-"' "$WORK/aliased.tsv" >"$WORK/unrecognised.tsv" || true
unrecognised="$(wc -l <"$WORK/unrecognised.tsv" | tr -d ' ')"
if [ "$unrecognised" -gt 0 ]; then
  echo "  $unrecognised deployment(s) carry no pr-<n> identity. Left alone, and listed here so that is a decision rather than an omission:"
  cut -f2,3 "$WORK/unrecognised.tsv" | sed 's/^/    /'
fi

awk -F'\t' '$1 != "-" { print $1 }' "$WORK/aliased.tsv" | sort -u >"$WORK/aliases.txt"

if [ -n "$only" ]; then
  printf '%s\n' "${only//,/$'\n'}" | sed '/^$/d' | sort -u >"$WORK/only.txt"
  comm -12 "$WORK/aliases.txt" "$WORK/only.txt" >"$WORK/aliases.filtered.txt"
  mv "$WORK/aliases.filtered.txt" "$WORK/aliases.txt"
fi

alias_count="$(wc -l <"$WORK/aliases.txt" | tr -d ' ')"
echo "  $alias_count pull request alias(es)."
echo

# ------------------------------------------------------------ decide on them

cutoff=""
if [ "$keep_days" -gt 0 ]; then
  cutoff="$(date -u -d "$keep_days days ago" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null \
    || date -u -v-"${keep_days}"d +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || true)"
  [ -n "$cutoff" ] || { echo "could not work out a date $keep_days days ago" >&2; exit 69; }
fi

# An open pull request's preview must survive; that is not a judgement call.
# Everything else is one, so it is made here, once, in the open: a closed pull
# request's preview is exactly what this sweep exists to remove, so the
# default window is zero and keeping yesterday's closures is something you ask
# for. A pull request GitHub does not have is kept and flagged - a `pr-<n>`
# with no pull request N behind it should not exist, and "delete the ones I
# cannot explain" is the wrong direction on the one irreversible step.
printf '%-10s %5s  %-22s %-6s  %s\n' ALIAS BUILDS "PULL REQUEST" LIVE DECISION
: >"$WORK/plan.tsv"
while IFS= read -r alias; do
  [ -n "$alias" ] || continue
  number="${alias#pr-}"
  builds="$(awk -F'\t' -v a="$alias" '$1 == a' "$WORK/aliased.tsv" | wc -l | tr -d ' ')"

  code="$(curl -sS -o "$WORK/pr.json" -w '%{http_code}' --max-time 30 \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "$GITHUB_API_BASE/repos/$GITHUB_REPOSITORY/pulls/$number" 2>/dev/null || echo 000)"

  if [ "$code" = "200" ]; then
    state="$(jq -r '.state // "unknown"' "$WORK/pr.json")"
    closed_at="$(jq -r '.closed_at // ""' "$WORK/pr.json")"
  else
    state="http-$code"
    closed_at=""
  fi

  case "$state" in
    open)
      decision=keep; why="open" ;;
    closed)
      if [ -n "$cutoff" ] && [ -n "$closed_at" ] && [[ "$closed_at" > "$cutoff" ]]; then
        decision=keep; why="closed ${closed_at%T*}, inside the $keep_days-day window"
      else
        decision=delete; why="closed ${closed_at%T*}"
      fi ;;
    *)
      decision=keep; why="GitHub said $state - needs a human" ;;
  esac

  live=-
  if $probe; then live="$(probe_alias "$alias")"; fi

  printf '%-10s %5s  %-22s %-6s  %s\n' "$alias" "$builds" "$why" "$live" "$decision"
  printf '%s\t%s\t%s\t%s\t%s\n' "$alias" "$builds" "$state" "$live" "$decision" >>"$WORK/plan.tsv"
done <"$WORK/aliases.txt"

echo
due_total="$(awk -F'\t' '$5 == "delete"' "$WORK/plan.tsv" | wc -l | tr -d ' ')"
kept_total="$(awk -F'\t' '$5 == "keep"' "$WORK/plan.tsv" | wc -l | tr -d ' ')"
due_builds="$(awk -F'\t' '$5 == "delete" { n += $2 } END { print n + 0 }' "$WORK/plan.tsv")"
if $probe; then
  live_due="$(awk -F'\t' '$5 == "delete" && $4 == 200' "$WORK/plan.tsv" | wc -l | tr -d ' ')"
  echo "$due_total alias(es) due, $due_builds build(s) between them, $live_due of them answering 200 right now. $kept_total kept."
else
  echo "$due_total alias(es) due, $due_builds build(s) between them. $kept_total kept. Reachability not probed."
fi

if ! $do_delete; then
  echo
  echo "Nothing was deleted. Re-run with --delete to remove the first one, then"
  echo "--delete --limit all once you have confirmed its URL stopped answering."
  exit 0
fi

# ------------------------------------------------------------- delete them

awk -F'\t' '$5 == "delete" { print $1 }' "$WORK/plan.tsv" >"$WORK/due.txt"
if [ "$limit" != "all" ]; then
  head -n "$limit" "$WORK/due.txt" >"$WORK/batch.txt"
else
  cp "$WORK/due.txt" "$WORK/batch.txt"
fi
batch="$(wc -l <"$WORK/batch.txt" | tr -d ' ')"
skipped=$(( due_total - batch ))

echo
if [ "$batch" -eq 0 ]; then
  echo "Nothing to delete."
  exit 0
fi
if [ "$skipped" -gt 0 ]; then
  # Never a silent cap. A run that removed 1 of 240 and said "done" reads
  # exactly like one that removed all of them.
  echo "Deleting $batch of $due_total due alias(es); $skipped left for a later run (--limit)."
else
  echo "Deleting all $batch due alias(es)."
fi

: >"$WORK/results.tsv"
while IFS= read -r alias; do
  [ -n "$alias" ] || continue
  before="$(probe_alias "$alias")"
  out="$WORK/out-$alias"
  : >"$out"
  status=0
  ALIAS="$alias" \
  API_TOKEN="$CLOUDFLARE_API_TOKEN" \
  ACCOUNT_ID="$CLOUDFLARE_ACCOUNT_ID" \
  PROJECT="$CLOUDFLARE_PAGES_PROJECT" \
  API_BASE="$API_BASE" \
  GITHUB_OUTPUT="$out" \
  PREVIEW_URL_TEMPLATE="$PREVIEW_URL_TEMPLATE" \
    bash "$DELETE_SCRIPT" </dev/null || status=$?
  # </dev/null so the child cannot eat the alias list this loop is reading
  # from. It does not today - it only ever curls - but a loop that silently
  # processes one item and reports success is the shape of failure this whole
  # file is about.
  found="$(sed -n 's/^found=//p' "$out" | tail -1)"
  deleted="$(sed -n 's/^deleted=//p' "$out" | tail -1)"
  failed="$(sed -n 's/^failed=//p' "$out" | tail -1)"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$alias" "${found:-0}" "${deleted:-0}" "${failed:-?}" "$before" "$status" >>"$WORK/results.tsv"
done <"$WORK/batch.txt"

# Settle before re-probing, because "it answered 200 one second later" and "it
# is still being served" are different claims and only the second one matters.
# What this window is worth is not known: 32 minutes was not enough for
# pr-1003 on 2026-08-25, and Cloudflare documents nothing about it. The
# default is a minute because a human is watching; it is not a finding.
if [ "$settle_seconds" -gt 0 ]; then
  echo
  echo "Waiting ${settle_seconds}s before re-probing."
  sleep "$settle_seconds"
fi

echo
printf '%-10s %6s %8s %7s  %-7s %s\n' ALIAS FOUND DELETED FAILED BEFORE AFTER
still_serving=0
could_not_delete=0
while IFS=$'\t' read -r alias found deleted failed before status; do
  after="$(probe_alias "$alias")"
  printf '%-10s %6s %8s %7s  %-7s %s\n' "$alias" "$found" "$deleted" "$failed" "$before" "$after"
  if [ "$status" != "0" ] || [ "${failed:-1}" != "0" ]; then
    could_not_delete=$(( could_not_delete + 1 ))
  elif [ "$after" = "200" ]; then
    still_serving=$(( still_serving + 1 ))
  fi
done <"$WORK/results.tsv"

echo
if [ "$could_not_delete" -gt 0 ]; then
  echo "$could_not_delete alias(es) could not be deleted and are still reachable. See the output above for what Cloudflare said." >&2
  exit 1
fi

if [ "$still_serving" -gt 0 ]; then
  echo "Cloudflare accepted every deletion, and $still_serving alias(es) are still answering 200 ${settle_seconds}s later." >&2
  echo "That is the state #1004 measured on pr-1003 and it is the whole point of stopping at a small batch: deleting the rest would not make them unreachable either. Do not widen this run - work out what is still serving them first." >&2
  exit 2
fi

echo "Every alias in this batch stopped answering."
if [ "$skipped" -gt 0 ]; then
  echo "$skipped due alias(es) remain. Re-run with --limit all."
fi
