# The launch budget

How long the app may take to put a usable screen in front of a hiker who opens it,
what a launch is allowed to do before that screen is there, and what stops the
number from creeping back up once it has come down. This is the intended state;
the work that gets there is tracked on **#1298 — The launch budget: half a second to a
usable screen, Skip that answers on first run, and a build that cannot regress either**
and its six sub-issues, and the instrument is `client/scripts/measure-first-run.mjs` (TESTING.md §21).

The ask this answers, from the maintainer on 2026-09-09: "the screen is still taking
way too long to load on initial opening — like 6 seconds. Get that down and keep it
down to like 0.5 seconds."

## 1. What a launch costs today

Measured 2026-09-09 with the stopwatch's own profile — Chromium at 390×844, 4× CPU
throttle, 12 Mbps / 80 ms, tiles stubbed — against two builds: production
(`https://ourhike.org/app/`, v1.2.2, deployed 2026-09-08) and a local build of `main`
at `52fdf08` given production's public build values (the data bucket, the Supabase
project). Each cell below is the range over the clean runs — three against production for the
returning launch (one of which is discussed separately in §6), two for first run, two
of each for the local build. The runs came from an agent sandbox whose Chromium had to
be pinned to TLS 1.2 to pass the sandbox's egress proxy; that changes the handshake and
nothing on the main thread, and it is why the figures are compared to each other and
not to a laptop's.

**The returning hiker** — onboarding done, the release on the phone, landing on Today.
This is the launch every day after the first.

| | production v1.2.2 | `main` @ 52fdf08 |
|---|---:|---:|
| first paint (a blank page in the page colour) | 120–320 ms | 108 ms |
| first contentful paint | **1,152–1,572 ms** | 612–820 ms |
| a tap on Plan made at 0.8 s was accepted after | **933–1,441 ms** | 254–328 ms |
| long tasks · longest · total blocking time | 10–12 · 275–332 ms · **534–764 ms** | 3 · 78–97 ms · 54–88 ms |
| taps from 2 s on, accepted after | 80–257 ms | 57–104 ms |

**The first run** — nothing on the phone, the three entry steps up, the release
downloading behind them. **#857 — Skip on the first-run steps feels like a broken button, because the map behind
them is doing every waypoint's work** measured this on 2026-08-20 after its fix
(PR #862 — *Give the first-run steps a map: the centerline as soon as it lands, and
nothing else on it*) at 3,673 ms of blocking time, longest task 434 ms, the three Skip
taps answered in 11, 4 and 220 ms.

| | production v1.2.2 | `main` @ 52fdf08 | after #857's fix, 2026-08-20 |
|---|---:|---:|---:|
| first entry step reachable | 2,137–2,267 ms | 1,648–1,763 ms | — |
| Skip 1 · 2 · 3 accepted after | **3,211–7,286 · 4,785–5,331 · 330–2,997 ms** | 3,182–4,290 · 80–97 · 305–383 ms | 11 · 4 · 220 ms |
| long tasks · longest · total blocking time | 25–28 · 1,600–1,986 ms · **9,556–10,409 ms** | 18 · 617–706 ms · 4,507–4,584 ms | — · 434 ms · 3,673 ms |

**A caveat these two columns need, added 2026-09-09 after it was found the hard way.**
The production column is a phone with a real release on it — 16,949 waypoints, 11.5 MB
of trail lines. The `main` column is not: this sandbox's Chromium cannot reach
`data.ourhike.org` at all (`TypeError: Failed to fetch` from the page, while `curl` from
the same container gets a 200), so a locally served build downloads nothing and its
`--returning` mode replays a launch whose release is empty. **The two columns are
therefore not comparable to each other.** What the `main` column is good for is
comparing against another locally served build, which is what §1.1 does; what it cannot
show is any of the work that scales with the waypoint list. Production is the only
number here that has ever had that work in it.

Two things to hold onto from those tables:

