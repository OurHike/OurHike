# Glossary

**The words this repository uses as if everybody already knew them.**

[CLAUDE.md](CLAUDE.md)'s *Name the thing, then say the thing about it* has a check
called the **"the" test**: go through every `the X` you write, and ask whether X was
introduced in the previous sentence or is the literal name of something here. This file
is the third answer. A word listed below is shared vocabulary and may be used bare; a
word that is not is a private referent and gets introduced on first use.

**Every definition here is read off the code, not handed down.** Nobody wrote these
words down as terms — they accumulated. So each entry carries where it is used, and the
ones that are a best reading rather than a settled meaning are tagged `@unvalidated`
with what would settle them. The tag means the same thing it means in the code: picked,
and nobody has checked it.

`grep -rn '@unvalidated' GLOSSARY.md` answers "which of our own words do we not actually
agree on". **One entry carries it: `seam`**, for the 3 km margin it cites, which
`pipeline/cut_cells.py` tags at the source as picked rather than found.

Two other questions were open on the first draft — whether `seam` is one idea or four,
and whether `gate`'s third sense is a term at all — and both were settled by going back
to the code rather than by anybody deciding. Each says what settled it, so the next
reader can disagree with the step rather than the conclusion.

---

## The dangerous ones — same word, different things

These are the entries that made this file worth writing. Each of these words is used for
several unrelated things, and **no reader can tell which from context**. Using one of
these bare is the single most reliable way to lose somebody.

**Say which one you mean on first use, every time.** It costs a few words and it is not
optional for anything on this list.

### seam

**Four meanings, all live.**

1. **A boundary between two adjacent map cells** — `lib/coverageCells.ts` declares
   `seamMarginKm` and the `SeamEdge` type, and a tile near a seam may be served by more
   than one cell.
2. **The zoom threshold** where the map changes what it draws — `App.tsx` writes "above
   the seam" and "past the seam (below it a tap cannot land within 150 ft of anything)".
3. **A test injection point** — "the engine seam passes the real `addProtocol` in"
   (`map/basemap.ts`), "mocked at the pmtiles seam" (`map/basemap.test.ts`), and
   `/** Test seam only */`.
4. **The client/backend API boundary** — V2_PLAN.md's **#502 — The API seam checks field
   presence and nullability, but not that a type narrowed**.

A fifth is nearby: `shard-seam-spike.yml`, which is sense 1 applied to build shards.

**Reasoned: it is one idea on four axes, not four coincidences.** The tailor's metaphor
is used at its root in `reporting/categories.ts` — a campsite escalating into something
called "Shelter repair" "was the seam showing", a join between two internal pieces
becoming visible from outside. Every sense above is that: cells joined along a border,
two rendering regimes joined at a zoom, a dependency joined to its replacement, a client
joined to a backend. Sense 3 is not even ours — a *test seam* is the established term
for a place you can change behaviour without editing there.

**That resolves the origin and changes nothing about the rule.** Knowing the metaphor
tells a reader the shape of the thing and not which of the four it is, which is the only
question they actually have. Name the axis.

Each sense has real code behind it, which is the fastest way to tell them apart. Sense 1
is `lib/coverageCells.ts`'s `SeamEdge` and `seamMarginKm`, drawn by
`map/coverageLayers.ts`'s `COVERAGE_SEAM_LAYER_ID`; every edge within the margin is filed
in both cells (`pipeline/cut_trail_graph.py`), so the cell whose own bounds hold a point
answers for it. Sense 2 has a constant: `App.tsx`'s `belowSeam` is
`camera.zoom < POI_PIN_MIN_ZOOM`, which is 9 (`map/poiLayers.ts`). Below it the map is a
corridor view and above it the hiker is navigating. **It is 7.5 since #1585 — A hundred-mile
resupply carry fits a phone at z8, and the map draws no waypoint until z9**, which moved it to
the zoom a five-day resupply section fits a phone. Two things that used to be the same number
are now deliberately not: `CORRIDOR_MAX_ZOOM` (`map/corridorLayers.ts`), where the corridor
sketch hands the other organizations' trails to the tiled ones, and `LOCATE_MIN_ZOOM`, where a
*where am I* tap lands. Both stayed at 9. Say which one you mean — "the seam" is the waypoints'.

**The seam is not a filter, and never has been.** It decides where waypoints start, never which
ones: every category the hiker has switched on is drawn at every zoom, as a pin where it fits
and as a dot where it does not.

`@unvalidated` — **the margin is 3 km and that number is picked, not found.**
`pipeline/cut_cells.py` says so at the source: "`SEAM_MARGIN_KM = 3.0` is picked, not
found. What would settle it: how far past a cell boundary a hiker actually pans and walks
once #558 ships and there is behaviour to measure, plus the duplication share this module
[costs]." Quoting 3 km here without that tag would be this file doing exactly what
CLAUDE.md's *Never let a display outrun its source* forbids.

