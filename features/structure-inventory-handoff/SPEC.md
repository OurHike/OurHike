# OurHike structure inventory — build spec

Written for whoever picks this up. It records the decisions behind the screens, not just their
appearance, and it says where each one lands in the repository as it stood at `main` on
2026-11-04. Every claim about the codebase below was checked against a file in it; a claim with
no file after it is a design decision, and says so.

Design references: the **Structure Inventory Wireframes** canvas (36 artboards) and the
**Structure Inventory Walkthrough** page (every screen in the order a volunteer meets it). The
brief that argues the product is **OurHike Structure Inventory — Design Brief**; the card content
with its sources is **Structure Field Guide**. The maintainer holds all four.

---

## Read these six first — every screen assumes them

1. **Nothing is overwritten.** A structure is one row; every visit to it is a new observation
   row, append-only, with the volunteer, the time and the review state. "Current condition" is
   the latest accepted observation, a query and not a column. Two volunteers logging the same
   bridge on the same day is two rows and free data, never a conflict to adjudicate. This is
   `features/FIELD_NOTES.md`'s layering rule applied to a club's own structures.

2. **The phone records what it knows and nothing it assumes.** The Location screen plots every
   GPS reading where it landed, on a plain grid with a scale bar, and saves the middle of them
   with the accuracy and the count. No trail line, no presumed place, no pin to drag. Distance
   to the centerline and the mile are computed afterwards, on the server, and stored beside
   the raw point, never instead of it (decision "Snap to trail", D).

3. **A guess is saved as a guess.** Size is a bucket ("10 to 25 ft") unless the volunteer
   opened the tape; the record carries the method, and nothing a volunteer estimated is ever
   rendered in the voice of a measurement. Same rule as `CLAUDE.md`'s "never let a display
   outrun its source".