- **First run has regressed to roughly three times the figure #857 — *Skip on the
  first-run steps feels like a broken button* — left it at**, and the Skip button reads
  as broken again, which is the complaint that issue was opened on. Nothing
  in CI could see it: `App.loadBudget.test.tsx` counts operations, and the operations
  it counts did not change; what changed is how much each one costs
  (**#1095 — POI from every org: the coverage survey, and DEC's and OPRHP's waypoints
  shipped** doubled the waypoint list to 16,949; **#1175 — Cut and publish coverage
  cells, because #556 built the unit the decision replaced** and **#1257 — Deliver the
  network lines and the junction graph in pieces a phone can read by range** added the
  coverage cells the launch now registers; the network overview arrived).
- **Production spends several times the blocking time of a build of `main`** — 534–764
  against 54–88 ms — on the same profile and the same data, and the gap held across
  every run. The two builds differ by three merged pull requests and by the host that
  serves them. Which of those it is remains an open question below, and it is the
  reason the plan's first job is an instrument rather than a fix.

### 1.1 After #1300 to #1304, measured the same way

Same profile, same flags, a build of the branch carrying production's public build
values, served locally — so this is the `main` column's successor and carries its
caveat: **no release on the phone**, which is why the last two marks read "not reached"
and why the waypoint work #1303 is about does not appear here at all.

