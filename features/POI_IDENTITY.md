# OurHike — POI Identity (Feature Design Draft v1)

Companion to [../pipeline/DATA_RELEASES.md](../pipeline/DATA_RELEASES.md) (the release machinery
this rides), [FIELD_NOTES.md](FIELD_NOTES.md) (whose §7 names the orphaning this design
removes), [POI_PHOTOS.md](POI_PHOTOS.md), [HIKE_PLANNING.md](HIKE_PLANNING.md),
[POI_SITES.md](POI_SITES.md) and [`pipeline/lib/poi_schema.py`](../pipeline/lib/poi_schema.py)
(the id contract as it stands). **Status: designed 2026-08-13; build-order steps 1 and 2 built
2026-08-18 (#671, #672)** — the ledger is seeded (3,004 rows, ids exactly as published, verified
a byte-for-byte no-op on the real snapshot; 2,215 rows carry an inventory fingerprint), tiers 1
and 2 run as `pipeline/reconcile_poi_identity.py` (key-carry with the teleport guard; evidence
matching over distance, normalised name, fingerprint and along-trail position, accepted only on
threshold + margin-over-runner-up on both sides + the hard ceiling + mutual-best — constants
`@unvalidated` pending #675), overrides live hand-owned in
`reference/poi_identity_overrides.json`, `--check` gates publish-vector-data.yml,
`verify_release.py` check 21 holds every published id to a live, agreeing ledger row, and
`export_poi.py` publishes under ledger ids with `reference/shelter_capacity.json` re-keyed onto
them. **Step 3's pipeline half built 2026-08-19 (#673)** — `retired_poi.geojson` published from
the ledger's retired rows, `superseded_by` written from tier 2's merge signature or a
`merged_into` override, `lib/poi_identity.resolve` as the one implementation, and check 21
extended to hold the tombstones to the ledger both ways; **its client half built
2026-08-22 (#831)** — `client/src/lib/poiIdentity.ts` resolving against the published
tombstones, `chrome/RemovedPoiCard.tsx` as §4's fourth existence state, `source` published on
every tombstone so the card's sentence is derived rather than hard-coded, and the two resolvers
held together by `pipeline/tests/fixtures/poi_resolver_cases.json`. **The backend half remains
blocked** on plumbing that does not exist, and #831 measured why: nothing under `backend/app/`
opens a file or a socket for data, `backend/Dockerfile` does not copy `pipeline/reference/`,
`requirements.in` ships no HTTP client, `main.py` has no lifespan hook, and `config.py` argues
at length against holding the published bucket's settings. Choosing between a table plus a
`load_assignments.py`-shaped loader and a boot-time fetch is a maintainer's call, not a
session's. Steps 4–5 remain
(**#674 — Closures anchor on miles alone, and a re-measure moves every mile**, **#675 — Measure
the first real ATC refresh: GlobalID survival, tier-2 volume, and where the thresholds land**).
The umbrella is **#666 — A POI's identity is its upstream key, so one ATC annual refresh can
orphan every photo and comment**.

*The row counts in this paragraph are from the seeding run and have already moved — the ledger
held 4,251 rows on 2026-08-19, of which 21 are retired. Re-measure before quoting them.*

**This doc owns one contract:** what a published POI id refers to, for how long, and what
happens to it when the upstream data it came from is refreshed. It is v2 platform work in the
same sense [DATA_ENVIRONMENTS.md](DATA_ENVIRONMENTS.md) is — no screen, and the thing several
v2 screens quietly depend on.

---

## The problem: identity currently belongs to whoever we fetched from

`unify_poi` mints every published POI id as `{source}:{source_feature_id}` —
`atc_shelters:{GlobalID}`, `opentrail_at:{dbid}` — and its docstring promises the id stays
stable "across repeated pipeline runs **on unchanged input**". The qualifier is the whole
problem. The ATC refreshes its GIS data roughly once a year: names change, locations move by a
few feet, POIs are added, some are removed, and a lot are edited. Distances get re-measured.
None of that is a defect — it is the source being maintained, which is why it was chosen — but
every piece of it lands on an id scheme that assumes the input holds still.

Two distinct failure modes, because ArcGIS keys behave differently under different upstream
workflows:

- **Edit in place.** Attributes and geometry change; `GlobalID` survives. Today's ids carry
  through untouched, and the refresh is invisible to identity. There is evidence ATC does work
  this way at least sometimes — `editingInfo.dataLastEditDate` moves between our fetches, and
  the centerline's club attribution is two years fresher than the club-sections layer
  ([../pipeline/SOURCE_SURVEY.md](../pipeline/SOURCE_SURVEY.md) §3e), which is the signature of
  a layer being edited rather than replaced.
- **Republish.** A truncate-and-reload, a layer migration, a service rebuilt from a new
  geodatabase — any of these re-mints **every** `GlobalID`, including on features that did not
  change at all. One snapshot of ATC's data cannot say whether their annual update ever does
  this, and nothing this project controls prevents it. `opentrail_at`'s `dbid` is equally
  unaudited.

The second mode is the catastrophe, and today it is a *silent* one: every published id changes,
every stored reference dangles, and no check anywhere compares id sets across runs —
`check_output_quality.py` compares counts and hashes. [FIELD_NOTES.md](FIELD_NOTES.md) §7
already names this for notes; the exposure is much wider than notes.

### What anchors on a POI id

| anchor | state | what a re-mint does to it |
|---|---|---|
| `reports.poi_id` (`backend/app/models/report.py`) | built | dangles; lat/lon fallback survives |
| `FieldNote.poi_id` ([FIELD_NOTES.md](FIELD_NOTES.md)) | designed | dangles; §7's check would report the orphans, after the fact |
| Shared photo galleries, club pins ([POI_PHOTOS.md](POI_PHOTOS.md)) | designed | a shelter's whole gallery detaches |
| A hiker's **private, on-device photos** ([POI_PHOTOS.md](POI_PHOTOS.md)) | designed | detaches **invisibly — no server-side check can even see this one break** |
| Hike plans' day boundaries ([HIKE_PLANNING.md](HIKE_PLANNING.md)) | designed | a saved thru-hike plan loses its shelters mid-hike |
| `reference/shelter_capacity.json`, keyed to bare GlobalIDs | built | every capacity line silently stops joining |
| `fetch_poi_images.py` / `fetch_atc_photos.py` per-POI caches | built | a full cold re-crawl, tens of minutes of throttled requests |
| The conditions baseline's client-side join ([CONDITIONS_DELIVERY.md](CONDITIONS_DELIVERY.md)) | built | a phone on last month's release stops matching this week's baked conditions |
| `site_id` ([POI_SITES.md](POI_SITES.md)) | built | regenerates with the release — consistent within it, so not at risk; listed to say why not |
| `spurs.json` destinations | built | same: rebuilt alongside the POIs it references, not at risk |

The last two rows are the useful contrast: references that live *inside one release* regenerate
together and need nothing from this design. Everything above them lives *outside* the release —
in Postgres, on a phone, in a checked-in file — and crosses release boundaries, which is
exactly where identity has to hold.

And one anchor is not an id at all: **closures and ATC Trail Updates anchor on miles**
(`start_mile_marker`/`end_mile_marker`, NOBO miles from Springer), and a re-measure moves every
mile a little. That gets its own section below, because the fix is different in kind.

### The property

Stated once, the way [../pipeline/DATA_RELEASES.md](../pipeline/DATA_RELEASES.md) states its
own: **an id, once published, refers to the same physical place for as long as OurHike
publishes anything; every id ever published resolves to something — a live POI, or a tombstone
that says what happened; and when the evidence cannot carry an id forward, it retires rather
than guesses.** A photo waiting on a tombstone is recoverable. A photo of one shelter shown on
another is a false statement wearing a hiker's name, and it is the direction every threshold
below is tuned away from.

## Why the two obvious answers both fail

**"GlobalIDs are probably stable — key on them and hope."** That is the current design, minus
the hope being stated. It is one upstream republish away from total loss, it cannot survive a
source *change* even in principle — **#529 — 97% of shelters have no water source within 250 m,
and the trail is not like that** is actively looking for a better water source, and the day one
lands, every water id re-keys by construction — and when it fails, it fails silently.

**"Fuzzy-match old against new at every refresh, automatically."**
`build_shelter_capacity.py` already wrote this project's answer: *"A fuzzy join running
unsupervised inside a data build is a join nobody ever reads."* The measured evidence behind
that caution is in this repository, not hypothetical: ATC's own data spells one shelter
"Winturri" where its neighbour list says "Wintturi", holds "Rocky Run Shelter 1" and "2"
against a single "Rocky Run Shelters" row elsewhere, and [POI_SITES.md](POI_SITES.md)'s naive
name matcher produced a **903 km** "match" from a generic campsite name. A matcher with no
ledger, no evidence trail and no human diff is how one of those becomes a hiker's photos
displayed on the wrong shelter, permanently, with nobody having decided it.

The design below uses both — the key as the fast path, the matching as the fallback — with the
part both are missing: **a durable record that is reviewed as a diff.**

## The design: mint once, then own it

### 1. The ledger

`pipeline/reference/poi_identity.json`, checked in — the same posture, and for the same
reason, as `reference/shelter_capacity.json`: each identity decision is a reviewable line in a
diff, and a release build never depends on the network to know who anyone is. One row per POI
**ever published**, keyed by the OurHike id:

```
"atc_shelters:9C21…": {              # the OurHike id — minted once, never re-minted, never reused
  "poi_type": "shelter",
  "source": "atc_shelters",          # where the feature comes from TODAY
  "source_feature_id": "9C21…",      # upstream's CURRENT key — the field a re-key changes
  "name": "Wintturi Shelter",        # as last published; earlier names live in history
  "lat": 43.66…, "lon": -72.47…,     # as last published
  "first_seen": "2026-08-07",        # release id, DATA_RELEASES.md's YYYY-MM-DD
  "history": [                       # append-only, one entry per identity event
    {"release": "2027-09-14", "event": "matched", "by": "name+distance+fingerprint",
     "source_feature_id_was": "9C21…", "distance_m": 11, "name_was": "Winturri Shelter"}
  ],
  "retired": "2028-09-12",           # present only on tombstones
  "superseded_by": "atc_shelters:41BD…"  # only where upstream merged this place into another
}
```

**It doubled on 2026-08-25, and "reviewable line in a diff" is the part under strain**
([#1026](https://github.com/OurHike/OurHike/issues/1026)). The ledger went from 4,267 lines to
**8,579** — 8,563 rows — in one publish run, because the app started publishing for the whole
of New York state rather than a ring around New York City
([#1019](https://github.com/OurHike/OurHike/issues/1019)) and water started being measured
against every trail it draws rather than the A.T. alone
([#1016](https://github.com/OurHike/OurHike/issues/1016)). 4,312 of those rows are new, and
4,311 of them sit on a network trail with no A.T. mile at all. The maintainer raised
`test_no_committed_data.py`'s reference ceiling to 12,000 rather than split the ledger, with
the reasoning dated in that constant — and nobody reads 8,563 rows, which is why the thing
actually reviewed is `data/identity_review/summary.txt`: new, retired, carried by key, matched
by evidence, with the evidence for each match. The next registered source is expected to break
that ceiling again, and the answer then is probably the split rather than a third number.

Three rules, and they are the contract:

- **Never re-mint** an id for a place that persists, whatever happened to its upstream key,
  name, position or source.
- **Never reuse** an id, however long its row has been retired.
- **Never delete** a row. Retirement is an event in a place's history, not the end of its
  record — the record is what a hiker's photos are anchored to.

**The id string is a birthmark, not a pointer.** An id minted as `atc_shelters:9C21…` keeps
that spelling forever, even after upstream re-keys the feature or a different source starts
supplying it. Provenance is the `source`/`source_feature_id` *properties*, which tell the
current truth on every release; the id's prefix only says where the place was first seen.
Nothing may parse an id to learn its source — one sentence that needs saying now, because the
day it is false someone will have assumed it.

**Seeding is the empty migration.** The first ledger adopts the ids exactly as published today,
so its introduction changes no artifact byte, invalidates no stored reference, and needs no
client or backend change at all. Everything already written against `atc_shelters:{GlobalID}`
stays correct; what changes is that those strings stop being *derived* and start being *owned*.

### 2. Reconciliation, tiered by evidence

`pipeline/reconcile_poi_identity.py` runs in the weekly candidate build
([../pipeline/DATA_RELEASES.md](../pipeline/DATA_RELEASES.md) §2), after the fetches and before
`export_poi.py`. Input: the new raw snapshot plus the prior ledger. Output: the updated ledger
and a human-readable summary. The export then publishes every POI under its ledger id.

**Tier 1 — the key survived.** `(source, source_feature_id)` matches a live row: carry the id.
Name changed, position nudged, attributes edited — all carried silently, because those facts
are upstream's to change ([FIELD_NOTES.md](FIELD_NOTES.md)'s layering table: upstream owns
what exists, where it is and what it is called). This is "merge in the new information", and
under a key-stable refresh it is the whole refresh. One guard: a surviving key whose feature
moved implausibly far (over a mile) is held for review rather than carried — key reuse is rare
and conceivable, and a shelter teleporting is evidence of it.

**Tier 2 — the key did not survive; the evidence might.** Over the bipartite set of
disappeared rows × unmatched new features, blocked by `poi_type` (an id never crosses type),
score each pair on signals this repository has already measured the worth of:

- **Distance** — the refresh the ATC actually ships moves things "a few feet";
  `lib/spurs.py`'s equirectangular `distance_m`, the measurement [POI_SITES.md](POI_SITES.md)
  already reuses.
- **Position along the trail** — robust to exactly the lateral corrections that move lat/lon,
  via `export_elevation.py`'s own positioning helpers, so the measure matches the published one.
- **Normalised name agreement** — reusing `lib/poi_sites.py`'s measured normalisation (strip
  punctuation, trailing sibling digits, `group`), not a new one.
- **The inventory fingerprint, where the layer has one** — ATC's own survey makes shelters
  close to uniquely identifiable independent of name and position: `Year_Built`, `Stories`,
  `Exterior_M` and the facility counts are non-null on all 280, and privies carry `Year_Built`
  on 308 of 316. A renamed, moved shelter that still says "built 1938, one storey, log" is
  carrying its own passport.

Acceptance is deliberately three conditions, not a bare score, each bought by a failure already
in this repository: **clear the threshold**, **clear it by a margin over the runner-up** (the
Laurel Ridge lesson — two candidates that reduce alike need a tie-break, and near-ties go to
review instead), and **sit inside a hard distance ceiling** applied as `min()` against
everything else (the 903 km lesson — a matcher's gates get widened by future hands, and the
ceiling is what survives them). Matches must be mutual best on both sides.

**Tier 3 — everything else retires and creates.** An unmatched old row becomes a tombstone; an
unmatched new feature gets a fresh id. This is the default precisely because it is the
*recoverable* mistake: if the matcher missed, a later one-line override re-unites the tombstone
with its successor and every anchored photo and note comes back. The unrecoverable mistake is
the confident wrong merge, which is why nothing ambiguous ever auto-merges.

**Overrides are a hand-written file,** `pipeline/reference/poi_identity_overrides.json` —
"these two are the same place", "these two are not", each line with a reason, applied before
scoring. Machine-owned ledger, human-owned overrides, so `--check` regeneration can rewrite one
file wholesale without ever moving a person's line — the same split `sources.json` keeps
between discovered and hand-added entries, and the same job `BAD_QUADS` does in
`fix_corrupted_quads.py`.

### 3. Where the human sits — and where they don't

The question this design exists to answer: **how does a refresh land safely without a person
reviewing every point?** By making the review a diff, on a gate that already exists:

- The ledger and overrides are **files in git**. A refresh's identity outcome is their diff in
  the release PR that [../pipeline/DATA_RELEASES.md](../pipeline/DATA_RELEASES.md) §4 already
  routes every release through. Tier-1 carries touch at most a coordinate or a name field;
  wholly unchanged places produce **no lines at all**.
- The reconcile summary rides the PR body next to the verification report: N carried by key, M
  matched by evidence — **each of those M named, with its evidence** ("Winturri → Wintturi
  Shelter, 11 m, fingerprint intact"), per this repository's own rule that a bare reference
  tells the reader nothing — K new, J retired, and the held-for-review list.
- `reconcile_poi_identity.py --check` runs in CI, `build_shelter_capacity.py --check`'s
  pattern: the checked-in ledger must be exactly what reconciliation produces from the raw
  snapshot plus the prior ledger, so the reviewed file provably describes the data it ships
  with.
- **The write mode runs in CI too, and had to (#811).** The gate's failure message asks for a
  regenerated ledger, and the snapshot it must be regenerated from is `pipeline/data/raw/` —
  gitignored, and populated only on a runner mid-job. For a while `--check` was the only
  invocation anywhere under `.github/`, so the single environment able to produce the diff was
  also the only one that refused to, and the instruction could not be followed by anybody.
  `publish-vector-data.yml`'s `regenerate_identity_ledger` input now runs the write mode in
  place of the check and uploads the new ledger and its summary as a run artifact to review and
  commit. Such a run cannot publish: a ledger rewritten this minute is a ledger nobody has read,
  which is the state the gate exists to keep out of the bucket.
- `verify_release.py` gains a battery check: every published POI id is a live ledger row whose
  `(source, source_feature_id)` agrees, no id appears twice, no retired id is published live —
  drift between ledger and artifact caught at the same gate that catches every other kind.

Arithmetic on the expected load, labelled as arithmetic and not measurement: ~2,800 published
points. A key-stable year, the diff is only real adds, removals and coordinate/name lines —
dozens of rows. A full re-mint year, tier 2 decides nearly everything trivially (same
normalised name within a few feet, fingerprint agreeing) and the human reads the same dozens:
the genuinely ambiguous residue plus true adds and removals. The first real ATC refresh is the
measurement, and recording it — including the GlobalID survival rate, which decides how much
tier 2 ever runs — is part of the build order below.

### 4. Retirement, supersession, and what a tombstone publishes

- **Retired** rows keep everything they had, gain the release that retired them, and are never
  eligible to match again except through an explicit override.
- **Upstream merges two places into one** (Rocky Run Shelters): one old id carries onto the
  survivor by evidence; the other retires with `superseded_by` naming it. Anything anchored to
  the retired id re-anchors by following the pointer — a resolver, in one place per runtime,
  each in exactly one file, held to the others by a contract test over shared fixtures.

  *That sentence used to read "in one place … rather than implemented twice", and **#831 asked
  for the amendment rather than for the sentence to be quietly inherited**. One implementation
  is not reachable and the repository already says why: `backend/tests/test_conditions_publisher_
  contract.py` — "the pipeline is not importable from here (different package, its own
  dependencies)" — and the client is a third runtime again. What is achievable is what three
  tests in `backend/tests/` already do, so this adopts a practice rather than inventing one.
  Built for the client 2026-08-22 (#831): `pipeline/lib/poi_identity.resolve` and
  `client/src/lib/poiIdentity.resolvePoiId`, over the nine cases in
  `pipeline/tests/fixtures/poi_resolver_cases.json`, with `client-tests.yml`'s scope list
  carrying that directory so editing a case runs both suites rather than one.*

  *The two resolvers see different things, which is the part a reader should not have to
  rediscover.* The pipeline resolves against the whole ledger; a phone gets only
  `retired_poi.geojson`, because the live half is already on it as `poi_*.geojson`. So the
  tombstones alone cannot tell a live id from one this project has never heard of — and those
  are different answers. The client's resolver therefore takes the live set as a predicate,
  which is what makes it answer exactly what the Python one answers rather than approximately.
- **Upstream splits one into two**: the id follows the best successor (name-containment beats
  nearest, [POI_SITES.md](POI_SITES.md) §2a's tie-break); the sibling is new. Content stays
  with the surviving id, which is where its history actually happened.
- **What publishes:** a small **`retired_poi.geojson`** — id, name, type, last position, retired
  release, `superseded_by` — so a hiker's photos of a decommissioned shelter keep a card to
  live on, saying what happened to the place rather than vanishing. How long a tombstone stays
  published is answered under *Open questions* below. This is a *fourth* existence state in
  [FIELD_NOTES.md](FIELD_NOTES.md)'s family — removed-from-source is upstream's own word,
  where reported-missing is the field's — and the two compose: that doc's rule that an
  upstream republish never clears a dispute has a mirror here, **an upstream removal never
  deletes a hiker's content.**

  *Two corrections from building this (#673), both to sentences above that were written before
  the code they describe existed:*

  - **The name is `retired_poi.geojson`, not `poi_retired.geojson`.** `poi_*.geojson` is not a
    wildcard in this repository but a namespace carrying the invariant *live rows of one
    `poi_type`*, and three consumers enforce it: `verify_release.check_poi_identity` (check 21)
    fails any feature in that glob whose id is not a **live** ledger row — so a tombstone file
    there would fail once per feature, by construction — `publish.referenced_photo_keys` walks
    the same glob for photo promises, and both `lib/poi_schema.POI_TYPES` and the client's
    `poiKey()` build the name as `poi_{poi_type}.geojson`. Check 21 landed with #672, one day
    before this step was built, which is why the original name looked safe when it was written.
  - **`lib/r2_keys.py` does not refuse an undeclared artifact,** and planning around a gate that
    does not exist is worse than having none. Measured 2026-08-19: `validate_key` returns
    "legal" for `retired_poi.geojson`, `poi_retired.geojson` and `tombstones.geojson` alike. It
    gates top-level *prefixes*, extensions, banned words and version-ish spellings — there is no
    per-artifact allowlist, and adding one would change how every existing key validates. What
    actually declares a new artifact is [../pipeline/R2_LAYOUT.md](../pipeline/R2_LAYOUT.md)'s
    five-step "Adding an artifact" checklist, `publish.collect_artifacts()`, and
    `tests/test_r2_keys.py`'s hand-kept list of what the pipeline can publish.

  *And one thing the copy above cannot assume:* the first 21 tombstones this ledger produced are
  all `atc_csi` water points, not ATC shelters, so a card hard-coding "No longer in **ATC's**
  data" would be a false statement about every one of them. The ledger carries `source` on every
  row, and the sentence should be derived from it.

  *Re-measured 2026-08-22 while building the card (#831), and it got stronger: **93 retired rows
  now, across two sources** — `atc_csi` and `opentrail_at`. The second is not the ATC at all, so
  the hard-coded sentence would now be false about a share of every card the app will ever draw.
  Two things followed. `source` is published on every tombstone, a sixth property beyond the five
  this section lists, because a phone has no other way to get it — and it is published rather
  than **split off the id**, which is the shortcut that looks free: ids are minted
  `{source}:{source_feature_id}`, but §5's "a source swap stops being a re-key" means the id
  keeps its original prefix while `source` moves to the new truth. The prefix is history; the
  column is the fact. And `chrome/removedPoiText.ts` builds the sentence through the same
  `sourceLabel` map the live card's provenance line reads, so the two cannot describe one source
  in two voices.*

  *The card is built — `chrome/RemovedPoiCard.tsx` — and **nothing selects a retired id yet**,
  which is stated here rather than left to be found. Every route into the client's selection
  hands it an id that came from the live waypoints. The card is the half that has to exist
  first: the anchors that will reach it are a hiker's private photos and `PlanStop.poiId`, whose
  own comment says it is "kept so a later feature can follow the reference", and neither of
  those features can be built until a followed reference has somewhere to land.*

### 5. Photos and comments, walked through

The second half of **#666**'s ask, made concrete:

- **Backend rows change nothing.** `reports.poi_id`, `FieldNote.poi_id`, gallery keys — same
  columns, same soft-reference posture; the durability moved into the id itself.
  [FIELD_NOTES.md](FIELD_NOTES.md) §7's orphan check stays, demoted from mechanism to
  backstop: expected to find nothing, kept because a backstop that is never needed is the
  cheapest kind, and still the recovery path for content written before the ledger existed.
- **On-device content is the quiet beneficiary.** A hiker's private photos and a saved hike
  plan anchor to ids on the phone, where no server-side reconciliation could ever reach them.
  Durable ids are the only fix that works there at all: the phone updates its dataset and
  every anchor still resolves.
- **A source swap stops being a re-key.** When **#529 — 97% of shelters have no water source
  within 250 m, and the trail is not like that** lands a better water layer, tier 2 carries
  each existing `opentrail_at:…` water id onto the ATC-sourced row that is the same physical
  spring — notes and reliability history survive the swap, `source` starts telling the new
  truth, and `confidence` may rise. Without this design, that improvement would orphan every
  note on every spring as a side effect of shipping it.
- **Renames keep the searchable past.** `name_was` in ledger history is where "Doc's Knob"
  remains findable after ATC settles on "Docs Knob" — whether search actually indexes aliases
  is left open below, but the record exists either way.
- **`shelter_capacity.json` re-keys onto ledger ids** in the first change after seeding — a
  no-op diff on that day, and the end of its silent dependency on GlobalID stability.

## Miles are a projection, not an anchor

The re-measure problem is identity's sibling and needs a different fix. `mi 1,407.2` is a
reading against a specific measurement of the centerline; when ATC re-measures, the same
physical spot gets a slightly different number. Everything *published* per release — POI
`mile`, the elevation profile, the half-mile markers — regenerates against the new measurement
together and is internally consistent. What breaks is the same class as before: **stored**
references that cross release boundaries.

- `reports.mile` and `FieldNote.mile` already travel with `lat`/`lon` — the geometry is the
  anchor, the mile is a convenience, nothing to fix.
- **Closures store only miles** (`start_mile_marker`/`end_mile_marker`), so a closure authored
  against this year's measurement refers to a subtly different stretch under next year's. The
  fix is [../CONTRIBUTING.md](../CONTRIBUTING.md)'s units rule applied to position: **store
  canonical, convert at display.** Closure endpoints gain captured `lat`/`lon`, computed at
  authoring time from the index the author's client already holds — the same derived-not-
  measured posture `reports.mile` documents — and the mile becomes a per-release projection of
  that geometry. Captured at write time, deliberately: converting later via the old release's
  centerline only works while retention keeps that release, and
  [../pipeline/DATA_RELEASES.md](../pipeline/DATA_RELEASES.md) prunes 90 days after
  supersession.
- **ATC Trail Updates need nothing.** Their miles are ATC's own claims in ATC's own datum,
  re-baked daily against the current release — self-healing by construction.

## What this deliberately isn't

- **Not a fork of upstream data.** [FIELD_NOTES.md](FIELD_NOTES.md)'s rule holds: the app
  never edits an upstream fact. Continuity — "this row is that row, a year later" — is the one
  fact upstream does not publish, and it is the only fact this design adds.
- **Not an adjudication queue.** The standing-job argument that shaped Field Notes applies:
  review here is bounded (once per refresh), rides a gate that already exists (the release
  PR), and defaults to the recoverable outcome when nobody decides. No inbox accumulates.
- **Not a general conflation engine.** Sources are matched at transitions — a refresh, a
  swap — never continuously deduplicated against each other at steady state. *(And the
  transition this doc does not cover — two sources describing one place at the same time — is
  [POI_DEDUPLICATION.md](POI_DEDUPLICATION.md)'s, added 2026-08-13. The boundary is time
  against sources: this doc owns "this row is that row, a year later", that one owns "this row
  is that row, from somewhere else". It writes its decisions as `superseded_by` edges in the
  ledger above rather than keeping a second one, so the resolver, the tombstone and the
  release-PR review here serve both.)*
- **Not a client-side matcher.** [POI_SITES.md](POI_SITES.md) §1's reasons transfer whole:
  stable ids can only be minted where the raw evidence lives, testable against the real
  corridor, computed once.
- **Not a new id format.** Existing references stay valid on the day this lands; there is no
  migration event, which is most of why the design is safe to adopt.

## Build order

Each step useful alone, per the house convention:

1. **Ledger seeded + tier 1 + `--check` + the PR summary.** Survives a key-stable refresh
   outright, and turns a wholesale re-mint from a silent catastrophe into a loud, blocked
   diff. This is the step that should land before [FIELD_NOTES.md](FIELD_NOTES.md) ships and
   multiplies the anchored content.
2. **Tier 2 evidence matching + overrides + the `verify_release.py` check.**
3. **Tombstones, `superseded_by`, the resolver in backend serialisation and client lookup,
   `retired_poi.geojson`** — and §7's orphan check, if Field Notes has not built it already.
   *Pipeline half built 2026-08-19 (#673): the artifact, the `superseded_by` edge, and
   `lib/poi_identity.resolve`. **The backend and client halves are not built, and the reason is
   structural rather than scheduling** — nothing under `backend/` can read this ledger today.
   `backend/Dockerfile` copies only `app/`, `alembic/` and `alembic.ini`, so
   `reference/poi_identity.json` is not in the production image; `backend/app/` opens no file
   and no socket for data; there is no HTTP client in `backend/requirements.in` and no lifespan
   hook in `main.py` where a ledger could be loaded once; and `app/config.py` argues explicitly
   against holding the published bucket's settings. This is the same wall
   `models/report.py` already names for the sibling case — "this backend holds no centerline
   geometry — the trail is a published artifact the client and the pipeline share, not a table
   here." Closing it needs either a `poi_supersession` table with a loader shaped like
   `load_assignments.py`, or a boot-time fetch of `retired_poi.geojson`; both are a design
   decision of their own rather than a step of this one. Note also that "one resolver" across
   Python and TypeScript can only mean one implementation **per runtime** held together by a
   contract test — `backend/tests/test_conditions_publisher_contract.py` records why ("the
   pipeline is not importable from here").*
4. **Closure endpoint geometry capture; miles as projections.**
5. **Measure the first real refresh** — GlobalID survival rate, tier-2 volume, threshold
   quality — and record it here, with what the thresholds were changed *from* if they move.

## Open questions

- ~~**How long a tombstone publishes.**~~ **Answered 2026-08-19 (#673): forever**, and now on a
  measurement rather than the estimate this line used to carry. The 21 rows retired so far
  export to a 5,235-byte `retired_poi.geojson` — 249 bytes a tombstone — so a refresh year
  retiring fifty places adds ~12 KB to a first fetch that is already 5.3 MB gzipped. Pruning
  costs more than that in machinery alone: it needs the pipeline to know which tombstones still
  have a hiker's photo or note anchored to them, which is a Postgres read from a build that
  deliberately has none. `lib/poi_identity.retired_rows` carries the figure to re-measure
  against.
- **The thresholds and ceilings themselves.** Like [FIELD_NOTES.md](FIELD_NOTES.md)'s
  corroboration numbers: settled against the first real refresh, not guessed harder in
  advance. The structure (margin + ceiling + mutual-best) is the decision; the constants are
  calibration.
- **Whether tier 2 should be reachable at all by a POI carrying no name and no fingerprint**,
  which is a different question from calibrating the constants above, because for those rows
  the constants do not decide anything. `_score_pair` can award such a pair `SCORE_NEAR` (1.0)
  and `SCORE_MILE` (0.5) and nothing else, so its **maximum reachable score is 1.5 against
  `ACCEPT_THRESHOLD` 2.5** — no distance is close enough, and the margin, ceiling and
  mutual-best conditions are never consulted. Measured against the 2026-08-25 ledger, **3,567
  of 8,469 live rows are that shape (42.1%)**: 3,370 `nhd_crossing`, 177 `osm_water`, 17
  `nhd_stream`, 3 `atc_communities`. It bites hardest on exactly those crossings, because their
  ids are *coordinate-derived* — `nhd_crossing:{lat},{lon}`, with `source_feature_id` the same
  string — so tier 1's key is minted from geometry this project re-measures itself, and a
  re-measure is an identity event for a population that has no way to survive one. The
  2026-08-25 run has an instance: its single retirement, `nhd_crossing:41.40819,-73.87630`,
  sits 24.7 m from `nhd_crossing:41.40803,-73.87609`, minted new in the same run — same type,
  both unnamed — while the one crossing that *was* carried, "Beechy Bottom Brook", moved 8 m
  and survived on the 2.0 its name scored. That reading is proximity and a plausible cause, not
  a measurement: nobody has checked the two against the raw NHD flowlines, and a second unnamed
  crossing sits 31.7 m out on the other side.
  **#1028 — A POI with no name and no fingerprint can never be carried by tier 2, and 42% of
  the ledger is now that shape** holds the options. Retire-and-create is the recoverable
  direction and "miss rather than cry wolf" is the stated asymmetry, so accepting this is a
  legitimate answer — it is just not currently a written-down one.
- **Whether search indexes `name_was` aliases**, and whether the card ever says "formerly
  Winturri Shelter". The record exists regardless.
- **Whether tier 2 should ever run cross-`poi_type`.** A campsite upstream reclassifies as a
  shelter is a real event and a rare one; v1 says retire-and-create with an override available,
  which is recoverable, and the question is whether that is ever worth automating.
