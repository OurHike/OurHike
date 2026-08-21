# OurHike — The Elevation Ribbon (Feature Design Draft v1)

Companion to [../WIREFRAMES.md](../WIREFRAMES.md) §1.3 and §1.4, [../FEATURES.md](../FEATURES.md)'s elevation line, and [PERSONALIZED_PACE.md](PERSONALIZED_PACE.md).

Covers the phone's elevation ribbon and the three waypoint lanes beneath it. **Not** the desktop's full interactive chart, which is a separate component with its own selection model.

**Scope note up front: almost all of this already exists.** `chrome/ElevationRibbon.tsx` and `chrome/WaypointLanes.tsx` are built and tested. `MapScreen` accepts both as optional props. `lib/elevationGain.ts` counts confirmed ascent, `lib/waypointLanes.ts` clusters pins, `lib/naismith.ts` gives the time estimate, and `pipeline/export_elevation.py` publishes the profile. What was missing is the wire between the last two, plus the two decisions below — neither of which is plumbing, which is why they are written down before the code rather than settled by whoever typed it.

---

## What the published profile actually is

`pipeline/export_elevation.py` samples the real merged centerline every 25 m and writes a JSON array of `{distance_mi, elevation_ft}`, sorted by distance. `distance_mi` is rounded to 3 decimals, `elevation_ft` to 1. A sample the DEM does not cover carries `elevation_ft: null` — a real coverage gap, kept in the array so the distance axis stays continuous.

Measured against a synthetic array of the real shape and record count:

| | |
|---|---|
| samples, full corridor | ~141,000 |
| raw JSON | **6.5 MB** |
| gzipped over the wire | **0.87 MB** |
| as `{distanceMi, elevationFt}` objects in JS | ~7–10 MB resident |
| as two `Float32Array`s | **1.1 MB** resident |

That settles the sizing question the ribbon was blocked on. **0.87 MB is not the thing to worry about** — `trails.geojson` is twelve megabytes of coordinates and the topo archive runs to 1.18 GB, so the profile is under 7% of what the corridor download already costs. It is fetched whole rather than windowed, because the whole point is that it works in a dead zone fifty miles from where it was downloaded.

The resident figure is the one worth acting on, and it is why the client stores the profile as two parallel `Float32Array`s rather than an array of objects. A DEM gap becomes `NaN`, which `cumulativeGainOverGaps` already treats as a break in the run — so the compact form costs no special-casing. Float32 resolves 0.2 m at mile 2,190, well under the 25 m sample spacing and the DEM's own ~10 m posting.

---

## Decision 1 — the window is 10 miles: one behind, nine ahead

Nothing in WIREFRAMES.md or FEATURES.md fixed this, and it has to be fixed because it is what the lanes cluster against: `lib/waypointLanes.ts` collapses pins closer than 1.5% *of the window*, deliberately, since overlap is a rendering problem rather than a distance one.

**Nine miles ahead**, for three reasons that agree:

- **AT shelters average about eight miles apart.** A nine-mile look-ahead almost always holds the next one, so the SLEEP lane has something in it. A lane that is routinely empty teaches a hiker that the lane is broken, and they stop reading it.
- **It is four to five hours at a loaded pace**, which is the horizon at which *push on or stop here* is actually decided. That is the decision FEATURES.md promoted this feature into MVP for.
- **1.5% of ten miles is 0.15 mi**, finer than typical spacing between water sources, so springs stay individually tappable instead of smearing into one count pill.

Longer breaks all three. At a forty-mile window the collapse threshold becomes 0.6 mi and the water lane degenerates into a row of pills, while a 1,000 ft climb occupies 2% of the width and reads as flat. Shorter breaks the first: at three miles the ribbon frequently shows less than the climb the hiker is standing on.

**One mile behind**, because the "you are here" rule needs somewhere to be. With the window starting exactly at the hiker it sits pinned at x=0 on every frame, which indicates nothing. One mile back puts it at 10% and shows the tail of the climb just finished — which is the context for *how much of this is left*.

### Direction

Ahead means decreasing mile for a southbounder, so the window mirrors: one mile north, nine south.

`lib/hikeDirection.ts` deliberately does not know the direction until the hiker has moved a quarter mile, and there is no onboarding question to ask instead. For that first quarter mile the window is **centred** — five miles either side — rather than assuming NOBO. Assuming is a confident-looking answer that is wrong for half of everyone, and it is the same mistake the opening camera already declined to make when it stopped defaulting to Harpers Ferry. A centred window says "here is the ground around you" without claiming to know which way anyone is facing, and it resolves to the asymmetric window as soon as the direction does.

### At the terminuses

