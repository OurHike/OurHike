# Branching and pull requests

How to keep a lot of work in flight at once without spending the day merging
`main` into things.

This is the canonical home for the branching strategy.
[CONTRIBUTING.md](CONTRIBUTING.md) and [CLAUDE.md](CLAUDE.md) point here rather
than restating it — one home per item.

## What the repository actually spends its time on

Measured over the last 300 commits, on 2026-08-07:

| | |
|---|---|
| Pull requests merged | 51 |
| `main`-into-branch merge commits | 73 |
| …that resolved a real conflict | 27 |
| **…that resolved nothing at all** | **46** |
| Merged branches never deleted | 67 |

A `main`-into-branch merge commit whose combined diff is empty touched nothing
that both parents had not already agreed on. Git had no question to ask, so
nobody answered one. Forty-six of those, each costing a full CI round trip and
a re-review of a diff that did not change.

That is the problem. It is not conflict resolution — that part is real work and
there is less of it than it feels like. It is catch-up merging performed on
branches that had nothing to catch up on.

## 1. Do not merge `main` into a branch to keep it current

**Being behind `main` is not a defect.** GitHub merges a pull request against
`main` as it stands the moment the button is pressed, not against whatever copy
of `main` the branch has absorbed. A branch eleven commits behind and a branch
freshly caught up produce the identical merge commit. The catch-up run bought
nothing but the CI minutes it spent.

Merge `main` in for exactly three reasons:

1. **It genuinely conflicts.** `scripts/threads.sh` says `CONFLICTS`.
2. **The branch cannot pass its own tests without something on `main`** — a
   fixture, a fixed flake, a dependency bump. The branch is broken now, and
   merging is the fix.
3. **The maintainer asks**, because the change is one whose interaction with
   recent work they want proven before it lands rather than after.

Anything else — "it has been a few days", "there were some merges", tidiness —
is not a reason. Leave it.

### Why this is safe here specifically

Because post-merge validation already exists and is already load-bearing. Every
suite runs on `push` to `main` as well as on pull requests, against the real
merge commit. That trigger was kept deliberately, and it is what caught the
flaky staleness boundary test in #32 — green on the pull request, red on the
merge.

So the semantic conflict that a catch-up merge is supposed to expose (two
branches that merge cleanly but are wrong together) gets caught on `main`
either way. Pre-merging every branch to look for it means paying for that check
once per branch instead of once per landing, and still not catching it any
earlier for the branch that lands second.

### This rule is only followable if the setting allows it

**Settings → Rules → "Require branches to be up to date before merging" must be
off for any of the above to be possible.** With it on, GitHub disables the
merge button until the branch is current, and the rule in this section becomes
something nobody can follow — the catch-up merge stops being a habit and
becomes policy.

It is also the setting that specifically punishes concurrent work, because it
serialises it. With five branches ready:

| | up-to-date required | off |
|---|---|---|
| landing five ready branches | merge one → the other four are now behind → each updates → each re-runs CI → repeat | merge all five |

Every merge invalidates every other open pull request. N ready branches cost N
sequential full CI rounds, and the last one in line pays the most.

Measured here: during a window with the setting off, pull requests merged 3, 7,
9, 16 and 23 commits behind `main`, and `main` stayed green.

### What the setting was protecting against

Two branches that are each green alone and broken together — a semantic
conflict, which merges cleanly and no `merge-tree` check can see. Turning the
setting off gives that guarantee up. Two things soften it: the push-to-`main`
runs catch it immediately after landing rather than before, and §2 keeps the
branches that could plausibly interact from being in flight together in the
first place.

### The option that gives you both: merge queue

A merge queue keeps the guarantee without anyone merging `main` into anything.
GitHub builds each queued pull request against `main` plus everything ahead of
it in the queue, in its own temporary branch, and merges only if the required
checks pass there. The pull request branch is never modified, and entries are
tested speculatively in parallel rather than one at a time — which is the
property this whole document is trying to buy.

**Not available to this repository, and being public is not what decides it.**
GitHub's rule is ownership:

> Pull request merge queues are available in any public repository owned by an
> organization, or in private repositories owned by organizations using GitHub
> Enterprise Cloud.

`OurHike` is public but owned by a personal account, which is the one
combination that misses. No plan upgrade fixes it — a personal account cannot
buy the feature at any tier.

