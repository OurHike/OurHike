# OurHike — POI Identity (Feature Design Draft v1)

Companion to [../pipeline/DATA_RELEASES.md](../pipeline/DATA_RELEASES.md) (the release machinery
this rides), [FIELD_NOTES.md](FIELD_NOTES.md) (whose §7 names the orphaning this design
removes), [POI_PHOTOS.md](POI_PHOTOS.md), [HIKE_PLANNING.md](HIKE_PLANNING.md),
[POI_SITES.md](POI_SITES.md) and [`pipeline/lib/poi_schema.py`](../pipeline/lib/poi_schema.py)
(the id contract as it stands). **Status: designed 2026-08-13; build-order step 1 built
2026-08-18 (#671)** — the ledger is seeded (3,004 rows, ids exactly as published, verified a
byte-for-byte no-op on the real snapshot), tier 1 with the teleport guard runs as
`pipeline/reconcile_poi_identity.py`, `--check` gates publish-vector-data.yml, `export_poi.py`
publishes under ledger ids, and `reference/shelter_capacity.json` is re-keyed onto them. Steps
2–5 remain (**#672 — Evidence matching for re-keyed POIs**, **#673 — Tombstones and
superseded_by**, **#674 — Closures anchor on miles alone**, **#675 — Measure the first real ATC
refresh**). The umbrella is **#666 — A POI's identity is its upstream key, so one ATC annual
refresh can orphan every photo and comment**.

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
  the retired id re-anchors by following the pointer — a resolver, in one place, used by the
  backend's serialisers and the client rather than implemented twice.
- **Upstream splits one into two**: the id follows the best successor (name-containment beats
  nearest, [POI_SITES.md](POI_SITES.md) §2a's tie-break); the sibling is new. Content stays
  with the surviving id, which is where its history actually happened.
- **What publishes:** a small `poi_retired.geojson` — id, name, type, last position, retired
  release, `superseded_by` — so a hiker's photos of a decommissioned shelter keep a card to
  live on, reading "No longer in ATC's data since September 2028" rather than vanishing. A new
  artifact is a deliberate act (`lib/r2_keys.py` will refuse it until it is declared; that is
  the gate working, per [POI_PHOTOS.md](POI_PHOTOS.md)'s precedent), and how long a tombstone
  stays published is left open below. This is a *fourth* existence state in
  [FIELD_NOTES.md](FIELD_NOTES.md)'s family — removed-from-source is upstream's own word,
  where reported-missing is the field's — and the two compose: that doc's rule that an
  upstream republish never clears a dispute has a mirror here, **an upstream removal never
  deletes a hiker's content.**

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
   `poi_retired.geojson`** — and §7's orphan check, if Field Notes has not built it already.
4. **Closure endpoint geometry capture; miles as projections.**
5. **Measure the first real refresh** — GlobalID survival rate, tier-2 volume, threshold
   quality — and record it here, with what the thresholds were changed *from* if they move.

## Open questions

- **How long a tombstone publishes.** Forever is ~a few KB a year and honest; pruning after N
  years with no anchored content needs the pipeline to know what is anchored, which is a
  Postgres read (`export_conditions.py` already has the read-only pattern). Recommendation:
  forever, until measured cost says otherwise.
- **The thresholds and ceilings themselves.** Like [FIELD_NOTES.md](FIELD_NOTES.md)'s
  corroboration numbers: settled against the first real refresh, not guessed harder in
  advance. The structure (margin + ceiling + mutual-best) is the decision; the constants are
  calibration.
- **Whether search indexes `name_was` aliases**, and whether the card ever says "formerly
  Winturri Shelter". The record exists regardless.
- **Whether tier 2 should ever run cross-`poi_type`.** A campsite upstream reclassifies as a
  shelter is a real event and a rare one; v1 says retire-and-create with an override available,
  which is recoverable, and the question is whether that is ever worth automating.
