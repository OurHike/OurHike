# OurHike — Structure Inventory (Feature Design v1)

Companion to [../FEATURES.md](../FEATURES.md), [../OurHikeValues.md](../OurHikeValues.md) and
[../TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md). This document owns **the
roving-volunteer survey of a club's built structures**: the programme, the survey app a
volunteer carries, the review chain the club runs, and the inventory the club keeps.

It applies [FIELD_NOTES.md](FIELD_NOTES.md)'s layering rule to a club's own structures (a
visit is a dated observation, never an edit), hands Unsafe findings to
[REPORT_A_PROBLEM.md](REPORT_A_PROBLEM.md) rather than building a second hazard queue, builds
on [VOLUNTEERING.md](VOLUNTEERING.md)'s `org_access` and its "no notification of any kind"
rule, lives inside [ORG_ONBOARDING.md](ORG_ONBOARDING.md)'s console and section registry, and
builds the `SurveyPass` that [INVASIVE_SPECIES.md](INVASIVE_SPECIES.md) sketched.

**Source.** [structure-inventory-handoff/](structure-inventory-handoff/) is the design
handoff as supplied on 2026-11-04 and is not edited to match what gets built.
`SPEC.md` there is the argument, `HANDOFF_README.md` the map of the 36 screens, and `copy/`
each screen's rendered text. The 36 artboards and the walkthrough page are held by the
maintainer, not committed. This document is the one home; where it and the handoff
disagree, this one is meant to win, and says why.

Two things about the folder that its own README does not say. **It is about 873 KB as
committed, with three plates** (measured from the tree on 2026-11-04), where the README
says "the two small plates; about 250 KB": that line predates the Steps plate and the move
to photographs. And **13 of its `copy/` files were recaptured** - the twelve field cards and
the plate sheet - from the walkthrough page rather than from the artboards, because the
zip's copy described the earlier pencil plates; each of those files says so in its header.

**Scope: designed, nothing built** (2026-11-04). Not yet placed on the roadmap; see Open
questions. The handoff's sample data and its draft ATC request point at the NY-NJ Trail
Conference's A.T. stretch as the first club, which is an expectation, not a decision
anyone has recorded.

---

## The problem, stated plainly

A trail club builds and keeps things nobody else keeps a condition record for: bridges,
puncheon, shelters, privies, campsites, water sources, blazes, signs, kiosks, parking,
steps, and the water bars and check dams in between. Upstream data is authoritative about
what exists and where, and silent about what a place is like today
([FIELD_NOTES.md](FIELD_NOTES.md), "two clocks"): ATC's GIS knows where a shelter is, not
that the bridge below it is scouring at one abutment. What the club itself knows is
wherever its maintainers wrote it down. How complete that is, for any club, nobody here
has measured.

The people who could fill that gap already walk the trail. What stops them is the same list
[VOLUNTEERING.md](VOLUNTEERING.md) names for every other kind of help: not knowing where
help is wanted, not knowing what to look for, and not knowing whether it mattered. A survey
tool also has two failure modes of its own:

- **It sends everyone to the same places.** Volunteers walk the stretches they like, so the
  data thickens where it was already thick.
- **It makes somebody adjudicate.** Two people log the same bridge differently, and the
  record needs an owner to decide which one is true. That owner is a standing job, and
  [FIELD_NOTES.md](FIELD_NOTES.md) has already argued why a standing reconciliation job is
  the thing that quietly stops happening.

This design answers the first with **priority areas** computed from where records are
thinnest, and the second by **never overwriting anything**.

---

## The six rules every screen assumes

1. **Nothing is overwritten.** A structure is one row; every visit to it is a new
   observation row, append-only, with the volunteer, the time and the review state.
   "Current condition" is the latest accepted observation: a query, not a column. Two
   volunteers logging the same bridge on the same day is two rows and free data, never a
   conflict to adjudicate.

2. **The phone records what it knows and nothing it assumes.** The Location screen plots
   every GPS reading where it landed, on a plain grid with a scale bar and a north arrow,
   and saves the median with its accuracy and the count. No basemap, no trail line, no pin
   to drag. The mile and the distance to the centerline are computed on the server after
   upload and stored beside the raw point, never instead of it. A shelter 300 ft off the
   trail must never be drawn on it.

