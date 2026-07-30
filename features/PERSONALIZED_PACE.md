# OurHike — Personalized Pace Estimates (Feature Design Draft v1)

Companion to [TRIP_PLANNING.md](TRIP_PLANNING.md), [SEGMENTS.md](SEGMENTS.md), [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md), [../OurHikeValues.md](../OurHikeValues.md) and [../WIREFRAMES.md](../WIREFRAMES.md).

Naismith's Rule is the right starting point and the wrong finishing point. It answers "how long does this take *a* hiker" when what someone actually wants is "how long does this take *me*, today, with this pack, on this ground."

This designs the path from one to the other: keep Naismith as the base and the cold-start default, let it be adjusted by hand, and let it learn from what the hiker has actually been doing — on device, without ever becoming a performance tracker.

---

## Why Naismith alone isn't enough

Naismith is 5 km/h plus one hour per 600 m of ascent. It is a **comparative** instrument: useful for saying this stretch is harder than that one, and for planning at the scale of a day. It was never a personal prediction, and it has three specific gaps for our use.

**It ignores descent entirely.** Not an oversight — the original rule genuinely has no descent term. But descent is not free: gentle downhill is faster than flat, and steep sustained downhill is *slower* than flat while wrecking your knees. Naismith scores a 3,000 ft descent identically to walking the same distance on the level.

**It is linear in ascent, and real pace is not.** A 5% grade barely slows anyone; a 25% grade slows everyone dramatically and non-proportionally. One coefficient across all steepness understates hard climbs and overstates easy ones.

**It knows nothing about the individual.** Fitness, pack weight, age, injury, and how many days into a thru-hike someone is all move pace more than the terrain does — and all of them change over a season.

The hiker's own framing of this, worth keeping in the doc because it sets the accuracy bar honestly: *time varies with mood, weather, trail conditions, steepness, and a lot else besides.* Most of that is unobservable. **A model that pretends otherwise is worse than one that admits it**, which is why the output below is a range rather than a number.

## A deliberate supersession, stated plainly

Two existing decisions are being changed here on purpose, and both were written to resist accidental change:

**1. `client/src/lib/naismith.ts` has no `descentFt` parameter, deliberately.** Its comment reads: *"not just 'ignored if passed' but structurally absent, so a future call site can't accidentally wire descent in without touching this function's signature first."* This document is that touch. Descent is now in scope — but the guard did its job, and the replacement should keep the same property: a `naismithTime()` that silently starts crediting descent would be a regression, so the personalized estimator is a **new function alongside it**, not a mutation of it.

**2. [../WIREFRAMES.md](../WIREFRAMES.md)'s load-bearing values** state: *"no descent credit (a known weakness of the rule — don't silently 'improve' it)."* The operative word was *silently*. This is the non-silent version, and WIREFRAMES.md should be amended to point here rather than left contradicting.

Everything else in that entry stays: rounded to 5 minutes, always prefixed `≈`, **never shown as an arrival clock**. Personalization makes those constraints more important, not less — see "The honest output" below.

## Design

### 1. Three layers, in order of authority

```
  base        Naismith                      always available, needs nothing
  manual      hiker-adjusted coefficients   overrides base
  learned     fitted from observations      shrinks toward whichever is below it
```

**Base** is what a fresh install uses, and what everything falls back to. It is never wrong, only generic.

**Manual** is a small set of controls: base flat pace, ascent penalty, descent penalty. Some people know their numbers, and a hiker who has been walking for thirty years should not have to wait a week for the app to discover what they already know.

**Learned** is fitted from what actually happened. It never replaces the layer below it outright — it *shrinks* toward it, weighted by how much evidence exists (see confidence, below). With two observations the estimate is essentially Naismith; with two hundred it is essentially the hiker.

### 2. Steepness tiers, because pace-vs-grade is not linear

Rather than one ascent coefficient, bucket each stretch by grade and learn a multiplier per bucket:

| bucket | grade | why it is its own tier |
|---|---|---|
| steep descent | < −20% | slower than flat; braking, careful footing |
| moderate descent | −20% to −5% | genuinely faster than flat |
| flat | −5% to +5% | the base pace |
| moderate ascent | +5% to +20% | Naismith's linear term works reasonably here |
| steep ascent | > +20% | where Naismith most understates |

This is not invented: the shape matches Langmuir's corrections to Naismith (which add descent terms) and Tobler's hiking function (which is exponential in slope). Bucketing rather than fitting a continuous curve is a deliberate simplification — it needs far less data per parameter, and with a rolling window there is not much data.

**Grade comes from the elevation profile we already ship** (`elevation_profile.json`, 25 m sampling), so this needs no new pipeline data.

⚠ **One caution carried over from that export:** cumulative ascent computed at 25 m over-counts, because fine sampling accumulates DEM noise as fake climbing — measured at 594,520 ft against the ~510,000 ft consensus figure, with 100 m sampling landing at 511,954 ft. **Grade classification and ascent totals should be computed from a decimated view of the profile, not the raw 25 m series.** Feeding inflated ascent into a pace model would teach it that the hiker is faster than they are, in exactly the terrain where being wrong matters most.

### 3. Moving time, not elapsed time — the thing that makes or breaks this

