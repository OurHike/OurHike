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
import { newNoticesSince, type NewNotices, type TrailNotice } from './notices'
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

/**
 * How far after its source's earliest `first_seen_at` a notice's own must
 * fall to count as first seen in a later build (decision 87).
 *
 * Not zero, because one build stamps one source's rows a moment apart: each
 * mart's row history is snapshotted on its own clock, and on soak run 536's
 * file (2026-10-05) the closures mart's rows of five sources read 22:01:55
 * and their warnings mart's rows 22:01:56, both from the build that first
 * loaded them (Measured: 1 s). Fifteen minutes is publish-conditions.yml's cap
 * on the whole job (`timeout-minutes: 15`, 10 until decision 103 raised the
 * build step's own cap), which one build's snapshots cannot outlast, and the
 * job shares the publish-data concurrency group, so two builds never overlap
 * (Reasoned).
 *
 * @unvalidated as a number: it is the job's cap, not a measured spread. A
 * notice first seen in a build that began within fifteen minutes of its
 * source's first build is not counted - a miss, the direction a banner that
 * must not cry wolf errs in. What would settle it is the spread of
 * `first_seen_at` within each build's rows over a few weeks of hourly files.
 */
export const SAME_BUILD_MS = 15 * 60 * 1000

function seenTime(notice: TrailNotice): number | null {
  if (notice.first_seen_at === null || notice.first_seen_at === undefined) return null
  const at = Date.parse(notice.first_seen_at)
  return Number.isNaN(at) ? null : at
}

/**
 * Decision 87 (the maintainer, 2026-10-05): when a notice with no date of its
 * own counts as new for the banner - when OurHike first saw it, but only if
 * that was after its source's earliest row in the same file, measured over
 * every row of `notices`, the whole file, and not only the rows a panel
 * shows. A source's first build is the initial load, not news: 84% of soak
 * run 536's closures carry no `updated_at`, and counting every first-seen
 * date would have lit the banner for all of them, because the row history
 * began within a day of that file. Null for a notice that does not count,
 * and for one with no readable `first_seen_at` (a build without the row
 * history writes none), which is never new.
 */
export function firstSeenRule(
  notices: readonly TrailNotice[],
): (notice: TrailNotice) => Date | null {
  const earliest = new Map<string, number>()
  for (const notice of notices) {
    const at = seenTime(notice)
    if (at === null) continue
    const first = earliest.get(notice.source_key)
    if (first === undefined || at < first) earliest.set(notice.source_key, at)
  }
  return (notice) => {
    const at = seenTime(notice)
    const first = earliest.get(notice.source_key)
    return at === null || first === undefined || at - first <= SAME_BUILD_MS
      ? null
      : new Date(at)
  }
}

/** The end of the watermark key a first-seen notice is silenced under
 *  (lib/notices.ts's `noticeSilenceKey`, `<source_key>:seen`). */
export const SEEN_WATERMARK = ':seen'

/**
 * What the "new notices" banner counts with conditions/notices.json: the
 * shown notices with an `updated_at` of their own as lib/notices.ts's
 * `newNoticesSince` counts them, and those without one from when OurHike
 * first saw them, where `firstSeenAt` (decision 87's rule) says that counts.
 * Worded "seen" when any of those is counted (`NewNotices.seen`).
 *
 * ONE COUNT, THROUGH THE ONE FUNCTION, WITH A WATERMARK OF ITS OWN. A
 * first-seen notice is handed to `newNoticesSince` dated by when OurHike
 * first saw it, under `<source_key>:seen`, so a dismissal silences it on
 * OurHike's clock and never on the club's: one watermark for both would let
 * a first-seen time silence a club's notice dated before it but read after
 * it, which nobody was shown. The banner then names the source itself.
 * Done here, behind import(), and not in lib/notices.ts, because that
 * module is on the first frame's path (this module's header says why that
 * matters).
 */
export function newClubNotices(
  shown: readonly TrailNotice[],
  firstSeenAt: (notice: TrailNotice) => Date | null,
  now: Date,
  silencedThrough: (sourceKey: string) => Date | null,
): NewNotices | null {
  const counted = shown.map((notice) => {
    if (notice.updated_at !== null) return notice
    const at = firstSeenAt(notice)
    return at === null
      ? notice
      : {
          ...notice,
          source_key: notice.source_key + SEEN_WATERMARK,
          updated_at: at.toISOString(),
        }
  })
  const found = newNoticesSince(counted, now, silencedThrough)
  if (found === null) return null
  const seen = (key: string) => key.endsWith(SEEN_WATERMARK)
  const sourceOf = (key: string) =>
    seen(key) ? key.slice(0, -SEEN_WATERMARK.length) : key
  const sourceKeys = found.sourceKeys.map(sourceOf)
  // The providers by the source's own key, which is what the banner names
  // an organization by; a seen watermark's key is only this module's.
  const providers = new Map<string, string>()
  for (const [key, provider] of found.providers ?? []) {
    if (!providers.has(sourceOf(key))) providers.set(sourceOf(key), provider)
  }
  return {
    ...found,
    sourceKeys: [...new Set(sourceKeys)],
    seen: found.sourceKeys.some(seen),
    providers,
  }
}

/** Decision 66's panel: the hikes and their notices, and every notice it
 *  shows once - what the "new notices" dot counts, with decision 87's rule
 *  for a notice that gives no date of its own. */
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
}): {
  planned: PlannedNotices
  shown: TrailNotice[]
  newSince: (
    now: Date,
    silencedThrough: (sourceKey: string) => Date | null,
  ) => NewNotices | null
} {
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
  const shown = shownNotices(planned)
  const firstSeenAt = firstSeenRule(input.notices)
  return {
    planned,
    shown,
    newSince: (now, silencedThrough) =>
      newClubNotices(shown, firstSeenAt, now, silencedThrough),
  }
}

/**
 * Decision 67's areas a trail on this phone runs through, and the
 * advisories for a tapped place on a trail: each drawn area it is inside or
 * beside (lib/hazardAreas.ts). Null with neither file here.
 *
 * FROM ONE FILE, so no area is drawn twice (decision 84): the areas are in
 * both conditions/hazard_areas.json, read whatever is planned, and
 * notices.json, read once a hike is planned (decision 77), and one build
 * writes the same rows to both. The newer of the two by `generated_at`, the
 * hazard file on a tie, so a copy of notices.json this phone kept from
 * before decision 77 never outranks a fresh hazard file. With only
 * notices.json here - a bucket without the hazard file, production until
 * the cutover - the areas come from it, as before decision 84: a missing
 * hazard file is never read as no hazard area.
 */
export function hazardView(
  notices: readonly TrailNotice[] | null,
  noticesAt: Date | null,
  hazardFile: { items: readonly TrailNotice[]; generatedAt: Date } | null,
  trailIndex: TrailIndex | null,
  graph: TrailGraphIndex | null,
): { areas: HazardArea[]; advisoriesAt: (at: Position) => StretchAdvisory[] } | null {
  const source =
    hazardFile !== null &&
    (notices === null ||
      noticesAt === null ||
      hazardFile.generatedAt.getTime() >= noticesAt.getTime())
      ? hazardFile.items
      : notices
  if (source === null) return null
  const areas = crossedHazardAreas(hazardAreasOf(source), trailIndex, graph)
  return {
    areas,
    advisoriesAt: (at) =>
      hazardsAt(areas, at).map((area) => ({
        id: area.notice.notice_id,
        ...HAZARD_ADVISORIES[area.hazard],
      })),
  }
}
