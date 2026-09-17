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

### 1.1 After #1300 to #1304 and #1324, measured the same way

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

| first run | `main` @ 52fdf08 | after #1300–#1304 | after #1328 |
|---|---:|---:|---:|
| first entry step reachable | 1,648 ms | 1,229–1,431 ms | 1,135–1,297 ms |
| Skip 1 · 2 · 3 accepted after | 3,182–4,290 · 80–97 · 305–383 ms | 3,721–3,848 · 46–55 · 235–262 ms | **120–147 · 52–71 · 242–254 ms** |
| long tasks · longest · total blocking | 18 · 617–706 ms · 4,507–4,584 ms | 18–20 · 632–1,202 ms · 4,219–7,081 ms | **10–12 · 238–259 ms · 785–861 ms** |

**The paragraph that stood here said first run was where this stopped, and it was
overtaken within the hour.** It is worth reading rather than replacing, because being
wrong is the interesting part: it named "MapLibre building the map behind the entry
card and the release landing mid-flow" as what remained, and treated the first as work
somebody would one day have to do. #1328 — *Stop building the map behind first run* —
found instead that the work should not be done at all: an opaque photograph has stood
over that map since #1054, so the ~900 ms was buying a backdrop that contributes no
pixel to the frame. The fix was to stop paying, not to pay more efficiently.

**Where first run stands now.** The longest-task row is inside its §3 budget (≤ 500 ms)
and the Skip rows are not: 120–147 ms against ≤ 100 ms on the first tap, 242–254 ms on
the third. Both are now `presentation`-dominated rather than script-dominated — Skip 1
breaks down as `input delay 8–10 · processing 0–2 · presentation 54–69`, and Skip 3
carries 205–219 ms of presentation, which is the entry card handing over to Today and
is unchanged by any of this work. That is a different problem from the one these five
issues were about, and nothing here has scoped it.

