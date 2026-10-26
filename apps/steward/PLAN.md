# Campsite Steward — build plan

**Status: planning.** Nothing under `apps/steward/` is built yet. This file is the
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

**Campsite Steward shows user-created site locations to any signed-in user.** Sign-up is
open to anyone with a Google, Apple or email account. The maintainer chose this by poll on
2026-10-24 and confirmed it the same day once the alternatives had been drawn for them:

- club-verified users only;
- the nearest mile until a site is claimed.

What still holds, whatever the decision:

- Locations never appear on a public page, in a share-link preview, in a public bucket,
  or in a search engine's index. The analysis summary page shows counts only.
- OurHike's screenshot rule applies to this folder: "a dispersed or user-created
  campsite at a readable zoom" never appears in a preview shot. The steward app's
  preview recipes will draw fixture sites with invented coordinates.
- OurHike itself is unchanged. Its export still requests official sites only.

If ATC or a land manager objects, the fallbacks are already designed: club-verified
access, or locations rounded to the nearest mile until a site is claimed (§4).

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

A spike in Python (pandas, numpy, and shapely for the land-manager join) read three
inputs on 2026-10-24:

- the CSI layer above, attributes only;
- USGS PAD-US, `services.arcgis.com/v01gqwM5QqNysAAi/ArcGIS/rest/services/Manager_Name_PADUS/FeatureServer/0`,
  queried with batches of 40 site points and joined point-in-polygon;
- ATC parking points, `services1.arcgis.com/fBc8EJBxQRMcHlei/arcgis/rest/services/ANST_Facilities/FeatureServer/2`
  (483 points), which give a straight-line distance from each site to the nearest parking.

**The spike is not in this repository.** It ran in the planning session's scratchpad, as
planning-only work, and phase 0 (§9) rebuilds it as a tested job. Every number in this
section is Measured, in that it was produced from the live layers on that date. Every
rule that produced it is written out here, so the numbers can be re-derived. Every
threshold is `@unvalidated`, and each one says what would settle it.

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
     + 10 if user-created where camping is restricted (2e)
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
| P1 | 382, in 223 complexes |
| P2 | 301 |
| P3 | 196 |

### 2d. One person, a team or a crew

| Crew size | Rule | P1 | P2 | P3 |
|---|---|---|---|---|
| **Crew, 4+** | hardening an official site, or over 1,500 ft², or a complex of 4 or more | 274 | 144 | 61 |
| **Team, 2–3** | 500–1,500 ft², or a complex of 2–3, or footprint slope 15% or more | 91 | 96 | 86 |
| **One person** (a buddy recommended) | up to 500 ft², alone, slope under 15% | 17 | 61 | 49 |

How much the 500 ft² threshold matters, on the 647 close-and-restore sites (median size
504 ft²):

| One person if the site is at most | One-person sites | P1 | P2 | P3 |
|---|---|---|---|---|
| 300 ft² | 83 | 8 | 46 | 29 |
| **500 ft² (chosen)** | 127 | 17 | 61 | 49 |
| 750 ft² | 162 | 27 | 73 | 62 |

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
| Potomac ATC | 48 | 38 | 29 | 20 | 27 | 68 |
| Mount Rogers ATC | 39 | 32 | 28 | 6 | 32 | 61 |
| Blue Mountain Eagle CC | 27 | 13 | 6 | 3 | 18 | 25 |
| Georgia ATC | 24 | 14 | 10 | 5 | 1 | 42 |
| Green Mountain Club | 22 | 12 | 3 | 5 | 10 | 22 |
| Carolina Mountain Club | 21 | 10 | 12 | 6 | 18 | 19 |
| NY-NJ Trail Conference | 19 | 33 | 18 | 23 | 26 | 21 |
| Natural Bridge ATC | 18 | 33 | 11 | 8 | 19 | 35 |
| Nantahala HC | 15 | 7 | 1 | 2 | 1 | 20 |
| Mountain Club of Maryland | 13 | 3 | 2 | 0 | 11 | 7 |
| Tidewater ATC | 12 | 6 | 11 | 1 | 9 | 19 |

These numbers move when the rules above move, which is why the app shows the method
beside them.

### 2g. How the analysis reaches the app

A scheduled job under `apps/steward/pipeline/`, in the style of OurHike's `pipeline/`
(Python, with DuckDB for the SQL steps, on GitHub Actions), writes two outputs:

- **A per-club site file with locations.** It is served through the API to signed-in
  users only, from a private bucket, never OurHike's public one.
- **A public summary:** counts by club, tier, action and crew size, plus the method
  text. It contains no locations, and the Analysis screen draws from it.

Nothing the job produces is committed: CONTRIBUTING.md's "Data does not go in commits",
held by `.github/tests/test_no_committed_data.py`, applies to this folder too.

---

## 3. Architecture

| Part | What it is | Reused from OurHike, or new |
|---|---|---|
| Sign-in | The same Supabase project, so an OurHike account works here | Reused: `backend/app/core/auth.py`'s token check |
| API | A FastAPI service under `apps/steward/api/`, with its own Postgres database. It handles claims, lists, invites, submissions, reviews, hours and weights | New |
| Photos | R2, keyed by the record id, following the pattern in `backend/app/core/photos.py` | Pattern reused, own bucket |
| Club sections | Which club owns which mile | Reused: `pipeline/export_club_sections.py`'s output |
| ArcGIS reading | Paging an ArcGIS layer | Reused: `pipeline/lib/arcgis.py` |
| Basemap | The map under the sites | Reused: OurHike's public basemap tiles on R2 |
| Web app | React, Vite and MapLibre under `apps/steward/web/`, a PWA, on its own Cloudflare Pages project and domain | New |
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
| Anyone, signed out | The Analysis summary (counts, no locations) and the Guide |
| Any signed-in user | Every site with its location, lists, claims, reviews, and the club weights with their history |

The fallbacks, drawn for the maintainer on 2026-10-24 and not chosen:

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
| `site` | `RIMS_ID`, `GlobalID`, club, mile, coordinates, indicator scores, action, crew, tier, complex id, camping regime | Rebuilt nightly by the job; read-only to the app |
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
| 0 | Analysis job | The scoring job as a tested, scheduled pipeline; the public summary; per-club site files | 1–2 weeks |
| 1 | Read-only app | The Analysis screen, the dashboard with club and section filters, and the guide | 2–3 weeks |
| 2 | Sign-in and lists | Supabase sign-in, locations for signed-in users, lists and share links, club weights with history | 2 weeks |
| 3 | Claims | Claims, the 14-day clock and reminders, before you go, invites, photo points and extras, review, hours | 3–4 weeks |
| 4 | Field-ready | Offline for claimed sites, the photo-point outline, follow-up visits, CSV export | 2–3 weeks |

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
- **Open location access.** Any account sees 2,411 user-created sites. The rule at the
  top of this file keeps them off public surfaces, but not out of the hands of whoever
  signs up.
- **Open review.** With anyone able to verify, "Verified" means another account looked at
  the photos, not that a club did. The CSV export should name the reviewer of each site.
- **Open weights.** Anyone can re-rank a club's sites. The history makes a change visible
  and undoable; nothing prevents it.
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

## 11. Still open

- Who transcribes the camping rules (decided: the session, reviewed by the maintainer)
  and when. It blocks the "+10 restricted" weight, not phase 0.
- Whether the steward API shares OurHike's Supabase project or only trusts its tokens.
  The plan assumes a shared project, which gives one account across both apps.
- The real name. "Campsite Steward" is a working name.
