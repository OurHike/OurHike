# Trail data for the White Mountains — a qualified survey (September 2026)

Companion to [SOURCE_SURVEY.md](SOURCE_SURVEY.md) (the A.T. survey whose qualification frame
this borrows), [NYC_SOURCE_SURVEY.md](NYC_SOURCE_SURVEY.md) (the second region, and the
template for how a region gets registered rather than merely described),
[README.md](README.md) and [../features/SOURCE_REGISTRY.md](../features/SOURCE_REGISTRY.md).
This is [#1207](https://github.com/OurHike/OurHike/issues/1207)'s deliverable.

**What this survey found, and what it ended up registering, are different sizes.** The
question was the White Mountains. The maintainer's decision on reading it was to ship the
*organizations* whole rather than clip them to the region — the same call
`export_nearby_trails.py` already records for DEC and NYNJTC, *"Don't limit data from orgs
based on geography"* — so `usfs_trails` and `usfs_rec_sites` are **nationwide** registrations
and `nh_granit_trails` is statewide. The Whites are where they were found and where every
field distribution below was measured; they are not the extent of what ships. §7 is the
nationwide picture and the one holdback it forced.

Written 2026-09-02 from live probes. **Every count and every field distribution below was
read from the layer itself that day**, by query, not from a page's claim about itself. Where
a service exposes no `editingInfo`, the substitute marker is named. Where a number came from
a paginated sample rather than the whole extent, it says so — and where an early sample
disagreed with the full extent, the full extent is what is written down.

The frame is SOURCE_SURVEY.md's, unchanged: **structured beats scrapeable, recent beats rich,
licensed beats good, stewarded beats scraped.** Sources needing a human decision are marked
**NEEDS REVIEW**, and §6 gathers every one of them in one place.

---

## 0. The complete candidate list

| source | trails | POIs | structured | last known change | verdict |
|---|:-:|:-:|:-:|---|---|
| USFS `EDW_TrailNFSPublish_01` | ✓ 2,093 segs / 1,548.171 mi in the Whites; **78,101 TERRA nationwide** | | ✓ | no date published — §5 | **ships** — §2, §7 |
| USFS `EDW_RecInfraRecreationSites_02` | | ✓ 335 in the Whites; **31,405 nationwide** | ✓ | no date published — §5 | **ships, minus the dispersed camping** — §2, §7 |
| NH GRANIT `CSD/RecreationResources` L2 | ✓ 7,643 in the Whites, 19,877 statewide | | ✓ | no date published — §5 | **ships** — §3 |
| NH GRANIT same service, L0/L1/L3 | | ✓ unprobed | ✓ | — | **NEEDS REVIEW** — §3 |
| AMC (Appalachian Mountain Club) | ✗ none published | ✗ none published | — | — | **no GIS to register** — §4 |
| ATC / NPS APPA layers | ✓ | ✓ | ✓ | 2026-08-04 | already in hand (sources.json) |
| OpenStreetMap | ✓ | ✓ | ✓ | continuous | already registered for water; the gap-filler question here is unasked |

**The headline, stated plainly because it decides everything below: neither USFS nor NH
GRANIT states any reuse terms at all.** Both were registered `licence_basis: unresolved` on
the morning of 2026-09-02; **the maintainer authorised publication the same day** ("yes do
publish these. Its publically available info."), so all three now carry
`maintainer_authorisation` — the footing ATC, NYNJTC, Mohonk and DEC already ship on, and
*not* a grant from either organization. §6(a) records what that does and does not settle.

All three now carry `reaches_hikers: true`, and that is a statement about wiring rather than
about intent: `export_nearby_trails.py` reads the two trail layers and `export_nearby_poi.py`
reads the recreation sites, both in the same change. §7 says what each filter keeps and drops.

---

## 1. The region, proposed with edges

"The White Mountains" has to be a shape before anything can be clipped to it. Two candidate
definitions turned up, and they are not the same shape — which is itself a finding:

- **The administrative one:** White Mountain National Forest, which the USFS layer selects
  exactly, as `admin_org LIKE '0922%'` (Region 09, Forest 22). The ranger districts present
  in a Whites bounding box are `092202`, `092204` and `092205`, plus 6 rows carrying the bare
  forest code `0922`. This is a *land ownership* boundary and it spans New Hampshire **and
  western Maine**.
- **The geographic one, as a probe bbox:** lon −71.95 → −70.85, lat 43.65 → 44.55 — Franconia
  Notch and the Kinsmans west to the Mahoosucs, Waterville Valley north to the Great North
  Woods edge. This is what §3's GRANIT counts are clipped to.

They disagree in both directions, and a hiker's weekend does not respect either: the WMNF
boundary excludes trails that are plainly "in the Whites" (state parks at Franconia Notch,
Crawford Notch), and the bbox includes ground nobody calls the Whites. **NEEDS REVIEW**: the
region's real edge belongs to the maintainer, the way NYC_SOURCE_SURVEY.md §1 left its
northern cut open. Nothing here depends on the answer — both sources are registered whole and
the clip is a later decision.

---

## 2. USFS — the authoritative WMNF layer, and its undecoded column

### 2a. Trails

`https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_TrailNFSPublish_01/MapServer/0`

Registered as `usfs_wmnf_trails`. The Forest Service's own published trail inventory, and
the only source surveyed here that is *authoritative* for the ground it covers rather than
derived from somebody else's.

Measured live 2026-09-02, on `admin_org LIKE '0922%'`:

| | count |
|---|---:|
| all segments | 2,093 |
| `trail_type` TERRA | 1,544 |
| carrying a `hiker_pedestrian_managed` season | 1,451 |
| total `gis_miles` | 1,548.171 |

The 549 non-TERRA rows are snowmobile and water corridors — a first page of results returned
`HIX MTN RD SNOMO`, `BERRY FARM SNOMO`, `ROSEBROOK SNOMO` — so **`trail_type` is a real filter
and not a formality**, the same lesson `dec_hiking_trails` records about DEC's per-use split.
`hiker_pedestrian_managed` is a season string (`01/01-12/31` on the sampled hiking rows), not
a boolean.

Sampled names confirm the layer is what it claims: `JEWELL`, `SCAUR`, `CHERRY MTN. CONNECTOR`,
`ROSEBROOK` — Mount Washington and the Bretton Woods side of the forest.

### 2b. `national_trail_designation` — undocumented, and better evidenced than it first looked

**@unvalidated, and this section has been revised once.** The field is an integer with **no
published domain** — `domain` is `null` on the live field metadata, read 2026-09-02, exactly
like `trail_class`, `trail_type` and `admin_org` on the same layer. Its distribution in WMNF:

| code | segments | miles |
|---:|---:|---:|
| 1 | 1,962 | 1,397.866 |
| 2 | 8 | 6.058 |
| 3 | 123 | 144.247 |

Code 3's 40 distinct names are dominated by the A.T.'s route through New Hampshire —
`CRAWFORD PATH`, `WEBSTER CLIFF`, `GARFIELD RIDGE`, `KINSMAN RIDGE`, `ETHAN POND TRAIL`,
`GULFSIDE`, `CARTER-MORIAH`, `MAHOOSUC`, `BEAVER BROOK`, `LIBERTY SPRING` — and one row is
named `GLENCLIFF (AT)` outright.

**The first version of this section concluded "it is not an A.T. filter"**, on the strength of
`GREAT GULF` and `MADISON GULF` carrying code 3 while certainly not being the A.T.

**An independent source now says otherwise.** §3a's white-blazed set — a different publisher,
a different column, the same ground — names essentially the same trails, **`GREAT GULF`
included**. So the row that was this section's main counter-example is grouped with the A.T.
by *both* agencies independently. Two unrelated sources making the same mistake is a much
weaker hypothesis than code 3 meaning the Appalachian National Scenic Trail, with Great Gulf a
corridor-adjacency call the two happen to share.

**The tag stays anyway**, for a reason that has not moved: this is a correlation between two
undocumented columns, not a decode of either, and `CRAWFORD PATH` still splits across codes 1,
2 *and* 3, which no "code 3 = the A.T." reading explains. What would settle it: the Forest
Service's data dictionary for the TrailNFS publish schema, which this survey did not find.

**What to do meanwhile:** do not route on it. A hiker's A.T. route comes from ATC's own
centerline, which this pipeline already ships and which is authoritative for exactly this
question. Searching `trail_name` for `APPALACHIAN` returns **0 rows** — the A.T. is here only
under its local trail names, which is correct for the Whites and is why a code-based filter
looked attractive in the first place.

### 2c. Recreation sites

`https://apps.fs.usda.gov/arcx/rest/services/EDW/EDW_RecInfraRecreationSites_02/MapServer/0`

Registered as `usfs_wmnf_rec_sites`. 335 point features on `managing_org LIKE '0922%'`,
measured 2026-09-02 — the whole set returned in one page, so this is a census and not a
sample. By `site_type`:

| `site_type` | n | | `site_type` | n |
|---|---:|---|---|---:|
| TRAILHEAD | 187 | | GROUP CAMPGROUND | 2 |
| CAMPGROUND | 53 | | INTERPRETIVE VISITOR CENTER (MINOR) | 2 |
| OBSERVATION SITE | 20 | | CLIMBING AREA | 3 |
| HOTEL, LODGE, RESORT | 16 | | BOATING SITE | 4 |
| PICNIC SITE | 15 | | SKI AREA NORDIC | 4 |
| CAMPING AREA | 12 | | SKI AREA ALPINE | 5 |
| LOOKOUT/CABIN | 6 | | six further types, 1 each | 6 |

Three things that matter to a hiker rather than to a schema:

- **187 trailheads** is the largest single category and maps cleanly to `poi_type` `parking`.
- **67 camping sites** (CAMPGROUND 53 + CAMPING AREA 12 + GROUP CAMPGROUND 2) map to
  `campsite` — but these are *developed Forest Service campgrounds*, drive-up sites with fee
  envelopes, not the backcountry sites a hiker on the ridge is looking for. Shipping them as
  `campsite` beside ATC's A.T. campsites would put two very different things under one pin,
  which is a POI_DEDUPLICATION question and not a licence one.
- **The layer publishes no water and no privies.** `total_capacity` and `fee_charged` exist as
  columns; neither was profiled, because nothing here ships.

The 16 `HOTEL, LODGE, RESORT` rows are where AMC's huts would be if they are anywhere in a
public dataset — **unprobed**, and §4 is why that matters.

---

## 3. NH GRANIT — wider than the forest, and a blaze column that is empty

`https://nhgeodata.unh.edu/nhgeodata/rest/services/CSD/RecreationResources/MapServer/2`

Registered as `nh_granit_trails`. New Hampshire's statewide GIS clearinghouse, run by UNH.
The service holds four layers — `Access Sites to Public Waters` (0), `Recreation Inventory:
Points` (1), `Trails` (2), `Recreation Inventory: Areas` (3) — and **only layer 2 was probed**;
the other three are a POI source this survey did not open and §6(c) records that.

Measured live 2026-09-02:

| | count |
|---|---:|
| statewide | 19,877 |
| inside the §1 Whites bbox | 7,643 |

That is **3.6× the USFS count for overlapping ground**, because GRANIT is not limited to
federal land: state parks, town forests and land-trust holdings are all in it. It is the only
surveyed source that covers Franconia Notch and Crawford Notch State Parks, which is most of
what §1 says the WMNF boundary leaves out.

### 3a. `BLAZE` is blank almost everywhere, and that is the ground, not a gap

**This section said the opposite for a few hours on 2026-09-02 and was wrong.** The
correction is kept visible rather than swapped, because the mistake is the instructive part.

GRANIT publishes a `BLAZE` column. Across the full 7,643 rows in the Whites bbox, by
group-by statistics rather than by sample:

| `BLAZE` | rows |
|---|---:|
| *(blank)* | 7,574 |
| White | 62 |
| Yellow | 4 |
| Red | 2 |
| Blue | 1 |

The first reading of this table was that a 0.9%-populated column is an unpopulated one, and
that `nh_granit_trails` should therefore register **without** a `blaze_field` — painting from
it would draw 99.1% of the Whites in no colour, which a hiker reads as a data outage.

**The maintainer corrected it from knowing the ground: the White Mountains largely do not use
paint blazes.** AMC's convention up there is cairns above treeline and unmarked tread below,
so a Whites trail having no blaze is the *normal* case, and GRANIT recording none is GRANIT
being right.

The data confirms it, and this is worth recording because it turns a domain fact into a
checkable one. Of the 62 rows that do read White, measured 2026-09-02:

- **61 carry `TRAILSYS` = `Appalachian Trail`**, and their names are the A.T.'s own route
  through the range — Beaver Brook, Kinsman Ridge, Franconia Ridge, Garfield Ridge, Ethan
  Pond, Crawford Path, Gulfside, Carter-Moriah, Glencliff, Liberty Spring, Centennial.
- The 62nd is `Lost Pond Trail` (`TRAILSYS` = `Square Ledge`), which runs beside the A.T. at
  Pinkham Notch.
- **Every one of the 7 non-white blazes is in lowland ground**, not the mountains — Dahl
  Wildlife Sanctuary, Burleigh CE, Red Hill.

So the column is not sparse; it is **correct**. The A.T. is white-blazed through the Whites,
almost nothing else up there is blazed at all, and that is exactly the picture GRANIT
publishes. `nh_granit_trails` registers **with** `blaze_field: "BLAZE"`, and
[`reference/blaze_mapping.json`](reference/blaze_mapping.json) maps the blank to `None` —
which `client/src/lib/blaze.ts` renders as *"Unblazed"*, as against `Unknown`'s *"Blaze not
recorded"*. The client already had the vocabulary for this distinction; the first reading
would have thrown away a true fact and printed a hedge in its place.

**What is still unstated**, and the reason the registry note keeps a limit on this: GRANIT
does not document whether blank means *unblazed* or merely *not recorded*. The reading rests
on the maintainer's knowledge of the region plus the A.T. correlation above — a sound basis,
and not the publisher's own word.

**This also re-opened §2b**, which is where the correction pays for itself twice — see there.

### 3b. The other columns

`PED` splits 3,883 rows `'1'` against 3,760 blank in the Whites bbox — so **blank is not
"no"**, it is unrecorded, and this layer gets **no `foot_field`** as a result. The evidence,
measured 2026-09-02: of those 3,760 blanks, **2,541 carry no use flag of any kind** — not
snowmobile, not ATV, not bike, not ski, not horse — and their names are ordinary hiking trails
(`Alpina Trail`, `Bathtub Trail`, `Beaver Pond Trail`), one of them literally
`Appalachian Trail - road link`. A `foot_allowed` of `{'1'}` would delete 2,541 hiking trails
including a piece of the A.T. — the exact failure `dec_hiking_trails`' `foot_allowed_comment`
records DEC's `{'Y'}` would have caused, one state over.

What the layer *does* justify dropping is the other direction: **1,209 blank-`PED` rows flagged
`SNOWMBL = '1'` and 124 flagged `ATV = '1'`** are motorized corridors. That is a filter on a
positive motorized flag rather than on an absent foot one, and `export_nearby_trails.py` has no
such filter today — so nothing is filtered yet, and `nh_granit_trails`' `foot_comment` is the
specification for the change that does it.

`MAINTORG` is a coded integer with **no published domain** — live values in the sampled page
are `0` (685), `22000` (422), `50110` (242), `31000` (215), `51700` (104) and a long tail. If
one of those codes is AMC, that is the closest thing to an AMC trail inventory anyone will get
from a public service, and finding out costs one lookup table this survey does not have.
**NEEDS REVIEW** — §6(d).

`MAPURL` exists and is unexamined. Sampled `TRAILNAME` values are real Whites trails (`A-Z
Trail`, `Air Line`) alongside rows that are not trails at all (`adj to Rt 118`, `Abanaki
Quad`), so the layer needs a name-quality pass before anything reads `TRAILNAME` as a label.

---

## 4. AMC — maintains the ground, publishes none of it

The Appalachian Mountain Club maintains most of the hiking trails in the White Mountains and
runs the hut system. **They publish no White Mountains trail or campsite GIS that this survey
could find**, which makes them the Whites' equivalent of NYNJTC in
NYC_SOURCE_SURVEY.md §4 — the org that holds the best data and offers no way in.

What was actually checked, 2026-09-02:

- ArcGIS Online search for `"Appalachian Mountain Club"` → 212 items.
- ArcGIS Online search for `owner:cpoppenwimer_AMC` → **721 items**, an active and substantial
  GIS program. Every item whose title matches trail/camp/hut/white-mountain is **Mid-Atlantic**:
  `Protect the View — Threatened Trail Views`, `Circuit Trails Assessment Project`,
  `The Highlands Trail in Pennsylvania`, `HT_entire_trail_network_u18n83`. This is AMC's
  Mid-Atlantic conservation and advocacy work, not the Whites.
- Their backcountry campsites page answers `200 text/html` to a named agent.

So AMC's Whites data is where SOURCE_SURVEY.md's club table already put it: the *White
Mountain Guide* (31st ed., paid, Avenza) and the backcountry-campsites page — **14 sites with
shelter/platform counts, caretaker fees and the bear-canister rule**, called there "best free
NH shelter data". Scrapeable is not licensed, and §6(b) is the ask.

**Nothing about AMC is registered.** An org with no fetchable source gets no registry row —
`test_no_verdict_for_an_org_that_is_not_a_source` would fail one, correctly.

---

## 5. Freshness — neither source publishes a date

Both are on-prem ArcGIS servers, and **neither layer exposes `editingInfo`**, so
`fetch_external_layers.py`'s change-aware skip cannot fire for any of the three registrations.
That is the state `dec_hiking_trails` and the OPRHP entries are already in, recorded rather
than fixed.

Worse than DEC's case in one specific way: DEC has an `UPDATED` column, so a
`max(UPDATED)` statistics query is a real substitute marker. **Neither of these layers has a
date column at all** — the USFS trails schema's only date-ish field is `accessibility_status`,
and GRANIT's has none.

What is available instead, measured 2026-09-02: the USFS service metadata answers a **strong
`ETag` (`"1a7709d0"`)**, the same marker shape `check_freshness.py` already compares verbatim
for ATC's and NYNJTC's feeds. It is recorded in the registry and **tagged `@unvalidated` as a
data-change signal**, for a reason worth stating: it is an ETag on the *service description
document*, and nothing has established that it moves when the *features* move. It could be
stable across a full republish, or it could churn on a server restart. What would settle it:
recording the value and re-reading it across a known USFS publish cycle. Nothing reads it yet.

---

## 6. Everything needing a human decision, in one place

**(a) The licence — ANSWERED 2026-09-02, and what the answer is worth.**
Neither organization states terms. Read live: `copyrightText` empty at the service level on
both; the USFS *layer* carries the bare string `USDA Forest Service`, which is an attribution,
not a grant; `EDW_RecreationOpportunities_01` carries a no-warranty disclaimer, which is a
disclaimer, not a grant. Neither is an AGOL item, so there is no `licenseInfo` to read.

The maintainer authorised publication on the grounds that the data is publicly available. That
is recorded as **`maintainer_authorisation`** rather than as `stated_by_org`, and the
distinction is not pedantry — it is what a sources screen prints. "Publicly available" is not
itself a reuse grant; SOURCE_SURVEY.md's rule is that public and queryable is not one, and it
is the same rule under which DEC, NYNJTC and Mohonk — all equally public — ship on
authorisation rather than on terms. The maintainer's decision is a legitimate basis and it is
*theirs*, not the agencies'.

**A stronger basis is available for USFS and has deliberately not been claimed.** A work of
the U.S. Government is not subject to domestic copyright (17 U.S.C. §105), and
`licence_basis_comment`'s own vocabulary lists "a federal public-domain work" as an instance
of `stated_by_org`. Adopting that reading explicitly would put these two entries on the
strongest footing anything in the registry has — stronger than ATC's. It is not done here
because the authorisation was given on public-availability grounds rather than on that
statute, and upgrading it unasked would be this survey asserting a legal position nobody
took. One sentence from the maintainer settles it whenever they want to.

**NH GRANIT is the thinner of the two authorisations**, and worth revisiting first if terms
ever matter: no public-domain-by-statute argument exists for it, and as a clearinghouse
aggregating town, land-trust and agency layers, the body that could actually answer for a
given segment may not be GRANIT.

**(b) AMC. NEEDS REVIEW.** The highest-value ask in this document and the one with no data
behind it. Their campsites page is the best free NH shelter data and their trail network is
the best full stop. Both are an agreement, not a scrape — the same verdict NYC_SOURCE_SURVEY.md
§4 reached for NYNJTC, and NYNJTC eventually answered.

**(c) GRANIT's other three layers. Unprobed.** `Recreation Inventory: Points` in particular is
an unopened POI source in the same service already registered. Cheap to probe; not probed here
because #1207's scope was trails.

**(d) `MAINTORG`'s domain. Unprobed.** If GRANIT publishes the lookup, it answers "which of
these 7,643 segments does AMC maintain" — a question no other source in this survey can answer.

**(e) The region's edge. NEEDS REVIEW.** §1: the WMNF boundary and "the White Mountains" are
different shapes and neither is obviously right.

**(f) USFS `HOTEL, LODGE, RESORT`. Unprobed.** 16 rows that may or may not be AMC's huts.

**(g) The overlap.** USFS and GRANIT both cover WMNF ground, at 2,093 and 7,643 segments. If
both ever ship, that is a deduplication problem on the scale `spike_poi_duplicates.py` exists
for, and nobody has measured it.


---

## 7. What actually ships, and the one thing held back

The registrations are nationwide (USFS) and statewide (NH GRANIT). This section is what the
exporters do with them — every count measured live 2026-09-02.

### 7a. Trails

`export_nearby_trails.py` gains both layers. Each needed a filter, and each needed a
*different* one, which is the part worth reading:

| source | filter | keeps | drops |
|---|---|---:|---|
| `usfs_trails` | `trail_type = TERRA` | **78,101** | SNOW 8,152, WATER 76 |
| `nh_granit_trails` | motorized exclusion | 19,877 less the flagged | `SNOWMBL` and `ATV` corridors |

**USFS's `foot_field` is `trail_type`, which is not a foot column**, and the reason is the
trap here. The obvious candidate is `hiker_pedestrian_managed` — and it is a *season string*
(`01/01-12/31`), not a flag, so it cannot be an allowed-set at all; worse, it is **null on
35,667 of the 78,101 TERRA rows**. Requiring it would delete 46% of the Forest Service's
terrestrial trail inventory. Absent is unrecorded, not prohibited — the same lesson DEC's `M`
and GRANIT's blank `PED` teach, three sources and three vocabularies making one mistake
available. And there is no prohibition to honour anyway: 78,064 of the 78,101 TERRA rows carry
some populated `hiker_pedestrian_*` column, and `hiker_pedestrian_restricted` reads the
literal string `N/A` on 399 of a 400-row sample.

**What that leaves undone, said rather than papered over:** the four-column per-use matrix
(managed/accepted/discouraged/restricted × fifteen uses) is undecoded, so the export cannot
tell a trail *managed* for hikers from one where hiking is merely accepted, and cannot exclude
a bike or OHV trail that also allows foot travel. That is a real gap against the maintainer's
*"It's OurHike, not OurBike"* rule — it keeps corridors a stricter reading would drop — and it
wants the Forest Service's data dictionary rather than a guess.

**GRANIT filters the other way round**, on a positive motorized flag rather than an absent
foot one, because its `PED` blank means unrecorded (§3b). New registry key `excluded_when`,
one source using it.

### 7b. POIs, and the holdback

`export_nearby_poi.py` gains `usfs_rec_sites` with a four-value allowlist:

| `site_type` | nationwide | → |
|---|---:|---|
| TRAILHEAD | 7,358 | `parking` |
| CAMPGROUND | 4,183 | `campsite` |
| GROUP CAMPGROUND | 422 | `campsite` |
| OBSERVATION SITE | 636 | `viewpoint` |

**`CAMPING AREA` — 10,783 rows, the largest site_type in the layer — does not ship.** It is
dispersed camping, and this project already decided not to publish that class of location.

The evidence, because the type name alone does not establish it:

- **`development_scale` reads 0 (undeveloped) on 8,135 of the 10,783**, with 1,549 at scale 1
  and 1,099 at scale 2. `CAMPGROUND` is the opposite shape — 3 on 2,490 rows, 4 on 960, 5 on
  139, 2 on 594, and **not one below scale 2**. The two types do not overlap at all.
- **The names are forest-road references, not places**: `FS1302-03`, `RD 614 SITE 13`,
  `RD 201 MI 8.2`, `LCR 839C-001`, `EAST FORK RESERVOIR RD-002`. That is a catalogue of
  individual pull-offs along a road.

The precedent is not new. [SOURCE_SURVEY.md](SOURCE_SURVEY.md) §3b holds back ATC's
Campsite Sustainability Index for the same reason — 2,333 user-created campsites, *"publishing
locations may be actively harmful"*, the ones land managers are often trying to close — and
the screenshot rules name a dispersed campsite at a readable zoom as one of four things that
must never appear even in a *picture*, on the grounds that a map is a publication of
coordinates. Shipping these would be that publication at **4.6× the scale of the holdback that
set the precedent**, arriving as a side effect of a change about the White Mountains rather
than as a decision anybody took.

`sources.json`'s `usfs_dispersed_camping_holdback` carries the argument;
`export_nearby_poi.py`'s `USFS_SITE_TYPES` is the mechanical guard; and
`tests/test_export_nearby_poi.py::test_usfs_dispersed_camping_never_ships` is what keeps a
future edit from widening the allowlist quietly.

**What would reopen it** is a real position and belongs to the maintainer: the Forest Service
publishes these itself, and is the land manager rather than a third party cataloguing what
hikers made — which is a material difference from ATC's case. That is an issue of its own.

### 7c. Two absences that must not be collapsed

Both sources cover the same ground and neither paints most of it. They are not saying the same
thing, and the export keeps them apart:

- **GRANIT blank → `None`** ("Unblazed"). GRANIT records a blaze where one exists, so its
  blank is evidence.
- **USFS → `Unknown`** ("Blaze not recorded"). USFS publishes no blaze column at all, so it
  has said nothing.

Collapsing them would tell a hiker the Forest Service had checked.