**The release still never lands in any of these runs** (§1's caveat), so the second
cost that paragraph named is measured by none of these columns, before or after.

Deterministic, and therefore subject to none of the above: eager JavaScript is **437 KB
compressed before this work and 215 KB after**, MapLibre is out of the eagerly loaded
closure, and `scripts/check-build-output.mjs` fails the build on either regression.

**What the stopwatch cannot see.** The maintainer's phone reports about six seconds
and the throttled profile reports 1.2–1.6 s to first content. The profile is a desktop
core at a quarter speed; a real launch adds the browser or WebView process starting,
a phone's storage, and its thermal state, and none of that has an instrument today.
Until it does, "six seconds" is the only measurement of the thing being complained
about, and it is one nobody can reproduce. §4.1 is the repair.

### 1.2 A laptop, which none of the above measures

Measured 2026-09-15 after a report of "the first page is loading blank for like 5
seconds" with a screenshot of a sidebar and an empty pane.

**Against production**: `https://ourhike.org/app/`, serving `main-Bx2gadkk.js`,
whose inlined version reads 1.3.0. Chromium at 1728×1080, returning hiker —
onboarding done, the 2026-09-14 release on the machine — reloaded with the service
worker, cache storage and HTTP cache cleared, which is the state a deploy leaves
every returning hiker in because it re-hashes every asset. The cold column is the
report's own case; the warm column is the same launch with the precache intact.

| | warm precache | cold, 1× CPU | cold, 4× CPU |
|---|---:|---:|---:|
| sidebar on screen | 136 ms | 682 ms | 812 ms |
| Today's journal has text | 585 ms | 1,310 ms | **2,725 ms** |
| map canvas sized | 638 ms | 2,229 ms | 2,970 ms |
| **the pane beside the sidebar is empty for** | 449 ms | 628 ms | **1,913 ms** |

The frame in between is not a slow render. It is `App.tsx`'s `nothingWouldRender`
branch — a tab bar and nothing else — which above the breakpoint is the sidebar, its
"Today I'm" switch and the wordmark, and nothing else at all. It holds for as long as
`mapMounted` is false, and on a laptop `mapMounted` is the only thing that can put
Today on screen: the Today branch is guarded `activeTab === 'today' && !isDesktop`,
and above the breakpoint the journal is `MapScreen`'s `journal` prop instead.

**Attributed** on the same profile at 4× CPU against a local build of `main` carrying
production's public build values, with `performance.mark` at each phase boundary
(the marks were temporary and are not in the tree):

| | at |
|---|---:|
| sidebar on screen | 212 ms |
| the preferences record read | 374 ms |
| the waypoints ready (`ourhike:today`) | 965 ms |
| MapScreen's deferred chunk landed | 1,662 ms |
| **`archivesRead` — the last gate to open** | **2,009 ms** |
| Today's journal has text | 2,230 ms |
| the map engine's chunk landed | 2,394 ms |

**These two tables are not comparable to each other**, for the reason §1 states in
bold about its own pair: one is production with its own release, the other a local
build on this sandbox's network. The 2,725 ms above and the 2,230 ms here are two
launches, not a before and an after. Each is comparable only to another run of the
same kind.

Two things that table settles and one it does not. It settles that the journal waits
on `archivesRead` alone on this run: MapScreen's chunk landed 347 ms before the gate
opened and the engine landed 164 ms *after* the journal already had text, so neither
was on the journal's critical path. It settles that the data Today draws was ready at
965 ms and sat unrendered for 1,265 ms behind a gate about which background the map
is built around — a decision Today does not participate in.

**What it did not settle was why `archivesRead` is late.** That mark has since been
taken — #1429, same profile, a probe on the archive sweep's own first read:

| | at |
|---|---:|
| the sweep issues its first read | 337 ms |
| **that read answers** | **663 ms** |
| `archivesRead` — every package finally answered | 2,327 ms |

**So it was never one slow read.** The sweep's first IndexedDB round trip costs 326 ms
on a 4× core and is done at 663 ms; the gate then takes a further 1,664 ms. What is
left to explain is an accumulation rather than a latency — many packages, a thread busy
with the release read and the index build (`ourhike:today` at 1,141 ms,
`ourhike:index` at 2,704 ms), or both. **Which of those, and in what proportion, is
still `@unvalidated`**: separating them wants a per-read timing and a package count at
the moment the gate opens, and nothing has taken those. It stopped being the front
door's problem in #1429 — Today no longer waits on this gate — so what remains is a
question about when the MAP arrives, which is a laptop's to answer and not a hiker's
first screen.

### 1.3 After #1429: the front door stops waiting for the map

Today above the breakpoint was `MapScreen`'s `journal` prop and nothing else, so it
could not draw until the map did. It renders in its own `.map-screen__journal` column
before the map arrives now, and MapScreen takes the same node over when the map lands.
Same profile as §1.2's attributed table — cold cache, returning hiker, 1728×1080, 4×
CPU, local build carrying production's public build values:

| | before | after |
|---|---:|---:|
| sidebar on screen | 263 ms | 255 ms |
| **Today's journal has text** | **2,565 ms** | **255 ms** |
| map canvas sized | 2,870 ms | 2,665 ms |
| **the pane beside the sidebar is empty for** | **2,302 ms** | **0 ms** |

The journal now arrives on the same frame as the sidebar, which is what "0 ms" means:
there is no frame in which a laptop shows navigation and nothing else. **The map is
unmoved** — 2,870 → 2,665 ms is this profile's run-to-run spread, not a saving, and no
part of this change was aimed at it. Eager JavaScript is unchanged at 254,816 bytes:
the column reuses what the shell already imports.

What did not change, and is the honest cost: when the map lands, the pre-map branch
unmounts and MapScreen mounts the same journal, so the column is rebuilt once. Every
piece of state a hiker can have touched by then is the shell's and survives — which
page Today is on, the mode, an open day-hike card. Scroll position inside the column
does not. Drawing nothing for those two seconds was the alternative.

One measurement nearby, for whoever picks this up: the map engine ships as
`mapWorker-*.js` at 991 KB raw and 257 KB compressed. It is correctly outside the
eager closure — `scripts/check-build-output.mjs` holds that — and on a laptop it is
in front of Today anyway, because Today is the map's child.

### 1.4 After #1560: the map's own arrival, and the two frames on the way to it

**#1560 — On a laptop the map arrives seconds after Today, and on the way the
journal renders full-width, the whole page blanks, and the engine only starts
loading once the gate has opened** measured the launch §1.3 left, on the
maintainer's report of 2026-09-17 ("several seconds for the map to appear…
makes the whole page look buggy on the first open"). Same shape as §1.3's
profile with three differences, each stated because it changes what the numbers
mean: 1× CPU rather than 4×, because the report was a laptop's; the release AND
the three coverage-cell indexes on the machine (seeded, since the published
indexes were being rejected — #1559); and a build of `main` at 596af5e served
through `client/scripts/data-proxy.mjs`, which sends the app's own assets
uncompressed, so every cold "network" figure below is pessimistic against
production's gzip and comparable only to its neighbour in the table. Two runs a
cell; a range is the two.

| laptop, 1728×1080, 1× CPU | cold, before | cold, after | warm, before | warm, after |
|---|---:|---:|---:|---:|
| sidebar and Today's journal on screen | 452–471 ms | 440–448 ms | 47–89 ms | 50–63 ms |
| the journal's width in that frame → once the map has it | **1,519 → 405 px** | 405 → 405 px | **1,519 → 405 px** | 405 → 405 px |
| the whole page blank, sidebar included | **897 → 2,044 ms** | never | never | never |
| map screen mounts (`.map-screen`) | 1,643–2,044 ms | 2,149–2,329 ms | 523–616 ms | 578–679 ms |
| map canvas exists | 2,748–2,982 ms | 2,371–2,486 ms | 591–679 ms | 578–679 ms |
| `ourhike:map` — the engine handed the shell a map | not instrumented | 2,705–2,808 ms | not instrumented | 578–679 ms |
| first frame with 40+ WebGL draw calls — the pins, NOT the line (see below) | 4,457–5,697 ms | 4,267–4,864 ms | 2,047–2,330 ms | 2,057–2,312 ms |
| the trail-line source reports loaded (instrumented build, one run each) | — | metadata at 4,707 ms; not loaded by 6.2 s | — | **6,155 ms** |

What moved and what did not, read across the rows:

- **The two frames that looked broken are gone**, and they were the report. The
  journal is its 404 px column from its first frame (`desktop.css`, one rule at
  the specificity App.css's phone rule had been winning on), and the pre-map
  branch now stays up until `MapScreen.loaded()` says the deferred screen can
  draw, so nothing blanks between the archive store answering and the chunk
  landing. A first draft of that hold was a render late on a warm launch and put
  two sidebars up for the length of the map's construction (250–310 ms); the
  readiness is read during the render now, and `journalNode2` lands in the same
  commit as `.map-screen` in every run above.
- **The canvas comes 0.3–0.5 s sooner on a cold launch** because the engine's
  chunk is fetched from the first frame on a laptop instead of after the map
  screen has mounted. The map screen itself mounts 0.3–0.5 s *later* on this
  profile, because the same 25 Mbps link now carries the engine beside
  MapScreen's chunk and 37 others — a cost that is the proxy's uncompressed
  bytes more than anything a laptop on production would pay, and the canvas
  is the frame a hiker sees.
- **The warm launch is unmoved, and the line is nowhere near two seconds.**
  The "40+ draw calls" row was first written up as "the trail line drawn", and
  the screencast says otherwise: at 2.2 s and 3.1 s the warm launch's pane
  holds the pins and no line. What that row measures is the pins arriving. An
  instrumented build recording each source's `sourcedata` puts the trails
  source — the 11.5 MB blob, 249,038 vertices in 1,657 features, fetched and
  tiled by MapLibre's single worker — at **loaded 6,155 ms** on a warm launch
  at 1×, with the basemap tiles (`osm`) loading at 6,158 ms behind it and
  every small GeoJSON source (pins, closures, sketch) done by 2.0 s; cold it
  reports metadata at 4,707 ms; at 4× it had not loaded by the 10 s the run
  watched. The line is the whole of the gap to the maintainer's two seconds,
  and no change here touches it — **#1564 — Research: the map on screen,
  trail line included, within two seconds of opening the app** is about that.

Two marks were added for this (`lib/launchMarks.ts`): `ourhike:map` and
`ourhike:map-drawn`, the second on MapLibre's `load`. Settings → About build
and the stopwatch print both, so the maintainer's own laptop can now say where
its map arrives — the number this section could not give and §6's first bullet
still asks for.

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

**One exception, stated so it stays one (#1560).** A laptop builds a map on
every launch (`isDesktop` is in `mapNeededNow`), so above the breakpoint
`App.tsx` calls `loadMapEngine()` at the first frame and the engine's fetch
overlaps the archive sweep instead of following it — a dynamic import, so
the eager closure is exactly what it was and `check-build-output.mjs` still
walks it. Below the breakpoint nothing changed: a launch onto Today asks for
the engine zero times, and `App.loadBudget.test.tsx` counts that.

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

**And a constant read out of a screen brings the screen with it.** A static value
import puts the exporting module in the importer's chunk, whole — Rollup cannot take
the number and leave the file — so `App.tsx`'s `import { FIT_PADDING } from
'./map/MapView'`, one integer used twice, held the map view in the eager closure along
with everything it statically reaches. **Measured** 2026-09-15, by attributing a
production-configured build's `main-*.js` to its sources through the sourcemap:
14,808 raw bytes came out when the constant moved to `map/fitPadding.ts` —
`map/MapView.tsx` 5,931, `map/trailsInView.ts` 4,762, `map/lineTaps.ts` 1,826,
`map/closureTape.ts` 849, `map/longPress.ts` 715, `map/mapDetail.ts` 351,
`map/labelVisibility.ts` 231, `map/mapEngineLoader.ts` 207 — taking the eager total
from 256,159 to 251,098 compressed, on a Today screen that mounts no map. This is
§4.2's shape without §4.2's marker: `check-build-output.mjs` finds MapLibre by name
and had nothing to find here, so the only thing that reported it was the budget going
red and the attribution being read afterwards. The rule it generalises to: **a
constant the shell reads out of a screen-sized module belongs in a module of its
own**, and the screen imports it too.

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
any machine. Its desktop block (§1.2, §6's bullet) counts the same way above the
breakpoint — the sidebar paints before any read resolves, one map is built for a
launch that lands on Today, and Today itself is on screen before the store answers.
That last one stood as characterisation until #1429: it asserted the pane WAS empty,
said the fix would turn it red, and named inverting it as the repair. #1429 inverted
it, which is the shape to copy the next time a defect is pinned before it is fixed.

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
  back to defaults, and defaults mean first run, which is the mirror-seeded
  `preferences` state beside `readLaunchMirror` and the `setPreferencesLoaded(true)`
  that a rejected read still runs — is not known, and it is the kind of thing §4.1's
  readout would catch on a real device. (This bullet used to cite `App.tsx:1165–1188`
  for that fallback; those lines are day-hike chart state today. The same drift §6's
  desktop bullet below records, found while editing the section around it.)
- **Whether a hiker ever notices the map arriving cold.** #1324 stopped building the
  map behind the entry steps and warms it on an idle callback once they are done, so a
  hiker who reaches the Map tab before that callback runs pays the build then. On the
  profile the warm lands at 3.8–5.1 s with nothing waiting on it, which says only that
  the callback fires — not that it beats a real thumb. `@unvalidated`: what would settle
  it is §4.1's marks read off a device, which is #1299's instrument and has not been
  pointed at this.
- **What the residual 84 ms in `lib/todayText.ts` is.** Hoisting its two `Intl` builds
  moved the sampled self time 100 → 84 ms and no further, and the count that would
  explain the rest does not: `Today` renders 14 times on a returning launch and 0 during
  first run (measured 2026-09-09 with a counter on the component), which is nowhere near
  enough `format` calls to be 84 ms. A sampled profile attributing neighbouring
  functions in the same module to that line is the likeliest explanation and is a
  hypothesis, not a finding. #1334 has the history, including the inference this
  document previously carried as fact.
- **Why first run's Skip taps are `presentation`-bound.** After #1324 the first tap is
  120–147 ms against a ≤ 100 ms budget with only 8–10 ms of input delay and 0–2 ms of
  processing; the third carries 205–219 ms of presentation. The remaining cost is paint
  rather than script, and nothing here has established what is being painted — the entry
  card runs its own keyed entry animation on every step, which is a candidate and has
  not been measured.
- **The Capacitor shells.** Both serve the same bundle from the binary with no
  service worker (`client/capacitor.config.ts`); the parse and the gate cost the same
  and the network costs differ. The stopwatch has no mode for them.
- **Desktop.** This used to read "`isDesktop` mounts the map at launch by design; the
  budget above is the phone's, and a desktop budget is not decided here", and it is
  worth keeping what was wrong with it rather than replacing it quietly. The sentence
  is true and the inference everybody drew from it is not: it reads as "a laptop pays
  extra for a map, and a laptop can afford one", and what it actually excluded was
  **Today**, because above the breakpoint Today is the map's `journal` prop and not a
  screen of its own. So the one form factor where the front door renders behind the
  map is the one form factor with no budget on the front door. §1.2 is what that cost,
  measured, and §1.3 is #1429 removing it — Today draws in its own column before the
  map arrives now, so a laptop's front door is on screen at 255 ms rather than
  2,565 ms. §5 names the counts `App.loadBudget.test.tsx` holds above the breakpoint,
  including the one that was characterisation until #1429 inverted it. **What is still not decided here is the budget itself** — §3's rows are
  the phone's, a laptop's are not them, and what they should be wants §4.1's on-device
  readout rather than a number picked here. The line reference this bullet used to
  carry (`App.tsx:1024`) had drifted off the symbol it named; so had
  `App.tsx:1165-1188` three bullets above, and citing a name rather than a line is the
  repair for both.

## 7. The map in two seconds: what the worker does at launch, and the plan (#1564)

The maintainer, 2026-09-17, after §1.4: "4-6 seconds to see the map feels like
it's too long… 2 seconds feels right as a user. I know that will be hard to
do." And, an hour later, the constraint that decides the shape of the answer:
"That trail-line file might become massive. Plan for us adding 100X the miles
of trails."

**#1564 — Research: the map on screen, trail line included, within two seconds
of opening the app** is the tracking issue. This section is what was measured
on 2026-09-17 and what it implies; nothing below is built.

### 7.1 What the map's worker does between being born and drawing the line

Every figure is a warm launch on the §1.4 laptop profile at 1× CPU, the map
born at 580–660 ms in every run, on an instrumented build that records each
source's `sourcedata` (the instrumentation is not in the tree). The basemap
and terrain hosts were switched off for the runs marked *no tiles*, so what is
left is the app's own sources; one run per row, so read differences of a few
hundred milliseconds as noise and differences of seconds as findings.

| the `trails` source as | network-overview sketch | basemap tiles | pins loaded | sketch loaded | **line loaded** |
|---|---|---|---:|---:|---:|
| GeoJSON (today) | present | through the sandbox proxy | 1,811 ms | 5,411 ms | **6,155 ms** |
| GeoJSON | present | no tiles | 2,040 ms | 5,685 ms | **6,488 ms** |
| vector tiles, cut by the pipeline | present | no tiles, 1 worker | 1,982 ms | 4,648 ms | **5,333 ms** |
| vector tiles | present | no tiles, 2 workers | 2,079 ms | 5,105 ms | **5,425 ms** |
| vector tiles | **removed** | no tiles | 1,797 ms | — | **2,487 ms** |
| GeoJSON | **removed** | no tiles | 1,693 ms | — | **3,142 ms** |

Three things the table settles, each measured rather than reasoned:

- **The line is late because of what is in front of it, not because of what it
  is.** Its source loads last in every configuration — after the 28,913
  waypoints (`pois`, a GeoJSON source of every pin, ~1.2 s of worker time from
  the map's birth) and after the network-overview sketch. Removing the sketch
  alone moves the line from 6.5 s to 3.1 s as GeoJSON and from 5.3 s to 2.5 s
  as tiles.
- **The network-overview sketch costs 3–3.5 s of the worker on every launch.**
  It is `network_overview.geojson`, 12,238,110 bytes in release 2026-09-16-4 —
  every other organization's trail lines simplified for the corridor zoom,
  handed to a GeoJSON source and cut into tiles by geojson-vt on the phone,
  every time the map is built. The same lines already exist as published
  tiles: `nearby_trails.pmtiles` (155 MB) is cut into cells at z9–14 and a
  `nearby_trails_context.pmtiles` at z≤8 by `cut_cells.py`, and the map's
  `nearby-trails` vector source reads the cells by byte range (#1257). The
  sketch duplicates the context archive's zooms as a whole file.
- **A second MapLibre worker does not help** — 5,333 → 5,425 ms with the same
  sources. The order is not a one-worker accident; it is the order the sources
  are attached and the size of what each has to cut.

Two more, from the same runs: the main thread is not the bottleneck here
(sampled at 73–75 % idle over the 20 s watched, with `poiCrowding.ts`,
`legendContents.ts` and the archive sweep the largest of the app's own
frames at 100 ms or less); and at 4× CPU the same launch had not loaded the
line by 10 s as GeoJSON and loaded it at 12,992 ms as tiles with the sketch
present — the phone's number is the laptop's times three to four.

The pre-tiled line for these runs was cut from `trails.geojson` (11,540,417
bytes, 1,657 features, 249,038 vertices) with the same DuckDB / GDAL PMTiles
call `export_nearby_trails.write_tiles` uses, z5–z14, in 2.5 s: 3,684,871
bytes. It was served over HTTP by range through MapLibre's standard `pmtiles`
protocol for the experiment; the app's own `pmtiles://` scheme reads IndexedDB
archives and would carry it the same way the corridor sheet is carried.

### 7.2 Why "100× the miles" decides the shape

At a hundred times the miles, `trails.geojson` is on the order of a gigabyte
and `network_overview.geojson` the same, and a GeoJSON source is read whole
into the worker and cut into tiles there — the cost above scales with the
total, not with the view. Tiles read by range scale with what is on screen:
the worker's cost per launch is the tiles in the viewport, whatever the
archive holds behind them. The network's lines already made that move under
#1257 after the whole file crashed every phone at 229 MB (#1254); the two
whole-file sources still on the launch — the sketch and the A.T.'s own line —
are the same design a hundredfold away from the same failure, and the pins
(one GeoJSON of every waypoint, growing with the miles) are the third.

So the plan is not "make the GeoJSON faster". It is that nothing the map draws
at launch may be a whole file whose size follows the miles.

### 7.3 The plan, in the order the measurements rank it

1. **Draw the corridor-view sketch from the context archive's tiles and stop
   shipping `network_overview.geojson` to the launch.** The z≤8 tiles exist
   (`nearby_trails_context.pmtiles`), the `network://` scheme already reads the
   family by range, and the sketch's only job is those zooms. **Measured**
   saving: 3–3.5 s of worker time at 1×, first on the line's critical path;
   at 4×, reasoned ×3–4. The sketch's other consumer, whatever the shell reads
   from `lib/nearbyTrailData.ts`, is the part to check before deleting the
   artifact rather than merely not drawing it.
2. **Publish the A.T. line as tiles too** (`trails.pmtiles`, cut in the same
   step that writes `trails.geojson`), and point the map's `trails` source at
   them — the GeoJSON stays for the index build, the mile axis and the
   elevation profile until those readers move to cells, which is #1257's
   pattern and a separate piece of work. **Measured** saving: 0.65 s at 1×
   (3,142 → 2,487 ms with the sketch gone), and the property that the line's
   cost stops following the miles. One thing to prove before shipping: that a
   tile cut at z5–z6 never drops a short segment of the trail — the #160
   failure in a new coat — which is a check of the cut against the merged
   chains, not a hope.
3. **Attach the line first.** MapView attaches trail data before the pins and
   the sketch, but the worker finishes them in the order their bytes arrive;
   with the sketch gone and the line tiled, the pins (~1.2 s) are what stands
   between the map's birth and the line. Put the line's source ahead of the
   waypoints in the style and hand the pins over after the line's first tiles
   are in — `@unvalidated`, what settles it is the same instrumented run.
4. **The pins as tiles, when the miles grow.** 28,913 waypoints as one GeoJSON
   source is 1.2 s of worker today and grows with the miles the same way; a
   point PMTiles with rank and type baked in, cut by the pipeline, is the
   same move as 1 and 2. Not first, because today it is the smallest of the
   three and the crowding logic (`map/poiCrowding.ts`) reads the whole list on
   the main thread — that reader moves with it.
5. **Not a lever, measured:** a second worker (above); batching the archive
   sweep (`getMany` against 2,415 separate reads in a real Chromium: 33–100 ms
   against 130–213 ms at 1×, 121–207 against 358–423 ms at 4× — a tenth of a
   second on a laptop, a third on a phone, and the restart when the package
   set grows, 2,480 → 4,103 reads on one run in §1.4, is worth more than the
   batching).

### 7.4 What two seconds would then be

Warm, on the laptop profile: the map born at 0.6 s (§1.4), the line's tiles
for the corridor view a few hundred milliseconds behind it, the basemap from
the downloaded sheet or the cells where the phone holds them and from the
network where it does not. On the phone's Map tab the same chain arrives on a
tap, on a core three to four times slower, which is why 1–3 are ordered by
worker seconds rather than by bytes. Cold launches keep the §1.4 shape; the
precache makes them the exception.

**Unvalidated, and named so nobody reads the table above as a phone's:** every
run here is one run on a server core with software WebGL and a sandbox's tile
network. What would settle the plan's arithmetic is `ourhike:map` and
`ourhike:map-drawn` read off the maintainer's laptop and phone from Settings →
About build, before and after item 1.
