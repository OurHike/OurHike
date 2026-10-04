// What chrome/noticesPanel.tsx loads behind import() (#1805): decision 66's
// selection rule and decision 67's hazard areas, with the geometry under
// them, shaped into the two answers the panel hook memoizes.
//
// WHY A SEPARATE ENTRY POINT. The panel hook is on the first frame's path,
// and the launch budget had 884 bytes of headroom when this landed
// (client/scripts/check-build-output.mjs: 244,876 of 245,760 eager bytes,
// measured on 37f411fb's build 2026-10-04). The rule and the geometry are
// about 4.5 KB compressed and nothing needs them before
// conditions/notices.json has arrived - a fetch that itself waits for the
// first frame (lib/useConditions.ts) - so the hook imports this module when
// the file lands and not before (features/LAUNCH_BUDGET.md §4.4: a constant
// read out of a module brings the module, so the panel reads nothing from
// these files directly). The shaping is here too, not in the hook, because
// every line of it the hook held was a launch byte.

import type { ClubSections } from './clubSections'
import type { resolveDayHike } from './dayHikeCard'
import type { DayHike } from './dayHikes'
import {
  crossedHazardAreas,
  hazardAreasOf,
  hazardsAt,
  HAZARD_ADVISORIES,
} from './hazardAreas'
import type { HazardArea, StretchAdvisory } from './hazardAreas'
import type { Position } from './noticeGeometry'
import type { TrailNotice } from './notices'
import { plannedNotices, shownNotices, type PlannedNotices } from './plannedNotices'
import type { Stewards } from './stewards'
import type { routeLines, TrailGraphIndex } from './trailGraph'
import type { TrailIndex } from './trailPosition'
import type { Trip } from './trips'

/** The routing the first frame already holds, handed in rather than
 *  imported - plannedNotices.ts's DayHikeRouter says why. */
export interface Routing {
  resolveDayHike: typeof resolveDayHike
  routeLines: typeof routeLines
}

/** Decision 66's panel: the hikes and their notices, and every notice it
 *  shows once - what the "new notices" dot counts. */
export function plannedView({
  graph,
  routing,
  ...input
}: {
  notices: readonly TrailNotice[]
  trips: readonly Trip[]
  dayHikes: readonly DayHike[]
  today: string
  trailIndex: TrailIndex | null
  graph: TrailGraphIndex | null
  routing: Routing
  clubSections: ClubSections
  stewards: Stewards
}): { planned: PlannedNotices; shown: TrailNotice[] } {
  const planned = plannedNotices({
    ...input,
    // A day hike's route on this phone's graph, for the rule's "touches":
    // none without a graph, and none for a hike it cannot route.
    routeDayHike:
      graph === null
        ? null
        : (hike) => {
            const resolved = routing.resolveDayHike(graph, hike)
            if (resolved === null) return null
            const lines: Position[][] = []
            for (const segment of resolved.segments) {
              const drawn = routing.routeLines(graph.graph, segment.route)
              if (drawn === null) return null
              lines.push(...drawn)
            }
            return { lines, legs: resolved.legs }
          },
  })
  return { planned, shown: shownNotices(planned) }
}

/** Decision 67's areas a trail on this phone runs through, and the
 *  advisories for a tapped place on a trail: each drawn area it is inside or
 *  beside (lib/hazardAreas.ts). */
export function hazardView(
  notices: readonly TrailNotice[],
  trailIndex: TrailIndex | null,
  graph: TrailGraphIndex | null,
): { areas: HazardArea[]; advisoriesAt: (at: Position) => StretchAdvisory[] } {
  const areas = crossedHazardAreas(hazardAreasOf(notices), trailIndex, graph)
  return {
    areas,
    advisoriesAt: (at) =>
      hazardsAt(areas, at).map((area) => ({
        id: area.notice.notice_id,
        ...HAZARD_ADVISORIES[area.hazard],
      })),
  }
}
