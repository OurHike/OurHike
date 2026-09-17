# Trail data within a day of NYC — a qualified survey (August 2026)

Companion to [SOURCE_SURVEY.md](SOURCE_SURVEY.md) (the A.T. survey whose qualification frame
this borrows), [README.md](README.md) (the pipeline that would consume these) and
[../features/SOURCE_REGISTRY.md](../features/SOURCE_REGISTRY.md). This is
[#770](https://github.com/OurHike/OurHike/issues/770)'s deliverable, inside
[#768](https://github.com/OurHike/OurHike/issues/768)'s program — the maintainer's 2026-08-18
scope call: Hudson Highlands core, plus the Catskills, plus everything NYNJTC maintains.

Written 2026-08-18 from live probes; **every count and every ArcGIS date below was read from
the layer itself that day**, not from a page's claim about itself. §12 was added 2026-09-15
under [#1432](https://github.com/OurHike/OurHike/issues/1432) and probed the same way — it
covers the one place this survey had no row for at all, which is New York City itself. Where a service exposes no
`editingInfo`, the substitute marker is named. The maintainer has offered links for sources
they know personally (their comment on #770) — the county rows in particular are expected to
grow when those arrive, and this snapshot says which rows are probed and which are not.

The frame is SOURCE_SURVEY.md's, unchanged: **structured beats scrapeable, recent beats
rich, licensed beats good, stewarded beats scraped.** Sources needing a human decision are
marked **NEEDS REVIEW**, and §10 gathers every one of them in one place.

---

## 0. The complete candidate list

| source | trails | POIs | closures | structured | last known change | verdict |
|---|:-:|:-:|:-:|:-:|---|---|
| NYS OPRHP AGOL org (4 layers) | ✓ 16,641 | ✓ 8,823 | ✓ live | ✓ | **2026-08-17** | **registered** (#769/#776); §2 |
| NYS DEC `dil` services | ✓ 5,277 hiking (+4 uses) | ✓ 21,466 + 10,524 + 314 | | ✓ | **2026-08-11** | trails **registered, ship** (#1019, maintainer authorisation 2026-08-25); POIs **registered, ship** as of 2026-08-27 (#1097) — seven layers, surveyed type by type in [POI_COVERAGE_SURVEY.md](POI_COVERAGE_SURVEY.md). Trailheads (10,524) are the one that stayed out, and DEC's water is a measured refusal rather than an omission (`dec_water_holdback`) — §3 |
| NYNJTC public extracts (LP, HT, SRT) | ✓ 43 + 12 | | ✓ one live detour | ✓ | **2026-08-04** | **registered, ship** — the two trail extracts on the maintainer's authorisation of 2026-08-24 (`nynjtc_licence`), their trail alerts separately on 2026-08-27 (#1078, `nynjtc_notices_licence`) — §4 |
| NYNJTC full network | ✓ | ✓ | | org-internal | GIS program alive | **agreement, not a scrape** — §4 |
| Mohonk Preserve trails/carriage roads | ✓ 304 | | | ✓ (own AGOL org) | **2026-08-24** | **registered, ships** (#992, maintainer authorisation 2026-08-25); §11 |
| NJDEP State Park Service Trails | ✓ 3,305 | ✓ (Land/62, uncounted) | | ✓ | undated (on-prem) | register after terms read — §5 |
| NJ Geospatial Forum Statewide Trails | ✓ 13,296 | | | ✓ | 2026-06-09 | the NJ-county answer — §5 |
| NJ Highlands Council HT copy | ✓ | | | ✓ | unprobed | secondary to NYNJTC's own — §5 |
| ATC / NPS APPA layers | ✓ | ✓ | ✓ | ✓ | 2026-08-04 | already in hand (sources.json) |
| Westchester County GIS | ✗ none found | | | ✓ server, no trails | — | thin — §6 |
| Other NY counties (Rockland, Putnam, Orange, Dutchess…) | ? | ? | ? | unprobed | — | awaiting maintainer links — §6 |
| data.ny.gov copies (DEC 2013, OPRHP 2014) | stale | | | ✓ | a decade ago | precedent, not a source — §9 |
| OpenStreetMap | ✓ | ✓ | | ✓ | continuous | gap-filler question, measured in #771 — §7 |
| **NYC Parks Trails** (five boroughs) | ✓ 7,059 | | | ✓ Socrata | **2026-09-03** | **registered, ships** (#1432, statutory terms — no ask needed); §12 |
| **NYC DOT greenways** (off-street) | ✓ 3,039 of 29,695 | | | ✓ Socrata | **2026-07-24** | **registered, ships** filtered (#1432); §12 |
| **NYC CSCL Centerline** (pedestrian classes) | ✓ 6,498 | | | ✓ Socrata | **2026-09-12** | **registered, ships** as `nyc_cscl_paths` (#1533) — path/boardwalk/step-street plus the doubly-asserted non-vehicular streets; holds the 97% of Central Park's path the trails layer does not; §12f |
| **NYC CSCL Centerline** (car-free park drives) | ✓ 124 | | | ✓ Socrata | **2026-09-12** | **registered, ships** as `nyc_park_drives` (#1533) — a reviewed ten-name list in two parks, boundary-clipped; the one entry that contradicts its own source; §12f |
| **NYC Planimetric Sidewalk** | polygons | | | ✓ Socrata | **2025-12-10** | **area, not line** — 80.7 acres inside Central Park, and centerline extraction is what it would take; §12f |
| NYC DCP's ArcGIS bike mirror | stale | | | ✓ | **2017-03-08** | not a source — nine years stale, no greenway column; §12 |

PIPC appears in no row of its own: its NY parks (Harriman, Bear Mountain, Sterling Forest)
are inside OPRHP's layer (verified — Harriman segments carry `Unit: Palisades`), and its NJ
section is *expected* inside the NJ layers but **unverified** — §10(f).

---

## 1. The ring, proposed with edges

"Within a day of NYC" has to be a polygon before the spike can clip against it and the
packaging can size it. Proposal, derived from the maintainer's three named pieces:

- **Counties, NY:** Westchester, Rockland, Putnam, Orange, Dutchess (the Hudson Highlands
  core and its approaches), plus Ulster, Sullivan, Greene, Delaware (the Catskill Forest
  Preserve's counties).
- **Counties, NJ:** Bergen, Passaic, Morris, Sussex, Warren (NYNJTC's territory to the
  Delaware Water Gap), plus Essex, Hudson, Union (the close-in parks a subway rider reaches).
- **As a spike bbox:** lon −75.4 → −73.4, lat 40.45 → 42.55 — Delaware Water Gap to the
  Connecticut line, New York Harbor to the Catskills' northern escarpment.

Two edges are deliberately open and belong to the maintainer, not this survey — **NEEDS
REVIEW**: (a) **Long Island** — OPRHP's layer has a `Long Island` region and DEC has Suffolk
units, but NYNJTC does not cover LI and the scope call did not name it; (b) the **northern
cut** — the Long Path itself continues past the Catskills toward Albany, and v1 of this
program should probably cut the trail at the ring's edge and say so on screen rather than
pretend it ends there (the seam question [#772](https://github.com/OurHike/OurHike/issues/772)
owns).

**Both closed 2026-08-25, and the ring with them**
([#1019](https://github.com/OurHike/OurHike/issues/1019)). The maintainer's words:

> There shouldnt be a ring around NYC. Include all of DEC, NYNJTC & NYSP. Don't limit data
> from orgs based on geography.

So there is no ring, no Long Island question and no northern cut: an organization's layer
ships whole, and `export_nearby_trails.py` filters only on what a source says about a trail
— walkable, open, whose route it is. The county lists above stay in this section as what
the scope call meant by "within a day of NYC"; they are no longer a clip. The bbox is gone
from the code rather than widened, because a wider box is the same decision with a
different number in it.

What the ring cost while it was on, measured 2026-08-25 by running the export either side
of the change against the same fetched layers: **4,002 features → 21,805**. NYS Parks 3,618
of their 16,641 statewide segments → 16,187. NYNJTC's Long Path 33 of 43 sections → all 43.
DEC, registered by the same change, 418 rows → 5,224. What it now costs to carry: 1.7 MB
gzipped → 7.3 MB, on a screen with no offline store yet —
[features/NEARBY_TRAILS.md](../features/NEARBY_TRAILS.md) §9 hands that number to
[#552](https://github.com/OurHike/OurHike/issues/552), which is where a per-region cut
belongs if one is wanted.

## 2. NYS OPRHP — registered, and what it does not cover

Registered 2026-08-18 (#769, merged as PR #776): four layers on org `1xFZPtKn1wKC6POA`,
fetched change-aware by `fetch_external_layers.py`, licence pending the maintainer's
outreach (`oprhp_licence` in [sources.json](sources.json)). Facts that place it in the ring:

- `Unit` is OPRHP's **eleven regions** — `Palisades` and `Taconic` are the ring's two, and
  the ring also touches `New York City` and `Long Island` if §1's open edge closes that way.
  (One hygiene wart, familiar from ATC's club spellings: `Saratoga-Capital` and
  `Saratoga/Capital District` both appear.)
- **Hudson Highlands State Park Preserve is fully inside it** — a bbox over Breakneck/Bull
  Hill alone returned 111 segments across 24 named trails with blazes (Breakneck Ridge
  White, Undercliff Bypass Green, Little Stony Point Red), all
  `Facility: Hudson Highlands State Park Preserve`. NYNJTC *maintains* most of those trails
  but publishes no data for them — §8's overlap rule in one park.
- What it does **not** cover: DEC land (the Catskills), anything in NJ, county parks, and
  every trail on ground OPRHP does not administer.

## 3. NYS DEC — the Catskills, qualified

The maintainer's lead (`gisservices.dec.ny.gov/gis/dil/`, "Outdoor Activity") resolves to an
on-prem ArcGIS server, folder `dil`, and it qualifies well:

- **`dil/dil_trails/MapServer`** — per-use layers. Hiking (layer 2): **5,277 segments**,
  fields `UNIT`/`FACILITY`/`NAME`, per-use flags (`FOOT`/`HORSE`/`BIKE`/`XC`/`SNOWMB`/
  `ATV`/`MOTORV`), `MILES`, `ACCESSIBLE`, `DESCRIP` — and **`MARKER`**, DEC's word for the
  blaze. Catskills proven: `UNIT: CFP` rows for the Burroughs Range Trail (Red), Diamond
  Notch (Blue), Dry Brook Ridge (Blue), with per-segment mileage. Sibling layers: XC ski
  4,511 · mountain bike 2,478 · snowmobile 2,365 · horse 1,263 · MAPPWD 364. Layer 3 is a
  42-feature conservation-easement variant (`PUBRIGHTS` field).
- **`dec_backcountry_features/MapServer`** — Back Country Features **21,466** points
  (`ASSET`-typed; whether water sources are among the asset types is **unchecked** — the
  same question #769 left open for OPRHP's facilities, and the same raised evidence bar if
  true) and Trailheads **10,524**.
- **`dil/dil_land_assets_lean_to`** — **314 lean-tos** statewide, the Catskills' shelter
  analog. Primitive campsites, parking, fire towers and vistas sit beside it as their own
  services, counts unprobed.
- **Freshness:** no `editingInfo` (classic on-prem MapServer), but the layer carries a
  per-feature `UPDATED` date and a `max(UPDATED)` statistics query answers in one request —
  **2026-08-11** on the day of this survey, so the layer moves. That is a registerable
  marker in the `usgs_3dhp` mould (a recorded query, not the default ArcGIS marker).
- **Hygiene, stated now so the spike is not surprised:** `UNIT` mixes preserve codes
  (`CFP`, `AFP`) with hundreds of per-county state-forest codes (`Ulster 02`,
  `Sullivan 05`) and real dirt — `-99`, blank, `Sullivan06`, an `Ostego` misspelling,
  trailing spaces. Ring-relevant units are CFP plus the state-forest codes of §1's NY
  counties.
- **Licence: unstated on the service** (empty copyright). The data.ny.gov "Hiking Trails"
  listing is attributed to DEC and carries no licence field either — §9. **NEEDS REVIEW:**
  the maintainer's OPRHP ask should probably bundle DEC — one state, two agencies, and the
  Open-NY listings are precedent that both already publish these layers openly.

**Verdict: register next**, as four-to-six `external_arcgis_layer` entries —
`lib/arcgis.py`'s fetcher pages MapServer layers exactly as it pages FeatureServer ones, so
`fetch_external_layers.py` consumes these with no code change beyond the freshness note.

**Acted on 2026-08-25** ([#1019](https://github.com/OurHike/OurHike/issues/1019)), for the
hiking layer only. `dil/dil_trails/MapServer/2` is in [sources.json](sources.json) as
`dec_hiking_trails` behind a new `dec_licence` block, shipping on the maintainer's
authorisation — the same footing `nynjtc_licence` and `mohonk_licence` use, since DEC's
`copyrightText` is empty and an on-prem service has no AGOL item carrying terms to read.
The prediction above held exactly, and then some: **no code change at all**, not even the
freshness note — `lib/arcgis.py` paged the MapServer and 5,286 features came back on the
first run.

Re-probed that day against this section's 2026-08-11 reading: **5,286 segments**, up from
5,277, so the layer moves as claimed. Three things the survey did not say, found on the
re-probe and now carried in the entry itself:

- **`MARKER` is a coded domain whose codes are the words** (Red/Yellow/Blue/Orange/Green/
  White/Other), like OPRHP's `Blaze` and unlike `side_trails`' integers — so it goes
  straight to `reference/blaze_mapping.json` with no decode in front of it. Live values:
  2,929 rows say nothing at all, and one reads `ORANGE AND RED`, which DEC's own domain
  does not declare and which is deferred rather than painted.
- **`FOOT` reads `Y` on 4,050 rows and `M` on 1,236, and nothing else.** DEC's CORRIDOR USE
  domain glosses `M` as MAINTAINED; 991 of those rows are `ASSET: FOOT TRAIL`, 681 carry a
  marker colour, and the named ones are ordinary hiking trails — the Finger Lakes Trail,
  the North Country Trail, the Long Path. Reading `M` as not-walkable would drop 23% of
  DEC's own hiking layer, so the entry declares `foot_allowed: ["Y", "M"]`. That reading is
  ours rather than DEC's and is tagged `@unvalidated` in `sources.json` with what would
  settle it.
- **There is no status column**, so every kept row exports as open. DEC publishes no
  closure state in this layer and the export does not invent one.

The `UNIT` hygiene is exactly as warned — AFP 2,293, CFP 312, hundreds of per-county
state-forest codes, blanks and misspellings — and it stopped mattering, because nothing
filters on where a trail is (§1). Two of DEC's rows are somebody else's route and are
suppressed by the route-owner rule rather than by anything DEC-specific: 61 named
`Long Path` (NYNJTC's) and 1 named `Appalachian Trail` (ATC's). **What was still
unregistered when this section was written:** Back Country Features (21,466 points),
Trailheads (10,524) and the 314 lean-tos.

**Since 2026-08-27 (#1097), two of those three ship.** The lean-tos are registered as
`dec_lean_tos`, and Back Country Features as `dec_backcountry_features` — the latter
through a value allowlist for exactly two types (privy and crossing) rather than as a POI
layer, because 68% of it is assets no hiker wants a pin for. **Trailheads are the one that
stayed out.** §10(g)'s water question was answered rather than inherited: no water ships
from any DEC layer, and `sources.json`'s `dec_water_holdback` carries the measurement that
made it a refusal rather than a gap.

**Surveyed properly 2026-08-27** ([POI_COVERAGE_SURVEY.md](POI_COVERAGE_SURVEY.md), #1092),
and the three lines above understate what is there in one way and overstate it in another.
Back Country Features is not a POI layer: DEC's own description calls it "assets on state
lands… man-made items, which require periodic maintenance or inspection", its largest
single asset type is `CULVERT` (4,290), and 68% of it is things no hiker wants a pin for.
Inside it, though, are **331 shelters, 2,315 backcountry campsites, 393 privies, 2,256
parking areas, 248 viewpoints and 1,182 crossings** — six of the eight `POI_TYPES`, and
more backcountry campsites than any other source in the registry. The `PUBLICUSE` flag
splits the layer 7,645 Y / 13,823 N, and **DEC republishes the Y slice as small per-type
services** (`dil_land_assets_lean_to` is 315 against 315, `_prm_cmp` 2,078 against 2,078 —
four exact matches of seven checked), which is what to register rather than the big layer.
§10(g)'s water question is answered in the same place, and the answer is no.

## 4. NYNJTC — a public shelf bigger than the A.T. survey knew, and still an agreement

Org confirmed: `nynjtc.maps.arcgis.com`, "New York-New Jersey Trail Conference", org id
`G1WTEJ6UVRUTvh9C`, **70 public items** (SOURCE_SURVEY.md §5 knew of the Long Path extract;
the shelf is broader):

- **Long Path** — item "Long Path - 2025 Fall", service
  `services7…/Long_Path_2023/FeatureServer/0` (the layer inside is named `Long_Path_2025Sep`:
  NYNJTC updates the *same service in place* each season, which is exactly the property a
  registry URL wants). **43 segments**, fields `Trail_Name`/`Blaze`/`Maintainer`/`Mileage`/
  `LP_Section`/`GuideURL`, `editingInfo` **2026-08-04** — fourteen days before this survey.
- **Highlands Trail** — item "Highlands Trail in NY & NJ - Fall 2025", service
  `NYNJTC_HighlandsTrail2021sections/FeatureServer/0`: **12 sections**, thinner schema
  (`Trail_Name`/`Section_Name`/`Source`), edited 2025-12-04.
- **Long Path_Shawangunk Ridge Trail**, **Long Path: Seasonal Routes**, and a live
  **Long Path Minnewaska Fire Detour** — the last one is a *conditions* artifact: NYNJTC
  publishing a reroute as data, which is the shape ATC_TRAIL_UPDATES.md wishes ATC used.
- **Catskill layers to treat with care:** `Cat_Trailless2023` and "Catskill Informal Trails
  Survey" are surveys of *unofficial* trails. **NEEDS REVIEW — do-not-ship posture:**
  publishing informal-trail locations is the land-manager-relations hazard SOURCE_SURVEY.md
  §3b documents for CSI's user-created campsites, and the same editorial holdback applies.
- **Terms: unstated everywhere** — both trail items have empty `licenseInfo` and
  `accessInformation`. Public ≠ licensed; the maintainer's NYNJTC conversation (in motion,
  #768) covers the extracts and the network both.
- **The full network stays withheld**, and SOURCE_SURVEY.md §10's verdict stands verbatim:
  *an agreement, not a scrape*. When it lands it arrives through [#100](https://github.com/OurHike/OurHike/issues/100)'s
  staging models like every other source.

**Verdict: register the Long Path and Highlands Trail services now** (review-only until the
conversation concludes), and treat the fire-detour layer as the first candidate for a
non-ATC conditions source.

**Acted on 2026-08-24** ([#950](https://github.com/OurHike/OurHike/issues/950)): both are in
`sources.json` as `nynjtc_long_path` and `nynjtc_highlands_trail`, review-only
(`reaches_hikers: false`) behind a new `nynjtc_licence` block. Re-probing them that day
found the shelf exactly as this section left it on 2026-08-18 — 43 sections and 12, the
same field lists, `dataLastEditDate` still 2026-08-04 and 2025-12-04 — so nothing here
needed correcting, which is worth recording because a snapshot that is never re-read is a
snapshot nobody knows the age of. Two things the survey did not say, found on the re-probe
and now carried in the entries themselves: the Long Path's `Blaze` is a **plain string with
no coded domain** (all 43 rows read the lowercase `aqua`), and the Highlands Trail layer
**publishes no blaze field at all**, which is registered as the neutral rather than as the
teal it wears on the ground. The fire-detour layer is still unregistered.

## 5. New Jersey — two real layers, and the first stated terms in this survey

- **NJDEP "NJ State Park Service Trails"** (`mapsdep.nj.gov/…/Features/Land/MapServer/63`,
  owner NJDEPBGIS): **3,305 segments** with the richest blaze schema surveyed anywhere in
  this project — `TRL_COLOR`, `ALT_TRL_COLOR`, `PBN_COLOR`, `BLAZE_TYPE` ("Painted Blaze"),
  `BLAZE_DESC`, `TRL_DIFF` difficulty, surface, ADA access, per-use flags. Ring coverage
  proven: Otter Hole Trail (Green) at the Weis Ecology Center / Norvin Green ground NYNJTC
  maintains. On-prem, no `editingInfo`; copyright "NJDEP". A companion POI layer
  (`Land/62`, State Park Service Points of Interest) is registered in the same folder,
  count unprobed.
- **NJ Geospatial Forum "Statewide Trails in New Jersey"**
  (`services1.arcgis.com/QWdNfRs7lkPq4g4Q/…/Statewide_Trails_in_New_Jersey/FeatureServer/10`,
  item `2fa0ddfecdf74f8a8718bd3791dabdd7`): **13,296 segments**, edited **2026-06-09**,
  fields including `BLAZE_COLOR`, difficulty, per-use flags, `PARK_NAME` — and
  **`MANAGING_AGENCY`, 166 distinct values**: counties (Morris, Atlantic, Burlington…),
  boroughs, land trusts, even corporate campuses. **This one layer is the answer to the
  NJ-county question** — per-segment agency attribution instead of eight county portals.
  Its own description is honest that it is "a first iteration and in no way complete", so
  it *supplements* the NJDEP park layer rather than replacing it.
- **Terms — stated, at last:** the item carries the **NJDEP Data Distribution Agreement**
  (as-is, no warranty, no duty to maintain). This section said **NEEDS REVIEW: read the
  agreement in full before registering**, and that was done on 2026-09-09 under
  [#1293](https://github.com/OurHike/OurHike/issues/1293): 1,968 characters, quoted
  verbatim into `sources.json`'s new `njdep_licence`. **The reading, in one line: it
  permits reuse and redistribution, on three conditions, and two of them need building
  before anything can ship.** The coordinate reference system must stay intact (satisfied
  by construction); the data "may not be reproduced or redistributed without all the
  metadata provided" (this project has no surface where a hiker reads NJDEP's metadata);
  and any map must carry NJDEP's credit/disclaimer sentence **verbatim**, not a paraphrase
  (`map/credits.ts` prints names, not sentences). So both layers are registered
  `licence_basis: unresolved`, `reaches_hikers: false` — a decision waiting on the
  maintainer rather than an ask waiting on New Jersey. The agreement is stated on the
  **Forum item only**; the on-prem park layer carries `copyrightText` "NJDEP" and no terms
  at all (read live 2026-09-09), so it inherits the agreement by shared ownership
  (NJDEPBGIS), which is an inference and is recorded as one.
- **Registered 2026-09-09** as `njdep_park_trails` and `nj_statewide_trails`, with
  `reference/blaze_mapping.json` tables for both. **What they would actually route** for
  [#1290](https://github.com/OurHike/OurHike/issues/1290)'s held New Jersey hikes, probed
  the same day within ~900 m of each trailhead: the park layer reaches Mount Tammany (8
  segments incl. the Red Dot and Dunnfield Creek trails), Swartswood's Duck Pond loop (9),
  Wawayanda's Laurel Pond loop (7) and the State Line Trail (1); the statewide layer adds
  the county ground the park layer cannot see — Ramapo Valley County Reservation's Vista
  Loop (7, Bergen County) and Schooley's Mountain (61, Morris County Park Commission).
  **Neither reaches the Palisades**: the PIPC New Jersey section is absent from both, so
  that hike stays held whatever the licence decision is.
- The NJ Highlands Council's own Highlands Trail copy (owner NJHWPPC) exists; NYNJTC's is
  fresher and theirs — secondary.

## 6. The counties — thin, and honestly so

- **Westchester (probed):** a real ArcGIS server (`giswww.westchestergov.com`), whose
  `Parks` folder holds canopy imagery and land cover — **no trails service found**. The
  county trailways (North/South County, the county-run Old Croton stretch) surface nowhere
  structured that this survey found.
- **Rockland, Putnam, Orange, Dutchess (NY) — unprobed.** The maintainer has offered links
  (#770 comment); these rows wait for them rather than guessing. **NEEDS REVIEW.**
- **NJ counties:** largely answered by §5's compilation — county-managed segments arrive
  with `MANAGING_AGENCY` set, no per-county source needed for v1.

## 7. OpenStreetMap — the gap-filler, stated as a question

What only OSM plausibly covers inside the ring: trails on ground no surveyed agency
publishes (municipal preserves, land-trust properties, the informal networks), and — until
the NYNJTC agreement lands — the full detail of club-maintained systems in NJ. The costs
are the ones this project already prices for OSM water: a contributor's observation, not a
steward's record, so it renders at low confidence and its description says who mapped it.

**Deliberately unmeasured here.** "How much of Harriman/the ring does OSM know that OPRHP/
DEC/NJDEP do not" is a spatial-join measurement, and
[#771](https://github.com/OurHike/OurHike/issues/771) is the runnable place for it — this
survey declines to guess a coverage number it has not computed. The maintainer chose
outreach-plus-public-extracts as the NYNJTC path (2026-08-18); OSM-as-trail-source remains
undecided and this row is evidence-gathering for it, not the decision.

## 8. One ground, many sources — the overlap the display design inherits

The ring is where OurHike first has *multiple authoritative sources on the same ground*,
and each cell below is a place where per-field precedence
([../features/POI_DEDUPLICATION.md](../features/POI_DEDUPLICATION.md)'s combine-don't-drop
rule) will have to be argued rather than assumed:

| ground | data of record today | also true on the ground |
|---|---|---|
| Harriman / Bear Mountain | OPRHP (`Unit: Palisades`) | AT (ATC/NPS layers), Long Path (NYNJTC), PIPC administers, NYNJTC maintains |
| Hudson Highlands SP Preserve | OPRHP (`Taconic`; 24 named trails at Breakneck alone) | NYNJTC maintains most trails, publishes none of them; AT clips Anthony's Nose |
| Minnewaska / Shawangunks | OPRHP | Long Path + SRT (NYNJTC), NYNJTC's live fire-detour layer, and Mohonk Preserve's own carriage-road network (#992, ships) |
| Catskill Forest Preserve | DEC (`UNIT: CFP`) | Long Path (NYNJTC), NYNJTC's Catskill programs, 314-lean-to layer statewide |
| NJ Highlands / Ramapos | NJDEP + the statewide compilation | Highlands Trail (NYNJTC), NYNJTC maintains |
| The AT corridor through NY/NJ | ATC/NPS (already shipping) | crosses OPRHP, PIPC and NJDEP ground registered above |
| **New York City's parks** | **NYC Parks** (7,059 trail segments) | **NYC DOT's greenways** (3,030 off-street), 1,828 of them on NYC Parks land by DOT's own `gwyjuris` — and **measured 2026-09-15, this row is the only one in the table with a number**: §13 |

The steward-versus-owner distinction matters for outreach too: OPRHP's answer covers the
*data*; NYNJTC's covers the *stewardship* and the network — one does not substitute for the
other.

## 9. Licensing, summarized

No blanks, per the issue. "Unstated" is an answer; an empty cell is not.

| source | terms | state |
|---|---|---|
| NYS OPRHP (4 layers) | **Stated** — reuse permitted, attribution to OPRHP required, *non-commercial purposes*. **Corrected 2026-08-24 (#950):** this row read "Unstated; no-warranty disclaimer" because the item's `licenseInfo` was read through a 200-character truncation that cut off exactly where the disclaimer ends and the terms begin. Full text (1,095 chars) is quoted in `oprhp_licence`. | **Ask still open, on a narrower question** — not "what are the terms" but "is OurHike non-commercial within them", given features/PRICING_MODEL.md's paid passes (#769) |
| NYS DEC (`dil` layers) | Unstated; no copyright text on the service or on the hiking layer, re-read whole 2026-08-25. On-prem, so there is no AGOL item carrying terms either | **The hiking layer ships on maintainer authorisation, 2026-08-25** (#1019, `dec_licence`) — the same footing NYNJTC's and Mohonk's extracts ship on, not a stated grant. The ask is still open and is now the live one: bundle with OPRHP, one state, two agencies; Open-NY listing is precedent |
| data.ny.gov copies | No licence field on either listing | Not a source: DEC copy last updated **2013**, OPRHP copy **2014-12-24** — proof the State publishes these openly, and proof the AGOL/on-prem services are the copies of record |
| NYNJTC public extracts | Unstated — `licenseInfo` AND `accessInformation` both empty on both items, re-verified whole 2026-08-24 against the registered service URLs | Covered by the maintainer's NYNJTC conversation (#768). An absent licence is more restrictive than OPRHP's stated one, not less |
| NYNJTC full network | Withheld | **An agreement, not a scrape** (SOURCE_SURVEY.md §10, reaffirmed) |
| NJDEP layers + NJ compilation | **NJDEP Data Distribution Agreement — stated** | **NEEDS REVIEW** — read in full; possibly no ask needed |
| ATC / NPS | See `atc_licence` in sources.json | In hand |
| OpenStreetMap | ODbL 1.0 | In hand (basemap + water precedent) |
| Mohonk Preserve (trails layer) | Unstated — no-warranty disclaimer only, no reuse grant, read whole 2026-08-25 | **Ships on maintainer authorisation, 2026-08-25** (#992) — the same footing NYNJTC's extracts ship on, not a stated grant |
| **New York City (Parks + DOT)** | **Stated, and by STATUTE** — NYC Local Law 11 of 2012, Admin Code §23-502(d): published data sets are available "without registration requirement, license requirement, or usage restrictions". Read 2026-09-15 from the City's own Open Data Technical Standards Manual, which quotes the law. Neither dataset page carries a licence field — and here that silence means the statute applies, the opposite of what it means on DEC's or Mohonk's services | **Ships, 2026-09-15** (#1432, `nyc_licence`). The only row here needing no ask: a statutory grant to everyone, not a permission to this project. One rider is open — the City "may require" a republisher to identify the source, **version and modifications**, and only the first is built | 

## 10. What to do with all this, ranked

1. **Register DEC** — `external_arcgis_layer` entries for the hiking layer, backcountry
   features, trailheads and lean-tos; the `max(UPDATED)` statistic recorded as the
   freshness marker. No new fetch code needed. **The hiking layer is done** (2026-08-25,
   #1019, §3) and needed no fetch code, as predicted; the three POI layers are not, and the
   `max(UPDATED)` marker is recorded in the entry's notes rather than wired to anything —
   nothing reads a freshness marker for an external layer today, so `fetch_external_layers.py`
   re-fetches DEC on every run.
2. **Register NYNJTC's Long Path and Highlands Trail services** — public, fresh, stable
   URLs; review-only until the conversation concludes.
3. **Read the NJDEP Data Distribution Agreement**, then register the two NJ layers.
4. **Run the spike** ([#771](https://github.com/OurHike/OurHike/issues/771)) on OPRHP +
   Long Path over Harriman/Hudson Highlands — it also owns the OSM coverage measurement
   this survey deferred (§7).
5. **NEEDS REVIEW, gathered:**
   - (a) The maintainer's county links (#770 comment) — Westchester found nothing
     structured; the other NY counties are unprobed.
   - (b) ~~**Long Island: in the ring or out?** §1's open edge.~~ **Dissolved 2026-08-25**
     (#1019): there is no ring, so the question stopped being one — see §1. Long Island's
     2,058 OPRHP segments ship.
   - (c) **Bundle DEC into the OPRHP ask** — one state, two agencies, Open-NY precedent
     for both. **Still open, and now the live one rather than the tidy one**: DEC's trails
     reach hikers as of 2026-08-25 on the maintainer's authorisation (#1019, `dec_licence`),
     which is a decision taken in the absence of DEC's terms rather than a grant from them.
   - (d) **NJDEP Data Distribution Agreement** — full text unread.
   - (e) **NYNJTC's informal-trails layers are a do-not-ship hazard** — the §3b posture
     from the A.T. survey, applied here before anyone fetches them.
   - (f) **PIPC's NJ section** — expected inside the NJ layers, unverified.
   - (g) Whether DEC's Back Country Features asset types include **water** — raises the
     evidence bar if true (CLAUDE.md's four ways). **Both halves are now answered, and
     they answer differently** — [POI_COVERAGE_SURVEY.md](POI_COVERAGE_SURVEY.md) §3,
     measured 2026-08-27 by `spike_org_poi_coverage.py`. **DEC's half is no.** Its only
     plumbed-water asset type is `WATER SUPPLY SYSTEM`, 23 features, **zero of them
     flagged `PUBLICUSE='Y'`** — DEC's own answer is that none of it is for visitors — and
     the 350 features whose names merely sound like water are worse: 207 `WATERHOLE` are
     fire-and-wildlife impoundments, 97 `WELL` are dominated by natural gas wells, 19
     `SPRING` include one "Unnoffical Unsanctioned" and one "Untested", and one sampled
     drilled well's own notes read "Not Approved For Human Consum[ption]". So DEC is not a
     water source, and that verdict is pinned by `tests/test_poi_coverage.py` rather than
     left to review. **OPRHP's half is yes** — measured live 2026-08-27:
     `NY_State_Park_Facilities`'s `Sub_Asset` holds **136 `Water Spigot` and 15
     `Drinking Fountain`** among 158 distinct values (`Mineral Spring`, `Water Tower`
     and `Waterfall` also appear and are *not* drinking water). So that layer is a
     water source, the evidence bar is live rather than hypothetical, and shipping it
     needs `export_poi.py`'s confidence-and-provenance treatment rather than a point
     dump. Carried in the `oprhp_facilities` entry. A second hazard found with it:
     `Asset` is a coded integer 1–17 whose domain the service does not publish, so a
     facility's type is legible only through `Sub_Asset`'s free text.
   - (h) **Mohonk Preserve's own stated terms** — still the ideal, per its licence
     block's open question; ships today on maintainer authorisation (#992). §11.

## 11. Mohonk Preserve — found after this survey, filling a real gap

Not in this survey's original 2026-08-18 pass: Mohonk Preserve is a ~8,200-acre nonprofit
nature preserve immediately adjacent to and interleaved with Minnewaska (§8's overlap
table already listed OPRHP and NYNJTC on that ground; Mohonk Preserve, a distinct
landowner with its own carriage-road network, was never surveyed as its own source).
Registered 2026-08-25 (#992):

- **Service:** Mohonk Preserve's own public AGOL org (id `cQ05sucxF4UWabFF`), item
  `88014aef85ef42c397c738154cf7f1dc`, owned directly by their GIS & Land Projects Manager.
  `Trails_CarriageRoads/FeatureServer/0` — **304 polyline segments**, fields
  Name/General_Classification/Classification/Use_/Blaze/Mileage/Surface/Owner/Manager.
  The layer is already a filtered VIEW (`definitionQuery`: classification in Carriage
  Road/Trail, `Manager = 'Mohonk Preserve'`) — Mohonk's own curated public extract, not
  their raw internal dataset. 298 of 304 rows carry `Owner: Mohonk Preserve`; six
  (Marakill Woods) carry `Owner: NYS OPRHP/PIPC` with `Manager` still Mohonk Preserve.
- **Freshness, measured the way this survey measures it elsewhere:**
  `editingInfo.dataLastEditDate` read live 2026-08-25 as **2026-08-24T20:52:57Z** —
  edited the day before. The AGOL item's own container metadata (title/sharing) last
  changed 2025-07-28, a full year stale by comparison — reading only the item, not the
  layer, would have understated how current this source actually is.
- **The candidate actually suggested** (`gis.ny.gov/gisdata/inventories/
  details.cfm?DSID=295`, the old NYS GIS Clearinghouse listing) **is dead
  infrastructure**: 404 on the detail page and on the bare inventory path, which
  301-redirects to `data.gis.ny.gov` — the whole ColdFusion inventory system has moved,
  with no working listing for this dataset found on the replacement. Worth recording
  here because it is this survey's own rule 3 in miniature: finding a live,
  actively-edited service instead of trusting a page's own claim about itself is the
  discipline every other row in this document was already held to.
- **Licence — unstated**, the same shape as NYNJTC's extracts before their maintainer
  authorisation. Read whole rather than through the 200-character truncation that
  misread OPRHP's once (§9): the item's `licenseInfo` is a no-warranty disclaimer only,
  no reuse or redistribution grant either way. The maintainer authorised shipping this
  public extract on 2026-08-25 — `mohonk_licence` in sources.json holds both the
  verbatim text and that authorisation, on the same footing `nynjtc_licence` already
  uses.

**Verdict: registered, ships** (`reaches_hikers: true`, maintainer authorisation
2026-08-25) — fetched by the existing `fetch_external_layers.py` and exported by the
existing `export_nearby_trails.py` with no code change to either: `blaze_field`/
`name_field` on the registry entry are all `network_line_sources()` needed to pick it
up. Verified live 2026-08-25: all 304 features kept (no ring/status/foot filter drops
anything — Mohonk Preserve is well inside the ring and the entry declares neither a
status nor a foot-use field), blaze resolution 297 mapped / 7 absent (the null-Blaze
rows) / zero unmapped against `reference/blaze_mapping.json`'s new `mohonk_trails`
table, and `client/src/map/credits.ts`'s `MOHONK_CREDIT` joins `OPRHP_CREDIT`/
`NYNJTC_CREDIT` on the shared `nearby_trails` map source.

## 12. New York City itself — the hole in the middle of this survey

Everything above is ground you reach by leaving the city. The five boroughs had **no row
in this document at all**, which is a strange gap in a survey named for New York City, and
the repository already carried the evidence of it: `reference/nynjtc_hike_routes.json`
holds a NYNJTC day hike that could not be routed, with the reason recorded as *"Van
Cortlandt Park, NYC Parks: only one Old Croton Aqueduct edge within 2.5 km; no source
registered for NYC Parks (pipeline/NYC_SOURCE_SURVEY.md)"*. Three sibling holds name
Rockland and Westchester county parks for the same reason (§6). This section closes the
NYC one.

Added 2026-09-15 under [#1432](https://github.com/OurHike/OurHike/issues/1432), from the
maintainer's own ask — they live in the city and can field-test there most easily, which
makes NYC the cheapest ground this project has for turning `needs-field-testing` into
somebody actually walking outside. **Every figure below was read live from the portal that
day.**

### 12a. The city publishes on Socrata, and its ArcGIS mirrors are dead

This is the finding that shaped the registration, and it is §9's "data.ny.gov copies —
precedent, not a source" meeting a second city.

New York City's open-data programme runs on **Socrata** (`data.cityofnewyork.us`), not
ArcGIS Hub — the opposite of New York State, whose agencies gave this project every source
in §§2–5. Every entry in `sources.json` before this one was an ArcGIS layer.

The obvious shortcut is to find an ArcGIS copy and register that instead, and one exists:
NYC DCP mirrors DOT's bike network at
`services5.arcgis.com/GfwWNkhOj9bNBqoJ/…/Bike_Routes/FeatureServer/0`. Probed live:

| | portal (`mzxg-pwib`) | DCP's ArcGIS mirror |
|---|---:|---:|
| rows | **29,695** | 13,953 |
| last edited | **2026-07-24** | **2017-03-08** |
| `grnwy` / `gwsystem` / `status` | present | **absent** |

Nine years stale, less than half the rows, and — decisively — **no greenway column at
all**, so the mirror cannot express the one filter that separates a walking path from a
bike lane in traffic. NYC Parks has no ArcGIS org publishing trails either (AGOL searched
2026-09-15; owner-scoped search returns zero items).

So the portal is the publication of record, and registering NYC meant a **new source kind
and a fetcher** — `socrata_geojson_layer` and `lib/socrata.py` — rather than a new URL.
That is a real cost and it bought a real thing: the two layers below, and any future city
that publishes this way.

### 12b. NYC Parks Trails — 7,059 segments, 73 parks

Dataset `vjbm-hsyr`, attributed to the Department of Parks and Recreation, refreshed
**2026-09-03** on a declared monthly automation.

The twelve largest parks, by segment count: **Pelham Bay 766, Van Cortlandt 663, Alley Pond
516, Prospect 376, Central Park 312, Forest Park 268, Inwood Hill 252, Wolfe's Pond 251,
Cunningham 242, Marine Park 218, Clove Lakes 213, LaTourette 168.** Van Cortlandt's 663 are
the direct answer to the held hike above.

**Its own description understates it,** which is this survey's rule 3 in miniature — the
reason every count here was read from the data rather than from the page. The description
says *"paths or trails in designated Forever Wild areas"*; Central Park and Prospect Park
are neither Forever Wild nor absent, and are the fourth and fifth largest parks in it.

**That paragraph was a count and it got read as coverage**, which
[#1530](https://github.com/OurHike/OurHike/issues/1530) opened on and this correction
answers. 312 segments is a big number and 6.98 miles is not. Measured 2026-09-16 by
`spike_central_park_paths.py`, clipping this layer to NYC Parks' own boundary polygons:

| park | segments | miles inside the boundary | acres | mi/acre | of its own paved walkway |
|---|---:|---:|---:|---:|---:|
| Central Park | 312 | **6.98** | 839 | 0.0083 | **10–17%** |
| Prospect Park | 376 | 14.32 | 478 | 0.0299 | 48–80% |

**A factor of 3.6 out of one layer surveyed by one steward**, which is what makes this a
fact about Central Park rather than about the dataset — and the reason Prospect Park is the
right control and not merely a second example. The walkway column is an independent check
against the city's planimetric sidewalk polygons (`52n9-sdep`): 80.7 acres of paved surface
inside Central Park, 35.4 inside Prospect, divided by an assumed 3–5 m width. That band is
picked rather than surveyed — `@unvalidated`, and the spike's `WALKWAY_WIDTH_BAND_M` says
what would settle it — but it does not need to be precise to separate a tenth from a half.

So **the description was closer to right than this survey gave it credit for.** What the
layer holds in Central Park is roughly its Forever-Wild-shaped corners — the Ramble, the
North Woods, the Hallett sanctuary — plus paved fragments. *Not absent* and *covered* are
different claims, and only the first one was ever checked here.

Where the rest of the park is, and what it would cost, is §12f; the decisions it raises are
[#1533](https://github.com/OurHike/OurHike/issues/1533).

Three things the registration carries that a reader should know before trusting a line:

- **There is no blaze field, and the colour is in the name.** `trail_name` reads `Blue
  Trail` 549 times, `Orange Trail` 326, `White Trail` 251, `Red Trail` 215, `Yellow Trail`
  153. The only marker column, `trailmarkersinstalled`, is a plain Yes/No (4,017/3,042) —
  *whether* a marker exists, never which. Registered as the neutral, the same as
  `nynjtc_highlands_trail`: a colour parsed out of a name is **our** claim, not NYC Parks',
  and a hiker matching a painted blaze against a drawn one cannot tell those apart. The
  honest version, if wanted, is a reviewed `blaze_mapping.json` table, not a regex in an
  exporter.
- **Half of it has no name, and the placeholders are registered as such.** `Unnamed
  Official Trail` 3,448, `Name TBD` 239, `TBD` 88 — 3,775 rows, **53%**, carrying a
  placeholder in a column that cannot be empty. The entry declares them in
  `name_placeholders` and the exporter reads them as an **absent** name, which is
  CLAUDE.md's "absent means unknown" applied to a steward's own idiom. That is not
  cosmetic: measured live, `Unnamed Official Trail` totals **128.7 miles**, past
  `NAMED_TRAIL_THRESHOLD_MILES`, so untreated it shipped as *one* overview feature named
  "Unnamed Official Trail" with `through_route: true`, drawn at through-route weight across
  five boroughs beside the Appalachian Trail and labelled that on the map. `park_name` is
  populated on every row and is the usable label for these.
- **The portal publishes no feature id, so the fetch asks for one.** A Socrata GeoJSON
  feature carries no `id` member and no id-shaped property, which drops every row onto
  `lib/feature_id.py`'s positional `generated-{index}` — an id that renumbers when NYC
  Parks inserts a segment, silently re-pointing anything keyed on a line id at the next
  publish. `$select=*,:id` returns Socrata's stable row key (`row-6p7c_bcx9.in7u`), and
  `lib/socrata.py` promotes it. Measured before and after on the two layers: 10,089
  warnings, then none.
- **The dataset's freshness and the survey's freshness are different numbers, and the
  second is the one on the ground.** `date_collected` runs 2013-10-17 to 2026-08-18:

  | 2013 | 2014 | 2015 | 2016–2020 | 2021 | 2022–2024 | 2025 | 2026 |
  |---:|---:|---:|---:|---:|---:|---:|---:|
  | 1,594 | 2,198 | 990 | 312 | 773 | 489 | 644 | 55 |

  **4,782 of 7,059 segments — 68% — were last surveyed in 2013–2015**, and every sampled
  Central Park row is from 2014. A monthly refresh of a file whose rows are twelve years
  old is a fact about the file, not about the trail. CLAUDE.md's *never let a display
  outrun its source* is the rule that bears on it, and nothing in this build currently
  shows a hiker that distinction.

### 12c. NYC DOT greenways — 3,039 of 29,695, and the filter is the point

Dataset `mzxg-pwib`, refreshed **2026-07-24**. It is DOT's entire bicycle network, and the
overwhelming majority of it is painted lanes in traffic. Three clauses cut it down:

| clause | drops | what that is |
|---|---:|---|
| `status='Current'` | 5,234 | retired facilities the dataset keeps as history — trail drawn where there is none |
| `grnwy='Greenway'` | 23,358 | ordinary bike lanes with no greenway designation |
| `onoffst='OFF'` | 2,322 | **current greenway-designated segments that run *on street*** |

**3,039 survive the filter and 3,030 of them ship** — nine carry a geometry object whose
coordinates are empty and are dropped by the exporter's own `no geometry` rule. Worth the
extra sentence because the first version of this section said "not one null geometry",
which is true and still hides those nine. The last clause is the one a hiker's safety turns on and the reason the
greenway flag alone is not enough: those 2,322 are the on-street connectors that link one
off-street greenway to the next — signed as part of the route, and carrying a walker into
traffic. Some are certainly pleasant to walk; dropping them is the acceptable false
negative, and *miss rather than cry wolf* is the standing rule.

What ships, by named system: Manhattan Waterfront 1,167, Jamaica Bay 799, Brooklyn
Waterfront 690, Central Queens 614, Staten Island Waterfront 340, Historic Brooklyn 304,
Queens Waterfront 302, Bronx River 243, Bronx Waterfront 233, Mosholu-Pelham 194,
Hutchinson River 144, Eastern Queens 126 *(counts over the 5,361 current greenway rows,
before the off-street clause, so they do not sum to 3,039)*.

**Why a bicycle dataset is registered at all**, against the maintainer's decision of
2026-08-18 — *"Only keep hiking trails for now… It's OurHike, not OurBike"* — is worth
stating rather than hoping past. That decision was taken over per-use flag columns, where a
row flagged BIKE and not FOOT is a mountain-bike trail: a different use of a different
tread. This is not that. An off-street greenway is a **shared-use path** that people walk
and run on in far greater numbers than they cycle, and DOT catalogues it inside a bicycle
dataset because DOT's mandate for building it was a cycling one. The subject is the path.

**Where the inference is, and it is real:** this layer has *no* foot-use column. Nothing in
it says a person may walk a given segment, and `onoffst='OFF'` is being read as "car-free,
therefore walkable". That is ours, not DOT's, and is tagged `@unvalidated` in
`sources.json`. What would settle it: the NYC Parks layer covers the same ground for the
2,095 greenway segments whose jurisdiction is DPR and would corroborate directly — a
spatial join nobody has run — or a maintainer who lives in the city walking one and saying.

### 12d. Licensing — the first statutory grant in this registry

Every other non-ATC source in this project is unstated (DEC, NYNJTC, Mohonk), conditioned
(NJDEP) or restricted (OPRHP's non-commercial clause, still an open ask). New York City is
none of those.

**NYC Local Law 11 of 2012**, codified at Administrative Code **§23-502(d)**, requires that
a published data set be available *"without registration requirement, license requirement,
or usage restrictions"*. That is a grant made **by statute to everyone**, not a permission
granted to this project — so it needs no ask, cannot be withdrawn by an agency editing a
portal field, and does not need re-confirming in its own name by a club that inherits this
project.

Read 2026-09-15 from the City's own **Open Data Technical Standards Manual**, which quotes
the law. Neither dataset page carries a licence field of its own — and *here* that silence
means the statute applies, which is the exact opposite of what the same silence means on
DEC's or Mohonk's services.

Two riders travel with it:

- **Attribution.** The City may require a republisher to *"explicitly identify the source,
  version, and modifications made to a public data set"*. **Source is satisfied** —
  `credits.ts` puts both agencies in the map corner. **Version and modifications are not**:
  this app has no surface where a hiker reads which vintage of a layer they are looking at,
  and the greenway layer ships modified in a way the map cannot show (3,039 of 29,695).
  `njdep_licence` records the same shape of gap and holds New Jersey back over it; **this
  one ships instead, and the difference is in the texts, not a change of posture** —
  NJDEP's agreement says data *"may not be reproduced or redistributed without all the
  metadata provided"*, a precondition on the act, where the City's says OTI *"may require"*
  identification, a reserved power nobody has exercised. `@unvalidated`: nobody has asked
  OTI. If the answer is yes, the fix is the stewards artifact.
- **No warranty.** *"The City does not warranty the completeness, accuracy, content, or
  fitness for any particular purpose or use of any public data set."* Boilerplate
  everywhere except on the paths CLAUDE.md's four ways name — and relevant on one of them
  here, given 12b's 2013 survey dates.

### 12e. What is still open

- **(a) ~~The two city layers overlap, and nobody has measured it.~~** **Measured
  2026-09-15 (#1453) — §13.** It is real, it is systematic, and it is a quarter of the
  ground: 23.6% of the mileage DOT records on NYC Parks land runs within 25 m of a NYC
  Parks trail, against 0.9% for the greenways elsewhere. What to *do* about it is still
  open, and §13 says why the mechanism that already exists declines to.
- **(b) The version-and-modifications rider**, above. An ask to OTI settles it.
- **(c) Walkability on the greenways is inferred**, not declared — 12c.
- **(d) The blaze colours in `trail_name` are unparsed** and 1,494 segments carry one. A
  reviewed mapping table is the honest route if they are ever wanted. Note this interacts
  with the placeholder rule above: the colour-named rows are exactly the ones that *do*
  carry a real name, so nothing here is lost by treating the placeholders as absent.
- **(f) NYC Parks publishes no use column at all** — no FOOT/BIKE/HORSE matrix — so no
  foot filter is possible, and the entry keeps every row. That is a widening of
  `export_nearby_trails.py`'s keep-everything default, whose stated justification ("a
  source with no use flags at all keeps every row, because NYNJTC and Mohonk publish
  hiking trails and nothing else") does not describe a municipal layer with 198
  bridle-named rows and 2,174 fully-paved ones. Every row is still walkable on foot, which
  is why it is right anyway — but for a different reason than the default's, and the entry
  says so rather than inheriting it quietly.
- **(e) Nothing here is field-checked.** This is the section of the survey whose ground the
  maintainer can actually stand on, which is the whole reason it exists — Van Cortlandt and
  Pelham Bay are a subway ride, and a single afternoon would settle (c), (d) and the 2013
  survey dates in 12b better than any amount of further probing.
- **(g) Central Park is a tenth drawn**, 12b's corrected table, and §12f is where the rest
  of it lives.

### 12f. The rest of Central Park, and the rest of the city — CSCL registered (#1530, #1533)

12b establishes the hole: 6.98 miles drawn inside an 839-acre park whose own paved walkway
implies 41–68. This section is what fills it. It began as a survey of two unregistered
candidates; the maintainer took all three of its decisions on 2026-09-17 and **two of them
are now registered entries**, so what follows is what shipped and on what evidence.

#### The data dictionary, which turned a reading into a quotation

§12f's first draft tagged `rw_type='6'` `@unvalidated` and said reading NYC's published
definition was what would settle it. **It is published, and it is settled.** Not on the
column descriptions, which are empty, and not at NYC Planning's PDF URL, which answers 403
— it is an **attachment on the dataset itself** (`Centerline.pdf`, assetId
`4cff63bb-aeb0-4ca3-adb5-d6027dc133d5`), reachable through Socrata's own file endpoint.
Quoted:

> `RW_TYPE` — 1 Street, 2 Highway, 3 Bridge, 4 Tunnel, **5 Boardwalk**, **6 Path/Trail**,
> **7 StepStreet**, 8 Driveway, 9 Ramp, 10 Alley, 11 Unknown, 12 Non-Physical Street
> Segment, 13 U Turn, 14 Ferry Route
>
> `TRAFDIR` — FT With, TF Against, TW Two-Way, **NV Non-Vehicular**
>
> `STATUS` — 1 Planned Private, **2 Constructed**, 3 Paper, 4 Under Construction,
> 5 Demapped, 9 Paper Street Coincident with Boundary

The lesson generalises past this layer and is worth carrying: **a Socrata dataset can
publish its dictionary as an attachment**, and `api/views/<id>.json`'s `metadata.attachments`
is where to look before concluding a vocabulary is undocumented. `nyc_drinking_fountains`'
own dictionary link is dead (`nyc_water_holdback`), so this is not a rule — but it is a
place to check that this survey had not checked.

#### `nyc_cscl_paths` — the three pedestrian classes, 6,498 rows citywide

`status='2'` and `rw_type` in 5/6/7, plus a fourth clause below. **Registered and shipping**,
on the maintainer's decision of 2026-09-17 taken with the counts in front of them.

| class | rows | what it is |
|---|---:|---|
| 6 Path/Trail | 5,990 | the park and greenway network — 3,041 names ending in PATH, 1,023 GREENWAY, 250 LINK, 197 TRL, 129 WALK, 71 ESPL, 61 TRAIL |
| 7 StepStreet | 246 | the Bronx and upper Manhattan public stairways, plus 40 rows named PEDESTRIAN PATH — on some hillsides the only pedestrian route there is |
| 5 Boardwalk | 101 | Coney Island, Rockaway, Orchard Beach, Jacob Riis, the Manhattan Beach promenade |
| 1 Street, doubly non-vehicular | 162 | see below |

Inside Central Park this is **13.75 miles across 172 features, of which 13.29 — 97% — lie
more than 25 m from anything the build already drew**. Not §13's question arriving a third
time: not the same tread digitised twice, but path nobody had. BRIDLE PATH 3.01 mi,
RESERVOIR LOOP 1.59, N MEADOW PATH 1.58, BRIDLE PATH W 1.52, HECKSCHER BALLFIELDS PATH 1.29.

**It is not a Central Park fix, which is why it went in citywide.** The same clip over
Prospect Park returns 0.67 miles — because NYC Parks' own layer already covers Prospect at
96% of the two layers' combined mileage. This layer is thick exactly where that one is thin,
and neither substitutes for the other.

**The fourth clause needed a second witness.** `trafdir='NV'` is the city's own
non-vehicular assertion, and alone it is 580 rows that cannot be trusted: **119 of them
carry a posted speed**, which contradicts the assertion, and the names include HILLSIDE AVE,
W END AVE and REID AVE. Requiring `posted_speed` **and** `number_travel_lanes` to be absent
as well cuts it to 162, and what survives reads right — CENTRAL PARK GREAT HL 19, OCEAN PROM
15, UNION TURNPIKE PED AND BIKE PATH 13, BRUCKNER BOULEVARD BIKE PATH 11, CHERRY HILL PATH 4,
COLUMBIA STREET ESPL 2, BAYONNE BR PED AND BIKE PATH 2. **Two independent assertions
agreeing is the bar**, and one of them alone was measured not to clear it.

#### `nyc_park_drives` — 12.02 miles, and the one place a display outruns its source

The maintainer's second decision was the car-free park drives, **excluding Central Park's
transverses in as many words**, and then: *"I really want every park. Cant you help figure
out which onces are driveable and exclude?"*

**The mechanical answer does not exist, and that is the finding.** Everything that could
have supplied it was tried:

| tried | result |
|---|---|
| CSCL `trafdir='NV'` inside a park | **3.59 miles across 14 parks** — and **none of Central Park's four drives**, against **61.58 miles** of park-interior street the city marks vehicular |
| CSCL `posted_speed` / `number_travel_lanes` | EAST DR reads **20 mph, one travel lane**; WEST DR 25; TERRACE DR 25 with three lanes — CSCL still models the drives as vehicular streets |
| `nyc_dot_greenways` | carries none of these drives |
| Open Streets (`uiay-nctu`, 391 rows) | a **per-day schedule** of temporary closures on ordinary streets — reading a Sunday-morning closure as a walkable path would be worse than omitting one |

So **no NYC dataset says which park drives are car-free**, and the entry ships a reviewed
list of ten street names in two boroughs instead: Central Park 6.61 mi (EAST DR 2.90, WEST DR
2.73, CENTER DR 0.58, TERRACE DR 0.40) and Prospect Park 5.41 mi (WEST DR 1.96, EAST DR 1.46,
CENTER DR 0.68, WELLHOUSE DR 0.60, S LAKE DR 0.48, E LAKE DR 0.11).

**This entry contradicts its own source, and the registry says so in its own note.** Both
parks' drives closed to cars in 2018 and the street file has not caught up. The evidence is
**the maintainer's decision of 2026-09-17**, recorded as that — somebody who lives in the
city and named this park as the ground they can test on (#1432). `@unvalidated` against any
published document: the city's own pages answer 403 from an agent sandbox, so nobody here has
read a primary source saying these are car-free. What would settle it is a DOT or NYC Parks
page cited by URL and date, or a CSCL republication setting these rows to `NV`.

**A name list alone was measured to be insufficient**, which is why `boundary_source` exists
on the entry. Queens has its own EAST DR, WEST DR and CENTER DR in Flushing Meadows — hence
the borough clause — and even within the right borough four of the ten names run on past the
park edge: Brooklyn EAST DR by 0.30 mi over 7 segments, Manhattan TERRACE DR by 0.03,
Brooklyn WEST DR by 0.02, Brooklyn CENTER DR by 0.04. Small, and on a safety path a tenth of
a mile of city street drawn as a car-free park drive is exactly the failure the entry exists
to avoid. `export_nearby_trails.load_boundary` does the final cut against NYC Parks' own
polygons, and `keep_reason` drops what falls outside.

**Why every other park is out**, which was the maintainer's actual question. A rule admitting
any street inside a park boundary takes **61.58 miles across 79 parks**, and the measurement
says what that buys: Pelham Bay's ORCHARD BEACH BUS TERMINAL LOOP and ORCHARD BEACH ROAD,
Bronx Park's JUNGLE WORLD RD and BOTANICAL GARDEN RD (zoo and botanical-garden service roads),
Flushing Meadows' SHEA RD and MERIDIAN RD, Forest Park's FOREST PARK DR, Highland Park's
HIGHLAND BLVD. **Those carry cars**, and a hiker walked onto one is CLAUDE.md's third way
this app can hurt somebody. Adding a park is one reviewed row plus its measurement, and the
entry is built so that is cheap.

#### Still open

- **The walkway polygons.** `52n9-sdep` holds 80.7 acres of paved surface inside Central Park
  (35.4 inside Prospect) — the whole network, in the wrong shape. Centerline extraction is
  something this pipeline has never done, and it is the one decision of the three that was
  not taken.
- **The greenway overlap.** 1,023 of the 5,990 `rw_type='6'` names end in GREENWAY, so
  `nyc_cscl_paths` and `nyc_dot_greenways` plainly describe some of the same tread.
  `duplicate_of` takes one senior key and this entry spends it on `nyc_parks_trails` — and
  that choice is now measured rather than argued. From the export's own dedupe line,
  2026-09-17: the parks pair removes **698 records, 71.3 miles**, against the greenway pair's
  427 and 30.4. The larger of the two by both counts, which is what the guess was. **The
  greenway pair remains unmeasured** — §13's shape, a third time.
- **Nobody has walked one.** The same `(e)` that closes §12e, and it bears hardest here: the
  drives entry rests on a decision rather than a document.

`spike_central_park_paths.py` is the measurement behind every figure above and is re-runnable.

## 13. The two city agencies do draw the same tread — a quarter of it (#1453)

§8's table has always been a list of places where *"per-field precedence will have to be
argued rather than assumed"*, and every row of it was an assertion with no number behind
it. New York City is the first row that can be measured, because it is the first where one
city's **two agencies** catalogue the same path and one of them says so in a column: NYC
DOT's `gwyjuris` records which greenway segments sit on NYC Parks land.

`spike_nyc_overlap.py` is the measurement and is re-runnable. Run 2026-09-15 against the
two fetched layers, asking what fraction of each greenway segment's length has **both**
endpoints within a radius of any NYC Parks trail vertex:

| radius | `gwyjuris: DPR` (1,828 segments, 124.1 mi) | control — every other jurisdiction (1,211 segments, 56.6 mi) | ratio |
|---|---|---|---:|
| 10 m | **17.7 mi shared (14.3%)**, 269 segments at least half covered | 0.1 mi (0.2%), 4 segments | **67×** |
| 25 m | **29.3 mi shared (23.6%)**, 423 segments at least half covered | 0.5 mi (0.9%), 16 segments | **25×** |

**The control is what makes this a finding rather than an observation about a dense city.**
New York will put *something* near everything, so an overlap figure alone proves nothing.
The greenways DOT records on its own, NYSDOT's, NPS's, RIOC's and MTA's share the city's
density and none of its land-management overlap — and they sit at 0.9%. The DPR figure is
twenty-five times that. The duplication tracks jurisdiction, exactly as it would if two
agencies were independently digitising one path.

Where it concentrates, at 25 m: **Bronx Waterfront 84.8%** of its 3.9 mi, Harlem
River-Putnam 58.1%, Mosholu-Pelham 56.7% of 11.8 mi, Central Queens 38.0%, Hutchinson
River 30.1%, New Springville 29.2%, Historic Brooklyn 22.2%. Manhattan Waterfront, the
longest system at 26.6 mi, is among the *least* duplicated at 10.9% — its esplanade is
DOT's and NYC Parks does not separately record it.

**A correction to §12e(a)'s own number while we are here.** That paragraph said 2,095
greenway segments carry `gwyjuris: DPR`. True of the 5,361 *current* greenway rows, and
not of what ships: after the `onoffst='OFF'` clause, **1,828** do. The larger number was
counted before the filter it is quoted alongside.

### Why the mechanism that exists declines to help

`lib/concurrency.py`'s `find_shared_ground` is precisely the machinery for two stewards on
one tread, and running it over both NYC layers emits **zero pairs**. Measured the same day,
and the reasons are worth reading in order because only the smallest one is the obvious
one:

| | dropped | why |
|---|---:|---|
| `nameless_skipped` | **3,777** | it pairs *trails*, and a trail is a name. #1432's `name_placeholders` rule reads `Unnamed Official Trail` and its siblings as absent, so over half the parks layer cannot be a party to a pair |
| `dropped_short` | 947 | shared stretches under `SHARED_GROUND_MIN_LENGTH_M` (50 m) |
| `dropped_unpainted` | 83 | the blaze gate: the feature it feeds is a **two-tone** treatment, and neither NYC layer has a blaze to paint |

So the blaze gate is the *last* filter and the smallest, which is the opposite of what a
quick look suggests. Even given blazes, most of this overlap would still be invisible to
the pairing, because the parks layer mostly has no names to pair on.

**None of this is a defect in `find_shared_ground`.** It exists to draw two blazed routes
side by side where they run together, and it is right to decline a pair it cannot paint.
The finding is that New York City's overlap is a *different* shape — unnamed, unblazed, and
in short pieces — and nothing in the build currently addresses it.

### What is still open, and it is a product decision

Three options, and the measurement does not pick between them:

1. **Leave both.** Defensible: both agencies genuinely maintain these paths, and 76% of the
   DPR greenway mileage is *not* duplicated, so suppressing the source wholesale would cost
   real ground to fix a quarter of it.
2. **Suppress one source's copy on overlapping ground**, the way `owns_route_names` already
   suppresses a route owner's duplicates — but that rule works on a name, and these rows
   mostly have none.
3. **Pair them as concurrent sources** and let the map say two stewards record this path,
   which is what §8 anticipates — and which needs `find_shared_ground` to grow a case for
   unnamed, unblazed tread, rather than a caller.

Recorded here rather than decided: what a hiker should see when two city agencies both
claim a path is a question about the map, and `@unvalidated` besides — nobody has stood on
one of the 423 doubled segments to see whether it is one path or two.

### Decided 2026-09-15: option 2, narrowed until it is safe (#1459)

The maintainer chose to build a real geometric dedupe rather than leave both or drop a
jurisdiction. `pipeline/lib/duplicates.py` is it, and the three choices that make option 2
survivable are all rounded the same way — removing a line a hiker needs is the *lost* path:

- **10 m, not the 25 m this section quotes.** `lib/concurrency.py` measured the knee of the
  same curve at 8–10 m, and 10 m is under the width of the drawn line at z14. 25 m would
  take in a boulevard's two sides digitised apart, which are two paths.
- **Half the feature's length**, so a greenway that merely runs beside a park trail for a
  stretch keeps both lines — outside that stretch it is the only record of that path.
- **Whole features, never split ones.** Cutting at the overlap boundary would be more
  precise and needs a rule for what the offcut is called and what happens to a fifteen-metre
  orphan. That question is open rather than answered badly.

**Measured 2026-09-15 against both live layers: 427 of the 3,030 shipped greenway records
removed, 30.35 miles — with 86 more coming near a parks trail for less than half their
length and kept.**

**And the rule validates itself against this section's own control.** It pairs on geometry
alone and never reads `gwyjuris`, yet:

| jurisdiction | flagged | of | rate |
| --- | ---: | ---: | ---: |
| **DPR** (NYC Parks' own ground) | **417** | 1,823 | **22.9%** |
| DOT | 10 | 690 | 1.4% |
| NYSDOT, NPS, MTA, RIOC, NYSPRHP, GIPEC, BPCA, BBPDC, SBS, DCAS, private | **0** | 517 | 0.0% |

**97.7% of what it flags is DPR**, and 22.9% of that jurisdiction's segments against
23.6% of its length by the independent vertex method above. Two different methods landing on
the same jurisdiction is the evidence that this removes double-draws rather than a dense
city's near neighbours. The 10 DOT-jurisdiction flags sit just above the 0.9% control floor
and are not individually checked — `@unvalidated`, and standing on one is what would settle
it.

**Option 3 is not foreclosed.** If somebody walks one of these and finds two paths, the pair
declaration comes out of `sources.json` and the lines come back.
