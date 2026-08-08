# Releasing OurHike

How a change gets from `main` to a hiker's phone, and what has to be true before it
does.

**Status: designed and largely built, 2026-08-07.** Written before the code, per this
project's usual convention ([DATA_RELEASES.md](pipeline/DATA_RELEASES.md),
[FEATURES.md](FEATURES.md)), and then built in the same change. **§13 is the honest
line between the two** — the workflows exist and run, and the parts that need a
dashboard, an account or a previous release to compare against do not. The remainder
is tracked in issues, per [CONTRIBUTING.md](CONTRIBUTING.md)'s one-home rule.

This is the canonical home for the **code** release process — versions, gates,
environments, notes. [pipeline/DATA_RELEASES.md](pipeline/DATA_RELEASES.md) owns the
**data** release process, and the two are separate trains that meet at exactly one
point (§9). [BRANCHING.md](BRANCHING.md) owns how work reaches `main`; this document
starts where that one stops.

There are no releases yet. There is no `v0.1.0`, no tag of any kind, and
`client/package.json` says `0.0.0`. That is the reason to write this now rather than
later: every rule below is free to adopt today and expensive to adopt once people are
standing on a ridge depending on the last one.

---

## 1. Why this exists: publishing is not releasing

`.github/workflows/pages.yml` deploys to GitHub Pages **on every push to `main`**. So
today, merging a pull request is the act of shipping to production. There is no state
in which a change is built, integrated and reviewable but not yet being served to
whoever opens the app.

That sentence is not new here. [DATA_RELEASES.md](pipeline/DATA_RELEASES.md) already
made the identical argument about *data* — its consequence 3, verbatim:

> **Publishing is the same act as releasing.** There is no state in which new data
> exists but is not yet being served. Every quality gate has to run *before* the
> upload, on local disk, and therefore tests something other than what hikers
> actually receive.

The defect is the same for code, and worse in one respect: a data release is built by
a scheduled job that runs weekly, while `main` moves several times a day. Fifty-one
pull requests merged over the last three hundred commits (BRANCHING.md, measured
2026-08-07) is fifty-one production deployments, each gated by nothing but a code
review and whichever suites the path filter decided to run.

**A "0% error" standard and continuous deployment from `main` are not compatible
claims.** Choosing the standard means choosing a gate, and a gate needs somewhere for
a change to wait.

## 2. The one mechanical change everything else rests on

**`main` stops being production.**

| | before | now |
|---|---|---|
| push to `main` | → GitHub Pages, live to hikers | → **UA**, live to testers |
| annotated tag `v*` | *nothing — no tags existed* | → **Production**, live to hikers |

That is the whole structural change. Everything else in this document is process
arranged around it: naming, notes, review, compatibility and testing are all things
that happen to a candidate *while it sits in UA*, which is a place that does not
currently exist.

It also costs almost nothing to build, because `pages.yml` already publishes to
**paths** on a `gh-pages` branch rather than through `actions/deploy-pages` — it was
written that way so previews could live alongside the site. Splitting one trigger into
two targets is a smaller change than the workflow's own header comment.

## 3. The three environments

| | Dev | UA | Production |
|---|---|---|---|
| **What it is** | a laptop, and a preview per pull request | one persistent deployment of `main` | what hikers install |
| **Deployed by** | `npm run dev`; `pr-preview.yml` | push to `main` | an annotated tag `v*` |
| **Client origin** | `localhost:5173` / `:4173`; `pr-<n>.ourhike-preview.pages.dev` | `ua.ourhike-preview.pages.dev` | `ourhike.github.io` |
| **Backend** | local uvicorn | `ourhike-backend-ua` on Fly, `min_machines_running = 0` | `ourhike-backend` on Fly, `min_machines_running = 1` |
| **Database** | local Postgres (`backend/scripts/local-postgres.sh`) | UA Supabase project | production Supabase project |
| **Map data** | local artifacts | the **candidate** `releases/<id>/` | the **released** `releases/<id>/` |
| **Migrations** | applied and reverted freely | applied here **first**, always | applied only after UA |
| **Who can change it** | anyone | a merged pull request | the maintainer, by tagging |
| **Lifetime of data in it** | disposable | disposable; may be wiped without notice | never disposable |

