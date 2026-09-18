# Suggested hikes, and finding one

Two surfaces, from the maintainer's design handoff of 2026-09-08 (`Hike_finder_search_design.zip`): a **Suggested hikes** shelf on the Today screen, and a **Find a hike** flow behind it. This is the canonical home for what they are and what they must stay honest about; the work is tracked on **#1284 — Suggested hikes on Today, and a Find-a-hike flow with five honest facets**, and the code is `client/src/lib/suggestedHikes.ts`, `client/src/screens/FindHike.tsx`, `client/src/chrome/FacetSheet.tsx` and the shelf section of `client/src/screens/Today.tsx`.

## What a suggested hike is

**A route somebody published.** A maintaining club, a guidebook author, another OurHike hiker, or an OurHike editorial pick. The app surfaces it and names who wrote it; it never rates, ranks or scores a route itself. Every line on a card is either the publisher's own word or arithmetic over the route's cached figures at the hiker's own pace:

| Line | Where it comes from |
|---|---|
| Name, distance | The publisher, cached at publication — the same provenance caveat as a saved day hike's figures |
| `≈3h` | `lib/pace.ts` over the cached climb, at this hiker's pace. **Only when the record carries a climb.** A route whose climb nobody measured prints `no time — climb unmeasured`, never a time from distance alone |
| Difficulty badge | Quoted from the publisher, or no badge. Never computed |
| Transit line | As published, with the source named. Absent means nothing was published — **not** "no transit exists" — and renders as nothing, not as a struck-through icon |
| Author line | Who published it, in the voice of what kind of publisher they are: `NY-NJ Trail Conference` · `Guidebook route · L. Adkins` · `Published by @slackpack` · `OurHike pick · route by Vernon Trails`. A pick is a label on a route, never a score |
| Photo | A data surface with its own credit and licence (`POI_PHOTOS.md`), or a plain sunken block. Never a bundled stand-in |

The record's shape is `SuggestedHike` in `lib/suggestedHikes.ts`. Its ends are `DayHikeSegment`s — coordinates only, never a `GraphPoint.edgeIndex`, for the reason `lib/dayHikes.ts` gives at length — and its climb keeps that file's three states: `undefined` (never asked), `null` (asked; the graph could not price it), a pair. Never 0 as a stand-in.

## The shelf on Today

A horizontal rail of up to three cards under a `Suggested hikes` rule, then a full-width **Find a hike** row carrying how many more there are, then the note *Routes from community contributions. Check before traveling.*

- **Mode re-ranks, it never hides.** The section leads in day mode and sits last in long and volunteer mode, where the hiker's own walk is the subject.
- **Nearest starts when there is a fix; the first published when there is not.** No fix makes no distance claim — the rule reads "Suggested hikes", not "near you".
- **Nothing to suggest collapses the section** — no rule, no gap, no row.

## Find a hike

Pushed from the row; Today stays the selected tab. One search in two states and a sheet over it:

- **Find** — crumb back to Today, the search field (`Town, trailhead, or near me`), the facet chips, and the results under a rule saying where the search is anchored.
- **Results** — pushed by a sheet's *Show N hikes*: the count as the title, a sort control, the applied filters as removable chips with `+ filter` after them, the first result promoted to a full-bleed card.
- **One facet sheet at a time** — `chrome/FacetSheet.tsx`: the brand's top rule (nothing about a filter changes what a hiker does next), the options with a count each, a caveat, and *Clear* beside *Show N hikes*.

### The five facets

| Facet | What it is | Offered when |
|---|---|---|
| Location | The field resolves against the towns and trailheads the phone already holds (`hikePlaces`); **Near me** is the fix | Near me: only while there is a fix |
| Difficulty | Easy / Moderate / Strenuous, the publisher's rating | Some route on the phone is rated |
| Time to complete | Under 2 h / 2 – 4 h / 4 – 6 h / All day, **buckets** of walking time at the hiker's pace, decided on the printed (5-minute-rounded) figure so a row and its sheet agree | Some route can be priced |
| Transit | One switch: reachable by public transport, as published. Not a journey planner | Some route has published transit |
| Author | Clubs / Guidebooks / Hikers / OurHike picks, with the named publishers under each | Anything is on the phone |

