# OurHike — Planning a Hike (v2 Research Spike)

Companion to [SEGMENTS.md](SEGMENTS.md), [TRIP_PLANNING.md](TRIP_PLANNING.md), [ELEVATION_PROFILE.md](ELEVATION_PROFILE.md), [PERSONALIZED_PACE.md](PERSONALIZED_PACE.md) and [../FEATURES.md](../FEATURES.md).

**This is a spike, not a build plan.** The distinction matters here more than usual: planning a thru-hike is the first thing OurHike would do that is not "show me where I am", and getting the shape wrong is expensive in a way a misplaced button is not — a plan is a structure everything after it hangs off. So this document's job is to name the decisions, answer the ones that are already answerable from data this repository holds, and leave the rest visibly open with a way to close them. [`pipeline/spike_day_planner.py`](../pipeline/spike_day_planner.py) is the runnable half.

Scope: **v2's first feature** ([../ROADMAP.md](../ROADMAP.md)). Nothing here is v1, and nothing here blocks launch.

---

## What is being asked for

Six capabilities, in the order they were asked for:

1. **Drop start, end and intermediate points** on the map to lay out a route along the trail, and see its **distance, elevation gain and loss, and an estimated time**.
2. **Plan across multiple days**, not one stretch.
3. **Roll days up into sections, and sections up into the whole trail.**
4. **Mark a day as a zero**, or as the day a **resupply** happens.
5. **A timeline** as the display, so a hiker can see **how much food a section needs**.
6. **Auto-generate the plan** — pick shelters as day boundaries, given a target daily time or mileage.

And one that is not a capability but is where planners actually fail:

7. **When today changes, the rest of the plan has to change well.**

Item 1 is a feature. Items 2–7 are a product, and the reason this is a spike.

## What already exists, so this does not re-litigate it

Worth reading this list before the design below — a surprising amount of the hard part is built, and the parts that are not are mostly *joins* between things that are.

