// Hunting areas, shooting sites and burned areas (#1805, decision 67).
//
// The maintainer, by poll on 2026-10-04 from decisions-64-67-mock.html §4:
// "A warning where a downloaded trail crosses one" - the area is drawn, the
// stretch of trail inside it carries an advisory, and THE TRAIL STAYS OPEN.
// These are areas a hiker walks into, not closures: nothing here may ever
// draw barrier tape or say a trail is shut, and the pipeline holds the same
// line (pipeline/dbt/tests/singular/assert_a_hazard_area_never_closes_a_trail.sql).
//
// WHICH AREAS DRAW. conditions/notices.json carries every one a source
// publishes (NY Parks', IATA's and USACE's hunting areas, BLM's shooting
// sites, USFS's burned areas). The phone draws the ones a trail it has
// downloaded runs through, because an area no trail on this phone meets is
// an area this hiker cannot walk into from the app:
//
//  - the A.T. centerline and its side trails (lib/trailPosition.ts's index);
//  - every trail-graph edge whose vertices this phone holds (the cells
//    lib/trailGraphData.ts loads).
//
// "Runs through" is the one rule lib/noticeGeometry.ts holds for every
// notice: a polygon a line enters or crosses, or a point within
// `NOTICE_REACH_FEET` of one (a shooting site is a point). An area this
// phone cannot check because it has no trail data near it yet does not draw;
// once a trail cell under it loads, it does.

import {
  geometryParts,
  grownBounds,
  linesMeetParts,
  partsBounds,
  positionMeetsParts,
  type Bounds,
  type GeometryParts,
  type Position,
} from './noticeGeometry'
import type { TrailNotice } from './notices'
import type { NoticeHazard } from './publishedConditions'
import { NOTICE_REACH_FEET } from './plannedNotices'
import type { TrailGraphIndex } from './trailGraph'
import { cellsInBox, type TrailIndex, type VertexIndex } from './trailPosition'

/** One hazard notice with the parts its place occupies. */
export interface HazardArea {
  notice: TrailNotice
  hazard: NoticeHazard
  parts: GeometryParts
  bounds: Bounds
}

/** What a hiker reads about one kind of area, in the card and on the
 *  stretch. Plain words (.claude/skills/plain-language/SKILL.md): what is
 *  there, what to do, and that the trail is open. */
export interface HazardAdvisory {
  /** The card's heading. */
  heading: string
  /** One or two sentences, OurHike's own words - never the layer's. */
  body: string
}

/** One advisory on a tapped stretch, as chrome/LineSheet.tsx prints it: an
 *  area's words, keyed by the area's notice id. */
export interface StretchAdvisory extends HazardAdvisory {
  id: string
}

export const HAZARD_ADVISORIES: Readonly<Record<NoticeHazard, HazardAdvisory>> = {
  hunting: {
    heading: 'Hunting allowed',
    body: 'This stretch crosses land where hunting is allowed. Wear blaze orange in season. The trail stays open.',
  },
  shooting: {
    heading: 'Shooting site nearby',
    body: 'This stretch passes a recreational shooting site, so you may hear gunfire. Stay on the trail. The trail stays open.',
  },
  burned_area: {
    heading: 'Burned area',
    body: 'This stretch crosses ground burned in a recent fire. Watch for falling trees, and for flash floods after rain. The trail stays open.',
  },
}

/** The hazard notices that carry a shape, each read once. */
export function hazardAreasOf(notices: readonly TrailNotice[]): HazardArea[] {
  const areas: HazardArea[] = []
  for (const notice of notices) {
    if (notice.hazard === null || notice.hazard === undefined) continue
    if (notice.place.kind !== 'geometry') continue
    const parts = geometryParts(notice.place.geometry)
    const bounds = partsBounds(parts)
    if (bounds === null) continue
    areas.push({ notice, hazard: notice.hazard, parts, bounds })
  }
  return areas
}

function vertexPieces(
  index: VertexIndex,
  box: Bounds,
  joinNext: (i: number) => boolean,
): Position[][] {
  const pieces: Position[][] = []
  for (const cell of cellsInBox(index, box.minLat, box.maxLat, box.minLon, box.maxLon)) {
    for (let k = 0; k < cell.length; k += 1) {
      const i = cell[k]
      const at: Position = [index.lons[i], index.lats[i]]
      pieces.push(joinNext(i) ? [at, [index.lons[i + 1], index.lats[i + 1]]] : [at, at])
    }
  }
  return pieces
}