| returning hiker | `main` @ 52fdf08 | after |
|---|---:|---:|
| first contentful paint | 612–820 ms | **276–448 ms** |
| tab bar rendered (the app's own mark) | not instrumented | **474 ms** |
| a tap on Plan at 0.8 s accepted after | 254–328 ms | **185–300 ms** |
| long tasks · longest · total blocking | 3 · 78–97 ms · 54–88 ms | **1 · 55–63 ms · 5–13 ms** |

| first run | `main` @ 52fdf08 | after |
|---|---:|---:|
| first entry step reachable | 1,648 ms | 1,229–1,431 ms |
| long tasks · longest · total blocking | 18 · 617–706 ms · 4,507–4,584 ms | 18–20 · 632–1,202 ms · 4,219–7,081 ms |

**First run is where this stops.** The returning launch is inside every §3 row on this
profile; first run is not, and the second Skip tap still waits seconds. #1304 removed
the two named main-thread costs — the pin rasteriser and the date formatter — and what
remains is MapLibre building the map behind the entry card and the release landing
mid-flow, which §4.6 describes and none of this work does. The run-to-run spread on the
first-run rows is wide enough that no claim smaller than "unchanged, and still over" is
honest.

Deterministic, and therefore subject to none of the above: eager JavaScript is **437 KB
compressed before this work and 215 KB after**, MapLibre is out of the eagerly loaded
closure, and `scripts/check-build-output.mjs` fails the build on either regression.

**What the stopwatch cannot see.** The maintainer's phone reports about six seconds
and the throttled profile reports 1.2–1.6 s to first content. The profile is a desktop
core at a quarter speed; a real launch adds the browser or WebView process starting,
a phone's storage, and its thermal state, and none of that has an instrument today.
Until it does, "six seconds" is the only measurement of the thing being complained
about, and it is one nobody can reproduce. §4.1 is the repair.

## 2. Where the time goes

### 2.1 Bytes before the first frame

Everything below is parsed and executed before React renders anything, on every
launch, whatever tab it lands on.

| eagerly loaded | raw | over the wire | what it is |
|---|---:|---:|---|
| `main-*.js` | 989 KB | 283 KB | React DOM (174 KB raw), every screen, `@supabase/supabase-js`, the shell |
| `protocol-*.js` (modulepreloaded) | 548 KB | 157 KB | **406 KB of it is `maplibre-gl-shared.mjs`** — the map engine |
| `main-*.css` | 260 KB | 36 KB | |

Measured off production's own HTML and assets on 2026-09-09; the attribution is the
local build's source maps.

**#722 — 860 ms of MapLibre parsing sits in front of the first paint, and nothing can
render until it finishes** deferred the engine behind `import('./engine')`
(`map/mapEngineLoader.ts`) because "maplibre-gl is 860 ms of parse on a throttled phone and it used to sit in
front of the first paint" (`map/MapView.tsx`). That deferral is defeated today by
three static imports in `App.tsx`, each of a module that does
`import { addProtocol } from 'maplibre-gl'` at its top:

| `App.tsx` line | imports | from | since |
|---|---|---|---|
| 74 | `CORRIDOR_ARCHIVE_URL` — a string | `map/protocol.ts` | `a5e8a49f`, 2026-08-27 — the same commit that introduced the `mapEngineLoader` seam |
| 132 | `setBasemapCells` — a setter on a module map | `map/basemap.ts` | `09998ef1`, 2026-09-02 |
| 133 | `setNetworkCells` — the same | `map/networkTiles.ts` | `50fe757c`, 2026-09-07 |

So Rollup puts the engine in a chunk both the shell and `engine.ts` reach, Vite
preloads it from the document head, and a launch that lands on Today — which mounts
no map on a phone (`App.tsx`'s `mapNeededNow`) — parses the whole engine for a
string and two setters. Nothing checks for this; `scripts/check-build-output.mjs`
asks whether the worker is wired up, not what the eager closure contains.

There is no `React.lazy` and no `Suspense` anywhere in `src/`. Plan, More, Moderation,
Registry, Downloads, Onboarding, the report and closure forms, Find a hike, the
volunteer screens and Settings are all in the eager chunk; so is the Supabase client,
constructed at mount and asking for a session before anything is on screen.

### 2.2 A first frame that waits on storage

`App.tsx:5706` — `if (!preferencesLoaded || !archivesRead) return null`. Nothing
renders until two things have come back from IndexedDB: the preferences and hiker
mode (two small reads), and **a status for every archive package** — for each one,
`readArchiveSize`, then `readDownloadProgress`, then a `localStorage` marker
(`lib/useArchiveDownload.ts:138–191`). The tab bar is behind that gate. So is the
Today header. The first frame a hiker sees is the page colour and nothing else, and
it stays that way for however long the slower of the two takes on their phone.

The archive half is worse than its comment says. The package set (`App.tsx:1377–1395`)
starts as the offered sheets and then **grows when the coverage cell indexes arrive**
— every basemap cell (62 for the A.T. package, measured in PR #1176 — *The bounding box proposes, the tiles
decide which cells get built*) and every network
cell, each registered "so their markers are read on mount like every sheet's". Each
growth makes `statusesKnown` false again (`useArchiveDownload.ts:379`), the shell
returns `null` again, and the tree that had just rendered is **unmounted and rebuilt**
once the new cells' markers have been read. A returning launch with signal does this
twice.

The gate exists for one decision — do not draw the live background for a beat and
then swap in the downloaded one (the comment above line 5706 says why: a blink, a
re-frame, ~2 MB of data). That decision belongs to the map's background choice. It
does not need the tab bar.

### 2.3 Waypoints on the render thread

**#1192 — A returning hiker's launch freezes for ten seconds while every waypoint is
placed on the trail, on the main thread** moved the placement into a worker
(`lib/trailIndexBuild.ts`) and `App.loadBudget.test.tsx` now holds that line. What
stayed on the render thread, per launch, for 16,949 waypoints:

- **Reading them.** `loadTrailData` (`lib/trailData.ts:1253–1292`) is nine
  `await get(...)` calls in sequence — nine round trips, not one — and the third is
  the whole waypoint array, deserialised out of structured clone on the main thread.
  The budget test's own figure was 82 ms for 2,837 waypoints on the throttled
  profile; the list is six times that now.
- **Walking them.** `searchablePois` (`App.tsx:2261`) maps every waypoint into a new
  object, and runs twice per launch — once when `pois` lands, again when `poiMiles`
  does. `viewportPoints` (`App.tsx:2493`) does it again for the map, on a launch that
  mounts no map. `hikePlaceOptions` (`App.tsx:2276`) walks the list for towns.
  `passedPlacesToday` (`App.tsx:5413`) walks `searchablePois`. `mileAnchors`
  (`App.tsx:2589`) walks it unless the release is on the pipeline's axis. `packPois`
  walks it once more to hand the worker its request. None of these is individually
  large; together they are five or six full passes with an allocation per row, in
  render, before Today has drawn.

### 2.4 Thirty requests before anyone tapped

A returning launch with signal starts, from `App`'s mount effects: **six independent
reads of `latest.json`** — `useTrailData`'s update check, `usePublishedSizes`, the
network overview, and one per coverage-cell family (`lib/dataManifest.ts` has 13 call
sites and its own header records the last time this multiplication cost a release);
three cell indexes, each fetched, SHA-256'd, parsed and written back; eight published
conditions artifacts, each written back to IndexedDB (`lib/useConditions.ts`); the
suggested-hikes artifact; the Supabase session; the service worker's own
`registration.update()`, called at mount rather than when the app is idle; and the
document head's `<link rel=preload>` of `trails_overview.geojson` — a request a
returning hiker's shell never reads, because `fetchTrailOverview` is gated on having no
trail lines (the bucket serves it with a five-minute `max-age`, so after that it is a
conditional request rather than the 200 KB, measured 2026-09-09; still a round trip on
the connection the first frame shares). None of it blocks a frame. All of it competes with the frame for one
connection and one thread.

### 2.5 First run's own bill

The local first-run profile names what holds the Skip button: about **1,000 ms of
MapLibre's own self time** building the centerline map behind the entry card (which
#857 — *Skip on the first-run steps feels like a broken button* — chose to keep: the
card is over a map, and the line is the one thing behind it worth seeing), 150 ms inside `App`'s render function itself, **140 ms of pin
rasterising on the main thread** (`map/poiIcons.ts`'s `insideGlyph` and
`buildPinImage` — work that `map/poiIconImages.ts` is supposed to send to a worker, so
either the fallback fired or a caller goes around it), and 61 ms of
`toLocaleDateString` in `lib/passedToday.ts`'s `localDay`, called per render. On
production the same window is dominated by functions in the engine chunk that the
minified build cannot name; the attributed run is what says they are MapLibre's.

**The parenthesis above is wrong, and §4.6 is where that gets settled.** "The card is
over a map" stopped being true at #1054 and this section inherited the sentence from
#857 without re-checking it. What the entry steps stand on is `.onboarding__hero`, a
full-viewport child at `inset: 0` painted in an opaque `--bg-chrome`. The line is not
the one thing behind the card worth seeing; nothing behind the card is visible at all.
Left in place rather than quietly corrected because the error is the interesting part:
every figure in this paragraph was measured, and the one clause nobody measured is the
one that made a thousand milliseconds look like a purchase.

## 3. The budget

All figures are on the stopwatch's profile (390×844, 4× CPU, 12 Mbps / 80 ms, tiles
stubbed), which is the only place they can be compared across pull requests. Each
carries how it was arrived at, per CLAUDE.md's three grades.

