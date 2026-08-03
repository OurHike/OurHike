# Working in this repository as Claude

[CONTRIBUTING.md](CONTRIBUTING.md) applies in full — the build commands, the testing
expectations, the "one home per item" rule for docs and issues. This file covers only
what is specific to an agent working here, and does not restate the rest.

## Never merge into `main`

**Landing work on `main` is the maintainer's decision, not yours.** No `merge_pull_request`
API call, no `git merge` of a branch into `main`, no push that puts a branch's commits
there — including when CI is green, the PR is approved, and the change is plainly correct.
Plainly correct is exactly the case where a wrong call is cheapest to make and slowest to
notice.

Open the pull request, describe what you did and what you were unsure about, and stop.

Nothing enforces this. The GitHub token in an agent session authenticates as the
repository owner, so a merge performed by an agent is recorded as a merge by the owner,
and the git history cannot afterwards tell the two apart — neither the author, the
committer, nor the PR's `merged_by` field distinguishes them. The rule holds because it is
followed, not because a breach would be visible later.

## What is still fine

Merging `main` **into** a branch you are working on. Keeping a long-running branch current
and resolving its conflicts is part of finishing the work, and it is the maintainer who
then decides whether the result lands.

Direction is the whole rule: `main` flows down into your branch, never the reverse.

If a branch has drifted too far to reconcile honestly, say so in the pull request and
leave it. Do not resolve it by pushing to `main`.
