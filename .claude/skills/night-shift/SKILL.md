---
name: night-shift
description: Work the backlog unattended - pick an eligible issue, claim it, build it, open a draft pull request, drive CI green, take the next one. Use when a scheduled run fires with nobody watching, or when the maintainer asks for a night-shift run. Covers the gate that decides what may be taken, the order, and the six things an unattended session must never do.
user-invocable: true
---

# The night shift

An unattended session working the backlog. The maintainer is asleep; nothing
here waits for an answer, and nothing here does anything a wrong answer cannot
be reverted from with one click.

[CLAUDE.md](../../../CLAUDE.md) applies in full and wins wherever this file
could be read as disagreeing with it — the evidence grades, the claim rule,
"Never merge into `main`", "Never cut a release either". This file is the
**order**, the way `release-train/SKILL.md` is the order for a release. It
restates as little as it can.

## The one-sentence version

Run `scripts/nightshift.sh`, take the top issue, claim it, branch, build it,
open a **draft** pull request, drive CI to green, take the next one — and stop
at the draft, every time, because the maintainer's merge is the only gate
standing between this lane and `main`.

## Why a draft pull request is the whole safety model

The night lane has no new authority. It cannot merge, cannot tag, cannot
publish to production. What it can do is arrive at morning with work already
built, tested and reviewable — so the maintainer's part is reading a diff
rather than starting one.

That is also why the gate below is about **who reviews**, not about difficulty.
A `client` issue is not harder; it is reviewed on a phone by somebody who can
see whether the thing looks right, and CI cannot stand in for that. Everything
else is reviewed by reading, and reading happens in the morning either way.

## 1. Ask what is eligible

```
scripts/nightshift.sh
```

It prints the queue in order, then every issue it may not take with the one
reason each. The gate is `scripts/night_queue.py`, held by
`.github/tests/test_night_queue.py` — if the answer looks wrong, that is where
the argument happens, not in a judgement call at 3am.

**Take the queue's order.** It is deliberate: a `deployment-health` issue is
open only while a check is red (`check-deployed-app.yml` — "opened green->red,
closed red->green"), so those describe the app failing *now*; then
`release-followup`, which names something a merge already left undone; then
least-recently-updated. That last tiebreak is `@unvalidated` and says so.

**Do not widen the queue.** An issue the script excluded is excluded. If the
exclusion looks wrong, say so in the morning report — do not take it anyway.

## 2. Claim it before writing any code

CLAUDE.md's "Claim the issue before you branch" in full, and the script only
does the mechanical half of it. It knows about an open pull request already
closing the issue; it cannot read a claim comment, because a claim is prose.

So before touching anything: read the issue's timeline and its Development
sidebar, and run `scripts/threads.sh --fetch` and read what each live branch is
about. If either turns up a live claim, **skip to the next issue in the queue**
and say so in the morning report. If nothing does, comment on the issue naming
the branch you are about to push, then start.

Two sessions have already collided on one issue and thrown an implementation
away. An unattended session is the case where nobody notices until morning.

## 3. Build it, one issue per branch

[BRANCHING.md](../../../BRANCHING.md) §3 — a new issue gets a new branch off
`main`, its own pull request, closed by its own merge. Stacking is for work
that genuinely sits on top of an open branch, and a stacked issue needs its own
claim comment exactly as a fresh one does.

Keep the diff to what the issue asks for. A night that also tidies three
neighbouring things produces a diff the maintainer has to separate by hand,
which costs more than the tidying saved.

## 4. Prove it before pushing

```
scripts/test.sh
scripts/pipelines.sh
```

Both, every time, per CLAUDE.md. `test.sh` picks the suites the change reaches;
`pipelines.sh` says which publishing paths the branch stales, and its verdict
goes in the pull request's `## Data pipelines` section when anything is `STALE`.
A push that fails on formatting costs a full CI round trip to learn what
`ruff format --check` says in one second.

Anything touching ordering, an effect, a rebuild or a mocked promise gets run
three times before it is pushed. Passing once on an idle machine is not
evidence.

## 5. Open it as a draft, then drive it green

Fill the template. Every section earns its answer, and `## Screenshot` gets the
real evidence — a before-and-after table, a test going red on the defect and
green on the fix, or the one line saying there is nothing to show and why. An
unrelated screenshot attached to fill the section is worse than the line.

Then subscribe to the pull request and work it: red CI is work now, merge
conflicts are work now, review-bot findings are bug reports. The PR rules in
the harness prompt govern the rest.

## 6. Take the next one

Re-run `scripts/nightshift.sh` — the issue just claimed now reads as in flight,
so the top of the queue has moved. Keep going until the queue is empty or the
session cannot continue. There is no per-night issue budget; the maintainer set
it that way deliberately.

## 7. Leave one report

One comment, on the issue for the night-shift lane itself (#1463), saying what
was taken, what was opened, what was skipped and why. Not a comment per issue —
the pull requests are the record of what was done; this is the record of what
was *not*, which is the part nobody can reconstruct in the morning.

If the queue was empty, say that in one line. **Never invent work to fill a
night.** An hour of nothing is a correct answer and a manufactured refactor is
not.

## What an unattended session must never do

Six, and none of them has an exception for "CI was green" or "it was plainly
correct":

1. **Merge anything into `main`**, or press any merge button. CLAUDE.md.
2. **Push a tag, publish a release, or promote to production.** CLAUDE.md. A
   `ua` data dispatch following your own merge is fine and expected;
   `data_environment: production` never is.
3. **Take a `client` issue**, or let a change that reaches a hiker-visible
   screen ride along inside a server-side branch. If the work turns out to need
   a client change, stop, say so on the issue, and take the next one.
4. **Add a dependency.** CONTRIBUTING.md has the process and it involves a
   person. An issue that cannot be done without one is an issue to report on,
   not to solve.
5. **Edit CLAUDE.md, CONTRIBUTING.md, BRANCHING.md or RELEASING.md** to make a
   rule fit the night's work. Propose it on the issue instead.
6. **Change a setting outside the repository** — Supabase auth configuration,
   Cloudflare, GitHub repository settings. #875 is the standing example: it is
   a real, live authentication exposure and its fix is a dashboard field, so the
   night shift's whole job on it is to say so precisely and hand it back.

## The asymmetry to keep in mind at 3am

Nobody is going to catch a mistake before morning. That makes the honest-unknown
rule from CLAUDE.md §"Four ways this app can hurt somebody" sharper here, not
softer: where the evidence supports "on the four fixtures this suite builds", do
not write "always"; where a number is picked, tag it `@unvalidated` and say what
would settle it.

The maintainer chose (2026-09-15) to treat the safety paths — trail position,
water distance, staleness, closures, pace and elevation — as ordinary
server-side work in this lane. That decision is theirs and stands. It does not
lower the evidence standard on those paths by one inch; it means the draft pull
request is where the extra care shows up, in a `## How it was checked` section
that says exactly what was verified and what was not.
