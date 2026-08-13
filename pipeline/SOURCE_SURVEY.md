# A.T. data sources — a qualified survey (August 2026)

Companion to [README.md](README.md) (the pipeline that consumes these) and
[../features/SOURCE_REGISTRY.md](../features/SOURCE_REGISTRY.md) (the design for letting
source organizations register themselves — this survey is the manual reconnaissance that
design would eventually replace). Written 2026-08-09 from live probes and web research;
every ArcGIS date below is the layer's own `editingInfo.dataLastEditDate` read that day,
not a page's claim about itself.

Why this exists: the registry (`sources.json`) grew from walking one public web map. That
found twelve layers, but nobody had surveyed what else is out there — what the maintaining
clubs publish, what the federal partners host, what the hiker community keeps current, and
which of those are structured enough to ingest. This is that survey: first the complete
candidate list, then a qualification of each. Sources needing a human decision are marked
**NEEDS REVIEW**.

The frame for qualifying a source, in order:

1. **Structured beats scrapeable.** A FeatureServer or GeoJSON file can be fetched,
   change-detected, and schema-checked; an HTML table can only be scraped and prayed over.
2. **Recent beats rich.** A stale shelter list is worse than a thin fresh one — the
   capacity number somebody plans an evening around has to be current.
3. **Licensed beats good.** CONTRIBUTING.md's rule: establish the licence before the bytes
   are in the build. Federal work is public domain; everything else needs an answer first.
4. **Stewarded beats scraped.** Data from the organization that maintains the ground it
   describes (SOURCE_REGISTRY.md's `authoritative` tier) outranks a hiker-made mirror of it.

---

## 0. The complete candidate list

Everything examined, one line each — the sections that follow are the qualification.
"Structured" means fetchable as data (REST/GeoJSON/GPX/CSV/API), not a page to scrape.

| source | maps | hikes | shelters | structured | last known change | verdict |
|---|:-:|:-:|:-:|:-:|---|---|
| NPS APPA GIS (ANST_* layers) | ✓ | | ✓ | ✓ | 2026-08-04 | in use; §1 corrects whose it is |
| ATC ArcGIS org — half-mile points | ✓ | | | ✓ | 2026-04-07 | in use |
| ATC org — `ATX_Ratings` overnight sites | | | **✓ capacity** | ✓ | 2025-10-01 | **best capacity source found** — §3a, ask ATC |
| ATC org — `Campsite_Sustainability_Index` | | | ✓ | ✓ | 2026-06-02 | rich, hazardous — §3b, ask ATC |
| ATC org — `Helene_Status` (+NPS twin) | | | | ✓ | 2026-08-06 | live closures — §3c |
| ATC org — other ~40 services | | | | ✓ | various | internal ops; catalogued §3d |
| ATC interactive map / website / A.T. Guide products | ✓ | ✓ | | | current | discovery chain in use; prose restrictively licensed — §4 |
| NPS `ANST_Administrative_Features`, 500ft buffer, SHEN copy | ✓ | | | ✓ | 2024–2026 | niche; §2 |
| NPS IRMA DataStore; NPS_Public_Trails; NRCA hub | ✓ | | | ✓ | 2022–2026 | catalog/fragments/ecology; §2 |
| USFS EDW trails + rec sites | ✓ | | | ✓ | maintained | cross-check on NFS land; §2 |
| USGS US Topo + 3DEP | ✓ | | | ✓ | multi-year cycles | in use (background/DEM) |
| Recreation.gov RIDB | | | | ✓ | live | frontcountry only; §2 |
| data.gov | | | | ✓ | — | aggregator; API unreachable from sandbox; §2 |
| **PATC** (240 mi) | ✓ | ✓ | ✓ | **✓ ArcGIS** | trails **2026-08-08** | standout club; terms unstated — §5 |
| **TEHCC** (134 mi) | ✓ | ✓ | **✓ capacity** | **✓ wiki APIs + GeoJSON** | 2026-08-08 | standout club; no licence — §5 |
| **NYNJTC** (160 mi) | ✓ sold | ✓ | | org exists, A.T. withheld | 2025–2026 | agreement path, Phase 5 — §5 |
| GATC (79 mi) | ✓ free PDF + CalTopo | ✓ | ✓ | CalTopo export | water PDF 2026-03 | best free club map set — §5 |
| CMC (93 mi) | | ✓ database | | wp-json unprobed | 2026 | hike DB; §5 |
| RATC (120 mi) | | ✓ 14 hikes | ✓ capacity table | scrapeable | 2024 | §5 |
| BMECC (65 mi) | | | ✓ capacity table | scrapeable | undated | §5 |
| AMC + AMC-WMA + AMC-CT | ✓ sold | ✓ | ✓ capacity tables | scrapeable | WMA 2026-07-17 | §5 |
| GMC (VT) | ✓ sold | ✓ | ✓ prose | | updates 2026-08-07 | live conditions feed; §5 |
| MATC (267 mi) | ✓ sold | | unpublished inventory | | 2021–22 | ask for Appendix G; §5 |
| MRATC, NHC, SMHC, ODATC, NBATC, PATH, OCVT, TATC, DOC, RMC, KTA, SATC, CVATC, AHC, YHC, MCOMD, AMC-DV, Batona | varies | varies | varies | mostly none | varies | complete inventory §5; several blocked sites flagged §10 |
| VCGI (Vermont) | ✓ | | | ✓ | 2026-07-27 | VT trails; §6 |
| Trail Finder (VT/NH) | | ✓ | | ✓ GPX/KML | 2026 | terms ask; §6 |
| PASDA NPS mirror | ✓ | | ✓ capacity (81) | ✓ | **2003** | historical only; §6 |
| **OpenStreetMap** | ✓ | | **✓ capacity ~153** | ✓ Overpass | live (May 2026 edit) | only *open* capacity source — §7 |
| Waymarked Trails | ✓ | | | ✓ API | live | convenience mirror; §7 |
| opentrail.org | | | | ✓ API | commits 2026-06 | in use; licence still open, now OSM-blended — §7 |
| tnlandforms.us | | | ✓ no capacity | GPX/KMZ | table 2026-03, coords 2009 | cross-check only; §7 |
| WhiteBlaze shelter PDF | | | ✓ 249 capacities | parseable PDF | 2024-02 | permission-gated cross-check; §7 |
| Postholer | ✓ | | | WFS defunct | 2026 site | nothing to take; §7 |
| FarOut / A.T. Guide / AllTrails / Hiking Project / Gaia | ✓ | ✓ | ✓ | closed | current | context only; §8 |
| Avenza store | ✓ | | | | **closing (April 2026 merger)** | strategic, not a source; §8 |

## 1. The correction first: "ATC" is two organizations, and mostly the NPS

Everything in `sources.json` says `provider: "ATC"`. Probing the item metadata behind the
services shows that is wrong for ten of the twelve entries:

| ArcGIS org | who it actually is | layers we use from it |
|---|---|---|
| `services1.arcgis.com/fBc8EJBxQRMcHlei` | **National Park Service** (item owner `jlfoster@nps.gov_nps`, org name "National Park Service") | `centerline`, `side_trails`, `campsites`, `shelters`, `parking`, `viewpoints`, `bridges`, `privies`, `at_treadway`, `trail_club_sections`, `communities` |
| `services9.arcgis.com/Nb3RpWJ36xRlYQj2` | **Appalachian Trail Conservancy** (item owner `ATConservancey`, org name "Appalachian Trail Conservancy") | `half_mile_points_from_springer` |

The NPS org is the Service's whole AGOL estate (1,578 public services, most of them
nothing to do with the A.T.); the A.T. layers there are the **APPA unit's official GIS**
("APPA Official Centerline", "APPA Features and Facilities" — APPA is the NPS alpha code
for the Appalachian National Scenic Trail). ATC and NPS build the public interactive map
cooperatively, which is why the Experience Builder app mixes both orgs' layers and why the
mislabel was easy to make.

