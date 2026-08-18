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

**Available now.** It was not when this section was first written, and being
public was never what decided it. GitHub's rule is ownership:

> Pull request merge queues are available in any public repository owned by an
> organization, or in private repositories owned by organizations using GitHub
> Enterprise Cloud.

`OurHike` was public but owned by a personal account — the one combination that
misses, and one no plan upgrade fixes. It now lives in the
[`OurHike`](https://github.com/OurHike) org, so it is a public repository owned
by an organisation and the feature arrived with the transfer, at no cost and as
a side effect. (The transfer is done, and so is the repo-side link sweep that
went with it — [#272](https://github.com/OurHike/OurHike/issues/272).)

#### The half that lives in the repository

Merge queue raises its checks on the `merge_group` event, and a workflow that
does not trigger on that event never reports against a queue entry. That does
not fail the entry — it **hangs** it, until the queue times out and ejects the
pull request. So the trigger has to be in place before the setting is turned on,
not after.

It is in place. These are the checks that report on a queue entry:

| Workflow | Check name |
|---|---|
| `client-tests.yml` | `test` |
| `pipeline-tests.yml` | `pytest` |
| `backend-tests.yml` | `pytest-postgres` |
| `pr-issue-link.yml` | `PR has a linked issue` |
| `settings-manifest.yml` | `Manifest agrees with the workflows` |

`pr-issue-link.yml` is not what it looks like. **It reports green on a queue
entry without checking anything**, and says so in its summary. A queue entry is
not a pull request and cannot be asked whether it closes an issue; each pull
request in the group already answered that on its own runs before it was queued.
It triggers anyway so that requiring it — which is the entire point of that file
— cannot hang the queue.

Everything else stays out, and none of it can be a required check anyway.
`pr-preview.yml` builds a per-pull-request preview and a queue entry is not one;
the spikes and the data builds are `workflow_dispatch`.

##### How the fifth row got there, and why the story is kept

**`Manifest agrees with the workflows` was missing from that table until
[#679](https://github.com/OurHike/OurHike/issues/679).** The evidence that kept
it out is worth keeping even though the conclusion has changed, because what it
produced is precisely the failure this section warns about: a check reporting
*nothing* rather than red. What follows is the state before the split.

At the time, both halves of the settings suite lived in one file,
`settings-check.yml`, which had no `merge_group:` trigger.

What was measured, on the pull request that added these triggers:

| Attempt | `Settings check` on the pull request |
|---|---|
| `merge_group:` added, `configured`'s `if:` widened to exclude it | `action_required`, **zero jobs** |
| same, next commit | `action_required` |
| `if:` restored to its original text, trigger kept | `action_required` |
| trigger removed, comment edits kept | `action_required` |
| **file restored byte-for-byte to `main`** | **success** |

The four other workflows that got the same trigger in the same commit ran
normally throughout, and this is the only `action_required` run in the
repository's last two hundred.

So the cause is **any proposed change to this file at all** — a comment is
enough — and not the trigger, not the `if:`, and not "the pull request edits a
workflow" ([#402](https://github.com/OurHike/OurHike/pull/402) edits `pages.yml`
and is green). The last row is what pins it: zero proposed changes, green.

The mechanism that fits is that this is the only workflow which both runs on
`pull_request` *and* reads the secrets context, through `configured`'s
`toJSON(secrets)`. `action_required` is what GitHub reports when a run needs
approval before it may reach secrets, and a pull request proposing edits to a
secrets-reading workflow is exactly what such a gate is for. Nobody had met it
before because no pull request had ever modified this file —
[#180](https://github.com/OurHike/OurHike/pull/180) created it.

**The gate therefore belongs to the pull request, not to `main`.** Adding the
trigger would not break anything downstream: a pull request that does not touch
this file would run it normally. That was the reason first given for leaving it
out, and it was wrong.

The reason it stayed out is the one that survived:

> A pull request that edits this file, once queued, would raise its
> `merge_group` run of this workflow under the same gate — and a queue entry
> waiting on an approval nobody knows to give is the hang this whole section is
> about, arriving in the one place it costs the most.

That could not be tested without a queue to test it in, so it stayed a risk
rather than a measurement — and the trade was bad: the settings suite is the
smallest of the four, and the failure it would have bought is the expensive one.

**That is the state #679 ended.** The fix removes the risk instead of avoiding
it: the two jobs are now two workflows, so the half that reads secrets and the
half that reads only the checkout no longer share an `on:` block.

| | reads `secrets` | `pull_request` | `merge_group` | schedule |
|---|---|---|---|---|
| `settings-manifest.yml` | no | yes | **yes** | no |
| `settings-configured.yml` | yes | **no** | no | weekly |

`settings-manifest.yml` touches no secrets context anywhere, which is the
property that was actually bought rather than a side effect: with nothing to
gate, there is no approval for a queue entry to wait on, and the fifth row is
safe. `settings-configured.yml` stays out of the table for a different reason
that has not changed — it cannot report on a pull request at all, and a required
check that cannot report on a pull request blocks every pull request.

The check names did not change across the split. Branch protection matches a
check name and not a workflow file, so keeping them verbatim is what let this
move without a window in which a required check reported nothing.

**Queue entries are never path-scoped.** `.github/actions/changed-paths` answers
"run" for `merge_group` exactly as it does for a push, so every suite that runs
on an entry runs whole. That is deliberate. The failure a queue exists to catch
belongs to the *combination* of two changes rather than to either one's diff, and
it is therefore invisible in any single pull request's file list — the scoping
described in [TESTING.md](TESTING.md) is a pull-request optimisation, and it
stops at the queue door.

#### The half that does not, and will not

Switching the queue on is a settings change on `main`, under **Settings → Rules
→ Rulesets** (or classic branch protection). Four decisions:

1. **Require merge queue.** The switch itself.
2. **Require status checks to pass**, naming the checks from the table above —
   and nothing outside it. A required check that cannot report on `merge_group`
   is the hang described above, so the table is the whole menu.

   > The table is five rows and not six on purpose — see the note above.
   > `settings-configured.yml` cannot report on a pull request, so requiring
   > `Settings are configured` blocks every pull request rather than
   > tightening anything.
3. **Leave "Require branches to be up to date before merging" off.** §1 above is
   why, and the queue is what makes it unnecessary rather than merely
   tolerable: the queue builds each entry against `main` plus everything ahead
   of it, which is the guarantee that setting was reaching for, obtained without
   serialising anybody.
4. **Merge method, and how many entries to build and merge at once.** The
   sizing knobs are the tuning; the only one with a wrong answer is a build
   concurrency of 1, which throws away the speculative parallelism that is the
   reason to want a queue at all.

**Nothing in `.github/` can grant itself the power to stop a merge, and this
repository does not try.** That switch is the maintainer's, for the same reason
landing anything on `main` is ([CLAUDE.md](CLAUDE.md)) — and `pr-issue-link.yml`
has recorded the same boundary since it was written.

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

`App.tsx` is 2,080 lines, holds 28 `useState` calls and imports about ninety
modules (measured 2026-08-17 - it was 1,507/25/~60 when this was first
written, which is the direction the argument predicts). It is where every feature is wired in, so every feature branch edits
it, so every pair of feature branches conflicts there. The subjects are
unrelated — a background picker and a download flow — and it makes no
difference.

**Before starting a second branch in the client, ask which of these files it
will touch.** If the answer is `App.tsx` and something in flight already has it
open, either sequence the two or accept the conflict knowingly. Do not discover
it a day later.

The structural fix is to decompose `App.tsx` so features wire themselves in
without a shared edit point. That is
[#327](https://github.com/OurHike/OurHike/issues/327) — a
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
rather than counted as threads. None of them can merge and none needs
watching. (A count used to sit here and drifted from nineteen to twice that
within a week - the script's output is the number, #661.)

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