/** The A.T. and its side trails near a box, as two-vertex pieces: each
 *  centerline vertex joined to the next one inside its own piece, and each
 *  side-trail vertex alone (the tread index keeps no piece boundaries, and
 *  its vertices sit closer together than any area worth drawing). */
function centerlinePieces(
  trailIndex: TrailIndex,
  starts: ReadonlySet<number>,
  box: Bounds,
): Position[][] {
  const count = trailIndex.lons.length
  const centerline = vertexPieces(
    trailIndex,
    box,
    (i) => i + 1 < count && !starts.has(i + 1),
  )
  return [...centerline, ...vertexPieces(trailIndex.tread, box, () => false)]
}

/** The graph edges with vertices whose box meets this one. */
function graphLines(graph: TrailGraphIndex, box: Bounds): Position[][] {
  const grid = graph.grid
  if (grid === null) return []
  const lines: Position[][] = []
  graph.graph.edges.forEach((edge, edgeIndex) => {
    if (edge.geometry === undefined || edge.geometry.length < 2) return
    if (
      grid.maxLon[edgeIndex] < box.minLon ||
      grid.minLon[edgeIndex] > box.maxLon ||
      grid.maxLat[edgeIndex] < box.minLat ||
      grid.minLat[edgeIndex] > box.maxLat
    ) {
      return
    }
    lines.push(edge.geometry)
  })
  return lines
}

/**
 * The hazard areas a trail on this phone runs through - the ones the map
 * draws (the module comment says why only those).
 */
export function crossedHazardAreas(
  areas: readonly HazardArea[],
  trailIndex: TrailIndex | null,
  graph: TrailGraphIndex | null,
): HazardArea[] {
  if (trailIndex === null && graph === null) return []
  const starts = new Set<number>(
    trailIndex === null ? [] : Array.from(trailIndex.partStarts),
  )
  return areas.filter((area) => {
    const box = grownBounds(area.bounds, NOTICE_REACH_FEET)
    const lines: Position[][] = [
      ...(trailIndex === null ? [] : centerlinePieces(trailIndex, starts, box)),
      ...(graph === null ? [] : graphLines(graph, box)),
    ]
    return lines.length > 0 && linesMeetParts(lines, area.parts, NOTICE_REACH_FEET)
  })
}

/** The drawn areas a tapped place on a trail is inside, or beside - what the
 *  tapped line's card prints its advisory from. */
export function hazardsAt(areas: readonly HazardArea[], at: Position): HazardArea[] {
  return areas.filter((area) => positionMeetsParts(at, area.parts, NOTICE_REACH_FEET))
}

/** The property a drawn area carries its notice id in, for taps. */
export const HAZARD_ID_PROPERTY = 'notice_id'
/** The property it carries its kind in, for the paint. */
export const HAZARD_KIND_PROPERTY = 'hazard'

export interface HazardFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    geometry: unknown
    properties: { notice_id: string; hazard: NoticeHazard }
  }>
}

/** The drawn areas as the map's source data. */
export function hazardFeatureCollection(
  areas: readonly HazardArea[],
): HazardFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: areas.flatMap((area) =>
      area.notice.place.kind === 'geometry'
        ? [
            {
              type: 'Feature' as const,
              geometry: area.notice.place.geometry,
              properties: { notice_id: area.notice.notice_id, hazard: area.hazard },
            },
          ]
        : [],
    ),
  }
}

/**
 * The area's own season, in words, where its layer gives one - and the honest
 * line where it does not. Never a season OurHike supplied: none of the four
 * hunting layers carries dates (pipeline/dbt/seeds/notice_source_fields.csv),
 * so today every hunting card says so.
 */
export function hazardDates(notice: TrailNotice): string {
  const from = notice.starts_on ?? null
  const to = notice.ends_on ?? null
  // A burned area's only date is the fire's start (BAER's `ig_date`, which
  // seeds/notice_source_fields.csv reads as its start): a fact about the
  // fire, never a date the danger began or ends.
  if (notice.hazard === 'burned_area') {
    return from === null
      ? 'Shown while the agency’s layer lists the area.'
      : `The fire started ${from}, as the layer states. Shown while the agency’s layer lists the area.`
  }
  if (from !== null && to !== null) return `From ${from} to ${to}, as the layer states.`
  if (from !== null) return `From ${from}, as the layer states.`
  if (to !== null) return `Until ${to}, as the layer states.`
  if (notice.hazard === 'hunting') {
    return 'The layer gives no season dates, so check the season before you go.'
  }
  return 'The layer gives no end date.'
}
