# POI coverage, org by org and type by type — a qualified survey (August 2026)

Companion to [SOURCE_SURVEY.md](SOURCE_SURVEY.md) and
[NYC_SOURCE_SURVEY.md](NYC_SOURCE_SURVEY.md) (where each org's *trail* data came from),
[ALERTS_NOTICES_SURVEY.md](ALERTS_NOTICES_SURVEY.md) (the same reconnaissance for their
*notices*, and the survey this one is shaped after), and
[../features/POI_SITES.md](../features/POI_SITES.md) (what a POI becomes once it reaches a
phone).

Why this exists: the maintainer's ask, 2026-08-27 — *"We don't have POI for the org's
outside of ATC. Search those sources for the POI types we have. For example, DEC has
Shelters & Campsites mapped. Maybe we need to track each of the POI types for the org, and
whether or not it is provided."*

When this was written the map drew five orgs' trails and every published POI was ATC's.
`lib/poi_schema.POI_TYPES` is eight categories — shelter, campsite, water, resupply,
crossing, viewpoint, parking, privy — and OPRHP, DEC, NYNJTC and Mohonk Preserve
contributed none of them.

**That changed the same day.** The maintainer read this and answered: *"Lets not use water
from DEC, you are right. How about you crank this out and implement these 2?"* — so DEC's
and OPRHP's waypoints now ship, 8,480 of them, and neither org's water does
([#1097](https://github.com/OurHike/OurHike/issues/1097)). The survey is kept in the tense
it was written in, with the outcome marked where it lands: **§0**'s matrix says what ships,
**§4a** says where shipping disagreed with the counting, and **§9**'s ranked list records
which follow-ups are done. A survey rewritten to look prescient is a survey nobody can
check.

Written 2026-08-27 from live probes. **Every count below came from
[`spike_org_poi_coverage.py`](spike_org_poi_coverage.py)**, which is in the tree so a
reader who doubts a number can re-derive it rather than re-probe by hand:

```
cd pipeline && python spike_org_poi_coverage.py
```

The second half of the ask — *track each of the POI types for the org* — is
`sources.json`'s `poi_coverage` block, and `tests/test_poi_coverage.py` is what stops it
becoming a snapshot of today: every provider in the registry must carry a verdict for
every POI type, from a five-word vocabulary, and a supply claim must carry a dated count.

## The frame, and the one place it differs from the parent surveys

SOURCE_SURVEY.md's qualification order is unchanged — **structured beats scrapeable,
recent beats rich, licensed beats good, stewarded beats scraped**. One thing is added,
because POIs are where it bites hardest:

**An org's own publication flag outranks our bucketing of its data.** Both big layers here
carry a field saying which rows the org itself considers visitor-facing — DEC's
`PUBLICUSE`, OPRHP's `ParksApp` — and wherever the two numbers disagree, the org's is the
one to build on. It is the difference between "DEC has 331 shelters" and "DEC will stand
behind 321 of them", and the second sentence is the one a hiker's evening depends on.

Sources needing a human decision are marked **NEEDS REVIEW** and gathered in §8.

---

## 0. The matrix

Read `n / p` as *features published / features the org's own flag marks visitor-facing*.
**shipping** reaches a phone today; **available** means the org publishes it and nothing
here ingests it; **unsuitable** means it fails the bar, with evidence; **absent** means
probed and there is nothing; **unprobed** is an admission, not a finding.

| | shelter | campsite | water | resupply | crossing | viewpoint | parking | privy |
|---|---|---|---|---|---|---|---|---|
| **ATC** | shipping | shipping | shipping | shipping | *available* 409 | shipping | shipping | shipping |
| **NYS OPRHP** | **ships 37** | **ships 204** | *available* 151 / 15 | *available* 109 / 91 | **ships 793** | **ships 629** | **ships 1,201** | **ships 574** |
| **NYS DEC** | **ships 315** | **ships 2,077** | **unsuitable** 23 / **0** | absent | **ships 246** | **ships 202** | **ships 1,852** | **ships 350** |
| **NYNJTC** | absent | absent | absent | absent | absent | absent | *unsuitable* 26 | absent |
| **Mohonk Preserve** | absent | absent | absent | absent | absent | absent | absent | absent |
| **GATC** | absent | absent | *available* 65 | absent | absent | absent | absent | absent |
| **OpenStreetMap** | unprobed | unprobed | shipping | unprobed | unprobed | unprobed | unprobed | unprobed |
| **USGS** | absent | absent | absent | absent | shipping | absent | absent | absent |

**Twelve of those cells became `shipping` on 2026-08-27**
([#1097](https://github.com/OurHike/OurHike/issues/1097)) — the maintainer's decision on
reading this survey: *"Lets not use water from DEC, you are right. How about you crank this
out and implement these 2?"* `export_nearby_poi.py` publishes **8,480 waypoints** as
`nearby_poi.geojson` (0.37 MB gzipped), the sibling of `nearby_trails.geojson` and gated
the same way. The bolded numbers above are what that artifact actually contains, which is
**not** the same as what each org publishes — the two differ wherever this survey's
counting bucket turned out to be wrong for shipping, and §4a says where.

Neither org's water is among them, for two different reasons that both matter: DEC's is a
refusal, OPRHP's is a holdback. The U.S. Drought Monitor is registered and publishes
nothing point-shaped at all; its row is `not_a_poi_source` in the block rather than eight
`absent` cells.

**The one-sentence answer to the ask:** OPRHP publishes something for all eight types and
DEC for six, so between them the non-ATC orgs would roughly *double* every POI category on
the map — but neither layer is a POI layer, both are maintenance-asset inventories with
recreation facilities inside them, and one of the sixteen cells is a refusal rather than a
number.

## 1. The finding that reframes the other seven sections

Neither agency publishes "shelters" and "campsites" as layers. Each publishes **one large
point layer of everything it maintains**, typed by a free-text column:

| | layer | features | type column | distinct values |
|---|---|---|---|---|
| NYS DEC | `dec_backcountry_features/MapServer/0` | 21,468 | `ASSET` | 234 as stored, 223 trimmed |
| NYS OPRHP | `NY_State_Park_Facilities/FeatureServer/0` | 8,823 | `Sub_Asset` | 158 |

DEC says what this is in the layer's own `description`, and it is worth quoting because it
settles what kind of source this is:

> Point data locating and differentiating **assets on state lands**. Assets represented as
> point features are **man-made items, which require periodic maintenance or inspection**.
> Examples include: bridge, dam, culvert, building, gate, sign, parking lot, lean-to, pit
> privy, campsite, trail structure, spring, well and many others.

The largest single value in that layer is **`CULVERT`, 4,290 features**. 68% of it is
things no hiker would ever want a pin for — culverts, gates, log landings, foundations,
sign posts. OPRHP's is the same shape: 53% unmapped, led by picnic areas, benches and
playgrounds.

So "does DEC have shelters mapped" is not a question about which layers exist. It is a
question about which values one column takes, which is why the spike pages that column
whole rather than counting rows. **The buckets are ours, not the orgs'** — nobody at DEC
decided `PRIMITIVE TENT SITE` is ATC's `campsite` — and they are written out value by
value in the spike so a reviewer can reject one line instead of a total.

Three bucketing decisions are load-bearing and all three are arguable:

- **`PROPOSED *` is not a feature.** DEC's column carries 98 of them across 27 values —
  `PROPOSED LEAN-TO` ×11, `PROPOSED PIT PRIVY` ×5. Excluded from every count. A hiker who
  walks to a proposed lean-to finds trees.
- **A bridge is a crossing; a culvert is not.** Both are drainage assets to DEC. Only one
  is a thing you walk across.
- **Nothing enters `water` on the strength of its name.** §3 is that argument at length.

## 2. The org flag, and why the second number is the real one

Both layers carry a field for "would we show this to a visitor", and they behave
differently enough that using one name for both would hide the finding.

**DEC's `PUBLICUSE` is a genuine filter**: 7,645 `Y` against 13,823 `N`. And it is not
merely a flag — DEC *republishes the `Y` slice as small per-type services*, which is the
most useful practical result in this survey. Measured against the big layer's
`PUBLICUSE='Y'` counts on 2026-08-27:

| DEC service | its own count | `PUBLICUSE='Y'` in the big layer | |
|---|---|---|---|
| `dil/dil_land_assets_lean_to` | 315 | 315 | exact |
| `dil/dil_land_assets_prm_cmp` | 2,078 | 2,078 | exact |
| `dil/dil_land_assets_scenic_vista` | 134 | 134 | exact |
| `dil/dil_land_assets_visitor_center` | 5 | 5 | exact |
| `dil/dil_land_assets_parking` | 1,852 | 1,857 | −5 |
| `dil/dil_land_assets_firetower` | 35 | 34 | +1 |
| `dil/dil_land_assets_viewing_area` | 34 | 33 | +1 |

Four exact and three within five features. Stated as **reasoned, not proven**: the
hypothesis fits seven of seven closely and four of seven perfectly, and nothing in DEC's
metadata declares it. **Registering the small services buys DEC's own curation instead of
re-deriving it** — and there is no per-type service for privies or water, so those are
reachable only through the 21,468-row layer.

**OPRHP's `Public` field looks like the same thing and is not: it reads `Y` on all 8,823
rows**, so it filters nothing. `ParksApp` (5,822 `Y` / 3,000 `N`) is the field that
discriminates, and it is uneven in ways worth seeing before anything is published:

- **0 of 37 lean-tos** are in OPRHP's own app. The widest supply-versus-curation gap
  anywhere in this survey, and a reason to ask OPRHP before publishing them, not after.
- **15 of 151 water points** — the drinking fountains, none of the 136 spigots.
- **1,202 of 1,202 parking areas.** The one category where supply and curation agree
  exactly.

One more OPRHP caveat, since it decides how a card would have to speak: `CollectedDate`
spans 2006-05-10 to 2026-04-30 with **10 rows carrying a `9999-09-09` sentinel**, and the
bulk was collected 2011–2021. A facility's presence is much better evidence than its
currency.

## 3. Water — the one refusal, and it closes an open question

[NYC_SOURCE_SURVEY.md §10(g)](NYC_SOURCE_SURVEY.md) asked whether DEC's backcountry asset
types include water, noting it "raises the evidence bar if true". OPRHP's half was
answered 2026-08-27 and is yes. **DEC's half is answered here and it is no** — and the
distinction matters more than the symmetry suggests, because this is the path
[CLAUDE.md](../CLAUDE.md)'s "four ways this app can hurt somebody" is about.

DEC's only plumbed-water asset type is **`WATER SUPPLY SYSTEM`, 23 features, of which
ZERO are flagged `PUBLICUSE='Y'`**. DEC's own answer is that none of it is for visitors.
Sampling 14 of them found real water spigots beside a "Water Storage Tank", an
"Underground Water Line", and a drilled well whose own `NOTES` read **"Not Approved For
Human Consum[ption]"**.

The values that *sound* like drinking water are worse, and every one of the 350 is
`PUBLICUSE='N'`:

| value | n | what the rows actually are, sampled 14 each |
|---|---:|---|
| `WATERHOLE` | 207 | Fire-and-wildlife impoundments — "Wetland Pool", "Made by Tioga County SWCD in 2016" |
| `WELL` | 97 | Dominated by **NATURAL GAS WELLS** ("Maple Lane Drill Site", "Clark 1 Well… Plugged In 1981") and historic stacked-stone wells |
| `SPRING` | 19 | Some real; also "Unnoffical Unsanctioned Traditional Public Wa[ter]" and one "Untested" |
| `WATERFALL` | 14 | Not a water source in the sense the card means |
| `CISTERN` | 4 | CCC-era fire cisterns, laid-up stone |

A pipeline that matched on the word "water" would have published 207 fire ponds and 97 gas
wells as places to fill a bottle. **DEC is not a water source**, and that verdict is
pinned by a test rather than left to review, because "unsuitable" reads like "not done
yet" to a future reader in a hurry. Reopening it should mean new data from DEC — a new
layer, a flag that flips — not a new reading of the same 23 rows.

**OPRHP's water is real and still not simple.** 136 `Water Spigot` and 15
`Drinking Fountain` are plumbed fixtures named as such. But `Mineral Spring` (17),
`Water Tower` (12) and `Waterfall` (55) sit in the same column and are none of them a
place to fill a bottle, and **the layer records no seasonal shutoff** — a spigot's
presence is not a promise that it runs in April. Shipping it needs `export_poi.py`'s
confidence-and-provenance treatment the way `osm_water` got one, not a point dump.

## 4. NYS DEC — the maintainer's example, confirmed and qualified

*"DEC has Shelters & Campsites mapped"* holds, and generously:

- **331 shelters** — 325 `LEAN-TO`, 6 `SHELTER`; 321 public-flagged. The largest non-ATC
  shelter source found, and the Catskills' and Adirondacks' network. **No capacity
  field**: the layer carries `NAME`/`DESCRIP`/`NOTES`/`ACCESSIBLE`/`UPDATED` and nothing
  about how many sleep there, so a DEC shelter would export without capacity — absent
  meaning unknown, never zero, per CLAUDE.md.
- **2,315 campsites** — 1,754 `PRIMITIVE TENT SITE`, 548 `PRIMITIVE CAMPSITE`, 8
  `CAMPSITE`, 5 `PRIMATIVE CAMPSITE` (DEC's own misspelling; the rows are real); 2,091
  public-flagged. These are genuine backcountry sites, unlike OPRHP's drive-in
  campgrounds.
- **393 privies** — 356 `PIT PRIVY`, 24 `PORT-A-JOHN`, 12 `RESTROOM`. The closest analog
  anywhere to ATC's own privies, and reachable only through the big layer.
- **2,256 parking**, **248 viewpoints**, **1,182 crossings** (of which the 36 `FORD` rows
  are the interesting ones — an unbridged crossing is a hazard, not an amenity, and wants
  HIKER_SAFETY.md's treatment rather than a pin).
- **Resupply: absent.** No store, outfitter, hostel or concession asset type among the 223
  values, and no service of that kind beside the others.

Freshness: rows carry `UPDATED`, spanning 2002-08-24 to **2026-08-18** with 21,445 of
21,468 dated — the layer moves. There is no `editingInfo` on an on-prem MapServer, so a
`max(UPDATED)` query is the freshness marker, the same substitute `dec_hiking_trails`
already records.

Two hygiene warts, recorded so they are not mistaken for parser bugs: the free-text column
has 12 whitespace variants (`FORD ` beside `FORD`, a bare `' '` on 86 rows), and
`PHOTO_LINK` points at an internal drive (`M:\DLF\StateForest\…`), as does the layer
description's asset-list URL (`http://internal/…`). Neither resolves from outside DEC.

## 4a. What shipping changed about §0's counts, and why counting is not drawing

Four of this survey's original buckets did not survive contact with an actual export, and
the differences are worth naming rather than smoothing over — a count and a pin answer
different questions, and three of these four are cases where the honest count was the
wrong thing to draw.

| | surveyed | shipped | why |
|---|---:|---:|---|
| OPRHP `crossing` | 1,222 | **793** | `Stairs` (414) and `Vehicle Bridge` (15) dropped. §5 already flagged that "a reviewer may reasonably want them separated"; drawing is where it matters. A staircase is not a stream crossing. |
| DEC `crossing` | 247 | **246** | The 36 `FORD` rows were already excluded from both; the remaining gap is one row with an empty coordinate array. |
| OPRHP `parking` | 1,202 | **1,201** | One row arrives as a `Point` with an empty coordinate array. |
| DEC `campsite` | 2,091 | **2,077** | DEC's own per-type service publishes 2,078, of which one has no usable coordinates — and the service, not the big layer's `PUBLICUSE` slice, is what ships. |

**Fourteen features across three layers arrive as a `Point` with an empty coordinate
array** (12 in `dec_backcountry_features`, 1 in `dec_primitive_campsites`, 1 in
`oprhp_facilities`) — an agency's null island, written the honest way. They are dropped and
counted rather than published at 0,0.

One thing the export added that no count could: **a description for every one of the 8,480**.
OPRHP names only 18% of its rows (`Name` is flagged "(Legacy Field)" in their own alias),
so 3,133 of these waypoints reach a phone with no name at all. Rather than put the *park's*
name on a bridge inside it, `compose_description` assembles one sentence from two columns
each org does populate — "Trail Bridge in Beaver Island State Park." — which is
`lib/poi_description.py`'s argument applied to two more agencies.

DEC's `DESCRIP` is deliberately **not** in that sentence, and the measurement is the reason:
it is populated on 14,303 rows and **27% of them are under twelve characters** of
maintenance shorthand — `18" X 24 Metal`, `12" Good`, `Saloon Style Gate`. That is the same
finding `lib/atc_notes.py` already recorded about ATC's own `Comments` column, on another
agency's data. One thing inside it is genuinely useful and is left on the table on purpose:
parking rows carry `3 Vehicle Capacity`, which is exactly what a hiker planning a trailhead
start wants, and getting it out means parsing free text against a pattern nobody has
measured coverage for.

## 4b. What 8,480 waypoints do to a screen, and the rule they break

Found after the export was written, not before, which is the honest order to record it in.
[#1105](https://github.com/OurHike/OurHike/issues/1105) landed on `main` the same day and
re-confirmed a display rule with evidence: **amenity POIs stay chosen-trail-only**
([features/NEARBY_TRAILS.md](../features/NEARBY_TRAILS.md) §10, §11). It measured 50 OPRHP
amenities on one Harriman screen against POI_VISIBILITY.md's ~16, and concluded the rule
should stand.

Six of the types this survey ships are amenities, clipped to nothing. Measured with
#1105's own arithmetic (`spike_oprhp_poi_density.py --artifact`):

| densest z12 screen, 390 × 700 | every category on | default visibility |
|---|---:|---:|
| Harriman / Bear Mountain | 64 | 26 |
| Catskills | 34 | 22 |
| **Adirondacks** | **114** | **107** |

The worst screen is not Harriman and not on any ground this program set out to cover: 105
of those 107 are DEC primitive tent sites along the Saranac lake shores.

Two mitigations, neither of which makes it fine: MapLibre culls colliding symbols rather
than stacking them and #597 draws a culled waypoint as a dot, so that screen is ~16 pins
and ~91 dots; and four of the six types start hidden under #865's default. What neither
changes is how many waypoints compete for the screen — which is exactly what #1105 was
counting when it decided fifty was too many.

**The maintainer's call, 2026-08-27, with these figures in front of them: ship, and record
the collision.** NEARBY_TRAILS.md §10 carries it in full, including what would close it
properly — clipping the amenity types to `NETWORK_BUFFER_FEET` around
`nearby_trails.geojson`, the way §11 already buffers water. That is a follow-up with its
own issue, not something this change did quietly either way.

## 5. NYS OPRHP — the richest, and the least curated where it matters most

The only org publishing something for all eight types, all in one layer registered since
2026-08-18 as `oprhp_facilities` with `reaches_hikers: false`. §0's row has the counts;
§2 has the `ParksApp` unevenness that qualifies every one of them. Two type-level notes:

- **Campsites are facilities, not sites.** 153 `Campground` + 51 `Group Camp`, one row per
  drive-in campground rather than per tent pad. Reading 204 as a campsite count would
  overstate it by orders of magnitude. OPRHP's separate `NY_State_Parks_Camping` service
  is the same shape — 66 points, one per camping park.
- **Resupply is 91 `Concession` + 18 `Store`,** and whether a park concession stand is
  resupply in the sense a thru-hiker means is exactly what
  [#806](https://github.com/OurHike/OurHike/issues/806) got wrong about opentrail's `r`
  tag (0 of 72 points named for a store). Counted, not judged.

`Asset` is a coded integer 1–17 whose domain the service does not publish, so `Sub_Asset`'s
free text is the only legible type — the join hazard to solve before any of these become
waypoints.

## 6. NYNJTC and Mohonk Preserve — probed whole, and thin

**NYNJTC.** All 25 services on their public AGOL org (`G1WTEJ6UVRUTvh9C`) were listed. Two
are point layers:

- **`Points` — 0 features.** An abandoned KML-import shell
  (`FolderPath`/`SymbolID`/`Snippet`/`PopupInfo`), last edited 2024-04-15.
- **`Trailheads_HighlandsProject_Apr2026` — 26 real points**, edited 2026-04-09, fields
  `Park`/`Coord`/`Town`/`Hike`/`Difficulty`/`Length`/`ParkingLot`. It is a **featured-hikes
  table** whose rows happen to be trailheads, not an inventory of parking areas —
  `ParkingLot` is the lot's name as prose and one row is one suggested hike. Recorded as
  `unsuitable` for `parking` rather than `available`, because calling 26 curated hike
  starts "NYNJTC's parking" would misdescribe both the layer and the org.

The org that maintains more of this ground than anyone publishes the least of it, which
NYC_SOURCE_SURVEY.md §4 established for trails and this confirms for POIs. Their full
network remains an agreement, not a scrape.

**Mohonk Preserve.** All 23 services listed; three carry real data and none is a POI layer
— the 304 trail polylines already shipping, a single boundary polygon, and the
deer-management restriction zones the alerts survey found. Not a criticism of an
~8,200-acre preserve that publishes its trail network openly and keeps it current.

## 7. The gaps this survey found in our own build

Three, none of them about the other orgs, all found by asking the coverage question of
every provider rather than only the new ones.

**(a) ATC has an un-ingested POI type of its own.** `bridges` — 409 features, edited
2026-08-14, registered since 2026-07-25 with `reaches_hikers: false` and read by nothing.
The `crossing` layer a hiker sees is USGS NHD's *stream* crossings, which answers a
different question: where water crosses the trail, not where there is a structure to get
across it. So the survey's "ATC ships all eight" is not quite true, and the exception is
ATC's own data sitting in the registry unread.

**(b) USGS ships without being registered.** Found by `test_poi_coverage.py` on its first
run, and left as a finding rather than fixed here. USGS's only registered entry is
`usgs_3dhp`, `kind: watched_only`, `reaches_hikers: false` — a deliberate watch on the
successor dataset, whose own notes say "Nothing fetches this". The data that actually
ships is the retired NHD, pulled as bulk HU4 GeoPackages by `fetch_trail_water.py`, and it
has **no entry in `sources` at all**. `reaches_hikers_comment` calls that field the record
of "which registered sources actually SHIP"; this is data that ships without being
registered, which is the one case the field cannot express, so `export_sources.py` cannot
name USGS however the flag is set. The licence is the easy half — federal public domain,
already stated on `usgs_3dhp` and already on the client's credits screen.

**(c) Three orgs publish trailheads and `POI_TYPES` has no category for one.** DEC 10,520
(its own `Trailhead` layer, a separate dataset from the backcountry features — only 414
trailhead-ish rows are in that one), OPRHP 287, NYNJTC 26. A trailhead is where a hiker
starts, which is neither `parking` nor `crossing`, and the absence is why NYNJTC's only
POI-shaped data has nowhere honest to go. Adding a ninth type is explicitly not a one-line
change — `lib/poi_schema.py` documents three other places keyed to that tuple, and
`test_poi_coverage.py` is now the fourth.

## 8. Licensing, and what still needs a human

No blanks, per the parent surveys' rule. Nothing in this survey changes any org's terms;
every row is an existing conversation that should gain a POI question rather than a new
ask.

| org | terms as they stand | the conversation to add this to |
|---|---|---|
| NYS OPRHP | **Stated** — reuse with attribution, *non-commercial* (`oprhp_licence`) | [#769](https://github.com/OurHike/OurHike/issues/769) — the open question is whether OurHike is non-commercial within them, given [features/PRICING_MODEL.md](../features/PRICING_MODEL.md)'s paid passes. Publishing 4,128 of their facilities makes that ask more pressing, not less |
| NYS DEC | Unstated; empty `copyrightText`, on-prem so no AGOL item carries terms (`dec_licence`) | The DEC bundle in the OPRHP ask (NYC survey §10(c)). Their trails ship on maintainer authorisation; POIs would be the same footing, and a shelter is a bigger claim than a trail line |
| NYNJTC | Unstated (`nynjtc_licence`) | [#768](https://github.com/OurHike/OurHike/issues/768) — moot for POIs while there are none to take |
| Mohonk Preserve | Unstated (`mohonk_licence`) | [#992](https://github.com/OurHike/OurHike/issues/992) — moot for the same reason |
| USGS (NHD) | Public domain, federal work | §7(b) — a registration question, not a licence one |

**NEEDS REVIEW, gathered:**

- **(a) OPRHP's 37 lean-tos, none of which OPRHP shows in its own app.** The one cell
  where our reading and the org's own curation disagree completely. Ask before publishing.
- **(b) Whether a park concession stand is `resupply`** (§5). #806 is the precedent for
  getting this wrong quietly.
- **(c) A ninth POI type for trailheads** (§7c) — a schema decision, not a data one.
- **(d) OPRHP water's seasonal shutoff** (§3) — unrecorded on the layer, and the
  difference between a useful pin and a dry one in April.
- **(e) DEC's `FORD` rows** (§4) — 36 unbridged crossings that are a hazard rather than an
  amenity. Whether HIKER_SAFETY.md wants them at all is a safety call.
- **(f) NJDEP** — the next org in line for trails, still Incapsula-walled from this
  sandbox, so its POI layers (`Land/62`, State Park Service Points of Interest) are
  unprobed here as they were in NYC_SOURCE_SURVEY.md §5. Needs a human with a browser.

## 9. What to do with all this, ranked

Candidate follow-ups, deliberately not done in this survey — registering a layer, writing
a fetcher or extending `export_poi.py` each needs its own issue and its own review.

1. ~~**Register DEC's per-type services** (§2) — `lean_to` (315), `prm_cmp` (2,078),
   `scenic_vista` (134), `parking` (1,852), `firetower` (35).~~ **Done 2026-08-27**
   (#1097), plus `viewing_area` (34), and the prediction held: no new fetch code, and
   `lib/arcgis.py` paged all six on the first run. Privies and crossings came from the big
   layer after all — DEC publishes no per-type service for either — through a value
   allowlist plus `PUBLICUSE` rather than the type-prefix match this line warned against.
   Water did not, and will not.
2. **Decide OPRHP's non-commercial question** (§8). This got MORE urgent rather than less:
   3,438 of their facilities now reach hikers on terms whose applicability to a paid pass
   is still open. Nothing in #1097 settled it and nothing in #1097 depended on it — the
   flip was about an exporter existing, not about a licence answer arriving — but the
   number of features riding on that answer went from zero to 3,438.
3. **Ship ATC's own bridges as `crossing`** (§7a) — data already registered, already
   fetched, already licensed, read by nothing.
4. **Register the NHD source USGS actually ships** (§7b) — or record deliberately why a
   fetched federal dataset stays out of the registry.
5. **Decide the trailhead type** (§7c). Three orgs have the data and the schema has no
   shelf for it — and #1097 made this concrete rather than theoretical: 287 OPRHP
   trailheads were dropped by name in that export, and the client now filters any waypoint
   whose `poi_type` it does not know, so the day a trailhead type is added both ends have
   to move together.
6. **Measure OSM's POI coverage over this ground** — seven of OSM's eight cells read
   `unprobed`, which is honest and unsatisfying.
   [#771](https://github.com/OurHike/OurHike/issues/771) is the runnable place for it.
7. **Clip the amenity types to the trail ring** (§4b) — the follow-up that closes the
   rule collision #1105 exposed, using §11's existing `NETWORK_BUFFER_FEET` machinery.
   Ranked here rather than higher because the maintainer took the ship-and-record decision
   knowingly; ranked at all because 107 waypoints competing for a 16-pin screen is a real
   cost somebody should get to weigh with a number for what the clip would drop.
8. **Get `N Vehicle Capacity` out of DEC's `DESCRIP`** (§4a). It is exactly what a hiker
   planning a trailhead start wants, it is in a free-text column 27% of which is
   maintenance shorthand, and #806's lesson is that a plausible read of an uncounted column
   ships wrong data quietly. Needs a coverage measurement before a regex.

Nothing in this survey is a reason to publish anything faster. Every org above publishes
its maintenance inventory, not its visitor guide, and the distance between those two is
where a hiker gets hurt.

---

*Method note for whoever refreshes this: `spike_org_poi_coverage.py --refetch` re-reads
both big layers and reprints every count in §0 through §5. The ArcGIS claims re-verify the
way both parent surveys do (`?f=json` for `editingInfo` and field lists,
`/query?returnCountOnly=true` for counts). One sandbox gotcha worth knowing: DEC's on-prem
server intermittently drops connections mid-request, and answered `urllib` with
`RemoteDisconnected` where `curl` and the pipeline's own `lib/http_retry` succeeded — a
failure to retry through, not a layer that is down. Agency layers move slowly but the
free-text type columns accumulate dirt, so re-read the unmapped list rather than assuming
the buckets still catch everything.*
