// How far a plan reaches, as usage measurement reads it (#1902,
// features/EVENTING.md §0 "Clubs").
//
// A plan's clubs are worked out from its A.T. miles - "assigned by # miles
// specific for each club" (the maintainer, poll 2026-10-27) - so what a
// measurement needs from a plan is the stretch it covers on the mile axis.
// A plan with no stretch on that axis still counts, by its length alone, and
// carries no club: a day hike on a club's own trails is named by the
// organization that publishes them, which this build does not yet look up
// (EVENTING.md §0, "What this build does not do").

import { type Hike, trailHasMileAxis } from './hikes'
import type { HikePlan } from './plan'
import type { PlanExtent } from './useUsageMeasurement'

function extentOfMiles(miles: readonly number[]): PlanExtent {
  const finite = miles.filter((mile) => Number.isFinite(mile))
  if (finite.length < 2) return {}
  return { fromMile: Math.min(...finite), toMile: Math.max(...finite) }
}

/** A trip or a section: its stops are on the pipeline's mile axis (lib/plan.ts). */
export function planExtent(plan: HikePlan): PlanExtent {
  return extentOfMiles(plan.stops.map((stop) => stop.mile))
}

/** A long hike: its points' miles, when its trail is the one with a mile axis. */
export function hikeExtent(hike: Hike): PlanExtent {
  if (!trailHasMileAxis(hike.trailId)) return {}
  return extentOfMiles(hike.points.map((point) => point.mile))
}
