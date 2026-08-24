# Trail data within a day of NYC — a qualified survey (August 2026)

Companion to [SOURCE_SURVEY.md](SOURCE_SURVEY.md) (the A.T. survey whose qualification frame
this borrows), [README.md](README.md) (the pipeline that would consume these) and
[../features/SOURCE_REGISTRY.md](../features/SOURCE_REGISTRY.md). This is
[#770](https://github.com/OurHike/OurHike/issues/770)'s deliverable, inside
[#768](https://github.com/OurHike/OurHike/issues/768)'s program — the maintainer's 2026-08-18
scope call: Hudson Highlands core, plus the Catskills, plus everything NYNJTC maintains.

Written 2026-08-18 from live probes; **every count and every ArcGIS date below was read from
the layer itself that day**, not from a page's claim about itself. Where a service exposes no
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
| NYS DEC `dil` services | ✓ 5,277 hiking (+4 uses) | ✓ 21,466 + 10,524 + 314 | | ✓ | **2026-08-11** | register next — §3 |
| NYNJTC public extracts (LP, HT, SRT) | ✓ 43 + 12 | | ✓ one live detour | ✓ | **2026-08-04** | register now — §4 |
| NYNJTC full network | ✓ | ✓ | | org-internal | GIS program alive | **agreement, not a scrape** — §4 |
| NJDEP State Park Service Trails | ✓ 3,305 | ✓ (Land/62, uncounted) | | ✓ | undated (on-prem) | register after terms read — §5 |
| NJ Geospatial Forum Statewide Trails | ✓ 13,296 | | | ✓ | 2026-06-09 | the NJ-county answer — §5 |
| NJ Highlands Council HT copy | ✓ | | | ✓ | unprobed | secondary to NYNJTC's own — §5 |
| ATC / NPS APPA layers | ✓ | ✓ | ✓ | ✓ | 2026-08-04 | already in hand (sources.json) |
| Westchester County GIS | ✗ none found | | | ✓ server, no trails | — | thin — §6 |
| Other NY counties (Rockland, Putnam, Orange, Dutchess…) | ? | ? | ? | unprobed | — | awaiting maintainer links — §6 |
| data.ny.gov copies (DEC 2013, OPRHP 2014) | stale | | | ✓ | a decade ago | precedent, not a source — §9 |
| OpenStreetMap | ✓ | ✓ | | ✓ | continuous | gap-filler question, measured in #771 — §7 |

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
  (as-is, no warranty, no duty to maintain). **NEEDS REVIEW:** read the agreement in full
  before registering — it is the first source in this program whose upstream wrote terms
  down, and the reading decides whether NJ needs an ask at all.
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
| Minnewaska / Shawangunks | OPRHP | Long Path + SRT (NYNJTC), and NYNJTC's live fire-detour layer |
| Catskill Forest Preserve | DEC (`UNIT: CFP`) | Long Path (NYNJTC), NYNJTC's Catskill programs, 314-lean-to layer statewide |
| NJ Highlands / Ramapos | NJDEP + the statewide compilation | Highlands Trail (NYNJTC), NYNJTC maintains |
| The AT corridor through NY/NJ | ATC/NPS (already shipping) | crosses OPRHP, PIPC and NJDEP ground registered above |

The steward-versus-owner distinction matters for outreach too: OPRHP's answer covers the
*data*; NYNJTC's covers the *stewardship* and the network — one does not substitute for the
other.

## 9. Licensing, summarized

No blanks, per the issue. "Unstated" is an answer; an empty cell is not.

| source | terms | state |
|---|---|---|
| NYS OPRHP (4 layers) | Unstated; no-warranty disclaimer on the item | **Ask in motion** — maintainer outreach declared 2026-08-18, recorded in `oprhp_licence` (#769) |
| NYS DEC (`dil` layers) | Unstated; no copyright text on service | **NEEDS REVIEW** — bundle with the OPRHP ask; Open-NY listing is precedent |
| data.ny.gov copies | No licence field on either listing | Not a source: DEC copy last updated **2013**, OPRHP copy **2014-12-24** — proof the State publishes these openly, and proof the AGOL/on-prem services are the copies of record |
| NYNJTC public extracts | Unstated (`licenseInfo` empty on both items, read 2026-08-18) | Covered by the maintainer's NYNJTC conversation (#768) |
| NYNJTC full network | Withheld | **An agreement, not a scrape** (SOURCE_SURVEY.md §10, reaffirmed) |
| NJDEP layers + NJ compilation | **NJDEP Data Distribution Agreement — stated** | **NEEDS REVIEW** — read in full; possibly no ask needed |
| ATC / NPS | See `atc_licence` in sources.json | In hand |
| OpenStreetMap | ODbL 1.0 | In hand (basemap + water precedent) |

## 10. What to do with all this, ranked

1. **Register DEC** — `external_arcgis_layer` entries for the hiking layer, backcountry
   features, trailheads and lean-tos; the `max(UPDATED)` statistic recorded as the
   freshness marker. No new fetch code needed.
2. **Register NYNJTC's Long Path and Highlands Trail services** — public, fresh, stable
   URLs; review-only until the conversation concludes.
3. **Read the NJDEP Data Distribution Agreement**, then register the two NJ layers.
4. **Run the spike** ([#771](https://github.com/OurHike/OurHike/issues/771)) on OPRHP +
   Long Path over Harriman/Hudson Highlands — it also owns the OSM coverage measurement
   this survey deferred (§7).
5. **NEEDS REVIEW, gathered:**
   - (a) The maintainer's county links (#770 comment) — Westchester found nothing
     structured; the other NY counties are unprobed.
   - (b) **Long Island: in the ring or out?** §1's open edge.
   - (c) **Bundle DEC into the OPRHP ask** — one state, two agencies, Open-NY precedent
     for both.
   - (d) **NJDEP Data Distribution Agreement** — full text unread.
   - (e) **NYNJTC's informal-trails layers are a do-not-ship hazard** — the §3b posture
     from the A.T. survey, applied here before anyone fetches them.
   - (f) **PIPC's NJ section** — expected inside the NJ layers, unverified.
   - (g) Whether DEC's Back Country Features asset types include **water** — raises the
     evidence bar if true (CLAUDE.md's four ways).