### shelf

1. **Where a generated file belongs** — `.github/tests/test_no_committed_data.py`: "The
   pipeline already has the right shelf for all of it: `pipeline/data/`". Also
   CLAUDE.md's *A build script's output has a home*.
2. **The list of suggested hikes the client shows** — `pipeline/route_hikefinder.py`
   ("the hike does not reach the shelf"), `App.tsx`'s "suggested-hikes shelf", and the
   day room's "shelf row" in `client/e2e/dayHikeCard.spec.ts`.

Sense 2 is the common one in client code and sense 1 is the common one in pipeline code,
which is exactly why a sentence spanning both is unreadable.

### fix

1. **A GPS position.** `fixMile`, "a build with no GPS fix", "a fix that did not land on
   the trail". This is the sense that appears in hiker-facing code.
2. **A code change that repairs something.** `lib/dataRefresh.ts`: "a prompt silenced
   forever is a fix nobody is offered".

Both appear in `client/src/lib/`. Prefer "a GPS fix" for sense 1 wherever a code change
is anywhere in the same paragraph.

### leg

1. **One stage of a longer run** — "the elevation leg" of a build, "three saves a leg"
   in `.github/tests/test_cache_keys_are_content_addressed.py`.
2. **One hop in a network path** — LAUNCH_CHECKLIST.md's "the Cloudflare-to-GitHub leg
   is unencrypted".

### settle

1. **To resolve an open question** — "what would settle them" throughout the evidence
   rule; `backend/app/schemas/common.py`'s "real hikers would settle where the ceiling
   belongs".
2. **To wait for state to stop changing** — `--settle-seconds` in
   `.github/tests/test_pages_preview_sweep.py`.

Sense 1 is the one CLAUDE.md's evidence grades mean, and it is load-bearing there.

### the camera

1. **The map viewport** — `App.tsx`: "under the camera once it is past the seam", "where
   the camera was left, so a rebuilt map opens where the hiker left it"; there is a whole
   module for it, `lib/cameraMemory.ts`. `lib/archiveCoverage.ts` asks whether the archive
   "has tiles to draw at this camera zoom".
2. **The preview screenshot rig** — `pr-preview.yml` photographing every recipe a pull
   request adds or changes, throughout
   [`.claude/skills/pr-screenshot/SKILL.md`](.claude/skills/pr-screenshot/SKILL.md)
   ("point the camera at the change").

This one was found by writing this file: the commit subject `Point the camera at the
split` and the code comment `under the camera` are different cameras, and nothing but
the surrounding file says which.

### bucket

1. **The R2 bucket** hikers download map data from — [pipeline/R2_LAYOUT.md](pipeline/R2_LAYOUT.md)
   owns where an artifact goes in it and what it may be called, `lib/r2_keys.py` enforces
   that, and every object is served publicly with its key as the URL path. "The bucket
   describes the code before your change" (CLAUDE.md's *A pipeline change is not finished
   at the merge*) means the published artifacts are stale, not that anything is broken.
   `App.tsx`'s "forgives every cell the bucket refused" is this one.
2. **A spatial lookup grid square** — `lib/trailPosition.ts`: "LOOKUPS ARE BUCKETED IN
   TWO DIMENSIONS", cutting 3,154 haversines per waypoint to 565. CLAUDE.md's own
   evidence section calls this "the bucket search".
