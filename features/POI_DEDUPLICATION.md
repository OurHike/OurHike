# OurHike — POI Deduplication (Feature Design Draft v1)

Companion to [POI_IDENTITY.md](POI_IDENTITY.md) (whose ledger records the decisions this doc
makes), [POI_SITES.md](POI_SITES.md) (several *different* waypoints at one place — this doc is
the *same* waypoint twice), [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md) (where a source declares
who it is, and whose "When two organizations map the same thing" section this supersedes),
[FIELD_NOTES.md](FIELD_NOTES.md) (which owns condition, and whose layering rule this reuses
rather than restates), [REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) and
[../pipeline/DATA_RELEASES.md](../pipeline/DATA_RELEASES.md) (the gate this rides).

**Status: designed 2026-08-13, not yet built.** Work is **#696 — Nothing stops two sources
publishing the same place twice, and the one rule that does is a 25 m constant for a single
source pair**. Every measurement below was produced by
[`pipeline/spike_poi_duplicates.py`](../pipeline/spike_poi_duplicates.py) against the live ATC
FeatureServer and opentrail.org on 2026-08-13, and is re-derivable by running it.

**This doc owns one contract:** when two published records describe one physical place, which
one survives, what it inherits from the other, and who is allowed to decide. It is v2 platform
work in the same sense [POI_IDENTITY.md](POI_IDENTITY.md) is — no screen, and the thing every
additional source depends on.

---

## Why a duplicate is worse than a gap

A hiker at eight percent battery wants to know whether there is water at the next shelter.
Two pins for one spring is two places to check, two cards to open, two sets of conditions to
reconcile — and the reconciliation is work the app has pushed onto someone standing in the
rain. **The map's job is to answer *is there water here*, not to enumerate the records we
hold.** That is [POI_SITES.md](POI_SITES.md)'s argument, and it applies with more force here:
a shelter and its privy really are two things, so drawing them as two pins was at worst
cluttered. One spring drawn twice is a false statement about how many springs there are.

It is also the failure this project can least afford to make quietly. Value #4 asks for
honesty about uncertainty; a second pin is not uncertainty, it is confident double-counting.

## The problem is arriving, not present

Every POI published today comes from a source that is ~1:1 with a `poi_type` — ATC's five
facility layers, its Communities layer, opentrail.org's two tags. Two records for one place has
been impossible by construction, which is why no rule exists. Three things end that at once:

- **A second source for a type we already carry.** `claude/water-sources-at-research-5b6xw0`
  folds OSM's 7,574 water nodes in beside opentrail.org's 174, and had to invent a merge rule
  to do it: `WATER_DEDUP_RADIUS_M = 25.0` in `export_poi.py`, dropping each OSM point within
  25 m of an opentrail one. The constant is measured — 41 of opentrail's 174 water points have
  an OSM twin inside it — and the call is the right one for one source pair under time
  pressure. It is also water-only, pair-specific, lives in an export function, and throws away
  the losing record's tags rather than keeping them.
- **Registered sources.** [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md) exists to let thirty clubs
  and a long tail of agencies supply data, and already predicts the collision: *"two orgs will
  both put a shelter near the same spot, tens of metres apart."*
- **Community submissions.** A hiker adding a spring already on the map is the highest-volume
  duplicate source there will ever be, and the only one with a person standing at the place
  while it happens.

Left alone this becomes one merge rule per source pair, each in the export function of whoever
added the source, none of them reviewable as a set.

## What the corridor actually holds

Same-`poi_type` pairs within a radius, over all 2,837 published points (pre-corridor-clip,
which slightly overstates crowding):

| radius | pairs | within one source | cross-source |
|---|---|---|---|
| 10 m | 24 | 24 | **0** |
| 15 m | 34 | 34 | **0** |
| **25 m** | **48** | **48** | **0** |
| 40 m | 77 | 77 | 0 |
| 60 m | 111 | 111 | 0 |
| 100 m | 217 | 217 | 0 |

At 25 m: 38 viewpoint pairs, 4 shelter, 2 parking, 2 privy, 1 campsite, 1 water.

**Two readings, and between them they settle the design.**