**Counts are what make the sheets honest.** Each option shows the number picking it would leave, taken with every *other* facet as the hiker has it; the primary button says the number it is about to show; `FindHike.test.tsx` asserts the list then shows that number. A facet no route on the phone can answer is not offered — the no-dead-controls rule `DayHikeList.tsx` keeps for its three sorts.

**Location orders, it never cuts.** "Near Pearisburg, VA" over the list means the list runs outward from Pearisburg. A radius nobody has picked would hide routes behind a number no hiker can see; if one is ever wanted it is a facet with a count like the others.

### The three sorts

Nearest first (needs an anchor — a fix or a picked place — and a readable start), shortest first (by walking time; an unpriced route sorts last rather than at zero), easiest first (by the publisher's rating; unrated last). Each is offered only when it can be honest; with one honest sort the header prints a word rather than a control; with none the list is the publisher's own order.

### The empty states

No published routes on the phone: *Nothing published reaches this phone yet — only routes inside what you have downloaded can be searched with no signal.* The boundary, never "no hikes here". Nothing matching the filters: a sentence, with the chips still removable.

## Data

`suggested_hikes.json` is an **optional** artifact on the published-data path (`config.ts`'s `SUGGESTED_HIKES_KEY`), read by `lib/suggestedHikesData.ts`: fetched when there is signal, kept in IndexedDB through the conditions cache, validated on both ways through. Junk costs the record, never the list — a route needs an identity, a name, its ends and a **named publisher** to be shown at all; everything else degrades to its honest absence.

**It is a shelf, and each hike's prose is its own object beside it (#1473).** The shelf had reached **1.70 MB of `conditionsCache.ts`'s 2 MB ceiling**, and that ceiling is a cliff rather than a slope: it *deletes* the copy a phone holds rather than trimming it, so the publish that crossed it would have emptied the shelf offline on every phone at once, with no warning and no shorter list. Measured over the 201 records published on 2026-09-15 by rebuilding the artifact without each field, `description` alone was **58.1%** of the bytes (989,145 of 1,703,940) and `directions` another 6.6% — prose the shelf and the finder never read.

| | per record | 201 | 2,000 |
|---|---|---|---|
| before | 8,477 B | 1.70 MB | 16.9 MB |
| **shelf now** | **877 B** | **0.18 MB** | 1.75 MB |
| detail, each | 6,331 B mean | — | fetched one at a time |

`suggested_hikes_detail_<n>.json` is one hike's prose, fetched by `lib/useHikeDetail.ts` when somebody opens it and kept per hike. **One object per hike rather than a shard, because a hiker opens one walk**; the *shelf* is what gets cut into 1-degree coverage cells, being the artifact that grows with how much ground a phone has downloaded. The 201 details together are 1,272,503 B — median 6,218, largest 10,086, which is **0.48% of the per-artifact cache ceiling**, so no single one can trip the cliff that prompted this. They accumulate in IndexedDB one per hike a hiker has *opened*, and nothing prunes them: all 385 opened would be about 2.3 MB, against the 1.18 GB a downloaded map occupies. That is the trade — the details are kept so an already-read walk reads again with no signal, and the bound is how many walks somebody opened rather than how many exist. A detail that has not arrived is a hike whose publisher said nothing more — the state every field in `SuggestedHikeDetail` was already written for, which is what makes fetching prose on demand safe rather than a new way for the screen to fail. Both are written **compact**, like every other artifact a phone downloads; indentation alone had been 51% of the shelf. The flat name is not cosmetic: `pipeline/lib/r2_keys.py` declares five top-level prefixes and this is not one of them, so a `suggested_hikes_detail/` directory makes every one of these keys illegal and `assert_valid_keys` aborts the whole vector-data publish before a byte is uploaded — the same shape `at_basemap_cell_<name>.pmtiles` uses, for the same reason.

**The client half landed first (#1284), the pipeline half followed with NYNJTC's Favorite Hikes (#1290), and #1427 replaced the source under it.** `pipeline/export_suggested_hikes.py` now writes the artifact from the NYNJTC Hike Finder export — 385 hikes rather than 20, because the scrape it replaced could only reach the pages NYNJTC does not password-protect.

**A route on this shelf came by one of two roads, and the record says which in `routeProvenance`.** That field, with `routeGrade` and `routeNotes`, rides on the **shelf** record rather than in the detail object — `App.tsx` draws the line from the shelf, so leaving provenance behind a fetch would let a generated line be drawn with its provenance still in flight, which is the display outrunning its source that the field exists to stop. `published` is a GPX track the writer **drew** — 110 of the 113 in gpx.studio, only 2 carrying a `<time>` element at all, so it is a line somebody drew on a map and not a walk anybody recorded (#1451); `generated` is a line `pipeline/lib/hike_route_builder.py` inferred from their turn-by-turn description over this build's junction graph, measured by `pipeline/lib/trail_graph_route.py`, the twin of this app's router. **A screen must never print one in the voice of the other.** An inferred route is graded before it ships — against the publisher's own stated mileage, their own route type, and whether a walk they call a Circuit actually closes rather than doubling back — and one the pipeline cannot stand behind ships as no route at all, which is FEATURES.md's "a confidently wrong prediction is more dangerous than an honest unknown" applied to the line a hiker follows. 201 records ship today, 47 of them published and 154 inferred.

It carries their prose, their categorisation, their **Features tags**, their difficulty and their stated length beside this build's measurement. Two notes on quoting the publisher faithfully: the export publishes six difficulty levels where `DIFFICULTIES` holds five, so "Very Strenuous" maps to `strenuous` — which *understates* it — and the publisher's own word rides along in `publishedDifficulty` on the shelf, so a card or a facet filter can read it without fetching anything; and a release still has no shelf when nothing passes, which is a phone with nothing to suggest rather than a failed download. The document shape is:

```json
{ "generated_at": "2026-09-08T12:00:00Z", "hikes": [ { "id": "…", "name": "…", "miles": 6.2,
  "climb": { "gainFt": 980, "lossFt": 980 }, "difficulty": "moderate",
  "author": { "kind": "club", "name": "NY-NJ Trail Conference" },
  "transit": { "line": "NJT 197", "toStop": "Culvers Gap", "walkMiles": 0.3, "source": "NJ Transit" },
  "photo": { "url": "…", "credit": "…", "licence": "CC BY 4.0" },
  "segments": [[ { "coord": [-74.6, 41.2], "poiId": null }, { "coord": [-74.58, 41.2], "poiId": null } ]] } ] }
```

## One route's detail, and what it refuses to say

`screens/HikeDetail.tsx` (#1290, wireframe `1g`) is what a card opens — on the Today shelf, in the finder's results, anywhere `SuggestedHikeCard` is a button. It is pushed over Today rather than made a fifth tab, so Today stays the selected room.

**The two figures are the point of the screen, and they are allowed to disagree.** `hike.miles` is what this build measured — on a published line, its own length; on an inferred route, the trail lines the phone holds. The publisher's own stated length sits beside it in `detail.publishedMiles`, and a quiet line under both names which is which. Printing one dressed as the other would be a display outrunning its source.

**A generated route says so, and says what was checked.** `detail.routeGrade` is `strong` or `fair` and `detail.routeNotes` carries every check that was not clean — a length that disagrees with the publisher by more than a fifth, a start further from the trail than the phone's own resolving radius, a loop that doubles back. This is the screen where an inferred line either earns a hiker's trust or is honest about not having it.

Four more things it declines to do:

- **No time from an unmeasured climb.** Every route shipping today has `climb: null`, so the figures line reads `no time — climb unmeasured` rather than pricing the walk as flat ground. Why they all do is the last section of this file.
- **No map plate.** Drawing the route truthfully means resolving it against the graph the phone holds and rendering that geometry, which is what *Open on map* does on the real map. A decorative sketch is a picture of a walk that may not be the walk.
- **No pace judgement, no score, no count of anything but the walks themselves** (#982, value #1).
- **No Avenza link**, on the maintainer's instruction, though the publisher's own pages carry one.
- **The publisher's paper map, since [#1574](https://github.com/OurHike/OurHike/issues/1574).** Where the publisher is a steward whose store block grants this screen and whose own sheet index names the hike's park, the footer says which sheet the park is on and links the product on the publisher's own store, title verbatim — "The park is on sheets 118 and 119 of the New York-New Jersey Trail Conference’s *Harriman-Bear Mountain Trails Map ›*". No price, ever: the store is the source for that. `client/src/lib/paperMaps.ts` is the join, and its word-containment rule ("Harriman State Park" is on the sheet NYNJTC lists as "Southern Harriman State Park") is `@unvalidated` against the real 385 park names, which were not in the checkout it was written in.

The start is the publisher's coordinate, and the screen says where it came from: a pin they placed, or the centre of the map on their page — the second reading is weaker and the card prints the caveat that says so before offering directions.

## Saving one: one record, many dates

A hiker who walks the same loop three times has walked one route three times, not three routes. That is the maintainer's decision on #1290 — *"we need 1 record, with the ability to log multiple dates"* — and it is why `DayHike` gained `walks?: DayHikeWalk[]` rather than the save button minting a fresh uuid each press.

The record is found by `sourceId` (`<source key>:<slug>`, the published route's own id) and never by name or geometry: a hiker may rename their copy, and two outings over mostly the same ground are genuinely different walks that a geometry comparison would merge wrongly. `savedFromSource`, `logWalk` and `walkedDates` in `lib/dayHikes.ts` are the whole of it; `MAX_WALKS` caps the list because the record syncs.

The button therefore has three states and says three different things — **Save to my hikes**, then **Log a walk**, then **Log another walk**. The middle one matters: saving a plan is not walking it, so a freshly saved route has logged nothing and the word "another" would be a lie about the hiker.

`sourceAuthor` rides along, captured at save time: the publisher's credit line as it read when the route was saved, printed on the day-hike list beside the hiker's own hikes. A published route landing in somebody's list with no publisher on it would be the app quietly presenting another organisation's work as theirs — and looking the credit up on display instead would lose it the day the route leaves the published document.

*Open on map* appears only once the route is saved, because what the map draws is a record in the hiker's own hikes (`openId`, re-resolved from its coordinates). Before the save there is nothing to draw, and a control that cannot do its job is not offered.

## Not built yet, and why

The handoff's low-fi round sketched four screens it said were **not designed hi-fi**. Two are now built — the hike detail (`1g`) and a suggestion saved with its author kept (`1j`), both #1290. The other two are not:

- **`1h`, the map view of a whole result set.** *See these on the map* is still not drawn, and the reason is now concrete rather than "undesigned": the map draws one route at a time, from a record the hiker has saved. Showing nine unsaved routes at once needs either a second drawing path or nine silent saves, and neither is a thing to add without a design. One route at a time is reachable today — the detail's *Open on map*.
- **`1i`, the nothing-downloaded and nothing-matched screens.** The finder prints an honest sentence for each case rather than a designed screen; the sentence says where the boundary is ("Only routes inside what you have downloaded can be searched with no signal") rather than claiming there are no hikes there.

One gap the detail screen inherits rather than creates: **no route shipping today carries a climb**, so no route on any of these surfaces can be given a walking time. That is **#1313 — The published per-edge climb sidecar no longer fits the junction graph, and the phone pairs them by index anyway**: 42,103 sidecar rows against the graph's 466,966 edges, paired positionally with no length check — and it is a safety-path gap, not a cosmetic one: a hiker deciding whether they beat the dark gets an honest "unmeasured" from every one of these screens until it is fixed.
