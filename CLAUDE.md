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

## One branch per issue, unless the work is stacked

**Default: a new issue gets a new branch off `main`, its own pull request, and gets closed
out on its own.** Small and independently reviewable beats comprehensive, and a session
that finds three things should leave three pull requests.

The exception is work that sits **on top of** an open branch — it touches code that branch
is actively rewriting, or it only makes sense with those changes present. Splitting that
does not produce two clean reviews. It produces two pull requests that conflict with each
other and a merge order somebody has to hold in their head. Keep it where it depends, and
say plainly in the pull request that it closes two issues and why.

**The test is dependency, not subject or size.** [#216](https://github.com/OurHike/OurHike/issues/216)
had nothing to do with [#210](https://github.com/OurHike/OurHike/issues/210)
as a problem — one was a blank background, the other was how you reach the download — but
its fix landed in `App.tsx`, `MapScreen.tsx` and `BackgroundPicker.tsx` while #210 was
rewriting all three. It stayed, and the pull request said so.

Switching branches is nearly free. What costs is re-verifying and resolving conflicts, so
the number worth minimising is how many times the full check suite has to run — not how
many branches exist. Do not let "fewer branches" become the goal it is not.

## Run what CI runs, before pushing

Every suite CI runs, not only the one you touched:

```
cd client        && npm run typecheck && npm run lint && npm run format:check && npm test && npm run build
cd pipeline      && python -m ruff check . && python -m ruff format --check . && python -m pytest
cd backend       && python -m ruff check . && python -m ruff format --check . && python -m pytest
cd .github/tests && python -m ruff check . && python -m ruff format --check . && python -m pytest
```

A push that fails on formatting spends a full CI round trip learning something
`ruff format --check` would have said in one second. That has happened, on a job that runs
the formatter *before* the tests — so the pipeline suite never ran at all and the log said
nothing about the change being made.

**Tests that depend on ordering get run several times before they are pushed.** Anything
awaiting an effect, a rebuild, or a mocked promise. Passing once on an idle machine is not
evidence: two tests written that way passed here and failed on CI, where a map was rebuilt
between the camera move and the assertion. A longer `findByText` window would not have
saved them — the state was gone, not late. Wait on something observable that proves the
sequence completed, and prove it holds by running the file three times.

Where the environment cannot run a check at all, confirm that against a clean tree, then
say so in the pull request rather than reporting a clean run you did not have. The old
standing example — the sandbox proxy 403s DuckDB's extension downloads, which failed a
large block of the pipeline suite on a clean tree (measured 2026-08-06: 515 passed,
27 failed, 36 errors, every one tracing back to `Failed to download extension "spatial"`)
— is handled now: `.claude/hooks/session-start.sh` seeds the extension from PyPI when a
web session starts. A run that still shows that signature means the hook did not run; run
it by hand rather than reporting those failures as environmental. What genuinely cannot
run here is backend's Postgres job — the sandbox has no Postgres service, so
`python -m pytest` in `backend/` exercises only the DuckDB engine, and a pull request
that changes backend behavior should say so.