4. **Works with no signal, uploads on any signal.** Every field screen is usable offline; the
   record goes into the outbox the moment it is saved; words upload before photos; cellular
   upload is on by default with a toggle; the app tells the volunteer what is still waiting.
   No timer polls the radio (`client/src/lib/outboxSync.ts`'s own rule), so "whenever service
   is available" is the `online` event plus a flush on app resume, which is new.

5. **The club's own chain reviews, not a global moderator.** The Local Chair accepts; a section
   supervisor accepts for the sections their role covers; maintainers and volunteers on that
   stretch see the record and can comment. Unsafe is never a global alert: it is a flag the
   Chair sees first in the queue and, when mail is enabled, an email.

6. **No streaks, no badges, no notifications** (`features/VOLUNTEERING.md` line 252, and
   `client/src/test/noNotifications.test.ts`, which fails the build if the Notification or
   Push API appears in shipped code). A claim is a heads-up that clears itself. Coverage is
   shown as the trail's need, never as a volunteer's score. Reminders are in-app, on open.

---

## Decisions made

The brief's decisions table is the record; these are the ones that shape code. Dates mark the
ones changed during review.

| Decision | Chosen | Why |
| --- | --- | --- |
| Where it lives | **A second front door, same client, same backend** (2026-11-04): `client/survey.html`, built with `VITE_BASE_PATH=/survey/`, its own manifest and install icon, served beside `/app/` on the same origin; a subdomain is a deploy step, not a code change (see Packaging) | One origin shares the map packs and auth; the volunteer still gets an icon that is the survey and nothing else |
| Form shape | One question per screen, a progress line, "Save for later" on every step | A thumb in a cold hand |
| Location capture | Timed sampling shown as a plain readings map; the median saved with accuracy and count (D) | A presumed place on screen tempts people to accept a wrong fix |
| Snap to trail | Never on the phone; server computes distance and mile afterwards (D) | A shelter 300 ft off the trail must not be drawn on it |
| Photos | Two shots that always work plus one or two suggested per type; no people in frame | A fixed list overfits the bridge |
| Dimensions | Buckets as the question, optional, saved as an estimate; a tape one link away; counts stay one tap (D) | People won't measure; a bucket still tells a crew leader what to bring |
| Condition | Good, Fair, Poor, Unsafe, with the definition on screen and the type's reminder card above it | Four words everyone already uses |
| Repair | Leave it, Minor, Major, Replace, Take it out; a timing; free text. "The Local Chair decides what happens and when" | The volunteer suggests, the crew leader prices |
| Where to walk | No fixed stretches: computed priority areas (fewer than 3 records in 3 months; none in a year highlighted), open to all, with a day-bound claim up to 14 days ahead that clears itself (C) | Effort lands where the data is thinnest; overlap is free data |
| Who reviews | The club's chain (C) | It is how the club already works, and `org_access` already expresses it |
| Hazards | One tap also files a Report a Problem (`shelter_repair`, severity serious) | The closure path and moderation already exist |
| Identity | Readable code (`AT-NY-BR-014`) plus a field for any existing id | The guidebook, ATC's lists and NPS each have their own |
| Publication | Club-private, with a per-club switch to publish locations | Condition notes are the club's working data |
| Offline and upload | Outbox; upload on any signal; cellular toggle on by default (C) | A record that sits on a phone helps nobody |
| Training | In-app field cards with a "call it" check; a field day per club if the club wants one | Starts anyone tonight |
| Field-card art | **Photographs, one per issue, in one house treatment** (square, one ink colour on paper, a soft vignette; `tools/duotone.py`), swiped one at a time; a plain "photo wanted" tile where none exists yet, never a drawing standing in (2026-11-04) | A volunteer must recognise the thing on the trail; a photo of a rotten stringer beats any drawing of one, and 79 phone photos read as one set once treated |
| Whitelabel | Club name from `clubs`; mark, accent and waiver text from a branding block that does not exist yet | A general OurHike need the inventory needs first — its own change |

---

## Where this lives

| Surface | Belongs in | Notes |
| --- | --- | --- |
| The survey app (phone screens 1a–2k, 3a) | `client/src/survey/` — `main.tsx`, `SurveyApp.tsx`, `screens/*.tsx` | A second Vite entry (`client/survey.html`), the pattern `viewer.html` and `spotify-callback.html` already use in `client/vite.config.ts` `build.rollupOptions.input`. See Packaging for why it is a second *config* rather than only a second entry |
| Field cards and plates | `client/src/survey/fieldGuide.ts` (content, from `fieldGuide.json`), `client/src/design-system/assets/plates/<type>/<n>.jpg` + `plates.ts` (art and credits, generated by `tools/fetch_plates.py` from `plates_manifest.json`) | Content is the Field Guide doc's twelve cards, ATC/NYNJTC only, each with its sources; every plate passed the `heroPhotos.ts` licence gate and a human eye against its caption, and carries its credit |
| Review queue, review map, coverage, inventory (web 3b–3e) | `client/src/org/screens/Inventory*.tsx`, reached as `/org/:slug/inventory?page=queue|map|coverage|list` | Add `inventory` to `ORG_ADDRESS` in `client/src/lib/orgEntry.ts` and a route in `client/src/lib/orgRoute.ts` `parseOrgRoute()`; same `?page=` grammar as `/org/:slug/volunteers` |
| Backend | `backend/app/models/inventory.py`, `backend/app/schemas/inventory.py`, `backend/app/routers/inventory.py`, one Alembic revision | One router with `APIRouter(tags=["inventory"])` and full paths under `/clubs/{slug}/inventory/…`, registered in `backend/app/main.py` beside the other org routers |
| Mile and distance to the line | `backend/app/core/trail_axis.py` | New. Pure Python point-to-polyline on `org_sections.geometry` (a GeoJSON LineString as text, `backend/app/models/org_registry.py:105`), falling back to the published `trails.geojson` — no PostGIS, by the repo's standing choice |
| Exports | In the inventory router: `GET /clubs/{slug}/inventory/export.csv` and `/export.geojson` | CSV copies `trail_challenges.py:575` `download_entries` (BOM, `QUOTE_ALL`, `spreadsheet_safe`); GeoJSON is new to the backend |
| Landing page | `site/src/pages/for-orgs/survey.astro`, linking to `/survey/?org=<slug>` | The `for-orgs/` pages are the pattern (`Base.astro`, `OrgNav.astro`, `Contours.astro`) |
| Design doc | `features/STRUCTURE_INVENTORY.md`, the one home | This folder is the handoff as given and does not get edited to match what was built — the same rule as `features/org-onboarding-handoff/README.md` |

---

## Conflicts with the existing codebase

Six, in the order they bite. Two are blocking until the maintainer answers; the rest have a
resolution written here.

### 1. The backend holds no centerline geometry, and decision D asks it to compute a mile

`reports.mile` is "a client claim; this backend holds no centerline geometry"
(`backend/app/models/report.py`). The design moved snapping off the phone precisely so the
phone never presumes a place. **Resolution:** `backend/app/core/trail_axis.py` projects a
point onto `org_sections.geometry` (the club's own registry line, with `start_mile` and
`end_mile` on the row) and returns `{section_id, mile, off_line_ft}`; where a club has no
section geometry it reads the pipeline's `trails.geojson` + `trail_miles.json` from R2
(`VITE_DATA_BASE_URL`'s bucket, release-pinned like the client) and caches them in process.
Pure Python haversine and segment projection, under 100 lines, with a fixture test against
three points whose miles `client/src/lib/trailPosition.ts` `locateOnTrail` already answers.
The client never sends a mile; `mile` and `off_line_ft` are nullable server columns, filled
on accept. Not blocking.

### 2. Priority areas need an "area" and the backend has only sections

The brief computes areas "parking lot to parking lot" from the records. The backend has
`org_sections` (the club's own division of each trail, `start_anchor`/`end_anchor` as text)
and no parking POIs — those live in the pipeline's published POI files. **Resolution for v1:
the area is the `org_section`.** The coverage rule (fewer than 3 observations in 90 days;
none in 365 days highlighted) runs per section over `inventory_observations.section_id`,
which conflict 1 fills. Parking-to-parking areas are a later refinement once the backend
reads POIs. **Blocking question for the maintainer:** do NYNJTC's registered sections run
road to road? If they do, this is the same thing with a better name; if they do not, the
coverage map will colour maintainer sections rather than walks, and the pilot should know.
`@unvalidated` either way until one club's sections are looked at.

### 3. "Alerts the Local Chair" and "Remind me if anything waits a day" against no-notifications

`noNotifications.test.ts` enforces the privacy policy's "OurHike sends no notifications at
all", and `features/VOLUNTEERING.md` says "No notification of any kind". The Condition
screen says Unsafe "alerts the Local Chair when it uploads"; the Outbox screen offers a
daily reminder. **Resolution:** neither is a push. Unsafe makes the record first in the
queue and, when `settings.mail_enabled` is on, sends one email through
`backend/app/core/mail.py` with a new `MailPurpose.inventory_unsafe` (SES, suppression list
and `List-Unsubscribe` already handled there). The reminder is a banner the survey app shows
on open when anything has waited more than 24 hours, plus a flush on app resume
(`visibilitychange` → `syncOutbox()`, which nothing does today — the only visibility
listeners belong to `useConditions`, `useAppUpdate`, `useUsageMeasurement` and
`useAvailableBytes`). The copy on both screens changes accordingly: "Alerts the Local Chair
when it uploads" stays true (it is an email); "Remind me if anything waits a day" becomes
"Show me on open if anything waits a day". Not blocking.

### 4. GPS lock, satellites, cell and Wi-Fi are not all observable on the web

The Location screen shows "GPS locked · 9 satellites · Cell · No Wi-Fi" and records them.
The web Geolocation API gives position and accuracy only (`client/src/lib/useGeolocation.ts`
`GeolocationFix = { at, accuracyFeet, accuracyM, fixedAt }`); the installed
`@capacitor-community/background-geolocation` gives accuracy, not a satellite count; there is
no other Capacitor plugin (`client/package.json`: core, android, ios, the one community
plugin). `navigator.connection.type` answers cellular vs Wi-Fi on Android Chrome and is
absent on iOS. **Resolution:** record what the platform gives and label the rest unknown:
`gps_lock` is derived (`accuracy_m <= 20` for three consecutive readings = locked; the
threshold is `@unvalidated`, what would settle it is the accuracy at which readings stop
scattering on a real phone under canopy), `satellites` is null on web and stays null until a
native plugin exists, `connection` is `cellular | wifi | none | unknown`. The chips render
only what is known; the record stores the nulls. Not blocking.

### 5. Two apps on one origin share one IndexedDB, including the outbox

`client/src/lib/outbox.ts` keeps one key, `ourhike:outbox`, in idb-keyval's default store.
If the survey app used it on the same origin, the main app's `flushOutbox` would meet cargo
it does not know. **Resolution:** the survey app's outbox is the same module instantiated on
its own store (`createStore('ourhike-survey', 'outbox')`), so each app flushes only its own
queue; the cargo shape (`inventoryObservation?: InventoryObservationDraft` beside
`photos?: Blob[]`) follows the optional-field convention so nothing stored ever needs a
migration. The map packs in `archiveStore` are shared on purpose — that is the point of the
same origin. Not blocking.

### 6. Production has no SPA fallback, so the survey app's addresses are query strings

`ourhike.org` is GitHub Pages with no `404.html` or `_redirects`; `/app/my/tread` answered
404 in production (measured 2026-09-17, recorded in `pr-preview.yml` and
`features/ORG_ONBOARDING.md`). Previews and UA on Cloudflare Pages have the fallback.
**Resolution:** the survey app lives at `/survey/` and addresses a club as
`/survey/?org=<slug>`, the `?org=` convention `/my/tread` already uses; screens within the
app are app state, as everywhere else in `client/src/App.tsx` (no router library, by
design). Not blocking; the fallback is a known gap with its own issue.

### Also checked, and clear

- **Any new table needs RLS in its migration**: `RLS_TABLES` + `rls_statements()` copied from
  `b3d1c7a94e02`, and `test_every_model_table_is_locked_by_some_migration` will fail the
  build otherwise. Five tables below.
- **Enums are VARCHAR + CHECK**: `Enum(X, native_enum=False, length=N)`
  (`test_column_conventions.py`). Timestamps naive UTC from `utc_now()`.
- **OpenAPI compatibility**: everything here is additive (new paths, no new required fields
  on existing request schemas), so `backend/openapi_baselines/` is untouched
  (`test_openapi_compat.py`'s rules).
- **Photos**: no photos table (`report.py:282`'s argument holds), `photo_count` on the
  observation, key `inventory/{observation_id}/{index}.jpg` from a pure function in
  `backend/app/core/photos.py` beside `photo_key`, `poi_photo_key` and `note_photo_key`;
  JPEG magic check, 2 MiB cap through `read_capped_body`, 300 s presign, private R2.
- **Client photo prep**: `client/src/lib/reportPhoto.ts` `preparePhoto(file, 1600)` already
  strips EXIF by re-encoding; reuse it unchanged.
- **Review states**: the report pattern (`submitted → verified | dismissed | resolved`)
  becomes `submitted → accepted | returned | merged | not_ours`, same audit columns
  (`*_by`, `*_at`).
- **Permissions**: `backend/app/core/org_access.py` `resolve_access` already gives
  `is_admin`, `is_supervisor` (a non-retired role at the club reports to one the person
  holds) and `is_volunteer` (a live assignment). The Local Chair is `is_admin`; a section
  supervisor is `is_supervisor` narrowed to the sections of the roles under theirs; the
  volunteer is anyone with a row in `inventory_enrollments` for the club, which is new —
  the survey's volunteers are not necessarily maintainers with assignments.

---

## Data model

Five tables, prefix `inventory_`. `String` ids from `uuid4`, naive UTC `DateTime`, every
`Enum` with `native_enum=False`. Column lists are the whole row.

**`inventory_enrollments`** — a volunteer's standing in the programme at one club.
`id`, `club_id` FK `clubs`, `person_id` FK `profiles`, `waiver_version` String,
`waiver_signed_at` DateTime, `typed_name` Text, `training_completed_at` nullable,
`field_day_at` nullable, `created_at`. Unique on (`club_id`, `person_id`). The waiver text
itself is club settings; the row records which version was signed and the typed name, which
is decision "Waiver" C (mirror the club's text, export to the club; counsel decides whether
this is the legal record).

**`inventory_structures`** — one physical thing on the trail.
`id`, `club_id`, `trail_id` FK `org_trails` nullable, `section_id` FK `org_sections`
nullable, `kind` Enum(`bridge puncheon shelter privy campsite water blaze sign kiosk parking
steps other`, length=10), `subkind` String nullable, `code` String (readable, unique per
club, assigned on first accept: `<trail>-<state>-<kind>-<n>`), `external_ids` JSON nullable
(`{"atc": "...", "nps": "...", "guidebook": "..."}`), `lat`, `lon` Float (from the latest
accepted observation), `mile` Float nullable and `off_line_ft` Float nullable (server, see
conflict 1), `poi_id` String nullable (a published POI id when one matches),
`status` Enum(`active removed merged`, length=8), `merged_into_id` FK self nullable,
`published` Boolean default False (decision "Publication" C), `created_at`, `created_by`.

**`inventory_observations`** — one visit to one structure. Append-only.
`id`, `structure_id` FK, `club_id`, `pass_id` FK `inventory_passes` nullable, `volunteer_id`
FK `profiles`, `captured_at` DateTime (phone clock), `offline` Boolean,
`lat`, `lon`, `accuracy_m` Float, `readings_count` Integer, `readings_seconds` Integer,
`readings` JSON (the raw samples: `[{lat, lon, acc, t}]`, kept because rule 2 says the phone
records what it knows), `fix_source` Enum(`sampled marked_from_here`, length=16),
`gps_lock` Boolean nullable, `satellites` Integer nullable, `connection`
Enum(`cellular wifi none unknown`, length=8), `same_as_structure_id` FK nullable (the
volunteer said "same one" on screen 2i), `condition` Enum(`good fair poor unsafe`,
length=6), `problems` JSON (tag keys from the type's card), `repair` Enum(`leave minor major
replace remove`, length=7), `timing` Enum(`now this_season next_year five_years`,
length=11), `size_bucket` String nullable, `size_measured` Float nullable, `size_unit`
String nullable, `size_method` Enum(`bucket tape`, length=5) nullable, `counts` JSON
nullable (sleeps, sites, cars, risers, rings — per type), `railings` Boolean nullable,
`notes` Text (`NoteText` cap, 4,000), `photo_count` Integer default 0,
`review_state` Enum(`submitted accepted returned merged not_ours`, length=9),
`reviewed_by`, `reviewed_at`, `review_note` Text, `report_id` FK `reports` nullable (the
Report a Problem filed from an Unsafe), `mile`, `off_line_ft` nullable (server),
`created_at`. The client id is the row id (idempotent upload, the outbox's own rule).

**`inventory_passes`** — one walk of one stretch by one volunteer.
`id`, `club_id`, `volunteer_id`, `trail_id`, `started_at`, `finished_at` nullable,
`from_lat`, `from_lon`, `to_lat`, `to_lon` (where the walk actually started and ended; the
Finish screen lets the volunteer place the end when they stopped early), `ended_early`
Boolean, `state` Enum(`in_progress completed abandoned`, length=11), `note` Text nullable,
`created_at`. The `SurveyPass` the invasive-species design sketched, built here first.

**`inventory_claims`** — a heads-up that a volunteer means to walk a section on a day.
`id`, `club_id`, `volunteer_id`, `section_id` FK `org_sections`, `claimed_at`, `walk_on`
Date (at most `MAX_CLAIM_DAYS_AHEAD = 14` ahead — `@unvalidated`, the figure is the
maintainer's own from review and what would settle it is whether claims past a week ever
get walked), `released_at` nullable. "Current" is `walk_on >= today and released_at is
null`; nothing expires a row, the query does. Modelled on `ridge_runner_commitments`: a
window, a cap, and no column for what was expected.

**Club settings for the module** — one row per club, `inventory_club_settings`:
`club_id` PK FK, `waiver_text` Text, `waiver_version` String, `claim_days_ahead` Integer
default 14, `coverage_window_days` 90, `coverage_min_records` 3, `stale_days` 365,
`publish_locations` Boolean default False, `created_at`, `updated_at`. Mark, accent colour
and units wait for the general branding block (decision "Whitelabel").

Photos have no table. The R2 object is derived and disposable; the observation row is
authoritative (`photos.py`'s own sentence).

---

## Permissions

| Action | Who | Mechanism |
| --- | --- | --- |
| Enrol, sign the waiver, do the training | Any signed-in person | `POST /clubs/{slug}/inventory/enrollments` with `get_current_user` |
| See priority areas, claim a day, start a pass, submit observations and photos | Enrolled at that club | New dependency `require_inventory_volunteer(slug)`: an `inventory_enrollments` row with `waiver_signed_at` and `training_completed_at` set |
| See the queue, accept / return / merge / not-ours, assign a code, edit a structure | Local Chair (`is_admin`) for everything; section supervisor (`is_supervisor`) for observations whose `section_id` is a section of a role that reports to theirs | `require_inventory_reviewer(slug)` built on `resolve_access`; the section narrowing is the one new piece |
| See the inventory list and map, comment on a record | Admin, supervisor, any enrolled volunteer or maintainer with an assignment on that trail | `OrgAccess` flags, read-only |
| Export CSV / GeoJSON, change settings, publish locations | `is_admin` | `require_org_admin`, the `download_entries` precedent |
| Read a published location without an account | Anyone | Only when `inventory_club_settings.publish_locations` is true, and only `kind`, `lat`, `lon`, `code` — never condition, notes or photos |

Every row of this table becomes a row in `backend/tests/test_org_permission_matrix.py`,
parametrised over `EVERYBODY` with `_expected(allowed, who)`, plus one more person,
`ENROLLED_VOLUNTEER`, who holds an enrollment and no assignment.

---

## Endpoints implied

Unversioned, under `/clubs/{slug}/inventory/`, additive to the OpenAPI document.

- `GET settings` · `PUT settings` (admin)
- `POST enrollments` · `GET enrollments/me` · `PATCH enrollments/me` (training done)
- `GET areas?trail=` — sections of the trail with `records_90d`, `last_record_at`,
  `claims` (walk_on, first name only) and a `need` of `none_in_a_year | under_3_in_90 |
  covered`
- `POST claims` · `DELETE claims/{id}`
- `POST passes` · `PATCH passes/{id}` (finish, with where)
- `POST observations` — idempotent on `id`; creates the structure when `structure_id` is a
  client id not yet seen; answers `{observation_id, structure_id, mile, off_line_ft}` once
  conflict 1's computation has run
- `PUT observations/{id}/photos/{index}` · `GET observations/{id}/photos/{index}/link`
- `GET queue?state=&section=` · `POST observations/{id}/accept | return | merge | not-ours`
- `GET structures?trail=&kind=` · `GET structures/{id}` (with its observations)
  · `PATCH structures/{id}` (code, external ids, status)
- `GET export.csv` · `GET export.geojson`
- `GET /survey/clubs/{slug}` — public, the landing page's data: name, trails, whether
  enrolment is open

No `/v1` prefix, no cookies: `Authorization: Bearer` from `client/src/lib/api.ts`
`accessToken()`.

---

## Packaging: a second front door

**What the maintainer asked:** a standalone PWA with its own landing page and subdomain,
linked to a club's trails, still part of OurHike. **Yes, and the shape that keeps it part of
OurHike is "a second front door on the same house":**

- **Same client source.** `client/survey.html` → `client/src/survey/main.tsx`, built by a
  second Vite config (`client/vite.survey.config.ts`) that shares `src/`, sets
  `base: '/survey/'`, and runs its own `VitePWA` with manifest `id`, `scope` and `start_url`
  `/survey/`, name "Trail structure survey", short name the club's (when branding exists),
  `display: 'standalone'`, its own icons. Two configs rather than one with two entries
  because `vite-plugin-pwa` generates one service worker per config with one
  `NavigationRoute(createHandlerBoundToURL("index.html"))`; a second scope needs a second
  worker. Output `client/dist-survey`.
- **Same origin, first.** `pages.yml` already assembles `_site/` from `site/dist` at `/`
  and `client/dist` at `/app/`; it gains `client/dist-survey` at `/survey/`. Nothing in
  `.github/expected-origins.yml`, the Supabase redirect allow-list or the R2 CORS policy
  changes, because no origin is added (`LAUNCH_CHECKLIST.md` says those three move
  together whenever one is). The survey app reads the main app's downloaded map packs
  (same IndexedDB `archiveStore`) and signs in with the same `redirectUrl()`, which already
  derives from `BASE_URL`.
- **Same backend, same bucket, same outbox code.** `api.ts`, `supabase.ts`, `auth.ts`,
  `outbox.ts` (on its own store, conflict 5), `outboxSync.ts`, `reportPhoto.ts`,
  `useGeolocation.ts`, the design-system tokens and fonts. The survey app imports; it does
  not copy.
- **A club's trails.** `/survey/?org=<slug>` opens on that club, its trails from
  `org_trails`, its sections as areas, its waiver text; the landing page
  (`site/src/pages/for-orgs/survey.astro`) explains the programme and links in. A hiker
  with no `?org=` sees the clubs with enrolment open.
- **A subdomain, when a club asks.** `survey.ourhike.org` is a Cloudflare Pages project
  deployed by a `survey-host` job copying `pages.yml`'s existing `docs-host` job
  (`DOCS_PAGES_PROJECT`, `wrangler-action`), with `VITE_BASE_PATH=/`. It is a new origin,
  so the three lists change together, and the survey app on that origin no longer shares
  the main app's map packs — it downloads the club's own cells, which for one club is a
  handful. Per-club subdomains (`nynjtc.survey.ourhike.org`) are the same job with a
  wildcard, and `?org=` becomes a hostname lookup. Worth doing after the pilot, not before.
- **What it must not become:** a fork. One `fieldGuide.ts`, one outbox module, one photo
  pipeline, one auth. The survey app is `client/src/survey/` and a build config, and
  everything else it uses is a path under `client/src/lib/`.

---

## Before this goes to Claude Code

Seven things worth settling first, in order of how much code they move.

1. **The area unit** (conflict 2): sections as areas for v1, or wait for parking-to-parking?
2. **The review chain mapping**: is the Local Chair a club admin seat, or a named `org_role`
   whose holders should accept? The wireframes say "Local Chair" everywhere; `org_access`
   says `is_admin`. If it is a role, the reviewer dependency reads `org_roles.name`, which is
   free text today.
3. **The waiver as a legal record** (decision C): counsel's answer decides whether the typed
   name is enough or the app links to the club's own form.
4. **Notifications** (conflict 3): confirm email-to-Chair on Unsafe and in-app-only reminders
   are acceptable, or the no-notifications line in the privacy policy and
   `noNotifications.test.ts` have to change for the survey app alone.
5. **Publication**: the default is club-private; is the per-club switch wanted in v1 or later?
6. **The plates**: `plates_manifest.json` names licensed candidates from Wikimedia Commons,
   NPS and the Forest Service for most of the 79; the fetch runs where the network is open
   (Claude Code), and **every candidate is approved by eye against its caption before it is
   treated** — a photograph of a sound bridge is never used for "abutment scoured" because
   it was the only bridge found. What no collection has comes from the club's phones; the
   treat stage prints that list. Until then a card shows a "photo wanted" tile, never a
   drawing.
7. **Packaging order**: same-origin `/survey/` first, subdomain after the pilot — or the
   reverse, if the club wants its own address on day one.

---

## Known gaps

- **Maps in the wireframes are schematic.** The readings map on 2c is a plain grid and is
  built as drawn (no basemap, by design). Every other map (1d, 1g, 2a, 2k, 3c, 3e) is a
  projected sketch; production draws the club's registry lines. `MapView.tsx` has 70 props
  and one consumer (`MapScreen.tsx`), no generic marker prop and no small mount; the org
  console draws no map today. A `SmallMap` that takes a line and typed points is new, and
  the phone screens that show one (2a, 2k, 1g) can ship without it in the pilot.
- **Numbers are plausible, not real.** Section names, counts, dates and the volunteer's
  initials are invented for density; "Bear Mountain Bridge to Hemlock Springs" is a real
  place used as a sample, not a club's registry.
- **Reading averaging does not exist** anywhere in the client; `useGeolocation.ts` is a
  single `watchPosition`. `client/src/lib/locationSampling.ts` is new: collect readings for
  up to 40 s or until three consecutive readings are within 20 m, keep them all, save the
  median. The two numbers are `@unvalidated`; what settles them is a real phone under
  canopy.
- **The field cards' "Call it" step uses the same plates.** Screen 1c shows `[PHOTO: …]`;
  it draws from `plates.ts` once the plates exist, so there is one art set, not two.
- **Satellite count** (conflict 4) is null on every platform this build can reach.
- **No flow coverage yet.** Every new screen module needs an entry in
  `client/src/test/flowCoverage.ts` (`SCREEN_DIRS` gains `survey/screens`), a `planned`
  entry being a real one, and a `client/preview-shots/` recipe so `pr-preview.yml`
  photographs it.
- **The Local Chair's note on the Inventory screen** and the comment thread on a record are
  drawn but have no table above; a `inventory_comments` table (`observation_id`, `person_id`,
  `text`, `created_at`) is the obvious sixth and was left out to keep the first revision to
  what the pilot needs.