### 3a. Dev

Exists already and needs nothing. Two halves: a laptop, and the per-pull-request
Cloudflare Pages previews from `pr-preview.yml` (LAUNCH_CHECKLIST.md 3a). Previews
deliberately do not read `API_BASE_URL`, so a preview cannot file test reports into a
moderation queue a club works from — that decision is already recorded in
`.github/expected-settings.yml` and this document does not disturb it.

### 3b. UA

The new one. A **stable Cloudflare Pages alias** in the existing `ourhike-preview`
project, deployed from `main` — the same upload mechanism `pr-preview.yml` already
uses, pointed at a fixed alias instead of a per-pull-request one.

Choosing the existing project over a new one is not laziness, it is the allow-lists.
`ua.ourhike-preview.pages.dev` is already covered by the wildcard entries that R2's
CORS policy and Supabase's redirect list both carry for previews —
`https://*.ourhike-preview.pages.dev` and `https://*.<project>.pages.dev/**`
(LAUNCH_CHECKLIST.md 1.4 and 4.3b). **UA therefore adds no entry to either list.**
That matters because LAUNCH_CHECKLIST.md already names those two lists as "the same
mistake waiting to happen twice", and a third environment is exactly the occasion for
a third instance of it.

What UA is *for*, specifically — the things no amount of CI can answer:

1. **A real browser draws a real map.** Every test in `client/src` mocks
   `maplibre-gl`, because jsdom has no WebGL (TESTING.md item 19). The whole suite can
   pass while the shipped bundle draws a blank sheet of paper, and has.