| | budget | today (production) | how the number was arrived at |
|---|---:|---:|---|
| **Shell frame** — tab bar and Today header rendered from the app's own markup, returning launch (the app's own mark is React's commit and lands a few tens of milliseconds ahead of `first-contentful-paint`, which the readout shows beside it) | **≤ 500 ms** after navigation start | 1,152 ms (first content) | **Picked** — the maintainer's ask. `@unvalidated` against a real phone: what settles it is §4.1's readout on the maintainer's own device |
| Any tab-bar tap, from the shell frame on | ≤ 100 ms to accepted | 933 ms at 0.8 s | **Reasoned** from the 100 ms input-response figure Chrome's RAIL model uses; not measured against this app's hikers |
| Longest task in the first 15 s | ≤ 100 ms | 275 ms | **Reasoned**: a 50 ms task is the long-task definition; 100 ms allows one frame's worth |
| Total blocking time in the first 15 s | ≤ 200 ms | 534 ms | **Reasoned** from Lighthouse's "good" threshold, which is the same 200 ms; not derived from anything measured here |
| Today's journal populated (waypoints on screen) | ≤ 1,500 ms | not instrumented | **Picked**. `@unvalidated`: a cached index and a batched waypoint read cannot beat two IndexedDB round trips plus a transfer, and nobody has measured those on a phone |
| First run: each Skip tap accepted | ≤ 100 ms | 3,211 · 5,331 · 2,997 ms | **Measured as achievable**: the fix for #857 — *Skip on the first-run steps feels like a broken button* — delivered 11 · 4 · 220 ms on 2026-08-20 |
| First run: longest task while the steps are up | ≤ 500 ms | 1,600 ms | **Measured as achievable**: 434 ms on 2026-08-20 |
| Eager JavaScript — every script the document loads before any `import()` | ≤ 250 KB compressed | 440 KB | **Reasoned** from the attribution: React DOM is ~50 KB compressed and the Today path's own code ~120 KB; 250 leaves room to grow and cannot hold the engine (157 KB) or a second screen set |
| `maplibre-gl` in the eager closure | never | present | **Measured**: #722 — *860 ms of MapLibre parsing sits in front of the first paint* |
| Full passes over the waypoint list on the launch thread before the shell frame | 0 | 5–6 | **Reasoned**: Today draws nothing from the list without a position, and the position arrives after the frame |