What fixes it is already planned:
[#272](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/272) moves
this repository into the `OurHike` org, and
[#274](https://github.com/jaimito-asuntos-gringuenos/OurHike/pull/274) is
already waiting on that transfer. A public repository owned by an organisation
gets merge queue at no cost, so the transfer unlocks it as a side effect rather
than as something to buy.

**And even then it cannot be switched on as-is.** Merge queue runs checks on
the `merge_group` event, and no workflow in `.github/workflows/` currently
triggers on it:

```yaml
on:
  pull_request:
    branches: [main]
  merge_group:        # ← required, currently missing everywhere
```

Without that, a required check never reports against a queue entry and every
merge hangs until the queue times it out. The trigger has to land before the
setting is turned on, not after.

### Answering "does it conflict?" without merging

```
scripts/threads.sh
```

`git merge-tree --write-tree` performs the merge against the object store and
throws the result away. No checkout, no working tree, no index, no branch
moved. It is exact — the same merge machinery, the same answer — and it takes
about a millisecond per branch.

## 2. Slice by conflict surface, not by subject

Two branches collide because they edit the same lines, not because they are
about related things. Of the 27 real conflicts, **12 were `client/src/App.tsx`**
— more than the next six files combined.

| File | Conflicts |
|---|---|
| `client/src/App.tsx` | 12 |
| `WIREFRAMES.md` | 7 |
| `LAUNCH_CHECKLIST.md` | 4 |
| `client/src/chrome/MapScreen.tsx` | 3 |
| `client/src/map/MapView.tsx` | 3 |
| `client/src/screens/Onboarding.tsx` | 3 |

`App.tsx` is 1,507 lines, holds 25 `useState` calls and imports about sixty
modules. It is where every feature is wired in, so every feature branch edits
it, so every pair of feature branches conflicts there. The subjects are
unrelated — a background picker and a download flow — and it makes no
difference.

**Before starting a second branch in the client, ask which of these files it
will touch.** If the answer is `App.tsx` and something in flight already has it
open, either sequence the two or accept the conflict knowingly. Do not discover
it a day later.

The structural fix is to decompose `App.tsx` so features wire themselves in
without a shared edit point. That is
[#327](https://github.com/jaimito-asuntos-gringuenos/OurHike/issues/327) — a
refactor with its own risk, not something to fold into whatever else is in
flight.

## 3. One branch per issue, unless the work is stacked

Default: a new issue gets a new branch off `main`, its own pull request, and is
closed by its own merge. A session that finds three things leaves three pull
requests.

The exception is work that sits **on top of** an open branch — it touches code
that branch is actively rewriting, or only makes sense with those changes
present. Splitting that does not produce two clean reviews; it produces two
pull requests that conflict with each other and a merge order somebody has to
hold in their head. Keep it where it depends, and say in the pull request that
it closes two issues and why.

**The test is dependency, not subject or size.** #216 had nothing to do with
#210 as a problem — one was a blank background, the other was how you reach the
download — but its fix landed in `App.tsx`, `MapScreen.tsx` and
`BackgroundPicker.tsx` while #210 was rewriting all three. It stayed, and the
pull request said so.

Switching branches is nearly free. What costs is re-verifying and resolving
conflicts, so the number worth minimising is how many times the full check
suite has to run — not how many branches exist.

## 4. Land the hot-file branches first

When several branches are ready at once, order matters, and only for the files
in the table above. Land the one touching `App.tsx` first. Every other branch
that touches it then has one conflict to resolve against a settled `main`,
rather than each of them conflicting with each of the others in whatever order
they happen to land.

Where nothing shares a hot file, order does not matter — land them in any
order, in parallel, without looking.

## 5. Delete branches when they merge

Sixty-seven merged branches are still on the remote. They are indistinguishable
at a glance from the four that are live, which is most of why keeping track of
what is in flight feels hard.

Turn on **Settings → General → Automatically delete head branches** once, and
this stops being a task. Until then, `scripts/threads.sh --stale` lists what is
safe to remove.

## 6. The ledger

```
scripts/threads.sh --fetch      # what is in flight and what each needs
scripts/threads.sh --stale      # ...plus what is safe to delete
```

For each live branch it reports how far ahead and behind it is, when it last
moved, **which suites CI will actually run for it** (using the same path gates
as `.github/actions/changed-paths`, so it agrees with CI by construction), and
whether it truly conflicts.

Branches sharing no history with `main` are listed separately as leftovers
rather than counted as threads. There are nineteen; none of them can merge and
none needs watching.

## Running the checks

Unchanged, and worth restating because it is the other half of why a needless
merge is expensive — [CONTRIBUTING.md](CONTRIBUTING.md) has the full commands:

```
cd client        && npm run typecheck && npm run lint && npm run format:check && npm test && npm run build
cd pipeline      && python -m ruff check . && python -m ruff format --check . && python -m pytest
cd backend       && python -m ruff check . && python -m ruff format --check . && python -m pytest
cd .github/tests && python -m ruff check . && python -m ruff format --check . && python -m pytest
```

You only need the suites your branch touches; `scripts/threads.sh` names them.
A push that fails on formatting spends a full CI round trip learning something
`ruff format --check` would have said in one second.

## What this does not change

**Never merge into `main`.** Landing work is the maintainer's decision. That
rule lives in [CLAUDE.md](CLAUDE.md) and nothing here softens it — the point of
this document is to reduce merges *into branches*, which is the opposite
direction and the only one that was ever fine.