Within ten miles of Springer or Katahdin the window would run past the end of the profile. It **slides** rather than shrinks, keeping the full ten-mile span against the end of the trail. The "you are here" rule leaves its 10% position and walks to the edge, which is exactly what is happening on the ground.

### Not a preference

The window is one constant, not a setting. [UX_CUSTOMIZATION.md](UX_CUSTOMIZATION.md) takes the position that options are a cost paid by everyone to satisfy a few, and a hiker cannot form an opinion about a window length before they have used one. If field testing (#105, #106) says ten miles is wrong, the fix is a better constant.

---

## Decision 2 — the upcoming climb is the next ≥300 ft ascent inside the window

`lib/elevationGain.ts` answers "how much ascent between these two mileposts". Picking *the next climb* out of a profile is a different question, and had no implementation.

**The rule.** Walk forward from the hiker through the window, using the same 3 m dead band `cumulativeGain` uses to decide a turning point is real rather than DEM noise. The first trough-to-peak run whose confirmed ascent reaches **300 ft** is the upcoming climb. Its start is that trough, its end is the peak, and its ascent is `gainBetween(start, peak)` — the same function everything else counts gain with, so the callout can never disagree with a total computed elsewhere.

**If the hiker is already on it**, the start clamps to their current mile and the ascent is recounted from there. The callout is a claim about work not yet done; printing `+640 ft` when four hundred of those feet are behind them is the kind of wrong this codebase spends its comments avoiding.

**Only inside the window.** A climb past the right edge cannot be highlighted on a ribbon that does not draw it, and a callout describing off-screen ground would be a caption for nothing.

### Where 300 ft comes from

Not a round number picked because it looked reasonable. `naismithTime` rounds to five-minute steps, and Naismith gives one hour per 600 m of ascent — so **164 ft of ascent is exactly one rounding step**. Below that, a climb cannot move the number the callout prints: the ribbon would highlight a region and then caption it with a time indistinguishable from flat ground, which is worse than highlighting nothing.

300 ft is comfortably clear of that floor (about nine minutes of Naismith time on top of the walking) and is roughly where a climb starts to be a pacing decision rather than a bump. It is also far below anything a hiker would name — Albert Mountain is ~500 ft, Blood Mountain ~1,400 ft, a Presidential day 3,000–4,000 ft — so the filter never removes a climb anyone would have wanted flagged.

The threshold sits next to the dead band in one module. They are different quantities and it is worth not confusing them: 3 m is *what the DEM can resolve*, 300 ft is *what a hiker cares about*.

### When nothing qualifies

No highlight, no callout, and the profile still draws. Rolling ridge with nothing over 300 ft in the next nine miles is a true and useful thing to show, and `MapScreen` already treats `upcomingClimb` as optional for precisely this reason.

---

## What this deliberately does not do

- **No personalised pace.** The callout is flat Naismith. [PERSONALIZED_PACE.md](PERSONALIZED_PACE.md) is where an observed pace would come from, and it is Post-MVP; wiring a half-built pace model into a safety-adjacent number is worse than a rule that is known to be conservative.
- **No descent.** `naismithTime` structurally refuses a descent parameter and this does not route around it.
- **No arrival clock.** A duration, always prefixed `≈`.
- **Nothing when there is no fix.** Without a position there is no "ahead", so both the ribbon and the lanes are omitted rather than defaulting to mile zero. Same for a release that publishes no profile. **Qualified by #910** — see "The same ribbon, asked the desk's question" below.
- **The desktop chart (#135) is not this.** It will want its own window — probably a selectable one — and shares only `lib/elevationGain.ts`. Built, and it does: `chrome/ElevationChart.tsx` over `lib/chartProfile.ts`.

---

## The same ribbon, asked the desk's question (#910)

The line above was right about the question and wrong about the *device*. "Without a position there is no ahead" is a fact about the field question. It is not a fact about the phone, and treating it as one meant that a hiker planning a trip at their kitchen table on the phone they would carry saw no terrain at all, while the same person on a laptop got the whole chart banding the stretch they were laying out.

So while the route builder is open, `lib/planRibbon.ts` builds the ribbon's props from **the draft's stretch** instead of from a fix, and the phone draws that. Everything below is what did *not* move, and each has a reason already on this page:

- **No upcoming climb.** The callout is a claim about work not yet done — the whole reason Decision 2 clamps the start to the hiker's current mile. A planned stretch has no walker, so there is no "not yet" to be right or wrong about.
- **No "you are here" rule unless the fix is genuinely inside the stretch.** Clamped to an edge by the SVG viewport, the rule would read as *you are at the start of this*. That is a claim about somebody's position, which is the one thing this surface must never guess at.
- **No waypoint lanes.** `lib/waypointLanes.ts` collapses pins closer than 1.5% *of the window*, a threshold Decision 1 sized against ten miles precisely so springs stay individually tappable. On a 60-mile plan it is 0.9 mi and the water lane degenerates into the row of count pills that decision names as the reason the window is not longer. The lanes stay with the fix or they are not drawn. **Reversed the same week — see "The lanes go with it" below.** The arithmetic was right and it was weighed against the wrong thing.
- **No figures.** Distance, climb and ≈time belong to `RouteStopsPanel` and `RouteEntranceSheet`, which price the walk at the hiker's own pace through `lib/route.ts`'s `legFigures`. A second time derived a second way is exactly the disagreement one source of truth exists to prevent. The ribbon contributes the shape, which is the thing that was missing.

**Decimation is the chart's, not a new one.** A thru-hike stretch is ~141,000 samples; `lib/chartProfile.ts`'s min-max envelope is reused at its own 1,200-bucket default. That count is *reasoned*, not re-measured for the phone: 1,200 buckets was sized for ~1,200 device pixels, and a 390 px phone at 3× is ~1,170 of them — the same order, so a second constant here would be a number nobody checked. If a phone ribbon ever looks visibly coarse, the fix is a measurement, not a guess.

**What this deliberately still does not do:** dragging the phone ribbon to re-stretch the route. The chart's selection is a 1,000-unit-wide instrument with a drag threshold, keyboard stepping and a zoom; the ribbon is 54 px of orientation. Seeing the ground is the gap that was worth closing — a second editor is not.

---

## The lanes go with it — POIs along the stretch being planned

The bullet above refused the three waypoint lanes on the planning ribbon, and the number in it is not in dispute: a pill really does swallow `COLLAPSE_THRESHOLD_PCT` — 1.5% — of whatever window it is drawn in, so on a 60-mile plan it stands for 0.9 mi of trail. What the refusal weighed that against was *the ten-mile ribbon's legibility*, which is not the alternative on this screen. The alternative was **an empty strip under the profile**, read by a hiker laying out an evening as "there is nothing along here" — a claim about water, on a surface where the shape of the ground had just been added because a picture beats a table of figures.

So the lanes are drawn over the planned stretch (`planLanes` in `lib/planRibbon.ts`), and the coarseness is accepted and named rather than avoided. A pill reading `3 water` over nine tenths of a mile is coarse **and true**; it is also the wireframe's own answer to crowding (WIREFRAMES.md §1.4), not a new invention for this screen.

Four things hold it up:

- **The pins are placed on the pipeline's mile axis, never the client index's.** The field lanes read `searchablePois`, whose mile comes from `lib/trailPosition.ts`; this ribbon is drawn from the published profile, and a POI's own published `mile` (#753) is the only value on that axis. Mixing them is [HIKE_PLANNING.md](HIKE_PLANNING.md) Finding 1, and here the two would be visible side by side — a pin a couple of tenths off the climb it is meant to sit under.
- **The window is the ribbon's own drawn ends, not the draft's stretch.** `envelopeSamples` starts at the first sample the DEM actually has, so a stretch that opens in a coverage gap draws from further along. Taking the samples' ends makes "a pin at 60% sits under the part of the profile it belongs to" true by construction.
- **Refused rather than emptied, in the one case that would lie.** A download published before #753 carries no POI miles at all. Empty lanes there would report "nothing along this stretch" about POIs the app simply cannot place; no lanes says the honest thing. A download that *has* miles and genuinely holds nothing on the stretch draws empty lanes, because that emptiness is a fact about the trail.
- **A span ceiling, derived rather than picked.** `MAX_LANE_SPAN_MI` is `8 / 0.015` ≈ **533 miles**: eight miles is the shelter spacing Decision 1 already rests its look-ahead on, and where a pill swallows that much ground a lane is all pills — it has stopped naming places and started drawing density. Past it the lanes are dropped, which is what keeps a whole-trail ribbon (asked for on PR #911) from wearing three rows of them. Worth being straight about what that number is and is not: it is **reasoned, not measured**, and eight miles is the *only* lane spacing this repository has a figure for. Water — the lane a hiker planning an evening is likeliest to be reading — has no census here, and the published counts in [pipeline/README.md](../pipeline/README.md) point to it being sparser than the shelters rather than denser, which would make a tighter bound the right one. So this marks where the lanes stop being lanes, not where they stop reading well. A census off `export_poi.py`'s published miles would settle the water-shaped bound.

**Staleness rides along**, through the same `stalenessPresentation` lookup the field lanes use (#759). One callback feeds both, because a spring that is stale in the field is stale on a plan and two lookups would be two chances to disagree about it.