**What the budget is not.** It is not a Lighthouse score, and it is not the phone's
number: the process starting is outside anything this repository can change, and the
readout in §4.1 is there to say how much of the six seconds is ours. The stopwatch is
still not a CI gate, for the reason TESTING.md §21 gives — a runner's milliseconds are
nobody's phone. What gates is the deterministic half (§5).

## 4. The shape of a launch that fits

Six changes of shape, one sub-issue each under #1298. None of them is a task list; the
issues carry those.

### 4.1 Instrumented before optimised

`performance.mark` at the moments that matter — script start, shell frame,
preferences landed, Today populated, index landed — read back in **Settings → About
build** and carried in the bug-report prefill beside the build details it already
fills in. The same marks are what the stopwatch prints, so a number from a phone and a
number from the profile name the same events. A daily scheduled run of the stopwatch
against production, in the `check-deployed-app.yml` family (a tracking issue as the
signal, never a red run), records where production stands each morning and what a
release moved. The maintainer's "six seconds" gets a name on their own device, and
the production-versus-`main` gap in §1 gets an answer.

### 4.2 The engine loads when a map is built, never before

Nothing `App.tsx` imports statically may import `maplibre-gl` at module top. The
corridor URL, the two cell registries and whatever else the shell needs from
`map/protocol.ts`, `map/basemap.ts` and `map/networkTiles.ts` live in maplibre-free
modules; the `addProtocol` registrations stay where the engine seam already calls
them (`map/engine.ts`). The build then emits the engine only in the chunk
`import('./engine')` reaches, and `scripts/check-build-output.mjs` walks the eager
closure from `index.html` — the module script plus every `modulepreload` — and fails
the build on a MapLibre marker or on the byte budget. This is the one change that is
a regression repair rather than a design: the state it restores is the one #722 —
*860 ms of MapLibre parsing sits in front of the first paint* — left.

### 4.3 A shell frame that waits on nothing

