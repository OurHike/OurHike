# Water near shelters — the measurements and the sourcing options (August 2026)

Companion to [SOURCE_SURVEY.md](SOURCE_SURVEY.md) (the general upstream survey this
narrows to one question), to [WATER_CONDITIONS.md](WATER_CONDITIONS.md) (the same question
asked about *time* rather than place — whether the water is flowing today, added
2026-08-15 and the one correction to §7's closing paragraph), and the working record for
**#529 — 97% of shelters have no
water source within 250 m, and the trail is not like that**. Everything here was
measured 2026-08-13 unless a different date is stated; the two measurement scripts are
committed beside this file ([spike_shelter_water.py](spike_shelter_water.py) for USGS
NHD, [spike_osm_water_census.py](spike_osm_water_census.py) for OSM), each re-runnable
and each caching upstream responses so a re-run re-reports without re-fetching.

What was known before this document, so it is not re-derived here:

- The app's whole water supply is 174 opentrail.org points for 2,197 miles; 8% of the
  280 shelters have one within 250 m (#529's own tables).
- A prior session measured OSM point sources near 80 shelters — **all of them in New
  England** — and found level pegging with that supply (8% at 250 m), plus a 73:1
  dominance of lake/pond polygons over point sources there. Its parting instruction was
  to measure the south before deciding anything, and that instruction was right.
- **#97 — Validate NHD flowline stream-crossings as a water-source candidate list**
  measured NHD against the *centerline*: 841 true geometric crossings (568 perennial,
  201 intermittent), against the ~1,100-source completeness benchmark commercial guides
  set. NHD's Spring layer was already known sparse trail-wide (99 points within 5 miles
  of the centerline). Nobody had measured NHD against the *shelters*, which is #529's
  actual frame.

## 1. USGS NHD, measured against all 280 shelters

Method in one sentence: for every shelter in the NPS `ANST_Facilities` shelters layer,
query NHDPlus HR within a 300 m envelope, compute true point-to-geometry distances
locally, classify by FCode, and widen the search (to 5 km, perennial only) where the
envelope is dry — zero failed queries, and an independent recount of six shelters with
separate code matched every distance to the metre. The sanity check writes itself:
Matts Creek Shelter measures 2.3 m from Matts Creek, Rainbow Stream Lean-to 0.7 m from
Rainbow Stream — the data finds exactly the water the shelters are named for.

Coverage: % of the 280 shelters with at least one feature of the class within the radius.

| radius | spring | perennial stream | intermittent | artificial path | lake/pond | flowing (per.+int.) | **any NHD water** | current supply | OSM (NE n=80) |
|---|---|---|---|---|---|---|---|---|---|
| 15 m | 0% | 5% | 0% | 0% | 0% | 5% | 6% | 0% | 0% |
| 30 m | 0% | 8% | 2% | 0% | 1% | 10% | 11% | 1% | 1% |
| 60 m | 2% | 17% | 6% | 1% | 4% | 23% | 29% | 3% | 5% |
| 100 m | 3% | 28% | 10% | 5% | 6% | 37% | 44% | 4% | 6% |
| 250 m | 4% | 44% | 17% | 9% | 11% | **58%** | **65%** | 8% | 8% |

Distance statistics, escalated past the envelope where needed:

- **Every one of the 280 shelters has a perennial NHD stream within 5 km.** Median
  distance 308 m, p90 1,355 m.
- Median distance to the nearest NHD water of any class is 126 m.
- Of the 123 shelters with a perennial stream within 250 m, 68 of those streams carry a
  GNIS name — the card could say *"Stony Brook, 73 m"* (Gren Anderson Shelter's real
  numbers), not just *"a stream"*.

By latitude third, at 250 m — the regional structure the New England OSM bias hid:

| third | n | spring | perennial | intermittent | artificial | lake/pond | any |
|---|---|---|---|---|---|---|---|
| south (34.6–37.4) | 93 | 6% | 46% | 11% | 1% | 2% | 61% |
| mid (37.4–42.2) | 93 | 5% | 32% | 24% | 2% | 3% | 58% |
| north (42.2–45.9) | 94 | 0% | 53% | 16% | 24% | 27% | 76% |

Three readings that matter:

- **NHD's structural distinction is the one #529's honesty question needs.** Perennial
  (FCode 46006) versus intermittent (46003) is exactly the "will this be dry in August"
  axis OSM turned out not to carry at all (zero `seasonal=*` tags in the prior
  measurement). §5 qualifies how far that classification can be trusted.
- **NHD springs do not solve this.** 4% at 250 m confirms #97's centerline finding at
  the shelters. The USGS route to water near shelters is flowlines, not springs.
- **NHD does not know the shelter's *actual* source.** Thomas Knob Shelter's water is
  a walk-to spring every guide lists; NHD's nearest perennial stream is 707 m away
  (Middle Fork Helton Creek). A stream 250 m from the shelter is a true statement that
  is *not* the statement "this is the shelter's water source" — the two claims must not
  be conflated in the UI, and §6 keeps them apart.

## 2. OSM, the completed census — the prior recommendation inverts in the south

The census the issue's comments asked for, done the way they said it wants doing:
Geofabrik state extracts for all fourteen trail states processed locally with DuckDB's
spatial reader, same point-source clause set as the Overpass measurements
(`natural=spring`, `amenity=drinking_water`, `man_made=water_tap`/`water_well`), all
280 shelters, with the NC/TN ridgeline handled by measuring each shelter against its
neighbouring states' extracts too. Recounted three Georgia shelters with independent
queries straight off the raw extract: distances match to the decimetre, and Blood Mtn
Shelter — famously dry, hikers carry water up — correctly shows nothing, which is the
kind of true silence #529 wants preserved.

% of shelters with an OSM point source within the radius:

| region | n | 15 m | 30 m | 60 m | 100 m | 250 m |
|---|---|---|---|---|---|---|
| **whole trail** | 280 | 1% | 5% | 12% | 17% | **26%** |
| south (GA/NC/TN) | 65 | 2% | 5% | 12% | 22% | **40%** |
| mid (VA–NY) | 109 | 0% | 5% | 14% | 20% | 32% |
| New England | 106 | 3% | 6% | 9% | 10% | 11% |

Per state at 250 m: GA 50% · NC 45% · MD 71% (5 of 7) · PA 38% · NJ 29% · VA 26% ·
TN 25% · NY 25% · NH 25% · ME 14% · VT 4% · MA 0% · CT 0%.

So the prior session's "OSM is level with what we have — don't build the fetcher" was
a New England artefact, exactly as its own caveat feared. **Trail-wide, OSM point
sources triple the current supply (26% vs 8%), and in the south they are 40%** —
overwhelmingly real mapped springs (60 of the 73 covered shelters' nearest point is a
`natural=spring`; 11 are `amenity=drinking_water`). The composition finding survives
too, inverted: `natural=water` ponds near shelters are a New England phenomenon, and
`waterway=stream` ways sit within 250 m of 52% of shelters trail-wide — corroborating
NHD's 58% flowing-water figure from an independent database.

What OSM still cannot say: of the 73 shelters' nearest points, six carry any
`seasonal=*`/`intermittent=*` tag and nine carry a name. The reliability axis simply
is not in the data, which keeps §1's point about NHD's perennial/intermittent code
being the only structured seasonality signal available anywhere open.

## 3. What the app has today, for scale

174 water points trail-wide, all from opentrail.org's `w`/`s` icons
([fetch_opentrail.py](fetch_opentrail.py)); 8% of shelters have one within 250 m, and
only 9 water points fold into the 287 POI sites at all. The A.T. Guide claims
~1,127 water sources for the same trail — the completeness benchmark #97 already used.

## 4. Sources that are not map data — the per-shelter answers

All probed live 2026-08-13; response copies were kept during the research session.

**The correction first: `ATX_Ratings` has no water field.** [SOURCE_SURVEY.md](SOURCE_SURVEY.md)
§3a listed "water source" among that layer's fields; enumerating all 40 fields of
layer 17 (and its sibling layers and DEMO/TEST twins) shows there is none. Water
appears only in free-text `notes` — 34 of 413 sites mention it at all, ten of them
parseable ("Spring 0.1 mile", all in the PATC block). Still the best capacity source
found; as a water candidate it is off the list, and §3a now carries this correction.

**ATC's `Campsite_Sustainability_Index` settles the premise and names its own
sources.** Its `Proximity_Water_ft` is populated on all 3,354 sites (edit date
2026-06-02): by ATC's own measurement, **498 of 531 shelters — 94% — have water within
250 m**, which is #529's "the trail is not like that" as a steward's number rather than
an intuition. But the layer stores the *distance*, not the water point, and its
`Nearest_Water_Source` field is provenance: `FarOut` on 1,412 sites, `NHDP_HR_Stream`
on 1,155, `OSA_Field_Estimate` on 533, `NHDP_HR_Pond` on 254. Two conclusions travel
with that: ATC itself has no open water-points layer — **the steward's own best
sources are FarOut and the same NHDPlus HR measured in §1** — and deriving points from
CSI is blocked twice over (unstated ATC terms, and 42% FarOut-derived). What it is
good for: sizing the gap, and validating whatever ships (it joins on `RIMS_ID` and a
2026 A.T. mile).

*Amended 2026-08-13, same day:* **#668 — A shelter card says nothing about water, and
ATC has measured the distance to it** ships the provenance-split reading of the above,
on the maintainer's direction. CSI's **NHD- and field-estimate-derived distances**
publish as `water_distance_ft` and as the card sentence's "water N m" — a proximity
claim as a sentence, exactly the shape §6 argues for, on the `photo_licence` footing
for the ATC-terms half. The **FarOut-derived rows shipped held back** in
[reference/water_distance.json](reference/water_distance.json) with the reason stated
per row, so the call this paragraph flagged stayed a human's.
[build_water_distance.py](build_water_distance.py) holds the join and the rule;
"derived points" stay unbuilt as this section concluded.

*Amended again 2026-08-13, hours later:* the human made the call — the maintainer
declared data ATC publishes reusable ("anything from the ATC is reusable", restated
specifically for the 218 held rows), recorded as sources.json's `atc_licence` block,
and **#688 — Release the FarOut-measured water distances ATC already publishes**
released them: 305 of 512 shelters/campsites now publish a distance. The reading that
authorises: the distance is ATC's own derived fact in ATC's own public layer. What
this amendment does **not** move: the allowlist stays (an unknown future provenance
still refuses until read), the user-created sites stay unpublished (§3b's rule is
safety, not licensing), and option 3's direct-from-ATC confirmation stays the ideal —
now a confirmation rather than a blocker.

**Neither ArcGIS org hides a water layer.** All 146 ATC-org services and all 1,440
NPS-org services were swept for water-ish names; every hit is another park's data
(GRSM's backcountry shelters layer, probed on the off-chance, has no water field
either). That search does not need repeating.

**Clubs and community, qualified for water specifically:**

- **GATC's water PDF**: 65 entries covering all ~79 Georgia miles as
  `mile point | name | distance off trail` — no GPS, no reliability codes, and the
  PDF's embedded title is "GATC Water Update July 2020.xlsx", so the 2026-03 date on
  the file is a re-export of plausibly six-year-old data. A pilot-state candidate
  after an email, and a template for what a club water list looks like.
  *Amended 2026-08-13, same day:* the fetch half exists — **#669 — The maintaining
  clubs publish PDFs nothing fetches, starting with GATC's water sources** registers
  it as a `club_pdf` source and [fetch_club_pdfs.py](fetch_club_pdfs.py) parses the
  65 rows into `data/raw/club_pdfs/` for review and cross-checks (the printed name
  and distance-off columns arrive fused — the PDF's text layer holds no boundary).
  Publication still waits on the email this bullet asks for; the registry entry's
  `licence` field records that gate.
- **WhiteBlaze 2024 shelter PDF**: ~198 of ~240 shelters carry a free-text water
  description ("Water (spring) 80 yards on a blue blazed trail…") — the best
  per-shelter water *prose* found anywhere — but water GPS on only 24 shelters
  (SOURCE_SURVEY.md's "water source GPS" oversold that), reliability words on ~33,
  and "Courtesy of WhiteBlaze Pages ©" on every page. Validation set for an ask;
  never an ingest.
- **State spring inventories — the unprobed open candidates.** Virginia DEQ's Springs
  Database (1,638 sites with inventory dates, improvements, discharge class;
  ArcGIS FeatureServer; terms page needs a manual read) and Pennsylvania's PAGWIS
  springs (2,555 sites, locations flagged approximate). VA and PA are the two longest
  A.T. states; corridor overlap is unmeasured and is the obvious next probe. Tennessee
  has no equivalent. No open community A.T. water dataset exists anywhere — GitHub,
  tnlandforms, nothing; FarOut's comment stream is the de-facto A.T. water report,
  which is precisely the position [DATA_NUDGES.md](../features/DATA_NUDGES.md) is
  designed to answer openly.

**The benchmark:** The A.T. Guide advertises **1,127 water sources** ("potentially
unreliable sources noted") for the trail. OSM's point sources within 250 m of the
trail number 183. Every open source combined is a fraction of what the commercial
guides carry — which is the honest scale of this issue, and the reason the
recommendation in §7 is additive rather than single-source.

## 5. NHD's status, access and licence

Researched against live USGS endpoints 2026-08-13; the load-bearing facts, each
checkable at the cited page:

**NHD is a frozen snapshot, and that is workable.** USGS retired the NHD on
2023-10-01 — still served, no longer maintained, no errata channel; the per-HU4 staged
files on S3 have sat unmodified since late 2023
([usgs.gov/national-hydrography](https://www.usgs.gov/national-hydrography/national-hydrography-dataset)).
USGS's own phrasing is that the static products remain available "for several years
while 3DHP is populated" — a soft end-of-life, so the pipeline should archive the
corridor files it ingests rather than assume the S3 objects are permanent. A frozen
upstream is also pipeline-friendly: fetch once, no freshness question.

**3DHP is not an option for the trail in 2026, and it changes the honesty story
later.** The successor program's only new elevation-derived hydrography so far covers
the Okanogan (WA) and Birch Creek (AK) watersheds — everything else, including the
whole A.T. corridor, is migrated NHD behind a new schema
([April 2026 service update](https://www.usgs.gov/3d-hydrography-program/news/usgs-announces-release-updated-3d-hydrography-program-data-service-and)).
Two schema facts worth recording now: 3DHP's flowline table **drops the
perennial/intermittent FCode entirely**, and its hydrolocation domain keeps a Spring
type. So the FCode this document leans on is a legacy attribute with no successor
until 3DHP reaches the east coast.

*Amended 2026-08-14: measured against the live services, and the paragraph above was
right for a reason it did not name.* Each figure below says where it came from, because
they come from three different places: 3DHP from
`3dhp.nationalmap.gov/arcgis/rest/services/usgs_3dhp_all/FeatureServer`, NHD from
`hydro.nationalmap.gov/.../nhd/MapServer` (layer 6 flowlines, layer 0 points), and the
bulk sizes from TNM Access's product catalogue. The geometry comparison is one
0.2° × 0.2° box on the trail in central Virginia (−79.2,37.5 to −79.0,37.7), both
services queried for everything it intersects:

| | NHD (`nhd` MapServer) | 3DHP layer 50 |
|---|---|---|
| flowlines in the box | 1,265 | 1,265 |
| total length | 775.149 km | 775.149 km |
| total vertices | 36,831 | 36,831 |

Paired 1:1 by position, the worst separation is **0.086 mm** and no pair differs in
vertex count. The springs layer matches the same way: **1,796 features in the corridor
bounding box against NHD's 1,796, every one within 1 m of an NHD spring**, and
17 within 100 m of the centerline either way. The decisive field is 3DHP's own:
every flowline in that box carries **`workunitid` = `NHD`** and `featuredate` 2023.
It is not that 3DHP resembles NHD for the corridor — it reports itself as NHD.

**What a switch would cost today, stated as arithmetic.** In the same box NHD holds
479 perennial + 540 intermittent + 244 artificial path + 2 connector; 3DHP holds
**1,019 Channel Line** + 244 Waterbody Connector + 2 Surface Connector. 479 + 540 =
1,019: the same lines with the distinction deleted. Counted in
`data/raw/trail_water.json`, **935 of the 1,125 crossings the pipeline publishes carry
a flow claim (83%) and 916 of those come from NHD's FCode** — the remaining 19 are
OSM's `intermittent` tag — so migrating now would take seasonality coverage to
whatever OSM alone supplies, which is 19 crossings, and receive identical geometry for
it.

The operational shape argues the same way. NHD ships as 21 HU4 GeoPackages read and
deleted one at a time — **3.13 GB in total, HEAD-measured across all 21 archives on
2026-08-14**; the "~5.7 GB" this file and `fetch_trail_water.py` used to carry was the
largest subregion multiplied by 21 rather than a measurement, and is corrected in both.
3DHP publishes no per-subregion slicing at all, only an annual CONUS file
(**23 GB GeoPackage / 12.5 GB FileGDB**, FY25 published 2025-03-20 and FY26 2026-01-23,
from TNM Access's product listing for a bounding box on the trail).

**So the answer is a watch, not a migration**, and it is now wired rather than
remembered: `sources.json` registers `usgs_3dhp` at kind `watched_only`, and
`check_freshness.py` asks five boxes spread along the trail from North Carolina to New Hampshire
for their distinct `workunitid`. All five answered `NHD` on 2026-08-14. When one stops, USGS has
resurveyed the corridor and this decision is worth re-costing. The honest counterweight
is that NHD's real risk is *availability* rather than correctness — this section already
says the S3 objects should not be assumed permanent — and archiving the 21 files the
pipeline ingests is a cheaper hedge than a 23 GB dependency.

**@unvalidated — the "continuous probability-of-flow estimate".** An earlier version of
this paragraph said 3DHP replaces the FCode with one, published only for the updated
areas. That claim came from USGS's April 2026 news release and **could not be confirmed
in the data**: the service exposes six layers, none named for it, and layer 50's 36
fields hold no flow-probability field (checked 2026-08-14). It may exist in a separate
product, in a release not yet public, or only in the news release's phrasing. What would
settle it is the FY26 CONUS download's schema, or a 3DHP layer covering the Okanogan
where the new hydrography actually exists. **Until then it must not be quoted as the
reason a migration would recover what the FCode gives us** — that is precisely the
sentence a future switch would lean on.

**How far the perennial/intermittent code can be trusted — measured, not vibes.**
The classification descends from the blue lines of 1:24,000 topo quads compiled
between 1947 and 1992, under whatever climate prevailed the survey year. Against
10,055 field observations, NHD permanence classes agreed 80.5% overall — and **dry
observations were five times more likely to disagree than wet ones**, meaning the
errors concentrate exactly where a hiker gets hurt
([Hafen et al. 2020](https://onlinelibrary.wiley.com/doi/abs/10.1111/1752-1688.12871)).
At ~300 *headwater* sites — ridgeline seeps and spring-fed channels, precisely the
water near A.T. shelters — agreement fell to ~50%
([Fritz et al. 2013](https://onlinelibrary.wiley.com/doi/abs/10.1111/jawr.12040)).
USGS abandoning the dichotomy in its successor product is itself the strongest
statement about it. A pin derived from FCode 46006 can honestly say *"USGS mapped
this stream as year-round, decades ago"*; it cannot say *"there is water here."*

**Springs stay a dead end in every federal dataset.** The live NHD Point layer holds
~63 Spring/Seep points within 3 km of the whole trail. GNIS (still maintained,
bi-monthly) has 2,778 named springs across the fourteen trail states but only ~54
within 3 km of the centerline, and a GNIS record carries a name and a coordinate,
nothing about flow. Both counts came from an approximate centerline and want
re-deriving with the real corridor geometry before anyone quotes them further.

**Bulk access is the pattern the pipeline already runs.** The same anonymous
`prd-tnm.s3.amazonaws.com/StagedProducts/...` bucket `fetch_elevation.py` and
`fetch_topo_quads.py` pull from serves hydrography: NHD per-HU4 GeoPackages at
`StagedProducts/Hydrography/NHD/HU4/GPKG/NHD_H_{hu4}_HU4_GPKG.zip`, NHDPlus HR
FileGDBs under `.../NHDPlusHR/VPU/Current/GDB/` (some filenames embed a snapshot
date — discover by prefix listing, don't construct). The corridor spans **21 HU4
subregions** (Springer's Etowah headwaters to Katahdin's Penobscot), ~3.1 GB as NHD
GeoPackages or ~4.6 GB as NHDPlus HR GDBs; one trap: the Lake Champlain drainage old
references call 0201 "Richelieu" is staged as **0430 "Middle Saint Lawrence"**. The
`hydro.nationalmap.gov` ArcGIS services (what the spike used) carry no published rate
limit but also no uptime promise — USGS explicitly says to plan a fail-over, which
matches the 503s `lib/http_retry.py` already exists for. Bulk work should use the
staged files; the services are for spot checks.

**Licence: public domain, whole column.** NHD, NHDPlus HR, WBD, 3DHP and GNIS are US
government work; USGS requests (not requires) the credit line "Map services and data
available from U.S. Geological Survey, National Geospatial Program" — one line in the
app's data credits covers hydrography alongside the US Topo and 3DEP data already
shipped.

## 6. How each option lands in this codebase

Verified against the code on 2026-08-13 (file references below are the load-bearing
ones; the client work for all of this is already built):

- **Water points ride the existing `water` POI type.** No new poi_type, no
  `verify_release.py` change, no client release: a water badge on the site pin, a
  `Water · N ft` chip on the shelter card, and the "Nearby: … water N ft" sentence
  all exist today and are starved of data, not code (`client/src/map/poiSites.ts`,
  `client/src/chrome/PoiCard.tsx`, `export_poi.py`'s `attach_nearby`). A new source is a
  fetch script on the `fetch_opentrail.py` pattern plus one loader loop in
  `export_poi.py` beside the opentrail one, plus freshness/baseline wiring
  (`check_freshness.py`, `check_output_quality.py`'s `COUNT_UPSTREAM_SOURCES`).
- **The fold gate is the catch: 60 m.** A water point folds into a shelter's site by
  proximity at `PROXIMITY_RADIUS_M = 60` (`lib/poi_sites.py`) — name matching (150 m)
  will not fire for a spring that does not share the shelter's name. Real springs often
  sit 60–250 m out: points alone put pins *near* shelters while most shelter cards stay
  silent. Widening the gate for water specifically is a product decision this document
  flags and does not make.
  *Amended 2026-08-13:* it stopped being a catch and became the mechanism. The
  100 ft match radius `fetch_trail_water.py` uses sits **inside** that 60 m fold
  deliberately, so a derived water point needs no second association rule — it is
  published at its real coordinates and the existing grouping puts it on the
  shelter's pin. A match the map could not draw would be a match in name only. *(Measured 2026-08-13 while #694 was scoped: against today's
  174 opentrail points, widening 60 m → 150 m folds in exactly zero additional water
  members — the decision only becomes live once the OSM points land, and wants
  re-measuring then.)*

*Amended 2026-08-13 (#694 — A card can promise water 37 m away while its site shows no
water at all):* the CSI distance now also materialises as a **synthesized site member**
— `source: "atc_csi"`, `CONFIDENCE_LOW`, inheriting the anchor's own coordinates because
ATC states how far and never where. The maintainer made the call, and the guards keep it
inside this document's claims taxonomy: a member draws no pin of its own (#524), so the
inherited location is never drawn as a dot where water is not; its description states
the distance, the measurement's owner, and that the spot is unmapped; the card's chip
prints the stated figure rather than measuring the inherited coordinates to zero; only
sites whose Nearby sentence fired (≤150 m) get one; and a site holding a **real** mapped
water point never does — the synthesized member stops being produced the export after a
real point folds in, so options 1's OSM points supersede it site by site as they land.
Justification, measured: of the 247 spliced cards, 16 have any real water point within
150 m today, so no fold-gate setting could have closed the gap.
- **A per-shelter sentence is pipeline-only.** The card renders `description` for every
  type already; `DESCRIBERS` simply has no water entry. *"Nearest mapped stream:
  Stony Brook, about 70 m (USGS, mapped as year-round)"* is a change confined to
  `export_poi.py` — no client work, no new column, and it reaches all 280 shelter cards
  regardless of the 60 m gate.
- **`crossing` is fully plumbed and intentionally empty.** Client icon, legend row,
  collision priority and card all ship today (`config.ts` says it "starts working the
  day the pipeline fills it"). Filling it needs the #97 intersection computation (not a
  point source — `unify_poi` takes Points, so crossings are computed then unified),
  plus flipping the three allowed-to-be-zero gates (`export_poi.py`,
  `check_output_quality.py`, `verify_release.py`) so a broken NHD fetch stops looking
  like the old intentional emptiness, plus a deliberate decision on
  `fetch_poi_images.py`'s existing `crossing: 300` radius before the Commons crawl
  starts paying for 841 crossings.
- **Confidence and seasonality surfaces exist; a third tier does not.** `low`
  confidence draws the dashed "nobody has confirmed this exists" rim and the card
  sentence; anything unknown normalises to `low` in old clients (`trailData.ts`), so
  additive evolution is safe. Water reliability *over time* is already designed as
  hiker-report territory — [DATA_NUDGES.md](../features/DATA_NUDGES.md)'s one-tap
  flowing/trickling/dry loop and [FIELD_NOTES.md](../features/FIELD_NOTES.md)'s dated
  observations — and FEATURES.md names NHD's perennial/intermittent code as an input to
  the eventual prediction, which is a reason to keep those attributes whatever ships.

## 7. The options, ranked

The frame the numbers force: ATC's own measurement says 94% of shelters have water
within 250 m; the best open point source reaches 26% of shelters; NHD reaches 58%
with *streams* that are true but are not "the shelter's source"; and nothing open
carries reliability. So no single source closes #529, and the honest shape is
additive — points where a point is true, a sentence where only proximity is true,
and hiker reports as the only eventual answer to "is it flowing".

1. **OSM point sources into the existing `water` type** — *medium effort, biggest
   honest win, recommended first.* One fetch script (Geofabrik extracts, the shape
   the census already proved) + one loader loop, `CONFIDENCE_LOW`, ODbL already
   complied with. Takes shelters-with-a-mapped-point from 8% to ~26–30% (the two
   supplies overlap but not fully), concentrated in the south where the current data
   is thinnest. Each pin is a mapped spring or tap — a claim a hiker can verify at
   the spot. The prior session's "don't build it" was answered by its own missing
   sample: at 40% in the south, the fetcher earns its place.
   *Amended 2026-08-13: built.* `fetch_osm_water.py` reads the same fourteen
   extracts the basemap build downloads (7,574 point nodes on the first full
   scan); `export_poi.py` folds them in at `low`, dropping each point within
   25 m of an opentrail water point as the same OSM node arriving twice — a
   radius measured before it was chosen (41 of opentrail's 174 water points
   have a twin inside it; the tail past it is real neighbours). The corridor's
   water layer goes from 174 features to 1,705.
   *Amended 2026-08-18 (#749): gated on reachability, and the gate is severe.*
   The 30-mile corridor was the only geographic filter between the scan and a
   hiker's screen, so the claim a pin made — *there is water here* — was true of
   a drinking fountain in a town park eight miles east.
   [build_osm_water_reach.py](build_osm_water_reach.py) now applies option 2's
   own two gates to this source: within **100 ft** of the nearest of the
   centerline, any side trail, any shelter or any campsite (a union of three,
   the maintainer's decision of 2026-08-17), and under a **15% grade** from
   3DEP elevations at both ends. Measured the same day, against 7,593 nodes
   across the fourteen states:

   | | |
   |---|---|
   | OSM water points inside the corridor | 1,576 |
   | clear the 100 ft union gate | 146 (9.3%) |
   | of those, refused by the grade gate | 61 (41.8%) |
   | **publish** | **85 (5.4%)** |

   **The clutter was the far points, and that was not assumed.** Only 232 of the
   1,576 are within 0.2 mi of anything a hiker walks; 1,159 are more than five
   miles away. So 1,344 of the 1,430 removals are points no radius argument
   would defend, and the contested band is the 86 between 100 ft and 0.2 mi —
   **55 of them springs**, which is the class §7's own guide comparison found
   OSM was the only cover for. Near-trail springs go from 176 to 121.
   `spike_osm_water_gate.py` is the census; every rejected point keeps its
   distance, drop, grade and reason in `data/raw/osm_water_reach.json`, so
   either gate can be re-argued from the file.

   **The grade gate misfired at very short range**, and did so in `main` for a
   day. Grade is drop ÷ distance, and where the nearest feature is the trail the
   spring sits beside, the denominator is a few feet: a spring **0.26 m from a
   side trail** with a 0.4 ft drop was refused as "a 39% grade, which is a
   scramble rather than a walk". 12 of the 61 refusals have a total walk under
   5 ft. `fetch_trail_water.py` already named this failure — *"two points a foot
   apart are the same place, and a grade computed from that is noise rather than
   terrain"* — but its `max(distance_ft, 1.0)` only guarded division by zero,
   and in its own context the nearest point on a stream is rarely a foot from a
   shelter, so it never bit. The remaining ~49 refusals look defensible (median
   grade 0.24 over runs of 10–100 ft).

   *Amended 2026-08-19 (#815): the floor is a minimum run of 10 ft.* Below it
   `grade_gate()` declines to have an opinion about steepness, and the two
   sources share that one function rather than restating it. **The value is
   picked against the distribution above and not against a fresh run** — the
   band between 5 ft and 10 ft is empty, so every floor in [5, 10] ft rescues
   the same 12 points and still grades the same ~49. 10 ft is the top of the
   band and the maintainer's pick. Points the floor carries are flagged
   `grade_floored` in the output, so the rescued set stays countable.

   **@unvalidated — what the shape of that floor costs.** A minimum *run*
   declines to grade a short walk at all, so a water point 3 ft from the trail
   at the top of a 40 ft bank now passes ungraded: the one case where a short
   run's ratio was telling the truth. A minimum *drop* was the alternative and
   has no such hole, since a real bank keeps a real drop and stays graded; the
   run was the maintainer's choice (2026-08-19) with that trade on the table.
   What would settle the cost is re-running `spike_osm_water_gate.py` with the
   floor in place and reading the drops of the sub-10-ft runs it rescues — if
   they are all a foot or two, the hole is theoretical. Nobody has counted them,
   and the counts in the table above predate the floor.
2. **The per-shelter nearest-stream sentence from NHD** — *small effort, closes the
   silence for everyone.* A describer entry in `export_poi.py` composing, for every
   shelter, *"Nearest mapped stream: Stony Brook, about 70 m (USGS; mapped as
   year-round, not recently verified)"* from §1's data — GNIS name where one exists
   (68 of 123 within 250 m), "mapped as seasonal" where the FCode says intermittent,
   distance always. This is a proximity claim, deliberately not a pin: it reaches all
   280 shelter cards including the 74% no open point source covers, and it cannot
   assert "there is water here" — §5's error literature is the reason that wording
   is load-bearing. Blood Mtn stays honest: "no mapped stream within 1 km" is also a
   sentence worth printing.
   *Amended 2026-08-13, and the amendment replaces the option rather than
   completing it.* This shipped first as a nearest-stream sentence on every
   shelter card, out to a kilometre. **The maintainer rejected the shape, and
   was right to**: a stream 700 m away is a true fact about the map that says
   nothing about the shelter, and a card printing it answers a question
   nobody asked. What replaced it is narrower and load-bearing —
   [fetch_trail_water.py](fetch_trail_water.py) publishes a water POI for a
   site only where a hiker could actually reach it: **within 100 ft AND under
   a 15% grade**, the second gate measured from real 3DEP elevations at both
   ends, because a stream 90 ft away and 120 ft below is not a water source
   however close the map says it is. Both numbers are the maintainer's, and
   the reasoning behind the tight radius is worth recording: **most A.T.
   shelters have had their own spring built out over decades**, so the water
   a shelter actually uses is a piped source somebody dug rather than the
   nearest blue line — which is why ATC's own measured distance (§4, #668)
   stays the better answer for shelters and this derivation only fills in a
   real coordinate where geometry can honestly supply one. Rejected candidates keep their numbers
   in the file so either gate can be re-argued from data. The same script
   fills `crossing` from exact trail×stream intersections — water a hiker
   walks straight through — which is the other half of "show the water that
   meets the trail or a POI". Streams come from **both** hydrographies,
   merged: USGS classifies flow — the one structured answer anywhere to "will
   this be dry in August", and §1's whole reason for measuring NHD — while OSM
   more often carries the local name and is edited by people who walk there.
   A crossing deduped across the two keeps whichever half each supplied and
   attributes the flow claim to whoever made it, per
   [features/POI_DEDUPLICATION.md](../features/POI_DEDUPLICATION.md)'s
   combine-don't-drop rule. USGS arrives as bulk staged GeoPackages, one
   subregion at a time: its query service 504s under corridor-scale load (the
   failure that killed two publish runs, ELEVATION_SOURCES.md), and a
   derivation nobody can re-run is not one anybody can check.
3. **The ATC ask, extended by one question** — *no code, unblocks the ceiling.* The
   combined ask SOURCE_SURVEY.md §10 already plans (capacity, Helene, half-mile
   points) should add: CSI shows per-site water distances sourced from FarOut and
   NHD — does any ATC/club water-*points* inventory exist, and on what terms? CSI
   itself, licence permitting, is the validation set for options 1–2 via `RIMS_ID`.
4. **VA DEQ + PAGWIS corridor probe** — *small spike, possibly a second point
   source.* ~4,200 structured spring points across the two longest trail states;
   overlap with the corridor unmeasured. If a meaningful fraction lands near the
   trail, these are open(ish) *state* inventories that fill exactly the mid-trail
   band where OSM is mediocre (VA 26%). Licence pages need human eyes first.
5. **NHD stream crossings (#97)** — *large, worth it for planning, not for #529.*
   The crossing layer answers "where does the walking route meet water", which is a
   hike-planning question; the client is already finished for it. #97's two
   validation steps stand, now with §5's status facts attached (frozen snapshot,
   fetch the 21 HU4 staged files once, keep the FCode attributes for the eventual
   reliability model). It should not be sold as the fix for shelter cards.
   *Amended 2026-08-14: validation step 2 is done, and it holds.*
   [spike_guide_water_check.py](spike_guide_water_check.py) measured the 1,125
   shipped crossings against the 980 water-tagged rows in the maintainer's own
   copy of The A.T. Guide, both placed on ATC's half-mile points and the two
   mileages aligned by an offset measured from the guide rows that print
   coordinates (median +0.51 mi, drifting −0.75 to +0.79 — which is why the
   alignment interpolates rather than applying one shift). **Two thirds of the
   guide's stream rows (302 of 460) have one of our crossings within 0.2 mi**,
   computed from hydrography that has never seen the guidebook: that is the
   positional confirmation the issue wanted, and it bears on step 1 too, since a
   centerline systematically misaligned against the hydrography would not agree
   with a third source this often. **Springs sit at 10% and cannot do better** —
   a spring does not cross the trail, so a crossing cannot find one by
   construction, and the 37% any OurHike water reaches there is OSM's points
   doing the work. **60% of our crossings are not guidebook water**, which is
   this issue's own "minor unnamed streams no guidebook would list" measured
   rather than feared, and the argument for publishing them as `crossing` and
   never as water pins. Step 1, the visual inspection, is still open. The guide
   is copyright AntiGravityGear, LLC and none of it is committed, published or
   folded into our data — §8 of [SOURCE_SURVEY.md](SOURCE_SURVEY.md) is
   unchanged, and what the spike writes down is statistics about *our* data.
6. **What not to build:** an NHD/GNIS springs fetch (4% / ~54 points — measured
   dead ends), anything derived from CSI's distances without an authorisation on
   record — first narrowed 2026-08-13 to ship the NHD- and field-estimate-derived rows
   (#668), then resolved the same day when the maintainer's declaration released the
   FarOut-measured rows too (#688, sources.json `atc_licence`; §4's amendments hold
   the sequence) — and any scrape of WhiteBlaze, FarOut or The A.T. Guide, which the
   CSI release does not soften: taking ATC's published number is not a licence to
   touch the app it was measured against.

**On the honesty question the issue says must be settled with the sourcing:** the
two-tier confidence channel is enough. Every water point from options 1 and 4 enters
at `low` — the dashed rim plus the card's existing "Unverified — nobody has confirmed
this one is really there" sentence — with seasonality carried in `description` when
the source says it ("mapped as seasonal"). Proximity-only knowledge (option 2) never
becomes a pin at all. Reliability over time — flowing *today* — belongs to
[DATA_NUDGES.md](../features/DATA_NUDGES.md)'s one-tap loop, with NHD's
perennial/intermittent code kept as an input to the prediction FEATURES.md already
sketches, not shown as a promise. A dry August at a `low`-confidence spring pin whose
card says "mapped as seasonal" is a hiker warned, not a hiker lied to.

*Amended 2026-08-15 (#716 — Nothing tells a hiker the water is running low, and 206 miles
of the trail are in severe drought today):* "nothing open carries reliability" was true of
every source measured above, and it is **not** true of the hydrology and drought column
those measurements never reached. USGS gauge percentiles, NOAA's National Water Model and
the U.S. Drought Monitor all publish a current, free, trail-locatable low-water signal —
206 miles of the trail are in severe drought as this is written.
[WATER_CONDITIONS.md](WATER_CONDITIONS.md) holds those measurements. What does **not**
change is the sentence this paragraph is really making: none of them observes a spring,
so "is *this* source flowing" still belongs to
[DATA_NUDGES.md](../features/DATA_NUDGES.md)'s one-tap loop, and the new sources answer
the regional question instead.