2. **A real download of real published bytes.** TESTING.md names this gap outright
   ([#94](https://github.com/OurHike/OurHike/issues/94)):
   everything is verified against local files and mocks. `verify_release.py`
   (DATA_RELEASES.md §3) checks the artifacts over HTTPS; UA is where a *browser*
   does, through the same CORS policy and range machinery a phone uses.
3. **A real migration against a real hosted Postgres.** Applied to UA first, always.
   The production run then has a precedent rather than being the first attempt
   ([#95](https://github.com/OurHike/OurHike/issues/95)).
4. **Real storage.** `vi.mock('idb-keyval')` and a full phone have nothing between
   them (TESTING.md, Redundancy). A 1.18 GB archive in real IndexedDB under real
   quota pressure is a UA activity or it is a production incident.
5. **Somewhere to send NYNJTC.** [#109](https://github.com/OurHike/OurHike/issues/109)
   is a soft launch with a real club. Handing volunteers a URL that changes under them
   several times a day is not a soft launch; UA is what makes that issue actionable.

### 3c. Why UA must not share production's origin

**IndexedDB is scoped to an origin, not to a path.** If UA were served from
`/OurHike/ua/` on the same `github.io` host as the app, it would share one origin —
and therefore one IndexedDB — with production. A UA build with a half-finished
storage change could evict, overwrite or misread a hiker's 1.18 GB archive, and the
service-worker scopes being different would not prevent any of it.

A separate path on the same Pages site is the cheaper design and it is the wrong one.
A separate origin is the requirement, and §3b is how to get one for free.

### 3d. What UA costs, honestly

- **Client: nothing.** Cloudflare's free plan does not limit preview deployments, and
  this uploads a directory built in Actions rather than using Cloudflare's builders
  (LAUNCH_CHECKLIST.md 3a).
- **Backend: one more Fly machine**, with `min_machines_running = 0` — a cold start is
  fine for a tester and is exactly what production declines to accept.
- **Database: one more Supabase project.** *Unverified:* whether the free tier allows
  a second active project for this account needs checking in the dashboard before this
  is planned around. If it does not, the fallback is UA using production's Supabase
  **for authentication only** with its own Postgres elsewhere — workable, at the cost
  of UA testers appearing in production's user list.
- **Settings: four or five new names** in `.github/expected-settings.yml`, which is a
  test change as much as a configuration one — the manifest suite fails on a workflow
  reading a setting nothing declares.

The line worth holding: **UA is disposable and production is not.** Anything that
makes UA precious — real hiker accounts, data anyone would miss — has quietly turned
it into a second production, and then there is no free place to break things.

## 4. Versions

`vMAJOR.MINOR.PATCH`, tagged, with the meanings chosen for what they cost a hiker
rather than for what they cost a developer:

- **MAJOR** — a hiker has to do something. Re-download map data, re-install, sign in
  again. A stored-format change that §8 cannot make backwards-compatible.
- **MINOR** — new behaviour, nothing required of anyone.
- **PATCH** — fixes only, no new behaviour, no schema change.

`client/package.json` is the single source, read at build time into the **About this
build** section at the foot of Settings. A version a hiker cannot read back to you is a
version that does not help when they report something.

Single source is enforced rather than asked for: `pages.yml` refuses to deploy a `v*`
tag whose version disagrees with that file, so the two cannot drift. It is the file and
not the tag that is read, because a tag exists only for a released build — and UA, every
pull request preview and a laptop all have to be able to answer the same question.

Two facts travel beside the version, because on their own neither the version nor the
tag can identify most of the builds people actually run:

- **The commit.** `client/package.json` says `0.0.0` and will until the first tag, so
  every build off `main`, every preview and every laptop carries the same version
  number. The commit is the only thing that tells them apart, and the section says so
  rather than letting `0.0.0` read as a version somebody could look up.
- **The build time.** A service worker can serve a bundle long after a newer one
  deployed (`client/vite.config.ts` has the history), so "built three weeks ago" on a
  site that deployed yesterday is what makes a stale install visible from the phone
  instead of from the deploy log.

## 5. Release names — the trail, northbound

Every release is named for the next landmark a northbound thru-hiker meets, starting
at the southern terminus. **v1.0.0 is Springer Mountain.**

| Version | Name | Why it is next |
|---|---|---|
| v1.0.0 | **Springer Mountain** | The southern terminus. Every northbound thru-hike begins here, and so does this one. |
| v1.1.0 | **Blood Mountain** | Georgia's high point on the trail, and its first real climb. |
| v1.2.0 | **Fontana Dam** | The gateway to the Smokies, and the shelter hikers call the Fontana Hilton. |
| v1.3.0 | **Kuwohi** | The highest point on the entire trail — restored to its Cherokee name in 2024. |
| v1.4.0 | **Roan Highlands** | The grassy balds, and the longest stretch of them anywhere on the trail. |
| v1.5.0 | **Grayson Highlands** | Virginia, and the wild ponies. |
| v1.6.0 | **McAfee Knob** | The most photographed view on the trail. |
| v1.7.0 | **Harpers Ferry** | ATC headquarters, and the trail's psychological midpoint. |
| v1.8.0 | **Delaware Water Gap** | Out of Pennsylvania's rocks, into New Jersey. |
| v1.9.0 | **Bear Mountain** | The oldest built section of the trail, and NYNJTC's own ground. |
| … | | |
| — | **Katahdin** | **Reserved.** The northern terminus is not a routine release. |

**The scheme is chosen partly because it removes a decision.** The next name is
already determined by the last one, so nobody debates it at the moment they are
trying to ship, and the name alone tells you which of two releases came first — no
lookup table. Patch releases inherit their minor's name with the number
(`v1.2.1 — Fontana Dam`), because a patch is the same release with a fix, not a new
place.

Landmarks are not scarce. When the list reaches Katahdin, the project has either
grown past one trail or earned the right to start over southbound.

## 6. The people the releases are named beside

Each release names **one figure from the trail's or hiking's history**, in a short
section of the release notes. Where there is a genuine link to the landmark or to what
the release actually did, use it; where there is not, do not invent one.

**One hard rule: every claim is cited, and nothing is embellished.** A release note
that invents trail history is the same class of defect as a water source in the wrong
place — this project's credibility with the clubs is the thing being spent. The
seeds below are **starting points that each need their source added and checked
before they ship**, not verified copy:

| Release | Figure | The link |
|---|---|---|
| Springer Mountain | **Benton MacKaye** | Proposed the trail in a 1921 article, *An Appalachian Trail: A Project in Regional Planning*. The trail named after him also begins at Springer. |
| Harpers Ferry | **Myron Avery** | Did the organising and measuring MacKaye's idea needed to become a footpath; ATC's long-serving chair. |
| — | **Earl Shaffer** | Reported the first thru-hike in 1948, and walked it again fifty years later. |
| — | **Emma "Grandma" Gatewood** | 1955, aged 67, in Keds and a homemade sack — and the reason a great many people believe they could do it too. |
| — | **Mildred Norman** | Hiked the trail in a single season in 1952, as the first leg of a much longer walk. |
| Accessibility work | **Bill Irwin** | Thru-hiked in 1990 without sight, with a guide dog named Orient. |
| Bear Mountain | **the NYNJTC volunteers** | Who built the first section of trail there, and still maintain it. |

Pairing a figure to a release whose subject matches theirs is the version worth
aiming for: an accessibility release named beside Bill Irwin says something a
changelog cannot.

## 7. The release notes

**Two audiences, one generated source.** Hikers want to know what changed about the
map; contributors want to know what changed in the repository. Writing two documents
by hand produces one stale document, which is the failure CONTRIBUTING.md's one-home
rule exists to prevent.

So the notes are **derived, then edited** — never maintained. The mechanism is already
in place and load-bearing: `pr-issue-link.yml` fails any pull request that closes no
issue, so every merged change between two tags carries a linked issue or an explicit
`no-issue` label. That is a machine-readable changelog nobody had to remember to keep.

A generator walks `v(previous)..v(next)` and emits:

1. **What changed for a hiker** — from the issues, grouped by area, in plain language.
   No PR numbers in this half.
2. **What changed in the repository** — every merged pull request, its issue, grouped
   by the `client` / `backend` / `pipeline` / `data` / `ops` / `docs` labels.
3. **Which data release this build pins**, and whether that moved.
4. **What is knowingly not validated** — §8d. This section is never empty, and a
   release whose author believes it is has not looked.
5. **Compatibility** — anything a hiker must do, or the sentence saying nothing.

The fun half — the name, the figure, the paragraph that makes it a release rather
than a diff — is written by a human on top of the generated draft. That is the part
worth a person's time, and the only part.

### 7a. Where they live

`releases/v1.0.0-springer-mountain.md`, committed to the repository. The GitHub
release body is generated from that file, not the other way round.

**Why the file is canonical:** a GitHub release body is editable in place with no
history and no diff, and it lives in one company's database. This project's whole
stance is that a club can be handed the repository and carry on
([OurHikeValues.md](OurHikeValues.md)) — which means the release history has to arrive
in the clone, not need an API call. A tag, a file and a commit are all things `git`
already keeps.

*Naming note:* this `releases/` directory holds **code** releases. The identically
named `releases/` prefix in the R2 bucket holds **data** releases
(pipeline/R2_LAYOUT.md). Two trains, one word; §9 is where they touch.

The GitHub release also carries attached artifacts, for reasons that are all about
being able to answer a question later: the built `client/dist` as a tarball, the
backend's OpenAPI document (§8b's baseline), and the data `manifest.json` for the
release being pinned.

## 8. The gate

What must be true before a tag is pushed. **Hard** means the release does not happen;
**soft** means it may proceed with the gap stated in the notes.

| | Check | | Enforced by |
|---|---|---|---|
| 1 | All four suites green on the release commit, **unscoped** | hard | branch protection: required status checks |
| 2 | `check-build-output.mjs` passes — a build that cannot draw a map does not ship | hard | already inside `npm run build` |
| 3 | Ordering-sensitive client tests run three times, green each time | hard | CLAUDE.md; [#343](https://github.com/OurHike/OurHike/issues/343) is the open instance |
| 4 | Migrations up, down, and `alembic check`, against real Postgres | hard | `backend/tests/test_migrations.py` |
| 5 | Migration applied to UA before production | hard | procedure; §3 |
| 6 | `verify_release.py` battery green against the candidate data over HTTPS | hard | DATA_RELEASES.md §3 |
| 7 | UA smoke: install the PWA, download the smallest archive, go offline, map still draws | hard | procedure, until automated |
| 8 | Backwards-compatibility checks (§8) | hard | tests |
| 9 | `check_freshness.py` — all four upstreams unchanged or knowingly changed | hard | LAUNCH_CHECKLIST.md 7 |
| 10 | Release review complete, findings triaged (§9) | hard | procedure |
| 11 | No open issue labelled `release-blocker` | hard | procedure, checkable by API |
| 12 | Notes written, name assigned, figure cited | hard | `pages.yml` refuses a tag with no `releases/<version>-*.md` |
| 13 | Field-validated thresholds actually field-validated | **soft** | stated in the notes — see §8d |
| 14 | Real-device pass on iOS and Android | **soft** until Phase 3 | stated in the notes |

Two of these need a repository setting that does not exist yet. TESTING.md records
that **none of the suites is a required check** — "a red run doesn't currently block
merging, it's just visible on the PR" — and the scoping was deliberately built so they
*can* be made required without any other change. Gate 1 is that change.

Gate 11 needs two new labels: `release-blocker` (this release does not go out) and
`release-followup` (the next one carries it).

### 8a. What "zero errors" can and cannot mean

The standard being asked for is right about which failures matter and needs restating
to be enforceable, because no process makes a codebase defect-free and a gate that
claims to will be believed.

What a gate can actually guarantee, and what this one is built to:

1. **No release ships with a known defect in the safety-critical set.** Not deferred,
   not accepted, not noted — fixed or the release waits.
2. **No safety-critical behaviour ships on an untested path**, where "tested" means
   TESTING.md's standard: a test proven to fail against the broken implementation, not
   one that merely passes.
3. **Nothing claims to be validated that is not.** §8d.
4. **A failure is detectable in minutes and reversible in one.** This is the part a
   zero-defect ambition usually omits, and the only part that is true regardless of
   how good the gate was. §11.

What no gate can guarantee is that nothing is wrong. The honest version of the
standard is: *nothing known-wrong about position, water, hazard or the map drawing at
all reaches a hiker, and anything that does is gone within the hour.*

### 8b. The safety-critical set

The failures that can mislead somebody in a place where being wrong is expensive.
Nothing here is ever a soft gate, and a finding in this set can never become a
follow-up issue:

- **Position** — where the hiker is, where the trail is, which way they are facing.
  The wrong-way alert's false-positive behaviour above all: `features/HIKER_SAFETY.md`
  and TESTING.md both already say false negatives are acceptable and false positives
  are the failure.
- **Water** — a water source shown that is not there, or omitted where it is.
- **Hazard, warning and closure** — anything that would keep somebody out of a place
  they should not be, including its freshness display.
- **The map drawing at all** — TESTING.md item 19's blank sheet of paper, and the
  off-archive hatch that says "no data here" and needs a `load` event to do it.
- **Held map data surviving an update** — §8c. Forcing a 1.18 GB re-download onto
  somebody at a resupply stop with one bar is a safety failure, not an inconvenience.
- **Attribution and licensing** — legally load-bearing, and one removed line breaks
  it (LAUNCH_CHECKLIST.md 7).

### 8c. Backwards compatibility

Four surfaces, each with a check rather than a promise:

| Surface | What breaks | The check |
|---|---|---|
| **Stored client data** | An update that cannot read the previous release's IndexedDB orphans a downloaded archive or drops queued reports. | A fixture of each of the last N releases' stored shapes, which the current build must read. Written at release time, kept afterwards. |
| **Backend API** | Old clients stay in the field — a PWA can be served from cache, and an app-store build cannot be forced forward at all. A removed field 404s somebody's report. | Diff the OpenAPI document against the previous release's attached copy. Removals and narrowings fail. |
| **Data artifacts** | A key a released client builds stops resolving. | R2_LAYOUT.md already forbids renaming a published key; `verify_release.py` check 19 already re-verifies the currently released folder. Extend to every folder a supported release pins. |
| **Migrations** | A column dropped in the same release that stops writing it breaks the previous release, which is still running during the rollout. | Expand and contract across two releases: add and backfill in one, remove in a later one. Never both. |

The stored-data fixture is the one worth building first, because it is the one whose
failure costs a hiker a gigabyte on a mountain, and the one nothing currently watches
at all.

### 8d. What is not validated goes in the notes

Three things are known-unvalidated today and each is already an issue: the wrong-way
alert's thresholds ([#93](https://github.com/OurHike/OurHike/issues/93) —
wireframe placeholders, and the feature where a false alarm costs most), cumulative
ascent ([#91](https://github.com/OurHike/OurHike/issues/91) — the
check exists and deliberately fails for want of reference figures), and end-to-end
verification against real published artifacts
([#94](https://github.com/OurHike/OurHike/issues/94)).

**A release does not have to resolve them. It has to say so.** A hiker deciding
whether to trust a direction cue is entitled to know the thresholds behind it have
never been tested under tree canopy. LAUNCH_CHECKLIST.md's "Things I know are not
done, stated plainly" is the register this section is written in, and the reason it
works is that it is not optional.

## 9. The release review

**A review of everything since the last tag, as one diff.** Distinct from per-pull-request
review, and not a repetition of it, because the two see different failures.

Per-PR review sees one change against `main`. The release review sees the
*combination* — which is precisely where this repository's real breakages have come
from. TESTING.md's audit is unambiguous about it: the only two failures that ever
broke `main` were both green on their own pull request and red at the merge, "where
the machine was loaded differently". Fifty-one pull requests reviewed one at a time
have been reviewed as fifty-one things, never once as the thing that ships.

How:

1. `/code-review` over `v(previous)..HEAD` at high effort, plus a read of the full
   diff by a human for anything about position, water or hazard.
2. Every finding lands in one of exactly three places: **fixed on the release
   branch**, **an issue labelled `release-followup`** and milestoned to the next
   release, or **`release-blocker`** and the release waits.
3. **A finding in §8b's safety-critical set cannot be a follow-up.** That is the rule
   that gives this step teeth; without it, "create issues for next time" is how a
   known hazard ships with a paper trail.
4. The counts go in the notes — findings, fixed, deferred. A review nobody can audit
   later is a review that happened once.

## 10. Where the two trains meet

A data release and a code release are separate ([DATA_RELEASES.md](pipeline/DATA_RELEASES.md)),
and they touch at exactly one line: `DATA_RELEASE` in `client/src/lib/dataRelease.ts`,
the constant naming which published dataset a build reads.

Under this document that constant's promotion is a merge to `main`, which puts the new
dataset **in UA** — where `verify_release.py` and a real browser can be pointed at it —
and it reaches hikers with the next tag. That is a change to DATA_RELEASES.md §4,
which currently says the merge itself is the release; the amendment is noted there.

The change is an improvement rather than a delay: it gives a data release the one
thing its own verification battery cannot provide, which is a real client fetching it
through a real browser before anyone depends on it.

## 11. What never waits for a release

**Closures, hazard warnings and condition reports are not in a release.** They live in
Postgres behind the backend and are served live — a moderator marking a bridge out
reaches every phone on the next sync, with no build, no tag and no deployment.

This is the fact that makes a deliberate gate acceptable for a safety-adjacent app,
and it is worth stating plainly because the opposite assumption would justify
weakening every rule above. **Urgent safety information was never on the release
path.** What the gate delays is software, and software that is a week late is not the
hazard that software that is wrong is.

### 11a. Hotfixes

A patch release off the current production tag, not off `main` — `main` contains
everything else, and a hotfix that drags six unrelated merges with it is not a
hotfix.

The gate narrows but does not empty: gates 1, 2, 4 and 8 stay hard, §8b still applies
in full, and the notes still get written. What is set aside is the release review's
full-diff pass over unrelated work, and the soft gates. A hotfix still gets its name —
the current one, with a patch number.

### 11b. Rollback

**Re-deploy the previous tag.** That is the whole procedure, and it is the reason
production deploys from a tag rather than from a branch: the previous good state is a
ref that still exists rather than a revert commit somebody has to write correctly
under pressure.

Three things have to be true for it to actually work, and each is a build task rather
than a hope:

- **The service worker must be able to move backwards.** An update path that only
  accepts a newer version will refuse the rollback and keep serving the broken build
  from cache. Compare versions, do not assume monotonicity.
- **The data release must be rollable too.** It is: folders under `releases/` are
  written once and never overwritten, and retention keeps a superseded release 90 days
  past being superseded with a floor of three (DATA_RELEASES.md, Retention). Rolling
  back the tag rolls back the pinned constant with it.
- **A migration must not have burned the bridge.** §8c's expand-and-contract rule is
  what keeps the previous release able to run against the current schema. It is a
  rollback rule as much as a compatibility one.

## 12. Who may cut a release

**The maintainer, and nobody else.** An agent working in this repository does not push
a tag, does not publish a GitHub release, and does not promote anything to production —
the same rule and the same reasoning as CLAUDE.md's prohibition on merging into
`main`, which this extends rather than duplicates.

An agent may do everything up to that line: prepare the branch, generate the notes,
run the battery, open the pull request, and create the GitHub release **as a draft**.
Publishing the draft is a human action.

The mechanism, so that it does not rest only on being followed: a GitHub **environment**
named `production` with a required reviewer. `publish-vector-data.yml` already runs
under `environment: production`, so the concept is in place; what it lacks is the
protection rule. An environment gate is checked by GitHub rather than by discipline,
which is the difference between this rule and the one it extends.

## 13. Status

**Built:**

| | |
|---|---|
| `pages.yml` | Deploys production from a `v*` tag, not from `main`. Refuses a tag with no notes file (gate 12) or one that disagrees with `client/package.json` (§4), and drafts the GitHub release with the app exactly as deployed, the OpenAPI document and the data manifest attached |
| `client/src/lib/buildInfo.ts` | The version, commit and build time, inlined at build time and shown at the foot of Settings |
| `ua.yml` | Deploys `main` to UA on its own Cloudflare origin, with no path to the production backend |
| `release-notes.yml` | Generates a notes draft and opens it as a pull request, labelled so it can pass CI |
| `.github/scripts/release_notes.py` | The generator. Pure half tested in `.github/tests/test_release_notes.py`; the git and API half is a thin seam |
| `releases/` | Where the notes live, canonically |
| `.github/expected-settings.yml` | The four `UA_*` settings declared, so the manifest suite can see them |

**Not built, and each one is why the process is not yet enforced rather than merely
followed:**

- **The UA infrastructure itself.** The workflow is written and degrades politely;
  the Cloudflare alias will appear on the first push to `main` after this lands,
  but the UA Supabase project and the UA Fly app are account work
  ([#371](https://github.com/OurHike/OurHike/issues/371)).
  Until `UA_API_BASE_URL` exists, UA queues reports in the outbox — which is a
  supported state, not a broken one.
- **The repository settings** — required status checks, the `production`
  environment's reviewer, and the two labels
  ([#375](https://github.com/OurHike/OurHike/issues/375)).
  These are the difference between §8's table being a mechanism and being a
  document, and none of them can be set from a checkout.
- **The compatibility checks** ([#374](https://github.com/OurHike/OurHike/issues/374)).
  Deliberately last: the OpenAPI diff and the stored-data fixtures both compare
  against a *previous release*, and there is no previous release to compare to
  until `v1.0.0` exists. Building them now would mean shipping code nothing can
  exercise — which TESTING.md is explicit about being worse than not having it.
  The baseline they will read is already being attached by the release job.
- **The version on the wire.** Settings now shows the version, the commit and the
  build time, and offers to copy all three (§4, `client/src/screens/AboutBuild.tsx`),
  so a hiker can read back which build they have. What a report still does not carry
  is that version *automatically* — somebody has to quote it. Nothing on the backend
  records a client version today, so sending a header would be a value with no
  reader; that is the half left open.

The build is tracked in issues rather than enumerated here — CONTRIBUTING.md's one
home per item, and the reason ROADMAP.md's checklists are gone.

## 14. Open questions

1. **Does the free Supabase tier allow this account a second active project?** §3d.
   The UA design assumes yes and has a stated fallback; the answer changes which.
2. **Does UA get its own R2 bucket, or only its own prefix?** Designed as prefix-only —
   UA points at a candidate folder in the same bucket, which is what makes UA a real
   verification of the bytes production will serve. A separate bucket would verify a
   copy.
3. **How many releases back does the backend support?** §8c needs a number. "The last
   two" is the cheapest answer that is not "forever", but app-store builds
   (Phase 3) may force a longer window, and that is the same argument DATA_RELEASES.md
   makes about retention.
4. **Does the client tell a hiker their map data is old?** DATA_RELEASES.md leaves the
   record built and the signal unbuilt. A release that moves `DATA_RELEASE` currently
   has no way to say so to a phone that already downloaded.
5. **Is a release cadence wanted, or is it release-when-ready?** Nothing above assumes
   either. A cadence makes `release-followup` mean something specific; ready-when-ready
   makes the gate the only clock.
