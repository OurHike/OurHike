# OurHike — Data Environments (Feature Design Draft v1)

Companion to [../RELEASING.md](../RELEASING.md), [../pipeline/R2_LAYOUT.md](../pipeline/R2_LAYOUT.md)
and [../pipeline/DATA_RELEASES.md](../pipeline/DATA_RELEASES.md). RELEASING.md owns **the three
environments a build moves through**; R2_LAYOUT.md owns **where an object goes in the bucket and
what it may be called**; DATA_RELEASES.md owns **when data is released and what is kept**. This
document owns the question none of them answers: **which environment's data is which, and what
stops one from writing another's.**

**Scope: v2, fifth feature** (2026-08-13), and the least visible of them — no hiker will ever see
it, which is the point. [HIKE_PLANNING.md](HIKE_PLANNING.md),
[VOLUNTEERING.md](VOLUNTEERING.md), [FIELD_NOTES.md](FIELD_NOTES.md) and
[PHOTO_DOWNLOADS.md](PHOTO_DOWNLOADS.md) are four features that all write data a hiker reads, and
[EVENTING.md](EVENTING.md) is how we find out whether any of them worked. Every one of them wants
somewhere to be wrong first. Right now there is nowhere: UA and production read one dataset and
one publisher writes it.

**Status: designed and built, 2026-08-13** — written before the code per this project's usual
convention and then built in the same change, with §8 the honest line between the two.

---

## 1. The defect, in one sentence

**Every byte OurHike publishes is written to a key that is live to hikers, by a job that has no
way to say it meant otherwise.**

`publish.py` writes `trails.geojson` at the bucket root. So does a dry run somebody re-ran with
the box ticked. So would a UA build, if UA had a way to publish at all — which is precisely why
it does not. RELEASING.md §3's table promises UA "the **candidate** `releases/<id>/`" and
production "the **released** `releases/<id>/`", and that layout does not exist yet
([DATA_RELEASES.md](../pipeline/DATA_RELEASES.md) §2, unbuilt). What exists is flat mutable keys
and one place to put them.

The consequence is not theoretical, and it is not really about UA. It is that **there is no
rehearsal**. `.github/workflows/publish-conditions.yml` bakes verified closures out of
production's database daily; the only way to test a change to that path is to run it against
production's database and publish the result over production's closures. DATA_RELEASES.md's
consequence 1 — a publish overwriting a key mid-download, splicing old bytes onto new — is a
failure mode the client now detects and cannot prevent, and the thing that would trigger it is
exactly a second publisher writing the same key.

So the question in RELEASING.md §14.2 — *"Does UA get its own R2 bucket, or only its own
prefix?"* — turns out to have been asking the wrong half. Prefix-only was the right answer and
it was never implemented, because there was no such thing as a prefix that belonged to an
environment.

## 2. Every data source, and whether sharing it is safe

The review this design exists to record. **Mutable is the whole discriminator**: an object that
is written once can be read by any number of environments without harm, and an object that is
rewritten in place cannot be shared by two writers at all.

