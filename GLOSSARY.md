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
agree on". Two entries carry it today: `seam` and `gate`.

---

## The dangerous ones — same word, different things

These are the entries that made this file worth writing. Each of these words is used for
several unrelated things, and **no reader can tell which from context**. Using one of
these bare is the single most reliable way to lose somebody.

**Say which one you mean on first use, every time.** It costs a few words and it is not
optional for anything on this list.

### seam

**Four meanings, all live.**

1. **A boundary between two adjacent map cells** — `map/basemap.ts` carries
   `seamMarginKm`, and a tile near a seam may be served by more than one cell.
2. **The zoom threshold** where the map changes what it draws — `App.tsx` writes "above
   the seam" and "past the seam (below it a tap cannot land within 150 ft of anything)".
3. **A test injection point** — "the engine seam passes the real `addProtocol` in"
   (`map/basemap.ts`), "mocked at the pmtiles seam" (`map/basemap.test.ts`), and
   `/** Test seam only */`.
4. **The client/backend API boundary** — V2_PLAN.md's **#502 — The API seam checks field
   presence and nullability, but not that a type narrowed**.

A fifth is nearby: `shard-seam-spike.yml`, which is sense 1 applied to build shards.

`@unvalidated` — that these are four separate senses rather than one idea applied four
times is my reading of the usages above. What would settle it: the maintainer saying
whether "seam" is meant as a single concept (*a boundary where two things meet and
something can leak*) or four coincidences. If it is one concept, this entry becomes one
sentence and the rule stays the same — say which boundary.

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

### gate

1. **A CI check that blocks a merge** — BRANCHING.md's "path gates".
2. **An environment approval a human presses** — RELEASING.md's gate table, the
   `production` environment's reviewers.
3. **A data filter that decides what may ship at all** — V2_PLAN.md: "It gates whether
   opentrail-derived data may ship".

`@unvalidated` — sense 3 may just be ordinary English rather than a term. What would
settle it: whether anybody writes "the gate" bare and means a data filter.

---

## The ones with a single meaning

Safe to use bare. Each is a real thing with a findable definition.

### bucket

**The R2 bucket hikers download map data from.** [pipeline/R2_LAYOUT.md](pipeline/R2_LAYOUT.md)
owns where an artifact goes in it and what it may be called; `lib/r2_keys.py` enforces
that. Every object in it is served publicly and its key is the URL path.

"The bucket describes the code before your change" — the state CLAUDE.md's *A pipeline
change is not finished at the merge* is about — means the published artifacts are stale,
not that anything is broken.

### corridor

**The 30-mile buffer polygon around the A.T.** that `export_poi.py` and
`export_trails.py` clip their output against — [pipeline/lib/corridor.py](pipeline/lib/corridor.py).

Since #1311 it is the A.T.'s polygon alone: another organization's trail network sits
beside it as an indexed line table rather than being unioned into it, because the
nationwide Forest Service layer took the widened version from 14.66 s to 20:07 per
build (measured, run #88 of `publish-vector-data.yml`, 2026-09-08). `keep_within_corridor`
asks both.

### cell

**A 1°×1° graticule square — the unit of offline coverage**, anchored on whole degrees
and never on an archive's bounding box, so two organizations' sheets over the same
ground produce the *same* cells. The maintainer's #552 decision, 2026-08-25, replacing
the trail-derived stretch cut of #556. It is what gets built, versioned, downloaded and
resumed. See [pipeline/cut_cells.py](pipeline/cut_cells.py).

**A hiker never sees a cell.** They tap a **piece**.

### piece

**A named set of cells a hiker downloads as one thing** — the hiker-facing unit that
cells sit underneath. See `features/OFFLINE_COVERAGE.md`.

### outbox

**The offline queue every write goes into**, with its authored timestamp, to sync later
— [client/src/lib/outbox.ts](client/src/lib/outbox.ts). On this trail that is the normal
path rather than the edge case: most reports are written with no signal at all. A report
written Monday and flushed Thursday still reads as Monday.

### anchor

**The place a report names** — a mile, a named place, or "here". The window takes a
finished phrase (`at mi 628.4`, or `here`) rather than composing one, because "here" is
an adverb and the other forms are nouns. An anchor needs a lat and a lon. See
`client/src/reporting/ReportWindow.tsx`.

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
