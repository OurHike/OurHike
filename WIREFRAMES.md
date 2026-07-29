# OurHike — v1 MVP Wireframes

Companion to [FEATURES.md](FEATURES.md), [ROADMAP.md](ROADMAP.md), [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md), [TESTING.md](TESTING.md), and everything in [features/](features/). Extracted and reconciled 2026-07-28 from the interactive wireframe set at the link below (16 design turns, low-fidelity) — this file is the durable, versioned spec that survives in git history; the live link is the visual reference for exact layout, spacing, and copy.

**Live source:** [claude.ai/design — "Hiking App UI Wireframes"](https://claude.ai/design/p/0cacd2b5-3cc3-4e6d-8d2b-eda5d3a68bf6?file=OurHike+Wireframes.dc.html). Frame ids below (`12a`, `14d`…) are anchors in that file — open it and jump to `#12a`.

## What this is, and isn't

`OurHike Wireframes.dc.html` is a **design reference**, not production code: a self-contained prototype (custom `<x-dc>` runtime + `support.js`) that shows structure, states, and copy. The task is to recreate these screens in the actual codebase — React + TypeScript + Vite, MapLibre GL JS + PMTiles, Capacitor — using this repo's own patterns, not to port the wireframe's inline styles or markup.

**Deliberately not vendored into this repo:** the raw `.dc.html` / `support.js` prototype files. They're a generated, throwaway rendering harness (`support.js` literally starts `// GENERATED ... do not edit`), need their own copy of the design-system bundle to render, and would only go stale the moment the design evolves — the same reasoning [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md) already applies to fetched/generated pipeline data never entering git. This file is the durable extraction instead. If you need to re-pull the source (e.g. after new wireframe turns), it's reachable through the `claude_design` MCP tool using the project URL above.

## Fidelity: apply the real design system

The wireframes are monochrome-leaning lofi — layout and hierarchy only. Real styling comes from the **OurHike Design System**, already in this repo at [.claude/OurHike Design System/](<.claude/OurHike Design System/>):

- Tokens: `tokens/colors.css`, `typography.css`, `spacing.css`, `effects.css`
- **Working React components, not just HTML demos:** `components/core/{Button,Badge,Card}.jsx`, `components/forms/{Input,Select}.jsx`, `components/navigation/{NavBar,Footer}.jsx`, `components/feedback/Callout.jsx` — plain function components styled via the CSS custom properties in `tokens/`, each with a sibling `.d.ts`. Per its own `SKILL.md`: "If working on production code, you can copy assets and read the rules here." These are a real starting point for the client, not disposable.
- Type: Bitter (display), Public Sans (UI/body), IBM Plex Mono (coordinates, mile markers, sizes).

Where a wireframe *does* commit to an exact value, it's because the value carries meaning, not style — those are listed under **Load-bearing values** below and must survive implementation regardless of visual restyling.

---

## Screens / views

### 1. Map screen — the ~80% of v1 (`12a`, `5a`, `4b`)

**Purpose:** know where you are, what's ahead, and whether to trust it.

**Layout, top to bottom:**
1. **Status strip** — time, GPS/offline state, sync age.
2. **Header (read-only zone).** Trail + state eyebrow, current mile + direction (`mi 1,407.2 · NOBO`) in mono. Right side: two 38px icon buttons, gap 7px — **legend** (list icon) then **search**. Nothing else lives here.
3. **Elevation ribbon.** SVG profile (`viewBox="0 0 100 40"`, `preserveAspectRatio="none"`), 54px tall, left-inset 36px for lane labels. Shaded area under the line, a highlighted upcoming-climb region, a vertical "you are here" rule, min/max ft labels, and a callout: `+640 ft · 2.6 mi · ≈1h 10m`.
4. **Three waypoint lanes**, 19px each, dashed top rules, mono 7.5px labels in the left gutter: `WATER`, `SLEEP`, `ELSE`. Pins position by percentage along the mile window; overlapping pins collapse into a count pill (category glyph + count).
5. **Map canvas.** Trail lines, waypoint pins, GPS dot. Bottom-left: scale bar (64px, three-sided box) above `USGS US Topo · © OSM`. Bottom-right, 10px inset: a vertical stack, gap 8px, of **compass** and **locate** (42px each). Zoom buttons are **web only** — pinch covers mobile and the thumb zone is reserved for locate.
6. **Tab bar** — Trail / Downloads / More.

**Interaction rules:** everything tapped mid-walk sits in the lower third; everything read but not touched sits above. Locate is blue while tracking, grey when the fix is lost (`7b`).

### 2. Legend (`12b`)

Bottom sheet from the header icon. Lists **only what's in the current viewport**, with counts: blaze rows (white / blue / unknown, line swatch on a topo-tinted chip), then a 2-column grid of pin types with counts, including confidence variants ("Unverified · 1"). Rows are tappable to hide — **except the closure row and the serious-warning row**, which carry an "Always shown" tag and no hide affordance. Full 10-category list lives in Settings, not here.

### 3. Trail line rendering — blazes (`11a`, `11b`, `11c`)

One normalized `blaze_color` attribute per line feature; one MapLibre `match` expression on `line-color`. No per-layer hardcoding.

| blaze | source | line treatment |
|---|---|---|
| White | `centerline` (3,025 segments), flat per-source default in `sources.json` | thin dash 10px on / 6px off, hairline dark casing |
| Blue (code 1) | 641 `side_trails` | same rhythm, blue |
| Yellow (5) | 20 | short fast rhythm 6/5 |
| Orange (4) | 6 | even rhythm 10/5 |
| Red (3) | 2 | longest dash 15/5 |
| Green (6) | 4 | 13/5 |
| Purple (7) | 2 (+3 White, 2 Other) | standard rhythm |
| Neutral grey | 484 `None` + 24 empty + 9 `"Unknown"` + 3 `"Gold"` | sparse dotted 4/6 |
| Black (8) | 0 today | wide casing, no fill — drawn by absence |

**Rules that must survive:** decode the coded domain from the FeatureServer's own field metadata (don't hardcode the table); anything that doesn't decode falls to neutral grey **with a loud pipeline warning**; dash rhythm is a second, hue-independent channel so warm hues stay separable in greyscale/glare; tapping any line opens a sheet naming the blaze and its source, and says plainly when it's unknown.