**First: there is no cliff.** The pair count roughly doubles from 25 m to 60 m and doubles
again by 100 m. 25 m is not a threshold the data discovered; it is a judgement about how close
two things can be before a hiker stops caring which is which. Adopting it is fine — the water
branch measured the same number useful for its own pair — but nothing may be built as though
the radius were the decision.

**Second: a blind 25 m rule would fire 48 times and be wrong about 35 of them.** Classify the
48 pairs by what their two names say:

| what the names say | pairs | reading |
|---|---|---|
| trailing sibling number — `"Tumbling Run Shelter 1"` / `"... 2"` | 14 | **two places** |
| a direction differs — `"The Horn (S)"` / `"The Horn (N)"` | 12 | **two places** |
| unrelated names — `"Goose Eye East Bog"` / `"Goose Eye Alpine Meadow"` | 9 | **two places** |
| one name contains the other — `"Bears Den Rocks Vista"` / `"Bears Den Rocks"` | 11 | one place, candidate |
| identical after normalisation — `"Height of Land"` / `"Height of Land "` | 2 | one place, candidate |

Thirty-five of the 48 are upstream saying, in its own words, that these are two places. ATC
numbers siblings and marks directions precisely because it is distinguishing things that stand
next to each other — the same convention [`lib/poi_sites.py`](../pipeline/lib/poi_sites.py)
already reads in the other direction. **Distance says these pairs are indistinguishable; the
name separates them cleanly.**

Worth noticing what a blind rule would delete: the two Horns Pond lean-tos, 11.3 m apart,
which [POI_SITES.md](POI_SITES.md) open question 1 already names as *genuinely one place with
two shelters*; the two Birches lean-tos at 10.1 m; the two Grafton Notch privies at 20.7 m,
which that doc's open question 4 also names. Three cases the repository had already identified
as real, all merged away by a rule that only knows how far apart they are.

### And the real duplicates are a very small number

The 13 candidate pairs are 11 places holding 23 records — **12 surplus points, 0.42% of the
map.** Twelve of the 13 pairs are ATC's viewpoint layer carrying an overlook twice, usually
with a trailing "Vista" on one of them and sometimes with nothing but a trailing space:

```
   0.0 m  'Bears Den Rocks Vista'          + 'Bears Den Rocks'
   0.4 m  'Wolf Rock (VA) Vista'           + 'Wolf Rock (VA)'
   0.5 m  'Jefferson Rock Vista'           + 'Jefferson Rock'
   0.8 m  'Sawtooth Ridge Vista'           + 'Sawtooth Ridge '
   3.8 m  'Height of Land'                 + 'Height of Land '
  16.2 m  'spring'                         + 'spring'          (opentrail water)
```

Wayah Bald carries three — `"Wayah Bald Summit"`, `"... Lookout Tower"`, `"... Lookout Tower
Vista"` — which is why the doc counts places rather than pairs.

**A source does publish a place twice.** The convenient assumption that intra-source pairs are
always two real things is false, and it is false in the layer that is 43% of every waypoint on
the map. What separates these from the 35 is not the source and not the distance: it is that
one name contains the other, at sub-metre separation.

### The cross-source duplicate we already ship is 4.7 km wide

`resupply` is the one `poi_type` fed by two sources today — ATC's 59 Community towns and
opentrail.org's 72 resupply points. Distance from each opentrail point to its nearest ATC
Community:

| within | 25 m | 100 m | 250 m | 1 km | 5 km |
|---|---|---|---|---|---|
| points | 0 | 0 | 0 | 0 | 1 of 72 |

Minimum 4,664 m; median 14,228 m.

**A radius would never find this pair, at any radius a map could use.** The two sources model
resupply at different granularity — a designated town against a specific road or store — so
"the same place" is not a distance question between them at all. Any design that treats
proximity as the definition of duplication is silently scoped to sources that agree about what
a point *is*, and this doc says so rather than discovering it later.

## The property

Stated once, the way the docs around this one state theirs:

**No two published POIs of the same type describe one place. Where the evidence says two
records are one place, exactly one id survives carrying every field the others can contribute;
the others retire with a pointer to it, and are never deleted, never averaged, and never
dropped without a line in a reviewed diff.**