It matters for two reasons. **Licence:** work of the federal government is public domain,
so the ten NPS-hosted layers have a *better* default answer than anyone knew —
their item pages carry only a general "reference purposes only" disclaimer, no copyright
claim. The unresolved-ATC-terms question really attaches only to the layers on ATC's own
org (half-mile points plus everything in §3). **Registry honesty:** `provider` (and
SOURCE_REGISTRY.md's future `steward`) should say NPS where it is NPS — the org to ask
about the shelters layer is the Park Service's APPA GIS program, not ATC.
Correcting the twelve `provider` values is a follow-up, not done in this survey
(the field is a label today — `discover_sources.py` writes it, nothing reads it).

### The twelve registered layers, re-probed 2026-08-09

Live counts and edit dates — compare against `pipeline/README.md`'s 2026-07-25 table:

| key | features | data last edited | note |
|---|---|---|---|
| `centerline` | 3,025 | **2026-08-04** | edited five days before this survey |
| `side_trails` | 1,200 | 2026-06-29 | |
| `campsites` | 232 | 2026-06-29 | |
| `shelters` | 280 | 2026-06-29 | still no capacity field ([#444](https://github.com/OurHike/OurHike/issues/444)) |
| `parking` | 482 | 2026-06-29 | |
| `viewpoints` | 1,223 | 2026-06-29 | |
| `bridges` | 409 | 2026-06-29 | |
| `privies` | 316 | 2026-06-29 | |
| `at_treadway` | 30 | 2026-06-29 | |
| `trail_club_sections` | 30 | 2024-08-15 | schema touched 2025-10-09, data two years old. **Not the club attribution the pipeline uses** — see §3e |
| `communities` | 59 | 2023-06-13 | the stalest layer we ship |
| `half_mile_points_from_springer` | 4,395 | 2026-04-07 | ATC org, not NPS |

The service description on `ANST_Facilities` stamps itself "Official Features and
Facilities - 04-24-2026"; the facilities layers were data-edited 2026-06-29 wholesale.
This upstream is actively maintained — on a cadence of weeks, not years.

Also present on `ANST_Facilities` but never registered: three non-spatial asset **tables**
(`Assets_Trail` 11, `Assets_Structures` 12, `Assets_Bridges` 13) — FMSS asset inventory
joins. Nothing hiker-facing; noted so the next person listing the server root doesn't
think them new.

---

## 2. Federal sources beyond the layers we use

**NPS `ANST_Administrative_Features`** (same NPS org) — Buildings, Dams, Tunnels, Roads,
Maintained Landscapes, Boundary (23 polygons), all data-edited 2026-03-05. The Boundary
layer is the corridor's legal footprint — potentially useful to LAND_OWNERSHIP.md's
Post-MVP polygon question; nothing here is a hiker POI. Public domain.

**NPS `Appalachian_National_Scenic_Trail_500ft_Buffer`** — one polygon, 2024-05-15. A
ready-made narrow corridor; we compute our own 30-mile one, so no use today.

**NPS `SHEN_TRANS_AppalachianTrail`** — Shenandoah's own copy of its 77 A.T. segments,
2025-05-09. Redundant with `centerline`; a cross-check at most.

**NPS `APPA_ECBS_Monitor_Sections`** — Exterior boundary monitoring sections, data 2020.
Stale, internal. Skip.

**NPS IRMA / DataStore** ([irma.nps.gov/DataStore](https://irma.nps.gov/DataStore/)) — the
Service's formal data catalog; the authoritative *live* products for APPA are the AGOL
services above (IRMA references snapshot editions of them). The National Trails Office GIS
page ([nps.gov/orgs/1453/gis-data.htm](https://www.nps.gov/orgs/1453/gis-data.htm), last
updated 2026-01-16) publishes centerlines for ten National *Historic* Trails and
explicitly not APPA. Useful catalog to know about; nothing to register from it today.

**USFS Enterprise Data Warehouse** — `EDW_TrailNFSPublish_01` (National Forest System
trails) carries **189 segments named "Appalachian"** where the A.T. crosses the eight
national forests, with USFS maintenance attributes; `EDW_RecInfraRecreationSites` and
`EDW_RecreationOpportunities` cover NFS recreation sites. Public domain, well-maintained
REST services at `apps.fs.usda.gov/arcx/rest/services/EDW`. Value to OurHike: an
independent cross-check of the centerline on USFS land and a possible source of
trailhead/rec-site attributes the NPS layers lack. Not a primary source — the NPS
centerline is the official alignment.

**A.T. Natural Resource Condition Assessment hub**
([appalachian-trail-natural-resource-condition-assessment-clus.hub.arcgis.com](https://appalachian-trail-natural-resource-condition-assessment-clus.hub.arcgis.com/))
— 58 datasets (forest condition, insect/disease damage, ecoregions), mostly 2022 vintage,
GeoJSON/CSV/ZIP downloadable. Ecological research, not hiker-facing. Known, skipped.

**USGS** — already the background-map and elevation supplier (US Topo quads,
3DEP-derived terrarium DEM; see README.md and BASEMAP.md). Public domain. Nothing new
found that the pipeline doesn't already use.

**Recreation.gov RIDB API** ([ridb.recreation.gov](https://ridb.recreation.gov/), key
free via recreation.gov/use-our-data) — structured JSON for federal recreation areas,
facilities, campsites and permits from twelve agencies; U.S.-government-work terms. Not a
trail source, but the one structured place federal *frontcountry* campgrounds and
permit-gated systems near the corridor are described. Corridor-relevant coverage
unmeasured. **NEEDS REVIEW** only if TRIP_PLANNING.md ever wants campground/permit data;
nothing to register today.

**data.gov** — aggregates the NPS/USFS records above; adds nothing original. (Its CKAN
API 404s from this sandbox — checked 2026-08-09; qualify it from the portal UI if ever
needed. **NEEDS REVIEW** only if someone wants data.gov as a discovery channel.)

---

## 3. The finds: unregistered ATC-org layers that answer open questions

Probing ATC's own org (the `half_mile_points` host, `services9…/Nb3RpWJ36xRlYQj2`) found
~130 public services. Most are internal operations — Survey123 form outputs, KRI chart
tables, land-acquisition planning, municipal reference copies. Four things stand out, two
of them directly answering questions this repo has open:

### 3a. `ATX_Ratings` layer 17 "Overnight Sites Symbol" — **shelter capacity exists** ⭐

413 overnight sites (271 shelters + 142 campsites), data-edited **2025-10-01**, with the
fields [#444](https://github.com/OurHike/OurHike/issues/444) says nothing published:
`Shelter_cpcty` (populated on 327 of 413), `sngl_night_max_cpcty` (370), group capacity,
tent platforms/pads, privy presence-count-type, food-storage capacity and type, plus
`mileage_from_N`/`mileage_from_S`, club section IDs, state, and FMSS
location IDs (`FMSS_LocID`) — that last one a potential **key join to the NPS shelters
layer**, dodging #444's name-matching problem entirely where it's populated. Spot-checked
values are real ("Hurd Brook Lean-to: Shelter_cpcty 6, single-night max 18, privy yes").

*Corrected 2026-08-13 (#529 research): this list previously included "water source".
Enumerating all 40 fields of layer 17 — and its sibling layers and DEMO/TEST twins —
shows **no water field exists anywhere in the ATX family**; water appears only in
free-text `notes`, on 34 of 413 sites. The capacity claims above stand.
[WATER_SOURCES.md](WATER_SOURCES.md) carries the water question, including the ATC-org
layer that does hold per-site water distances (`Campsite_Sustainability_Index` §3b,
whose provenance field shows those distances come from FarOut and NHDPlus HR).*

Caveats, honestly: capacity values are strings (`"6"`, `"0"`, `"Unknown"`); the service is
named for ATC's **Visitor Use Management program** ("ATX" = A.T. experience — current vs.
desired zone ratings per trail section), so the overnight inventory rides inside a
planning product, not a published "shelters" dataset; and the item carries **no licence**
(ATC org, so the unresolved-terms question applies in full). Sibling services
`ATX_Current_Conditions_DEMO`, `ATX_Condition_Differences_DEMO`, `ATX_SingleFC_TEST`
carry the same 413 sites under DEMO/TEST names — use `ATX_Ratings`, ignore the demos.

**NEEDS REVIEW**: this is the best shelter-capacity candidate found anywhere (better than
every community list — §6), but it is an unannounced internal layer. Registering it means
asking ATC — which the licence question requires anyway.

### 3b. `Campsite_Sustainability_Index` — a 3,354-site overnight inventory

Data-edited **2026-06-02**. Every overnight site ATC's stewardship program knows about:
531 shelters, 482 club/agency campsites, and **2,333 user-created (unofficial) sites**,
each with a `RIMS_ID`, site type, size in ft², A.T. mile (2026 measurement!), club,
documented-in (guidebook/map/databook/FarOut) flags, and sustainability scoring.

An order of magnitude richer than the 232-campsite facilities layer — and **not shippable
as-is**: the 2,333 user-created sites are the ones land managers are often trying to
close, and publishing them as places to camp would put OurHike on the wrong side of every
partner it depends on. **NEEDS REVIEW** — worth asking ATC whether the
established-sites subset could be used; do not ingest unilaterally.

*Amended 2026-08-13:* one narrow, maintainer-directed use now exists — **#668 — A
shelter card says nothing about water, and ATC has measured the distance to it** takes
`Proximity_Water_ft` for the **official sites only** (the WHERE clause never requests a
user-created row) and attaches it to the shelters and campsites already published,
publishing only the NHD- and field-estimate-derived rows and holding the FarOut-derived
ones pending §10's ATC ask. WATER_SOURCES.md §4 holds the reasoning,
`build_water_distance.py` the join, `reference/water_distance.json` the reviewable
result. The sites themselves stay unpublished exactly as this section says.

### 3c. `Helene_Status` — live-ish closure status per club section

140 polygons, data-edited **2026-08-06** (three days before this survey), fields
`TRAIL_CLUB`, `Status`, `Notes`, segment endpoints. The companion NPS-org layer
`APPA_HeleneStatusCenterline` (64 line segments, 2026-07-31) is the same information as
geometry. This is the closure/conditions signal CONDITIONS_DELIVERY.md currently gets
nowhere upstream — scoped to Hurricane Helene recovery, so treat it as a
program-lifetime source, not a permanent one. A third sibling,
`ATC_Hurricane_Helene_Survey_2_view_Public` (12,503 USFS-schema damage survey points,
edited 2026-08-07), is the raw field data behind it — too raw to ship, useful context.
**NEEDS REVIEW** for CONDITIONS_DELIVERY.md.

### 3d. Smaller findings on the two orgs

| service | what it is | date | verdict |
|---|---|---|---|
| `AT_ClubMap` (5 layers) | club section points/lines/polygons for the club map, incl. 35 club-name points | 2025-06/07 | **the same thirty clubs as `trail_club_sections`, not more** — corrected 2026-08-13, see §3e |
| `VUM_Clubs` | 52 club *sub*-section polygons with N/S end descriptions | 2025-09-05 | finer-grained club sections than anything registered — useful for SAYING_THANKS/MaintainerAssignment granularity someday |
| `NERO_ATX_OvernightSites` / `NERO_ATX_Merged` | New-England-region subset of the ATX data | 2024-03 | superseded by the trail-wide layers above |
| `2022_ATC_Lands_Fee_Parcel_Shapefile` / `…Easement_Parcel_2` | ATC-held land parcels (24 fee + 33 easement) | data 2025-05 | LAND_OWNERSHIP.md material, Post-MVP |
| `LRF_Tread_Deficiency_2025_08` + LRF_* siblings | trail-work planning: 3,978 tread-deficiency points, 6,025 prescriptions (Aug 2025) | 2025-08 | internal work-planning ("LRF" = Legacy Restoration Fund); not hiker-facing |
| `at_deficiencies_2004_2013` | historic deficiency inventory | 2004–2013 | archive only |
| `ATC_Wilderness_Areas_in_the_US_Offline` | wilderness boundaries copy | — | national reference copy; get wilderness from USFS/UMT directly if ever needed |
| ~40 `survey123_*` / `Chart_*` / `service_*` services | form outputs and dashboard tables | various | internal, skip |

**A discovery-method note for the registry:** every find above came from listing the two
orgs' `rest/services` roots directly — the same move that found `bridges` and `privies`
last month, one level up. `discover_sources.py` walks the curated public map and can never
see these. Worth remembering as SOURCE_REGISTRY.md's probe design firms up.

### 3e. Club attribution: the centerline is the source, not the polygons (measured 2026-08-13)

Checked while building #594, and it corrected two things this document previously said.

**The centerline already carries the club.** `ANST_Centerline` has `Trail_Club`, `Acronym`
and `Reg_Acro` on **every one of its 3,025 features**, and so does `at_treadway`. That is a
better source than `trail_club_sections` on every axis that matters:

| | `centerline` | `trail_club_sections` |
|---|---|---|
| last edited | **2026-08-04** | 2024-08-15 |
| attribution sits on | the trail line → exact mile ranges | polygons → derived by point-in-polygon |

So `export_club_sections.py` reads the centerline for **which stretch belongs to whom**, and
the polygon layer for **how a club's name is spelled** and its region. Fresh source decides
the fact; stale source decides only the wording.

**Correction — the 35-vs-30 discrepancy in §3d was not real.** `AT_ClubMap`'s
`APPA_TrailClub_secPoints` holds 35 point features but only **31 distinct name strings**, and
those 31 are the same **30 clubs**: four clubs maintain discontiguous trail and get a label
point each (AMC-Delaware Valley, Blue Mountain Eagle, Mountain Club of Maryland, Roanoke
ATC), and one club appears under both `Outdoor Club of Virginia Tech` and the typo
`Outdoor Club of Virginina Tech`. **Randolph Mountain Club has its own polygon in the
30-layer**, so the claim that it was "folded elsewhere" was wrong. There is no missing club.

`AT_ClubMap` is also not in the NPS org — it belongs to `jweems_ATConservancy` on
`services9`, which is why listing `fBc8EJBxQRMcHlei` does not show it.

**What is wrong with the centerline's club fields, so nobody trusts them blindly.** Freshness
is bought at a cost in cleanliness — 44 distinct `Acronym` values where there are 30 clubs:

- **47 features carry a digit string in both `Trail_Club` and `Acronym`** (`"23"`, `"11"`,
  `"27"`, …) — an unjoined FID or a shifted column upstream. 41.4 miles, **1.90% of the
  trail**. The pipeline publishes those miles as *unattributed* rather than backfilling them
  from the two-year-old polygons.
- **Two clubs are misspelt in `Trail_Club` and correct in `Acronym`** — `Potomac Appalachain
  Trail Club` (PATC) and `New York - New Jersey Trail Conference` (NYNJTC, spacing). Every
  acronym maps to exactly one spelling, which is what makes the **acronym** the safe join key
  and the name an unsafe one.

Not reported upstream. If that changes, these are the specifics to send.

---

## 4. The Appalachian Trail Conservancy as a *published*-content source

Beyond the GIS estate, what ATC publishes for hikers, qualified:

- **Interactive map** ([map.appalachiantrail.org](https://map.appalachiantrail.org/)) —
  the Experience Builder app `sources.json` was discovered from. Consumption path already
  exists; nothing new.
- **Suggested hikes** — "Explore by State" pages and a Day Hiking resource library:
  editorial HTML, no structured form, no dataset behind it we could find. Scraping would
  be both fragile and against their terms (below). The *structured* shape of "suggested
  hikes" this project already designed (HIKE_PLANNING.md generates plans from data rather
  than ingesting itineraries) is the better path — treat ATC's pages as inspiration, not
  a source.
- **A.T. Data Book / guidebooks / paper & Avenza maps** — sold products, ATC's revenue;
  not ingestable and shouldn't be.
- **FarOut** became ATC's **official app** (announced 2024-08); ATC data increasingly
  reaches hikers through it. Commercial, crowd-sourced comments layered on licensed data;
  no reuse path. Relevant mostly as context: the CSI layer's `Documented` field literally
  tracks "is this site in FarOut".
- **Terms**: [appalachiantrail.org/terms-and-conditions](https://appalachiantrail.org/terms-and-conditions/)
  prohibits copying/redistribution of site content without written permission and says
  nothing specific about GIS services. So the working assumption for anything on **ATC's
  own ArcGIS org** stays "ask first" — one conversation covering the half-mile points we
  already ship, ATX overnight sites (§3a), CSI (§3b), and Helene status (§3c) would
  resolve the whole column. The contact route is
  [appalachiantrail.org/contact](https://appalachiantrail.org/contact/) /
  info@appalachiantrail.org. Same posture #98 takes for opentrail.org: asked, recorded,
  then shipped.

---

## 5. The maintaining clubs — all thirty

ATC's current [Clubs & Partners page](https://appalachiantrail.org/protect/trail-management/clubs-partners/)
lists **30 affiliated maintaining clubs** — matching the 30 polygons in
`trail_club_sections`. (The old `/get-involved/volunteer/trail-clubs/` URL is a 404 now;
update any bookmarks.) Checking every club's own site surfaced three corrections to the
roster as it is usually recited:

- **Wilmington Trail Club and Philadelphia Trail Club no longer maintain A.T. sections.**
  Their former Pennsylvania miles are covered by AMC Delaware Valley (two sections:
  Wind Gap–Little Gap and Fox Gap–Delaware Water Gap, incl. Kirkridge Shelter) and by
  **Keystone Trails Association itself** (~11 mi at Lehigh Gap) — KTA is a maintaining
  club in its own right, not only the PA umbrella.
- **AMC Berkshire Chapter is now AMC-Western Massachusetts** (the chapter renamed;
  ATC's shelter/CSI layers still carry the old name — a join hazard).
- **Randolph Mountain Club** (2.2 mi in the northern Presidentials) is easy to drop from
  informal lists; ATC counts it.

The qualification headline: **club-published data is overwhelmingly paper/Avenza
cartography and hand-maintained HTML.** Exactly one club exposes a real, queryable GIS
service (PATC); one runs a wiki with machine-readable APIs (TEHCC); one has an in-house
GIS program whose A.T. data is deliberately *not* public (NYNJTC). Everything else is
scrapeable pages, PDFs, or nothing. Per-club inventory, north to south — dates are what
each site itself showed on 2026-08-09:

### New England (7 clubs)

| club | A.T. miles | what they publish | structured? | recency / flags |
|---|---|---|---|---|
| Maine A.T. Club (MATC) | 267 | 7 paper/Avenza topo maps (2021), *Guide to Maine* (2021); no public shelter table — but their Local Management Plan (2022 PDF) references a campsite inventory in an unpublished appendix | none | **NEEDS REVIEW**: asking MATC for the Appendix G campsite inventory could yield structured campsite data |
| Randolph Mountain Club (RMC) | 2.2 | *Randolph Paths* guide + map (2016); 4 year-round camps off the A.T. proper (Crag 20, Gray Knob 15, Log Cabin 10, The Perch 8 — capacities per search results, unverified); network map lives in Trailforks | Trailforks (proprietary) | site dated 2023; **NEEDS REVIEW** if RMC camps matter: Trailforks licence unexamined |
| Appalachian Mountain Club (AMC) | White Mtns region + W. Maine | Tyvek maps + *White Mountain Guide* (31st ed. 2022, Avenza); **backcountry-campsites page: 14 sites with shelter/platform counts, $15 caretaker fees, 2026 bear-canister rule** — best free NH shelter data | scrapeable HTML | campsites page actively maintained (2026 policy text) |
| Dartmouth Outing Club (DOC) | 54 | essentially nothing online; legacy pages disagree with ATC on section length (50 vs 54 mi) | none | stale `.shtml` pages |
| Green Mountain Club (GMC) | ~150 (LT overlap + Maine Jct–Norwich) | *Long Trail Map* 7th ed. (new; Avenza still 6th ed. 2021); ~70 overnight sites described but no master table; **Trail Updates page is a genuine live feed** (entries 2026-08-07, incl. two A.T. bridge removals with mileposts) | none | own `/hiking/maps/` page still advertises the 5th ed. — internally stale; caretaker fees ended 2023 |
| AMC-Western Mass. (ex-Berkshire) | 90 | **full N→S campsites/shelters list with capacities** (Wilbur Clearing 6, Kay Wood 12, Upper Goose Pond Cabin, etc.) | scrapeable HTML | page footer "last updated 2026-07-17" — fresh |
| AMC Connecticut | 52 | campsite page: 12 sites with tent counts, water, privies, bear boxes at every site; club map PDFs dated 2008–2014 | scrapeable HTML | camping policy current; **maps are the stalest in the region** |

### Mid-Atlantic (11 clubs)

| club | A.T. miles | what they publish | structured? | recency / flags |
|---|---|---|---|---|
| NY-NJ Trail Conference (NYNJTC) | ~160 | sold Tyvek maps + Avenza (deliberately not downloadable PDFs); ~42 free maps incl. two A.T. ones; A.T. day-hike pages; **no shelter list at all** | own ArcGIS org — **but only Long Path / Highlands Trail extracts are public, not the A.T. or full network** | Long Path layer Sep 2025, hike-app Apr 2026 — the GIS program is alive; §10 covers what this means for ROADMAP Phase 5 |
| Batona Hiking Club | ~8.6 | hike calendar via Meetup/Wild Apricot | none | site unfetchable (JS/503) — **NEEDS REVIEW** manually |
| AMC Delaware Valley | 15 + 7 | trail-work pages; maintains Leroy Smith + Kirkridge shelters | none | current |
| Keystone Trails Assoc. (KTA) | ~11 | *PA A.T. Guide* 13th ed. (2023); umbrella advocacy for all PA clubs | none | site rate-limits (429) — maps page unverified, **NEEDS REVIEW** manually |
| Blue Mtn Eagle Climbing Club (BMECC) | 65 | **8-shelter page with build years, capacities, water, privies, caretakers** (Rausch Gap → Bake Oven Knob) | scrapeable HTML | undated but detailed; best free PA shelter data |
| Allentown Hiking Club | 10.3 | hike listings; maintains Allentown Shelter | none | active calendar |
| Susquehanna A.T. Club (SATC) | 20 | trail + hiking pages; Peters Mountain Shelter | none | site 429-blocked — **NEEDS REVIEW** manually |
| York Hiking Club | 7 | hike program | none | current |
| Cumberland Valley A.T. Club (CVATC) | 17 | Alec Kennedy + Darlington shelters | none | site 429-blocked — **NEEDS REVIEW** manually |
| Mountain Club of Maryland (MCOMD) | 10 + 32 in PA | hike schedule; **news post: James Fry Shelter CLOSED** — live condition signal a shelter dataset must reflect | none | maintenance page updated 2025-08 |
| Potomac A.T. Club (PATC) | 240 | 19 paper maps ($16.95; SNP editions 2025 are Avenza-first), guidebooks (MD/NoVA 19th ed.), 47 shelters + 49 cabins (18 public, on-site booking) | **yes — see below** | the region's standout |

**PATC's ArcGIS org** (`patc-gis.maps.arcgis.com`, services at
`services7.arcgis.com/BbnVmymrKxjFL0SO/…`, 58 public services) — re-verified by direct
query 2026-08-09:

| layer | features | data last edited | fields worth having |
|---|---|---|---|
| `PATC_Trails_Master_view/FeatureServer/10` | 2,118 segments | **2026-08-08** (the day before this survey) | TrailName, District, Maintainer, GuidebookSection, SegmentLengthMiles, SurveyDate |
| `PATC_Shelters_AT_and_TT_2_view/FeatureServer/0` | 47 shelters | 2024-09-25 | Year_Built, materials, food-storage (box/cable/pole), Ownership, photos — **no sleeping capacity** |
| `Cabin_Locations/FeatureServer/0` | 49 cabins | 2026-03-10 | **Capacity**, Cabin_Type, Pet_Friend, Hike_In, AT_Access, fees, booking link |

Query-enabled, GeoJSON output works, no licence text anywhere. 240 of the A.T.'s ~2,197
miles with a *maintained* trails layer fresher than anything except NPS's own centerline —
and the same "public ≠ licensed" caveat as every club asset (§9).

### Southern (12 clubs)

| club | A.T. miles | what they publish | structured? | recency / flags |
|---|---|---|---|---|
| Old Dominion A.T. Club (ODATC) | 19.1 | 2 circuit hikes; Paul C. Wolfe Shelter | none | active club, thin data |
| Tidewater A.T. Club (TATC) | ~10 | little public; section endpoints not even stated | none | newsletter Jun/Jul 2026 |
| Natural Bridge A.T. Club (NBATC) | ~90 | own interactive map page (shelters, relocations, invasives layers) + a Favorite Hikes GPX (2017) | one GPX; map's data layer loads by script — **NEEDS REVIEW** (needs a browser look) | site visibly ageing (2012–2023 stamps) |
| Roanoke A.T. Club (RATC) | ~120 | **16-shelter table with build year, capacity, off-trail distance, water reliability** + a 14-hike breakdown of their whole section | scrapeable HTML | posts to Nov 2024; hike PDF Oct 2024 |
| Outdoor Club at Virginia Tech (OCVT) | 30 | trips system only; legacy domain dead | none | ocvt.club 403s bots (curl works) |
| Piedmont A.T. Hikers (PATH) | 66 | section map PNG; "five shelters" in prose | none | copyright 2023–24 |
| Mount Rogers A.T. Club (MRATC) | 59.4 | suggested-hikes page (7+ curated hikes with mileage/difficulty); 2026 detour notices | none | news posts late July 2026 — current |
| Tennessee Eastman (TEHCC) | ~134 | **club wiki with APIs** — see below | **yes** | A.T. page edited 2026-08-08 |
| Carolina Mountain Club (CMC) | 92.7 | **find-a-hike database** (filterable, rich per-hike detail pages, no GPX); A.T.-MST challenge log (15 legs w/ cumulative miles); no shelter content | WordPress; `wp-json` root exists — **NEEDS REVIEW**: whether the hike post type is exposed is untested | hikes scheduled thru Sep 2026 |
| Smoky Mtns Hiking Club (SMHC) | 102 | 2026 member handbook PDF (Dec 2025); maps page links NPS + historic archives | none | handbook contents unparsed — **NEEDS REVIEW** if hike schedules wanted |
| Nantahala Hiking Club (NHC) | 58.6 | SOBO-by-sections map/guide PDF (Oct 2025) | none | current |
| Georgia A.T. Club (GATC) | 78.6 (+8.8 approach) | free map+profile PDFs (Nov 2024), **water-sources PDF (2026-03-02)** — since 2026-08-13 fetched and parsed for review by `fetch_club_pdfs.py` (#669, `kind: club_pdf`; publication still gated on asking GATC), mile-by-mile trail guide (2023), CalTopo maps with GPX/KML export | CalTopo export | **NEEDS REVIEW**: CalTopo terms for bulk reuse; members-only "Districts Sections Mapping" suggests internal GIS |

**TEHCC's wiki** (`tehcc.org/clubwiki`) — re-verified 2026-08-09: MediaWiki 1.43.9 with
Semantic MediaWiki; Action API + REST API answer anonymously; a `GeoJson:` namespace holds
**156 raw FeatureCollection pages** (real coordinates confirmed); 17 `Shelter:` pages
carry infoboxes with **Capacity, Privy, lat/lon, elevation, distance-to-next-shelter,
nearest-medical** (Roan High Knob: capacity 15, confirmed in raw wikitext); a `Report:`
namespace holds timestamped per-trail condition reports. The A.T. page was edited the day
before this survey. Two catches: the shelter infobox fields are not exposed as semantic
properties (harvesting means parsing wikitext, a solved problem but real work), and
`rightsinfo` is empty — **no licence declared, ask the club** (§9).

### What the clubs give the three asks, in one look

- **Maps**: sold paper/Avenza everywhere (MATC 2021, AMC 2022, GMC 7th ed., NYNJTC,
  PATC 2025 editions, KTA 2023). Free georeferenced club cartography does not exist;
  the *data* path is GIS layers, not scanned maps. GATC's CalTopo maps are the one
  free-export exception.
- **Suggested hikes**: genuinely good curated day-hike content at RATC (14 hikes),
  MRATC, CMC (database), GMC, NYNJTC, GATC (mile-by-mile guide), TEHCC (full trail
  wiki); everything is HTML/PDF prose except TEHCC's and CMC's, which are one API probe
  away from structured.
- **Shelters**: club pages carry what no GIS layer does — **capacity** (AMC-WMA, AMC
  White Mtns, BMECC, RATC, TEHCC ≈ 55+ shelters with capacities between them, in
  scrapeable form, join-by-name) — plus live closure signals (MCOMD's James Fry post,
  GMC's updates feed). But §3a's ATX layer already covers capacity trail-wide from one
  steward; club pages are better used as **verification and freshness cross-checks** than
  as 30 tiny scrapers.

## 6. State portals and regional platforms (found while checking clubs)

| source | what | structured? | recency | verdict |
|---|---|---|---|---|
| **VCGI (Vermont Open Geodata)** — `Vermont_Trails_SCORP_Public` FeatureServer | statewide 2025 trail inventory | yes (FeatureServer + GeoJSON/SHP/KML) | modified 2026-07-27 | fresh; but the dedicated GMNF "Long Trail and A.T." dataset it once had is retired (404, gone from the DCAT catalog) — **NEEDS REVIEW** whether SCORP substitutes for VT A.T. geometry |
| **Trail Finder** (trailfinder.info, run by Upper Valley Trails Alliance) | VT/NH hike finder incl. the A.T. (297.4 mi), per-trail pages | **yes — per-trail GPX + KML downloads** (verified live) | maintained (2026) | best structured suggested-hikes source found for NH/VT; "© All Rights Reserved" — terms need asking |
| **PASDA** (Penn State) NPS mirror — `pasda/NationalParkService/MapServer` | A.T. shelters (117 pts, **CAPACITY populated on 81**, FEE), centerline (4,549 segs), parks polygons | yes | **2003 vintage** ("Appalachian Trail Conference"-era attribution; verified by query) | historical snapshot only — schema is interesting precedent for capacity, data is 23 years old. Do not ingest |
| **Trailforks** (RMC network), **CalTopo** (GATC maps), **HikingUpward** (linked by VA clubs for hike pages) | third-party platforms clubs lean on | varies | varies | platform terms, not club terms, govern — treat as leads to the club, not as sources |


## 7. Community sources

**OpenStreetMap** — the A.T. is superrelation **156553** (`operator=Appalachian Trail
Conservancy`, `network:type=US:NST`), containing 14 state-section relations; last edited
~May 2026. Shelters along it are `amenity=shelter` (+`shelter_type=lean_to`), and a live
Overpass query (2026-08-09) found **181 shelter nodes within 500 m of the trail, 153 of
them carrying a `capacity` tag** — a floor, not a total: shelters mapped as building
*ways* weren't counted (the follow-up query wouldn't complete through the sandbox proxy —
**NEEDS REVIEW**: re-run as `nwr` to get the true coverage). ODbL: attribution +
share-alike, the licence the basemap already complies with. This is the only **openly
licensed** shelter-capacity source found anywhere, and the crowd's numbers would want
verifying against §3a's before either ships.

**Waymarked Trails** (hiking.waymarkedtrails.org) — OSM-derived route service;
`api/v1/details/relation/156553?geometry=geojson` returns the assembled A.T. geometry in
one 5.8 MB response (verified live). Convenience mirror of data we could assemble
ourselves; no stated usage policy for the hosted API, so treat as a reference
implementation rather than infrastructure to lean on.

**opentrail.org** — already ingested (`fetch_opentrail.py`); confirmed alive (API 200
with ETag, 1,840 A.T. features, commits to June 2026). Two licence facts that sharpen
[#98](https://github.com/OurHike/OurHike/issues/98): the repo still has **no LICENSE
file** (re-checked at raw.githubusercontent on `main`, 2026-08-09), and a May 2026 commit
added `scripts/import-osm.js`, which pulls Overpass data (water, shelters, campsites…)
into their database **with no ODbL attribution handling** — so their dataset is now
partly OSM-derivative. That both compounds the question and suggests its natural answer:
ODbL treatment. Worth stating in the #98 conversation.

**tnlandforms.us** (Tom Dunigan's A.T. page) — a shelter table *revised 2026-03-10*
(mileages tracked to the 2026 Companion) sitting on **2009-era ATC coordinates**, no
capacity column, personal copyright inheriting old ATC conditions. A labor of love and a
good mileage cross-check; not an ingestion source.

**WhiteBlaze** — forum is active (May 2026 front-page articles). The community's real
data artifact is the annual **shelter listing PDF** ("courtesy of WhiteBlaze Pages ©"):
the 2024 edition (newest verifiable — 2025/2026 URLs don't exist) parses to ~245 shelters
with **249 sleeps-capacity values**, shelter *and water source* GPS, water reliability,
tenting, privies, bear boxes. Richest single shelter attribute set found; PDF-shaped,
copyright a commercial guidebook, updated 2024-02. Permission-gated cross-check material,
not a pipeline source. (The forum's live shelter database at `at-shelters.php` needs a
real browser — **NEEDS REVIEW** if anyone wants its field list.)

**Postholer** — the documented WMS/WFS at `gis.postholer.com` now redirects to the
homepage (verified with an on-trail coordinate); no downloadable GIS found; map data
credited to ATC anyway. Nothing to take.

## 8. Commercial guides — context, not sources

None of these is ingestable; all shape what hikers expect and what the capacity/water
data ecosystem looks like:

- **FarOut** (Atlas Guides) — ATC's **official app** since Aug 2024. ToS verified:
  scraping prohibited, no API, commercial reuse only by written agreement. ATC's CSI
  layer literally tracks which of its sites appear in FarOut — that is who OurHike's data
  quality gets compared against.
- **The A.T. Guide** (AWOL, theatguide.com) — 2026 edition on sale; the reference for
  landmark/water completeness (1,127 water sources claimed). Traditional copyright.
- **AllTrails / Hiking Project / Gaia** — Hiking Project's public API has been dead since
  2020 (owner onX still declining requests, verified on their data page); AllTrails is
  bot-protected and enforces; Gaia's topo is OSM-derived — its trail data is the same
  ODbL data available directly. No path, and no loss.
- **Avenza — the strategic headline.** Per NYNJTC's June 2026 news article (verified):
  Avenza merged with Blue Marble Geographics in **April 2026**; vendors can no longer add
  or update maps; **the Map Store will close**, timeline unannounced, fate of purchased
  maps unclear. Every Avenza-exclusive club edition (PATC Maps 9/11's newest editions,
  MATC's digital set, NYNJTC's 50+ maps, GMC's) is exposed. This is the exact scenario
  OurHike was founded on, now happening to the whole store at once — both a validation
  and, handled respectfully, the opening for club partnerships (§10).

## 9. Licensing, summarized

| licence reality | sources | what it means for the pipeline |
|---|---|---|
| **Public domain (US federal work)** | NPS APPA layers (10 of our 12), USFS EDW, USGS topo/3DEP, NPS_Public_Trails | Ship freely; attribution as courtesy. The survey's provider correction moves most of our current data *into* this row |
| **ODbL** | OSM (incl. shelter capacities), Waymarked Trails, Geofabrik extracts (already used) | Attribution + share-alike on derivative databases — already complied with for the basemap |
| **Unstated — org would need to answer** | ATC's own org layers (half-mile points, ATX overnight sites §3a, CSI §3b, Helene §3c), PATC's GIS, TEHCC's wiki, NYNJTC's services, club HTML pages, Trail Finder | Public ≠ licensed. One conversation each with ATC, PATC, TEHCC covers everything worth having in this row |
| **Unresolved, now compounded** | opentrail.org (#98) | No LICENSE file + now imports OSM without attribution; raise both in the same ask |
| **Copyrighted, permission-gated** | WhiteBlaze shelter PDF, club paper/Avenza maps, MATC's unpublished campsite inventory appendix | Cross-check/validation material, or a direct ask |
| **Closed, no path** | FarOut, A.T. Guide, AllTrails, Hiking Project (API dead), Gaia | Context only |
| **Restrictive site terms** | appalachiantrail.org website content (suggested-hikes prose) | Don't scrape; hike *generation* from data (HIKE_PLANNING.md) is the better design anyway |

## 10. What to do with all this, ranked

Each of these is a candidate follow-up, deliberately **not** done in this survey — the
registry file stays untouched until licences are answered (the #98 lesson, applied in
advance):

1. **Ask ATC one combined question.** Their own org hosts four things worth shipping —
   half-mile points (already shipped, terms never confirmed), **ATX overnight sites with
   shelter capacity (§3a — closes [#444](https://github.com/OurHike/OurHike/issues/444)'s
   source hunt)**, Helene closure status (§3c), and possibly a vetted subset of CSI
   (§3b). One conversation, via info@appalachiantrail.org / the interactive-map team,
   settles the whole ATC column of §9. The FMSS-ID join between ATX sites and the NPS
   shelters layer should be tested while that conversation happens.
2. **Correct `sources.json`'s provider story** — ten layers are NPS's, not ATC's
   (§1). A small change; SOURCE_REGISTRY.md's `steward` field is its eventual home.
3. **OSM shelter capacities as the openly licensed fallback** (§7): if the ATC ask
   stalls, 153+ capacity tags under ODbL are shippable today, verified against club pages
   (§5's five capacity tables) — with the `nwr` re-query done first.
4. **Register the Helene status layer for CONDITIONS_DELIVERY.md** once ATC blesses it —
   140 club-section polygons, edited three days before this survey, is a real closure
   feed no other source offers.
5. **PATC and TEHCC conversations, in ROADMAP order not ahead of it** — PATC's trails
   layer (edited the day before this survey) and cabins-with-capacity, TEHCC's GeoJSON +
   shelter infoboxes. Both are exactly SOURCE_REGISTRY.md's `arcgis_feature_layer` /
   `http_file` registrants-in-waiting; neither has stated terms.
6. **NYNJTC is an agreement, not a scrape** — their GIS program is real and their A.T.
   network deliberately unpublished; Phase 5's onboarding path runs through their Trail
   Planner / Professional Services channel. The Avenza store closing (§8) is the shared
   problem that makes that conversation timely for every club in §5.
7. **Update #98 with the OSM-import fact** (§7) — it materially changes the licence
   question's shape.

### Marked for maintainer review, collected

Things found but not resolvable without a human (or a real browser):

| item | why it needs eyes | where |
|---|---|---|
| `ATX_Ratings` / VUM services on ATC's org | internal planning product carrying the best shelter-capacity data; is it meant to be public? | §3a |
| `Campsite_Sustainability_Index` | 2,333 user-created campsites — publishing locations may be actively harmful; established-sites subset is the askable part | §3b |
| `Helene_Status` + survey layers | closure feed scoped to one recovery program; lifetime unclear | §3c |
| ATC org's ~40 `survey123_*`/`Chart_*`/`service_*` services | opaque names, form outputs; catalogued and skipped — spot-check only if something specific goes missing | §3d |
| NBATC interactive-map data layer | loads by script; needs a browser look to find the underlying file | §5 |
| CMC `wp-json` | whether the hike database is exposed as a post type — one probe answers it | §5 |
| KTA / SATC / CVATC sites; Batona; Wilmington | Weebly 429s and JS shells blocked automated checking | §5 |
| `potomactrailclub.org` | DNS dead but linked from patc.net — new domain not yet live, or rot? | §5 |
| SMHC 2026 handbook PDF | unparsed; may contain the year's structured hike schedule | §5 |
| GATC CalTopo maps; RMC Trailforks | platform terms govern bulk export; unexamined | §5, §6 |
| VCGI's retired GMNF "Long Trail and A.T." dataset | whether the SCORP layer substitutes for VT A.T. geometry | §6 |
| OSM way-mapped shelters (`nwr` re-query) | capacity coverage floor vs. true total | §7 |
| WhiteBlaze live shelter DB (`at-shelters.php`) | vBulletin, needs a session; field list unknown | §7 |
| data.gov CKAN API | 404s from this sandbox; only matters if wanted as a discovery channel | §2 |

---

*Method note for whoever refreshes this: every ArcGIS claim above is one
`<layer-url>?f=pjson` away (`editingInfo.dataLastEditDate`, epoch ms) and one
`/query?where=1=1&returnCountOnly=true&f=json` away from re-verification — the same two
requests `check_freshness.py` and `fetch_all.py` already make. Club sites rot faster than
federal servers; re-date the club table before trusting it a season later.*
