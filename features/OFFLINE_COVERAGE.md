# OurHike — Offline Coverage (Feature Design v1)

Companion to [MAP_OPTIONS.md](MAP_OPTIONS.md) §1 and §5 (whose "outside downloaded area"
banner this finally gives a footprint to), [NEARBY_TRAILS.md](NEARBY_TRAILS.md) §9 (whose
offline requirement this answers), [../WIREFRAMES.md](../WIREFRAMES.md) §4 and Known
Deviations #1 (which this reopens, and which is amended in the same pull request),
[HIKE_PLANNING.md](HIKE_PLANNING.md) (the planning moment this hangs a prompt on) and
[../pipeline/DATA_RELEASES.md](../pipeline/DATA_RELEASES.md) (the per-artifact versioning
this must not fork).

Answers [#552 — Decide the unit of offline coverage, and write it
down](https://github.com/OurHike/OurHike/issues/552), inside
[#551](https://github.com/OurHike/OurHike/issues/551)'s offline-coverage program.

**Status, 2026-08-28: decided, and the pipeline half built.** The unit is the maintainer's
call of 2026-08-25, recorded on #552. `pipeline/cut_cells.py` cuts it (#1175, landed with
this doc), and `publish.py` publishes what it cuts. **Nothing hiker-facing exists yet**:
#557 (drawing from several units, and saying where they end) and #558 (choosing a piece)
are both open, and until they land no cell reaches a phone.

Measurements below are dated. Everything read off the published bucket was fetched
2026-08-28 against release `2026-08-28`, whose manifest carries a `size_bytes` per
artifact since [#505](https://github.com/OurHike/OurHike/issues/505) — so these are
weighed figures, not advertised ones.

---

## The decision

**Candidate 1 — region units, at 1°×1° — with a named layer on top of it.** The
maintainer, 2026-08-25, on #552:

> This needs to be able to be flexible enough to handle multiple orgs of data. Lets do
> 1°×1° cells, but divided into understandable units within an org, and within a state for
> instance like the AT where the trail is big.

Two layers, and keeping them apart is the whole of it:

| | what it is | who sees it |
| --- | --- | --- |
| **the cell** | 1°×1°, the unit that is built, versioned, downloaded and resumed | nobody |
| **the piece** | a named set of cells, scoped by org and — for something as long as the A.T. — by state | the hiker chooses this |

A hiker taps *"Virginia"* or *"Harriman"*; the app fetches the cells underneath. The grid
is the engineering answer, the naming is the human one, and neither has to compromise for
the other.

### Decisions taken 2026-08-28 (maintainer, in session, reviewing the mock-ups)

Four questions the unit decision left to the screens, answered while drawing them. Each
shapes #557 or #558 rather than the pipeline.

- **Choosing a piece is a named list, with a map beside it.** The list is the control —
  grouped by org, offline-safe, reachable by a screen reader — and a small map previews
  whatever is selected. Not a map you tap regions on: that needs the map alive inside the
  download window and fails one-handed in sun.
- **Detail is one global level, with a per-piece override.** You pick Standard once and
  every piece arrives at Standard; a hiker who wants Fine on the hundred miles they are
  walking can say so per piece. The override is what makes §7's sharpness seam possible,
  which is why it is stated here rather than left to the UI.
- **A seam is a dashed boundary plus a banner on crossing** — quiet until it matters. Not
  permanently-muted ground beyond the edge, which reads as a rendering fault.
- **The prompt belongs in planning.** A plan already names the ground it crosses, so the
  Plan tab offers its pieces with a one-tap "take these" and says what *not* taking them
  costs. This is the maintainer's 2026-08-18 rider on #552, given a screen.

## 1. Why the other two lose

**Candidate 2 — trail-derived stretches — loses because it cannot describe two orgs' trails
in one scheme.** A 30-mile piece of the A.T. and a Harriman loop are not the same kind of
object, and [#768](https://github.com/OurHike/OurHike/issues/768) has already put both on
the same map. The scheme would need a mile axis per trail; Harriman's network has no single
mile axis to have (`#928` is the same discovery made from the planner's side). It also
re-earns WIREFRAMES.md §4's objection unless the choosing is solved, which is the objection
that retired the per-section list in the first place.

This is not a hypothetical loss. **Candidate 2 was chosen on 2026-08-18, built, and
published**, before the second-org problem was weighed — see §3.

**Candidate 3 — on-demand tile caching — loses where this app cannot afford to lose.** What
you never looked at in town is missing on the ridge, and the failure is silent and arrives
at the worst moment. It earns one sentence rather than a section, and this is it. Note that
`nearbyTrailData.ts`'s stored copy ([#1082](https://github.com/OurHike/OurHike/issues/1082))
is *not* this candidate arriving by the back door: it keeps the last verified copy of a
**whole** artifact, which is a superset of any boundary, and it appears in no download UI
and answers no question about what is on the phone. NEARBY_TRAILS.md §9 is explicit on the
distinction.

## 2. The grid already exists, and it is this one

#552 asked whether `build_cells_manifest.py`'s grid is "the right grid to reuse or a
coincidence of a different job". **It is the same grid, and it was deliberately factored
out to be shared**: `pipeline/lib/corridor_grid.py`, `CELL_DEGREES = 1.0`, so that
`spike_raster_mosaic.py` and `fetch_and_mosaic_cell.py` "can never silently compute
different cell boundaries or quad-to-cell assignments, which would otherwise be an easy way
to introduce a coverage gap that only surfaces downstream."

It exists for the reason offline coverage wants cells: the corridor is a thin winding band
inside a huge bounding rectangle. **The A.T. corridor is 51 cells**, and that number is
already load-bearing — `build_cells_manifest.py` hard-fails a cell with zero quads,
validated against the real 51-cell manifest.

So the seam logic will be written against boundaries CI already fans out over, and one
class of bug — two modules disagreeing about where a cell ends — is closed before it opens.

## 3. What is already built, and built to the superseded answer

**Measured 2026-08-28, production release `2026-08-28`:**

| | |
| --- | --- |
| Stretch tile archives published | **88** (44 `at_basemap_stretch_*`, 44 `dem_stretch_*`) |
| Their total weight | **942.9 MB** |
| The sheet they partition | 809.5 MB — Fine (`at_basemap_package` 533.9 + `dem` 275.6) |
| So the cut costs | **116%** of the source — the 16% is `SEAM_MARGIN_MILES` overlap |
| Shared context artifacts | 35.6 MB (`at_basemap_context` 6.3 + `dem_context` 29.4) |
| Client code that reads any of it | **0** |

`pipeline/cut_stretches.py` closed
[#556](https://github.com/OurHike/OurHike/issues/556) on 2026-08-18, implementing the
decision taken that morning. The decision moved on 2026-08-25 and the pipeline was not
told, so it went on cutting stretches for three days. **#1175 replaced it with
`cut_cells.py` and removed the module**; `publish.py` now names `CELL_FAMILIES`.

**Most of that module survived the change of unit, and this is the reason re-cutting was
cheaper than it looked.** What ported:

- **The shared context artifact.** The context zoom stays 9: everything through z9 goes
  to *one* sibling download per sheet instead of riding in every unit. This is §6's answer,
  already written and already measured.
- **Tile routing that handles a straddling tile.** Against a lat/lon grid this got
  *simpler* rather than merely surviving: five-point sampling existed because "which miles
  does this tile serve" is a question about a curve, and cell membership is an exact
  rectangle overlap. No sampling, so no false negatives at all.
- **The seam margin.** Widening a unit's bounds before routing, so a unit's map does not end
  at the exact perpendicular of its boundary. §4 is what it is for.

What does not port is the mile-axis machinery — `calibrated_trail_axis`,
`miles_of_merc_points`, `stretch_span`. That is the part that could not describe a second
org, and it is the part being deleted.

## 4. A wrong answer must not cost somebody map where they are walking

This is #552's non-negotiable and the sentence that retired the per-section list. Three
mechanisms hold it, and none of them is "choose carefully":

1. **The margin.** A unit carries beyond its own boundary, so the edge of the data is never
   the edge of the choice. The stretch cut set this at 2 miles; `cut_cells.py` states it
   as 3 km instead, because a degree of longitude is 111 km at the equator and about 77 km
   in Maine, so a degree margin promises different amounts of ground at each end of one
   trail. `@unvalidated` either way — both numbers were picked, not found. What would
   settle it: how far past a boundary a hiker actually pans, once #558 ships and there is
   behaviour to measure.
2. **The choosing is derived, not enumerated.** `lib/plannedHike.ts` already stores start
   and end, and `plannedDirection()` falls out of the pair — so "the ground I am walking" is
   answerable today, without a route builder and without anyone picking rows off a list.
   The planning surface is where this prompt belongs (the maintainer's 2026-08-18 rider on
   #552: prompt *before leaving*, during planning).
3. **The default is not a choice at all.** §5.

**Neither direction of error is safe here, and that is worth stating plainly** because it
is unlike `wrongWay.ts`. Over-cutting strands somebody without a map; over-shipping puts
the app back to asking for a gigabyte, which is the harm #551 exists to end. There is no
conservative direction to round toward — only a margin wide enough that the question stops
being sharp.

## 5. The whole trail stays one tap

One tap still means the trail: **the A.T. is the union of its 51 cells**, and that stays the
default a first-run hiker gets by pressing the obvious button. Partial coverage is the
*option*, never the thing somebody has to understand before they can leave.

Stated rather than implied because it is the sentence protecting everything WIREFRAMES.md
Known Deviations #1 was right about. The per-section list failed because it made a hiker get
a mile-by-mile choice right, and a wrong answer cost them map. A named piece under a
whole-trail default fails neither way: the default asks nothing, and the piece is a region
with a name rather than a mile range to compute.

## 6. Context zooms, which is where this decision could quietly defeat itself

`extract_package.py`'s `DEFAULT_CONTEXT_ZOOM = 9` ships every source tile through z9 in each
package. [#193](https://github.com/OurHike/OurHike/issues/193) measured those at 6.3 MB per
package at corridor scale, **duplicated by construction**.

**At 51 cells, context carried per cell would be ~321 MB of the same bytes** — reasoned from
that 6.3 MB figure — which is 40% of the whole sheet, spent on duplication, to solve a
problem about size. That would defeat the entire point of splitting.

So context is **one shared artifact per sheet, fetched once**, and it is not optional: it is
what a hiker holding one piece sees when they zoom out past it. Measured on the current cut,
that costs 35.6 MB for both sheets together — 6.3 MB of basemap and 29.4 MB of DEM.

This also hands the DEM the context mechanism #552 correctly notes it never had
(`export_dem.py` walks the region at every zoom). The two sheets stop needing different
answers.

**What a hiker with cells and no context sees** must be the §7 answer — *unknown*, not
absence — and the context artifact should be fetched with the first piece rather than
offered as a separate decision. It is not a thing to choose; it is the thing that makes a
piece legible.

## 7. Seams: one module answers "is here covered"

`client/src/lib/archiveCoverage.ts` is that module, and it answers half the question today.
`archiveCoversZoom()` and `openingZoomFloor()` handle the **vertical** edge — the zoom range
an archive declares — and the file names the horizontal one as unaddressed in its own
header: *"Panning off the 30-mile strip does the same thing horizontally. That one is not
addressed here: it needs the archive's real footprint read out of the header."*

**The footprint is now available and the answer belongs in this same file**, so that the
map, the status strip and the download window cannot disagree. A cell's bounds are computable
from its own identity — that is what a lat/lon grid buys — so "is here covered" is a point-in-
set test over the cells on the phone, not a geometry read out of every archive.

Two rules govern what it says, and the first is inherited rather than invented:

- **Unknown coverage is rendered as unknown, never as absence** (MAP_OPTIONS.md §1, the rule
  #216 was built on). A cell set not yet read, or unreadable, must not produce a claim that
  the download falls short.
- **The seam is a straight line, and the UI should not pretend otherwise.** 1° cells make
  boundaries meridians and parallels. A hiker crossing one sees a dead-straight edge, which
  looks like a rendering fault unless it is named. The mock-ups draw it dashed and labelled
  ("edge of what you downloaded") for exactly this reason.

**What stops at a seam, and what does not**, is §8.

## 8. Does a piece carry its POIs? — the constraint the screens turned up

Two docs disagree, and neither noticed:

- **WIREFRAMES.md §4**: the centerline, spurs, POIs and elevation profile "are downloaded by
  default wherever they are missing — so they never appear in this window as something to
  choose." On that reading a piece is **the basemap and terrain**, and a hiker past the seam
  still has the trail line and its water, drawn on blank paper.
- **NEARBY_TRAILS.md §9**: "a download named 'Harriman' contains every shipped trail and
  every safety POI inside its boundary." On that reading a piece carries them.

**Both held while there was one org and the trail's own data was 12.3 MB. Neither survives
five orgs statewide**: `nearby_trails.geojson` measured 23.5 MB raw / 7.34 MB gzipped at
21,805 features on 2026-08-25, once the maintainer removed the ring around New York City
(#1019).

**The decision this doc takes: safety data is never piece-scoped.** Water, closures,
warnings and the trail lines themselves ship with the trail, wherever the hiker is, and a
seam takes away the *ground* and never the *hazard*. Three reasons:

1. It is the only reading under which a hiker at a junction cannot be surprised. NEARBY_TRAILS
   §9's promise is really a promise about the screen, and honouring it globally honours it
   inside every boundary for free.
2. It matches CLAUDE.md's four ways this app can hurt somebody. A missing basemap tile is an
   inconvenience; a missing closure is one of the four.
3. It is cheap in the only place it is expensive. The 0.7 MB gzipped figure for two parks'
   full trail geometry (#771) says geometry is not the problem; the 23.5 MB is a *parse and
   memory* problem, and the fix for that is a per-region cut of the artifact for **drawing**,
   which is not the same thing as a per-region cut for **coverage**.

So: **pieces scope the sheet; they do not scope safety.** What a seam banner may say is
"the map stops here", never "your water stops here".

**The parse cost is a real follow-up and is not this issue's**, but it must not be lost:
every phone still parses 21,805 features to draw any of them. That wants its own issue
against #557.

## 9. What it costs, and who says so

#552 asks that a unit scheme keep the ±0.6% advertised-size promise per unit. **That
constraint has changed shape since the issue was written, in the direction that helps.**

[#1167](https://github.com/OurHike/OurHike/issues/1167) removed the hand-kept byte figures
from `hikingDetail.ts` — they had already drifted 34.7% — and the client now prices a
download from the manifest (`lib/usePublishedSizes.ts`, `packageSizeBytes`), which carries a
`size_bytes` measured by `publish.py` on upload. `verify_release.py`'s check 18 has nothing
left to weigh, because nothing is advertised that was not measured.

**This scales to N units for free, and it is the reason per-unit pricing is not a problem
to solve.** 138 of the 141 artifacts in today's release already carry a measured
`size_bytes`. A piece's price is the sum over its cells plus the shared context, computed on
the phone from figures the pipeline weighed — never a constant anybody has to keep in step
with a promotion.

What still needs saying, and is UI rather than pipeline: **the price of a piece must be the
price of what is missing**, not of the whole piece, when some of its cells are already held.
The mock-ups show this as a running total that only counts new cells.

## 10. Versioning and resume do not fork

`latest.json` is per-artifact SHA-256 (DATA_RELEASES.md), and N cells is N entries in a
manifest that already holds 141. Nothing about the scheme changes.

**The resume gets better rather than worse, and this is worth naming as a benefit rather
than a risk.** Today a hiker resuming Fine's 533.9 MB basemap is one transfer that can be
corrupted by a publish mid-flight — the splice #197 hardened against, caught by holding the
completed archive to its published hash. A cell is ~16 MB, so a publish landing mid-download
costs one cell rather than a gigabyte, and the hash check that already exists per artifact
now guards a much smaller blast radius.

What the client gains that it does not have: a record of *which cells* it holds, and a
resume that knows which cell it was in the middle of. That is `#557`'s to build, and it is
the same store that answers §7.

## 11. What happens to the 88 artifacts already published

`publish.py`'s manifest merge is additive-only, and its own comment is the constraint: *"a
name once published cannot be renamed by this module — it can only be joined by a sibling
and abandoned."*

So the stretch keys are **abandoned, not reclaimed**. Concretely, and none of it is
automatic:

- `STRETCH_FAMILIES` came out of `publish.py` and the cut came out of `build-basemap.yml`
  and `build-dem.yml` in #1175 — otherwise every future build re-publishes 942.9 MB nothing
  reads. Done, and safe to do first precisely because no client reads either unit: there is
  no hiker-facing state to regress between the last stretch cut and the first cell one.
- The 90 existing keys (88 archives + 2 stretch manifests) stay in the bucket until somebody
  deletes them deliberately. That is a maintainer action against R2, not a pipeline change,
  and it should follow rather than precede the cell cut — an abandoned artifact costs
  storage, and a prematurely deleted one costs a rollback.
- **Nothing hiker-facing regresses when they go**, because nothing hiker-facing reads them.
  That is the one comfortable fact in this section and it is worth stating: the wrong answer
  was caught before it reached a phone.

## Open questions (for the maintainer, gathered)

1. **When do the 88 stretch artifacts get deleted from R2?** Recommendation: after the first
   cell cut publishes and verifies, not before.
2. **How are pieces named, and who names them?** "Virginia" and "Harriman" are obvious;
   the A.T. through a state with 11 trail miles is not, and neither is a piece spanning two
   states. A reviewed table in `reference/` is the shape this repository already uses for
   judgement-encoding joins, and it has a line ceiling for exactly that reason.
3. **Does a piece ever cross an org?** The ground does — Harriman's cells hold A.T. miles.
   The doc assumes a piece belongs to one org and that overlapping pieces share cells
   without duplicating bytes, which is candidate 1's whole structural virtue. Worth
   confirming that is what was meant.
4. **Is 1° right for a dense park?** A cell is ~16 MB averaged over the A.T. corridor, but
   the corridor is a thin band and Harriman is not. `@unvalidated` — nobody has cut a cell
   over a network park and weighed it. `spike_package_overlap.py` makes this a ~7-minute
   dispatch once there is a pair to measure.