Every threshold below is tuned away from the same direction: **a wrong merge is unrecoverable
in a way a surviving duplicate is not.** A duplicate is visible, embarrassing and fixable by
one override line. A merge that folds two overlooks into one deletes a place from the map,
takes any photos and notes anchored to the loser with it, and nobody is looking for a pin that
was never drawn.

## The design

### 1. Proximity proposes; evidence decides

Two stages, and keeping them apart is most of the design.

**Candidate generation** is `poi_type` agreement within `DUPLICATE_RADIUS_M = 25.0` — one
constant, matching the water branch's measured value, with a hard ceiling applied as `min()`
against it exactly as [`lib/poi_sites.py`](../pipeline/lib/poi_sites.py)'s
`MAX_SITE_RADIUS_M` is, and for the same reason: the next hand to widen this will widen it on
a hunch, and the ceiling is what survives them.

**Adjudication** scores each candidate on evidence, and the tiers are ordered by how much the
outcome can be trusted:

- **Tier 1 — the same upstream feature, arriving twice.** Same `source` and
  `source_feature_id`, or a source-declared cross-reference (an OSM `ref` naming an ATC
  GlobalID). Automatic, silent, no review. This is a fetch artifact, not a judgement.
- **Tier 2 — names agree and geometry agrees.** Normalised names identical, or one wholly
  containing the other, within the radius. This is the class the corridor's 13 candidates fall
  in, and it reuses [`lib/poi_sites.py`](../pipeline/lib/poi_sites.py)'s measured normalisation
  rather than a second one. Merged automatically, **named in the release PR summary with its
  evidence** — the same disclosure POI_IDENTITY.md's tier 2 makes.
- **Tier 3 — geometry agrees and the names do not contradict.** One side unnamed, or names
  that neither match nor carry a distinguishing token. Held for review; never auto-merged.
- **Never — the names distinguish.** A differing sibling number, a differing direction token,
  or two names that are simply unrelated. **These are not candidates at all, at any distance**,
  which is what keeps Horns Pond two shelters — and, measured against the corridor, is what
  rules out 35 of the 48 pairs a radius alone would have offered up.

The acceptance shape is [POI_IDENTITY.md](POI_IDENTITY.md)'s, deliberately: clear the
threshold, clear it by a margin over the runner-up, sit inside the hard ceiling, and be mutual
best on both sides. Reusing the shape matters more than reusing the constants — the two
problems are the same shape of problem, and a second scoring idiom is a second thing to get
wrong.

### 2. The hierarchy, and what precedence actually decides

Three tiers, as asked, and the thing worth saying about them is that **precedence is decided
per field, not per record.**

| tier | who | declared by |
|---|---|---|
| **1 — land manager or trail steward** | ATC, NPS, USFS, state agencies, land trusts | `Organization.kind` in [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md), confirmed at review |
| **2 — maintaining club** | the thirty A.T. clubs, authoritative on their own sections | `kind: club` plus a `MaintainerAssignment` covering the mile |
| **3 — community** | OSM, opentrail.org, and individual hiker submissions | everything else |

The tier is **declared at registration and confirmed by a human**, never inferred by the
matcher. It cannot be derived from `Organization.kind` alone — ATC is a `nonprofit` by kind and
tier 1 by role — and that is not a wrinkle to hide: whose data is authoritative where is a
trail-community question, and SOURCE_REGISTRY.md is already explicit that this project records
that decision rather than making it.

Now the part that matters. The winning record is not simply "the highest tier's row":