The tab bar and the Today header render on React's first commit. The stored values
they need — onboarding completed, theme, hiker mode — are mirrored to `localStorage`
for a synchronous read, the pattern `lib/cameraMemory.ts` and `lib/pace.ts` already
use, with IndexedDB staying the record and the mirror correcting itself a tick later
if the two disagree. The archive-status gate moves from the tree to the one decision
that needed it, the background sheet's, and the marker sweep becomes one batched read
(`getMany`) that fills statuses in as they come and never returns the tree to `null`.
**What stays honest**: a Today that renders before its data says "unknown" in every
line that needs the data — the mile, the journal, the alerts — exactly as it does now
between the index landing and the fix arriving.

### 4.4 Only Today's code arrives eagerly

Every screen a launch does not show is a `React.lazy` boundary with an idle-time
prefetch, so a tap on Plan is instant a second after launch and the eager chunk
holds the shell, Today and what Today draws. The Supabase client is constructed
behind a dynamic import after the shell frame; nothing on Today needs an account.
`latest.json` is read once per launch and shared by every consumer — the shape
`publishedHashes()` already gives the download path. The conditions fetches, the cell
indexes and their hashing, the suggested-hikes artifact and the service worker's
update check run after the shell frame, on idle, in that order of usefulness to a
hiker. The head preload of `trails_overview.geojson` is emitted only for a first run,
which is the only launch that reads it.

### 4.5 Waypoints are the worker's, not the render's

The waypoint list is read and shaped off the launch thread — either stored packed
(one typed record rather than 16,949 objects) or read inside the trail-index worker,
which already holds the request that needs them — and handed back as the one derived
structure the shell actually uses. The five passes in §2.3 become one, computed where
the data lands, and map-only derivations (`viewportPoints`, `disputedPoints`) wait for
a map. Today's journal, passed places and the search rows read the same structure.
**What stays honest**: absent is still unknown; a waypoint the worker has not placed
has no mile, never a zero.

### 4.6 First run keeps its budget too

The first-run profile is read by name (§2.5) and each named cost is either moved off
the tapping thread or held until the steps are done, the way #857 — *Skip on the first-run steps feels like a broken button* — held the
waypoints: the pin rasteriser goes back into its worker for every caller, and
`localDay` is memoised per day rather than per render.

**And the map is not built at all while the steps are up** — #1324 — *First run builds
the whole map screen behind an opaque photograph*. This section used to say MapLibre's
work behind the card should be *bounded*: draw the 200 KB centerline sketch, hold the
11.5 MB line and the network until the card is gone. That was the right shape for a
card the map is visible through, which is what first run was from #721 until #1054 put
a photograph in front of it. It is the wrong shape for a wall.

**Measured** 2026-09-09 on the built app at 390×844, in pixels: every layer of the map
screen — the wrapper, the screen, the canvas container and the canvas — painted
`rgb(255, 0, 255)` by injected CSS, first run rendered as it normally does, the frame
screenshotted and counted. The map screen was present and so was its canvas. **Magenta
pixels in the frame: 0 of 329,160.** `desktop.css` had already run the same experiment
in red on 2026-08-27, for a different reason, and filed the answer under the scrim.

A `document.elementFromPoint` grid was tried first, and is recorded here because it is
the wrong instrument in a way that looks right: `.onboarding__hero` is
`pointer-events: none`, so the hit test walks past the very element whose opacity is
the question and reports whatever is behind it. It answers what a finger reaches, never
what an eye sees — and on this screen those are different questions with, as it happens,
the same answer.

So the bound is zero. The saving is the whole of MapLibre's self time — 730–950 ms
across three cold runs — plus the map screen's own React tree, which is where
`StatusStrip` was rebuilding an `Intl.DateTimeFormat` per render (87–124 ms) for a
clock the same wall covers. What #721 promised — *the map is warm the moment the steps
finish* — is kept, and moved: an idle callback after the steps mounts it, at the point
the thread is free rather than the point it is busiest. A phone never collected that
warmth at the promised moment anyway, because first run lands on Today and Today covers
the map.

