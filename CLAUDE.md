# Working in this repository as Claude

[CONTRIBUTING.md](CONTRIBUTING.md) applies in full — the build commands, the testing
expectations, the "one home per item" rule for docs and issues. This file covers only
what is specific to an agent working here, and does not restate the rest.

## Name an issue or PR, don't just number it

**Every reference to an issue or pull request carries its number *and* its title** — in chat,
in pull request bodies, in issue comments, in anything reporting what was done. Write:

> **#555 — The Fine tier is offered on iOS, where WebKit will not hold it** and
> **#554 — Deleting a map does not give the space back in time to download a bigger one**
> are both storage headroom, and only one of them is a platform question.

not "#555 and #554 are both storage headroom, and only one is a platform question." The
second version is shorter and tells the reader nothing — they have to open two tabs before
they can judge whether any of it is theirs to care about.

A bare number is worse in this repository than in most, because `#N` here is not reliably an
issue at all. [FEATURES.md](FEATURES.md) numbers the *values* that way — "Community reporting
*(#2, #4)*" means values two and four — while [pipeline/README.md](pipeline/README.md) uses
the same notation for issues (`#184/#185/#186`) and
[features/MAP_STYLE_SPEC.md](features/MAP_STYLE_SPEC.md) for a pull request (`PR #345`). The
title is the only thing that separates them on sight.

The habit is already here, applied unevenly. **#558 — Let a hiker take the stretch they are
walking, without picking it off a list** opens by declaring itself "Blocked on #552 (which
unit)": the gloss got added because the bare number would not have carried the sentence, and
the six other issues that body cites went without one. Write the title rather than a
parenthetical, and write it for every reference — not only the one that felt ambiguous while
you were typing it.

One form stays bare, because GitHub parses it rather than reads it: the closing line in a
pull request body is exactly `Closes #42`, the linking mechanism
[CONTRIBUTING.md](CONTRIBUTING.md) describes and CI enforces as **PR has a linked issue**.
Leave that line alone and name the issue in full in the prose above it.

This governs what you write. It is not a licence to go retitling references in files you are
not otherwise touching.

## Claim the issue before you branch

Sessions run concurrently and unsupervised, and nothing stops two of them from picking up
the same GitHub issue at the same time. That has now happened **twice**, both times caught
by a human noticing rather than by anything in the repository.

The second time is the one worth reading, because everybody followed this section as it
was written and it happened anyway. **#597 — A waypoint that loses a collision disappears,
when it could be a dot** was claimed at 02:31 by a session that had checked the timeline
and the ledger and found nothing. Twelve minutes later a second session opened
**#610 — Draw every waypoint as a pin or a dot, and never as neither** against the same
issue. Both were green. One entire implementation was thrown away.

Nothing below would have caught it, because **the second session never opened a branch**.
It stacked #597 onto a branch already carrying two unrelated pipeline issues — which
[BRANCHING.md](BRANCHING.md) §3 explicitly allows — so `scripts/threads.sh` had no new
branch to show and reported that branch as `suites: pipeline` right up until the client
commit landed. The heading said "before you branch", and a session that was not branching
read itself as out of scope.

So the trigger is **starting work on an issue**, not opening a branch for one. Stacking is
the case that feels exempt and is not: adding an issue to a branch you already have is
picking up that issue, and it needs the same claim as a fresh branch would. `#594`'s claim
comment on that same branch shows the practice being applied correctly an hour earlier —
what failed was the rule's *scope*, not anybody's diligence.

Before starting work on an issue — a new branch, a new commit on an existing one, or a
pull request body that will carry `Closes #N`:

- Read the issue's timeline, not just its body. Check the "Development" sidebar for a
  linked pull request, and read the comments for one saying work has already started —
  a comment is a claim even before a branch or PR exists to back it up.
- Check `scripts/threads.sh --fetch` for a branch already carrying that issue's subject.
  Branch names encode the topic, not the issue number, so this means reading what each
  branch is about, not grepping for `#N`.
- If either turns up a live claim, stop. Do not open a second branch or a second PR for
  the same issue — say so to whoever asked, and either pick a different issue or work the
  dependency where the existing branch already lives ([BRANCHING.md](BRANCHING.md) §3).

If nothing turns up, claim the issue immediately, before writing any code: leave a comment
on the issue naming the branch you are about to push — or the branch you are stacking it
onto, which is the case that gets forgotten. This is the only signal that works — every
session authenticates as the same GitHub identity (see below), so assigning the issue
proves nothing and self-assignment cannot distinguish one session from another. A plain,
timestamped comment is what the next session checking this issue will actually find.

