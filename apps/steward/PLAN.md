# Campsite Steward — build plan

**Status: phases 0 and 1 built; phases 2 and 3 built but not deployed** (§9): the
analysis job, the read-only web app, and sign-in, lists, club weights and claims. Since
2026-10-27 those live in a `steward` schema in OurHike's Supabase project, which the app
talks to directly: there is no API server (decided by poll; the decisions table). The
schema is written and tested but not yet applied to the project (§11). Phase 4's first
part is built too: the app installs, opens with no signal and queues photos (#1911);
follow-up visits wait on a decision (§11). Five adversarial review passes on 2026-10-27
proved 33 problems in the Python API and the offline layer, all fixed, and their tests
were carried into the SQL (§10); the SQL itself has not yet had a pass of its own. This
file began as the
deliverable of **#1899 — Plan Campsite Steward, a separate app that ranks the A.T.
campsites needing restoration and lets volunteers claim them**, written 2026-10-24 to
2026-10-26 from a planning session with the maintainer: a first-pass analysis, then
five rounds of polls, then a first round on mockups.

Campsite Steward (a working name) is a second PWA, used in a browser on a desktop and
installed on a phone. It helps A.T. maintaining clubs find the overnight sites most in
need of restoration, hands those sites to volunteers, and gets before-and-after proof
back. **It is not part of OurHike.** It lives in this repository and reuses OurHike's
sign-in, photo storage and club-section data, but it has its own name, its own look,
its own API service and its own database.

The evidence grades are CLAUDE.md's: **Measured** (re-runnable, dated), **Reasoned**
(the derivation is shown), and `@unvalidated` (picked, with what would settle it).

---

## The rule this app changes

OurHike does not publish where user-created campsites are. `pipeline/SOURCE_SURVEY.md`
§3b gives the reason: "the 2,333 user-created sites are the ones land managers are often
trying to close, and publishing them as places to camp would put OurHike on the wrong
side of every partner it depends on." `pipeline/build_water_distance.py` never even
requests those rows.

**Campsite Steward publishes every site's location openly, user-created ones included.**
The scored data is two plain public files served beside the app, and anyone can open the
map without signing in. The maintainer decided this in two steps:

- **2026-10-24:** locations for any signed-in user, over club-verified users only or
  locations rounded to the nearest mile until claimed.
- **2026-10-27:** open, with no sign-in at all. The maintainer reasoned that "the data is
  open": ATC publishes the same locations in its own public layer, which anyone can query
  without signing in, and the job reads them from there. A private bucket would have
  protected little and cost a bucket, a token and three secrets. The other options were
  a private bucket, or publishing scores only and having the app read locations live
  from ATC's layer. The poll named the cost of the chosen option: OurHike's
  infrastructure becomes a second public host of the 2,411 user-created locations.

What still holds:

- OurHike's screenshot rule applies to this folder: "a dispersed or user-created
  campsite at a readable zoom" never appears in a preview shot. The steward app's
  preview recipes will draw fixture sites with invented coordinates.
- Nothing fetched or scored is committed to this repository
  (`.github/tests/test_no_committed_data.py`).
- OurHike itself is unchanged. Its export still requests official sites only.

If ATC or a land manager objects, the fallbacks are already designed (§4): scores only
with locations read live from ATC, club-verified access, or locations rounded to the
nearest mile until a site is claimed.

---

## Decisions

Every choice below was put to the maintainer as a poll with a picture: a rendered plan
page and, for the last round, a design canvas of mockups. The alternatives are recorded
so that the next reader knows they were considered, not so that they get argued again.

| Date | Question | Chosen | Offered and not taken |
|---|---|---|---|
| 2026-10-24 | Where the code lives | A folder in this repository, `apps/steward/`, with its own API and web app | A new repository; new routers inside OurHike's backend |
| 2026-10-24 | Who sees user-created site locations | Any signed-in user | Club-verified users only; the nearest mile until claimed |
| 2026-10-24 | Who approves work before it starts | Nobody: claims are instant, and the work is reviewed afterwards | Club pre-approves sites; each claim approved |
| 2026-10-24 | An unsubmitted claim on day 15 | Released back to Open automatically, with reminders on days 10 and 13 | One extension, then release; a reviewer decides |
| 2026-10-24 | Keep round 1, once ATC's approval and insurance rules (§7) were shown | Kept. Instant claims cover every kind of work, and the app shows ATC's rules as guidance | Instant claims limited to "hide the site" work |
| 2026-10-24 | Does being near water force a team? | No. Water distance stays in the priority score only | (dropped on the maintainer's question, not by poll) |
| 2026-10-24 | Largest close-and-restore site one person takes on | 500 ft² | 300 ft²; 750 ft²; each club sets its own |
| 2026-10-24 | How sites are ranked | The composite need score (§2c), with weights each club can change | Plain CSI, lowest first; composite with fixed weights |
| 2026-10-24 | Where the camping rules come from | Transcribed by hand from ATC's regulations page, with a source on every row, reviewed by the maintainer | Ask ATC for the table first; leave camping rules out of v1 |
| 2026-10-24 | What a volunteer claims | One site. The claim screen offers the rest of the site's complex and warns that closing one alone can move campers next door | The whole complex; each site with no nudge |
| 2026-10-24 | How a list is shared | A link, and the person opening it must sign in | Sharing to named people; club-wide lists |
| 2026-10-24 | What a submission must include | Two fixed photo points with a before and after at each, plus any number of extra photos | One before/after pair from any angle; photo points plus a "taken here" location check |
| 2026-10-24 | Follow-up visits | One after each peak season for three years, each a claimable task with its own 14 days | Fixed 6-month, 1, 2, 3-year visits; scheduled by hand; none in v1 |
| 2026-10-24 | Name and look | Its own name and look; the footer credits OurHike's infrastructure | An OurHike sub-brand; its own name in OurHike's look |
| 2026-10-24 | Platform | A PWA only for v1 | Store apps through Capacitor at launch; store apps later |
| 2026-10-24 | What works without signal | Claimed sites: detail, plan, checklist and map saved on claiming; photos queue on the phone | A whole section; online only |
| 2026-10-24 | How the guide uses ATC's material | Our own step lists, short quotes, a link to ATC on every step | Ask ATC to reproduce in full; links only |
| 2026-10-24 | Who marks a submission Verified | Any signed-in user except the claimer and their crew (the exception is the session's call) | Club coordinators seeded by the maintainer; OurHike club admins; users with several verified sites |
| 2026-10-24 | The 241 well-scoring user-created sites | A note on the site page: "This site scores well; your club may want to adopt it" | A coordinators-only filter; leave out of v1 |
| 2026-10-24 | When ATC sees this | Not planned. It stays on the risk list (§10) | Before building; after the read-only app; after a pilot |
| 2026-10-24 | The empty fifth bullet in the original request | Volunteer hours logging | Nothing more; reporting to ATC and land managers; club notifications |
| 2026-10-26 | The look in the mockups | Kept as drawn: IBM Plex type, dark slate and teal, with flagging-tape orange used only for top priority, the camera button and the logo | Less orange; a second direction |
| 2026-10-26 | Who may change a club's ranking weights | Any signed-in user, with a visible history of who changed what and an undo | Named editors per club; the maintainer only; no per-club weights |
| 2026-10-27 | Where the scored files live, first answer | A private Cloudflare R2 bucket of the app's own (replaced the same day, next row) | A private Google Drive folder; run by hand for now |
| 2026-10-27 | Where the scored files live, revisited ("the data is open… can't we just keep this simple?") | Two public static files, `summary.json` and `sites.json`, served beside the app, locations included. No bucket, no secrets. Anyone can see the map without signing in; sign-in is for claims, lists, reviews and weights | Scores only, with locations read live from ATC's layer; keep the private R2 bucket |
| 2026-10-27 | How often the job re-scores | Weekly | Monthly; only when ATC's layer changes |
| 2026-10-27 | Where volunteers' claims, photos, reviews, hours, lists and weights live ("this really is meant to be open source data… is there a simpler solution that would involve Supabase Postgres?"), by poll with a diagram of the three options | No API server: the app talks to OurHike's Supabase project directly. A `steward` schema holds the tables; Postgres functions hold the rules; row-level security says who may write; anyone may read what is public; photos go to a public Supabase Storage bucket; the volunteer work is also published as open files beside `sites.json` | Keep the Python API and move its tables into OurHike's Supabase Postgres; keep the API and its own database as built |
| 2026-10-27 | Who is named on a claim in the open data | Nobody, until the work is verified: before that, the public sees that a site is claimed and when it is due, not who will be out there. The crew sees its own names throughout | Only volunteers who opt in; always named |
| 2026-10-26 | How a follow-up visitor finds a hidden site | The site page adds coordinates and a bearing (for example, "leave the A.T. at mile 12.4, walk 40 ft west, bearing 270°"), and photo point 1 keeps its own position | Mile and offset only; step-by-step directions from parking |

---

## 1. The data: ATC's Campsite Sustainability Index

The source is ATC's Experience Builder app titled **CSI**, which draws the web map
**Campsite Sustainability Index**. Its overnight-site layer is:

```
https://services9.arcgis.com/Nb3RpWJ36xRlYQj2/arcgis/rest/services/Campsite_Sustainability_Index/FeatureServer/1
```

Layer 2, `Relative_Site_Density`, carries the same 3,442 rows with the same fields.

**Measured 2026-10-24** against the live layer, whose data was last edited 2026-08-20:

| | Sites |
|---|---|
| Overnight sites | 3,442 |
| `Site_Type` = User Created Campsite | 2,411 |
| `Site_Type` = Shelter | 538 |
| `Site_Type` = A.T. Club or Agency Created Campsite | 485 |
| `Site_Type` blank | 8 |
| Maintaining clubs (`Trail_Club`) | 29, in 4 ATC regions |

The layer is growing: `pipeline/SOURCE_SURVEY.md` counted 3,354 sites on 2026-06-02.

### The CSI score is a weighted sum, and every row reproduces it

```
CSI = 2·Expansion + 2·Size + OtherSites + WaterEcological + WaterSocial
      + TrailProximity + 3·SideHillFootprint + 3·SideHillBuffer
```

Each indicator is 0–3, except the two side-hill flags, which are 0 or 1. The maximum is
30, and **a higher score means a more sustainable site**. **Measured 2026-10-24:** a
least-squares fit returned whole-number weights, and with those weights the formula
reproduces 3,442 of 3,442 published `CSI_Score` values exactly. ATC publishes no
description of the calculation; its Visitor Use Management page calls the CSI only "a
summary of A.T. campsite inventory data". This reconstruction is the only written method.

| Indicator (weight) | Scores 3 when | Scores 0 when |
|---|---|---|
| Size (×2) | under 300 ft² | over 1,500 ft², or 0 |
| Expansion potential (×2) | field-assessed 0–3; no raw value published | |
| Other sites nearby | nearest site over about 100 ft away | under 30 ft |
| Water, ecological | over 200 ft from water | under 50 ft |
| Water, social | 200–400 ft | under 200 ft or over about 1,320 ft |
| Trail proximity | over 200 ft from the A.T. | under 50 ft |
| Side hill, footprint and buffer (×3 each) | median slope 15% or more scores 1, else 0 | |

**Measured 2026-10-24.** Each threshold was read from the range of raw values behind each
indicator value. The 200 ft and 15% breaks match ATC's 2023 Overnight Site Planning
Guidance ("at least 200 feet from water sources"; side-hill benches "where the slope is
>15%"). ATC's own map colours scores Low 3–12 (622 sites), Medium 13–21 (2,415) and High
22–30 (405).

### Other fields that change what the app does

- **`Inventory_Status`:** Established 1,896 · New 1,489 · Closed/Recovering 49 · Site
  Absent/Recovered 8. 1,477 of the 1,489 "New" rows are user-created, so "New" looks like
  "first inventoried this round" rather than "recently formed". `@unvalidated`: ATC would
  know, and nobody has asked.
- **`Documented`:** 947 of the 2,411 user-created sites are listed in at least one guide,
  almost all in FarOut. A closed site keeps drawing hikers until FarOut changes too.
- **`Site_Photo_1`:** 3,327 rows link a photo in a storage path named
  `atcOvernightSiteAssessmentPhotos`. It could be the "before" baseline. `@unvalidated`:
  nobody has said who owns those photos or whether the app may show them.
- **`RIMS_ID` and `GlobalID`** are both present, so a claim can be keyed to ATC's own id.
- **Licence.** The layer sits on ATC's ArcGIS org with no stated terms. OurHike's
  `atc_licence` block in `pipeline/sources.json` records the maintainer's authorisation
  for facts ATC publishes. This app uses those facts differently, for user-created sites
  OurHike never requested, so the authorisation should be re-read with that in mind
  rather than assumed to cover it.

---

## 2. The analysis (first pass)

The job in `apps/steward/pipeline/` (phase 0, **#1901 — Campsite Steward phase 0: score
ATC's CSI sites in a tested job that writes a public summary and a public sites file**) reads three inputs:

- the CSI layer above, attributes only;
- USGS PAD-US, `services.arcgis.com/v01gqwM5QqNysAAi/ArcGIS/rest/services/Manager_Name_PADUS/FeatureServer/0`,
  queried with batches of 40 site points and joined point-in-polygon;
- ATC parking points, `services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Facilities/FeatureServer/2`
  (483 points), which give a straight-line distance from each site to the nearest parking.

`python -m steward_analysis.build --fetch`, run from that folder, reproduces every number
in this section. They are **Measured 2026-10-26** by the job against the live layers.
They match the planning session's spike of 2026-10-24 exactly, except where §2c says
otherwise. Every threshold is `@unvalidated`, and each one says what would settle it.
`steward_analysis/rules.py` is the one home for the thresholds and repeats what this
section says about each.

### 2a. Complexes

A complex is a group of sites joined by gaps of under 200 ft, such as a shelter and the
user-created sites that grew up around it. The method is single linkage, which is DBSCAN
with a minimum of one point.

| Joining distance | Complexes | With 2+ sites | With 4+ sites | Largest |
|---|---|---|---|---|
| 100 ft | 2,656 | 390 | 89 | 16 |
| **200 ft (used)** | 2,195 | 477 | 157 | 28 |
| 400 ft | 1,919 | 539 | 201 | 32 |

`@unvalidated`: 200 ft sits near the median gap to the nearest other site (198 ft), and
that is all that chose it. What would settle it: a club's own judgement, for a handful of
complexes they know, of which sites belong together.

280 user-created sites share a complex with an official site, which is the "satellite
site" problem.

### 2b. What to do with each site

| Recommended action | Rule | Sites |
|---|---|---|
| **Close and restore** | user-created, and either CSI 12 or below or within 100 ft of water | 647 |
| **Harden the official site** | shelter or club campsite with CSI 12 or below. It can't be closed, so it is fixed in place | 232 |
| Note "your club may want to adopt it" | user-created with CSI 22 or above | 241 |
| Monitor | everything else in the medium band | 2,105 |
| Monitor recovery | already Closed/Recovering or Absent/Recovered | 57 |
| OK | official site with CSI 22 or above | 154 |
| Unknown | blank `Site_Type` | 6 |

`@unvalidated`: CSI 12 is ATC's own Low band, and 100 ft is half of ATC's 200 ft water
setback, picked to catch the worst cases. What would settle it: a club walking a sample
of sites in each action and saying whether the action fits.

A first version also closed user-created sites within 25 ft of the A.T. That rule caught
1,025 sites, because most sites sit right against the treadway (decile distances 0, 9,
19, 30, 44 ft), so it was dropped. Trail proximity only adds points now.

### 2c. Priority: the need score

```
need = 60 × (30 − CSI) / 27            the sustainability deficit
     + 12 if within 100 ft of water     (+6 if within 200 ft)
     +  6 if within 50 ft of the A.T.
     +  8 if in a complex of 4+         (+4 if 2–3)
     + 10 if user-created where a reviewed rule restricts camping (2e)
capped at 100.  Tiers, for actionable sites only: P1 ≥ 60 · P2 50–59 · P3 below 50.
```

The water and trail points count impacts CSI already includes a second time, which is
deliberate: they are the impacts ATC's 2023 guidance sets distances for. These weights
are the default. Any signed-in user may change a club's weights for that club's
sections, and the change is shown with who made it, when, and an undo (decided
2026-10-26). `@unvalidated`, every weight and both tier breaks. What would settle them:
a club ranking twenty of its own sites by hand and comparing that order with this one.

| | Sites |
|---|---|
| Actionable (close or harden) | 879 |
| P1 | 348, in 199 complexes |
| P2 | 310 |
| P3 | 221 |

**Changed 2026-10-26, the session's call.** The planning spike gave the restricted-camping
points to sites whose regime was only guessed from the land manager's type (§2e). The job
gives them only where a reviewed rule says camping is restricted. Until that table
exists the weight adds nothing, so a guess never moves a rank, which is CLAUDE.md's
"never let a display outrun its source". Fed the same guesses, the job reproduces the
spike's tiers exactly, so this is the only difference:

| | Spike, guesses scored | Job, guesses not scored |
|---|---|---|
| P1 | 382 | 348 |
| P2 | 301 | 310 |
| P3 | 196 | 221 |

The sites that moved sit on state parks and state game lands, where the placeholder
guessed "designated only?" or "restricted?". NY-NJ Trail Conference moves most: 19 P1
sites become 11.

### 2d. One person, a team or a crew

| Crew size | Rule | P1 | P2 | P3 |
|---|---|---|---|---|
| **Crew, 4+** | hardening an official site, or over 1,500 ft², or a complex of 4 or more | 261 | 153 | 65 |
| **Team, 2–3** | 500–1,500 ft², or a complex of 2–3, or footprint slope 15% or more | 77 | 97 | 99 |
| **One person** (a buddy recommended) | up to 500 ft², alone, slope under 15% | 10 | 60 | 57 |

How much the 500 ft² threshold matters, on the 647 close-and-restore sites (median size
504 ft²):

| One person if the site is at most | One-person sites | P1 | P2 | P3 |
|---|---|---|---|---|
| 300 ft² | 83 | 3 | 49 | 31 |
| **500 ft² (chosen)** | 127 | 10 | 60 | 57 |
| 750 ft² | 162 | 18 | 71 | 73 |

**Under every one of these thresholds, top-priority work is crew work.** A single
maintainer's useful queue is P2 and P3, and the app should say so rather than offer a P1
site to one person.

Water distance was in the first version of the team rule and was taken out on
2026-10-24. Nothing ATC publishes ties water distance to labour. It cut the one-person
count from 83 to 7 at the 300 ft² threshold.

`@unvalidated`: 500 ft² and 1,500 ft². ATC publishes no crew size or person-hours for a
restoration; the planning session's search found none. ATC's nearest statement is a 2019
article: "It's a safety best-practice for volunteers not to work alone." What would
settle them: hours and crew sizes from the first verified submissions, which the app
records anyway.

### 2e. Is dispersed camping allowed there?

**Measured 2026-10-24:** 3,359 of 3,442 sites fall inside at least one PAD-US unit, and
1,506 fall inside more than one, such as a wilderness inside a national forest. The most
common units:

| Unit | Sites |
|---|---|
| NPS Appalachian National Scenic Trail lands | 708 |
| Jefferson NF | 646 |
| Chattahoochee NF | 306 |
| Shenandoah NP | 258 |
| Mount Rogers NRA | 188 |
| Pisgah NF | 183 |
| Nantahala NF | 183 |

**The analysis does not yet know the camping rule in each unit.** A placeholder guesses
from the manager type alone: USFS "dispersed allowed?", state parks "designated only?",
state game lands "restricted?", Great Smoky Mountains NP "designated only?". The question
marks are part of the value, because none of these is a cited rule.

| Placeholder regime | User-created | Shelter | Club campsite |
|---|---|---|---|
| dispersed_allowed? | 1,089 | 320 | 210 |
| unknown | 744 | 143 | 185 |
| permit_or_designated? (national parks) | 226 | 8 | 24 |
| designated_only? | 182 | 55 | 58 |
| restricted? (state game lands) | 170 | 12 | 8 |

**Decided:** the real rules are transcribed by hand from ATC's camping regulations page
(https://appalachiantrail.org/explore/hike-the-a-t/thru-hiking/camping-regulations/).
That page holds 16 tables, one per state or region, with no date and no download. ATC's
terms of use (https://appalachiantrail.org/terms-and-conditions/, updated 2025-11-21)
forbid "systematic or automated data collection", so the table is typed in by a person,
not scraped. Each row carries the unit, the rule, a short quote, the link and the date it
was read. The maintainer reviews it row by row, and the placeholder stays, labelled as a
guess, until then.

Once the rule exists it changes the recommendation:

- Where dispersed camping is **prohibited**, a user-created site breaks the rules, so it
  is a closure candidate however well it scores.
- Where it is **allowed**, closing a decent site moves the campers to the next spot, so
  the adopt note is the better call.

### 2f. By club

The 12 clubs with the most P1 sites:

| Club | P1 | P2 | P3 | One person | Team | Crew |
|---|---|---|---|---|---|---|
| Roanoke ATC | 59 | 45 | 27 | 20 | 54 | 57 |
| Potomac ATC | 46 | 39 | 30 | 20 | 27 | 68 |
| Mount Rogers ATC | 39 | 31 | 29 | 6 | 32 | 61 |
| Georgia ATC | 24 | 13 | 11 | 5 | 1 | 42 |
| Blue Mountain Eagle CC | 22 | 13 | 11 | 3 | 18 | 25 |
| Green Mountain Club | 22 | 12 | 3 | 5 | 10 | 22 |
| Natural Bridge ATC | 18 | 33 | 11 | 8 | 19 | 35 |
| Carolina Mountain Club | 16 | 13 | 14 | 6 | 18 | 19 |
| Nantahala HC | 15 | 7 | 1 | 2 | 1 | 20 |
| Tidewater ATC | 12 | 6 | 11 | 1 | 9 | 19 |
| NY-NJ Trail Conference | 11 | 30 | 29 | 23 | 26 | 21 |
| Maine ATC | 9 | 16 | 5 | 7 | 5 | 18 |

These numbers move when the rules above move, which is why the app shows the method
beside them.

### 2g. How the analysis reaches the app

The job under `apps/steward/pipeline/` is Python in the style of OurHike's `pipeline/`. The
spatial work uses numpy and shapely, and DuckDB runs the summary's SQL. It writes two
outputs under its gitignored `data/out/`:

- **`sites.json`:** every site with its location and every score, sorted by club and
  then by need, each with its `need_parts` for re-ranking under a club's weights. 4.3 MB
  as written, 470 KB gzipped (measured 2026-10-27).
- **`summary.json`:** counts by club, tier, action and crew size, plus the method text.
  At 8 KB, it is the Analysis screen's whole input, so that screen never downloads the
  sites file to draw a chart.

Both are public (decided 2026-10-27, see the opening section). The web app's deploy
serves them as static files beside itself, in its `data/` folder.

Nothing the job produces is committed: CONTRIBUTING.md's "Data does not go in commits"
applies to this folder too. `.github/tests/test_no_committed_data.py` holds it with its own
rule: nothing under `apps/steward/` that sits in a `data/` folder, and no JSON there except
the web app's named tool configuration (`package.json`, the `tsconfig` files and so on).
`steward_analysis/build.py`'s tests check that the summary carries no coordinate, mile or
site id, and that neither output carries ATC's assessment-photo links. The job never
requests those links, because nobody has said who owns the photos (§1).

**The schedule.** `.github/workflows/steward-analysis.yml` runs the job every Monday at
06:47 UTC, and on dispatch. Each run attaches `summary.json` and `sites.json` to itself
as the artifact `campsite-steward-data`, kept 35 days. Then, on `main` only, it builds the
web app with the pair in its `data/` folder and uploads both to the Cloudflare Pages project
named by the repository variable `STEWARD_PAGES_PROJECT`, with OurHike's existing
Cloudflare token. App and data are one deployment, so the app can never show a week's
scores with another week's code. Until the maintainer creates that project and sets the
variable, the run skips the upload with a notice and stays green.

**Directions from the trail.** The job also measures, for each site, the nearest point
on ATC's centerline (`ANST_Centerline`, simplified to about 5 m) and the bearing from
there to the site, so the site page can say "leave the A.T. at mile 100.0 and walk 100 ft
east (bearing 90°)". Measured 2026-10-27: the distance this gives differs from ATC's own
`Proximity_AT_ft` by a median of 12 ft, and 3,414 of 3,442 sites agree within 50 ft. Where
the two disagree by more than the larger of 100 ft and half of ATC's figure, the job
withholds the directions rather than guess which is wrong: 18 sites, all in Georgia, where
the gap reached 24,770 ft. Their pages say there are no walking directions and to use the
coordinates. A wrong bearing sends a volunteer the wrong way off-trail, which is worse
than none (CLAUDE.md, "omit rather than guess"). `@unvalidated`: the 100 ft gate was
picked to sit well above the 12 ft median; nobody has walked to a site on these
directions.

---

## 3. Architecture

| Part | What it is | Reused from OurHike, or new |
|---|---|---|
| Sign-in | The same Supabase project, so an OurHike account works here. A six-digit code by email, typed back: the shared project's email template sends a code, not a link, and `client/src/lib/auth.ts` (#1600) records why asking it for a link fails. A code also needs no redirect address registered with Supabase | Reused: the project's own sign-in; PostgREST checks the token before any steward function runs |
| Data | A `steward` schema in the same project, under `apps/steward/db/`: tables nothing reaches directly, one Postgres function per action holding its rule, and three open views anyone may read. The app calls the functions through supabase-js. Decided 2026-10-27 in place of a FastAPI service on Render with its own database, which was built, reviewed five times and retired the same day; its tests were carried into the SQL | New |
| Photos | A private Supabase Storage bucket, `steward-photos`, under `<claim id>/<uploader's user id>/<the phone's id for the photo>.jpg`. Only a claim's crew may upload, each under their own id, only while the claim is open, at most 20 photos waiting to go on a claim and 150 a day per account; nothing is overwritten; JPEG only, at most 3 MB. A photo is read through a link Storage signs for an hour, by its crew, by anyone signed in while its claim waits for review, and by anyone once verified (§10, the sixth pass). The phone redraws every photo before it leaves, which strips its location. Nothing redraws it again: the retired API did, against a tampered phone (§10) | Pattern new |
| Open data | The volunteer work as CSV and Parquet beside `sites.json`, written daily from the open views with the public anon key (`steward_analysis/open_data.py`); each verified photo with its path and a link signed for eight days | New |
| Club sections | Which club owns which mile | Reused: `pipeline/export_club_sections.py`'s output |
| ArcGIS reading | Paging an ArcGIS layer | Reused: `pipeline/lib/arcgis.py` |
| Basemap | The map under the sites | Not reused: OpenFreeMap's OpenStreetMap tiles (`tiles.openfreemap.org`), free and keyless at every zoom. OurHike's basemap is a PMTiles file with OurHike's own style and protocol handler, which would have had to be copied in. `@unvalidated`: nobody has checked OpenFreeMap's uptime; if it fails, the table and every site page still work |
| Web app | React, Vite and MapLibre under `apps/steward/web/`, on its own Cloudflare Pages project. Static: hash routes, no server. Built in phase 1 (#1904); the PWA manifest and offline cache come in phase 4 | New |
| Invites | An email invite that is claimed on first sign-in | Copied as a pattern from `RoleInvite`, not a shared table |
| Hours | Hours per person per verified submission | Copied as a pattern from VOLUNTEERING.md's `VolunteerHoursRecord` |

**Because this folder is in OurHike's repository, OurHike's CLAUDE.md applies to it:**

- evidence grades on every threshold;
- no committed data;
- `scripts/test.sh` before every push;
- the screenshot rule.

Its CI jobs need their own workflow file, with the folder in its path scope, so
`scripts/test.sh` can find them.

---

## 4. Who can see what

| Who | Sees |
|---|---|
| Anyone, signed out | Every site with its location and scores, the Analysis summary and the Guide; through Supabase's REST API or the daily open files, every claim's site, state and dates, every club's weights history, and, on verified work only, who did it, who verified it, the steps, the hours and the photos |
| Any signed-in user | Also: lists, reviews, their own hours, and a claim's report and photos once it is submitted, so anyone may review it. Before that a claim's report and photos are its crew's. Names on a claim show only to its crew until the work is verified (decided 2026-10-27) |

Decided 2026-10-27 (opening section). The fallbacks, should ATC or a land manager object:

- **Scores only:** publish no coordinates, and have the app read locations live from
  ATC's own layer, so OurHike hosts no copy.

- **Club-verified only:** a club coordinator verifies a person before they see that
  club's user-created sites.
- **Nearest mile until claimed:** signed-in users see user-created sites rounded to the
  nearest mile, and the exact point unlocks for one site once someone claims it.

---

## 5. Screens

Eight screens were drawn as mockups on 2026-10-26. The canvas is private to the
maintainer's claude.ai account, so it is described here. It is not committed, because
pictures do not go in commits; `.claude/skills/visual-poll/SKILL.md` says why. Every
club, site id, mile, date and person on the mockups is invented. The Analysis screen's
counts are the real ones from §2.

**The look.** IBM Plex Sans Condensed for headings, IBM Plex Sans for text and IBM Plex
Mono for numbers. The palette is dark slate (`#15252A`) and teal (`#1D5C61`) on a cool
off-white (`#F2F4F1`). Flagging-tape orange (`#D9481F`) is used only for P1, the camera
button and the flag logo. Nothing uses ATC's name or marks, and the footer reads "Runs
on OurHike's sign-in and storage. Not an ATC or OurHike product."

| Screen | Device | What is on it |
|---|---|---|
| Club dashboard | desktop | Club and section pickers, filters for tier, action and crew size, a summary line, the map and the site table side by side, save-to-list and CSV export, and a ranking bar showing the current weights, who last changed them, a history link and "Edit weights" |
| Analysis summary | desktop, public | The four headline counts, the priority-by-crew table, P1 by club, the CSI formula and need score, and "What this doesn't know yet" |
| Site detail | phone | The tier, action and crew chips; a complex nudge ("1 of 3 sites less than 200 ft apart"); "Where it is", with mile, bearing, coordinates and a copy button; "Why it ranks", with the indicator bars and raw values; the plan from the guide; Claim and Invite |
| Claim | phone | The 14-day countdown and due date; the release rule; the other sites in the complex, with "Claim all 3"; crew progress against the suggested size; invites by email or link; the note that ATC's cover applies to people working through a club |
| Before you go | phone | Seven checklist items, each linked to its ATC source (§7), and "Saved on this phone". Start work stays disabled until everything is ticked |
| At the site | phone | The no-signal banner with the queued-photo count; the camera with a dashed outline of the before photo to line up on; the four required photos; extra photos; what got done; volunteer hours |
| Review | phone | Before and after photos side by side for each photo point, the reported steps, extras and hours, a note to the volunteer, and Send back or Verify. It says why this user may review |
| My claims | phone | Hours this year, verified and waiting; claims in progress with a countdown; submissions waiting for review; follow-up visits; "3 submissions near you need a reviewer"; lists with Share link |

---

## 6. The claim workflow

```
Open ──claim──► Claimed ──before photos──► In progress ──after photos──► Submitted ──review──► Verified ──► Follow-ups
                (14 days start)                                          (the clock stops)                 (3 seasons)
   ▲
   └────────── not submitted by the end of day 14: released on day 15 (reminders on days 10 and 13)
```

- **The clock stops at Submitted**, not at Verified, so a slow reviewer never costs a
  volunteer their claim.
- **Reviewing:** any signed-in user except the claimer and their crew. Verifying
  confirms the hours and schedules the first follow-up.
- **Follow-ups:** one after each peak season for three years, each a claimable task with
  its own 14 days: re-photograph the points, and redo the debris if it has been moved.
  The three years come from Marion 2003 (§7): "the bulk of this work will occur during
  the first three years". Visiting after peak season follows its advice to redo the
  hiding "immediately after busy or peak use weekends".
- **Invites:** by email or link. An invitee joins the claim's crew, and their hours count
  toward the submission.
- `@unvalidated`: 14 days, which came from the original request. What would settle it:
  how many claims are released unfinished, by season, once the app runs. A January
  claim in Vermont is the case most likely to show it is wrong.

---

## 7. The remediation guide, and where it comes from

One page per action, each a numbered step list in our own words. Every step quotes its
ATC source briefly and links to it. ATC's terms allow quoting but no other reproduction
"without our prior written permission", so the guide summarizes, quotes and links
(decided 2026-10-24). The site page's plan is the guide's step list for that site's
action, so the two cannot drift apart.

**Close and restore a user-created site.** The method is Marion, *Camping Impact
Management on the A.T.* (2003, published by ATC), pp. 58–59 and 105–109:

1. Photograph first: "a photographic record of existing site sizes and conditions
   provide a baseline… prior to implementing corrective actions." (2019 USGS
   best-practices draft hosted by ATC)
2. Hide the site with woody debris and organic litter. "The objective is to hide the
   site." Brushing-in "is rarely effective unless large materials are used".
3. Keep one established fire site, and "only dismantle new fire sites".
4. Block the way in, "where they first leave the A.T. with rocks, woody debris and
   possibly transplanted shrubs".
5. Sign it if the club agrees: "Campsite Closed – Please allow this site to recover".
6. Restore it with half-buried rocks, transplants and watering. "These generally
   require land management agency actions and approval."
7. Come back and redo step 2 after busy weekends.

Scarifying the soil is left out of the one-person steps. The 2019 draft measured it on
its own at 4% plant cover after about 15 years, against 28% for the best combined
treatment. That draft is USGS research, not ATC policy.

**Harden an official site.** From ATC's 2023 Overnight Site Planning Guidance and
Marion 2003, pp. 99–101:

- Consult first: "Trail Clubs must consult with ATC and their land management partners."
- Side-hill benches "where the slope is >15%".
- "Minimize use of tent platforms."
- One central fire ring.
- Cut-and-fill tent pads with stone cribbing.
- Sites "at least 200 feet from water sources" and "just beyond sight of the A.T.
  footpath".

The two documents disagree on slope: Marion builds pads on "10–15% slopes". The guide
cites the 2023 policy and mentions the older figure.

**What ATC's documents put behind approval.** Instant claims (decided) mean the app
shows these as guidance and cannot enforce them:

| Work | What the documents say |
|---|---|
| Hide the site, pick up litter, dismantle new fire rings, block the side path | No approval named |
| Signs, string | Not found whether a sign on federal land needs the land manager's consent |
| Rocks, soil work, transplants, watering | "These generally require land management agency actions and approval"; "soil and vegetation disturbance often require environmental assessments and archaeological surveys" |
| Any renovation of an official site | "Trail Clubs must consult with ATC and their land management partners" |

**Who is covered.**

- ATC's volunteer protections apply to people working "under the auspices of one of the
  designated Trail maintaining clubs or ATC".
- The volunteer agreement "must be completed and signed by any and all participants…
  even for projects lasting only a few hours".
- "Each individual or group must have a stated supervisor".
- ATC's agreement template counts a hiker as a volunteer only if they "coordinated their
  service with {Club}".

**Reasoned, not legal advice:** a stranger who signs up, claims a site and goes out alone
is probably not covered. The claim screen and the before-you-go list say this, and a
volunteer can tick the boxes without it being true.

**Sources**, read 2026-10-24. The PDFs were quoted from their text. HTML pages on
appalachiantrail.org refuse plain requests, so they were read through a fetcher that
returns excerpts; their quotes are near-verbatim.

- ATC Overnight Site Planning Guidance (2023): https://appalachiantrail.org/wp-content/uploads/2023/09/202309-ATC-Overnight-Site-Planning-Guidance.pdf
- Marion, Camping Impact Management on the A.T. (2003): https://appalachiantrail.org/wp-content/uploads/2020/05/camping-impact-mgmt-on-the-a-t-.pdf
- Sustainable Camping BMPs review draft (USGS, 2019): https://appalachiantrail.org/wp-content/uploads/2020/04/at-final-rpt-bmp-review-draft.pdf
- Trail facility management: https://appalachiantrail.org/protect/trail-management/at-partner-resources/trail-facility-management/
- Volunteer protections: https://appalachiantrail.org/get-involved/volunteer/safety-training/volunteer-protections/
- Volunteer services agreements: https://appalachiantrail.org/wp-content/uploads/2020/04/volunteer-services-agreements.pdf
- VSA template packet: https://appalachiantrail.org/wp-content/uploads/2023/02/VSA-Template-Packet.pdf
- Job hazard analyses library: https://appalachiantrail.org/get-involved/volunteer/safety-training/job-hazard-analyses-library/
- Hand tools hazard analysis: https://appalachiantrail.org/wp-content/uploads/2020/04/hand-tools-1.pdf
- Check-in/check-out policy: https://appalachiantrail.org/wp-content/uploads/2022/07/Check-in-Checkout-Policy.pdf
- Trail updates: https://appalachiantrail.org/trail-updates/

**Not found:**

- any ATC crew size or person-hours for a restoration;
- a current ATC step-by-step for closing a site (the method comes from the 2003 report);
- the contents of ATC's A-2 checklist;
- how the CSI is calculated.

---

## 8. Data model sketch

| Table | Holds | Note |
|---|---|---|
| `site` | `RIMS_ID`, `GlobalID`, club, mile, coordinates, indicator scores, action, crew, tier, complex id, camping regime | Loaded from the job's weekly `sites.json`; read-only to the app |
| `club_weights` | club, the four weights, changed_by, changed_at | Every change is a new row, so the history and undo come free |
| `camping_rule` | land unit, regime, rule text, quote, source URL, read_on, reviewed_by, reviewed_on | Replaces the "?" placeholder |
| `list`, `list_item` | named lists of sites, owner, share token | Opening a share link requires sign-in |
| `claim` | site, claimer, state, kind (restore or follow-up), claimed_at, due_at, released_at | One live claim per site, held by a unique index |
| `claim_member` | claim, user, invited_by, joined_at | The crew |
| `photo_point` | site, number, position, set_on | Set on the first visit; reused by follow-ups |
| `submission` | claim, steps done, notes, submitted_at, reviewed_by, verdict | `reviewed_by` is never the claimer or a crew member |
| `photo` | submission, phase (before, after or follow-up), photo point (none for an extra), taken_at | R2 key derived from the id |
| `hours` | submission, user, hours, state (claimed or verified) | The volunteer hours log |
| `membership` | user, club (self-declared) | Rolls hours up per club; grants no permissions |

---

## 9. Build phases, each useful on its own

| # | Phase | Ships | Rough size |
|---|---|---|---|
| 0 | Analysis job | **Built, #1901:** the scoring job, its tests and CI, `summary.json` and `sites.json`, and the weekly run that attaches them to itself until the app can serve them | 1–2 weeks |
| 1 | Read-only app | **Built, #1904:** the dashboard with club, mile-range, tier, action and crew filters, the map and CSV export; the site page with directions, the indicator bars and the plan; the Analysis screen; the guide. Deployed by the weekly job | 2–3 weeks |
| 2 | Sign-in and lists | **Built, not deployed, #1906:** email-code sign-in; lists and share links; club weights with history and restore, re-ranking the dashboard through each site's `need_parts`. Behind them, the `steward` schema in `apps/steward/db/`, tested on Postgres. The web app switches accounts on when the Supabase variables are set | 2 weeks |
| 3 | Claims | **Built, not deployed, #1910:** claims of one site or a cluster, the 14-day clock (reminders in the app; email needs a provider), before you go, crew invite links, photo points and extras, submit, review (verify, send back, or reject), hours | 3–4 weeks |
| 4 | Field-ready | **First part built, #1911:** installable, opens with no signal (the app and this week's analysis precached together), claims saved on the phone, photos queued until there is signal, the before photo shown to line up the after. CSV export came with phase 1. **Not built:** follow-up visits | 2–3 weeks |

`@unvalidated`: the sizes assume one developer working with an agent. Nobody has
measured them. Each phase gets its own issue once this plan is merged; this file does not
list their tasks, by CONTRIBUTING.md's one-home-per-item rule.

---

## 10. Risks, and what nobody has checked

This app sends volunteers off-trail with hand tools, sometimes alone, to places it chose.
That puts it on CLAUDE.md's list of ways an app here can hurt somebody, and the items
below are where the evidence is thinnest.

- **Approval and insurance.** ATC's documents put soil work, transplants and any work on
  an official site behind land-manager approval, and cover only volunteers working
  through a club. Instant claims for every kind of work invite uncovered, unapproved
  work. The app shows the rules and cannot enforce them.
- **Open locations.** Anyone can download the location of every one of the 2,411
  user-created sites from OurHike's infrastructure, with no sign-in. ATC already
  publishes them, so this adds a second host rather than new exposure, but it is the
  thing `pipeline/SOURCE_SURVEY.md` §3b keeps OurHike itself from doing.
- **Open review.** With anyone able to verify, "Verified" means another account looked at
  the photos, not that a club did. The CSV export should name the reviewer of each site.
- **Open weights.** Anyone can re-rank a club's sites. The history makes a change visible
  and undoable; nothing prevents it. The API caps one account at 30 changes a day and
  refuses a change that changes nothing, which keeps the history readable and does
  nothing about a determined account with several addresses.
- **ATC is not being approached (decided).** The app uses ATC's inventory in a way ATC did
  not publish it for. If ATC objects, its likely asks are to hide user-created locations
  or to route claims through clubs. §4's fallbacks and §7's approval table are the
  designs to fall back on.
- **Two weeks against the seasons.** See §6.
- **FarOut-listed sites (947).** A closed site keeps drawing hikers until FarOut is told,
  and nobody owns that hand-off yet.
- **Photo rights** for ATC's assessment photos are unknown (§1).
- **Every threshold in §2** decides which sites reach P1, and every one is
  `@unvalidated`.

---

### The adversarial review, 2026-10-27

These five passes were made against the Python API that the move to Supabase retired
the same day. What carried over: every rule and every test of it, now SQL functions
and `apps/steward/db/tests/`, and the whole offline layer, which did not change. What
did not: the server-side photo redraw (finding 6, N1), the upload limits (N5, the
fifth pass) and the health check (N3, N6), which have no server to live on. The
schema had a pass of its own, the sixth, at the end of this section.

An independent reviewer read phases 0 to 3 and tried to break them against a real
Postgres and server. Thirteen findings; each fix has a test that fails without it.
The commits name each finding by number:

| # | Finding | Fix |
|---|---|---|
| 1 | Fifteen slow photo uploads held every database connection; other requests failed | Sign-in ends its transaction; an upload is checked before its body is read, read with a deadline, and stored outside any transaction |
| 2 | One account held 30 sites by submitting junk, and claimed sites that do not exist | The hold limit counts submitted claims; only sites `sites.json` says need work can be claimed; a send-back needs new after photos; a reviewer can reject, which releases the site |
| 3 | Deleting an account let the same sign-in return as a stranger, able to verify its own claim | The account row stays as a tombstone and that sign-in is refused |
| 4 | A failing club list was refetched by every request | Back off for a minute and serve the last good copy |
| 5 | The Cloudflare token sat in the job that installs and builds | A token-only deploy job |
| 6 | A byte search for EXIF was passed four ways | The server redraws every photo from its pixels |
| 7–13 | A client per signed URL; races past every cap; a send-back that shortened the clock; history that changed with a rename; a 500 on a huge id; CSV formulas; health that did not check the database | Fixed each; see the commits |

Re-checking the fixes, the reviewer closed eleven of the thirteen outright, and found seven new problems:

| # | Finding | Fix |
|---|---|---|
| N1 | One upload declaring 60 megapixels cost 687 MB to decode | Each side is capped at what the app sends (2048 px), read from the header; two photos decode at once at most (a cap on width × height came first, and the third pass got past it) |
| N2 | A reviewer could reject a finished claim and claim the site straight after | Whoever rejects may not claim that site for 30 days |
| N3 | Code ahead of its migration answered healthy while signed-in requests failed | Health compares the database's schema with the code's |
| N4 | One unexpected error stopped the site list ever reloading | The refresh always finishes |
| N5 | A photo had 60 s in all, which a weak signal could not meet | 20 s without a byte, or 300 s in all |
| N6 | Health checks shared the database pool with real requests | Their own pool of one, one check at a time, the answer reused for 5 s (the pool alone still let a flood of probes read as an outage) |
| N7 | A stolen token could lock an account out for good by deleting its data | A deleted account comes back empty on its next sign-in, with its crew places marked left (they had stayed live) |

The third pass checked those seven and attacked phase 4's offline layer. Five of the
seven held; N1, N6 and N7 above carry what it took to close the other two and N7's
note. In the offline layer:

| # | Finding | Fix |
|---|---|---|
| P1 | A photo the API refused was deleted from the phone, so photos taken on a claim that ran out while there was no signal were lost | Refused photos are kept, marked, with **Try again**, **Save a copy** and **Discard**; nothing leaves the phone unless its owner discards it or signs out after a warning |
| P2 | Three triggers could send one queued photo at once, and a lost answer sent it again | One send at a time; each photo carries its queue id and the API stores it once (migration 0004); a newer photo of a slot replaces an older one still waiting |
| P3 | Signing out with no signal and an expired token left the session stored; the next account inherited the queue | Sign-out removes the session itself when supabase-js cannot; everything kept offline is stored under its account |
| P4 | A new version took over an open page and removed files it still had to load | The new version waits; the page offers **Reload now** |
| P5 | The service worker's own CSP blocked its fonts cache | The font hosts are in `connect-src`; in Chromium the cache now fills |
| P6 | Storage could be evicted; reviewers' claims were kept; the basemap style was cached for a month | Persistent storage requested when a photo is queued; only claims you are crew on are kept; the style and TileJSON are revalidated, and only dated tiles are cache-first |

The fourth pass found the third's fixes held, P2's in part, and four new problems:

| # | Finding | Fix |
|---|---|---|
| A | About an hour after the signal went, the sign-in token expired and supabase-js answered "no session": the volunteer was shown as signed out, saved claims would not open and photos were not queued | A session supabase-js still keeps stored is a person still signed in; a request that cannot renew it is "no signal", so the claim opens from the phone and photos queue. supabase-js retries a renewal for 25 s with no signal (measured), so a request waits 5 s at most, and none with no network at all |
| B | Deleting your data reset how many sites you held, while your submitted claims still held theirs | Your own claims count whether or not your place on them is marked left |
| C | A replay of a photo since replaced or removed put it back; an older queued photo could land over a newer one from another crew phone | Receipts for every photo id a claim has received (migration 0004); a queued photo says what was in its slot when it was taken, and the API refuses it with 412 if that has changed. Phones' clocks are not compared |
| D | 0004's backfill cannot see accounts that deleted their data and came back under 0003 | Recorded in the migration; no deployment has run 0003 |

It also moved the decode limit (N1) from a lock inside the worker thread to a limiter
taken before one, so photos waiting to decode hold no thread another request needs.

A fifth pass closed all four, through the app's own sign-in and claim screen with
supabase-js and no signal, and against real uvicorn. Two notes from it are taken: one
account may have at most 4 photos arriving at once (each holds its body in memory,
and nothing limited them), and the 412 now says what the server knows (the point has
a newer photo than the phone had seen), not which photo was taken first.

### The sixth pass: the steward schema, 2026-10-27

An independent reviewer read `apps/steward/db/` against the Supabase-direct design.
Seven findings. Each fix is in the one migration, since none has been applied
anywhere, and each test was checked by undoing the fix and watching it fail:

| # | Finding | Fix |
|---|---|---|
| 1 | The public `steward-photos` bucket on OurHike's production project was free file hosting: any crew member could upload any JPEG and hand out its address | The bucket is private, and its select policy decides who may read a photo or sign a link to one: the claim's crew, anyone signed in while the claim waits for review, and anyone once verified. An object no photo uses is nobody's to read. An account may have 20 uploads waiting to go on a claim and 150 a day. Waiting uploads on a claim that has closed stop counting, so lost answers cannot lock an account out |
| 2 | A crew member could take, or delete, the object a crewmate's phone was about to upload | The uploader's user id is in the object's name, and an upload goes only under the uploader's own. The crew may delete only an object a photo was replaced or removed out of |
| 3 | Any signed-in account could read any claim's notes, review note and photo paths | `read_claim` gives the full detail to the crew, to reviewers while submitted, to whoever last reviewed it, and to everyone once verified. Anyone else gets what the open views show, marked `full: false`, so a screen never reads empty lists as no photos |
| 4 | Each load was held only against the last, so a run of bad loads could halve the sites day by day. The load job installed test tooling beside the loader's login and passed the login on the command line | A load is held against the largest of the last ten, in sites and in workable sites. The job installs psycopg alone, hash-pinned, and the login comes from the environment |
| 5 | The hidden-character check was a hand list | Every code point Unicode calls Cc, Cf or Co, tested against Python's own tables (3.13 and 3.14 agree, measured) |
| 6 | Photos were cached for a year, so a retake stayed served | An hour, the life of a link. The service worker keeps photos a phone has shown, so the before photo still lines up the after one with no signal |
| 7 | `migrate --dry-run` created the schema and its bookkeeping table | A dry run only reads |

Found while fixing 3: a claim nobody had reviewed made the audience check
null, and the null opened the full view. The tests caught it, and the check
now fails closed.

## 11. Still open

Each is the maintainer's: a setting, an account or a decision this build cannot make.

- **The steward schema on Supabase** (`apps/steward/db/README.md`, three steps): add
  `steward` to the exposed schemas, apply `migrations/` with `steward_db.migrate`, and
  give the site loader a login in `STEWARD_SITES_DATABASE_URL`. Until then, signing in
  works but every list, weights or claim call fails, and no site can be claimed.
- **Whether Supabase's `postgres` role bypasses row-level security**, which the photo
  functions rely on to read `storage.objects`. Assumed, and checked by the migration
  runner before it changes anything.
- **The Cloudflare Pages project** named by `STEWARD_PAGES_PROJECT`, and a GitHub
  environment that only `main` may deploy to, holding the Cloudflare token, so the
  deploy job's "main only" holds even against an edited workflow.
- **Email**, for the day-10 and day-13 reminders and for invites by email. Reminders are
  in the app until a provider exists.
- **How long claim photos are kept**, and a sweep for orphaned objects. Neither exists.
  The app deletes a photo's object when the photo is retaken or removed. An object
  uploaded and never put on a claim stays, readable by nobody, as does a replaced one
  once its claim closes. The caps bound how fast they gather: 80 objects a claim, 150
  uploads an account a day. They do not bound the total.
- **A signed link outlives the access it was made with.** Storage checks a link's
  signature, not the policy, so a crew member can sign their claim's photos for as
  long as they like and share the links. That is at most 80 objects a claim, and the
  same is true of downloading the photos. Making it impossible would need a server
  between Storage and the reader.

- **Which Supabase project.** The deploy uses OurHike's production project
  (`SUPABASE_URL`), as §3's "the same project" implies. The sign-in email will carry
  OurHike's template and name.
- **A privacy statement for this app.** It holds a Supabase user id, a chosen display
  name, lists, weights changes, claims, crew places, hours and photos. OurHike's privacy
  policy does not cover a second app.
- **Calls this build made that a poll did not:** a reviewer may reject, which releases
  the site, and may not claim it for 30 days (added after review finding 2 and the
  re-check's N2); a send-back gives the crew the time it had left, at least 7 days; one
  account holds at most 10 sites; deleting your data keeps your weights changes and
  your crew places (marked left, so they give no access), without your name, and a
  later sign-in starts an empty account. From the third pass: signing out signs out
  this browser only, not every device (the Supabase project is OurHike's, so the
  default would sign the person out of OurHike too); a photo the API refuses stays on
  the phone until its owner decides; a session that ends without a sign-out leaves
  that account's offline data on the phone, unseen by the next account, rather than
  deleting photos nobody else has; the API refuses a photo over 2048 px on either
  side rather than shrinking it; a new version waits for the person to reload. From
  the fourth: a phone stays signed in with no signal for as long as its stored
  session lasts; a queued photo of a point someone else has photographed since is
  kept as not sent, and **Try again** puts it over theirs. From the move to Supabase:
  the open files are written daily while ATC's layers are fetched weekly. From the
  sixth pass:
  - photos are private, read through links signed for an hour;
  - a submitted claim's photos and report are open to any signed-in account, so
    anyone may review;
  - a load with under half the sites, or half the workable ones, of the largest of
    the last ten is refused;
  - an account may have 20 uploads waiting to go on a claim and 150 a day;
  - a verified photo's public path carries its uploader's user id. That is a UUID
    with no name in it, but it links one person's photos across claims, and it
    outlives `delete_my_data()`.
- **When peak season ends, by section of the trail**, which decides when each of the
  three years' follow-up visits opens (§6). Follow-ups are not built until it is set.

- Who transcribes the camping rules (decided: the session, reviewed by the maintainer)
  and when. It blocks the "+10 restricted" weight, not phase 0.
- Whether the steward API shares OurHike's Supabase project or only trusts its tokens.
  The plan assumes a shared project, which gives one account across both apps.
- The real name. "Campsite Steward" is a working name.