**#863 — On a cold first run the trail line never appears behind the entry steps,
because it waits for the whole release to commit**'s answer — commit the centerline as
soon as it is fetched — stays, for a different reason than it was written for. Nothing
draws it during the steps now; what it buys is a warm map that already has its line,
and a phone that is not still fetching one when the hiker reaches the Map tab.

Two things this deliberately does not do. **Desktop still builds its map from launch**
(`isDesktop` is not conditioned on `entering`): the hero covers a desktop viewport too,
but a desktop shows Today *beside* the map the moment the steps end, so the warmth is
collected there, and a laptop is not the profile this budget is about. And **the
photograph stays** — #1054 settled what first run sells, and this changes only what is
paid for behind it.

## 5. What keeps it there

Three layers, each catching what the one above cannot.

**At build time, deterministic** — `scripts/check-build-output.mjs`, which already runs
inside `npm run build`: the eager closure's compressed bytes against the budget in §3,
and a refusal if any eager chunk carries `maplibre-gl`. A pull request that puts the
engine back fails its own build before CI sees it.

**In the suite, deterministic** — `App.loadBudget.test.tsx`, which already counts
operations rather than milliseconds: the tab bar is on screen before any IndexedDB
read resolves; the launch thread performs no full pass over the waypoint list before
it; the archive sweep never unmounts a rendered tree. Each is a count, so it fails on
any machine.

**In review, by hand** — a pull request touching the launch path pastes the
stopwatch's `--returning` and first-run output into its body, the way #857 — *Skip on the first-run steps feels like a broken button* —
and #1192 — *A returning hiker's launch freezes for ten seconds* — did. The launch path, named so nobody has to guess: `main.tsx`, `App.tsx`
above its first `return`, `lib/useTrailData.ts`, `lib/trailIndexBuild.ts`,
`lib/useArchiveDownload.ts`, `screens/Today.tsx`, `vite.config.ts`, and anything
that changes what `index.html` loads.

**Every morning, against production** — the scheduled stopwatch in §4.1, so a
regression that slips all three still has a date on it by the next day, and a
release's effect on the launch is a row in an issue rather than a feeling.

## 6. What this does not know

- **The phone's own number.** Six seconds is one report from one device with no
  breakdown; §4.1 exists to get one. Until then every budget line in §3 is on the
  profile, and the gap between the profile and the pocket is unmeasured.
- **Whether 500 ms is reachable on a phone once the process start is counted.** It
  is reachable on the profile — a build of `main` already paints content at 612 ms
  with the engine still in the eager chunk — and unknown on a device.
- **Why production costs several times what a local build does.** Partly the release on
  the phone, which the local runs do not have (§1's caveat) — and that alone may be the
  whole of it. The daily job in §4.1 times production itself, which is what settles it.
- **What this branch does to a launch with a real release on it.** Nothing measured here
  can say: the sandbox's browser cannot put one on the phone. #1303's saving is counted
  in passes rather than in milliseconds for that reason, and the first production number
  after this ships is the one to read.
- **One production run in three did not launch as a returning hiker at all.** Content
  painted at 1,368 ms, but no tab bar appeared for the eight minutes the run waited, and
  the main thread spent them in MapLibre's tile handling — 38 long tasks, the longest
  1,780 ms. That is the shape of the entry steps coming back up over a full map, which
  is the launch #857 fixed and only happens when the stored preferences do not say
  onboarding is done. The other two runs, and both local runs, launched normally from
  the same warm-up. Whether a phone can hit it — a preferences read that rejects falls
  back to defaults, and defaults mean first run (`App.tsx:1165–1188`) — is not known,
  and it is the kind of thing §4.1's readout would catch on a real device.
- **The Capacitor shells.** Both serve the same bundle from the binary with no
  service worker (`client/capacitor.config.ts`); the parse and the gate cost the same
  and the network costs differ. The stopwatch has no mode for them.
- **Desktop.** `isDesktop` mounts the map at launch by design (`App.tsx:1024`); the
  budget above is the phone's, and a desktop budget is not decided here.