3. **A group a hiker puts their own trips in** — `App.tsx`: "The hiker's own buckets
   (#800). A trip stays in every other group it is in".

Senses 1 and 2 are the collision that matters: a sentence about publishing and a sentence
about an in-memory index read identically.

### anchor

1. **Where a report lands and how the header says so** — `ReportWindowAnchor` in
   `reporting/ReportWindow.tsx`. `label` and `phrase` are required; `lat`, `lon`, `mile`
   and `poiId` are all optional, because a build with no GPS fix anchors to "here".
2. **The place a report is about** — `chrome/FieldNoteSection.tsx`'s `ReportAnchor`.
   Sense 1's own docstring says these are **not the same thing**: "that one is the place
   a report is ABOUT, and this one is that plus the words the header prints."
3. **A POI type that can hold a site** — `pipeline/lib/poi_sites.py`'s
   `ANCHOR_TYPES = ("shelter", "campsite")`, and `map/poiIcons.ts`'s "a viewpoint never
   anchors a site".
4. **A rendering attachment point** — a layer's lower zoom anchor, and MapLibre's own
   `text-anchor`.

The repository went to the trouble of naming senses 1 and 2 apart in code and then used
one word for both in prose.

### cell

1. **A 1°×1° graticule square — the unit of offline coverage**, anchored on whole degrees
   and never on an archive's bounding box, so two organizations' sheets over the same
   ground produce the *same* cells. The maintainer's #552 decision, 2026-08-25, replacing
   the trail-derived stretch cut of #556. What gets built, versioned, downloaded and
   resumed: [pipeline/cut_cells.py](pipeline/cut_cells.py), `lib/coverageCells.ts`.
2. **A square of an in-memory lat/lon lookup grid** — `lib/trailPosition.ts`'s "Cells of
   latitude AND longitude". Not 1°, not anchored on whole degrees, never built or
   downloaded. It is sense 2 of **bucket** wearing the other word.

On sense 1, `cut_cells.py` says "a hiker never sees one, they tap a named PIECE that is a
set of cells". That is true of the *unit* and not of the *boundary*: `map/coverageLayers.ts`
draws the seam between cells as a dashed line labelled "edge of what you downloaded",
because a 1° cut crossing the map as a dead-straight meridian "reads as a rendering fault
unless it is named" (maintainer's call, 2026-08-28). So a hiker never picks a cell and
does see where one ends.

### gate

1. **A CI check that blocks a merge** — BRANCHING.md's "path gates".
2. **An environment approval a human presses** — RELEASING.md's gate table, the
   `production` environment's reviewers.
3. **A data filter that decides what may ship at all** — V2_PLAN.md: "It gates whether
   opentrail-derived data may ship".

**Settled: sense 3 is a real noun here, not just the verb.** V2_PLAN.md §72 writes
"1,705 water features reaching the map through **a gate** that is only 'within thirty
miles of the trail'" — a bare noun, and a data filter. The CI sense is a bare noun too:
"a gate that cannot go red is not a gate" (V2_PLAN.md §424). So all three senses are
live and a reader has to be told which.

---

## The ones with a single meaning

Safe to use bare. Each is a real thing with a findable definition.

### corridor

**The 30-mile buffer polygon around the A.T.** that `export_poi.py` and
`export_trails.py` clip their output against — [pipeline/lib/corridor.py](pipeline/lib/corridor.py).

Since #1311 it is the A.T.'s polygon alone: another organization's trail network sits
beside it as an indexed line table rather than being unioned into it, because the
nationwide Forest Service layer took the widened version's unify-and-clip from 14.66 s to
20:07 (measured, run #88 of `publish-vector-data.yml`, 2026-09-08) — **and that step is
paid twice per build**, once in `reconcile_poi_identity.py` and once in `export_poi.py`,
so roughly forty minutes a build rather than twenty. `keep_within_corridor` asks both.

### piece

**A named set of cells a hiker downloads as one thing** — the hiker-facing unit that
cells sit underneath. See `features/OFFLINE_COVERAGE.md`.

### outbox

**The offline queue every write goes into**, with its authored timestamp, to sync later
— [client/src/lib/outbox.ts](client/src/lib/outbox.ts). On this trail that is the normal
path rather than the edge case: most reports are written with no signal at all. A report
written Monday and flushed Thursday still reads as Monday.

### stretch

**A length of trail between two points**, as a hiker would describe it — "a closed
stretch of trail", "the stretch you're walking". Not a unit of anything since #552 made
the **cell** the offline unit.

### room

**A screen or sheet, in the flow tests' vocabulary** — "the day room", "the Plan room",
"the hike room" in `client/e2e/`. A room has an *entrance*, *states* and an *exit*, which
is how those test names are structured. See `features/FLOW_TESTING.md`.

### recipe, shot

**A recipe** is a small Playwright driver under `client/preview-shots/`, each reaching one
screen. **A shot** is the picture it takes. Recipes are committed; pixels never are. See
[`.claude/skills/pr-screenshot/SKILL.md`](.claude/skills/pr-screenshot/SKILL.md).

For **the camera**, which is not one thing, see the dangerous list above.

### mock

**A rendered page of a screen as it would be**, drawn in the design system's tokens and
sent to the maintainer's side panel before a poll about it — the default picture since
**#1566 — A session's questions to the maintainer carry no wireframe or screenshot, so the
plan cannot be seen from the words**. Not a shot: nothing in a mock was photographed, and
its caption says so. See
[`.claude/skills/visual-poll/SKILL.md`](.claude/skills/visual-poll/SKILL.md).

### UA

**The environment `main` deploys to** — the one that keeps `main` testable, between dev
and production. A `ua` dispatch carries no approval gate (#1330); production is a
promotion and belongs to the release train. See [RELEASING.md](RELEASING.md).

### the train

**The release train** — the order the release jobs run in, written once as
[`.claude/skills/release-train/SKILL.md`](.claude/skills/release-train/SKILL.md).

---

## Not in here on purpose

**Ordinary domain words that mean what they say**: shelter, blaze, thru-hiker, blowdown,
resupply, ford, trailhead. A hiker would recognise all of them and so would a reader.

**Words whose definition is one click away**: POI, DEM, pmtiles, R2, dbt. These are
findable; the entries above are not.

**Anything invented for one file.** If a word appears once, it does not need a glossary
entry — it needs a sentence introducing it where it appears.
