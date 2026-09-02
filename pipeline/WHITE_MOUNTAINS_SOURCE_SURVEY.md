# Trail data for the White Mountains — a qualified survey (September 2026)

Companion to [SOURCE_SURVEY.md](SOURCE_SURVEY.md) (the A.T. survey whose qualification frame
this borrows), [NYC_SOURCE_SURVEY.md](NYC_SOURCE_SURVEY.md) (the second region, and the
template for how a region gets registered rather than merely described),
[README.md](README.md) and [../features/SOURCE_REGISTRY.md](../features/SOURCE_REGISTRY.md).
This is [#1207](https://github.com/OurHike/OurHike/issues/1207)'s deliverable.

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
| USFS `EDW_TrailNFSPublish_01` | ✓ 2,093 segs / 1,548.171 mi | | ✓ | no date published — §5 | **registered, does not ship** — §2 |
| USFS `EDW_RecInfraRecreationSites_02` | | ✓ 335 | ✓ | no date published — §5 | **registered, does not ship** — §2 |
| NH GRANIT `CSD/RecreationResources` L2 | ✓ 7,643 in the Whites | | ✓ | no date published — §5 | **registered, does not ship** — §3 |
| NH GRANIT same service, L0/L1/L3 | | ✓ unprobed | ✓ | — | **NEEDS REVIEW** — §3 |
| AMC (Appalachian Mountain Club) | ✗ none published | ✗ none published | — | — | **no GIS to register** — §4 |
| ATC / NPS APPA layers | ✓ | ✓ | ✓ | 2026-08-04 | already in hand (sources.json) |
| OpenStreetMap | ✓ | ✓ | ✓ | continuous | already registered for water; the gap-filler question here is unasked |

**The headline, stated plainly because it decides everything below: neither USFS nor NH
GRANIT states any reuse terms at all.** Both register with `licence_basis: unresolved` and
`reaches_hikers: false`. Nothing in this survey puts a byte on a hiker's phone. §6(a) is the
ask that would change that.

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

### 2b. `national_trail_designation` — the column that looks like an A.T. filter and is not

**@unvalidated, and this is the finding most likely to be misused by the next person here.**

The field is an integer with **no published domain** — `domain` is `null` on the live field
metadata, read 2026-09-02, exactly like `trail_class`, `trail_type` and `admin_org` on the
same layer. Its distribution in WMNF:

| code | segments | miles |
|---:|---:|---:|
| 1 | 1,962 | 1,397.866 |
| 2 | 8 | 6.058 |
| 3 | 123 | 144.247 |

Code 3 is *mostly* the Appalachian Trail. Its 40 distinct names are dominated by the A.T.'s
route through New Hampshire — `CRAWFORD PATH`, `WEBSTER CLIFF`, `GARFIELD RIDGE`,
`KINSMAN RIDGE`, `ETHAN POND TRAIL`, `GULFSIDE`, `CARTER-MORIAH`, `MAHOOSUC`, `BEAVER BROOK`,
`LIBERTY SPRING` — and one row is named `GLENCLIFF (AT)` outright.

**But it is not an A.T. filter.** `GREAT GULF` and `MADISON GULF` also carry code 3 and are
certainly not the A.T.; `WEBSTER CLIFF` is entirely code 3 while `CRAWFORD PATH` splits across
1, 2 *and* 3 and `FRANCONIA RIDGE` across 1 and 3, so the code does not even partition
consistently within a single named trail that the A.T. runs along.

What would settle it: the Forest Service's own data dictionary for the TrailNFS publish
schema, which this survey did not find. What the alternative costs: filtering the A.T. on
`national_trail_designation = 3` would silently adopt two Presidential-Range side trails as
A.T. and would fragment trails the A.T. actually follows. Searching `trail_name` for
`APPALACHIAN` returns **0 rows** — the A.T. is here only under its local trail names, which is
correct for the Whites and is why a code-based filter looked attractive in the first place.

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

### 3a. `BLAZE` exists and is empty — do not paint from it

**This is the finding that most needs to survive this document.** GRANIT publishes a `BLAZE`
column, which is precisely the field
[`reference/blaze_mapping.json`](reference/blaze_mapping.json) wants and which `oprhp_trails`,
`dec_hiking_trails` and `mohonk_trails` all supply. Across the full 7,643 rows in the Whites
bbox, by group-by statistics rather than by sample:

| `BLAZE` | rows |
|---|---:|
| *(blank)* | 7,574 |
| White | 62 |
| Yellow | 4 |
| Red | 2 |
| Blue | 1 |

**69 of 7,643 rows carry a blaze — 0.9%.** A first pass read a 2,000-row page and got 1,933
blank / 61 White, which is the same picture; the table above is the whole extent and is what
the registry records. Rendering a blaze from this column would mean 99.1% of the Whites drawn
with no colour and a scattered 62 in white, which reads as a data outage rather than as a map.
That is CLAUDE.md's "never let a display outrun its source" with the numbers attached, and it
is why `nh_granit_trails` registers **without** a `blaze_field` even though the column exists.

### 3b. The other columns

`PED` splits 3,883 rows `'1'` against 3,760 blank in the Whites bbox — so **blank is not
"no"**, it is unrecorded, and a `PED = '1'` filter would drop nearly half the layer including
trails that are plainly walkable. Left unfiltered and unresolved, the same shape as
`dec_hiking_trails`' `foot_allowed` question but without DEC's published domain to reason from.

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

**(a) The licence, and it blocks everything else. NEEDS REVIEW.**
Neither organization states terms. Read live 2026-09-02: `copyrightText` is empty at the
service level on both; the USFS *layer* carries the bare string `USDA Forest Service`, which
is an attribution, not a grant; `EDW_RecreationOpportunities_01` carries a no-warranty
disclaimer, which is a disclaimer, not a grant. Neither is an AGOL item, so there is no
`licenseInfo` to read the way `nynjtc_licence` and `mohonk_licence` quote one.

There *is* a real argument that the USFS layer is a public-domain work of the U.S. Government
(17 U.S.C. §105) and needs no grant. **That argument is not this survey's to accept.** It is a
legal reading rather than a published term, and this project's own rule — SOURCE_SURVEY.md's
"licensed beats good" — is that public and queryable is not a reuse grant. Recorded as the
question in `usfs_licence`, for the maintainer, alongside the observation that the two asks
are one state and one federal agency and need not be one conversation.

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
