# Structure inventory — the issues, in the order to land them

One home per item (`CONTRIBUTING.md`): these become GitHub issues, each linking to
`features/STRUCTURE_INVENTORY.md`; the design doc describes the intended state and this list
is retired once the issues exist. Titles are written to be read without opening them
(`CLAUDE.md`, "Name an issue, don't just number it"). Each carries what it rests on and what
finishes it. Phases land in order because each one's tests need the one before.

Suites in brackets are what `scripts/test.sh` will pick; a pull request that touches a
screen a volunteer can reach is not finished without a `client/preview-shots/` recipe and a
`flowCoverage.ts` entry, and every backend endpoint without its permission-matrix row.

---

## Phase 0 — Decisions the maintainer makes before code

Not issues. `SPEC.md` §"Before this goes to Claude Code" lists seven; the two that block
Phase 1 are the area unit (sections as areas for v1?) and the review-chain mapping (is the
Local Chair a club admin seat or a named role?). The rest can be answered while Phase 1 runs.

## Phase 1 — Backend: the tables, the router, the mile

1. **The structure inventory's five tables land in one revision, locked by RLS, with every
   enum as VARCHAR + CHECK** [backend]
   `backend/app/models/inventory.py`, `backend/app/schemas/inventory.py`, one Alembic
   revision copying `b3d1c7a94e02`'s `RLS_TABLES` + `rls_statements()`. Done when
   `test_migration_rls.py`, `test_migrations.py` (against Postgres), `test_migration_expand_contract.py`
   and `test_column_conventions.py` pass with the five tables in `Base.metadata`. Rests on
   `SPEC.md` §Data model.

2. **A club's enrolment, settings and waiver have endpoints, and an enrolled volunteer is a
   person `org_access` did not know about** [backend]
   `POST /clubs/{slug}/inventory/enrollments`, `GET|PATCH …/enrollments/me`,
   `GET|PUT …/inventory/settings`; `require_inventory_volunteer(slug)` and
   `require_inventory_reviewer(slug)` in `backend/app/core/inventory_access.py` built on
   `resolve_access`. Done when `test_org_permission_matrix.py` has a row per endpoint over
   `EVERYBODY` plus the new `ENROLLED_VOLUNTEER`. Carries Phase 0's answer on the Local
   Chair.

