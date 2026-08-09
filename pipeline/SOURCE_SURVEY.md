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
| `trail_club_sections` | 30 | 2024-08-15 | schema touched 2025-10-09, data two years old |
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
tent platforms/pads, privy presence-count-type, food-storage capacity and type, water
source, plus `mileage_from_N`/`mileage_from_S`, club section IDs, state, and FMSS
location IDs (`FMSS_LocID`) — that last one a potential **key join to the NPS shelters
layer**, dodging #444's name-matching problem entirely where it's populated. Spot-checked
values are real ("Hurd Brook Lean-to: Shelter_cpcty 6, single-night max 18, privy yes").

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
| `AT_ClubMap` (5 layers) | club section points/lines/polygons for the club map, incl. 35 club-name points | 2025-06/07 | fresher sibling of `trail_club_sections`; the 35-point list includes Randolph Mountain Club, which the 30-polygon layer folds elsewhere |
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
| Randolph Mountain Club (RMC) | 2.2 | *Randolph Paths* guide + map (2016); 4 year-round camps (Crag 20, Gray Knob 15, Log Cabin 10, The Perch 8 — off the A.T. proper); network map lives in Trailforks | Trailforks (proprietary) | site dated 2023; **NEEDS REVIEW** if RMC camps matter: Trailforks licence unexamined |
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
| Georgia A.T. Club (GATC) | 78.6 (+8.8 approach) | free map+profile PDFs (Nov 2024), **water-sources PDF (2026-03-02)**, mile-by-mile trail guide (2023), CalTopo maps with GPX/KML export | CalTopo export | **NEEDS REVIEW**: CalTopo terms for bulk reuse; members-only "Districts Sections Mapping" suggests internal GIS |

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


<!-- SPLICE: §6 community + §7 commercial (community agent) -->

<!-- SPLICE: §8 summary tables + recommendations -->
