# Org coverage, org by org and type by type — a dated survey (October 2026)

Companion to [POI_COVERAGE_SURVEY.md](POI_COVERAGE_SURVEY.md) and
[ALERTS_NOTICES_SURVEY.md](ALERTS_NOTICES_SURVEY.md) (the same reconnaissance for five
orgs and two data types, in August), [SOURCE_SURVEY.md](SOURCE_SURVEY.md) (where the first
orgs' trail data came from) and [../features/ORG_BULK_LOAD.md](../features/ORG_BULK_LOAD.md)
(what the catalogue's `load` verdicts mean).

**The row-level data was `reference/org_coverage.json`:** one row per organisation × data
type, 2,670 rows, each with its status, evidence, grade and note. This file is the narrative over
it. Neither file decides anything. Phase 1 of **#1793 — Rebuild the data platform as dlt → dbt:
seven contracted marts, a monthly refresh, published docs, and lighter phone downloads** wrote the
`pipeline/extract/<club>/` files from the JSON. Decision 88 (`pipeline/ELT.md`, 2026-10-06) then
retired the JSON and moved every note into one file,
[`extract/not_available.toml`](extract/not_available.toml), which is now the one home of what
each managing club does not publish; a club's resource files stay in its folder. git keeps the
JSON: `git show bcc70dd0:pipeline/reference/org_coverage.json`, which is what a citation of it
below means.

Written 2026-10-01 from live probes made that day. It is kept in the tense it was written in.
Every count is the audit's own, taken from public metadata on 2026-10-01; none was re-taken
for this file.

## What was asked

The maintainer, 2026-10-01, unprompted (decision 15 in that issue's planning log): *"Part of
this work should recheck that each org has all the potential data loaded. I think a lot of the
orgs have data available that we haven't included yet."* Asked when, the maintainer chose
**now, in this plan**.

Three decisions shape what "each org" and "all the data" mean:

- **Decision 12:** *"I think it would be better to have 1 folder per org. Then in each folder,
  there should always be the same # of files, 1 for each data type being extracted. If that
  datatype isn't available, then the file should have the note detailing when that was
  confirmed."* So the survey is a census by data type, and a NOT_PUBLISHED row is the text of a
  future dated note.
- **Decision 13:** the club file set is `trail_lines`, `points_of_interest`, `elevation`,
  `closures`, `warnings`, `places`, `suggested_hikes`, `podcasts`, `challenges` and `photos`,
  plus `org.py`. Those ten types are the survey's columns.
- **Decision 14:** *"we should probably add data checks to make sure each of the different
  file types have been created."*

Round 5 widened the scope part-way through. The first audit covered only the 30 providers in
`sources.json`, and the maintainer interrupted it: *"We have more than 7 clubs now. Are you
missing the others? We also didn't load all the clubs at your urging. We should just load ALL
the clubs now and handle any deduplication after the extract-load."* So the survey covers all
173 rows of `reference/trail_orgs.json`, built under **#1543 — 165 trail organizations exist
and the registry knows 14, with no way to load the rest that does not cost one pull request
each**.

The same relayed request added the candidate trails: *"Check the 153 candidate trails in
trail_candidates.json. Check that those haven't already ran before doing the audit."*
`reference/trail_candidates.json` lists 153 trails of 40 miles or more that the emblem
catalogue does not carry. 103 of them have a steward who is not in `trail_orgs.json`: 95
stewards, all surveyed here. The other 50 have a steward who is; §9 says whether that
steward's survey reached each trail.

Round 8 came last, and it changes how every licence line below reads:

- **Decision 20** (*"DEC is allowed if it is part of their GIS clearinghouse"*) and
  **decision 22** (*"And the same goes for OPRHP"*): a NYS DEC or NYS OPRHP dataset listed in
  the NYS GIS Clearinghouse may be published. These are maintainer decisions, not grants. The
  items' own `licenseInfo` still says "not for distribution", and that text stays quoted beside
  the decision.
- **Decision 21(a):** a GIS layer an org publishes itself on a public endpoint is presumed
  reusable with attribution (`licence_basis: public_gis`). Explicit restrictive text is still
  extracted and staged, and goes to the maintainer as **one batched question** (§6). The
  presumption does not reach photographs, podcast audio or page prose (Reasoned in the log,
  not decided).
- **Decision 21(b):** *"Make sure for all of these orgs that you dont give up to easily."* No
  GIS-shaped row is accepted as NOT_PUBLISHED until a fixed checklist has been worked (§2).

---

## 0. The matrix

**Status by data type.** 267 row sets: the 173 catalogue orgs, 92 candidate ids, and two
USFS units that carry candidate trails (§8).

| type | LOADED | AVAILABLE_NOT_LOADED | NOT_PUBLISHED | UNKNOWN |
|---|---:|---:|---:|---:|
| trail_lines | 116 | 128 | 20 | 3 |
| points_of_interest | 30 | 209 | 17 | 11 |
| elevation | 2 | 57 | 188 | 20 |
| closures | 13 | 208 | 33 | 13 |
| warnings | 7 | 217 | 33 | 10 |
| places | 21 | 226 | 15 | 5 |
| suggested_hikes | 2 | 205 | 50 | 10 |
| podcasts | 0 | 57 | 196 | 14 |
| challenges | 0 | 151 | 101 | 15 |
| photos | 19 | 42 | 166 | 40 |
| **all** | **210** | **1,500** | **819** | **141** |

**Status by org kind** (the catalogue's `type` column; candidates as their own kind):

| kind | orgs | LOADED | AVAILABLE | NOT_PUBLISHED | UNKNOWN |
|---|---:|---:|---:|---:|---:|
| candidate steward | 92 ids | 36 | 573 | 265 | 46 |
| regional_nonprofit | 54 | 29 | 299 | 192 | 20 |
| at_club | 30 | 93 | 117 | 90 | 0 |
| nht_org | 21 | 1 | 172 | 32 | 5 |
| nst_org | 13 | 16 | 82 | 22 | 10 |
| route_only | 13 | 0 | 24 | 96 | 10 |
| state_clearinghouse | 12 | 15 | 74 | 27 | 4 |
| national_umbrella | 12 | 0 | 23 | 56 | 41 |
| federal | 7 (9 row sets) | 9 | 73 | 7 | 1 |
| state_agency | 7 | 10 | 45 | 12 | 3 |
| aggregator | 3 | 0 | 12 | 17 | 1 |
| land_trust | 1 | 1 | 6 | 3 | 0 |

What the matrix says, counted from `bcc70dd0:pipeline/reference/org_coverage.json`:

- **The maintainer's guess holds.** 254 of 267 row sets have at least one AVAILABLE_NOT_LOADED
  type. Only 11 have nothing but NOT_PUBLISHED and UNKNOWN: four national umbrellas, six
  route-only trails, and Volunteers for Outdoor Colorado.
- **Closures and warnings are the biggest gap, and they are the safety types.** 208 org ×
  closures rows and 217 org × warnings rows are AVAILABLE_NOT_LOADED. 13 and 7 are LOADED.
- **LOADED is concentrated.** 93 of the 210 LOADED rows are A.T. clubs, nearly all arriving
  through ATC's layers.

Three things the AVAILABLE column is **not**, so nobody reads it as more than it says:

1. **Not licensed.** AVAILABLE means the data exists publicly. Whether OurHike may publish it
   is the `sources` mart's `may_publish`, decided by decisions 20–22 and §6.
2. **Not always the org's own.** 144 AVAILABLE status cells across the audit and persistence
   tables say "via" another folder: a land manager or partner publishes data about this org's
   trail (counted by pattern over the files, superseded cells included).
3. **Not always machine-readable.** Pages and PDFs count. At most 791 of the 1,500 AVAILABLE
   rows name a machine-readable format in their evidence. That is a keyword count and an upper
   bound, because a row that says "ArcGIS: 0 results" matches too (Reasoned).

---

## 1. Method

### The batches

| batch | scope | row sets | skeptic pass | file last written (UTC) |
|---|---|---:|---|---|
| b1_atc | ATC | 1 | yes | 04:26 |
| b2_nynjtc | NYNJTC | 1 | yes | 04:25 |
| b3_nys_dec | NYS DEC | 1 | yes | 07:42 |
| b4_oprhp_mohonk_gatc | OPRHP, Mohonk Preserve, GATC | 3 | yes | 07:58 |
| b5_nyc_nj_ct_ma_pa | NYC Parks, NYC DOT, NJDEP, CT DEEP, MassGIS, PASDA | 6 | yes | 08:33 |
| b6_federal | NPS, USFS, BLM | 3 | yes | 04:24 |
| b7_long_trails_states | 12 long-trail and state providers | 12 | yes | 07:54 |
| c1–c3 | A.T. clubs, north to south | 28 | yes | 07:43–07:52 |
| c4–c8 | regional nonprofits | 52 | yes | 07:48–08:17 |
| c9_federal_state_rest | the remaining federal and state rows | 8 | yes | 04:03 |
| c10_nst_rest | National Scenic Trail orgs | 9 | yes | 07:57 |
| c11_nht | the 21 National Historic Trail orgs | 21 | **no** | 03:42 |
| c12_umbrella_route_aggregator | umbrellas, route-only trails, aggregators | 28 | **no** | 04:03 |
| c13–c21 | the 95 candidate stewards, by region | 94 | yes | 07:46–08:39 |
| p01–p10, q01, r01 | persistence pass (§2) | 202 rows | — | 08:44–09:20 |

### How each batch ran

- **Survey, then skeptic.** One agent surveyed each batch. A second agent, the skeptic, was
  told to *"assume it missed things"*: look harder at every NOT_PUBLISHED and UNKNOWN row,
  confirm every LOADED key exists in `sources.json`, and spot-check one URL per
  AVAILABLE_NOT_LOADED row. It edited verdicts in place, marked "(changed by skeptic: …)", and
  its verdict wins. 136 rows in `bcc70dd0:pipeline/reference/org_coverage.json` carry that mark. The 23 skeptic sections
  that count their verdict changes total 120; b1, b2 and b4 list theirs without a number.
- **Four statuses**, defined in the JSON's `_statuses`. The rule the workflow repeated in every
  prompt: *"Never round UNKNOWN down to NOT_PUBLISHED: a false 'not published' stops the next
  person looking."*
- **Etiquette.** Metadata, counts and pages only: `?f=json`, `returnCountOnly=true`,
  `outStatistics` group-bys, one `resultRecordCount=1` attribute sample, item `licenseInfo`,
  sitemaps, feeds. No feature download. A few requests per second per host at most; robots.txt
  and Crawl-delay honoured once read. Walls and logins were recorded, never routed around
  (§5).
- **What "Measured" means here:** the auditor queried it on 2026-10-01 and the figure can be
  fetched again. It is a count of features in a public service on that day. It is **not** a
  count of what reaches a phone, not a check of positional accuracy, and a licence is "read"
  only as far as the item's own text goes. A few Measured rows rest on WebFetch's summarising
  model or a search index; their `grade_detail` says so.

### Runs that were lost and redone, said plainly

- **The first registered-provider run was lost to an interrupt.** The maintainer's Round 5
  message stopped it while it covered only the 30 `sources.json` providers. It was rerun as
  b1–b7, beside the new c-batches.
- **Most skeptic passes were rerun after a usage limit.** The orchestrating session reports
  that a usage limit stopped the first round of skeptic passes, and the file times agree: b1,
  b2, b6 and c9 finished both passes before 04:30 UTC, and every other skeptic section was
  written between 07:42 and 08:39 UTC (Reasoned from the times plus the session's
  account). c19's survey is itself a rerun: its file says an earlier attempt fetched pages from
  04:00 to 04:26 UTC and wrote nothing.
- **c11 and c12 have no "## Skeptic pass" at all.** The workflow marked both batches light
  and skipped the second agent for them. Their 49 orgs' verdicts are one agent's. c12 was also
  left out of the persistence pass (§2), so its rows had neither second look.

### Constraints met on the way

- **The session's 200-call WebSearch budget ran out** part-way through b5, c4, c8 and c18.
  Those rows rest on direct fetches, and say UNKNOWN or `@unvalidated` where that left a gap.
- **data.gov's CKAN API is gone.** `catalog.data.gov/api/3/action/package_search` answers
  `404 {"message":"Not Found"}`; the catalogue now answers JSON at `catalog.data.gov/search?q=`
  (Measured by six persistence batches).
- **The NPS Data API's `DEMO_KEY` ran out within each batch** (`x-ratelimit-limit: 10`). A
  production fetch needs a registered api.data.gov key.
- Several batch files carry an aside about the dbt version. Decisions 17 and 19 settled it as
  dbt-oss 2.0.5 everywhere, one version, and decision 32 then moved that one version to the
  full `dbt` 2.0.6.

### From markdown to rows

`merge_coverage.py` parsed every org table into one row per org × type, with the persistence
verdict replacing the audit's. Two parse defects were repaired before
`bcc70dd0:pipeline/reference/org_coverage.json` was written, and neither changed a status: cells holding an escaped `\|`
had been split mid-text (15 rows, plus one with an unescaped pipe fixed by hand), and c18's two
USFS tables (George Washington & Jefferson NF, Mount Rogers NRA) had overwritten each other and
the national USFS elevation row. The JSON
keeps all three USFS row sets apart with a `scope` field. Every email address, phone number,
personal ArcGIS account name and named private individual was replaced by a description.

---

## 2. The persistence pass (decision 21b)

**Rows checked: 202. Rows flipped: 148 (73%).** In `bcc70dd0:pipeline/reference/org_coverage.json` 203 rows carry
`persisted: true`, because q01's one USFS elevation verdict covers both USFS candidate-trail
scopes.

**Which rows.** `build_persist.py` took every NOT_PUBLISHED or UNKNOWN row of a GIS-shaped type
(`trail_lines`, `points_of_interest`, `places`, `closures`, `warnings`; `elevation` only for
federal, state-agency and clearinghouse rows), from every batch but c12. p01–p10 were built at
08:04 UTC from the batches complete by then. q01 (b5, c8, c18) and r01 (c19) took the four
batches whose skeptic passes were still being written.

| batch | rows | | batch | rows |
|---|---:|---|---|---:|
| p01 | 19 | | p07 | 18 |
| p02–p06 | 18 each | | p08–p10 | 18 each |
| q01 | 15 | | r01 | 6 |

By type: closures 58, warnings 50, places 39, points_of_interest 29, trail_lines 14,
elevation 12. The batches that gave up most often were c5 (32 rows), c6 (25) and c7 (17).

**The checklist**, worked and written down in a "Tried:" list on every row:

1. Every ArcGIS REST root on the org's and its parent agency's hosts (`/arcgis`, `/arcgis2`,
   `/arcgis_image`, `/server`, `/gis`), every folder. WDNR's DEM sat under `/arcgis_image`.
2. ArcGIS Online search by name, acronym, trail, then owner and orgid; Hub search; every
   item's `licenseInfo`.
3. The state GIS clearinghouse for every state the trail crosses.
4. The land manager under the trail: USFS, NPS, state parks or forests, county, MPO.
5. data.gov and Socrata.
6. Files on the org's own site: GPX, KML, KMZ, GeoJSON, Google My Maps exports, GeoPDF.
7. For closures and warnings: conditions pages, RSS, WordPress categories, status APIs.

**What came out:**

| audit said | persistence said | rows |
|---|---|---:|
| NOT_PUBLISHED | AVAILABLE_NOT_LOADED | 112 |
| UNKNOWN | AVAILABLE_NOT_LOADED | 23 |
| NOT_PUBLISHED | LOADED | 11 |
| UNKNOWN | LOADED | 2 |
| NOT_PUBLISHED | NOT_PUBLISHED | 37 |
| UNKNOWN | UNKNOWN | 17 |

**Most flips are other organisations' data.** The pass counted a row AVAILABLE when a land
manager or partner publishes that type for the org's ground, and named that publisher's folder
in the note. At least 59 of the 135 AVAILABLE flips say so in the status cell itself; p07
reports that all 16 of its flips are other organisations' data, and p10 that 16 of its 17 are.
**The batches did not read this rule the same way.** p10 notes that p09 used the stricter
reading (only the org's own output counts) for the Tennessee Trails Association. The rule
needs one reading before the NOT_AVAILABLE notes are written (Reasoned).

**What the pass found that nothing else had:** the USFS R3 forest-order layer and R4's
full copy on the Forest Service's own server (§4), the 339 closed USFS sites that ship as open
pins (§3a), GSMNP's own closed-trail layer, and
the Paumanok Path drawn whole by Suffolk County (744 segments, 118.63 mi, against about 18 mi
loaded today).

**What it did not check**, by its own selection rule:

- **c12's 132 GIS-shaped give-up rows.** Umbrellas and route-only trails get no club folder
  (decision 18), so no NOT_AVAILABLE note will quote them. The aggregators `osm`, `outerspatial`
  and `avenza` are among them.
- **182 elevation rows for non-agency orgs.** Clubs rarely publish a DEM and USGS 3DEP covers
  the ground, but decision 21(b) names elevation as GIS-shaped, so these rows have not met its
  bar.
- **No photos, podcasts, challenges or suggested_hikes row**, by design: they are not GIS.

---

## 3. Findings that change records already in the repository

### 3a. Wrong on a hiker's screen today

| what ships | what is true | from |
|---|---|---|
| `usfs_trails` draws "TUSCARORA - DOLL RIDGE" (3.7 mi, GWNF), `reaches_hikers: true` | PATC's `hikethetuscarora.org/updates` says the section is closed for loss of landowner permission, with a 7-mi road detour. Whether the current release's file holds the segment is `@unvalidated` | c2 |
| Overmountain Shelter, capacity 20 (`shelter_capacity.json`, ATC `ANST_Facilities/4`) | Dismantled November 2023 (TEHCC wiki; USFS NEPA decision 2023-11-08) | c3 |
| Cherry Gap Shelter, capacity 6 | Destroyed by Hurricane Helene; hikers tent at the former site | c3 (skeptic) |
| 501 Shelter, capacity 12 | Retired November 2025; no camping in or around it (BMECC). The closure itself does ship | c2 |
| `atc_updates.json` lists James Fry and Limestone Spring shelters closed | ATC withdrew both pages (404); MCOMD posted James Fry reopened 2026-09-24. Four newer updates are missing, including the Shenandoah backcountry camping closure at NOBO mile 918. Two entries in `atc_updates_proposed.json` now 404 | b1, c2 |
| `usfs_rec_sites`: 339 campgrounds, trailheads and viewpoints marked CLOSED ship as ordinary pins | Filed as **#1803 — 339 USFS campgrounds, trailheads and viewpoints the Forest Service marks CLOSED ship as ordinary pins, because nothing reads seasonal_operational_status** | p10 |
| `nps_trails`: every GRSM row reads `TRLSTATUS='Existing'` | The park's `GRSM_TRAILS` marks 12 segments Closed, 10 Caution and 3 "Warning (Bears)". Its `EditDate` is 2026-08-25 on every row, so it cannot date one closure | p02 |
| `utah_sgid_trails`: Mineral Fork, Mill D North Fork and Days Fork read `Status='EXISTING'` | USFS order 04-19-26-744 closes them to every user 2026-08-20 to 2026-11-30 | p08 |
| `usfs_trails` Iron Mountain Trail: 2 of 14 rows draw (5.08 mi of 34.48) | 12 rows have null geometry. It carries most of the 2026 A.T. detour | c18 |
| `reference/water_distance.json`, built 2026-06-02 | `Campsite_Sustainability_Index/FeatureServer/0` no longer exists; the sites are in layer 1. The fix is the layer id only | b1 |

### 3b. Registry rows that are wrong or stale

| record | what is wrong | from |
|---|---|---|
| `sources.json` `azgeo_arizona_trail` | Loads layer 5, the ATA's *connector* trails (228.9 mi). The trail is layer 3 (44 passages, 831.6 mi), in the Arizona Trail Association's own org, so the `steward` and the state-publication licence argument are wrong too | b7, c10 |
| `blm_trails` | Says "no name field"; layer 7 has `ROUTE_PRMRY_NM` on 14,599 of 19,532 features. Carries no motorized exclusion: 10,224 rows are motorized, which **#1711 — Ship only hiking trails: remove NH GRANIT, and drop USFS motorized trails nationwide** applied to USFS only | b6 |
| `usfs_trails` freshness | The ETag `"1a7709d0"` stood still while the count moved 86,329 → 86,417. It is not a change marker | b6 |
| `dec_licence` | Says DEC's terms are "genuinely UNSTATED". True of the on-prem services; DEC's AGOL copies of the same data state restrictive terms (§6). Decision 20 now rules on them | b3 |
| DEC "Trailhead" layer (`dec_backcountry_features/2`) | Holds 10,644 campground infrastructure points, 37 of them trailheads. DEC's trailheads are in layer 0 | b3 |
| `oprhp_trail_closures` | Its own item has an empty `licenseInfo`; `oprhp_licence` was read from the trails item | b4 |
| `nyc_public_restrooms` | `dataset_id: i7jb-7jku` but `url` points at `hjae-yuav`, a different dataset | b5 |
| `nyc_drinking_fountains` | Not refreshed since 2024-07-15 | b5 |
| `nyc_cscl_paths` | The dataset's own attribution is OTI, not NYC DOT | b5 |
| `massgis_long_distance_trails` | Steward is DCR; the lines are compiled from club GPS tracks | b5 |
| `nps_trails`, `pasda_dcnr_trails` | `reaches_hikers: true` beside a `reaches_hikers_comment` that still reads "Registered, not shipped" | c8 |
| `wa_rco_trails.segment_length_mi` | Reads about 1.46× WSPRC's own mileage on four trails. Whether an exporter reads it is unchecked | c21 |
| `atc_licence`, `photo_licence`, `atc_support`, `atc_trail_updates` | Point their open question at **#98 — Confirm opentrail.org data-reuse terms with the maintainer**, which is about opentrail.org. ATC's terms have no issue of their own | b1 |
| `Helene_Status` (SOURCE_SURVEY.md §3c: "closure status") | All 140 polygons read `Complete`. It records finished assessments, not closures | b1 |
| POI_COVERAGE_SURVEY.md §10 | NYC parking (421 lots) and trailheads (257 signs) are not absent, and `DPR_Hiking_001.json` is a queryable feed | b5 |

### 3c. `via` rows whose upstream is not loaded, retired, or not the trail

| org | `via` | what was measured | from |
|---|---|---|---|
| 19 NHT orgs | `nps` | `nps_trails` holds 0 features for 16 NHT unit codes. The alignments are in NPS's ArcGIS Online org, and NPS's own item text says they are "not a fully developed hiking trail" and should not be shown beyond 1:100,000 | c11 |
| `msgtc` | `nh-granit` | Retired by the NH GRANIT removal (#1711, above); the Greenway arrives through nothing loaded | c4 |
| `trustees`, `blue-hills` | `massgis` | DCR Roads and Trails, which the `why` cites, is not registered, and does not cover the Trustees' reservations | c4 |
| `condor` | `usfs` | The 2 matched features are Condor Peak Trail (Angeles NF) and Condor Observation, not the 400-mi route | c7 |
| `fta` | `usfs` | 183.6 mi of the 1,568.8-mi Florida Trail arrives | c10 |
| `pnta` | `usfs` | 0 EDW segments match PNT under any name | c10 |
| `shta` | `duluth` | ~100 mi loaded; the whole 300.3-mi trail is in NCTA's `agol_sht_public` | c7 |
| `buckeye` | `outerspatial` | ODNR's `ODNR_Trails/MapServer/2` holds a 1,288.7-mi copy; BTA's terms bar reuse without permission (§5) | c8 |
| `sheltowee` | dual source | The "own source" is OutraGIS's $10 product | c8 |
| `gwta` | none | Not none: `usfs_trails` 440.6 mi, `utah_sgid_trails` 143 features | c7 |
| `rmc` | dual source | Every `RMC_cartographer` item answers "Subscription is canceled" | c1 |

These belong with **#1709 — Register the steward and the redistributor both, and declare which
one wins where they overlap**.

### 3d. Layers loading an old copy while the steward publishes a newer one

| loaded key | what it is | the steward's current layer |
|---|---|---|
| `cdtc_centerline` | `ContinentalDivideTrail2016` on a Wyoming university server | CDTC's `Continental_Divide_Trail_2/FeatureServer/0`, edited 2026-09-30, CC BY |
| `cotrex_trails` | A Boulder County snapshot, last edit 2024-08-30 | CPW's `CPWAdminData/FeatureServer/15`, 2026-08-27 |
| `nc_mst_trail` | NC Commerce's 2020 copy | NC DPR's `State_Trails/FeatureServer/1`, 402 MST segments, 2026-09-30 |
| `ct_deep_blue_blazed` | Last edit 2024-05-17 | CFPA's `BBHT_Public_Map_Trails`, 2026-09-29 |
| `njdep_park_trails` | On-prem `Land/MapServer/63`, no `editingInfo` | NJDEP's hosted `NJ_State_Park_Service_Trails_h/FeatureServer/63`, 2026-09-02, which NJDEP's newest Trail Tracker draws |
| `pasda_dcnr_trails` (Rachel Carson Trail) | 37.13 mi, `UPDATE_` 2017-08-28 | RCTC's GeoJSON, 46.2 mi, version 2026-06-08 |

### 3e. Status columns nothing reads

`export_nearby_trails.py` applies a status only where a `sources.json` row declares
`status_field`; everything else ships as `DEFAULT_STATUS = "open"`. Only `oprhp_trails`
declares one (b7, Measured from the code).

| layer | column | values that should not draw as open trail |
|---|---|---|
| `nps_trails` | `TRLSTATUS` | Temporarily Closed 60, Decommissioned 20, Abandoned 5, Proposed 6 |
| `utah_sgid_trails` | `Status` | CLOSED 122, PROPOSED 984, UNCERTAIN 829 |
| `cotrex_trails` | `access` | `no` 939, "Authorized/Permitted User Only" 2,632, date windows |
| `nc_mst_trail` | `TRAILSTAT` | Regional Plan 66, Manager Agreement 33 |
| `ncta_trail` | `closure` | Closed 4, Highwater 2, Hunting 2 |
| `usfs_rec_sites` | `seasonal_operational_status` | CLOSED 757 nationwide (§3a) |

Not loaded yet, and the same trap: Virginia DCR's `SP_Trails` reads `Status='Open'` on the New
River Trail while the park says use only the open portions; VTrans notices have `isActive=0`
with a null `endDate`; Montour's proposed Muse Branch has `Status` 1, "Existing"; the Rio Grande
Trail has 438.3 mi `Proposed` beside 188.5 mi designated; San Diego's Trans County Trail is
26.2 mi existing against 83.0 mi proposed. A mandatory, mapped `trail_status` column in each
`stg_<org>__trail_lines` model is what makes this fail at build time rather than default to
open (b7's recommendation, Reasoned).

### 3f. Findings for the plan itself

- **The folder contract needs more note kinds** (c5, c6). Data that exists but must not be
  loaded makes a `NOT_AVAILABLE` note false. Proposed: `PUBLISHED_TERMS_BLOCKED`,
  `UNREACHABLE` and `PUBLISHED_DO_NOT_LOAD` (for open data that is personal information).
- **Hyphenated slugs cannot be Python packages** (`import pipeline.extract.pa-dcnr` is a
  syntax error). The plan needs one stated slug → folder mapping and a test that maps each
  folder back to one catalogue slug (b5, b7).
- **No candidate challenge fits the challenges model.** `export_challenges.py` (merged in
  **PR #1798 — Challenges: a club's list of places on its own trails, joined and tagged at
  camp, starting with the ATC's Summer Bucket List**) needs places with published POIs.
  PCTA's 2,600 Miler, NCTA's Hike 100 and the rest are completion programmes (b7).
- **Decision 7 sends most ATC closures to `warnings`.** All 7 `Closure` rows in
  `atc_updates.json` carry `obstructs_trail: false`; only 4 `Detour` rows are `true` (b1).
- **Walls move during a day.** `northcountrytrail.org` and `tahoerimtrail.org` answered
  WordPress REST early and Cloudflare 403 hours later. A run that gets 403 must report UNKNOWN,
  never zero rows (b7).
- **Change markers that lie.** On-prem ArcGIS ETags (above); NYNJTC's RSS ETag moved with no
  post changed (b2); FoOT's PDF `Last-Modified` headers do not match the files (c6).
- **"Cowboy Trail Detour (CLOSED)" is a closure baked into a feature name** in the USGS
  national trails layer; deduplication must not read it as a closure (c14).

---

## 4. Worth loading first, ranked by the four harms

CLAUDE.md names four ways this app can hurt somebody: lost, out of water, in front of something
dangerous, or unable to get off the trail quickly. Every batch's list of finds that bear on
them is merged here and deduplicated. b4 and b7 wrote no such list; their safety items are in
§3. Repairs to data that ships wrong today are §3a, and come before all of this. Within each
harm, geometry and machine-readable feeds come before pages. "Terms" marks an item that waits on §5 or §6.

### Closures and obstructions

| find | where | from |
|---|---|---|
| USFS regional forest orders as geometry: R6 fire closures (1,536 active lines; filter `ClosureStatus='Active'`), R4 (230 polygons), R3 (60 points, 104 polygons), R9 Superior, R1 Bob Marshall, Kootenai inaccessible roads and trails (389) | `services1.arcgis.com/gGHDlz6USftL5Pau/.../R06_FireClosureOrders_PublicView/FeatureServer/1`; `apps.fs.usda.gov/fsgisx02/rest/services/r04/R04_Alerts_And_Closures_01/MapServer/0`; `…/r03/r03_ForestOrder_01/MapServer` | b6, p01, p06, p08 |
| NPS park closures as geometry (YOSE 29 lines, SEKI 140 lines + 23 polygons, GRCA 41 polygons, DENA, GRTE, ROMO) and GSMNP's `GRSM_TRAILS` | NPS AGOL services, per park | b6, p02, p10 |
| NPS Alerts API, every unit (617 alerts; 146 Park Closure in the first 500). Category does not encode closure | `https://developer.nps.gov/api/v1/alerts` (registered key) | b6, c9, c10, c11 |
| Tennessee State Parks closed segments (22) plus the alerts API | `services5.arcgis.com/bPacKTm9cauMXVfn/.../TDEC_Trail_Closures_Public/FeatureServer/0`; `https://tnstateparks.com/api/alerts` | c9 |
| Ice Age Trail posted conditions (21 live of 80) and gun-deer closures (52 lines) | `IAT_Trail_Conditions_Posted` (filter `posted='yes'`), `IAT_Hunting_Closures` | c10 |
| FLTC notices (121 active, 9 closures), closure lines (82), temporary notices (28) | `noticesJSON.php?data=notices`; ArcGIS `Closures_`, `Temporary_Notices` | c4 |
| Idaho emergency route closures (61, seven national forests) — terms | `Idaho_Recreation_Trails/FeatureServer/127` and `/123` | c13 |
| Michigan DNR temporary closures (206 lines; 82 non-motorized) and reroutes | `DNRTrailsOPENDATA/FeatureServer/0`, `/1` | c13 |
| Empire State Trail closed segments (9) plus reasons and detours | `Empire_State_Trail_Closures_(Public_View)/FeatureServer/0`; `empiretrail.ny.gov/trail-closures` | c16, c17 |
| VTrans rail-trail closures and warnings, `isActive` | `VT_Rail_Trails_Closure_View/4`, `VT_Rail_Trails_Warning_View/4` | c18 |
| Missouri trail advisories with mile markers and dates; park status (93 parks) | `gis.dnr.mo.gov/…/parks/Trail_Advisory_Viewer/MapServer/13`; `…/State_Parks_Status_Viewer/FeatureServer/0` | c14 |
| Cowboy Trail live closures (not the two 2019 copies) | `services5.arcgis.com/IOshH1zLrIieqrNk/…/Cowboy_Trail/FeatureServer/5` | c14 |
| FMST Helene recovery map: 2 closed lines and a detour | `google.com/maps/d/kml?mid=1oSH-JQQpOan3r5Km7lJSVDDopenkW6k&forcekml=1` | c7 |
| GAP trail alerts (65, with obstruction status and coordinates) | `gaptrail.org/wp-json/wp/v2/trail-alerts` | c15 |
| D&L Trail sections (44; "closed" means obstruction here) | D&L `mapdata.json` | c15 |
| East Coast Greenway closure and detour points (198, undated) — terms unknown | `router.greenway.org/alertpois/` | c15 |
| Oregon State Parks notices, all 175 in one request; HCRH State Trail landslide closure | `https://stateparks.oregon.gov/services/notices.cfc?method=getAll&currPage=1&perPage=200` | c21 |
| Washington State Parks alerts (234; 26 closures) | `parks.wa.gov/about/news-announcements/alerts` (page) | c21 |
| Arkansas State Parks alerts across 52 parks | `https://www.arkansas.com/sitewide_alert/load` | c19 |
| Land Between the Lakes alerts, including a live N/S Trail closure (→ `usfs`) | `https://www.landbetweenthelakes.us/wp-json/wp/v2/alerts` | c19 |
| Club feeds in WordPress REST or RSS: GMC alerts (`/wp-json/wp/v2/alert`), MCOMD (category 216, ahead of ATC on James Fry), OHTA (`pages?slug=trail-alerts`), SHTA (`/trail-conditions/`), TKO's Oregon Coast Trail (`posts?categories=10`), River to River (`categories=4`), ATA (`aztrail.org/category/closures-reroutes/feed/`), FTA (categories 37–43), Maine Huts, ODT (`/feed/?post_type=trailalerts`), D&R Canal RSS, Montour (Tribe events with `start_date`), Austin's Butler Trail detours, SRKG category 5 | the org's own site | c1, c2, c6, c7, c8, c10, c14, c15, c16, c17, c21 |
| Club pages: NYNJTC Highlands Trail segment and parking alerts; Long Path West Point seasonal closures (`Long_Path_West_Point_Seasonal/FeatureServer/0`); Sheltowee `/alerts`; OTA section conditions; Palmetto closures; PNTA alerts table; CFPA notices; Cross Vermont `tempnote.php`; Eastern Trail; Tahoe-Pyramid; NBATC notices; MRATC alerts; Montour's National Tunnel banner; RVTA's Brookville Tunnel; NJ, CT and NYC DOT closures (`ctparks.com`, NYC DOT Greenway Closures) | pages | b2, b5, c2, c3, c7, c8, c10, c15, c16, c17, c21 |
| NYS DEC Adirondack and Catskill backcountry pages, dated weekly: 5,292 DEC segments render as open — terms (DEC website policy) | `dec.ny.gov` (page; send an honest user agent) | b3, c17 |
| ADK High Peaks conditions — terms (no automation) | `adk.org` | c4 |

### Warnings: fire, hunting, bears, hazards

| find | where | from |
|---|---|---|
| USFS Region 8 prescribed burns (5,804 blocks; 8 in progress); one source for the BMT, Bartram, LSHT, Sheltowee and OHT | `services1.arcgis.com/gGHDlz6USftL5Pau/ArcGIS/rest/services/R8_Prescribed_Burn_Status__read_only/FeatureServer/0` | c8, q01 |
| NIFC current fire perimeters and incidents, for `_shared/nifc/` | WFIGS layers | p02, p06, p10 |
| Fire danger: NJ Forest Fire Service (`Envr_admin_FFS_danger_public/FeatureServer/2`), Utah FFSL `Fire_Restrictions/0` (176 polygons), WA DNR fire danger and burn bans, MN DNR fire-danger WMS, MI DNR `Burn_Permits/MapServer/0`, NM Forestry `NMDF_Restrictions` (read `Notes`: 11 counties say Stage 2 and "No Restrictions" at once), PA DCNR daily PDFs, DEC's ratings through `api.nysmesonet.org/data/firewx/GetFDRA/` — terms | state services | b3, b5, c13, c14, c15, c17, p01, p03, p04, p10 |
| Hunting, where and when: FWC `HuntDates_v3` (27,932 per-day rows), FWS `FWS_NWRS_HQ_PublicHuntUnits_view` (2,215), FLTC `Hunting_Bypasses_` (69), VA DCR `VSP_Deer_Hunting_Areas_view/4` (330), OPRD hunting areas (89), RIDEM hunting polygons and the orange rule, DEC WMU season layers, Blue Hills hunt areas, NYNJTC `/hunting-season/`, MST-PA section closures in effect now, Trustees' designations PDF, ATC's hunting table with NPS `AT_Lands` | agency layers and pages | b1, b2, b3, b5, c4, c9, c10, c17, c18, c21, r01 |
| Bear rules: Blood Mountain canister requirement (ATC page), GMNF food storage (GMC feed), Desolation Wilderness canister order, Bridger-Teton and Shoshone orders, YELL bear management areas | pages; NPS layer | b1, b6, c1, p03, p04, p08 |
| Hazard geometry: YOSE rockfall lines (12), USFS BAER burn areas (246), Arizona GWT wash crossings (423), Anchorage avalanche zones (324), Hawaii County tsunami evacuation layers, CCT tidal-closure and impassable points (`/wp-json/wp/v2/info_point`) | agency and club layers | b6, c20, p01, p10 |
| Condition boards: Ouachita Trail sheet (190 segments; read the xlsx, the CSV drops the status colour), Central Iowa trail status API, Yuba Expeditions per-trail board, TEHCC maintenance log (drop names) | club sheets and pages | c3, c5, c6 |
| avalanche.org forecast zones (83) — terms (§6) | `api.avalanche.org/v2/public/products/map-layer` | p04, p05, p06, p08, p10 |

### Water

| find | where | from |
|---|---|---|
| OSM drinking water and springs beyond the 14 A.T. states (25,911 and 39,692 US-wide), already ODbL-attributed | Geofabrik extracts | c12 |
| Steward water layers: ATA water (312 + 162 waypoints), IATA `IAT_Water` (423, potability and reliability codes), FLTC `Waypoints` (122 water and restrooms), GMC `OS_MASTER` (72 Long Trail sites, "Unreliable" where so), CT DEEP `DEEP_Trails_Set` trail access (209 with `WATER`, CC0), BLM potable water (61, plus 6 at Fort Meade), NPS POI water types (Potable Water 214, Drinking Water 136, Spring 25) | ArcGIS layers | b5, b6, c1, c4, c9, c10, c15, p10 |
| Steward water pages and books: RATC shelter water and reliability, MDHTA waterboxes (8) and pump-removal dates, LSHT drought ratings, Loxahatchee data book (potable, non-potable, pitcher pump), Standing Stone list (32, 2015–2017), BMECC springs My Map (16), AMC chapters' campsite water, PHNST amenities (38 fountains) | pages, PDFs, KML | c1, c2, c3, c8, c10, c19 |
| Published "no water here" statements: LBL, Caprock Canyons (with a nitrate advisory), Loxahatchee; Trail of the Coeur d'Alenes "Do not drink surface water even if filtered" | pages | c13, c19 |
| USFS springs (43,255), only as "spring reported" and filtered on `PUBLICINFO = 1`; 87% are "reported, not verified" | `StaticSnapshotForMobile_HydroSpringsUSFS/FeatureServer/0` | b6 |
| Water that needs a permission ask, not a fetcher: ONDA water caching (waiver), Blue Mountains Trail databook (waiver), Bigfoot Trail (sold in its mapset) | — | c7, c20 |

DEC's 1,218 campground spigots exist (`dil_campgrounds/MapServer/4`), and the condition DEC's
holdback names for reopening is arguably met, but the maintainer's words stand: *"Lets not use
water from DEC"* (b3).

### Shelters and overnight

| find | where | from |
|---|---|---|
| ATC's own capacity and food storage (413 sites, 246 with capacity) | `ATX_Ratings/FeatureServer/17` | b1 |
| PATC shelters (47; 14 on the Tuscarora that nobody else publishes) | `PATC_Shelters_AT_and_TT_2_view/0` | c2 |
| GRSM backcountry shelters (15, all with capacity) | NPS layer | b6 |
| FTA campsites (177, with distance to water), CFPA shelters (16), IATA camping (247), SHT campsites 2025 (94; "internal use" label), Ridge Trail campsites (192), NJ State Park Service shelters and lean-tos (`Land/62`), PA DCNR trail shelters (55) and the LHHT's 40 shelters, TN backcountry shelters (10), MA DCR shelters (59), Missouri backpack camps (40), Empire State Trail campgrounds (69) | ArcGIS layers | b5, c6, c7, c9, c10, c14, c16 |
| RMC's Gray Knob, Crag Camp and Log Cabin; MRATC's Iron Mountain shelters on the detour; Ouachita shelters (23); Baker Trail shelters (8); Pine Mountain overnight camps | pages | c1, c3, c6, c17, c19 |
| 139 USFS shelters typed `CAMPING AREA` that the dispersed-camping holdback drops (7 are the Pinhoti's own) | `usfs_rec_sites` | p02 |

### Ways off the trail

| find | where | from |
|---|---|---|
| Numbered emergency locations: OPRD beach access signs (486), Cobb County Silver Comet markers (100, with US National Grid numbers), PA Game Commission emergency response points (3,019) | `…/ELM_Public_wm/MapServer/0`; `PennsylvaniaGameCommission/MapServer/14` | c19, c21, p03, q01 |
| Road access: ATC's New England access-zone lines (189), AMC Western Massachusetts parking with winter road closures, WMNF forest road status, GWJ road closures at A.T. miles 538.5 and 542, DEC trailhead registers (388) | layers and pages | b1, b3, c1, p05, p09 |
| Closed bail-outs: Black Mountain Campground closed in USFS `openstatus` below Mount Mitchell; Bottchers Gap (Condor Trail terminus) closed and inside a fire closure order | `EDW_RecreationOpportunities_01` | p01, p09, p10 |
| Tunnels, crossings and intersections on the Washington rail trails (13 tunnels, 376 road intersections); Northern Rail Trail at-grade crossings (14) | WSPRC layers; UVLSRPC | c21, p08 |

---

## 5. Terms and fetch restrictions that are the maintainer's decisions

**None of these was routed around.** Where a batch made requests before reading a terms page
or robots.txt, it said so: about 6 `adk.org` pages, 3 `wta.org` requests, 10 `bmta.org`
requests (Crawl-delay 60), 11 to BRBTC (Crawl-delay 10), 5 to `coloradosprings.gov`, 38 BTA
pages, one `fnrt.org` request, one `lidarportal.dnr.wa.gov` listing, and one 45.8 MB NCTA
GeoJSON fetched whole by a reachability probe. c6 sent its first four probes to each site before
reading robots.txt, and c8 fetched BMTA's 1.72 MB `/wp-json/` index twice and one 2.5 MB PDF by
mistake. Each batch stopped on reading the rule.

| kind | where | what it blocks |
|---|---|---|
| **The four `refuse` rows** | `rtc`: TrailLink terms are personal and non-commercial, consent required; RTC's own ArcGIS org (252 services) carries a "contact RTC" licence. `onda`: guidebook, GPS data and water caching behind a waiver form. `avenza`: terms forbid automated access; USFS maps frozen there since April 2026. `buckeye`: BTA's terms and its own layer's "Permission … is required before use!" | Round 5's "note now, load on permission" stands. Two copies would route around a refusal unless the steward agrees: Oregon State Parks' "Oregon Desert Trail" item and ODNR's 1,288.7-mi Buckeye Trail line. ONDA's own public `ODT Tracks` layer (28 sections, no licence) asked a different question: does the waiver govern it, or decision 21(a)? (p06). Decision 39 answered it on 2026-10-01: a club's own public ArcGIS layer counts as published whatever its website's waiver says, so `ODT Tracks` is extracted. Whether it may publish while `onda` is a `refuse` row is put to the maintainer in `pipeline/ELT.md`'s open questions. c12 recommends `_shared/rtc/` and `_shared/avenza/`, since decision 18 keeps umbrellas and aggregators out of club folders |
| **No-automation terms** | ADK (no bots, scripts or scrapers; written permission); ATC's website terms (2025-11-21: no "systematic or automated data collection"), which cover `lib/atc_scrape.py` and rest on **#458 — Confirm with the ATC what may be republished from their Trail Updates**; WTA (Crawl-delay 60; internal use only); Save Mount Diablo; Tennessee Trails Association (robots.txt names ClaudeBot); Colorado Mountain Club (§3(e)); OuterSpatial (robots.txt disallows ClaudeBot; personal, non-commercial); COTREX app terms | Extraction waits for written permission (decision 39, 2026-10-01: no-automation terms mean ask, and the plan drafts each request). ATC's trail-updates scrape stays as today, on **#458 — Confirm with the ATC what may be republished from their Trail Updates** |
| **Consent or negotiated licence** | Trail Finder and Maine Trail Finder (UVTA): "may not be … redistributed by third-parties without the express written consent"; Maricopa County (written authorisation); SHTA (data request form; its public layers say "internal use"); TKO's Oregon Hikers Field Guide; Ohio to Erie (ClubExpress terms); avalanche.org | A permission ask |
| **Walls** (Cloudflare, Akamai, Incapsula, Sucuri, SiteGround, WAFs) | `parks.ny.gov`, `floridastateparks.org`, `dem.ri.gov`, `rivcoparks.org`, `sawpa.gov`, `ksoutdoors.gov`, `mass.gov`, `dep.nj.gov`, `depdata.ct.gov`, `outdoornebraska.gov`, `coloradotrail.org`, `greenway.org`, `mountainstoseatrail.org`, `montanatrail.org`, `railtrails.vermont.gov`, `schuylkillriver.org`, `nptrail.org`, the Mountaineers, `foothillstrail.org`'s REST API, `olympicdiscoverytrail.org` (after about six requests), and several umbrellas | UNKNOWN rows (§10) |
| **Hosts that filter by user agent** | `tnstateparks.com` refuses an identified bot and serves a Chrome UA; `www.fws.gov` does the opposite; `dec.ny.gov`, `parks.ny.gov` and `empiretrail.ny.gov` challenge a browser imitation but serve an honest UA; LSHT's ClubExpress files need a browser UA plus a session cookie; CFI's sitemap rejects some non-browser UAs | Decided 2026-10-01 (decision 39): the pipeline never imitates a browser and always sends its own honest user agent, so `tnstateparks.com` and LSHT's files hold until the org answers. The honest-UA hosts need nothing |
| **Waiver gates** | ONDA (above; its own public ArcGIS layer is extracted under decision 39, and the waivered files are not); Greater Hells Canyon Council's Blue Mountains Trail maps and databook; Ala Kahakai Trail Association's Waikapuna land (a waiver for access, which a `places` row must carry) | Not signed |
| **Paid apps and products** | FarOut (Foothills, STC, WVSTA, MSTA, CTF, FMST, Sheltowee), Avenza (MATC, Cohos), OutraGIS ($10 Sheltowee files), onX (Montana Trail 406), Bigfoot mapset ($20), Beartooth High Route map pack ($20), Cohos map ($16.95 / $16.99), FLTC map zips, WVSTA guidebook, LIGTC maps, Uwharrie Trailblazers map ($10), Coeur d'Alene GPS files, Trailforks (RMC) | Not bought. Republishing something a club also sells is a question to ask first |
| **Geocaching and closed apps** | PA DCNR GeoTrail (geocaching.com terms unread), Maine GeoTour (geocaching.com login), NH State Parks on Goosechase, Millstone Valley audio tour on TravelStorys, RMFI's podcast on Spotify only | Not fetched |
| **Members-only and social** | TEHCC post bodies; LIGTC's "Members-Only" newsletter (publicly linked); Facebook for dozens of clubs, including the only closure channel for the Tanglefoot, the Pinhoti, the GWT and the San Diego Trans-County Trail; GHCC's Instagram | Meta's terms bar automated collection (Reasoned; not re-read) |

---

## 6. Explicit restrictions — one question for the maintainer

Decision 21(a) presumes public GIS reusable, and sends every layer whose own text restricts
reuse to the maintainer as one batched question. These are all of them, from every audit and
persistence file. Each is extracted and staged; `may_publish` stays false for these rows only
until the question is answered. Quotes are verbatim from the item's `licenseInfo`, read
2026-10-01, unless the row says otherwise.

| layer | org / row | where | the words | decision 20/22? |
|---|---|---|---|---|
| DEC Trails | nysdec | item `ab5d56644a404b41bac8d72f32017e4e` | "Data is not for distribution to third parties." | **Yes, 20** |
| NYS State Land Assets (lean-tos, campsites, towers, vistas, parking) | nysdec | item `c756ab8f4b654789812c1b9d6d783640` | "Data may NOT be distributed outside DEC without permission … Secondary distribution of the data is not allowed." | **Yes, 20** |
| NYS DEC Lands | nysdec | item `84b4cce8a8974c31a1c5584540f3aaae` | "Secondary Distribution of the data is not allowed." | **Yes, 20** |
| Campsite Amenities; Forest Ranger Contact | nysdec | items `5da7d4e7aaf640c0bd0b85ddb11601af`, `9eb7c613f65240a4bb5f309622c48ded` | "Data is not for distribution to third parties." | **Yes, 20.** Ranger names and numbers are never extracted |
| Wildlife Management Units; Wildlife Management Areas | nysdec (LIGTC warnings) | items `fb5f181f7ee440409487f86a06371972`, `0ad51574122f43e586975c96643f4287` | "Secondary Distribution of the data is not allowed." | **Yes, 20** |
| Small Game Seasons | nysdec | item `2f30f0cb2be74779a6be889714ca6a95` | "Secondary Distribution of the data is not allowed." | **No.** Not found in the clearinghouse; stays under `dec_licence`'s 2026-08-25 authorisation (**#1019 — A survey's proposed ring decides which of NYS Parks' and NYNJTC's trails ship, and DEC's ship not at all**) |
| Fire Danger Rating Areas (JSON, not a clearinghouse item) | nysdec | `https://api.nysmesonet.org/data/firewx/GetFDRA/` | Mesonet policy forbids redistribution "without the express prior written consent of RFSUNY" | **No.** Whether a DEC rating is "Mesonet Data" is `@unvalidated` |
| NY State Parks Property | nysparks | item `bb2dfa2c…` | "Credit source of NY State Parks. Do not redistribute." | **Yes, 22** |
| OPRHP layers incl. `EST_Public` (Empire State Trail), hunting areas, greenways | nysparks | OPRHP org `1xFZPtKn1wKC6POA` | "for informational and non-commercial purposes", with attribution to OPRHP | **Yes, 22.** The same text `oprhp_licence` already records as a grant with two conditions |
| PR: WI Park Closures PUBLIC READ view | wi-dnr | item `2a0f013583dc452e938aead18cbf71f3` | "It is not intended for reuse and is subject to be changed or removed without notice." | No |
| Pacific Northwest National Scenic Trail (USFS R6) | pnta | `services1.arcgis.com/gGHDlz6USftL5Pau/arcgis/rest/services/Pacific_Northwest_National_Scenic_Trail/FeatureServer/0` | "not intended for trip planning or to determine public access along the trail" | No. A use caveat on a federal work |
| Oregon NHT and the other NHT alignments | NHT orgs | item `beea1da3fccd493b8c9090c774d829f4` | "This data set should not be displayed or used at scales that exceed 1:100,000." | No. A display limit |
| Idaho Recreation Trails (closures 127, restrictions 123, routes 128) | idpr, fwrt, gwta | item `5a08280a853b41b69115a3fc0abbd2bc` | "Not for commercial use and may not be used in 3rd party apps without source attribution." | No |
| Texas State Parks Trails, Public Areas, Boundaries | tpwd, tx-tamers | `https://tpwd.texas.gov/arcgis/rest/services/Parks/TexasStateParksTrails/MapServer/0`; items `876c319b…`, `3d25602d…`, `47c52b2c…` | "This data is not intended to be used for profit." | No |
| FPS POIs | fl-state-parks | item `10e55abd…` | "For internal use by Florida Park Service staff and authorized partners only … Not for public distribution without review and approval." | No |
| ACTIVE_OBA_PTS (Florida Forest Service) | fta-loxahatchee | `https://services3.arcgis.com/XYg2eF8UuxZVuVmF/arcgis/rest/services/ACTIVE_OBA_PTS/FeatureServer/0` | "This map is for internal uses only …" | No. Not needed for its row |
| Maricopa County park and trail service, and its web app | maricopa-parks | `https://gis.maricopa.gov/arcgis/rest/services/PNR/ParkAndTrail/MapServer` | "Any download for commercial intent or resale of this information is prohibited, except in accordance with a sublicensing agreement"; the app: "For Maricopa County government internal use only … obtain written authorization." | No |
| Metro_Sites_Access_Points and siblings (Oregon Metro) | forty-mile-loop | item `f5fdb875df4c4608b96ff2d5ffd4527c` | "Use only for the TriMet trip planner." | No. The sibling `DestinationAccessPoints` states nothing |
| SDRP trail layer | sdrp | item `8e8c627777b84620a281002c7d76cf41` | "Internal Use Only … cannot be reproduced without the written permission of SANDAG" | No |
| SanGIS-licensed San Diego County layers (trails, parks, places) | sd-trans-county | items `36c00230…`, `d2f1357c…`, `4d541874…`, `f2ea8caa…`, `b87041d5…`, `a473cef9…`; re-hosted copy `79b2d8ba…` | "SanGIS discourages, but does not prohibit, the re-distribution of this data"; no altered copy redistributed as SanGIS's; no SanGIS attribution "at scales below 1:24,000"; the copy: "re-distribution … is strongly discouraged" | No |
| California State Parks routes, campgrounds, boundaries | sd-trans-county, smd, tahoe-yosemite | items `45fa4fba…`, `81c47bee…` (`services2.arcgis.com/AhxrK3F6WM8ECvDi/arcgis/rest/services/Campgrounds/FeatureServer`), `a5f3bbb6…` | "may not be sold or altered … Commercial uses of these Materials must be approved by CSP in advance" | No. "Altered" bites on reprojection and tiling |
| California State Parks entry points | sd-trans-county, smd | items `077faa6b…`, `000f7966…` | "DPR Administrative codes are intended for interagency use only; Park names, locations, and web links may be freely shared with DPR citation." | No. Drop the admin-code fields |
| VSP Trails; Virginia Conservation Lands | va-dcr, path, ocvt | `https://services1.arcgis.com/PxUNqSbaWFvFgHnJ/arcgis/rest/services/SP_Trails/FeatureServer/0`; item `aae5e3fc…` | "The re-distribution of this dataset for profit is prohibited." | No |
| Cold water streams (VDGIF) | geta (not proposed for any row) | item `ae3ff774…` | "Data may not be released to any other party without the VDGIF's written consent." | No |
| City of Colorado Springs parks and trails | rmfi | `gis.coloradosprings.gov/arcgis/rest/services/GeneralUse/ParksRecreation/MapServer` (item `9f5d0bb4…`) | "may not be reproduced, modified, distributed … without the prior express written consent … intended for internal use only." The City's hosted "Trails" layer (`1f8c0912…`) states nothing | No |
| El Paso County Trails; Park Locations | rmfi | `gisservices.elpasoco.com/arcgis2/rest/services/HubPublic/Trails` (items `89e837e6…`, `85f76c00…`) | "No part … may be reproduced; used to prepare derivative products; or distributed without the specific written approval …" | No |
| Conestoga Trail (Lancaster County) | lancaster-hiking-club | item `035bf2fc8c5340d78970a996edea916c` | "For illustration and demonstration purposes only. For internal use by Park Rangers." | No |
| GET Board 2021 web map | geta | item `3597bca131e443aaa4b4f3176b6bb25b` | "confidential for 2021 Board meeting" | No |
| City of Des Moines Trails | cita | item `758972248b7b47cf8891dee2b429c4cd` | "© Copyright City of Des Moines, Iowa 2025. All rights reserved." | No |
| GreatPlainsTrail_FS2 | gpta | item `a8957207a77b4a10b12abdf1cf79c4b0` | "For use by Great Plains Trail Working Group only. Not ready for public use." It is c13's evidence for gpta's POIs; the public V2 line says "Use is open to the public" | No |
| SHT Trail Protection Web Map | shta | `https://services6.arcgis.com/MoQNIarJueJ3X9ir/arcgis/rest/services/SHT_Trail_Protection_Web_Map_WFL1/FeatureServer` | Snippet: "for internal use at the SHTA". Its parcel layers name landowners and are never fetched | No |
| BT_trail_line_updated | buckeye | `https://services.arcgis.com/VV0wGgcoagcH1JO8/arcgis/rest/services/BT_trail_line_updated/FeatureServer/0` | "Permission from the Buckeye Trail Assocation is required before use!" | No. A `refuse` row |
| A 2017 third-party Benton MacKaye Trail copy | bmta | NEMAC-hosted item | "Restricted for use. Please contact Blue Ridge Forever…" | No. Not to be loaded |
| RTC's route data | rtc | `services5.arcgis.com/ZrPVNtByTK88ebut` | a "contact RTC" licence | No. A `refuse` row |
| King County parks alerts | mtsg | item `d4e0cced…` | "Any sale of this map or information on this map is prohibited except by written permission" | No. Sale only; whether paid tiers are "sale" is the question |
| Cumberland Trail elevation profiles app | cumberland | item `2710adec164343f7817ad323c0c431a7` | "Any sale … prohibited except by written permission of TDEC/State Parks" | No. The service item's own text is unread |
| Minnesota DNR GIS Data License Agreement (every Geospatial Commons item) | mn-dnr | `dnr.state.mn.us/sitetools/data_software_license_plain.html` | "may not be resold, distributed or displayed for commercial purposes or otherwise" | No |
| SHARP tidal marsh DEM (FWS-hosted) | usfws elevation | item `10f2960f53df4d86aa44fea7d60981da` | "This dataset may not be used for commercial purposes." | No |
| avalanche.org map layer | rmc, wmc, iditarod, tahoe-yosemite | `api.avalanche.org/v2/public/products/map-layer` (API root page) | "Please contact avalanche.org / American Avalanche Associate for permission" | No |
| Explore PA Trails (and, Reasoned, the PASDA copy loaded today) | pasda, pa-dcnr rows | item `7820f9cade8e4961b937916d81628ab9` | "intended for demonstration, education, planning, and monitoring purposes only … save the Commonwealth harmless" | No |
| RIGIS / RIDEM layers | ri-dem | `services2.arcgis.com/S8zZg9pg23JUEexQ` | A disclaimer must "appear on all map[s]": "These data were created by RIDEM for informational, planning and guidance use only." | No. A display obligation |
| NJDEP Data Distribution Agreement (fire danger, live status, trails) | njgin, nj-state-parks | `Envr_admin_FFS_danger_public`, `New_Jersey_State_Park_Service_Live_Status_Updates_(Public_View)` | "distributed subject to the following conditions and restrictions…" | No. Conditional, and already the subject of **#1293 — Register New Jersey's two trail layers — NJDEP's State Park Service Trails and the Geospatial Forum's Statewide Trails — after reading the NJDEP Data Distribution Agreement in full** |
| CPW State Park Boundaries 2026 | cotrex | item `cefdf049d1aa46dc897ddeb7ec3ba957` | licence "Limited"; "for use by CPW staff" | No. Not needed: `CPWAdminData/FeatureServer/5` serves the public set |
| PA DCNR emergency dashboard; NPNHT auto-tour app; IN DNR restricted natural areas | — | items `7b423ed6…`, `69fae6c8…`, `a8f6a443…` | "only to be used as an internal application"; "for USFS and other invited users only"; "restricted for use by the Indiana Department of Natural Resources and approved partners only" | No. Apps or login-gated; listed so nobody loads them |

Conditions that are not restrictions, listed so they are not missed: VT ANR Lands is CC BY-SA
(share-alike may bind derived files); Albuquerque asks that "Closed" open-space properties not
be displayed, and that its restroom layer not be used for "emergency or mission-critical
applications"; NJDEP's hosted trails item says "should not be used for orienteering purposes".

**The question, in one line:** for the layers marked "No" above, does OurHike publish under
attribution, publish only the layers whose words limit *sale* or *profit*, or hold every one
until its publisher answers?

**Answered by the maintainer, 2026-10-01, by poll** (decisions 36–38 in `pipeline/ELT.md`):
profit-, sale- and commercial-limited layers publish with attribution, because OurHike is
non-commercial, and California State Parks' "altered" does not cover reprojection, tiling or
simplification for display (36); internal-use, not-for-distribution and all-rights-reserved
layers on anonymous public GIS endpoints publish under the GIS presumption, against their own
words (37); conditions publish and are honoured downstream, and a condition that cannot be met
holds its layer, as the Pacific Northwest Trail's "not intended for trip planning" does (38).
Person fields, the four `refuse` orgs without permission, and items that are not anonymous
public endpoints stay out. The table above stays as the record of what each layer's own text
says.

---

## 7. Catalogue corrections

For whoever next edits `reference/trail_orgs.json`, `org_channels.json` or
`trail_candidates.json`. The survey edited none of them.

**Never fetch these domains. Each now serves spam or a parked page:**

| domain | catalogue row | live site instead |
|---|---|---|
| `waldotrails.org` (redirects to a gambling site) | `waldo` | `hillstosea.org`. The org is the Hills to Sea Trail, 46 mi |
| `tidewateratc.org` (gambling) | `tatc` | `tidewateratc.com` |
| `cdtsociety.org` (lottery site) | `cdt-society` | none found |
| `pinhotitrailalliance.org`, `alabamatrailsasso.org` (gambling storefronts) | `pinhoti` | `alpta.org`; `org_channels.json` harvested the spam |
| `hayduketrail.org` (hotel spam); `hikinghayduke.com` does not resolve | `hayduke` | — |
| `batonahikingclub.org` (parked ad domain) | `batona` | `batona.wildapricot.org` |
| `ocvt.org` (parked); `outdoor.org.vt.edu` does not resolve | `ocvt` | `ocvt.club` |
| `blueridgebartram.org` is the steward's own domain, injected with casino text site-wide | `bartram` | read the section content block only |

**Licence and type fields:**

| row | fix | from |
|---|---|---|
| `nysdec` | `licence_basis: public_domain` → `maintainer_clearinghouse`, dated 2026-10-01 (decision 20). No state work is public domain by default | b3 |
| `nysparks` | the same (decision 22); `type` is a state agency, not a clearinghouse. b4 also suggested the folder slug `oprhp`; the folder is `nysparks`, because a club folder takes its catalogue row's slug (`pipeline/ELT.md`, "Folder name = `trail_orgs.json` slug") | b4 |
| `usgs-tnm` | The hold reason ("no URL to fetch on a schedule") is contradicted: the MapServer answers, 607,202 segments, `MAX(loaddate)` 2026-09-14 | c14 |
| `nps` | "21 NHT stewards … point here" is false for 16 unit codes (§3c) | c11 |
| `smd` | `licence: unstated` should say the terms forbid automated access | c6 |

**Wrong websites, names and facts** (each Measured by the batch named):

| row | correction | from |
|---|---|---|
| `amc-berkshire` | Now AMC Western Massachusetts Chapter, `amc-wma.org` | c1 |
| `doc` | `dartmouth.edu` is the university; the club is `outdoors.dartmouth.edu` | c1 |
| `gmc` | Publishes its own data under `GMC_Special_Projects` | c1 |
| `odatc`, `yhc`, `path` | `odatc.org`; only `www.yorkhikingclub.com` answers; `piedmontathikers.org` | c2, c3 |
| `patc` | "Publishes no geometry of its own" is wrong: 58 public services | c2 |
| `ocvt`, `smhc` | Mileage: about 30 and 72 + 30, not 19 and 100 | c3 |
| `cmc`, `mratc` | CMC maintains about 94 A.T. and 150 MST miles plus the Art Loeb Trail; MRATC maintains the Iron Mountain Trail | c3 |
| `cita` | `bikecita.org` does not resolve; `centraliowatrails.com` | c5 |
| `hoosier`, `ridgetrail`, `tko`, `sbts`, `wmc`, `nmvfo` | "No open dataset found" is wrong for each | c5, c6 |
| `austin-trail` | Now The Trail Conservancy; the Ann and Roy Butler Hike-and-Bike Trail | c6 |
| `tx-tamers` | `texastrailtamers.wildapricot.org`; the Central Texas Trail Tamers | c6 |
| `ouachita` | Maintains four trails, not one | c6 |
| `gwta` | `americantrails.org` is the umbrella's site; `gwt.org` redirects to Facebook | c7 |
| `palmetto` | Rebranded Palmetto Trails | c7 |
| `nc-high-peaks` | Maintains trail, and publishes a trail KML | c7 |
| `bartram` | Names the heritage society; the footpath's steward is the Blue Ridge Bartram Trail Conservancy | c8 |
| `ohta` | Sells no GPX; publishes a My Maps KML "for illustrative purposes only" | c8 |
| `bmta` | 287.6 mi official, not 300 | c8 |
| `lc-trust` | `lewisandclark.org` is the renamed `lcthf`; the Trust is `lewisandclarktrust.org` | c11 |
| `anza`, `ovta`, `carta` | `anzatrailfoundation.org`; apex `ovta.org`; `caminorealcarta.org` does not resolve | c11 |
| `pohe` | Website `potomactrail.org`; endpoint the NPS PHNST centerline (600 segments, about 855 mi) | c10 |
| `sky-islands` | Withdrawn by its author in 2023; never load a copy | c12 |
| `hot-springs` | 2,421 mi per the route page, not 2,241 | c12 |
| `tpl` | ParkServe (154,780 park polygons) and a 27-episode podcast | c12 |
| `_agol_accepted_owners` | The `MRWMgis` entry was accepted as a water district; it is a private landscape-architecture firm working for the Rio Grande Trail Commission. At least 19 institutional accounts these batches cite are not listed, among them `nctgis`, `superiorhikingtrail`, `GMC_Special_Projects`, `mappingservice_FLTC`, `gishikemstorg`, `TTOR_2`, `RT_GISDepartment`, `POHE_GIS`, `USFSRegion06`, `orstateparks` and `OregonMetro.RLIS`. Staff and personal accounts the batches also met are not named here | c4, c6, c7, c10, c11, c20 |

**`trail_candidates.json`:** Mesabi's steward is the St. Louis and Lake Counties Regional
Railroad Authority (c14); `cnyhiking.com` is a hobbyist site, not NCTA's chapter (c17); the six
Pennsylvania candidates are already in `pasda_dcnr_trails` (c17); the Rio Grande Trail's
designated mileage is 188.5, not 88.5 (c20); the Sun Circle Trail is 122.4 GIS miles (c20); the
Uwharrie Trail is 40 mi, not 20 (c19); the Silver Comet's stewards are three counties, not PATH
(c19); the Allegheny Trail's 316 mi includes a 36.8-mi road walk (c18); and `warriortrail.org`
is a different organisation (c18). The planning session's own `candidates_classified.json`
mislabels the Empire State Trail and the Batona Trail as new stewards (b4, c15), and maps 15
NPS-stewarded trails to `semo` rather than `nps`.

---

## 8. The 95 candidate stewards, as proposed `trail_orgs.json` rows

92 proposed slugs (none collides with an existing slug), plus two USFS units that fold into
`usfs`. The two Maricopa County rows are one department (c20). Classification and folder are the
audit's; "publishes" lists the types each row found AVAILABLE or LOADED.

| slug | steward | class | folder | publishes |
|---|---|---|---|---|
| brta | Border Route Trail Association | managing | yes | lines (loaded), POIs, closures, warnings, places, hikes |
| cfrt | Colorado Front Range Trail (CPW) | route-only | no | lines (loaded), POIs, warnings, places |
| fwrt | Friends of the Weiser River Trail | managing | yes | lines, POIs, closures, warnings, places |
| gpta | Great Plains Trail Alliance | route-only | no; `_shared/` | lines, POIs, closures, warnings, places, hikes |
| idpr | Idaho Dept of Parks and Recreation | managing | yes | lines, POIs, closures, warnings, places, hikes, challenges |
| idpr-coeur-dalenes | IDPR + Coeur d'Alene Tribe | managing | into `idpr` | lines, POIs, closures, warnings, places, hikes, challenges |
| il-dnr | Illinois DNR | managing | yes | lines, POIs, closures, warnings, places, hikes, podcasts, challenges |
| kdwp | Kansas Dept of Wildlife and Parks | managing | yes | lines, POIs, places, podcasts; unknown: elevation, hikes, challenges, photos, closures, warnings |
| mi-dnr | Michigan DNR | managing | yes | lines, POIs, closures, warnings, places, hikes, podcasts, photos |
| mi-dnr-high-country | High Country Pathway (MI DNR) | managing | into `mi-dnr` | lines, POIs, closures, warnings, places, hikes |
| mtra | Michigan Trail Riders Association | managing | yes | lines (loaded), POIs, closures, warnings, places, challenges |
| mn-dnr | Minnesota DNR | managing | yes | lines, POIs, elevation, closures, warnings, places, hikes, podcasts, challenges; unknown: photos |
| mo-state-parks | Missouri State Parks | managing | yes | lines, POIs, closures, warnings, places, hikes, podcasts, challenges; unknown: photos |
| montana-trail-406 | Montana Trail 406 | route-only | no | lines, closures, warnings, places, hikes; unknown: elevation, podcasts, challenges, photos, POIs |
| ngpc | Nebraska Game and Parks | managing | yes | lines, POIs, closures, warnings, places, hikes, podcasts, challenges; unknown: photos |
| otet | Ohio to Erie Trail Fund | managing | yes | lines, POIs, closures, warnings, places, hikes, challenges (terms) |
| r2r | River to River Trail Society | managing | yes | lines (loaded), POIs, closures, warnings, places, hikes, challenges |
| sd-gfp | South Dakota Game, Fish and Parks | managing | yes | lines, POIs, warnings, places, hikes, podcasts, challenges; unknown: closures |
| mesabi | Mesabi Trail authority | managing | yes | lines, POIs, closures, warnings, places, hikes |
| beartooth-high-route | (no steward) | route-only | no | lines, POIs, closures, warnings, places, hikes (GPX sold) |
| wind-river-high-route | (no steward) | route-only | no | lines, POIs, closures, warnings, places, hikes |
| september11-trail | 9/11 National Memorial Trail Alliance | managing | yes | lines, POIs, closures, warnings, places, hikes, challenges |
| bay-circuit | AMC / Bay Circuit Alliance | managing | yes | lines (loaded), POIs, elevation, closures, warnings, places, hikes, challenges |
| adt | American Discovery Trail Society | managing | yes | lines, POIs, elevation, closures, warnings, places, hikes, challenges |
| batona-trail-nj | Batona Trail, NJ State Park Service half | managing | into `batona` | lines (loaded), POIs, closures, warnings, places, hikes, podcasts, challenges |
| cvta | Cross Vermont Trail Association | managing | yes | lines, POIs, closures, warnings, places, hikes |
| dlnhc | Delaware & Lehigh NHC | managing | yes | lines (loaded), POIs, closures, warnings, places, hikes, challenges |
| ecga | East Coast Greenway Alliance | managing | yes | lines, elevation, closures, warnings, places, hikes, podcasts, challenges; unknown: photos, POIs |
| eastern-trail | Eastern Trail Alliance | managing | yes | lines, POIs, closures, warnings, places, hikes |
| fcht | Farmington Canal Heritage Trail | managing | yes | lines, POIs, closures, warnings, places, hikes |
| gap | Great Allegheny Passage Conservancy | managing | yes | lines (loaded), POIs, closures, warnings, places, hikes, challenges |
| geta | Great Eastern Trail Association | umbrella | no | lines, POIs, closures, warnings, places, hikes |
| horse-shoe-trail | Horse-Shoe Trail Conservancy | managing | yes | lines (loaded), POIs, closures, warnings, places, hikes, challenges |
| indiana-county-parks | Indiana County Parks (+ CCCRA) | managing | yes, two proposed | lines (loaded), POIs, places, hikes, challenges |
| lancaster-hiking-club | Lancaster Hiking Club | managing | yes | lines (loaded), POIs, closures, warnings, places |
| ma-dcr | Massachusetts DCR | managing | yes | lines, POIs, closures, warnings, places, hikes, challenges; unknown: elevation, podcasts, photos |
| maine-bpl | Maine Bureau of Parks and Lands | managing | yes | lines, POIs, closures, warnings, places, hikes, challenges; unknown: photos |
| maine-huts | Maine Huts & Trails | managing | yes | lines, POIs, elevation, closures, warnings, places, hikes |
| montour-trail | Montour Trail Council | managing | yes | lines (loaded), POIs, elevation, closures, warnings, places |
| fnrt | Friends of the Northern Rail Trail (+ NH Bureau of Trails) | managing | yes | lines, POIs, warnings, places, challenges |
| nj-state-parks | NJ State Park Service | managing | yes | lines (loaded), POIs, closures, warnings, places, hikes, podcasts, challenges; unknown: photos |
| nova-parks | NOVA Parks | managing | yes | lines, POIs, closures, warnings, places, hikes |
| empire-state-trail | Empire State Trail (OPRHP) | managing | into `nysparks` | lines, POIs, closures, warnings, places (loaded), hikes, challenges |
| nys-canal | NYS Canal Corporation (+ ECNHC) | managing | yes | lines, POIs, closures, warnings, places, hikes, challenges |
| cl50 | Cranberry Lake 50 | route-only | no | lines (loaded), POIs (loaded), closures, warnings, places, hikes, challenges |
| ncta-cny | NCTA Central New York chapter | managing | into `ncta` | lines (loaded), POIs, closures, warnings, places, hikes |
| pa-dcnr-moshannon, pa-dcnr-sproul, pa-dcnr-tiadaghton, pa-dcnr-tioga | PA DCNR state forest districts | managing | into one `pa-dcnr` with `laurel` | lines (loaded), POIs, elevation, closures, warnings, places, hikes, challenges; unknown: photos |
| ri-dem | RI DEM | managing | yes | lines, POIs, elevation, warnings, places, podcasts; unknown: hikes, challenges, photos, closures |
| rctc | Rachel Carson Trails Conservancy | managing | yes | lines, POIs, elevation, closures, warnings, places, hikes, challenges |
| rvta | Redbank Valley Trails Association | managing | yes | lines (loaded), POIs, closures, warnings, places |
| srkg | SRK Greenway Coalition | managing | yes | lines, POIs, closures, warnings, places, hikes, challenges |
| srg | Schuylkill River Greenways | managing | yes | lines (loaded), POIs, closures, warnings, places, hikes, challenges |
| stc | Susquehannock Trail Club | managing | yes | lines (loaded), POIs, closures, warnings, places, hikes, challenges |
| vtrans | Vermont Agency of Transportation | managing | yes | lines, POIs, closures, warnings, places, hikes; unknown: elevation, podcasts, challenges, photos |
| vctf | Virginia Capital Trail Foundation | managing | yes | lines, POIs, closures, warnings, places, hikes, challenges |
| va-dcr | Virginia DCR State Parks | managing | yes | lines, POIs, closures, warnings, places, hikes, challenges, photos |
| warrior-trail | Warrior Trail Association | managing | yes | lines (loaded), POIs, warnings, places; unknown: challenges, photos, closures |
| wvsta | West Virginia Scenic Trails Association | managing | yes | lines, POIs, elevation, closures, warnings, places, hikes, challenges |
| wv-state-parks | West Virginia State Parks | managing | yes | lines, POIs, closures, warnings, places, hikes, challenges |
| ligtc | Long Island Greenbelt Trail Conference | managing | yes | lines (loaded), POIs, closures (loaded), warnings, places, hikes, challenges |
| arkansas-parks | Arkansas State Parks | managing | yes | lines, POIs, closures, warnings, places, hikes, podcasts, challenges; unknown: photos |
| fl-state-parks | Florida State Parks (FDEP) | managing | yes | lines, POIs, elevation, closures, warnings, places, hikes; unknown: podcasts, challenges, photos |
| fl-state-parks-fkoht | Florida Keys Overseas Heritage Trail | managing | into `fl-state-parks` | lines, POIs, closures, warnings, places, hikes; unknown: podcasts, challenges, photos |
| fta-loxahatchee | FTA Loxahatchee Chapter | managing | yes (or into `fta`) | lines, POIs, closures, warnings, places, hikes, challenges |
| gmo-rtt | GM&O Rails-to-Trails District | managing | yes | lines, POIs, warnings, places; unknown: closures |
| lbl | Land Between the Lakes (USFS) | managing | into `usfs` | lines (loaded), POIs (loaded), closures, warnings, places (loaded), hikes, challenges, photos |
| nett | NorthEast Texas Trail Coalition | managing | yes | lines, POIs, closures, warnings, places, hikes |
| cobb-parks | Cobb County PRCA (Silver Comet; PATH does not maintain it) | managing | yes | lines, POIs, closures, places, hikes, podcasts, challenges |
| pl-rtt | Pearl and Leaf Rivers Rails-to-Trails District | managing | yes | lines, POIs, warnings, places |
| pmtc | Pine Mountain Trail Conference | managing | yes | lines, POIs, closures, warnings, places, hikes |
| tpwd | Texas Parks and Wildlife | managing | yes | lines, POIs, closures, warnings, places, hikes, podcasts, challenges (terms) |
| trlt | Three Rivers Land Trust | managing | yes | lines (loaded), POIs (loaded), closures, warnings, places, hikes, podcasts, challenges |
| forty-mile-loop | 40-Mile Loop Land Trust | umbrella | no; `oregon-metro` proposed | lines, POIs, closures, warnings, places |
| bfta | Bigfoot Trail Alliance | managing | yes | lines, POIs, closures, warnings, places, hikes, podcasts, challenges |
| coastwalk | Coastwalk / California Coastal Trail | managing | yes | lines, POIs, closures, warnings, places, hikes, podcasts, challenges |
| chinook-trail | Chinook Trail Association | managing | yes | lines, POIs, closures, warnings, places (loaded), hikes, challenges |
| ghcc | Greater Hells Canyon Council | managing | yes | lines, POIs, closures, warnings, places, hikes (waiver) |
| maricopa-parks | Maricopa County Parks (both rows) | managing | yes | lines, POIs, elevation, closures, warnings, places, hikes, challenges (terms) |
| nm-rgtc | NM Rio Grande Trail Commission | managing | yes | lines, POIs, closures, warnings, places |
| sart | Santa Ana River Trail county parks | managing | three county folders proposed | lines, POIs, closures, warnings, places, challenges; unknown: hikes |
| odot | Oregon DOT (HCRH State Trail) | managing (road) | into `oprd` | lines, POIs, closures, warnings, places, hikes |
| oprd | Oregon Parks and Recreation | managing | yes | lines, POIs, elevation, closures, warnings, places, hikes |
| peninsula-trails | Peninsula Trails Coalition | managing | yes | lines (loaded), POIs, closures, warnings, places, hikes |
| sdrp | San Dieguito River Park JPA | managing | yes | lines, POIs, closures, warnings, places, hikes, challenges |
| tahoe-pyramid | Tahoe-Pyramid Trail | managing | yes | lines, POIs, closures, warnings, places, hikes |
| wa-parks | Washington State Parks | managing | yes | lines (loaded), POIs, elevation, closures, warnings, places, hikes |
| tahoe-yosemite | (no steward) | route-only | no | lines (loaded), POIs, closures, warnings, places |
| sd-trans-county | (no steward) | route-only | no | lines, POIs, closures, warnings, places |
| kings-canyon-high-basin | an author's two routes | route-only | no | lines, POIs, closures, warnings, places, hikes (guides sold) |
| usfs (GWJ) | George Washington & Jefferson NF (Massanutten Trail) | managing | into `usfs`, `patc` | lines (loaded), POIs (loaded), elevation, closures, warnings, places, hikes, challenges, photos |
| usfs (Mount Rogers) | Mount Rogers NRA (Iron Mountain Trail) | managing | into `usfs`, `mratc` | lines (loaded), POIs, elevation, closures, warnings, places, hikes, photos |

New catalogue rows the batches suggest beyond these: Kentucky DGI (a CC0 statewide trail
layer), FDEP's park system statewide, the Uwharrie Trailblazers, the Kanza Rail-Trails
Conservancy, Los Padres Forest Association, County of San Diego Parks, CPW as an agency (no row
exists), Parks & Trails New York, and the Top of Michigan Trails Council.

---

## 9. The 50 candidate trails whose steward was already catalogued

| reached by the steward's survey | trails |
|---|---|
| **By name (19)** | Tuscarora (c2), Highlands Trail and Shawangunk Ridge Trail (b2), Genesee Valley Greenway (b4, loaded), Mattabesett, Metacomet and Nipmuck (c10, CFPA), Air Line State Park Trail (b5, closure on 2026-10-02), Overmountain Victory, Lewis and Clark, Nez Perce, Old Spanish, Anza, Iditarod and Ala Kahakai NHTs (c11), Kekekabic (b7, c13), Tecumseh (c5), Desert Trail (c7, ONDA as successor), Alaska Long Trail (b7) |
| **In part, or by reasoning (6)** | C&O Canal Towpath (c10 names its NPS alert code, not its line); Shenipsit and Mattatuck (inside CFPA's 848-line Blue-Blazed layer, Reasoned, not named); Lake Ouachita Vista (p05 cites one USFS alert); Collegiate Loop (c7, through Collegiate West waypoints only); Lost Sierra Route (c6 names it as a plan SBTS leads) |
| **Not reached (25)** | Midstate Trail (MA); Lake Okeechobee Scenic Trail (USACE); Buffalo River Trail; John Muir Trail (Big South Fork); Black Creek; Uinta Highline; Wyoming Range NRT; Greenstone Ridge; Teton Crest; Zion Traverse; Metolius-Windigo; General George Crook NRT; Fremont NRT; Tonto Trail; Wonderland Trail; North Umpqua; Boundary Trail (USFS trail 533); Olympic Wilderness Coast; Toiyabe Crest NRT; Lost Coast Trail; Highline NRT; Kettle Crest; Rae Lakes Loop; Timberline Trail; Rogue River NRT |

**Why 25 were not reached:** 23 of them are USFS, NPS or BLM trails, and b6 audited those
agencies' national layers and alert channels, not individual trails. Whether `usfs_trails`,
`nps_trails` or `blm_trails` draw each one by name, and what its forest or park posts about it,
is unchecked (`@unvalidated`). A name query per trail against the three layers, plus each unit's
alerts page, would settle it. Of the other two, the Midstate Trail's steward (the Midstate Trail
Committee and AMC Worcester) has no catalogue row, and the Lake Okeechobee Scenic Trail's
steward, USACE, was audited in c9 without the trail being named.

---

## 10. Still UNKNOWN, and why

141 rows are UNKNOWN. By the reason their evidence gives (a keyword count, Reasoned):

| reason | rows | examples |
|---|---:|---|
| A bot wall or a 403 | at least 67, and most of the 56 that say only "site walled", "site blocked" or "same as above" | `parks.ny.gov` per-park alerts, `floridastateparks.org`, `ksoutdoors.gov` (the Flint Hills construction closure stays unread), `dem.ri.gov`, the Mountaineers, `montanatrail.org` |
| Photos whose licence could not be read | 40 of the 141 | Flickr licence filters need an API key; ArcGIS photo services state no licence; the GIS presumption does not reach photographs |
| A login, a members-only page or social media | 9 named; many more NOT_PUBLISHED rows say "the site has none, Facebook may" | TEHCC closure post bodies; Facebook for the Pinhoti, the GWT, the Tanglefoot and the San Diego Trans-County Trail |
| A site that no longer resolves or was taken over | 5, plus whole orgs | `cdtsociety.org`, `gwt.org`, `caminorealcarta.org` |
| Script-rendered content | 3 | Wix and widget pages neither client renders |
| A key or rate limit | 1, plus figures re-taken from a sibling | NPS `DEMO_KEY`; RIDB `/media` (401); DVIDS |

c12 holds 52 of the 141, and has had neither a skeptic nor a persistence pass. Each UNKNOWN row's
evidence says what would settle it. Most need a person with a browser, a permission ask or a
key, not another automated pass.

---

## 11. What this survey did not cover

- **No feature was downloaded.** Every count is metadata. No overlap between a steward's layer
  and a redistributor's was measured, so the deduplication that **#1709 — Register the steward and the
  redistributor both, and declare which one wins where they overlap** asks for has no numbers
  yet.
- **Nothing was checked on a phone.** Several §3a items say what the registry or the layer holds
  and stop short of the published file (`@unvalidated` where they say so).
- **Licences beyond GIS were not read row by row.** Pages, photos, podcasts and challenge
  programmes keep their own licence questions under decision 21(a).
- **No social media was read**, by rule.
- **The persistence pass skipped c12, non-agency elevation rows, and every non-GIS type** (§2).
- **c11 and c12 had no skeptic** (§1).
- **trail_candidates.json's own gaps stand:** no statewide sweep of Virginia, Maryland, Delaware,
  New Hampshire or Maine, and no enumeration of National Recreation Trails as a class.
- **25 of the 50 catalogued-steward candidate trails were not reached** (§9).

---

## 12. Worth telling the organisations

Security and privacy findings on third-party sites and layers. None was tested, used or copied:
the values are not in this file or in `bcc70dd0:pipeline/reference/org_coverage.json`, only what kind of exposure it is.
Each is for the maintainer to pass on, or not.

| org | what was seen | from |
|---|---|---|
| MATC | A WordPress feed plugin prints a Facebook page access token into public HTML on one page. MATC's credential to rotate | c1 |
| PA DCNR | `BOF_ForestAccessGates` (4,875 gates) has a public `KeyOrComboCodes` field. Never selected, values unread | c17 |
| ATC | 12 public services advertise create and update | b1 |
| NYNJTC, GMC, PATC, VCTF, WV DNR | Public services advertise editing to anonymous requests (old NYNJTC forms; GMC `TRAIL_MASTER`; PATC `Trail_Maintenance_Needs`; VCTF `VCTFmap`; WV DNR `North_Bend_Rail_Trail_WFL1`) | b2, c1, c2, c18 |
| OPRHP | `Palisades Bear Program_results` answers anonymous queries: 343 rows with patron and observer contact fields; three more views expose contact fields | b4 |
| Mohonk Preserve | A volunteer survey results table exposes names and emails | b4 |
| NJDEP | `NJDEP_Park_Mapping_Activity_public_view` exposes volunteers' names | b5 |
| KDWP | A bridge-inspection layer exposes inspectors' names, emails and phones on 8,684 rows | p01 |
| Bay Area Ridge Trail Council | A public hazard-report layer exposes reporter names and emails | c6 |
| IATA, RIDEM, OPRD, ODFW, Illinois DOT, The Trail Conservancy, VTrans, NM Rio Grande Trail Commission, MTRA, CITA | Public layers or pages carry personal fields: Survey123 `email_address` (IATA); observer names on 1,243 records (RIDEM); witness contacts (OPRD sightings); a staff email in `copyrightText` (ODFW); editor emails on 12,648 rows (IDOT); reporter fields (TTC); commenter names and emails (VTrans base service); segment contacts (RGTC); members' names and photos (MTRA uMap); a volunteer's name and an embedded API key constant (CITA) | c5, c10, c13, c18, c20, c21, p02, p06, p08, p09 |
| SHTA | A public service labelled internal names private landowners on its parcel layers | c7 |
| BRBTC, TATC, CDT Society, Pinhoti stewards, Waldo County Trails, Batona Hiking Club, OCVT | Their old or current domains serve injected spam, gambling redirects or parked pages (§7) | c1, c2, c3, c4, c7, c8, c10 |