**Release the claim if you stop.** A claim pointing at a closed or abandoned pull request
is worse than no claim: it reads as live work and stops the next session touching the
issue. One comment saying the branch is free costs nothing and is the other half of making
claims mean anything.

### What actually catches this now

`pr-issue-link.yml` reads the `Closes #N` every pull request already carries and warns —
in the check summary, as an annotation, and as one sticky comment — when another **open**
pull request closes the same issue. It warns rather than fails, because two pull requests
closing one issue is occasionally deliberate and a red check would block that to catch the
common case.

**It catches the collision at the pull request, which is late.** By then both
implementations exist and the only thing saved is the second review. Nothing mechanical
watches at claim time, and the checks above are still the only thing that can save the
work rather than the review — so they are not optional now that a backstop exists.

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

Merging `main` **into** a branch you are working on, *when the branch needs it*. Direction
is the whole rule: `main` flows down into your branch, never the reverse.

If a branch has drifted too far to reconcile honestly, say so in the pull request and
leave it. Do not resolve it by pushing to `main`.

## Never cut a release either

Same rule, one step further down the pipe: **do not push a tag, do not publish a GitHub
release, do not promote anything to production.** Shipping to hikers is the maintainer's
decision for the same reason landing on `main` is, and with the same invisibility
afterwards — the token authenticates as the repository owner, so a tag an agent pushed
and a tag the owner pushed are the same object.

Everything up to that line is fine and is the job: prepare the branch, generate the
notes, run the gate, open the pull request, create the GitHub release **as a draft**.
Publishing the draft is a human action. [RELEASING.md](RELEASING.md) is the full
process — §12 is this rule with its mechanism.

## Do not merge `main` in just to be current

**Being behind `main` is not a defect, and catching up is not part of finishing the work.**
GitHub merges the pull request against `main` as it stands when the button is pressed, so a
branch eleven commits behind produces the same merge commit as one freshly caught up.

Forty-six of the last seventy-three `main`-into-branch merges in this repository resolved
nothing — empty combined diffs, a full CI round trip each, bought nothing. This file used
to ask for them. It was wrong.

Merge `main` in when `scripts/threads.sh` reports `CONFLICTS`, when the branch cannot pass
its own tests without something on `main`, or when the maintainer asks. Otherwise leave it
alone and say in the pull request that it merges clean.

[BRANCHING.md](BRANCHING.md) is the full strategy — how to slice work so branches do not
collide, which files actually cause the collisions, and what order to land things in. Read
it before opening a second concurrent branch. It also holds the one-branch-per-issue rule
that used to live here.

## A build script's output has a home, and it is not the repository

Before running a script that writes a file, decide where that file lives — because
committing it is the one choice that cannot be undone. [CONTRIBUTING.md](CONTRIBUTING.md)
has the rule and the reasoning ("Data does not go in commits"); what an agent needs is the
trigger: **you are about to add a generated file, so pick its shelf first.**

`pipeline/data/` for anything fetched or derived — gitignored, cached between CI runs,
published to R2 by `publish.py`. `pipeline/reference/` **only** for a join that encodes
judgement somebody reviews row by row, and it has a line ceiling for exactly that reason.

This is written down because an agent did the wrong one and had a good story for it:
`reference/` is not gitignored, holds three small checked-in files, and reads as "where
derived things go", so a 20,099-line derivation went in with a docstring explaining why it
belonged there. Every sentence of that explanation was about *reproducibility*, and none of
it noticed that the file was a permanent publication of somebody else's data. The maintainer
caught it in review. `.github/tests/test_no_committed_data.py` catches it now.

## Run what CI runs, before pushing

```
scripts/test.sh
```

That is the whole command. It works out which suites your changes actually
reach — reading each one's scope list out of its own workflow YAML, so it
cannot disagree with CI by being forgotten — and runs those, linters and
formatters first, each suite across every core. A change to one of the Python
parts finishes in 20 to 50 seconds; `--all` is the full four suites in 174s,
against 294s for running them by hand. `--list` says what it picked and which
file decided it, `--all` overrides the scoping, and `--coverage` puts the
coverage reports back.

Every uncertain case runs everything rather than guessing — a stale `main`
ref, an unreadable workflow, a detached head — so a wrong answer costs a
minute, never a missed regression. If you want the long-hand form anyway, or
the script cannot run:

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
it by hand rather than reporting those failures as environmental. Backend's Postgres job
used to be the other standing example — "the sandbox has no Postgres service, so
`python -m pytest` in `backend/` exercises only the DuckDB engine." That was wrong: the
container ships Postgres 16 with its cluster stopped. `backend/scripts/local-postgres.sh`
starts it (the session-start hook now does too), and the backend suite runs against the
same engine CI and production use. A connection-refused failure in `backend/` means that
script has not been run, not that the check cannot run here.