| field | who wins | why |
|---|---|---|
| `lat`/`lon` | highest contributing tier, **never an average** | a survey beats a recollection, and a midpoint is a location that exists in neither dataset — value #4's exact failure mode |
| `name`, `poi_type` | highest contributing tier | upstream owns what exists, where it is, and what it is called ([FIELD_NOTES.md](FIELD_NOTES.md)'s layering table) |
| `description` and attributes | highest tier **that has one**; gaps filled from lower tiers, attributed | a blank from ATC is not better than a sentence from a club. This is "combine the information", and it is where the water branch's drop-the-loser rule leaves value on the floor: OSM's `natural=spring` and `intermittent` tags are exactly what opentrail lacks |
| `photos` | union, ordered by tier | already decided and shipping — `export_poi.py` merges ATC's and Commons' galleries with ATC winning overlaps |
| `confidence` | highest contributing tier's | see below — corroboration does **not** raise it |
| condition, freshness, `last_confirmed_at` | most recent observation, whatever its tier | not this doc's at all: [FIELD_NOTES.md](FIELD_NOTES.md) owns the condition axis, and a maintainer's three-day-old note beats ATC's annual refresh there by design |

**Corroboration does not raise confidence, and the reason is measured.** Two community sources
agreeing looks like independent evidence and frequently is not: the water branch's own note
records that *opentrail imports OSM*, so an opentrail point and an OSM node at the same spring
are often one observation arriving twice. Independence between community datasets cannot be
assumed, so a merge records `corroborated_by` and leaves the dashed pin dashed. Only a tier 1
or tier 2 source contributing to the merge moves a POI onto the verified side of
[WIREFRAMES.md](../WIREFRAMES.md) §11's existence axis.

**Licence and attribution never merge into a winner.** A merged POI carries the attribution of
every source that contributed a field it publishes — ODbL for the OSM tags, ATC's terms for
the geometry — and the same per-record posture [CONTRIBUTING.md](../CONTRIBUTING.md) already
takes for photos applies. Publishing a merged record under the winner's licence alone is a
licence breach that no amount of correctness in the merge logic excuses.

### 3. The merge is a line in the identity ledger, not a new file

[POI_IDENTITY.md](POI_IDENTITY.md) already owns *this row is that row, a year later*, already
has `superseded_by` for the case where upstream merges two places into one, and already routes
its diff through the release PR. **A cross-source merge is that same edge with different
evidence**, so it is recorded in `pipeline/reference/poi_identity.json` rather than in a second
ledger that could disagree with it:

```
"opentrail_at:8814": {
  "poi_type": "water",
  "retired": "2026-11-07",
  "superseded_by": "atc_springs:41BD…",
  "history": [
    {"release": "2026-11-07", "event": "merged", "by": "name+distance",
     "into": "atc_springs:41BD…", "distance_m": 4, "tier_was": 3, "tier_won": 1}
  ]
}
```

Everything that follows comes free from that choice, which is the argument for it: the
resolver that re-anchors a hiker's photos through `superseded_by` already exists in that
design; the tombstone that keeps a card alive already exists; `verify_release.py`'s check that
no retired id is published live already exists; and the human review is the ledger diff on a PR
that already happens. **This doc adds the rules for drawing the edge and nothing else.**

Ordering in the build, which is not arbitrary: deduplication runs in the weekly candidate build
after the fetches and identity reconciliation, and **before `attach_sites`**. Site grouping
folds *different* types into one place; running it first would let a duplicate shelter become
the anchor of a site whose members then have to be re-parented when the duplicate is merged
away.

### 4. The check belongs in the submission, where the person is

The strongest evidence about whether two records are one place is held by someone standing at
the place, and it is available for exactly as long as they are still filling in the form.

- **The client checks first, offline.** The POI dataset is already on the phone — that is what
  offline-first means — so a submission at a dropped pin can search its own local data with no
  round trip and no signal. Same-type POIs within the radius surface as a question before the
  submission is written: *"There's already a spring 18 m from here. Is this it?"*
- **Two answers, and both are useful.** *Yes, that's it* turns the submission into a
  [FIELD_NOTES.md](FIELD_NOTES.md) observation on the existing POI — a confirmation, which is
  the more valuable contribution and takes one tap instead of a form. *No, this is a different
  one* proceeds, carrying the id it was warned about and the hiker's assertion that they are
  distinct. That assertion is a person's testimony from the ground, it outranks any matcher,
  and it is recorded rather than merely used.
- **The server re-checks, because the client is a courtesy and not a gate.** A stale dataset, a
  replayed request or an older build all bypass the client check. The server's check is
  authoritative; the client's exists so a hiker is told *before* they type a paragraph.
- **Nothing here blocks a submission.** A hiker who insists is right often enough — two springs
  twenty metres apart is an ordinary thing on this trail — and the failure mode of refusing is
  that the app has told someone on the ground that they are wrong about what they can see.

This also makes the tier-3 volume tractable. The duplicates that never get created are the ones
nobody has to adjudicate, and the check that prevents them costs one query against data the
phone already holds.

### 5. Overrides: strict means recorded, reviewed, and narrow

Maintainers and admins can override. The rules, and each one is load-bearing:

- **An override is a line in `pipeline/reference/poi_merge_overrides.json`, in git.** Machine
  owns the ledger, humans own the overrides — the same split
  [POI_IDENTITY.md](POI_IDENTITY.md) keeps, and the same one `sources.json` keeps between
  discovered and hand-added entries, so regeneration can rewrite one file wholesale without
  ever moving a person's line.
- **It reaches hikers through a merged pull request, never a button.** A maintainer without
  commit access submits it as a form and a bot opens the PR —
  [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md)'s exact bridge, with a second producer rather than a
  second mechanism. This is the rule [../pipeline/DATA_RELEASES.md](../pipeline/DATA_RELEASES.md)
  exists to protect: nothing self-service changes the bytes on a phone.
- **Two verbs only: `same` and `distinct`.** Force a merge, or forbid one. `same` may name
  which id survives; that is the whole surface.
- **What an override may never do:** create a POI no source published, move a point, rename one
  to something no source says, merge across `poi_type`, resurrect a retired id, or merge a
  record that has a `distinct` override standing against it. Each is a way of forking upstream
  data through a mechanism built for something else, and
  [FIELD_NOTES.md](FIELD_NOTES.md)'s rule holds here too: the app annotates upstream and files
  corrections upstream; it does not edit upstream facts.
- **Every line carries a reason and a person.** An override with an empty reason fails CI, the
  way `build_shelter_capacity.py --check` already fails a ledger that does not match its
  inputs. The reason is what the next maintainer reads in three years, and it is the only part
  of this file a machine cannot regenerate.
- **`distinct` outranks `same`,** whoever wrote them and in whichever order. The asymmetry is
  the property restated: refusing to merge is the recoverable outcome.
- **Reversing a merge is allowed; the anchored content does not follow it back.** Photos and
  notes written against the survivor stay with the survivor, because they were authored about
  *the place*, and the place is what survived. Saying this now is cheaper than discovering it
  during the first reversal.

And the escape hatch, named so nobody has to invent one: **if something is urgent it is not a
deduplication problem.** A hazard, a closure or a dangerously wrong pin goes through
[REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md)'s moderation queue, which is designed to move in
hours. A duplicate on the map for one release cycle costs a hiker one extra tap.

## What this deliberately isn't

- **Not an averaging or conflation engine.** Positions are never blended.
  [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md) is right about that and this doc keeps it.
- **Not "publish both and disclose the other".** That is the one place this **supersedes**
  SOURCE_REGISTRY.md, which recommended letting both records survive and showing *"ATC also
  maps a shelter 40 m north"*. It is a coherent position and it fails the opening argument of
  this doc: it publishes the two-pins-for-one-place state deliberately, and hands a hiker the
  adjudication. Disclosure survives — the merged card names every contributing source — but as
  provenance on one place rather than as two pins and a footnote. That section of
  SOURCE_REGISTRY.md is updated to point here.
- **Not a continuous matcher.** Sources are reconciled at transitions — a new source, a
  refresh, a submission — never re-deduplicated against each other at steady state, which is
  POI_IDENTITY.md's line and it holds for the same reason.
- **Not a client-side merge.** Stable ids can only be minted where the raw evidence lives.
  [POI_SITES.md](POI_SITES.md) §1's four reasons transfer whole.
- **Not a moderation queue.** Review is bounded (once per release), rides a gate that already
  exists, and defaults to the recoverable outcome when nobody looks. No inbox accumulates —
  the standing-job argument that shaped Field Notes applies unchanged.
- **Not POI_SITES.md.** That doc folds a shelter, its privy and its campsite — *different*
  types at one place — onto one pin. This one is the *same* type published twice. A privy is
  never a duplicate of its shelter, and two shelters are never parts of each other.
- **Not a fix for display crowding.** [POI_VISIBILITY.md](POI_VISIBILITY.md) owns what the map
  does when it cannot draw everything, and its dot rank means a surviving duplicate is drawn
  rather than silently dropped — which is why a duplicate is a visible defect rather than an
  invisible one.

## Build order

Each step useful alone, per the house convention:

1. **Candidate detection and a report, merging nothing.** Run the spike's rule in the weekly
   build and print the candidates into the release PR summary. This alone turns the 11 measured
   duplicates from unknown into a list somebody can act on, and it is what says whether the
   thresholds are right before anything depends on them.
2. **Tier 1 and tier 2 merges into the identity ledger**, with `--check` regeneration in CI and
   the `verify_release.py` battery check that no retired id is published live.
3. **Field-level precedence and the merged record's provenance** — `contributing_sources` on the
   published feature, gap-filling from lower tiers, and the attribution every contributor
   requires. This is the step that makes a merge combine rather than discard, and the step the
   water branch's rule should be folded into once both have landed.
4. **The submission-time check**, client then server, with the *"is this it?"* answer routed
   into a Field Note.
5. **Overrides, the form, and the bot-opened pull request.**
6. **Measure the first real cross-source merge** — the OSM water fold is the obvious candidate —
   and record here what the thresholds were changed *from* if they move.

Step 1 is worth doing whether or not the rest follows, and it is the step that stops this
document being a guess.

## Open questions

- **Whether the radius should vary by `poi_type`.** Viewpoints are 38 of the 48 pairs at 25 m
  because ATC maps overlooks densely along a ridge, and two overlooks 20 m apart are two
  overlooks. A tighter viewpoint radius is defensible; so is leaving one constant and letting
  the name evidence carry it, which is what the measurement suggests is already happening.
  Recommendation: one radius until a second type shows a problem.
- **The unnamed case.** `"spring"` + `"spring"` merged cleanly here, but a great many
  community-supplied water points will have no useful name at all, and tier 2 needs a name.
  Whether an unnamed cross-source pair inside a very tight radius (5 m?) should auto-merge, or
  always go to tier 3 review, is the decision most likely to be wrong in either direction, and
  it should be settled against the OSM fold's real volume rather than guessed harder now.
- **Whether ATC's twelve duplicate viewpoints should be filed upstream instead of merged.**
  [FIELD_NOTES.md](FIELD_NOTES.md)'s position is that the real fix is upstream's data changing,
  and a dozen named pairs is a small, actionable report ATC could act on once, for every
  consumer of that layer. Merging locally and filing upstream are not exclusive; doing only the
  first is how a private correction layer starts.
- **What a merged record's `source_feature_id` says**, given the published schema has one of
  each and a merged POI has several. `contributing_sources` as an additive property is the
  cheap answer; whether the scalar fields keep naming the winner or become null is a client
  question.
- **Whether a `distinct` override should expire.** A pair marked distinct in 2027 on evidence
  that ATC later corrects stays distinct forever. Permanence is the safe default and the doc
  keeps it; a review prompt after N years is the alternative and needs somebody to be reading.

## Related

**[POI_IDENTITY.md](POI_IDENTITY.md) is the sibling and the boundary is clean:** that doc owns
*this row is that row, a year later* — continuity across **time**. This one owns *this row is
that row, from somewhere else* — continuity across **sources**. Same ledger, same review gate,
same tuned-toward-recoverable posture; different evidence, and neither makes the other
unnecessary. Landing that doc's step 1 first is worth doing, because a merge edge in a ledger
that does not exist yet has nowhere to be written.

**[SOURCE_REGISTRY.md](SOURCE_REGISTRY.md) supplies the tier.** A source's trust level and
steward are declared there and read here; this doc adds no second taxonomy of who is
authoritative.

**[FIELD_NOTES.md](FIELD_NOTES.md) owns everything about condition**, and the division is worth
restating because it is what keeps both designs small: deduplication decides *how many places
there are*; Field Notes decides *what a place is like today*. A merge never touches a note, and
a note never merges a place.