### 4. Downloads (`10a`, `10b`, `6d`, `7a`) — ⚠ see Known Deviations, below

Wireframed as a per-section list with a per-section detail override. **This interaction model is superseded — see "Known deviations" below before building.** What still carries over: the Light / Standard / Fine (z11 / z12 / z13) detail choice itself, and the measured sizes.

### 5. Onboarding — Tier 1 (`13a` chosen, `13b` rejected, `13c` sequence)

Three screens, each skippable, each with a step counter:

1. **What OurHike is** — the real logo mark (see `.claude/OurHike Design System/` → `components/core/Logo.jsx`, chosen 2026-07-28 — supersedes this turn's original type-only wordmark), a small map vignette, two short paragraphs: what it does offline, and that paid memberships fund the ATC and volunteer clubs. "No account. Nothing to sign up for."
2. **Map size** — the whole corridor at Light 64 MB / **Standard 314 MB** (recommended) / Fine 1.18 GB. ⚠ The wireframe copy adds "...or take single sections later, in Downloads" — **drop that clause**, see Known Deviations.
3. **Location permission** — asked as an overlay **on top of the already-downloading map**, so the reason is visible. Copy: works with no signal, position never leaves the phone.

**Never asked here:** notifications (belongs to the wrong-way alert, at hike start) and **accounts** (asked at first contribution — see Reporting below). The step counter is derived from the live step list, and a skipped step still counts so the total never grows mid-flow.

### 6. Reporting (`14a`–`14d`) — supersedes turn `8` — ⚠ see Known Deviations

Five condition types in a 2-col grid: blow down, flooding, trash, shelter repair, animals. Then a separate section, **"About people on the trail,"** with two full-width cards, deliberately not icon buttons:

- **Something unsafe happened** (amber) — threats, robbery, being followed. Private to club moderators, never a public pin with a name. Its own form has chips (Threatened / Followed / Theft / Assault / Harassment / Other), a note, GPS location, and opens with an honest limit: **call 911 if you're in danger now; this reaches volunteers, sometimes days later.** If moderators confirm a pattern it can become an unnamed warning.
- **Say thanks to a maintainer** (green) — pick the club or a specific crew, tap what made the difference (blazes / blow down cleared / shelter / privy / bridge / tread work), leave a note. Negative feedback is nudged to the club directly rather than a public complaint.

**Report form:** note (free text), optional photo, location (existing POI, dropped pin, or GPS), "signed as `<trail name>` · `<reporter type>`," and the report's **real timestamp — the moment of writing, not of sending**.

**Sign-in happens at the first contribution, not in onboarding.** The report is written and saved first; then Google / Apple / email, then trail name + reporter type (thru / section / day / maintainer; maintainer is club-granted and stays unverified until confirmed). A green callout states that reading the map — water, shelters, closures, warnings — never needs an account.

**Four states, always visible to the reporter:** Waiting → Confirmed → Fixed, or Not confirmed. "Not confirmed" carries no penalty, deliberately.

**Public read of a report:** trail name + reporter type + exact date + maintainer confirmation badge + note + photo. (Hiding name/date is the Post-MVP anonymity window.)

### 7. Closures (`15a`)

A closure is a **line**, not a pin: a wide barred red band with a hard 1.5px casing along the closed trail geometry — structurally distinct from a red *blaze* (thin dash, hairline casing) so the two survive greyscale.

- Header banner when one is ahead: "Trail closed 1.4 mi ahead · Storm damage · mi 1,408.6 – 1,411.0".
- Tap sheet: reason (plain language), mile range, status (`open | closed | reroute-available`), closed-since + expected reopen, marked by (club admin, through the same moderation queue as reports), and a link to the club's reroute notice.
- **OurHike does not compute detours** and says so.
- **Sync age lives on the closure itself** ("Your copy is 3 days old…") — a downloaded map is most dangerous when it's stale about closures.
- **Not hideable.** `show_closures` is not a setting, anywhere.

### 8. Serious warnings (`15b`)

`severity: normal | serious` on the existing `Report` model, **set by a moderator, never self-declared**.

- Pin: 34px, red, `triangle-alert`, high-contrast halo — a variant inside the same icon spec, not a new visual language.
- Route banner on map open: "2 serious warnings on your route," with See both / Dismiss.
- Detail: "Confirmed by club moderators" badge + date, the corroboration sentence ("several separate reports over four days…"), reporter names **withheld** for anything about a person, and an explicit "why you weren't pinged."
- **Warnings never push.**

### 9. Wrong-way / off-trail alert (`15c`) — the only notification

Three beats:
1. **In-app cue** while the app is open: "You may be off the trail — about 90 ft from the white blazes for the last 12 minutes," with Show me the way back / I'm fine.
2. **Push**, only after sustained divergence: "You've been heading south for 25 minutes. Your hike is set NOBO." It won't ask again.
3. **Permission asked when a hike direction is set**, not at launch — before a direction exists there's nothing to be wrong about.

Two detection modes: distance-from-centerline (reuses `ST_LineLocatePoint` snap math) and reversed bearing vs. the `Hike`'s direction (needs a trailing GPS window, a minimum-movement threshold, a minimum persistence). Thresholds in the wireframe (90 ft, 12 min, 25 min) are **placeholders for field testing under canopy**. Web push requires the PWA added to the Home Screen on iOS; the Capacitor build is the reliable channel.

### 10. Settings (`16a`)

Four groups, one canonical `UserPreferences` model:

- **You** — trail name (Linked / on-this-device), reporter type, account.
- **The map** — background source (USGS topo downloaded is the default and the only offline-capable one), detail for new downloads, roads & walkability *(Later)*.
- **Display** — theme (Auto), units *(Later; mile markers stay miles either way)*.
- **Safety & privacy** — wrong-way alert toggle, "hide my name on reports for…" *(Later)*, and a red locked callout: **closures and serious warnings are always shown; there is no switch, here or anywhere.**
- **Your data** — export reports/routes (GPX, GeoJSON), last synced + Sync, sources & attribution.

Later rows are shown at reduced opacity with a "Later" tag rather than hidden.

### 11. Data staleness (`16b`)

A third visual channel, independent of confidence:

| tier | age | treatment |
|---|---|---|
| Fresh | ≤ ~14 days | pin + green ring |
| Ageing | ~14–60 days | pin, no ring |
| Stale / never | months, or never | pin faded to ~50%, dotted border, grey dotted ring |

Confidence stays separate: a dashed pin means *never verified to exist*; staleness means *when a human last said it was fine*. Always state it in words too: "Last confirmed in May · 78 days ago." A one-tap "Was it flowing?" updates the date, needs no account, changes nothing else — this is `DATA_NUDGES.md`'s `ConditionConfirmation` model. **Boosting** stale POIs' prominence to solicit confirmations is Data Nudges — Post-MVP; today staleness is described, never amplified.

### 12. Other states already wireframed

`7a` download in progress / failed mid-way (structure likely still applies to a single whole-corridor download, see Known Deviations) · `7b` no GPS fix · `7c` empty offline search (says the thing may exist outside what you downloaded) · `9b` off-corridor with the dashed "edge of downloaded area" boundary · `9c` offline outbox (reports wait, with their original timestamps) · `9d` sunlight/greyscale pass · `7f` web shell.

---

## Interactions & behavior

- **Search** takes over the header and collapses the ribbon to one line; local GeoJSON only, no network path, and says so on empty results.
- **Legend** opens as a bottom sheet from a header icon; contents recompute per viewport.
- **Locate** follows MapLibre `GeolocateControl` (`trackUserLocation` for continuous); **compass** is `NavigationControl`, tapping resets north-up. Scale bar is `ScaleControl`, imperial by default.
- **Motion:** 120–200 ms ease fades/colour transitions only; buttons press to 97%. No bounce, no spring (design-system rule).
- **Offline everywhere:** every write (report, thanks, confirmation) queues in an outbox with its authored timestamp and syncs later. Nothing blocks on network.
- **Loading/empty/error states are first-class:** download failure resumes rather than restarts; no-GPS shows the last known position with its age; empty search explains the boundary.

## State management

**Client:**
- `UserPreferences` (the single model above) in IndexedDB; syncs when an account is linked.
- Downloaded-package registry — **shape depends on resolving Known Deviations #1** below (whole-corridor vs. per-section).
- Live map state: viewport, visible-layer set, legend contents (derived), GPS fix + accuracy + age.
- Outbox: queued reports / thanks / confirmations with authored timestamps.
- Ephemeral `WrongWayCheck`: `{distance_from_nearest_trail_line, bearing_delta_from_hike_direction, sustained_since}`.

**Server (FastAPI + Postgres):**
- `User` (OAuth/email, verified, optional MFA, `display_name` = trail name, role incl. club admin / maintainer).
- `Report` — `type`, location (POI ref or lat/lon), `reporter_type`, `timestamp`, note, photo, `follow_up` (empty in v1, additive later), `status: submitted | verified | resolved | dismissed`, `visibility: public | internal-only`, `severity: normal | serious`. **Type enum needs a decision — see Known Deviations #2.**
- `Closure` — geometry range along the centerline, reason, `status: open | closed | reroute-available`, dates, marked-by.
- Moderation queue over `Report` + `Closure` (one workflow, not two).

## Load-bearing values

Meaning, not decoration — keep these regardless of restyling:

- Naismith: 5 km/h + 1 h per 600 m ascent, **rounded to 5 minutes, always prefixed `≈`, never shown as an arrival clock**, no descent credit (a known weakness of the rule — don't silently "improve" it).
- Download sizes: whole-corridor archive at z11 ≈ 64 MB, z12 ≈ 314 MB (default), z13 ≈ 1.18 GB (see `pipeline/README.md`).
- Blaze dash rhythms per hue (table above) and the neutral-grey fallback `#8a8271`.
- Closure = barred band + hard casing; blaze = thin dash + hairline casing.
- Staleness ring semantics (green / none / grey dotted) and the ~14 day / ~60 day tier edges.
- Control sizes: 42px map controls, 38px header buttons, ≥44px effective touch targets.
- The four report states' exact words: Waiting, Confirmed, Fixed, Not confirmed.

---

## Known deviations from the live wireframe — read before implementing

The wireframes were drawn iteratively across 16 turns while the feature docs kept evolving; two spots fell out of sync. Neither is a formatting nitpick — both change what actually gets built.

### 1. Downloads: whole-corridor, not per-section (resolved — follow ROADMAP.md)

[ROADMAP.md](ROADMAP.md) Phase 2 already decided this on 2026-07-28: **"chunking decided: whole corridor, one package"** — a hiker downloads the entire trail's data at once. That decision is settled and this file defers to it.

The wireframe (turns `6d`, `7a`, `7c`, `9c`, `10a`, `10b`) shows a **per-section** list — ~30–50 mile rows, a per-section detail-override sheet, roll-up totals, "mixed-detail seam" messaging. That model was drawn by explicit product direction *after* the whole-corridor decision, so the wireframe and the roadmap directly disagree. **Build to ROADMAP.md, not the wireframe, here:**

- One package for the whole corridor, not a section list.
- Keep the Light / Standard / Fine (z11 / z12 / z13) detail choice — but as the *only* download's detail, not a per-section override. The measured sizes (64 MB / 314 MB / 1.18 GB) are already whole-corridor figures, so they apply directly with no per-section ratio math needed.
- Drop: section list, per-section override sheet, roll-up "bytes remaining" math, mixed-detail-seam messaging.
- Fix the onboarding "Map size" screen (`13a`/`13c`) copy to remove "...or take single sections later, in Downloads" — there's no section granularity anywhere in the app.
- `7a`'s in-progress/failed states likely still apply structurally (a single download can still be mid-transfer or fail partway) — just against one package, not per-section rows.

### 2. Reporting: the "unsafe behaviour" / "say thanks" split isn't in the data model yet (open — needs a decision, not a docs fix)

[REPORT_A_PROBLEM.md](features/REPORT_A_PROBLEM.md) defines exactly six report types — `blowdown | trash | bad_hikers | flooding | shelter_repair | animals` — and explicitly flags `bad_hikers` handling as **"an open question, not decided [there]."**

Turn 14 of the wireframe answers that open question, but not by simply routing `bad_hikers` internal-only as the doc anticipated. It replaces the single `bad_hikers` type with **two** new cards:
- **"Something unsafe happened"** — this maps cleanly onto `bad_hikers` → `visibility: internal-only`, consistent with the doc's own recommendation.
- **"Say thanks to a maintainer"** — a **new, positive-report type with no prior design anywhere in the repo.** It's not a condition report and doesn't obviously belong in the `Report` model's `type` enum as written (wrong shape: no location-of-hazard, no moderation-queue need in the same sense, arguably not `internal-only` vs `public` at all but club-facing-only).

This is a real product/data-model decision — whether "say thanks" is a seventh `Report` type, a separate model entirely, or something else — not something to resolve silently in a docs-hygiene pass. Recommend picking this up explicitly in the next planning round, before backend/report work starts, since [MAP_OPTIONS.md](features/MAP_OPTIONS.md)'s closures and [HIKER_SAFETY.md](features/HIKER_SAFETY.md)'s warnings both build on the same `Report`/moderation-queue mechanism and would inherit whatever shape this takes.

> **Resolved 2026-07-29 — see [SAYING_THANKS.md](features/SAYING_THANKS.md).** A thanks is a comment about a specific place: the **seventh `Report` type**, same fields plus photos, optionally tagging a maintainer. It skips the moderation queue (there is nothing to verify), gets its own two states (`Sent` / `Delivered`) because "Not confirmed" on a thank-you note would be insulting, and gets a new `club_only` visibility rather than reusing `internal_only`, which was named for the `bad_hikers` safety case and means a different audience.
>
> The decision pulled in a dependency: to thank a maintainer you cannot name, the app must know who looks after which stretch **and when**, so [VOLUNTEERING.md](features/VOLUNTEERING.md) now carries a versioned `MaintainerAssignment` model. Lookups are always as-of the thanks' authored date, never "now" — a thanks written in June about a section reassigned in July belongs to the June maintainer.

---

## Design tokens & components

Real values live in this repo, not in this file — see [.claude/OurHike Design System/](<.claude/OurHike Design System/>) (`tokens/`, `components/`, `guidelines/`). The wireframe's own working palette was an approximation for layout purposes only; don't carry its hex values into real code.

## Assets

- **Icons:** Lucide line icons throughout (1.75–2.1px stroke) — `droplet`, `house`, `tent`, `mountain`, `signpost`, `square-parking`, `tree-pine`, `waves`, `trash-2`, `hammer`, `paw-print`, `shield-alert`, `heart-handshake`, `triangle-alert`, `octagon-alert`, `compass`, `locate-fixed`, `list`, `search`, `bell`, `lock`, `clock`, `refresh-cw`, `badge-check`, `shield-check`.
- **Real logo mark chosen 2026-07-28** — see `.claude/OurHike Design System/` → `components/core/Logo.jsx` (React) and `assets/logo-icon.svg` (standalone, for favicons/app icons). Supersedes every "no logo yet" note elsewhere in this doc and in the design system's own readme.
- **No photography** — placeholders only.
- **Map data:** USGS US Topo (public domain), ATC GIS layers, OpenStreetMap (ODbL — **visible "© OpenStreetMap" attribution required** once the Protomaps context basemap ships), USGS NHD, USGS 3DEP 1m DEM.

## Screen map

Which repo docs each screen derives from — useful when a frame's intent isn't obvious from the HTML alone:

| Screens | Repo files it derives from |
|---|---|
| Map approaches `1a`–`1d` | FEATURES.md (v1 MVP, UX principles), TECHNICAL_ARCHITECTURE.md |
| Ribbon + search `3a`–`3c` | FEATURES.md (search/filter, "use the app less often") |
| Ribbon density + icons `4a`–`4e` | FEATURES.md (waypoint icon spec), MAP_OPTIONS.md (legend), TRIP_PLANNING.md (Naismith time — MVP) |
| Lanes + clustering `5a`–`5c` | FEATURES.md (waypoint icon spec, outdoor usability pass) |
| POI detail `6a`–`6b`, `2a`–`2b` | OurHikeValues.md (#4), FEATURES.md (data sources), DATA_NUDGES.md (staleness) |
| Search `6c`, `2c` | FEATURES.md (basic search/filter by POI type) |
| Downloads `6d`, `2d`–`2e`, `10a`–`10b` | ROADMAP.md Phase 2 offline download flow; `pipeline/README.md` z11/z12/z13 sizes — **see Known Deviations #1**, per-section framing is superseded |
| Reporting `14a`–`14d` (supersedes `8a`–`8e`) | REPORT_A_PROBLEM.md (types, reporter_type, statuses), AUTHENTICATION.md (sign-in at first contribution), IDENTITY_AND_PRIVACY.md (trail name + who-sees-what) — **see Known Deviations #2**, type split isn't in the data model yet |
| Safety `15a`–`15c` | MAP_OPTIONS.md §4 (closures as a line, not hideable, no reroute computation), HIKER_SAFETY.md §1 + §5 (moderator-set severity, no push for warnings; wrong-way cue → push) |
| Blaze colours `11a`–`11c` | TRAIL_BLAZE_COLORS.md (coded domain + real counts, neutral fallback, accessibility), SEGMENTS.md (segments inherit line colour) |
| Route setup / direction `6e` | SEGMENTS.md, TRIP_PLANNING.md, MAP_OPTIONS.md (snap-to-trail) |
| Component inventory `6f`, `2m` | all feature docs |
| Download states `7a` | ROADMAP.md Phase 2 offline download flow |
| No GPS fix `7b` | ROADMAP.md Phase 2 "You are here," MAP_OPTIONS.md (GeolocateControl) |
| Empty offline search `7c` | FEATURES.md (offline-first), ROADMAP.md |
| Day-hiker map `7e` | SEGMENTS.md (day-hike persona), TRIP_PLANNING.md |
| Web shell `7f`, `2i` | FEATURES.md (web-only payments), MAP_OPTIONS.md (web legend panel) |
| About / attribution `9a`, `2g` | ROADMAP.md (OSM attribution), MAP_OPTIONS.md (settings), HIKER_SAFETY.md (anonymity window) |
| Off-corridor `9b`, `2h` | ROADMAP.md (Protomaps extended-context basemap) |
| Offline outbox `9c` | REPORT_A_PROBLEM.md (backend), DATA_NUDGES.md |
| Sunlight pass `9d` | ROADMAP.md Phase 2 outdoor usability pass |
| Settings `16a` | IDENTITY_AND_PRIVACY.md (canonical `UserPreferences`), UX_CUSTOMIZATION.md |
| Data staleness `16b` | DATA_NUDGES.md |

## Not yet wireframed

The source handoff's own "not yet wireframed" checklist listed several screens that the Screens/views section above (and the Screen map) already shows as drawn — closures, serious warnings, the wrong-way alert, settings, staleness, and onboarding all have frame ids. That checklist wasn't kept in sync with the later turns; reconciled against the actual screen inventory, what's genuinely still open is:

- A club-side moderator queue view (admin UI for the `Report`/`Closure` moderation workflow) — optional for MVP, hikers never see it.
- Anonymity window (Post-MVP, HIKER_SAFETY.md).
- Weather relay + elevation-aware conditions (Post-MVP, HIKER_SAFETY.md).
- Segments / Trip Planning (Post-MVP).
- Volunteering work-project pins (Post-MVP).
- Roads/walkability overlay (Post-MVP, MAP_OPTIONS.md).
- Auto-rotate (Post-MVP, UX_CUSTOMIZATION.md).
- Theme override, metric units, persistent waypoint/layer prefs (Post-MVP, UX_CUSTOMIZATION.md).
- Community Building — Tramily, check-ins, mentions (Post-MVP).
- Pricing tiers / paywall UI (Post-MVP, PRICING_MODEL.md).
- Trail names as a distinct onboarding tier (Post-MVP, ONBOARDING.md).

## Test plan

See [TESTING.md](TESTING.md)'s **Client (React/TypeScript)** section — the behaviors these screens need covered (blaze normalization, Naismith, download sizing, staleness tiers, the wrong-way detector, offline outbox, moderation invariants) before implementation starts.
