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
//   - Nothing about WHERE the pins are: `planLanes` below is the lanes over
//     the same stretch, and it is a separate function for one reason - it
//     reads a different axis. The ribbon is drawn from the profile; a pin is
//     placed from the POI's own published mile (#753), and only that one.
//   - A time, a gain or any other figure. Those belong to RouteStopsPanel and
//     RouteEntranceSheet, which price the walk at the hiker's own pace through
//     lib/route.ts. A second figure derived a second way is the disagreement
//     one source of truth exists to prevent; the ribbon contributes the shape.

import type { ElevationSample } from '../chrome/ElevationRibbon'
import type { ElevationProfile } from './elevationProfile'
import { envelopeSamples, type ChartDomain } from './chartProfile'
import { COLLAPSE_THRESHOLD_PCT, type Waypoint } from './waypointLanes'

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
  /** The stretch itself, which is what the ribbon's width stands for - given
   *  explicitly rather than left to the samples' own ends, because the lanes
   *  are positioned in the same 0-100 space and the two have to agree about
   *  which ground that width covers. `planLanes` reads it back. */
  domain: { startMile: number; endMile: number }
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
    domain: { startMile, endMile },
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

/** What the lanes need over a planned stretch: assignable to what MapScreen's
 *  `waypoints` takes, less the `onSelectPoi` that screen supplies itself and
 *  the `stalenessFor` the shell adds from its note roll-up. */
export interface PlanLanes {
  points: Waypoint[]
  startMile: number
  endMile: number
}

/**
 * A pin is placed from a POI's PUBLISHED mile and from nothing else, so this
 * is the shape `planLanes` reads - `StoredPoi` narrowed to the three fields it
 * uses. Optional `mile` is the load-bearing one: a download from before #753
 * carries no published mile, and there is no second way to get one on this
 * axis (lib/trailPosition.ts answers a different question with the same word).
 */
export interface PlaceablePoi {
  id: string
  type: string
  mile?: number
}

/**
 * The widest stretch the lanes still say something individual about.
 *
 * REASONED, from one figure this repository already stands behind: AT
 * shelters average about eight miles apart (features/ELEVATION_PROFILE.md
 * Decision 1, which sizes the fix window's nine-mile look-ahead on it). A pill
 * swallows `COLLAPSE_THRESHOLD_PCT` of whatever window it is drawn in, so on a
 * stretch of S miles it stands for 0.015 x S miles of trail. Where that
 * reaches a lane's own spacing, that lane is all pills: it has stopped naming
 * places and started drawing density, which is a different picture and one
 * nothing here asked for. 8 / 0.015 is about 533 miles.
 *
 * Two things it is not. It is not a claim that a 500-mile stretch reads well -
 * a pill standing for seven miles of trail is coarse, and this number only
 * says where the lanes stop being lanes at all. And eight miles is the ONLY
 * lane spacing this repository has a figure for: WATER, the lane a hiker
 * planning an evening is likeliest to be reading, has no census here, and
 * published counts (pipeline/README.md) suggest it is sparser than the
 * shelters rather than denser - which would make a tighter bound the right
 * one. Until somebody measures it off the published POI export
 * (`export_poi.py`'s `attach_miles`, #753) this is deliberately the generous
 * end: it is the number that keeps a whole-trail ribbon from wearing three
 * rows of pills, not a number that says a 400-mile plan reads well.
 */
export const MAX_LANE_SPAN_MI = 8 / (COLLAPSE_THRESHOLD_PCT / 100)

/**
 * The POIs along a planned stretch, for the three lanes under the ribbon
 * (WIREFRAMES.md §1.4) - the same lanes, over the ground being planned rather
 * than the ground being walked.
 *
 * #910 asked for none of this, on the arithmetic above: over a 60-mile plan a
 * pill swallows 0.9 mi. That is the reason the FIX window is ten miles and not
 * forty, and it is a real cost here - but it is a cost about legibility, and
 * the thing it was traded against turned out to be a hiker planning an evening
 * with no idea where the water is. A pill saying "3 water" over 0.9 mi of
 * trail is coarse and true; an empty strip under the profile says nothing at
 * all, and a hiker reads THAT as "nothing along here".
 *
 * The window is the ribbon's own `domain` - the stretch, which is what its
 * width stands for - and reading it back from there rather than recomputing it
 * is what makes "a pin at 60% sits under the part of the profile it belongs
 * to" (chrome/WaypointLanes.tsx) true by construction rather than nearly true.
 * The samples' ends are NOT that window and using them was a real bug while
 * this was being written: the profile is sampled every 25 m, the last sample
 * at or before a stretch's end is up to that far short of it, and the stop the
 * route is walking TO therefore dropped out of the SLEEP lane.
 *
 * Undefined - never empty lanes - when the pins cannot be placed honestly:
 *
 *   - No ribbon. There is nothing to sit under.
 *   - A stretch past MAX_LANE_SPAN_MI, where the lanes stop naming places.
 *   - A download that publishes no POI miles at all (pre-#753). Empty lanes
 *     there would be this screen reporting "nothing along this stretch" about
 *     data it simply cannot place, which is the confident wrong answer
 *     CLAUDE.md's four-ways section rules out. A download that HAS miles and
 *     genuinely holds nothing on this stretch draws empty lanes, because that
 *     emptiness is a fact about the trail.
 */
export function planLanes(
  ribbon: PlanRibbon | undefined,
  pois: readonly PlaceablePoi[],
): PlanLanes | undefined {
  if (ribbon === undefined) return undefined

  const { startMile, endMile } = ribbon.domain
  if (endMile - startMile > MAX_LANE_SPAN_MI) return undefined

  const points: Waypoint[] = []
  let anyPlaced = false

  for (const poi of pois) {
    if (poi.mile === undefined) continue
    anyPlaced = true
    if (poi.mile < startMile || poi.mile > endMile) continue
    points.push({ id: poi.id, type: poi.type, mile: poi.mile })
  }

  if (!anyPlaced) return undefined

  return { points, startMile, endMile }
}
