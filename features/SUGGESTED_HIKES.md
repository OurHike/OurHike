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

**The client half landed first (#1284), and the pipeline half followed with NYNJTC's Favorite Hikes (#1290).** `pipeline/export_suggested_hikes.py` writes the artifact from the routes a person has signed off in `pipeline/reference/nynjtc_hike_routes.json` — NYNJTC publishes a trailhead pin and a description and no line, so each route is OurHike's construction of that description as the ends the phone routes between, measured by `pipeline/lib/trail_graph_route.py`, the twin of this app's router. It ships their prose, their photograph with its credit (a `photos/<digest>.jpg` key the client resolves against the bucket), their five-level difficulty by their own slug, and their stated length beside this build's measurement. A release still has no shelf when nothing is signed off, which is a phone with nothing to suggest rather than a failed download. The document shape is:

```json
{ "generated_at": "2026-09-08T12:00:00Z", "hikes": [ { "id": "…", "name": "…", "miles": 6.2,
  "climb": { "gainFt": 980, "lossFt": 980 }, "difficulty": "moderate",
  "author": { "kind": "club", "name": "NY-NJ Trail Conference" },
  "transit": { "line": "NJT 197", "toStop": "Culvers Gap", "walkMiles": 0.3, "source": "NJ Transit" },
  "photo": { "url": "…", "credit": "…", "licence": "CC BY 4.0" },
  "segments": [[ { "coord": [-74.6, 41.2], "poiId": null }, { "coord": [-74.58, 41.2], "poiId": null } ]] } ] }
```

## Not built yet, and why

The handoff's low-fi round sketches four more screens it says are **not designed hi-fi** and to ask about before building: the hike detail (`1g`), the map view of the results (`1h`), the nothing-downloaded / nothing-matched screens (`1i`), and a suggestion saved into the day-hike list with its author kept (`1j`). Until they exist:

- A card is an `<article>`, not a button — a control that looks pressable and goes nowhere is the failure `chrome/LineSheet.tsx`'s rule exists to prevent. `SuggestedHikeCard` takes an `onOpen` the shell does not yet pass.
- *See these on the map* is not drawn.
- A photo's credit line is the detail screen's to print; a 172px card has no honest room for it.
- Saving a suggestion re-uses the day-hike store as the handoff specifies — a `DayHike` built from the segments, `recorded: 'planned'`, through `saveDayHikes` so the sync ledger records it as the hiker's own edit — but it waits for the detail screen that offers it, and for a decision about carrying the author on a synced record (`backend/app/schemas/synced_day_hike.py`).