3. **An observation uploads once, idempotent on its id, creates its structure when the
   structure is new, and keeps every GPS reading it was given** [backend]
   `POST /clubs/{slug}/inventory/observations`; the `readings` JSON is stored whole;
   `review_state` starts at `submitted`; Unsafe sets nothing special on the row — the queue
   orders it. Done when a second POST with the same id answers the same row and changes
   nothing (the outbox's contract), and the OpenAPI compat test still passes with
   `backend/openapi_baselines/` untouched.

4. **Observation photos use the report pipeline with a key of their own and no table**
   [backend]
   `inventory_photo_key(observation_id, index)` → `inventory/{observation_id}/{index}.jpg`
   beside `photo_key` in `backend/app/core/photos.py`; `PUT …/observations/{id}/photos/{index}`
   through `read_capped_body`, JPEG magic, `MAX_REPORT_PHOTOS`; `GET …/photos/{index}/link`
   presigned 300 s. Done when the photo tests in `backend/tests/` run against the new key
   and `photo_count` is the only thing the row learns.

5. **The server computes an observation's mile and distance to the line from the club's own
   section geometry, and stores both beside the raw point** [backend]
   `backend/app/core/trail_axis.py`: point-to-polyline on `org_sections.geometry`
   (GeoJSON LineString text) interpolating `start_mile`…`end_mile`; fallback to the
   published `trails.geojson` + `trail_miles.json` from R2, cached in process; runs on
   accept and on a backfill command. Done when three fixture points agree with
   `client/src/lib/trailPosition.ts` `locateOnTrail` to within 0.05 mi (`@unvalidated`
   tolerance; what settles it is a real section's line). Resolves `SPEC.md` conflict 1.

6. **Priority areas are sections scored by the records in them, and a claim is a day a
   volunteer means to walk one** [backend]
   `GET …/inventory/areas?trail=` with `records_90d`, `last_record_at`, `need`, `claims`;
   `POST|DELETE …/inventory/claims` with `MAX_CLAIM_DAYS_AHEAD = 14` `@unvalidated`.
   Thresholds read from `inventory_club_settings`. Done when the three sample sections in
   the fixture come back `none_in_a_year`, `under_3_in_90`, `covered`. Carries Phase 0's
   answer on the area unit; resolves conflict 2 for v1.

7. **The club's chain reviews: accept, send back, merge, not ours, each with a note and an
   audit column, and a section supervisor sees only their sections** [backend]
   `GET …/inventory/queue`, `POST …/observations/{id}/accept|return|merge|not-ours`; merge
   sets `structure.status = merged` and `merged_into_id`; accept assigns the readable `code`
   on a structure's first accepted observation and runs issue 5. Done when the permission
   matrix proves the supervisor narrowing with a section that is not theirs answering 403.

8. **A survey pass records where a walk really started and ended, including when it ended
   early** [backend]
   `POST …/inventory/passes`, `PATCH …/passes/{id}` with `to_lat`, `to_lon`, `ended_early`.
   Small; the Finish screen depends on it.

9. **An Unsafe observation sends the Local Chair one email when mail is on, and nothing
   else** [backend]
   `MailPurpose.inventory_unsafe` in `backend/app/models/mail.py`, sent through
   `backend/app/core/mail.py` on upload, gated by `settings.mail_enabled` and the
   suppression list, with `List-Unsubscribe`. Done when `noNotifications.test.ts` still
   passes (it scans the client; this is backend) and the mail test asserts one send per
   Unsafe. Resolves conflict 3's first half.

10. **The inventory exports as CSV and GeoJSON for the club's GIS, admin-only, with every
    estimate labelled as one** [backend]
    `GET …/inventory/export.csv` on the `download_entries` pattern (BOM, `QUOTE_ALL`,
    `spreadsheet_safe`); `GET …/inventory/export.geojson` as a FeatureCollection of
    structures with the latest accepted observation's fields, `size_method` on every
    feature. Done when the permission matrix says admin only and a size recorded as a
    bucket never appears as a number.

## Phase 2 — The survey app

11. **A second front door: `client/survey.html` builds with its own base, manifest and
    service worker, and is served at `/survey/` beside `/app/`** [client, .github]
    `client/vite.survey.config.ts` (base `/survey/`, `VitePWA` with id/scope/start_url
    `/survey/`, output `client/dist-survey`), `client/src/survey/main.tsx`, a `survey`
    npm script, `pages.yml` and `pr-preview.yml` copying `dist-survey` to `_site/survey/`
    (previews get `/survey/*  /survey/index.html  200` in `_redirects`), `ua.yml` the same.
    Done when a preview URL opens `/survey/?org=central-park-throughikers` (the demo org),
    installs with its own icon, and `.github/tests/test_pages_publish.py` covers the new
    folder. No new origin, so `expected-origins.yml` is unchanged — say so in the PR.
    Resolves conflicts 5 and 6; `SPEC.md` §Packaging.

12. **The survey app's outbox is the same module on its own store, with an
    `inventoryObservation` cargo and photos as blobs, and it flushes on resume as well as
    online** [client]
    `createStore('ourhike-survey', 'outbox')`; `InventoryObservationDraft`;
    `visibilitychange` → `syncOutbox()` in the survey shell only. Done when the outbox tests
    cover the new cargo and a hidden→visible transition flushes once. Resolves conflict 3's
    second half and conflict 5.

13. **Enrolment on the phone: join, sign the club's waiver by typed name, finish the field
    guide, pick an area** (screens 1a, 1b, 1e, 1c, 1d, 1g) [client]
    `client/src/survey/screens/{Join,Waiver,FieldGuide,CallIt,Areas,AreaDetail}.tsx`;
    `fieldGuide.ts` from `fieldGuide.json` with the source line on every card; the claim
    day picker capped by the club setting. Done when each screen has a `flowCoverage.ts`
    entry (`SCREEN_DIRS` gains `survey/screens`) and a preview-shot recipe.

14. **Where is it? — GPS readings populate a plain grid as they arrive, the median is
    saved with its accuracy and count, and the screen never shows a presumed place**
    (screen 2c) [client]
    `client/src/lib/locationSampling.ts` (collect for up to 40 s or three consecutive
    readings within 20 m, both `@unvalidated`; keep all; median; `gps_lock` derived;
    `connection` from `navigator.connection` where it exists, else `unknown`);
    `screens/Location.tsx` drawing dots, the accuracy circle, a 50 ft bar and N on a grid
    with no basemap. "Can't stand at it? Mark it from here" sets `fix_source`. Done when
    the recipe shows readings landing and the verdict line, and the unit test proves the
    median and the lock rule on a fixture of 23 readings. Resolves conflict 4.

15. **Log a structure, one question per screen: type, same-one check, photos, size as a
    bucket, condition with the type's reminder, what should happen, check and save**
    (screens 2a, 2b, 2i, 2d, 2e, 2f, 2g, 2h) [client]
    `screens/{Stretch,Kind,SameOne,Photos,Size,Condition,Repair,Check}.tsx`; photos through
    `preparePhoto(file, 1600)`; "Save for later" on every step persists the draft to the
    outbox; Unsafe pre-selects the Report a Problem hand-off (`shelter_repair`, serious).
    Done when a draft survives a reload at every step and the eight recipes exist.

16. **A structure's history and finishing a walk, including where it ended early**
    (screens 2j, 2k) [client]
    `screens/{Structure,Finish}.tsx`; the Finish map is the walked track with a handle,
    which needs the small map below or ships as a list of the two end points for the pilot.

17. **Waiting to upload: the queue, the cellular toggle, Try now, and the on-open banner
    when anything has waited a day** (screen 3a) [client]
    `screens/Outbox.tsx`; copy reads "Show me on open if anything waits a day". Done when
    the banner appears in a test with a 25-hour-old item and not with a 23-hour-old one.

18. **The field-card plates: fetch the licensed candidates, approve each by eye against its
    caption, treat them to the house style, and list what the club still owes** [client]
    `features/structure-inventory-handoff/tools/fetch_plates.py` on `plates_manifest.json`:
    `fetch` (re-checks every licence at the source), `sheet` (contact sheets), a review pass
    that sets `approved` only where the photograph shows the scenario in the caption — a
    sound bridge is never approved for "abutment scoured" — then `treat`, which writes
    `client/src/design-system/assets/plates/<type>/<n>.jpg` and `plates.ts` with a credit
    per plate. Done when the PR's `## Screenshot` section carries the contact sheets with
    the approved rows marked, every plate's credit is in `plates.ts`, and the PR body lists
    the plates still wanted, by caption, for the club. Rests on the `heroPhotos.ts` licence
    gate; the one new rule is the eye against the caption.

19. **The field cards: one component, twelve contents, one plate at a time, the same card
    in training and on the Condition screen** (screens 4a–4l) [client]
    `survey/FieldCard.tsx`; plates from `plates.ts` with the credit rendered under the
    plate; a plate with no photograph shows the "photo wanted" tile (glyph + caption), never
    a drawing. Done when the card renders from `fieldGuide.ts` and `plates.ts` alone and the
    credit is in the DOM for every plate that has one.

20. **A small read-only map for the survey app and the org console: a line, typed points,
    nothing else** [client]
    `client/src/map/SmallMap.tsx` on the lazy engine (`map/mapEngineLoader.ts`), props
    `line`, `points: {kind, lat, lon, tone}[]`, `fit`; no gestures beyond pan/zoom. Unblocks
    1d, 1g, 2a, 2k, 3c, 3e; everything in Phases 2–3 ships without it first.

## Phase 3 — The club console

21. **`/org/:slug/inventory` joins the org console with queue, map, coverage and list pages**
    [client]
    `ORG_ADDRESS` in `client/src/lib/orgEntry.ts` gains `inventory`; `parseOrgRoute()` the
    `?page=queue|map|coverage|list` grammar; `client/src/org/screens/Inventory{Queue,Map,
    Coverage,List}.tsx`. Done when `reachability.test.ts` and `flowCoverage.ts` know the
    four modules and the demo org (`client/src/org/demoOrg.ts`) carries sample records.

22. **Review: accept, send back, merge, not ours, from a queue that puts Unsafe first and
    lets a supervisor see only their sections** (screen 3b) [client]

23. **Coverage: a trail, then Needs a walk or Everything on it, the rule in words and its
    thresholds in settings** (screen 3c) [client]

24. **Inventory and history: worst first, a history per structure, the Chair's note, CSV
    and GeoJSON** (screen 3d) [client]

25. **Review map: every record as a dot by review status, the same records as the list**
    (screen 3e) [client] — needs issue 20.

## Phase 4 — The landing page and the door

26. **A landing page explains the survey programme to a club and links to its door**
    [site]
    `site/src/pages/for-orgs/survey.astro` on `Base.astro` + `OrgNav.astro`, a hero from
    the licence-checked pool with its credit, a link to `/survey/?org=<slug>`; a
    `site-for-orgs-survey.mjs` recipe. Done when `siteCss.test.mjs` and the site build pass.

27. **A club can have the survey at its own address: `survey.ourhike.org` as a Cloudflare
    Pages project, with the three origin lists changed together** [.github]
    A `survey-host` job copying `docs-host` in `pages.yml`; `expected-origins.yml`, the
    Supabase redirect allow-list (`LAUNCH_CHECKLIST.md` 4.3b) and the R2 CORS policy in one
    pull request; `check-auth-redirects.yml` proves the redirect. After the pilot.

## Phase 5 — After the pilot

28. **Priority areas run parking lot to parking lot once the backend can read the published
    parking POIs** — replaces issue 6's section unit; carries a comparison of the two
    colourings on one club.
29. **A comment thread on a record** — `inventory_comments`, the sixth table.
30. **The club branding block: mark, accent, units, read by every club screen** — the
    general change the inventory needs first (`SPEC.md` decision "Whitelabel"), its own issue
    because the volunteers console and the embeds want it too.
31. **The SPA fallback on production GitHub Pages** — the standing gap `features/ORG_ONBOARDING.md`
    records; the survey app routes around it with `?org=` until then.
