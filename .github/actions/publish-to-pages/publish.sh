#!/usr/bin/env bash
#
# Publishes a directory as the entire contents of a branch, and survives
# losing a race to another push. See action.yml for why that is not automatic.
#
# Every attempt rebuilds the commit from a fresh clone of the current remote
# tip rather than replaying one it built earlier. That is what makes a lost
# race safe to retry: the published tree is a function of `source-dir` alone,
# never of what happened to be on the branch when this job started, so there
# is nothing to merge and so nothing that can conflict.

set -euo pipefail

: "${SOURCE_DIR:?}"
: "${BRANCH:?}"
: "${COMMIT_MESSAGE:?}"
: "${REMOTE_URL:?}"
: "${MAX_ATTEMPTS:?}"
: "${BACKOFF_BASE_SECONDS:?}"
: "${BACKOFF_CAP_SECONDS:?}"

GIT_USER_NAME="${GIT_USER_NAME:-github-actions[bot]}"
GIT_USER_EMAIL="${GIT_USER_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"

if [ ! -d "$SOURCE_DIR" ]; then
  echo "::error::source-dir '$SOURCE_DIR' does not exist. Refusing to publish, because what would be published instead is an empty branch - which is to say, the site taken down."
  exit 1
fi

# Absolute: the copy below runs against a working tree somewhere else.
SOURCE_DIR="$(cd "$SOURCE_DIR" && pwd)"

if [ -z "$(ls -A "$SOURCE_DIR")" ]; then
  echo "::error::source-dir '$SOURCE_DIR' is empty. Publishing it would take the site down, which is not something a build failing quietly should be able to do."
  exit 1
fi

WORK="$(mktemp -d)"

pushed=false
attempts=0

# Reported from a trap rather than from the end of the script, so that the two
# ways out that are not the end - giving up after losing every race, and
# bailing on an error that is not contention - still say how many attempts it
# took. On a failure that is the number worth having: it is the difference
# between "this deploy never got a turn" and "this deploy could not have got
# one", which are not diagnosed the same way.
report() {
  rm -rf "$WORK"
  if [ -n "${GITHUB_OUTPUT:-}" ]; then
    {
      echo "pushed=$pushed"
      echo "attempts=$attempts"
    } >>"$GITHUB_OUTPUT"
  fi
}
trap report EXIT

# `$RANDOM` is seeded from the pid and the clock, which on separate runners is
# already distinct. Mixing the run id in costs nothing and closes the one case
# where it would not be - several jobs of one run starting in the same second
# on identically configured runners.
RANDOM=$(( ($$ + ${GITHUB_RUN_ID:-0} + ${GITHUB_RUN_ATTEMPT:-0}) % 32768 ))

branch_exists=false

# Rebuilds the whole commit from whatever is on the remote right now. Called
# once per attempt, so a push that lost a race is redone against what actually
# won rather than against what was there when this job started.
build_commit_from_tip() {
  rm -rf "$WORK"
  mkdir -p "$WORK"
  git init -q "$WORK"
  git -C "$WORK" remote add origin "$REMOTE_URL"
  git -C "$WORK" config user.name "$GIT_USER_NAME"
  git -C "$WORK" config user.email "$GIT_USER_EMAIL"

  # Shallow on purpose. This branch takes a commit per deploy and none of that
  # history is of any interest here - only the tip is. Pushing from a shallow
  # clone works precisely because the parent of the new commit is that tip,
  # which the remote already has.
  if git -C "$WORK" fetch --quiet --depth=1 --no-tags origin "$BRANCH" 2>/dev/null; then
    git -C "$WORK" checkout -q -B __publish FETCH_HEAD
    branch_exists=true
  else
    # No such branch yet - the first deploy into a repository that has never
    # had one. Not an error and not a race, so it does not consume an attempt.
    echo "Branch '$BRANCH' does not exist yet; creating it."
    git -C "$WORK" checkout -q --orphan __publish
    branch_exists=false
  fi

  # Clearing through git rather than `rm -rf` is what keeps this safe: git will
  # not delete `.git`, and an `rm -rf` of the working tree one day edited to
  # include dotfiles would.
  git -C "$WORK" rm -rq --ignore-unmatch -- .
  cp -a "$SOURCE_DIR"/. "$WORK"/
  git -C "$WORK" add -A
}

# True when the staged tree already matches the tip, i.e. this deploy would
# push a commit that changes nothing. Worth asking on every attempt rather than
# only the first: a rebuild that produces byte-identical output is ordinary,
# and the cheapest push is the one that never happens.
nothing_to_publish() {
  if [ "$branch_exists" = true ]; then
    git -C "$WORK" diff --cached --quiet --
  else
    [ -z "$(git -C "$WORK" ls-files --cached)" ]
  fi
}

for (( attempt = 1; attempt <= MAX_ATTEMPTS; attempt++ )); do
  attempts="$attempt"

  build_commit_from_tip

  if nothing_to_publish; then
    echo "Nothing to publish: '$BRANCH' already matches this build."
    pushed=false
    break
  fi

  git -C "$WORK" commit -q -m "$COMMIT_MESSAGE"

  # --porcelain so the outcome is parseable. Without it, "was this rejected"
  # has to be read out of human-facing text git is free to reword.
  push_output=""
  push_status=0
  push_output="$(git -C "$WORK" push --porcelain origin "__publish:refs/heads/$BRANCH" 2>&1)" || push_status=$?

  if [ "$push_status" -eq 0 ]; then
    echo "Published to '$BRANCH' on attempt $attempt of $MAX_ATTEMPTS."
    pushed=true
    break
  fi

  if ! grep -qE '\[(remote )?rejected\]|non-fast-forward|fetch first' <<<"$push_output"; then
    # Not contention. A bad token or a protected branch will not get better for
    # being retried nineteen more times, and burying the real message under
    # that many attempts is how a five-second fix becomes an afternoon.
    echo "$push_output"
    echo "::error::Pushing to '$BRANCH' failed for a reason that is not contention. Not retrying."
    exit 1
  fi

  if [ "$attempt" -ge "$MAX_ATTEMPTS" ]; then
    echo "$push_output"
    echo "::error::Gave up publishing to '$BRANCH' after $MAX_ATTEMPTS attempts, every one of them lost to another push. If that is routine rather than a bad day, raise max-attempts."
    exit 1
  fi

  # Full jitter: sleep a uniform random time in [0, ceiling] rather than the
  # ceiling itself. Backing off without jitter leaves every loser of a race in
  # lockstep, so they collide again on the next attempt and the one after.
  ceiling=$(( BACKOFF_BASE_SECONDS * (1 << (attempt - 1)) ))
  [ "$ceiling" -gt "$BACKOFF_CAP_SECONDS" ] && ceiling="$BACKOFF_CAP_SECONDS"
  delay=0
  [ "$ceiling" -gt 0 ] && delay=$(( RANDOM % (ceiling + 1) ))
  echo "Attempt $attempt lost the race for '$BRANCH'; rebuilding against the new tip and retrying in ${delay}s."
  sleep "$delay"
done
