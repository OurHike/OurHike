# OurHike — The Corridor View (Feature Design Draft v1)

Companion to [POI_VISIBILITY.md](POI_VISIBILITY.md) (which owns the map *above* this doc's seam),
[MAP_OPTIONS.md](MAP_OPTIONS.md), [VOLUNTEERING.md](VOLUNTEERING.md),
[SAYING_THANKS.md](SAYING_THANKS.md), [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md),
[EVENTING.md](EVENTING.md) and [../OurHikeValues.md](../OurHikeValues.md) #1.

Answers [#532 — Decide what the zoomed-out map shows instead of pins: cluster counts, or the
waypoint lanes](https://github.com/OurHike/OurHike/issues/532), and answers it with neither.

---

## The first map a hiker ever sees is an empty line

`CORRIDOR_BOUNDS` in [`App.tsx`](../client/src/App.tsx):240 opens the app on the whole 2,197-mile
corridor, which lands near z4 on a phone. `POI_MIN_ZOOM = 9` means no waypoints. So the opening
screen is a thin line down fourteen states with nothing on it, and the legend says *Nothing on
this part of the map yet — pan or zoom out to see more*, which is false in both halves.

Every previous answer to this took the same shape: find something to draw **in place of the
waypoints that were deleted**. Count bubbles that expand on tap; the elevation ribbon's waypoint
lanes driven from the viewport instead of the GPS fix. Both are written up in
[POI_VISIBILITY.md](POI_VISIBILITY.md)'s history, and #532 exists to choose between them.

**Neither is what a zoomed-out map is for.** A hiker at a kitchen table looking at fourteen states
is not asking *how many privies are in Virginia*. A line of bubbles reading 312, 289, 410 down a
uniformly dense trail answers a question nobody has. The corridor view has a subject of its own,
and the waypoints are not it.

## The seam

[POI_VISIBILITY.md](POI_VISIBILITY.md) owns the number — **`POI_PIN_MIN_ZOOM = 12`**, measured
2026-08-13 by [`pipeline/spike_poi_seam.py`](../pipeline/spike_poi_seam.py) rather than argued.
Below it, this doc. Above it, that one.

**So this view owns z0–z11**, which on a phone is everything from the whole corridor at about z4
down to a screen holding roughly 3.5 × 6.4 miles of ground. That is the full range in which
somebody is choosing where to go rather than looking at where they are, which is the right span
for a screen about exploring.

The property that makes the split honest, and it is the whole reason this is a separate doc:
**below the seam the map is not an incomplete map of places. It is a complete map of something
else.** All thirty club sections, all of the stretches. Nothing sampled, nothing dropped, nothing
needing a caption that admits it. There is no visibility problem down here because visibility is
not the subject.

---

## What it carries

### 1. The thirty clubs, and the data is already on disk

The A.T. is maintained by thirty clubs, and ATC publishes one polygon each.
`trail_club_sections` is **already registered in [`pipeline/sources.json`](../pipeline/sources.json)
and downloaded by every pipeline run since 2026-07-25** — `pipeline/README.md` records it as
fetched for "the maintainer attribution" with nothing downstream reading it.
[SOURCE_REGISTRY.md](SOURCE_REGISTRY.md) opens on the same fact from the other direction.

So the corridor view's primary content costs one exporter and no new source. Below the seam the
trail draws as thirty named stretches rather than one line, and tapping one says who looks after
it — which is a question this app already cares about in three other places
([VOLUNTEERING.md](VOLUNTEERING.md), [SAYING_THANKS.md](SAYING_THANKS.md), the backend's `Club` and
`MaintainerAssignment` models) and has never been able to answer on the map.

**Two data problems to settle before the app states club attribution as fact**, both already
recorded in [`pipeline/SOURCE_SURVEY.md`](../pipeline/SOURCE_SURVEY.md) and neither discovered
here:

- That layer's data is dated **2024-08-15** — "two years old", in the survey's own words, with
  the schema touched 2025-10-09.
- There is a **fresher sibling**, `AT_ClubMap` (5 layers, 2025-06/07), whose 35 club-name points
  include Randolph Mountain Club, *which the 30-polygon layer folds into somebody else*. So the
  two sources disagree about how many clubs there are and about who maintains at least one
  stretch.

Thirty-versus-thirty-five is exactly the kind of disagreement this app must not resolve by
picking the one that was easier to parse. Whichever is published, the club attribution carries
its source and date the way every other published claim here does.

### 2. Stretches worth going to

The second half, and the one that makes the corridor view a thing to *explore* rather than a thing
to read: named stretches of trail — Roan Highlands, Franconia Ridge, McAfee Knob, Grayson
Highlands, Mahoosuc Notch — each with a mile range, a length, an ascent, a Naismith time, and a
reason it is named.

**The numbers cost nothing.** `export_elevation.py` already ships ~141,000 samples at 25 m
(0.87 MB gzipped, offline), `elevationGain.ts` computes confirmed ascent over any window with the
3 m dead band that keeps DEM noise out, and `naismith.ts` turns distance plus ascent into a
duration. A stretch is two mileposts; everything else is derived from artifacts already on the
phone.

**The list is the hard part, and "popular" is three different questions.**

---

## "Popular" is three questions, and the app should answer all three separately

The ask was *popular hikes*. The word hides three claims with completely different evidence behind
them, and the failure mode is blending them into one number that means none of them — which is
the same failure as the count that read zero.

So: **one record type, three bases, and the app never says "popular" flatly.** It says what it
knows and where it came from.

| basis | what it actually claims | evidence | when it ships |
|---|---|---|---|
| `named` | This stretch is well known | A curated in-repo list, each entry with a citation | v1 |
| `published` | ATC lists this as a hike | ATC's own day-hike material and the `communities` layer, through the pipeline | when the source is registered |
| `visited` | Hikers using this app sent something from here | Counted from reports, photos and thanks that already carry a mile | fills in over time; ships empty |

### `named` — curated, cited, and the only one that works on day one

Twenty or thirty entries in the repository, each carrying a source. Not a ranking, not a score: a
list of stretches that a reasonable person would agree are known, with the reason attached. It is
editorial, it says so, and it is the honest way to have something on the screen before there is
any data.

Cheap to be wrong about and cheap to fix, which is the argument for starting here rather than
waiting for either of the other two.

### `published` — ATC's, not ours

ATC publishes day-hike material and `communities` is already source [7] in `sources.json`. An
entry sourced this way is attributable to ATC rather than to us, which is strictly better than
`named` for the same stretch, and the two coexist: the same stretch can carry both bases, and the
stronger one is what the app cites.

This is ordinary [SOURCE_REGISTRY.md](SOURCE_REGISTRY.md) work — register the source, record its
freshness, publish with attribution — and it is not blocked on anything.

### `visited` — real, and it must not come from analytics

This is the one that could go badly, so the rule is worth stating before the feature is:

**Never from the eventing pipe.** [EVENTING.md](EVENTING.md)'s rule 2 is *"No geography, ever. No
coordinates, no mile, no segment id, no POI id, no region"*, and it is not a preference — it is
the finding [#252](https://github.com/OurHike/OurHike/issues/252) already paid for, that a stable
identifier next to a trail position and a time is a hiker's route down the corridor, recoverable
with `curl`. A popularity metric built on analytics is a machine for producing exactly that pair.

**From the records that already exist, instead**, which is [EVENTING.md](EVENTING.md) §4's own
rule — *do not instrument what the server already knows*. A report carries a mile
([`report.py`](../backend/app/models/report.py):134) because a blowdown with no location is
useless; photos and thanks carry one for the same reason. These are things a hiker **chose to
publish**. Counting them is not new collection, and it survives an opt-out and a dropped queue,
which an event stream does not.

Three constraints on the output, and the first is borrowed rather than invented:

- **No published cell below k = 25**, [EVENTING.md](EVENTING.md) §6's suppression floor, applied
  at the query layer so the slice nobody thought about is covered too. A count of three is a
  description of three people.
- **Coarse grain.** A stretch, never a point and never a POI. The whole hazard is precision.
- **Labelled as what it is.** This measures *where hikers using this app sent something*, not
  where people hike. It is biased toward where the app has users, toward the kind of terrain that
  generates reports, and it lags. The app says the former; it must never imply the latter.

And it ships empty. On day one every stretch is `named`, and that is fine — a feature that fills
in as the app is used is a feature that improves without anybody shipping anything, which is rare
enough to be worth designing for.

### The rule that holds the three together

**No blended score.** No weighting `named` against `visited` into a single number, no sort order
that implies a ranking across bases. The three answer different questions and a hiker reading
"popular" deserves to know which one they are being told. `OurHikeValues.md` #1's warning about
prescriptive gamification is the same instinct pointed at a different feature: a leaderboard of
trail sections is exactly the thing that tells people there is a right way to hike.

---

## What this is instead of

#532 asked for a decision between two options and this is a refusal of both, so the reasons
belong here rather than in a commit message.

**Not cluster bubbles (#532 Option A).** They are a density map of a uniformly dense trail; they
break the tap path, since `poiTaps.ts` resolves to a `poi_id` that cluster features do not carry
and `getClusterExpansionZoom` is async; and they re-cluster on every zoom, so a group tapped at z5
and at z7 is two different things wearing one appearance. The deeper objection is the one at the
top of this doc: they answer *how many waypoints are hidden here*, which is only a question if
you have accepted hiding them. [POI_VISIBILITY.md](POI_VISIBILITY.md) stops hiding them.

**Not the waypoint lanes driven from the viewport (#532 Option B).** The lanes are good and the
idea was the strongest thing in the old design — but a 2,197-mile window collapses them into a
handful of pills reading in the hundreds, and it puts a second, differently-derived window beside
the elevation ribbon's when [../WIREFRAMES.md](../WIREFRAMES.md) §1.3–1.4's whole point is that
the two agree about what stretch they are showing. The lanes stay what they are.

**Not a trip planner.** [HIKE_PLANNING.md](HIKE_PLANNING.md) and [SEGMENTS.md](SEGMENTS.md) own
planning and are v2. This is a map that shows what is out there; the moment it starts holding a
route someone is building, it is that feature and should be built there.

---

## Data model

Two published artifacts, both small, both offline-first like everything else here.

**Club sections.** The exported `trail_club_sections` geometry plus, per club, its name, its mile
range, and the source date it came from. Thirty features. The backend already holds `Club` and
`MaintainerAssignment` for the *authoritative* answer used when a thanks is resolved
([`maintainerLookup.ts`](../client/src/lib/maintainerLookup.ts) is the client's half); this is the
map's copy for drawing and for working offline, and where the two disagree the backend is right.

**Stretches.**

```
Stretch
  id                  stable, minted in the pipeline - a stretch is referenceable
  name
  start_mile, end_mile
  bases: [ named | published | visited ]   - one or more, never blended
  citation per basis                       - who says so, and when
  visited_count                            - suppressed below k=25, absent otherwise
```

Length, ascent, descent and Naismith time are **not** stored. They are derived on the phone from
the elevation profile it already has, which keeps one number in one place and means a better
profile improves every stretch without a republish.

No new preference keys.

---

## Open questions (for you, not decided here)

- **Thirty clubs or thirty-five.** `trail_club_sections` (30 polygons, 2024-08-15) against
  `AT_ClubMap` (35 club-name points, 2025-06/07). The newer one is not the same shape — points,
  not polygons — so it cannot simply replace the older, and Randolph Mountain Club exists in one
  and not the other. Needs a look at both services before either is published.
- **How many `named` stretches, and who writes them.** Twenty is a screen; two hundred is a
  gazetteer and a maintenance burden. And an editorial list in a repository is a thing somebody
  has to own.
- **Whether a club section is tappable below the seam only.** Above the seam it would be a
  polygon over a map a hiker is navigating by, which is clutter; but "who maintains where I am
  standing" is a good question at any zoom, and the status strip or the attribution line may be
  the better home for it there.
- **Whether `visited` should count *downloads* too.** A map package downloaded from R2 is a
  server-side record ([EVENTING.md](EVENTING.md) §4 lists it), it is geographic by construction,
  and it is arguably a better signal of intent than a report is — a hiker downloads a sheet before
  going, and reports only if something is wrong. It is also the one that most needs the k floor.
- **What the corridor view does with a hiker who has a GPS fix.** Opening on the whole trail is
  right for planning at home and wrong for someone standing on it. `cameraMemory.ts` already
  decides this; the corridor view should not re-decide it.
- **Whether this is v1.** #532 is labelled `research` and deliberately did not assume its build
  falls inside v1. The club sections are cheap enough to argue for; the `visited` basis plainly is
  not, and ships empty regardless.
