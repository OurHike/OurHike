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
