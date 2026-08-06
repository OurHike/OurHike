#!/usr/bin/env bash
#
# Deletes every Cloudflare Pages deployment belonging to one pull request's
# preview alias. See action.yml for why this is not something Cloudflare does
# on its own.

set -euo pipefail

: "${API_TOKEN:?}"
: "${ACCOUNT_ID:?}"
: "${PROJECT:?}"

# Not `:?` like the rest, because an empty alias is the most likely way this
# ever goes wrong - an upstream step that produced nothing - and it deserves
# the explanation below rather than bash's "parameter null or not set", which
# carries no ::error:: annotation and so does not surface in the run summary
# at all. The check below rejects it either way.
ALIAS="${ALIAS:-}"

# Overridable so the tests can point this at a local stand-in for the
# Cloudflare API. There is no other way to exercise a function whose entire
# job is issuing DELETEs - against the real API the only honest test would
# destroy something.
API_BASE="${API_BASE:-https://api.cloudflare.com/client/v4}"

# The alias is the only thing between "tidy up a closed pull request" and
# "delete a deployment somebody is using". A filter one character too loose
# would not look wrong in review and would not fail a test that only checks
# the happy path, so the shape is asserted before anything is even listed.
if [[ ! "$ALIAS" =~ ^pr-[0-9]+$ ]]; then
  echo "::error::Refusing to delete anything: '$ALIAS' is not a pull request preview alias (expected pr-<number>)."
  exit 1
fi

DEPLOYMENTS="$API_BASE/accounts/$ACCOUNT_ID/pages/projects/$PROJECT/deployments"

found=0
deleted=0
failed=0

report() {
  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    {
      echo "found=$found"
      echo "deleted=$deleted"
      echo "failed=$failed"
    } >>"$GITHUB_OUTPUT"
  fi
}
trap report EXIT

api() {
  # Deliberately not --fail: a Cloudflare error arrives as a 200 carrying
  # "success": false at least as often as it arrives as a 4xx, and the message
  # inside the body is the only useful part of either.
  curl -sS -H "Authorization: Bearer $API_TOKEN" -H "Content-Type: application/json" "$@"
}

# Collect every id first, and only then delete. Not page-by-page-deleting as
# it goes: removing items from a paginated collection while paging through it
# shifts everything after them back a place, so the next page begins past
# whatever moved into the slots just vacated and those are never looked at.
# What that produces is a cleanup that silently leaves some behind - which is
# the exact failure this action exists to prevent, arrived at by way of the
# fix for it.
ids=()
page=1
while :; do
  if ! response="$(api "$DEPLOYMENTS?env=preview&per_page=100&page=$page")"; then
    echo "::error::Could not reach the Cloudflare API to list deployments for '$PROJECT'."
    exit 1
  fi

  if [ "$(jq -r '.success // false' <<<"$response")" != "true" ]; then
    jq -r '.errors[]?.message // empty' <<<"$response" >&2 || true
    echo "::error::Cloudflare declined to list deployments for '$PROJECT'. The token needs \"Cloudflare Pages: Edit\" on this account."
    exit 1
  fi

  if [ "$(jq '.result | length' <<<"$response")" -eq 0 ]; then
    break
  fi

  # Matched two ways because only one of them is guaranteed to be there. The
  # branch recorded against the deployment is what `--branch` set and is the
  # authoritative answer; the alias URLs are what the deployment actually
  # serves from. Either alone identifies this pull request's deployments, and
  # if Cloudflare ever stops populating one the other still finds them.
  #
  # Both are exact rather than prefix matches. `pr-28` must never select
  # `pr-281`, and a `startswith` on the branch would do precisely that.
  while IFS= read -r id; do
    if [ -n "$id" ]; then
      ids+=("$id")
    fi
  done < <(jq -r --arg alias "$ALIAS" '
    .result[]
    | select(
        (.deployment_trigger.metadata.branch? == $alias)
        or (any(.aliases[]?; startswith("https://" + $alias + ".")))
      )
    | .id
  ' <<<"$response")

  page=$(( page + 1 ))
done

found=${#ids[@]}

if [ "$found" -eq 0 ]; then
  echo "No deployments found for '$ALIAS'; nothing to remove."
  exit 0
fi

echo "Found $found deployment(s) for '$ALIAS'."

for id in "${ids[@]}"; do
  # force=true because the newest deployment for an alias is the one holding
  # that alias, and it is the single most important one to remove - a cleanup
  # that deleted every deployment except the one still serving the URL would
  # have achieved nothing at all. What makes that safe is the filter above,
  # not restraint here.
  if response="$(api -X DELETE "$DEPLOYMENTS/$id?force=true")" \
    && [ "$(jq -r '.success // false' <<<"$response")" = "true" ]; then
    deleted=$(( deleted + 1 ))
  else
    failed=$(( failed + 1 ))
    echo "Could not delete deployment $id:" >&2
    jq -r '.errors[]?.message // empty' <<<"${response:-{\}}" >&2 || true
  fi
done

echo "Deleted $deleted of $found deployment(s) for '$ALIAS'."

if [ "$failed" -gt 0 ]; then
  echo "::error::$failed of $found deployment(s) for '$ALIAS' could not be deleted and are still reachable."
  exit 1
fi