| source | where it lives | mutable | shared today | verdict |
|---|---|---|---|---|
| Trail vectors — `trails.geojson`, `trails.fgb` | bucket root | **yes** — `PutObject` over a live key | yes | **separate.** A UA publish overwrites what a hiker is downloading |
| POIs — `poi_*.{geojson,fgb}` | bucket root | **yes** | yes | **separate**, same reason |
| Spurs, elevation — `spurs.json`, `elevation_profile.json` | bucket root | **yes** | yes | **separate**, same reason |
| Raster and package archives — `background*.pmtiles`, `at_basemap_package*.pmtiles`, `dem.pmtiles`, `quad_sheet_z14.pmtiles` | bucket root | **yes** | yes | **separate.** The 1.18 GB tier is the one a resumed download splices |
| `latest.json` | bucket root | **yes** — the one mutable pointer by design | yes | **separate.** Two writers on one pointer is the fastest corruption in the bucket |
| `build_state.json` | bucket root | **yes** | yes | **separate.** It describes the upstreams *this environment's* bytes were built from; shared, it describes whichever ran last |
| Published conditions — `conditions/{closures,reports}.json` | `conditions/` | **yes** — rewritten daily, by design | yes | **separate, and most urgently.** Baked from a *database*, so sharing the artifact means sharing which database is authoritative for a safety warning |
| ATC trail updates — `conditions/atc_updates.json` | `conditions/` | **yes** | yes | **separate object, identical content.** Baked from a reviewed file in git; there is no database it could differ by, so both environments publish the same bytes into their own tree |
| POI photos — `photos/<digest>.jpg` | `photos/` | **yes** — objects are added *and deleted* | yes | **separate.** Content-addressing makes the bytes safe; the *deletion* is what is not. A withdrawal rehearsed in UA would take the photograph out of production |
| Photo originals — `originals/<digest>.jpg` | `originals/` | **yes**, same rule | yes | **separate**, same reason |
| Build intermediates | `_internal/` | **yes** — rewritten per build | yes | **separate.** Two builds diffing against one cell state is a raster leg that reuses the other environment's tiles |
| Release folders — `releases/<id>/…` | `releases/` | **no** — written once, never overwritten | n/a, unbuilt | **shared, deliberately.** §5 |
| Postgres — accounts, reports, closures, comments | Supabase | yes | **yes today** | already designed separate: `UA_SUPABASE_URL` / `UA_MIGRATION_DATABASE_URL`, unbuilt account work ([#371](https://github.com/OurHike/OurHike/issues/371)) |
| The backend API | the backend host | yes | **no** — `UA_API_BASE_URL` has deliberately no fallback | already separate, and the precedent this follows |
| Upstream ArcGIS / opentrail / USGS | somebody else's servers | read-only to us | yes | **shared, and nothing to decide.** We fetch; we never write |
| IndexedDB on the phone | the phone | yes | **no** — UA has its own origin | already separate (RELEASING.md §3c) |

Two things fall out of that table worth naming, because both were surprises.

**The backend already got this right and the bucket never did.** `UA_API_BASE_URL` has no
fallback to `API_BASE_URL`, on the stated grounds that a UA build able to send would file test
reports into a queue a club works from. That is the same argument, one layer down, and the bucket
has been the exception to it since the first publish.

**The one source nobody would have listed is the one most worth splitting.** Photos are
content-addressed, so a shared `photos/` prefix can never serve wrong bytes — and that is why it
reads as safe. It is not: `photos/` is the only hiker-facing prefix objects are *deleted* from,
because a withdrawal is a promise made to whoever shared the photograph
([POI_PHOTOS.md](POI_PHOTOS.md)). Rehearsing that promise is exactly the thing UA is for.

## 3. The mechanism: an environment is a prefix

```
                              trails.geojson          production
environments/ua/              trails.geojson          UA
environments/dev/             trails.geojson          a laptop, or a field test
```

One function computes it ([`pipeline/lib/data_env.py`](../pipeline/lib/data_env.py)), and one
module calls it — `publish.py`, which is the only thing in this repository that writes to the
bucket. Everything else that touches R2 reads. That is what turns a rule into a mechanism: a run
publishing to UA is not *expected* to leave production's keys alone, it is *unable* to name
them.

Three properties, each of which is a test:

1. **The environment is declared, never inferred.** `OURHIKE_DATA_ENV` must name one of
   RELEASING.md §3's three, and **unset is a refusal rather than production**. There is no safe
   default here: the only value a default could take is the one that overwrites what hikers have
   already downloaded. Same shape as `R2_WRITE_ENABLED`, which already refuses to publish until
   somebody types it out.
2. **The set is closed.** `OURHIKE_DATA_ENV=uat` is a typo, and an open set would answer it by
   publishing a complete, correct dataset into a tree nothing reads, nothing prunes and nobody
   is looking at. `r2_keys.TOP_LEVEL_PREFIXES` already makes this argument about prefixes.
3. **A key legal in one environment is legal in all of them.** `validate_key` strips the
   environment before applying any layout rule, so depth is counted from the environment's own
   root. Counting the prefix would put UA's tree two levels shallower than production's under
   the four-segment limit — which would make `environments/ua/releases/<id>/trails.geojson`
   illegal while production's identical key was fine, and a dataset that cannot be staged where
   it is meant to be verified.

**Readers may leave it unset where writers may not.** The check scripts take `--env` and
otherwise use the base URL exactly as given. The asymmetry is deliberate: a check pointed at the
wrong environment is a wasted run, and a write to the wrong environment is a hiker's map
overwritten.

## 4. The client side is already built, and that is not luck

`client/src/lib/config.ts` builds every URL it fetches as `` `${DATA_BASE_URL}/${key}` ``, and
every read in the app goes through it — `trailData.ts`, `dataManifest.ts`, `packages.ts`,
`publishedConditions.ts`, the photo URL on a POI card. So **an environment is a longer base URL,
and the client needs no change at all**:

```
UA_DATA_BASE_URL = <DATA_BASE_URL>/environments/ua
```

`ua.yml` computes that value itself now, by default - the formula above is derivable entirely
from `DATA_BASE_URL` plus a fixed suffix, so nothing has to type it into a variable for the
ordinary case. `UA_DATA_BASE_URL` still exists as an explicit override for whoever needs UA to
read something other than its own environment.

The manifest's *contents* stay unscoped, and that is load-bearing rather than incidental. An
artifact is `trails.geojson` in every environment; which bytes that names is decided by the base
URL the build was given. So a `latest.json` can be read, diffed or promoted between environments
without rewriting a single entry, and `dataManifest.ts` never learns that environments exist.

**There is no fallback to production's base.** A UA build pointed at a prefix nothing has
published to yet 404s on every artifact rather than quietly reading production's - a UA that reads
production's bytes by default is a UA that looks like it is testing a publish and is not, and a
404 says plainly that nothing has shipped to UA yet where a silent fallback would not. The cost is
real only before the first UA publish; after that, `environments/ua/` always has something in it.

## 5. What stays shared, and why that is not a compromise

**One bucket.** RELEASING.md §14.2 asked bucket-or-prefix and answered prefix, on the grounds
that UA verifying a copy verifies the wrong thing. That answer stands and this design is what
finally implements it. One bucket means UA is served through the same CORS policy, the same
`r2.dev` host, the same range machinery and the same `If-Range` behaviour a phone gets — which is
what that argument was actually protecting. [#506](https://github.com/OurHike/OurHike/issues/506)
is a live example: the bucket permits `If-Range` and does not honour it. A second bucket is a
second policy that could differ in exactly that way, and the difference would be invisible until
a hiker's resume spliced.

**Release folders, once they exist.** `releases/<id>/` is written once and never overwritten
(DATA_RELEASES.md), and an immutable object cannot be corrupted by another environment reading
it. So the rule when that layout lands is:

> **An environment resolves a release; it does not copy one.** The bytes live in one place and
> `environments/<env>/latest.json` says which release that environment is on.

That is what keeps §14.2's property intact where it actually matters — the object UA verified is
the object production serves, bit for bit, not a copy that was verified separately — while UA and
production remain free to be on different releases, which is the separation a tester experiences.
Until `releases/` exists, every published key is mutable and every one of them is scoped.

**Upstream sources.** Twelve ATC ArcGIS layers, opentrail.org, USGS quads and 3DEP, ATC's Trail
Updates page. We read them and never write them, so there is nothing to separate — every
environment fetches the same upstream, as it should, because an environment that fetched
*different* upstream data would be testing a different trail.

## 6. What it costs

- **Storage.** One extra copy of whatever a non-production environment publishes. A full UA
  dataset is on the order of 2 GB including the archives, plus ~75 MB of photos — call it
  $0.03/month at R2's $0.015/GB-month. The photo corpus is the only part that is a straight
  duplicate of identical bytes, and duplicating it is the price of being able to rehearse a
  withdrawal.
- **A first UA publish pays for everything.** The photo upload check is a HEAD per photo against
  the environment's own prefix, so UA's first run uploads the whole corpus and every later one
  uploads nothing. That is the same shape the production bucket already went through once.
- **Two conditions runs a day instead of one.** Both are two SELECTs and a handful of small
  objects; the UA leg publishes nothing at all until UA has a database.
- **Nothing on the client.** No bundle change, no code change, one variable.

## 7. What this does not fix

**The credential is still one bucket-wide token.** `R2_ACCESS_KEY_ID` can write every key in the
bucket, so what stops a UA run reaching production's keys is `publish.py`'s scoping and not R2's
permissions. That is a real limit and worth stating plainly: this design makes the *wrong write*
impossible by construction in the code, not impossible by construction in the account. A token
scoped to `environments/ua/*` would close it, and R2 supports prefix-scoped tokens.

**Publishing to UA still waits on production's reviewer.** `publish-vector-data.yml` runs under
`environment: production` so that the R2 credentials sit behind a gate. Once
[#375](https://github.com/OurHike/OurHike/issues/375) adds that environment's required reviewer,
a UA data publish will need the same approval a production one does — which makes UA slower to
break things in than production is, and UA exists to be the fast place. Splitting the job's
GitHub environment by its data environment is the fix and is deliberately not in this change:
it needs a `ua` GitHub environment to exist first, which is account work.

Both are follow-ups rather than gaps in the design, and both are cheaper to do once there is a
UA dataset to point them at.

## 8. Status

**Built:**

| | |
|---|---|
| [`pipeline/lib/data_env.py`](../pipeline/lib/data_env.py) | The environment: the closed set, the prefix, the scoped key, the base URL, and the refusal to guess |
| [`pipeline/lib/r2_keys.py`](../pipeline/lib/r2_keys.py) | `environments/<name>/` stripped before the layout rules, so a key is legal in every environment or in none |
| [`pipeline/publish.py`](../pipeline/publish.py) | Every artifact, sidecar, photo and manifest key scoped on the way out; refuses to run with no environment set; names the environment in its log |
| `check_deployment.py`, `smoke_published.py`, `verify_release.py` | `--env`, so the monitors can look at an environment instead of a hand-spliced URL |
| `publish-vector-data.yml`, `build-raster.yml`, `build-basemap.yml`, `build-dem.yml` | A `data_environment` choice, defaulting to **ua** — the same "UA first, always" `migrate.yml` applies to schema changes |
| `publish-conditions.yml` | One run per environment, each reading its own database and writing its own prefix |
| `ua.yml` | Computes `environments/ua` from `DATA_BASE_URL` by default; `UA_DATA_BASE_URL` is an explicit override, not the primary path |
| `.github/expected-settings.yml` | `UA_CONDITIONS_DATABASE_URL` declared; `UA_DATA_BASE_URL`'s entry corrected to describe the prefix that now exists |

**Not built, each for a reason rather than an omission:**

- **The first UA publish.** One action, and it cannot be done from a checkout: somebody dispatches
  `publish-vector-data.yml` with `data_environment: ua`. `ua.yml` computes `environments/ua` on its
  own, so nothing further is needed once that publish lands - and until it does, UA 404s on every
  artifact rather than quietly reading production's.
- **UA's conditions database** ([#371](https://github.com/OurHike/OurHike/issues/371)). The UA
  Supabase project does not exist, so the UA conditions leg warns and publishes no closures. Its
  ATC trail-updates artifact publishes either way, which makes UA's `conditions/` prefix real
  rather than empty from the first run.
- **The prefix-scoped R2 token**, and **the UA GitHub environment**. §7.
- **A prune rule for `environments/`.** DATA_RELEASES.md's retention design is written per
  prefix and this adds one. Nothing needs pruning until there are several UA datasets, and
  Phase 7 is where that job gets written — but the rule it will need is stated now so it is not
  rediscovered: **a non-production environment's data is disposable and is pruned on its own
  clock, and no exemption in `releases/pinned.json` applies to it**, because no app-store build
  has ever pointed at one.

## 9. Open questions

1. **Does `dev` publish at all, in practice?** It is declared because a field test wants real
   bytes over a real network, which is the one thing a laptop's static server cannot be. If a
   year passes with nothing ever publishing to it, the honest move is to delete it rather than
   keep a third tree nobody has looked in.
2. **Should UA's data be seeded from production's on its first run, rather than built?** A
   server-side copy of production's current artifacts would give UA a full dataset in seconds and
   for nothing, which is attractive and is also the thing §5 declines for release folders. The
   distinction is probably that seeding a *starting point* is not the same as verifying a
   *candidate* — but it is not obviously right, and nothing depends on it yet.
3. **Does the freshness check need to run per environment?** `check-upstream-freshness.yml` reads
   `build_state.json` over the public URL and asks whether upstreams have moved since. Against
   UA's state that answers a question about UA's build, which is not obviously worth a daily
   issue update. Left as production-only until somebody wants it.