| Already built | Where | What it gives planning |
|---|---|---|
| Hike → Segment tree | [SEGMENTS.md](SEGMENTS.md) | The data model. Days, sections and the whole trail are **one recursive structure**, already designed. This spike does not invent a second one. |
| Snap a tap to the trail | `client/src/lib/trailPosition.ts` | `locateOnTrail()` turns a tapped coordinate into a mile from Springer, or refuses if it is more than 3 miles off the corridor. This is the route builder's whole input mechanism. |
| Confirmed ascent over any window | `client/src/lib/elevationGain.ts` | Gain between two mileposts, with the 3 m dead band that keeps DEM noise out of the number. Loss is the same function on a negated profile and does not exist yet. |
| The elevation profile itself | `pipeline/export_elevation.py` | ~141,000 samples at 25 m, shipped whole (0.87 MB gzipped) so it works with no signal. |
| Naismith time | `client/src/lib/naismith.ts` | Distance + ascent → a duration. Deliberately refuses descent. |
| The stops a day can end at | `pipeline/export_poi.py` | **280 shelters and 232 campsites**, plus ATC's 59 Community towns. Opentrail's 72 `r` points were counted here as resupply until [#806](https://github.com/OurHike/OurHike/issues/806) found them to be roads and gaps; its 103 towns are fetched and unpublished ([#803](https://github.com/OurHike/OurHike/issues/803)). |
| Water near a shelter | [TRIP_PLANNING.md](TRIP_PLANNING.md) | Designed as a precomputed shelter→nearest-water distance. Not built, and the auto-planner is the feature that makes it pay. |

## The questions, and where each one stands

| # | Question | Status |
|---|---|---|
| Q1 | Can real shelter spacing carry an auto-generated plan at a target day length? | **Measurable, not yet measured** — `spike_day_planner.py` answers it, and needs the fetched ATC data to run. |
| Q2 | Does the existing Hike → Segment tree hold days, sections and the trail without a second model? | **Answered: yes.** See "The model" below. |
| Q3 | What happens to the rest of the plan when today changes? | **Answered as a design**, and it is the piece with the most product risk. See "The cascade". |
| Q4 | Is the timeline the primary surface, or the map? | **Answered: both, one plan.** See "The timeline". |
| Q5 | How much of food planning can be computed honestly? | **Answered: days, never calories.** See "Food". |
| Q6 | Is any of this big enough to need a backend? | **Answered: no.** ~24 KB per thru-hike plan. See "Where a plan lives". |

---

## Finding 1 — there are two "miles" in this codebase, and a plan cannot survive that

This is the first thing to fix and the easiest to miss, because it is invisible at the scale everything currently uses it at.

`client/src/lib/trailPosition.ts` measures a mile by walking the centerline's vertices. `pipeline/export_elevation.py` measures a mile by walking the *merged* centerline after `ST_LineMerge`. Its own header says so plainly: *"a mile here and a `distance_mi` in `elevation_profile.json` are close but not identical. They should not be compared against each other as though they were the same measurement."*

They are compared anyway — `App.tsx` windows the elevation ribbon at the GPS fix's mile. Over a 10-mile window a small offset moves the ribbon slightly and nobody can tell. **A plan sums that offset 150 times**, and prints a per-day gain figure against a day boundary that is not quite where the profile thinks it is.

**Recommendation: one scale, and it is the pipeline's.** The client should stop deriving miles from geometry it re-measures locally, and read a mile that was computed once, upstream, on the same line the elevation profile was sampled along.

## Finding 2 — the pipeline should publish a mile on every POI

Which falls straight out of Finding 1, and is worth stating separately because it is a small change that unlocks most of this feature.

`export_poi.py` publishes shelters, campsites, water and resupply as points. Add one attribute — `mile`, computed by projecting each point onto the same ordered, merged, metric centerline `export_elevation.py` already builds (`ordered_oriented_parts()` → `reproject_lines_to_meters()` → shapely's `.project()`). Then:

- Every candidate day boundary arrives with its position along the trail already known, so the auto-planner is a pass over a sorted array rather than 512 linear-referencing operations on a phone.
- Shelter miles and profile miles are the same measurement by construction, so a day's distance and that day's gain describe the same stretch of ground.
- The client's `locateOnTrail()` keeps its job — placing a *tapped point*, which has no precomputed answer — and stops being the source of truth for things that do.

Cost: one more column in an artifact that already exists, and a `mile` field in `pipeline/lib/poi_schema.py`. Old data releases without it degrade the same way `spurs.json` and `elevation_profile.json` already do — the map still draws, the planner says it needs a newer download.

> **Built (#753).** `export_poi.attach_miles` projects every POI onto the profile's own ordered metric centerline with the same carry-across-gaps accumulation, and the client's `StoredPoi` carries the optional `mile` through. Two things settled in the building: the number is a **position** (NOBO miles from Springer, the repo's standing convention — direction stays the consumers' derived view), and it deliberately shares the profile's ordering fault (#652/#559) rather than fixing it privately — one measurement, wrong together where the ordering is wrong, improving together when it improves.

## Finding 3 — the auto-planner is small enough to run on a phone, instantly

Choosing day boundaries is a shortest-path problem, not a search. Candidate stops are sorted by mile; a day is an edge from one stop to a later one; the cost of an edge is how far that day lands from what the hiker asked for.

```
best[j] = min over reachable i < j of  best[i] + cost(day from i to j)
```

The size, **measured 2026-08-18 by `spike_day_planner.py` against the live ATC layers** (fetched the same day: 280 shelters + 232 campsites; 273 and 227 of them within 0.5 mi of the centerline — this table was arithmetic over assumed-even spacing until #754 ran it):

| | measured |
|---|---|
| candidate stops, whole trail | 512 (500 on-corridor) |
| average spacing, shelters + campsites | 4.3 mi mean · 3.5 median · **10.8 p90 · 21.5 max** |
| average spacing, shelters only | 7.9 mi mean · 7.2 median · 13.5 p90 · **34.4 max** |
| stops reachable within a 25-mile cap, from any one stop | 6.4 mean |
| edges evaluated for a **whole thru-hike** | **3,299** |

Three findings the arithmetic could not have produced:

- **The even-spacing assumption was fine for the totals and wrong about the tail.** The mean really is 4.3 mi and the edge count really is ~3,000 — but spacing is lumpy: one shelters-only gap runs **34.4 miles**, which no 25-mile cap survives. **Campsites are load-bearing, not an enrichment**: with them, generated plans at every target from 10 to 20 mi/day schedule **zero** over-cap days, and the worst day is 21.5–24.3 mi.
- **Real plans hit their targets well enough to ship.** Within ±20% of target: 50% of days at a 10-mile target rising to 86% at 20 — the short-target misses are the trail forcing longer days through sparse stretches, which is a fact about the Appalachians the planner should show a hiker rather than hide.
- **The axis these miles ride carries #652's fault, now quantified.** Projecting ATC's own 4,395 half-mile markers onto the same ordered metric centerline the profile (and #753's POI miles) use, the published mile disagrees with ATC's own `Measure` field by a **median 7.7 mi (p90 29.5, max 101.8), systematically short** — the uncounted cross-part gaps accumulate ~35 mi by Katahdin and the misordered stretches scatter the rest. Spacing and plan figures above are differences between near neighbours and mostly dodge this; anything comparing a published mile against an ATC-quoted mile (a closure's `start_mile_marker`, a guidebook figure) does not. That comparison is recorded on #652, where the half-mile markers were already named as the candidate fix.

**The auto-planner needs no backend, no network and no precomputation beyond Finding 2** — 3,299 edge evaluations is less arithmetic than one frame of the map costs — and that is now a measurement rather than an assumption.

What the cost function should be:

- **Deviation from the target, asymmetric.** Overshooting is worse than undershooting: a hiker who arrives early can walk on, and one who runs out of daylight two miles short of the shelter cannot. Square the deviation, and weight over-target more heavily than under.
- **A hard ceiling, never exceeded.** A plan is allowed to be short; it is not allowed to quietly schedule a 31-mile day because the shelter spacing was awkward.
- **A tie-break toward shelters over campsites**, and toward stops with water — which is where TRIP_PLANNING.md's precomputed shelter-to-water distance earns its keep.

## Finding 4 — plan by time, not by distance

A 15-mile day in southern Virginia and a 15-mile day in the White Mountains are not the same day, and every paper planner has to pretend they are. **This app has the elevation profile, so it does not have to.**

The target should therefore be expressible either way, and default to time:

> 15 miles with 4,000 ft of ascent is **≈6h 50m** of Naismith walking.

Two honest limits, both of which have to be visible in the UI rather than buried here:

- **Naismith is moving time.** It knows nothing about lunch, water stops, a view, or forty minutes at a shelter. A day planned to a 8-hour Naismith target is a longer day than eight hours. Either the planner asks for *walking hours* and says so, or it applies a break allowance the hiker sets — and pretending an arrival clock falls out of this is exactly what WIREFRAMES.md's load-bearing values already forbid.
- **It ignores descent, and tread roughness has no data source at all.** TRIP_PLANNING.md establishes both. Pennsylvania's rocks do not appear in any field the pipeline ingests, and a planner that implies otherwise is confidently wrong in advance, away from the ground where a hiker could check it.

[PERSONALIZED_PACE.md](PERSONALIZED_PACE.md) is the eventual answer to the first limit and half of the second. It is Post-MVP and this feature must work without it — Naismith as the cold start, the hiker's own adjustment as the escape hatch.

---

## The model

SEGMENTS.md's tree, with three additions and no new hierarchy. Its `Hike` is this document's plan; its `Segment` is a day, a section, or the whole trail depending on depth.

```
Hike                                  (SEGMENTS.md, unchanged)
  + direction         NOBO | SOBO     which way "forward" runs
  + target            { walking_hours } | { miles }   what the generator aimed at
  + break_allowance   optional, per walking hour

Segment                               (SEGMENTS.md, plus)
  + stop              StopRef | null  where the night is spent
  + pinned            bool            this one does not move - see the cascade
  + generated         bool            the app chose this, the hiker has not touched it

StopRef                               (SEGMENTS.md's "start/end reference", named)
  poi_id | dropped point, always with a real mile
  + resupply          bool            supplies are picked up here
```

Three decisions inside that, each of which could have gone another way:

**A zero day is a Segment whose start and end are the same stop.** It needs no `kind` field and no special case: it is a day with a date, a place, and no distance. That falls out of SEGMENTS.md's *"there's no fixed unit"* rather than fighting it — and it is the reason a zero has to be *in* the tree rather than a gap between days. A gap has no date and eats no food; a zero does both.

**Resupply is a property of a stop, not of a day.** A resupply happens at a place — a town, a road crossing, a post office — and can land in the middle of a walking day as easily as at the end of one. Attaching it to the day would make "how much food do I need" a question about day boundaries, which is not what it is a question about.

**A section is derived, not drawn.** For a thru-hiker a section *is* the stretch between two resupplies — that is what the word means on trail. So sections generate themselves from the resupply flags, and the hiker can override the grouping but never has to build it. This answers SEGMENTS.md's open question about whether picking "thru-hike" should auto-generate ~180 empty daily Segments: **no** — generate days from the route and the target, and group them by where supplies come from.

## Food

The single most useful number in a section is *how many days of food to carry out of this town*, and it is also the easiest place to be dishonest.

**The app computes days. It never computes calories, weight or a menu.** Between two resupply stops it knows exactly how many days there are, including zeros, and that is a fact. What a hiker eats in a day is not a fact the app has any access to — appetite at week six is not appetite at week one, and a number invented here would be acted on in a supermarket, in advance, where it cannot be checked.

So the timeline says **"6 days of food"**, and if the hiker has entered their own per-day figure in settings it multiplies theirs and labels it as theirs. This is the same line [TRIP_PLANNING.md](TRIP_PLANNING.md) already draws around unverified water data, applied to a number the app would otherwise be making up entirely.

One genuine open question: **a zero day in town usually means eating in town.** Counting it as a day of food carried is wrong; not counting it is wrong when the zero is at a shelter rather than in a hostel. Both answers are defensible and the difference is a day's food on a hiker's back. Flagged rather than decided — see the open questions.

## The timeline

Sequence and span are two different things and a plan has both. Days are a sequence; sections, resupply stretches and food carries are spans *over* that sequence. A list can show one; a timeline is the layout where a span can be drawn beside the rows it covers, which is the whole reason to build one rather than a table.

```
  ┌ SECTION 3 · Damascus → Pearisburg · 166 mi · 11 days ─────────────┐
  │                                                                    │
  │  ▪ Tue 12 May   Day 24   Damascus → Lost Mtn      15.4 mi  ≈7h05m ┐│
  │  ▪ Wed 13 May   Day 25   Lost Mtn → Thomas Knob   17.1 mi  ≈8h20m ││ 6 days
  │  ○ Thu 14 May   ZERO     Grayson Highlands                        ││ of food
  │  ▪ Fri 15 May   Day 26   Thomas Knob → Old Orchard 12.8 mi ≈5h40m ┘│
  │  ⬤ Sat 16 May   Day 27   … → Atkins            RESUPPLY           │
```

Rules that make it readable rather than dense:

- **One row per day, always** — a zero occupies a row, because it occupies a day.
- **Spans sit in a gutter beside the rows**, not as headers between them, so a food carry that crosses a section boundary is still one continuous thing.
- **Roll-up totals live on the container**, not repeated per row: the section header carries its miles and days, the trail header carries the whole hike's and its projected finish date.
- **The map and the timeline are two views of one plan.** Selecting a day in the timeline highlights that stretch on the map; selecting a stretch on the map scrolls the timeline to it. Dropping points is spatial and belongs on the map; checking whether Thursday is survivable is temporal and belongs here. Neither is the "real" one.

## The cascade — when today changes

The hardest part, and the part that decides whether anyone uses this twice. Plans slip constantly: weather, a zero that was not planned, feeling strong and walking eleven miles past the shelter. A planner that requires re-doing the next four months by hand gets abandoned on day three; a planner that silently re-does it for you loses the hostel booking that was the one fixed thing in it.

**Three named responses, and the app never picks one silently.**

| | What it does | When it is right |
|---|---|---|
| **Shift** | Every later day moves by the same date delta. | The change was *temporal* — an unplanned zero, a late start. Mileage was fine; the calendar moved. |
| **Absorb** | The finish date holds; the generator re-runs over the remaining route with the same target. | The change was *spatial* — walked further or shorter than planned. The plan re-balances into the days that are left. |
| **Leave** | Nothing after today changes. | The rest of the plan is already fixed by things outside the app. |

This is TRIP_PLANNING.md's bulk date shift, generalized — that document names the shift operation as the single most valuable one and leaves restructuring for later. Absorb is the restructuring, and it is only tractable because the generator exists: re-balancing is just re-running the plan over a shorter route with the same target.

**Two rules make automatic re-planning safe rather than dangerous:**

**Pins.** Anything a hiker has committed to in the real world — a booked hostel, a mail drop with a date on it, a ride to a trailhead, a permit — is pinned. **A cascade re-plans between pins and never through one.** Without this, any automatic update eventually moves the one day that had a real-world commitment attached, which is precisely the failure that teaches people not to trust planning tools. With it, "absorb" has hard walls to work inside, and the generator's job on each stretch is unchanged.

**The past is a record, not a plan.** Completed days are immutable; the cascade only ever touches days after today. This is SEGMENTS.md's completion model, and it is what keeps a plan honest as a log of what actually happened.

**And the choice is offered with its consequences spelled out, not as a "recalculate?" prompt:**

> You walked 4.2 miles past Lost Mountain today.
> **Absorb** — finish 30 Aug as planned; the next 6 days average 16.2 mi instead of 15.0
> **Shift** — same daily mileage; finish 31 Aug
> **Leave** — tomorrow is a 10.8 mi day

Three concrete outcomes beat one abstract question. Nobody can answer "should I recalculate?"; everybody can answer that.

## The route builder — the original ask

The manual half, which the generator does not replace: a hiker drops points and gets numbers back.

> **Amended 2026-08-18: the entrance changed; the arithmetic did not.** The
> maintainer redirected the builder to a destination-led flow — "like a Google
> Maps route that lets you add multiple destinations": look a stop up by name
> first, with the map and a distance from the previous stop as the other two
> doors, and *where from + how far / how long* as the opening question
> (PR #774, from mockups chosen there). What survives of the bullets below:
> `locateOnTrail()`'s snap and the 3-mile refusal; the least-added-distance
> insertion, placing added destinations as well as taps; and every figure and
> limitation, unchanged. An added destination is also now a *forced day
> boundary* the generator plans through (`planDaysVia`), pinned in the
> laid-out plan — on a linear trail, forcing the boundary is the whole
> meaning of naming a stop.
>
> **Amended 2026-08-25 (#973): tap-to-drop is back, as the second door.** The
> earlier amendment concluded "tap-to-drop is no longer the input mechanism",
> and that went one step further than the redirect required. The maintainer,
> reviewing wireframe 2a frame 1 against what shipped: *"The route builder
> should use this wireframe, but keep the google maps types design."* So both,
> and they were never in tension — the destination list is the anatomy, the
> tap is an input into it.
>
> The entrance keeps its job, which is the question nothing else in the app
> asks: **how far can I get?** It gains "or just tap the trail", opening an
> empty editor where the map is the input; a start already placed carries
> through. Every bullet below is live again, and none of it needed writing:
> `insertRoutePoint` had implemented the placement rule, tie-break and all,
> the whole time, and `onRouteTap` was already wired on the canvas for an open
> draft. The editor phase simply declined to act on the tap.

- **Tap the trail to drop a point.** It snaps to the centerline via `locateOnTrail()`; a tap more than 3 miles off any centerline vertex is refused rather than placed, because there is no honest mile to give it.
- **The first point is the start, the last is the end, and everything between is intermediate.** No modes, no separate "add waypoint" tool.
- **A new point is inserted where it adds the least distance** — which makes both natural workflows work without the hiker learning a rule. Tapping in walking order always appends; tapping between two existing points always inserts there; tapping behind the start extends the hike backwards from it.
- **Per leg and in total: distance, gain, loss, and ≈time.** Gain and loss are direction-aware — the same stretch walked south has its gain and loss swapped — which means the ordered sample run has to be reversed before counting, not the totals swapped afterwards.
- **Loss needs one new function.** `cumulativeGainOverGaps()` over a negated profile, so confirmed descent uses exactly the dead band confirmed ascent does and the two can never drift apart.

**A limitation to state in the UI, not just here: only the AT centerline is routable.** `buildTrailIndex()` includes `source === 'centerline'` and nothing else, so blue-blazed side trails, alternates and road walks into town cannot currently carry a route. That is right for v1's "which mile am I at" question and wrong for planning, where the walk into Damascus is part of the day. It is the largest single gap between this design and a plan a thru-hiker would actually keep.

## The day hike on a network — what a tap means, and what a drawn line snaps to

Everything above assumes one trail's mile axis. `mi 470.8 → mi 486.2 → mi 503.3` is the right model for Damascus → Atkins and the only model the A.T. ever needed. A Harriman day hike is four trails and three junctions, and "mile 2.1" is not a thing a hiker can name there — so on that ground the builder above does not degrade, it has **nothing to ask for**. That gap is [#928](https://github.com/OurHike/OurHike/issues/928) — *A day hike built by touching lines, because a park has no single mile axis to drop stops on*.

Two decisions had to land before it could be built, and both were taken by the maintainer on **2026-08-23** — on [#934](https://github.com/OurHike/OurHike/issues/934) — *Decide what a tap between two junctions means — split the segment, or snap to the nearer junction — and write it down* — and [#935](https://github.com/OurHike/OurHike/issues/935) — *Decide the snap tolerance for a drawn route, and what happens to the parts with no trail under them*. Each was filed as a decision in its own right, on the pattern of **#552 — Decide the unit of offline coverage, and write it down**. This section records them and does not relitigate them.

**A tap splits the segment (#934).** Verbatim:

> I think this should split the segment.
>
> If a user drops too points, the route should be exactly between those points.  We shouldn't do any guessing about what POI the user meant.  I would imaging most users would start/stop at POI's but not always

So the route runs **exactly between the two tapped points**, and the junction graph gains a temporary node where the finger went. The rejected alternative — snap to the nearer junction — is rejected on ground that is measured rather than argued: Harriman–Bear Mountain has **263 junctions across 316 trail-miles, one every 1.2 miles** ([NEARBY_TRAILS.md](NEARBY_TRAILS.md), measured by **#771 — Spike: Harriman's crossing trails next to the AT — find what a trail network breaks that a linear trail never could**), so snapping would have moved a start by roughly 0.6 mi on average, which is a material piece of a six-mile day and an arbitrary one.

Note what the rule is stated about: **POIs, not pixels.** The app may not decide a hiker meant the trailhead because they tapped 400 m past it. That is the refusal `locateOnTrail()` already makes on the A.T. when a tap is off-corridor — it declines rather than inventing a plausible mile — carried onto a network.

**An end is wherever the hiker put it; a lot is an annotation, never a precondition (2026-08-25).** The same decision read forward into storage and into the card, taken by the maintainer on [#981](https://github.com/OurHike/OurHike/issues/981) — *A day hike starts at a parking lot, and nothing in the pipeline knows where the lots are*:

> A dayhike should be able to start anywhere - not just the parking lot. Can you make sure the issues and features are built to allow the user to choose their start/end points

The merged builder already obeys it and this records why it must keep doing so. `tapAt` accepts any point the junction graph can claim, and `lib/dayHikes.ts`'s `DayHikeEnd` stores that end as the **coordinate** it landed on, with `poiId` an optional annotation — null on every hike the builder has made. No code path asks for a trailhead. #981's body asserted the opposite — that ends are "stored as POI references rather than coordinates" — and that was corrected rather than implemented: a POI reference as an end's identity would turn a start the app cannot *name* into a start the hiker cannot *take*, which is the failure this whole section exists to prevent.

So frame `1l`'s parking block is an annotation on a start that happens to be near a lot, and its absence is not a degraded card: a hike starting halfway up a trail nobody parks at is a first-class hike with no lot to name. #981 is worth building for the hiker who *did* drive — it just does not get to be the way a day hike begins.

**The one real limit, stated rather than implied:** an end must sit on a trail one of the three organizations maintains — the #935 rule below, not a parking rule. A tap on open ground, a road shoulder or a herd path is refused in words, and widening *that* is [#931](https://github.com/OurHike/OurHike/issues/931)'s to do.

**Left open, and then answered from the other end (#1041).** Frame `1l`'s turn list is junction-relative throughout — *"mi 2.1 Right onto Seven Hills (blue) at the Pine Meadow junction"* — and a leg starting mid-segment has no such phrase available for its first line. Describing that start by the nearest **named feature** ("0.4 mi along the Pine Meadow Trail from Reeves Meadow") is not the guess this decision forbids, because it describes where the hiker put the point rather than moving it. It is still not what was decided, and it is still the option on the table if a junction-relative list is ever wanted.

The storyboard's on-trail frames sidestep it. `D10` names no junction at all — it names the **arms**:

> **Turn left** onto *Seven Hills Trail*, white blaze
> Straight on is **Pine Meadow Trail**, blue blaze — not your route
> Behind you is **Pine Meadow Trail**, blue blaze — the way you came

Every one of those is an edge attribute the published graph already carries, and the mid-segment first leg stops being a problem because **the start of a walk is not a turn** — it never appears in the list. What a hiker checks against the blaze in front of them is the trail's own name and colour, not a junction's name, which is the one thing they cannot see from where they are standing. `client/src/lib/dayHikeTurns.ts` builds the list on that rule; a turn is exactly a leg boundary, tested against the same `sameTrail` predicate the leg list uses, so the two cannot disagree about where Pine Meadow becomes Seven Hills.

This unblocks the list without settling the naming question it was blocked on. A junction-relative *list* — the whole walk, read at the kitchen table — still wants the named-feature answer above for its first row.

**A drawn line snaps only to a marked path, and a day hike may be more than one segment (#935).** Verbatim:

> The snap too should always be to a marked path.  There should be no guessing as to whether something is walkable or not.
> The whole point of OurHike is to give trustworthy maps.  Snapping to fuzzy areas would go against that.
>
> Users should be able to have multiple segments to a day hike (>1 start/stop) taht could handle some scenarios where they want to bushwack.

Two things, and the second changes the model.

**The snap target is a maintained trail line and nothing else** — no walkability inference over roads, woods roads, herd paths or open ground. This is [NEARBY_TRAILS.md](NEARBY_TRAILS.md) §3's omit-rather-than-guess rule, the one keeping `Proposed` and `Unknown` segments out of the published artifact entirely, applied to geometry instead of status.

**A day hike is an ordered list of routed segments, not one route.** This dissolves the threshold question #935 was filed asking — *when does dropping a piece stop being a footnote and become a refusal* — because there is never a bridge to size. A stretch with no trail under it **ends a segment**; the next segment begins where trail resumes; the gap between them is drawn as a gap and belongs to the hiker, who may well be planning to bushwhack it. The app never routes anyone across ground it has no evidence for, and never refuses a hike it can honestly describe most of.

It also gives [#931](https://github.com/OurHike/OurHike/issues/931) — *Roads and connectors: a loop that only closes along a shoulder, drawn honestly or not at all* — a shape it did not have. A loop that only closes along a road shoulder is expressible as two segments with a gap where the road is, without OurHike drawing a route onto a road no steward maintains. That does not build #931 or close it — a hiker still cannot **see** that the road is there, which is the whole point of its `LATER` row — but it does mean the builder is not blocked on it.

**Still undecided: the tolerance itself — and the decision above changes what kind of number it is.** Nobody has measured one, and "always snap to a marked path" removes the walkable/unwalkable ambiguity without touching the one that bites in a park: *which marked path*. Along the A.T. through Harriman–Bear Mountain, **48% of sampled points sit within 150 m of a different marked trail** ([NEARBY_TRAILS.md](NEARBY_TRAILS.md), measured from the #771 spike). A tolerance generous enough to catch a line drawn with a thumb on a moving bus is therefore, across roughly half that corridor, generous enough to reach two trails at once. So this is a **disambiguation** problem rather than a reach problem, and a single number will not settle it. Whatever lands carries `@unvalidated` and what would settle it until somebody has drawn on it outdoors; #935 stays open for that half.

## Two rooms, one tab — the mode is the chrome (#1008, 2026-08-25)

The fork above ("What are you planning?", #977) asked its question once and then nothing downstream looked different: day hikes were a shelf section between "Your hikes" and "Recent trips", in identical chrome, and no screen past the fork said which of two kinds of plan a hiker was inside. [#1008 — Day hikes and trips share one Plan tab that never says which one you're planning, and a saved day hike has no way back to it but one row on a mixed shelf](https://github.com/OurHike/OurHike/issues/1008) — consolidated from the planning-personas storyboard ("Plan a hike — day vs multi-day", 15 frames) — made the mode visible:

- **The Plan home is two rooms with a switch chip.** Day hikes wear the brand band and speak in legs and walks; Trips wear the dark chrome band and keep the trail vocabulary — days, zeros, resupply, carries. SEGMENTS.md calls `Hike.type` "a label, not a constraint"; this makes the label load-bearing on screen without enforcing anything in the model. Each room's one primary action does what its label says — "Plan a day hike" opens the day-hike builder, "Plan a new trip" the route builder — and the fork stays the entrance where the question is real: the empty state, where no mode exists yet.
- **A saved day hike has two ways back to it.** A list screen (the trips-side `TripList` counterpart) splits still-to-walk from walked off the store's own `recorded` flag, with the cached figures a list is allowed to print; and the map offers a saved hike when the GPS fix is near its start — a straight-line radius that ships `@unvalidated` in `lib/dayHikeShelf.ts`, because nobody has measured how far from a trailhead a parked hiker stands.
- **"Leave this with someone"** is the day flow's one safety surface that is not a map: a plain-text card of the plan, with the route and the trail miles from the app's own figures and everything else — the start, the car, above all "if I'm not back by" — typed by the hiker and never computed. The app has no arrival clock and does not pretend to one on precisely the card somebody will decide to worry from.

- **≈ walking time and ± elevation arrived from the other side.** This branch built a corridor-profile pricing module for the day-hike surfaces; **#1011 — Give the network's trails their climb** landed on `main` first and did it better, so the module was deleted rather than kept beside it. The graph carries per-edge climb now, `routeClimb` scales it by the metres actually walked, and both the builder bar and the finished card price Naismith from `route.climb` — on *every* trail in the network, not just the A.T. centerline the corridor profile covered. The two implementations agreed on the rule that matters and that rule is the one that survived: **null is all or nothing**. A walk with one unmeasured edge prints no time at all, because pricing that edge at zero ascent is a flat-ground claim about real ground and pricing only the measured edges understates by the same amount with a number attached. Both fail *short*, which is the direction that gets somebody caught by the dark.

**What the storyboard drew that deliberately did not ship, and what each waits on:** starter hikes ("laid out by the clubs that maintain them" — no club-laid route dataset exists anywhere in this repository; the storyboard itself calls the work editorial, related to #981's parking lots); ≈ time on the day-hike **list** and the trailhead door (both read the stored cache, and pricing needs the routing graph a list must not load); the whole-walk turn list (#934's first-leg naming question, above — the *next* turn and the junction card ship with #1041, which needs no junction name at all); recording a finished walk (#982); freehand drawing (#983).

**The one surface that prints no computed time on purpose** is "Leave this with someone", and that is a decision rather than a gap: asked and answered by the maintainer on 2026-08-25, *after* #1011 had already made the estimate available network-wide. Moving time on the card somebody decides to worry from reads as an arrival promise however it is worded, and the line that matters there — "if I'm not back by" — is a judgement about lunch and the swim and the view that only the hiker can make. The reach of the data was never the objection, so better data does not reopen it.

## Where a plan lives

On the phone, in the same IndexedDB the map already uses — SEGMENTS.md's answer, and nothing here changes it.

A thru-hike plan is about 160 segments (147 walking days at 15 mi/day, plus zeros). At roughly 150 bytes each — two stop references, two dates, a handful of cached numbers — that is **~24 KB**. Against a 314 MB background archive it is not a storage question at all, which is worth stating plainly so that nobody designs a backend for it.

Sync across devices is [AUTHENTICATION.md](AUTHENTICATION.md)'s to give, and it now exists, so the trade-off SEGMENTS.md flagged as unresolved has an answer available whenever this feature wants it. Export is [FEATURES.md](../FEATURES.md)'s existing GPX/GeoJSON commitment — a plan is a set of stretches with dates on them, which is exactly what a GPX track with waypoints is.

---

## What this spike deliberately does not settle

- **Structural editing beyond the cascade** — splitting one day into two, merging two into one. TRIP_PLANNING.md flagged it; the cascade above does not solve it, and it should be designed against a real plan on a real screen.
- **Anything social.** Sharing a plan is [COMMUNITY_BUILDING.md](COMMUNITY_BUILDING.md)'s Tramily feature, which already shares a Hike rather than inventing a second structure. Not this.
- **Any suggestion that a plan is a target to hit.** Value #1 forbids prescriptive gamification, and a planner is two design decisions from a schedule that scolds. No progress bars against plan, no "behind schedule", no streaks. The plan is a hiker's own paper log with arithmetic attached.
- **Whether the auto-generated plan is offered on first use or on request.** A generated plan is a strong anchor and it is easy to make it feel like the app's opinion of how someone should hike.

**Update 2026-08-18:** two of this document's gaps are now filled, both from a maintainer walkthrough of the shipped planner.

**A rest rhythm** (#798). The generator planned walking days and nothing else, so a hiker who takes a zero every Sunday had to add seven by hand to a fifty-day plan and lost them on the next re-lay. A plan now carries `rhythm: { everyDays, kind }` and `lib/restRhythm.ts` inserts the rests — a **zero** where you stand, or a **nearo** to the first place to sleep inside `NEARO_MAX_MI` (`@unvalidated`), falling back to a zero and saying so when nothing is inside the window. It does not re-plan the remainder: a rest lands at a boundary the generator already chose, and the day after a nearo is shorter by whatever the nearo walked, which is true and which the timeline prints. It has no opinion — nothing suggests a rhythm, warns about its absence, or counts the rests taken.

**The food carry is now visible** (#799). `foodCarries()` derives one carry per section, so the food block and the timeline read the same `planSections()` and cannot disagree. Two things it says that nothing said before: **a plan with no resupply anywhere** used to never print the word food, which reads as "no food needed" rather than "all nine days are on your back"; and a carry at or past `LONG_CARRY_DAYS` (`@unvalidated`) gets one line saying that is the heaviest the pack gets — a note, never a warning, because a long carry is a fact about a stretch of trail with no towns on it.

That work also fixed a real defect in the zero question this document leaves open. Zeros count against the carry — the answer `lib/plan.ts` picked, erring toward carrying enough — but `insertZeroAfter` duplicated the boundary *including its resupply flag*, which closed a second section holding just the zero. So a zero in town read as its own one-day carry and vanished from the carry it actually eats from. The duplicate no longer inherits the flag: supplies are picked up once, at the stop the hiker walked into.

## Open questions (for you, not decided here)

- **Whether a zero in town counts against the food carry.** Named above. A day's food on someone's back, and both answers are defensible.
- **What the target actually asks for** — walking hours, elapsed hours, or miles. Time is the better instrument (Finding 4) and miles is what every hiker already thinks in.
- **Whether "absorb" is allowed to change where a resupply happens.** Re-balancing days is safe; silently moving which town someone buys food in is not obviously safe, and the pin mechanism may need resupply stops pinned by default.
- **Whether generated days should be visibly marked as generated.** The `generated` flag is in the model above so the option exists; whether the timeline shows it is a UX call about how much the app should admit it guessed.
- **How side trails become routable**, which is the real blocker on this being a plan someone keeps rather than a sketch. Related to [SPUR_TRAILS.md](SPUR_TRAILS.md)'s spur-destination work and to [MAP_OPTIONS.md](MAP_OPTIONS.md)'s snap-to-segment.
- **How a first leg that starts mid-segment is described**, now that a tap splits the segment rather than snapping to a junction (#934). Still open, and narrower than it was: the on-trail cards (#1041) need no junction name, so what is left is the whole-walk turn list somebody reads before they go. See "The day hike on a network" above for the option that looks right and was not decided.

## Suggested build order

Each phase is useful on its own, which is deliberate — none of them is a bet on the next one landing.

| Phase | What | Depends on |
|---|---|---|
| **A** | Publish `mile` on every POI (Findings 1 and 2). | Nothing. Do this first regardless of what follows; it also fixes a real, existing inconsistency. |
| **B** | The route builder: drop points, distance, gain, loss, ≈time. Adds `cumulativeLossOverGaps()`. | A, for trustworthy per-stretch gain. |
| **C** | Multi-day: days as Segments, the timeline, zero days and resupply flags, food as days. | B. |
| **D** | The auto-generated plan. | A and C. `spike_day_planner.py` should have been run against real data by here. |
| **E** | The cascade, with pins. | C, and worth D existing first — "absorb" is the generator re-run. |

## Running the spike

```
cd pipeline
python spike_day_planner.py            # needs data/raw from fetch_all.py
python spike_day_planner.py --targets 12,15,18 --cap 25
```

It reports what Q1 asks for: the real spacing distribution of designated stops, how close a generated plan gets to a range of targets, what the worst day looks like, and what campsites buy over shelters alone. It was **not** run while this document was written — the environment it was written in has no route to ATC's servers — so every number in it is still unmeasured, and the table in Finding 3 is arithmetic over counts from `pipeline/README.md` rather than a measurement of spacing. That is the first thing to close.