3. **A guess is saved as a guess.** Size is a bucket ("10 to 25 ft") unless the volunteer
   measured it, and every size carries its `size_method` all the way to the CSV. Nothing a
   volunteer estimated is rendered in the voice of a measurement. This is `CLAUDE.md`'s
   "never let a display outrun its source", applied to a tape measure.

4. **Works with no signal, uploads on any signal.** Every field screen works offline. A
   record goes into the outbox the moment it is saved; words upload before photos;
   cellular upload is on by default with a toggle; the app says what is still waiting.
   Nothing polls the radio (`client/src/lib/outboxSync.ts`: "Deliberately not on a
   timer").

5. **The club's own chain reviews, not a global moderator.** The Local Chair accepts; a
   section supervisor accepts for the sections under their role. Unsafe is never a
   global alert: it is first in the Chair's queue and, when mail is enabled, one email to
   each approved club admin (the Local Chair, decided under Permissions).

6. **No streaks, no badges, no notifications.** `client/src/test/noNotifications.test.ts`
   fails the build if the Notification or Push API appears in shipped code. A claim on an
   area is a heads-up that clears itself. Coverage shows the trail's need, never a
   volunteer's score. Reminders are in-app, on open.

---

## What a volunteer does

The screens are in [structure-inventory-handoff/HANDOFF_README.md](structure-inventory-handoff/HANDOFF_README.md)
by code; this is the shape of the whole.

**Once, at home (1a–1g).** Join a club's survey, sign the club's own waiver by typed name,
and work through the field guide: twelve cards, one per structure type, each showing one
photograph per problem with "Unsafe means", the one rule, and the ATC or NYNJTC source for
every line. A "call it" check uses the real Condition screen. Then pick a priority area on
a map coloured by need, and optionally claim a day to walk it.

**On the trail (2a–2k).** For each structure: what it is, where it is, whether it is one
already known, photos, about how long, what shape it is in, what should happen, check and
save. One question per screen, a progress line, "Save for later" in the header, Back always
to the previous step. A walk that stops early records where it stopped.

**Back in signal (3a).** The outbox uploads; the Waiting to upload screen shows what has
not gone yet.

**The club (3b–3e, web).** A review queue with four verbs (accept, send back, merge, not
ours) and a note, Unsafe first. A coverage page showing which areas need a walk. An
inventory, worst first, with each structure's full history and the exports. A review map
with every record as a dot.

The field card is one component and one content file, shown in training and from the
Condition screen. Its content is
[structure-inventory-handoff/fieldGuide.json](structure-inventory-handoff/fieldGuide.json),
and **no line goes on a card without a source** in that file's `sources` field.

---

## Decisions already made

From the handoff's decisions table; the dated rows changed during design review.

| Decision | Chosen | Why |
| --- | --- | --- |
| Where it lives | A second front door: same client source, same backend, same origin, its own install icon at `/survey/` (2026-11-04) | One origin shares the map packs and sign-in; the volunteer still gets an icon that is only the survey |
| Form shape | One question per screen, a progress line, "Save for later" on every step | A thumb in a cold hand |
| Location capture | Timed sampling shown as a plain readings map; the median saved with accuracy and count | A presumed place on screen tempts people to accept a wrong fix |
| Snap to trail | Never on the phone; the server computes distance and mile afterwards | Rule 2 |
| Photos | Two shots that always work, plus one or two suggested per type; no people in frame | A fixed list overfits the bridge |
| Size | Buckets, optional, saved as an estimate; a tape one link away | People will not measure; a bucket still tells a crew what to bring |
| Condition | Good, Fair, Poor, Unsafe, with the definition on screen and the type's reminder above it | Four words everyone already uses |
| Repair | Leave it, Minor, Major, Replace, Take it out; a timing; free text. "The Local Chair decides what happens and when" | The volunteer suggests, the crew leader prices |
| Where to walk | Computed priority areas open to all, with a day-bound claim that clears itself | Effort lands where data is thinnest; overlap is free data |
| Who reviews | The club's chain | It is how a club already works, and `org_access` already expresses it |
| Hazards | Unsafe also files a Report a Problem, one tap, no re-typing | The closure path and moderation already exist |
| Identity | A readable code (`AT-NY-BR-014`) plus a field for any existing id | The guidebook, ATC's lists and NPS each have their own |
| Publication | Club-private, with a per-club switch to publish locations only | Condition notes are the club's working data |
| Field-card art | Photographs, one per issue, in one house treatment (square, one ink colour on paper, a soft vignette); a "photo wanted" tile where none exists, never a drawing (2026-11-04) | A volunteer must recognise the thing on the trail; a photo of a rotten stringer beats any drawing of one |
| Whitelabel | Club name from `clubs`; mark, accent and waiver text from a branding block that does not exist yet | A general OurHike need, its own change |

---

## Where it meets the codebase: six conflicts

The handoff checked its plan against `main` on 2026-11-04 and found six places where the
design asks for something the code does not do. Each is carried here with its resolution.
Conflict 2 was the maintainer's call and was decided on 2026-11-04; the others are resolved on paper.
The file references below were re-checked against `main` at ff829580 on 2026-11-04; two of the handoff's details had drifted and are corrected where they fall.

### 1. The backend holds no centerline, and rule 2 asks it to compute a mile

`reports.mile` is documented as a client claim: "this backend holds no centerline geometry
- the trail is a published artifact the client and the pipeline share, not a table here"
(`backend/app/models/report.py`).

**Resolution.** `backend/app/core/trail_axis.py` projects a point onto the club's own
section line, `org_sections.geometry` (GeoJSON LineString as text, with `start_mile` and
`end_mile` on the row, `backend/app/models/org_registry.py`), and returns the section, the
mile and the distance off the line. Pure Python, no PostGIS, by the repository's standing
choice. The client never sends a mile; `mile` and `off_line_ft` are nullable server
columns filled on accept, and by `backend/scripts/inventory_place.py` for records accepted
before their club drew its sections.

**A club that has drawn no sections gets no mile.** Decided 2026-11-04 by the maintainer by
poll, over the handoff's fallback to the published `trails.geojson` and `trail_miles.json`.
That file's only mile-bearing line is the A.T. centerline, and nothing in the registry says
which of a club's trails is the A.T., so the fallback would have given an A.T. mile to a
structure on any trail within 3 mi of it. The fallback is #2029 — A club that has drawn no
sections gets no structure mile, until the registry can say which of its trails is the A.T.

**A section's line is assumed to be drawn from its start anchor to its end anchor.**
`@unvalidated`: the console stores the line as pasted text and nothing records its
direction, so a line drawn the other way reads its miles mirrored inside the section. What
would settle it: each club's drawn sections checked against the published axis.

**The agreement tolerance is `@unvalidated`.** The handoff proposes that three fixture
points agree with `client/src/lib/trailPosition.ts`'s `locateOnTrail` to within 0.05 mi.
That figure is a pick. On `client/src/lib/trailAxis.golden.json`, a synthetic two-mile line
whose calibration runs 3% long then 2% short, the largest disagreement measured 2026-11-04
is 0.017 mi. What would settle it: one real section's line, and the largest disagreement
between the two projections along it.

### 2. Priority areas need an "area", and the backend has only sections

The design computes areas parking lot to parking lot. The backend has `org_sections`, the
club's own division of each trail, with `start_anchor` and `end_anchor` as free text, and no
parking points: those live in the pipeline's published POI files.

**Decided 2026-11-04, by the maintainer by poll: for v1, the area is the `org_section`.**
The coverage rule runs per section over the observations conflict 1 places in it. The
Coverage screen's note changes from "areas are computed from the records, parking lot to
parking lot" to say that areas are the club's own sections. Parking-to-parking areas stay a
later comparison, once the backend reads published POIs.

**What the alternative would have drawn, measured for the poll.** ATC's own layers, fetched
2026-11-04: the A.T. centerline (`ANST_Centerline`) and official parking areas
(`ANST_Facilities` layer 2), clipped to NYNJTC's polygon in `APPA_Trail_Club_Sections`.
The 367 centerline segments inside the polygon chain into 156.2 mi; ATC's own `Length_Ft`
sums to 155.9 mi. **Not all of that is attributed to NYNJTC.** ATC's `Trail_Club` field names
NYNJTC on 365 of the 367 segments, which sum to 152.2 mi. The other two are the I-80 bridge,
0.5 mi, which ATC attributes to AMC's Delaware Valley Chapter, and a 3.2 mi segment whose
`Trail_Club` and `Region` fields hold the codes `7` and `1` where every other row holds a
name; its `Comments` call it the Palisades Parkway relocation, inside NYNJTC's stretch, so it
reads as a coding inconsistency rather than another club's trail, but nothing here settles
which. Of the 59 parking areas, 49 sit within 500 ft of the line (median 59 ft away for
those 49; 75 ft for all 59), making 43 trailheads once lots within 0.1 mi of each other are
merged. That gives 44 parking-to-parking areas, median 2.7 mi, from 0.1 mi to 14.8 mi (Elk
Pen to Seven Lakes Drive). Dropping both segments not attributed to NYNJTC moves none of
those counts or the median; the longest area falls to 12.8 mi, because the Palisades
Parkway segment lies inside it. The 500 ft and 0.1 mi cut-offs were picks for that picture,
not findings. One
difference was already visible: the handoff's sample area "Dennytown Road to Canopus Hill
Road" ends at a road with no ATC parking area, so a parking-to-parking rule would never
draw it.

**Still unmeasured:** whether the pilot club's registered sections start and end at those
trailheads. If they do, sections and parking-to-parking areas colour the same map. If they
do not, the coverage map colours maintainer sections rather than walks, and the later
comparison is where that shows.

### 3. "Alerts the Local Chair" and a daily reminder, against no notifications

The Condition screen says Unsafe "alerts the Local Chair when it uploads", and the Outbox
screen offers a daily reminder. `noNotifications.test.ts` enforces the privacy policy's
"OurHike sends no notifications at all", and `VOLUNTEERING.md` says "No notification of any
kind".

**Resolution: neither is a push.** Unsafe puts the record first in the queue and, when
`settings.mail_enabled` is on (`backend/app/config.py`, default off), sends one email to
each approved club admin, the Local Chair as decided under Permissions, through `backend/app/core/mail.py` with a new `MailPurpose.inventory_unsafe`; the
suppression list and `List-Unsubscribe` are already handled there. The reminder is a
banner the survey app shows on open when anything has waited more than a day, plus a flush
of the outbox when the app comes back to the foreground. Nothing does that today: the
outbox is flushed after something is queued or retried (`client/src/App.tsx`,
`client/src/chrome/PoiCard.tsx`), and none of the `visibilitychange` listeners in the
client calls `syncOutbox`. The Outbox screen's copy changes to "Show me on open if anything
waits a day". **The maintainer confirms this reading of the privacy line**; it is an open
question below.

### 4. GPS lock, satellites, cell and Wi-Fi are not all observable on the web

The Location screen shows "GPS locked · 9 satellites · Cell · No Wi-Fi". The web gives a
position and an accuracy and nothing else (`client/src/lib/useGeolocation.ts`'s
`GeolocationFix` is `at`, `accuracyFeet`, `accuracyM`, `fixedAt`). The one native location
plugin installed, `@capacitor-community/background-geolocation`, gives accuracy, not a
satellite count. `navigator.connection.type` tells cellular from Wi-Fi on Android Chrome and
does not exist on iOS.

**Resolution: record what the platform gives and label the rest unknown.** `gps_lock` is
derived, `satellites` stays null until a native plugin exists, and `connection` is
`cellular | wifi | none | unknown`. The chips render only what is known; the row stores the
nulls. The lock rule's numbers are `@unvalidated`; see the evidence table.

### 5. Two apps on one origin share one IndexedDB, including the outbox

`client/src/lib/outbox.ts` keeps one key, `ourhike:outbox`, in idb-keyval's default store.
On the same origin, the main app's flush would meet cargo it does not know.

**Resolution.** The survey app runs the same outbox module on its own store
(`createStore('ourhike-survey', 'outbox')`), so each app flushes only its own queue. The
new cargo is an optional field, the convention that means nothing stored ever needs a
migration. The downloaded map packs are shared on purpose: that is what the same origin is
for.

### 6. Production has no SPA fallback, so the survey's addresses are query strings

`ourhike.org` is GitHub Pages with no `404.html` or `_redirects`; `/app/my/tread` answered
404 in production when measured on 2026-09-17 (recorded in `pr-preview.yml` and
[ORG_ONBOARDING.md](ORG_ONBOARDING.md)). Previews and UA run on Cloudflare Pages and have
the fallback.

**Resolution.** The survey lives at `/survey/` and addresses a club as
`/survey/?org=<slug>`, the `?org=` convention `/my/tread` already uses. Screens inside it
are app state, as everywhere else in the client, which has no router library by design.

### Also checked, and clear

- **New tables need row-level security in their own migration.** `RLS_TABLES` and
  `rls_statements()` copied from `b3d1c7a94e02_enable_row_level_security.py`;
  `test_migration_rls.py` fails the build otherwise.
- **Enums are `native_enum=False` with a length, so Postgres holds a plain `VARCHAR(N)`
  and no type.** Not a `CHECK` constraint, whatever `test_column_conventions.py`'s header
  says: migrated to head `e4b8d2a7c391` on 2026-11-04, the public schema held no `CHECK`
  constraints at all, and SQLAlchemy creates one only under `create_constraint=True`. The
  values are validated by Pydantic at the edge and by the enum in the session. Timestamps
  are naive UTC (`test_column_conventions.py`).
- **The OpenAPI document only grows.** New paths, no new required fields on existing
  request schemas, so `backend/openapi_baselines/` is untouched.
- **Photos reuse the report pipeline with no table.** A key of their own beside
  `photo_key`, `poi_photo_key` and `note_photo_key` in `backend/app/core/photos.py`, JPEG
  magic check, `MAX_PHOTO_BYTES` (2 MiB) through `read_capped_body`, `MAX_REPORT_PHOTOS`
  (6), presigned links for `PHOTO_URL_TTL_SECONDS` (300 s), private R2. On the phone,
  `client/src/lib/reportPhoto.ts`'s `preparePhoto(file, 1600)` already strips EXIF by
  re-encoding.
- **Review states follow the report pattern**, `submitted` becoming `accepted`,
  `returned`, `merged` or `not_ours`, with the same audit columns.
- **Flow coverage needs a new directory.** The handoff names `client/src/test/flowCoverage.ts`
  for `SCREEN_DIRS`; the constant is in `client/src/test/flowCoverage.test.ts`, line 38,
  and the survey's screens join it there.

---

## Data model

Five tables, prefix `inventory_`, plus one settings row per club. String ids from `uuid4`,
naive UTC timestamps, every enum `native_enum=False`. Column lists are whole rows; the
handoff's `SPEC.md` §Data model has each column's reasoning.

```
inventory_enrollments        a volunteer's standing in one club's programme
  id, club_id → clubs, person_id → profiles
  waiver_version, waiver_signed_at, typed_name     which text was signed, and by what name
  training_completed_at?, field_day_at?, created_at
  unique (club_id, person_id)

inventory_structures         one physical thing on the trail
  id, club_id, trail_id? → org_trails, section_id? → org_sections
  kind        bridge | puncheon | shelter | privy | campsite | water | blaze | sign
              | kiosk | parking | steps | other
  subkind?, code (readable, unique per club, assigned on first accept: <trail>-<state>-<kind>-<n>)
  external_ids?   {"atc": …, "nps": …, "guidebook": …}
  lat, lon        from the latest accepted observation
  mile?, off_line_ft?    server-computed (conflict 1)
  poi_id?         a published POI id when one matches
  status          active | removed | merged,   merged_into_id? → self
  published       default false,   created_at, created_by

inventory_observations       one visit to one structure; append-only
  id (the client's id: upload is idempotent on it), structure_id, club_id
  pass_id? → inventory_passes, volunteer_id → profiles
  captured_at (phone clock), offline
  lat, lon, accuracy_m, readings_count, readings_seconds
  readings        every raw sample [{lat, lon, acc, t}], kept whole (rule 2)
  fix_source      sampled | marked_from_here
  gps_lock?, satellites?, connection (cellular | wifi | none | unknown)
  same_as_structure_id?   the volunteer's answer on "Is this the same one?"
  condition       good | fair | poor | unsafe,   problems (tag keys from the type's card)
  repair          leave | minor | major | replace | remove
  timing          now | this_season | next_year | five_years
  size_bucket?, size_measured?, size_unit?, size_method? (bucket | tape)   rule 3
  counts?         sleeps, sites, cars, risers, rings: per type
  railings?, notes (NoteText, 4,000 chars), photo_count (default 0)
  review_state    submitted | accepted | returned | merged | not_ours
  reviewed_by?, reviewed_at?, review_note?
  report_id? → reports    the Report a Problem an Unsafe filed
  mile?, off_line_ft?     server,   created_at

inventory_passes             one walk of one stretch by one volunteer
  id, club_id, volunteer_id, trail_id, started_at, finished_at?
  from_lat, from_lon, to_lat, to_lon     where the walk really started and ended
  ended_early, state (in_progress | completed | abandoned), note?, created_at

inventory_claims             a heads-up that a volunteer means to walk a section on a day
  id, club_id, volunteer_id, section_id → org_sections, claimed_at
  walk_on (date), released_at?
  current = walk_on >= today and released_at is null; nothing expires a row, the query does

inventory_club_settings      one row per club
  club_id (PK), waiver_text, waiver_version
  claim_days_ahead (14), coverage_window_days (90), coverage_min_records (3), stale_days (365)
  publish_locations (default false), created_at, updated_at
```

`inventory_claims` is modelled on `ridge_runner_commitments` (`backend/app/models/ridge_runner.py`):
a window, a cap, and no column for what was expected. Photos have no table: the R2 object
is derived and disposable, and the observation row is authoritative.

**Left out on purpose.** The Inventory screen draws a Local Chair's note and a comment thread
on a record. Neither has a table here; `inventory_comments` is the obvious sixth, kept out
so the first migration holds only what a pilot needs.

---

## Permissions

| Action | Who | Mechanism |
| --- | --- | --- |
| Enrol, sign the waiver, do the training | Any signed-in person | `get_current_user` |
| See priority areas, claim a day, start a walk, submit observations and photos | Enrolled at that club, waiver signed and training done | New `require_inventory_volunteer(slug)` |
| See the queue; accept, send back, merge, not ours; assign a code; edit a structure | The Local Chair, meaning any approved club admin (decided 2026-11-04), for everything; a section supervisor for observations in sections under their role | New `require_inventory_reviewer(slug)` on `resolve_access`; the section narrowing is the one new piece |
| See the inventory list and map | Admin, supervisor, any enrolled volunteer, any maintainer with an assignment on that trail | `OrgAccess` flags, read-only |
| See a record's photos | The volunteer who took them, the club's admins, and a supervisor for a structure in a section under their role | The photo link answers everybody else with the same 404 a missing photo gets |
| Export CSV and GeoJSON, change settings, publish locations | Club admin | `require_org_admin`, as `download_entries` in `backend/app/routers/trail_challenges.py` |
| Read a published location without an account | Anyone | Only when `publish_locations` is on, and only `kind`, `lat`, `lon`, `code`: never condition, notes or photos |

`resolve_access` (`backend/app/core/org_access.py`) already answers `is_admin`,
`is_supervisor` and `is_volunteer`. The survey's volunteer is new to it: anyone with an
enrollment row, who need not hold a maintainer assignment. Every row above becomes a row in
`backend/tests/test_org_permission_matrix.py`, over its `EVERYBODY` plus one new person who
holds an enrollment and no assignment.

**A supervisor's sections count only agreed assignments, on both sides of the reporting
line.** An assignment grants nothing until it is confirmed or was never a proposal -
`resolve_access`'s rule for the roles a person holds, from #1635 — The organization
console's new endpoints trust self-registered orgs with maintainer powers, seats and mail.
The survey applies it to the crews under a supervisor too, so proposing somebody onto a
section does not put that section's records in the supervisor's reach before an admin
confirms it.

**Photos are narrower than the inventory list, for now.** The list and map rows above let
enrolled volunteers and assigned maintainers read the inventory; a record's photos reach
only the people who took them or review them. Whether the list's readers see photos too is
a question for #2007 — Inventory and history: worst first, a history per structure, the
Chair's note, CSV and GeoJSON. Until it is answered they do not, which is the narrower
answer to start from for photographs of a club's working data.

**A waiver version names one text, for good, once anybody has signed it.** A signature
records the version, not the words, so the same version with different words is refused,
and so is a signed version coming back after it was replaced or cleared: the settings row
keeps only the current text, so there is nothing to compare a returning version against.
A changed waiver takes a new version.

**Decided 2026-11-04, by the maintainer by poll: the Local Chair is any approved club
admin** (`is_admin`: an approved seat in `club_admins`, codeowners included). It is the
check that already gates exports and settings, so the reviewer dependency needs no new
column. The consequence, chosen with it: when mail is on, the Unsafe email goes to every
approved admin at the club. The alternative offered was the holders of one role the club
picks in the survey's settings.

---

## Packaging: a second front door

The maintainer asked for a standalone app with its own landing page and its own address,
linked to a club's trails, still part of OurHike. The shape that keeps it part of OurHike is
**a second front door on the same house**:

- **Same client source.** `client/survey.html` opens `client/src/survey/main.tsx`, built by a
  second Vite config that shares `src/`, sets its base to `/survey/`, and runs its own PWA
  manifest and service worker with scope `/survey/`. It needs a second config, not just a
  second entry like `viewer.html` and `spotify-callback.html` in `client/vite.config.ts`,
  because the PWA plugin makes one service worker per config, and a second scope needs a
  second worker.
- **Same origin, first.** The deploy that already puts the site at `/` and the app at
  `/app/` puts the survey at `/survey/`. No origin is added, so the origin allow-list, the
  Supabase redirect list and the R2 CORS policy do not change. The survey reads the main
  app's downloaded map packs and signs in with the same redirect.
- **Same backend, same bucket, same code.** The survey imports from `client/src/lib/`
  (the API client, auth, the outbox on its own store, photo preparation, geolocation, the
  design-system tokens) and copies nothing.
- **A club's trails.** `/survey/?org=<slug>` opens on that club, its trails, its sections as
  areas, and its waiver. A landing page at `site/src/pages/for-orgs/survey.astro` explains
  the programme to a club and links in.
- **Its own address, when a club asks.** `survey.ourhike.org` as its own Cloudflare Pages
  project is a deploy step, not a code change: a new origin, so the three lists change
  together, and the survey there no longer shares the main app's map packs. After the
  pilot, unless the maintainer decides otherwise (open questions).
- **What it must not become: a fork.** One field guide, one outbox module, one photo
  pipeline, one sign-in.

---

## The numbers this design rests on

Every threshold the design introduces, with its grade. Constants already in the code are
cited in place above and not repeated.

| Number | Where it acts | Grade | What would settle it |
| --- | --- | --- | --- |
| Fewer than **3** records in **90** days marks an area as needing a walk | Coverage, priority areas | `@unvalidated`: the design's pick, in `SPEC.md`'s decisions | A pilot season: whether the areas it colours are the ones the Local Chair would have named as thin |
| No record in **365** days is highlighted | Coverage | `@unvalidated` | The same season, and how many areas sit in that band on day one |
| A claim can be up to **14** days ahead | Claims, `inventory_club_settings` | `@unvalidated`: the maintainer's own figure from design review | Whether claims made more than a week ahead are walked on the day claimed |
| Sampling stops after **40 s**, or at **3** consecutive readings within **20 m** | Location screen | `@unvalidated` | A real phone under canopy: the time at which more readings stop moving the median |
| `gps_lock` is true at accuracy **≤ 20 m** for **3** consecutive readings | Location chips, the row | `@unvalidated` | The accuracy at which readings stop scattering on a real phone under canopy |
| The server's mile agrees with the client's to **0.05 mi** | `trail_axis.py` tests | `@unvalidated` | One real section's line (conflict 1) |
| A record more than **3 mi** from every drawn section gets no mile | `trail_axis.MAX_OFF_LINE_FT` | Reasoned: the client's `MAX_OFF_TRAIL_MILES`, so the server and the phone refuse the same points | None needed while the client's gate stands; it moves when that one does |
| The outbox banner shows when anything has waited **more than a day** | Waiting to upload | Reasoned: the screen's own copy, "waits a day" | None needed; it is a wording decision, not a safety threshold |
| **79** plates; **3** finished (Sign, Blaze, Steps) | Field cards | Measured: counted in `plates_manifest.json` and `plates/` on 2026-11-04 | |
| **311** licensed-candidate rows across the 79 plates | The plate fetch | Measured: counted in `plates_manifest.json` on 2026-11-04 | The fetch re-checks every licence at the source before anything is used |
| **13** plates no licensed collection covers well | `CLUB_SHOT_LIST.md` | As the handoff states it; not re-derived here | The club's photos arriving |

**Not specified at all: when the Location screen says "Good, you can save".** The artboard
draws the good state ("Within 14 ft ✓ Good, you can save") and nothing else; no threshold in
the handoff decides when a fix is good enough, or what the screen says when it is not. This
sits on a safety path (a structure in the wrong place is a crew sent to the wrong place) and
is an open question below.

---

## Where this touches a hiker's safety

The inventory is club-private, so most of it never reaches a hiker. Three paths do, and each
is held to the standard in `CLAUDE.md`'s "Four ways this app can hurt somebody".

- **Unsafe becomes a Report a Problem.** That is how a hiker ever hears about an unsafe
  bridge, through the existing closure and moderation path. The handoff files it as
  `shelter_repair` at severity `serious` for every structure type. `ReportType` has no
  bridge, puncheon or steps type (`backend/app/models/report.py`), so an unsafe bridge would
  reach the moderation queue labelled as a shelter repair. Nobody has checked what a hiker
  or a moderator reads from that label. Open question below.
- **A published location is only a location.** With `publish_locations` on, a hiker could
  see that a bridge exists at a point. Never its condition: a published "bridge here" with
  no word on whether it stands is the right amount of claim for a club-private record.
- **The field cards teach what Unsafe means.** Every line on a card comes from ATC or
  NYNJTC with its source named, and a plate shows exactly the problem its caption names or
  shows the "photo wanted" tile. A photograph of a sound bridge is never used for
  "abutment scoured" because it was the only bridge found.

---

## What this deliberately isn't

- **Not a merge.** No screen asks anybody to decide which of two observations is true. Merge
  in the review queue joins two *structures* that turned out to be one thing; it never
  edits an observation.
- **Not a presumed place.** No basemap and no trail line on the Location screen; no snapping
  on the phone; no pin to drag.
- **Not a measurement dressed up.** An estimate is labelled an estimate on every screen and
  in every export.
- **Not a notification.** No push, no badge, no "you haven't surveyed lately".
- **Not a score.** Coverage is the trail's need; there is no per-volunteer count, streak or
  leaderboard, the guardrail [VOLUNTEERING.md](VOLUNTEERING.md) states with its boundary
  (comparison and pressure, not memory).
- **Not a public condition map.** Condition, notes and photos stay with the club.
- **Not a fork of the app.** One codebase, a second front door.
- **Not drawn art.** A plate is a credited photograph or an honest "photo wanted" tile.

---

## Open questions

The first two blocked any code and were answered by the maintainer on 2026-11-04.
The rest are still the maintainer's decisions, written here as questions, not answers.

1. ~~**The area unit.**~~ **Decided 2026-11-04, by poll: sections are the areas for v1**
   (conflict 2, with the parking-to-parking measurement it was decided against).
2. ~~**Who the Local Chair is in code.**~~ **Decided 2026-11-04, by poll: any approved club
   admin** (Permissions).
3. **The waiver as a legal record.** Whether a typed name against a recorded version is
   enough, or the app links to the club's own form. Counsel's answer, not this repository's.
4. **Notifications.** Whether one email to the Chair on Unsafe and an on-open banner fit the
   privacy policy's "no notifications at all" (conflict 3), or the policy and
   `noNotifications.test.ts` have to change for the survey alone.
5. **Publication.** Whether the per-club switch to publish locations is wanted in v1 or
   later. Club-private is the default either way.
6. **The plates.** The licensed candidates are fetched, each approved by eye against its
   caption, then treated; what no collection has comes from the club's phones. The
   maintainer sees the contact sheets with approvals marked before anything is treated.
7. **Packaging order.** Same-origin `/survey/` first and a subdomain after the pilot, or
   the reverse if the club wants its own address on day one.
8. **When the Location screen's verdict says "Good, you can save".** No threshold exists
   (see the numbers above), and the not-good state is not drawn.
9. **The report type an Unsafe files.** Whether `shelter_repair` is acceptable for a bridge,
   puncheon or steps, or Report a Problem needs a structure type first. A safety path.
10. **Where this sits on the roadmap**, and which club pilots it.
11. **Which records count toward coverage.** The handoff says "records" without saying
    whether a submitted, not-yet-reviewed observation counts. Counting only accepted ones
    makes a slow review queue paint walked areas as needing a walk; counting everything
    lets a record the Chair later marks "not ours" hide a gap.