A hiker stops. For water, for a view, for lunch, for forty minutes at a shelter. Elapsed time between two points includes all of it, and a model trained on elapsed time learns that this hiker is extremely slow and highly erratic — which is both useless and, since it would inflate every estimate, actively harmful.

**Observations must record moving time**, with stops detected and excluded (a sustained low-movement window, reusing the same trailing-GPS-window machinery [HIKER_SAFETY.md](HIKER_SAFETY.md)'s wrong-way detector already needs).

This is the single most likely thing to quietly ruin the feature, which is why it is called out at design level rather than left as an implementation detail.

### 4. What gets stored, and where

```
PaceObservation          on device only - never synced, never uploaded
  at                     when
  distance_m             horizontal distance covered
  ascent_m, descent_m    from the decimated elevation profile
  grade_bucket           one of the five above
  moving_seconds         stops already excluded

PaceProfile              derived, recomputed on demand
  per bucket: multiplier vs Naismith, sample count, observed spread
  manual overrides, if the hiker set any
```

**On device only.** [IDENTITY_AND_PRIVACY.md](IDENTITY_AND_PRIVACY.md) is unambiguous and onboarding makes the promise out loud: *"position never leaves the phone."* A pace history is a movement history — where someone was, when, and how fast. It is among the most sensitive things this app could hold, and it buys nothing by leaving the device. **This is not a sync target even when an account exists**, which makes it a deliberate exception to the "preferences sync once linked" rule and should be recorded as one.

### 5. The rolling window

The hiker asked for a recommendation based on the previous 7 days, and recency genuinely matters — a thru-hiker's pace at week six is not their pace at week one, pack weight drops, and trail legs are real.

**Recommend weighted recency rather than a hard 7-day cutoff.** A hard window throws away everything on day eight, which on a sparse dataset is a lot to discard; and it makes the estimate jump for no reason the hiker can see. Exponential decay with a ~7-day half-life keeps the same responsiveness without the cliff. A hard window is simpler and defensible if the decay proves fiddly — flagged as an open question rather than decided.

### 6. The honest output: a range, not a number

This is the part personalization actually earns, and it is easy to miss.

Once there are real observations, the app knows not just the hiker's typical pace but **their spread** — how much they vary run to run. That variance is the honest answer to everything the model cannot see: mood, weather, trail surface, sleep, whether they are having a good day.

So the estimate should say:

> **≈2h 15m** — usually 2h to 2h 40m

rather than a lone `≈2h 15m` implying a precision nobody has. A wide range is not a failure of the model; it is the model correctly reporting that this hiker varies a lot, which is *true information* a planner can use.

**Confidence must be visible.** Early on, say so plainly — "based on your last 3 walks" — so nobody mistakes a two-sample fit for a personal law. And the `≈` stays, always, exactly as WIREFRAMES.md requires. **Still never an arrival clock**: a personalized number invites more trust than a generic one, which makes the no-clock rule more necessary here, not less.

## What this deliberately isn't

- **Not a fitness tracker.** No streaks, no personal bests, no "you were faster last Tuesday", no progress graphs. [../OurHikeValues.md](../OurHikeValues.md) #1 forbids prescriptive gamification and anything implying a right way to hike — and a pace model is about two design decisions away from a performance scoreboard. Everything here exists to answer *"how long will this take me?"* and nothing exists to answer *"am I doing well?"*
- **Not comparative.** Never against other hikers, never a percentile, never a leaderboard. The same restraint [VOLUNTEERING.md](VOLUNTEERING.md) already applies to volunteer hours.
- **Not a guarantee.** [TRIP_PLANNING.md](TRIP_PLANNING.md) already frames this as *"informational, not prescriptive… a helpful estimate, not a guarantee"*, and personalization does not upgrade it.
- **Not a reason to track people.** No background location. Observations come from foreground use the app already makes, consistent with [../TECHNICAL_ARCHITECTURE.md](../TECHNICAL_ARCHITECTURE.md)'s foreground-GPS-is-sufficient stance.

## Open questions (for you, not decided here)

- **Weighted decay vs a hard 7-day window.** Recommended decay above; the hiker asked for 7 days. Worth deciding on how jumpy the estimate feels in practice, not in the abstract.
- **The bucket boundaries.** −20/−5/+5/+20% is a reasonable first cut drawn from Langmuir/Tobler, not a measured one. Real observations will say whether five buckets is too many to fill.
- **Minimum evidence before showing a personalized number at all.** Shrinkage handles it mathematically, but there may be a floor below which showing "your pace" is misleading regardless of the maths.
- **Whether descent gets a manual control at all, or only a learned one.** Most people know their flat pace and can guess their climbing penalty; almost nobody has a number for descent.
- **Weather.** Named by the hiker as a real factor, and [HIKER_SAFETY.md](HIKER_SAFETY.md) already contemplates an NWS relay (Post-MVP, and flagged there as a genuine open tension about a second notification). Conditioning pace on weather is a natural later layer and explicitly not v1.
- **Whether any of this is MVP.** The base Naismith estimate already ships. Everything here is additive and none of it blocks the map working — this reads Post-MVP, but that is a scope call.
