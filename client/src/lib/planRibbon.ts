// The phone's elevation ribbon while a route is being planned (#910).
//
// The ribbon proper is a field instrument: it needs a GPS fix, because the
// question it answers is "what is ahead of ME" and there is no ahead without
// a here (features/ELEVATION_PROFILE.md, "What this deliberately does not
// do"). That is still right, and this file does not weaken it.
//
// Planning is a different question with the same shape - "what is this
// stretch of trail LIKE" - and it is the DESK question, which is why the
// desktop chart (#135) answers it with no fix at all. A hiker planning at
// their kitchen table on the phone they will carry is asking exactly that,
// and until this existed the phone answered it with nothing: the stops, their
// distances, their climbs and their times, and no picture of the ground.
//
// So this builds ribbon props from a STRETCH rather than from a fix. What it
// deliberately does not build:
//
//   - An upcoming climb. `upcomingClimb()` clamps its start to the hiker's
//     current mile because the callout is a claim about work not yet done. A
//     planned stretch has no walker and therefore no "not yet".
//   - Waypoint lanes. lib/waypointLanes.ts collapses pins closer than 1.5% OF
//     THE WINDOW, a threshold ELEVATION_PROFILE.md's Decision 1 sized against
//     ten miles. Over a 60-mile plan that is a 0.9-mile collapse and the water
//     lane becomes a row of count pills - the degeneration that decision names
//     as the reason the window is not longer. The lanes stay with the fix.
//   - A time, a gain or any other figure. Those belong to RouteStopsPanel and
//     RouteEntranceSheet, which price the walk at the hiker's own pace through
//     lib/route.ts. A second figure derived a second way is the disagreement
//     one source of truth exists to prevent; the ribbon contributes the shape.

import type { ElevationSample } from '../chrome/ElevationRibbon'
import type { ElevationProfile } from './elevationProfile'
import { envelopeSamples, type ChartDomain } from './chartProfile'

/** What `ElevationRibbon` needs to draw a planned stretch: assignable to
 *  ElevationRibbonProps, which is what MapScreen's `elevation` takes, with
 *  `units` left to the screen and `upcomingClimb` deliberately absent. Not
 *  declared as a Pick of that type - a `Pick` would say these three fields
 *  are the same fields, and `subject` is narrowed to one of its two values
 *  here on purpose. The assignability is checked by the shell passing it. */
export interface PlanRibbon {
  samples: ElevationSample[]
  currentMile: number | null
  subject: 'planned-stretch'
}

/** Two samples is the least that has a shape; one is a dot and none is a
 *  blank ribbon reading as "no terrain here", which is a claim. */
const MIN_DRAWABLE_SAMPLES = 2

/**
 * The stretch a route draft covers, drawn.
 *
 * `stretch` is on the PIPELINE's mile axis - the axis the published profile
 * and every route stop's `mile` share (#753, HIKE_PLANNING.md Finding 1) - and
 * so is `hereMile`. Mixing in a client-index mile here would put the "you are
 * here" rule a few tenths off the ground it claims, which is the fault
 * lib/route.ts's anchor carry exists to stop; callers pass `gpsPlanMile`.
 *
 * Undefined - not an empty ribbon - whenever there is nothing honest to draw:
 * no profile in this download, no two-ended stretch yet, or a stretch that is
 * entirely DEM coverage gap. MapScreen omits the whole block on undefined, the
 * same way it does for a fix-anchored ribbon it cannot build.
 */
export function planRibbon(
  profile: ElevationProfile | null,
  stretch: ChartDomain | null,
  hereMile: number | null,
): PlanRibbon | undefined {
  if (profile === null || stretch === null) return undefined

  const startMile = Math.min(stretch.startMile, stretch.endMile)
  const endMile = Math.max(stretch.startMile, stretch.endMile)
  if (endMile <= startMile) return undefined

  // The chart's own min-max envelope, at the chart's own bucket count. A
  // thru-hike stretch is ~141,000 samples and a path with a hundred points per
  // pixel is decided by paint order rather than by terrain (lib/chartProfile.ts
  // has the reasoning, and the reason it is min-max rather than an average).
  // The default bucket count is not re-tuned for the phone: 1,200 buckets was
  // sized for ~1,200 device pixels, and a 390 px phone at 3x is ~1,170 of them
  // - the same order, so a second constant here would be a number nobody
  // measured. Short stretches keep their real samples; the function only
  // decimates once there are more than two per bucket.
  const samples = envelopeSamples(profile, { startMile, endMile })
  if (samples.length < MIN_DRAWABLE_SAMPLES) return undefined

  return {
    samples,
    // Only when the fix is genuinely on this stretch. Outside it there is no
    // rule to draw - ElevationRibbon takes the same view of a mile past its
    // own edges, and the two agreeing is deliberate rather than redundant:
    // this one is about the ROUTE, that one about the samples that survived
    // the DEM.
    currentMile:
      hereMile !== null && hereMile >= startMile && hereMile <= endMile ? hereMile : null,
    subject: 'planned-stretch',
  }
}
