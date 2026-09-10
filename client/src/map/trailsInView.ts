// Which named trails the map is drawing right now, and where each
// through-route's badge goes (#1283).
//
// Two consumers, one measurement. The legend's "Trails in view" block lists
// every named trail on screen; the badge layer (map/trailBadges.ts) needs one
// point per named through-route on screen. Both are read off the same
// `queryRenderedFeatures` pass, so the panel and the canvas can never
// disagree about which trails are in front of the hiker - the rule
// lib/useDrawnPoiCounts.ts keeps for the waypoint counts and the ghosting
// sentence, for the same reason.
//
// SHAPED ON map/drawnPois.ts, TRAPS INCLUDED. `queryRenderedFeatures`
// answers for the LAST RENDERED FRAME, so this recomputes on `idle` (and on
// `moveend`, for a quick first answer while tiles are still landing). And a
// GeoJSON source is tiled internally, so one trail crossing a tile boundary
// comes back once per tile, with its geometry clipped to each: the A.T.
// across a z12 screen is three or four pieces. Deduplicated by NAME rather
// than by feature id, because a name is what a hiker reads and what the
// badge prints, and a trail that is one thing to a hiker should be one row
// and one badge however many records or tiles it is cut into
// (features/NEARBY_TRAILS.md §5: one place, one line, many orgs).
//
// WHERE THE BADGE GOES. On a vertex of the trail - never floating beside it,
// because a badge off its line belongs to nothing - at the middle of the
// longest stretch of that trail the screen actually shows. That is the
// prototype's rule (anchor at half the visible path length) applied to what
// this map can measure: the pieces come back tile-clipped and in no
// particular order, so "the visible path" is the longest run of in-view
// vertices among them, and "the middle" is half its planar length along.
// Recomputed as the camera settles, so the badge slides along its line as
// the hiker pans and never sits off screen while the trail is on it.
//
// AND NOT WHERE A PIN ALREADY IS, which the third preview frame taught. The
// plate is a 26 px pill some 230 px long, and both halves of the symbol are
// required, so MapLibre drops it whole when every position round its vertex
// overlaps a pin - and pins are placed first. Harriman's A.T. is lined with
// shelters, campsites and springs a thumb's width apart, so the vertex at the
// middle of the run had a pin on every side and the map's one badge was
// dropped on exactly the screen it was designed for. So the anchor is chosen
// with the pins in view: the candidate vertices - every in-view vertex of
// every visible piece of the trail, nearest the frame's centre first - are
// tried in turn, and the first with a free pill position inside the frame
// - the same eight positions map/trailBadges.ts hands the placer, tested
// against the pins' boxes here - wins; then the same again for the mark
// alone; then the mark on the nearest vertex regardless. The layer is
// allowed to overlap, so what this module chooses is what is drawn (the
// maintainer's review of #1374: "the badge always finds a place"). The box
// tested has to be the one the placer would have tested, to the pixel, and
// the fifth preview frame is what that sentence cost: plateBox() below
// says which box that is and how the first model got it wrong.
//
// "THE SCREEN" IS THE PART OF THE CANVAS A HIKER CAN SEE, and the second
// preview frame is why that sentence is here. Over Harriman the A.T.'s
// longest visible stretch ran along the top of the canvas, its middle sat
// under the identity plate, and the badge was placed there - correctly, by
// MapLibre's lights, which knows nothing about the DOM laid over it - and
// was invisible. So the shell hands this module the chrome's insets
// (MapView's `chromeInsets`, measured by MapScreen), the anchor is chosen
// among the vertices inside the canvas MINUS those bands, and only a trail
// with no vertex in the clear falls back to the whole canvas. The list of
// trails in view still reads the whole canvas: a trail under the plate is
// still on the map.
//
// NEAREST THE CENTRE, since the review of #1374 (2026-09-10). The first
// rule anchored the badge at the middle of the longest visible run, and
// this paragraph used to name the alternative - the vertex nearest the
// screen's centre, "steadier under panning and exactly where a following
// hiker's own dot is" - as the thing nobody had tried. The review's renders
// of this branch tried it for us: at the opening camera the badge was
// dropped whole, at z13 the plate hung half off the left edge, and at z12
// a pin on every vertex of the longest run left the trail nameless while
// another piece of it sat clear by the centre. So the centre rule is the
// rule now, every piece counts, the frame is a bound, and the mark is the
// floor. `@unvalidated` still, as a display choice: chosen against those
// frames, not watched on a phone in a hiker's hand, and what would settle
// it is the same report as before - somebody panning through a park with a
// badge on screen and saying whether it jumps in a way that distracts.

import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { ATC_UPDATE_POINT_LAYER_ID } from '../lib/atcUpdateStyle'
import { CHOSEN_SYSTEM_SOURCES } from './nearbyTrails'
import { POI_LAYER_ID } from './poiLayers'
import { TAPPABLE_BLAZE_LAYER_IDS } from './style'
import { whenStyleReady } from './styleReady'
import {
  BADGE_ANCHOR_PROPERTY,
  BADGE_CHIP_PROPERTY,
  BADGE_FIT_PROPERTY,
  BADGE_MARK_PROPERTY,
  BADGE_NAME_PROPERTY,
  BADGE_SOURCE_PROPERTY,
  BADGE_SOURCES,
  type BadgeFit,
  TRAIL_BADGE_ANCHORS,
  TRAIL_BADGE_MARK_GAP,
  TRAIL_BADGE_MARK_SIZE,
  TRAIL_BADGE_PLATE_BORDER,
  TRAIL_BADGE_RADIAL_OFFSET,
  TRAIL_BADGE_SOURCE_ID,
  TRAIL_BADGE_TEXT_FIT_PADDING,
  TRAIL_BADGE_TEXT_SIZE,
  blazeChipImageId,
  trailIdForSource,
  trailMarkImageId,
} from './trailBadges'
import { WARNING_LAYER_ID } from './warningLayers'
import { WORKDAY_LAYER_ID } from './workdayLayers'

/**
 * The symbol layers placed before the badge, whose pins it must not sit on:
 * every pin layer after it in the stack (style.ts). The along-line names and
 * the sheet's own labels are NOT here - they are placed after the badge and
 * yield to it.
 */
export const BADGE_OBSTACLE_LAYER_IDS: readonly string[] = [
  POI_LAYER_ID,
  WARNING_LAYER_ID,
  WORKDAY_LAYER_ID,
  ATC_UPDATE_POINT_LAYER_ID,
]

/** Half the largest pin on the map - the 44 px serious-warning pin
 *  (map/warningPin.ts) - plus MapLibre's default 2 px symbol padding, as one
 *  clearance for every obstacle. A waypoint's 38 px pin gets three px more
 *  room than it needs, which is the safe side to be wrong on. */
const OBSTACLE_HALF_PX = 44 / 2 + 2

/**
 * The TEXT block the placer anchors, in CSS px: the mark, and for the full
 * form the gap and the name. Measured on the stand-alone render of
 * 2026-09-08: "Appalachian National Scenic Trail" (33 characters) set 185 px
 * wide at 12 px Noto Sans, 5.6 px a character, so 0.5 em a character is a
 * slight over-estimate - the right direction for a box that decides whether
 * there is room. As tall as the mark, which is taller than the 12 px name.
 */
export function badgeTextSize(
  name: string,
  fit: BadgeFit = 'full',
): { width: number; height: number } {
  if (fit === 'mark')
    return { width: TRAIL_BADGE_MARK_SIZE, height: TRAIL_BADGE_MARK_SIZE }
  const text = name.length * TRAIL_BADGE_TEXT_SIZE * 0.5
  return {
    width: TRAIL_BADGE_MARK_SIZE + TRAIL_BADGE_MARK_GAP + text,
    height: TRAIL_BADGE_MARK_SIZE,
  }
}

/** How wide the plate comes out for a name: the text block plus the paper
 *  round it. What the legend and the tests reason about; the collision
 *  model below builds its own box from the same parts. */
export function badgePlateWidth(name: string, fit: BadgeFit = 'full'): number {
  const [, right, , left] = TRAIL_BADGE_TEXT_FIT_PADDING
  return badgeTextSize(name, fit).width + left + right + TRAIL_BADGE_PLATE_BORDER * 2
}

/** MapLibre's default `text-padding` and `icon-padding`: the ring it grows
 *  every symbol's box by before testing it against the others. */
const SYMBOL_PADDING_PX = 2

interface Box {
  x1: number
  y1: number
  x2: number
  y2: number
}

function overlaps(a: Box, b: Box): boolean {
  return a.x1 <= b.x2 && a.x2 >= b.x1 && a.y1 <= b.y2 && a.y2 >= b.y1
}

/**
 * The box the placer will test for one anchor at one screen point - the
 * geometry MapLibre's variable placement produces, and it is the TEXT block
 * that is anchored, not the plate.
 *
 * `text-variable-anchor` puts the text block's edge at the vertex, pushed
 * out by `text-radial-offset`; `icon-text-fit` then grows the plate round
 * the text by TRAIL_BADGE_TEXT_FIT_PADDING, which is not symmetric - nine
 * px on the right against three on the left - so on a right-hand anchor
 * the plate reaches past the vertex on the far side; and the engine grows
 * the result by its two px of padding before testing it. The first model
 * here anchored the plate itself, and found a spot "free" of a shelter by
 * under a pixel that the engine, growing the box as above, found taken and
 * dropped - the fifth preview frame over Harriman, and the instrumented
 * build that showed the feature written and never drawn (2026-09-08).
 */
function plateBox(
  anchor: string,
  at: { x: number; y: number },
  text: { width: number; height: number },
): Box {
  const offset = TRAIL_BADGE_RADIAL_OFFSET * TRAIL_BADGE_TEXT_SIZE
  // Where the anchor point sits on the text block: 0 = its start, 1 = its end.
  const horizontal = anchor.includes('left') ? 0 : anchor.includes('right') ? 1 : 0.5
  const vertical = anchor.includes('top') ? 0 : anchor.includes('bottom') ? 1 : 0.5
  const dx = horizontal === 0 ? offset : horizontal === 1 ? -offset : 0
  const dy = vertical === 0 ? offset : vertical === 1 ? -offset : 0
  const textX1 = at.x + dx - text.width * horizontal
  const textY1 = at.y + dy - text.height * vertical
  const [top, right, bottom, left] = TRAIL_BADGE_TEXT_FIT_PADDING
  const grow = TRAIL_BADGE_PLATE_BORDER + SYMBOL_PADDING_PX
  return {
    x1: textX1 - left - grow,
    y1: textY1 - top - grow,
    x2: textX1 + text.width + right + grow,
    y2: textY1 + text.height + bottom + grow,
  }
}

/** The pins on screen, as the boxes a plate must clear. */
function obstacleBoxes(map: TrailsInViewMap): Box[] {
  const layers = BADGE_OBSTACLE_LAYER_IDS.filter((id) => map.getLayer(id) !== undefined)
  if (layers.length === 0) return []
  const boxes: Box[] = []
  for (const feature of map.queryRenderedFeatures(undefined, { layers })) {
    const geometry = feature.geometry as
      { type?: string; coordinates?: unknown } | undefined
    if (geometry?.type !== 'Point' || !Array.isArray(geometry.coordinates)) continue
    const [lng, lat] = geometry.coordinates as number[]
    const at = map.project([lng, lat])
    boxes.push({
      x1: at.x - OBSTACLE_HALF_PX,
      y1: at.y - OBSTACLE_HALF_PX,
      x2: at.x + OBSTACLE_HALF_PX,
      y2: at.y + OBSTACLE_HALF_PX,
    })
  }
  return boxes
}

interface BadgeAnchor {
  point: Position
  fit: BadgeFit
  /** Which side of the vertex the text block sits - one of
   *  TRAIL_BADGE_ANCHORS, and the one the layer draws (below). */
  anchor: string
}

/**
 * The vertex of `run` the badge should anchor to, and in which form: the
 * first vertex, walking outward from the middle, at which one of the full
 * plate's positions overlaps no pin and stays inside `clear`; failing that,
 * the same search for the mark's small plate; failing that, the middle
 * itself, in full, for the placer to decide.
 */
/** A vertex the badge could sit on, with where it projects and how far that
 *  is from the frame's centre. */
interface Candidate {
  point: Position
  at: { x: number; y: number }
  distance: number
}

/**
 * How many vertices the search reads. At the opening camera the A.T.'s
 * drawn geometry is thousands of vertices; trying every anchor of every one
 * of them on each `idle` is work nobody would see.
 *
 * THINNED ALONG THE LINE, NOT CUT AT THE CENTRE. The first cut kept the six
 * hundred nearest the centre, on the argument that the cap only bites at
 * the overview, where the line is far from every pin. The z9 frame proved
 * that wrong on both a phone and a laptop (rendered 2026-09-10, the review
 * of #1374): tile geometry at the seam puts six hundred vertices inside a
 * few miles of trail, the few miles nearest the centre over Harriman were
 * the ones under a dozen pins, every plate and every mark collided, and
 * the last resort put the mark on the vertex nearest the centre - under a
 * pin, invisible. The clear stretch by Warwick was the six-hundred-and-first
 * vertex and beyond. So a run longer than the cap is sampled evenly along
 * its length first, and sorted by distance to the centre second: the same
 * bound on the work, over the whole visible line rather than its densest
 * mile. The figure itself stays @unvalidated - picked to bound the work;
 * what would settle it is the cost of one pass at z9 on a slow phone.
 */
const CANDIDATE_LIMIT = 600

/** Every `step`-th entry of `all`, the first kept, so a run longer than the
 *  cap is read end to end at a coarser pitch rather than only at one end. */
function thinned<T>(all: readonly T[], limit: number): T[] {
  if (all.length <= limit) return [...all]
  const step = Math.ceil(all.length / limit)
  return all.filter((_, i) => i % step === 0)
}

/**
 * Every in-view vertex of every visible piece of a trail, nearest the
 * frame's centre first - the clear runs (under no chrome) ahead of the rest
 * (the maintainer's review of #1374: "the badge always finds a place").
 *
 * The old rule took one run, the longest, and walked outward from its
 * middle; a trail whose longest piece ran under the pins had nowhere to go
 * even when another piece of it lay in the clear, and a badge anchored by
 * the run's middle jumped as the run's ends came and went. Nearest the
 * centre is steadier under panning and sits where a following hiker's own
 * dot is - the alternative this file's header named and nobody had tried.
 */
function candidatesOf(
  clearRuns: readonly Run[],
  viewRuns: readonly Run[],
  map: TrailsInViewMap,
  centre: { x: number; y: number },
): Candidate[] {
  const seen = new Set<string>()
  const list = (runs: readonly Run[]): Candidate[] => {
    const points: Position[] = []
    for (const run of runs) {
      for (const point of run.points) {
        const key = `${point[0]},${point[1]}`
        if (seen.has(key)) continue
        seen.add(key)
        points.push(point)
      }
    }
    // Along the line first (the runs' own order), then by distance.
    return thinned(points, CANDIDATE_LIMIT)
      .map((point) => {
        const at = map.project([point[0], point[1]])
        return { point, at, distance: Math.hypot(at.x - centre.x, at.y - centre.y) }
      })
      .sort((a, b) => a.distance - b.distance)
  }
  return [...list(clearRuns), ...list(viewRuns)].slice(0, CANDIDATE_LIMIT)
}

function withinFrame(box: Box, frame: Box): boolean {
  return (
    box.x1 >= frame.x1 && box.x2 <= frame.x2 && box.y1 >= frame.y1 && box.y2 <= frame.y2
  )
}

/**
 * Where the badge sits: the first candidate, nearest the centre first, with
 * a position for the full plate that is inside the frame and clear of every
 * pin; failing that the first with room for the mark alone; failing that,
 * the mark on the nearest vertex, handed to the placer as it is.
 *
 * INSIDE THE FRAME is new with the review of #1374: the fourth zoom frame
 * of that review's renders had "National Scenic Trail" cut in half at the
 * left edge, a plate hung off the one vertex the old search reached. A
 * plate that is not wholly on screen is not a name a hiker can read.
 *
 * THE LAST RESORT IS THE MARK, NOT THE FULL PLATE. The old code handed the
 * middle over in full and let the engine drop it whole where it collided
 * (the sixth preview frame of #1283, and the z12 frame of the review's
 * renders, where a pin on every vertex left the trail nameless). The mark
 * is 32 px, is the same tap target, and with the layer allowed to overlap
 * (map/trailBadges.ts) it is always drawn - never nothing, which is what
 * "always finds a place" has to mean when nothing fits.
 */
function anchorWithRoom(
  candidates: readonly Candidate[],
  obstacles: readonly Box[],
  frame: Box,
  name: string,
): BadgeAnchor | null {
  if (candidates.length === 0) return null
  for (const fit of ['full', 'mark'] as const) {
    const text = badgeTextSize(name, fit)
    for (const candidate of candidates) {
      for (const anchor of TRAIL_BADGE_ANCHORS) {
        const box = plateBox(anchor, candidate.at, text)
        if (!withinFrame(box, frame)) continue
        if (obstacles.some((obstacle) => overlaps(box, obstacle))) continue
        return { point: candidate.point, fit, anchor }
      }
    }
  }
  return { point: candidates[0].point, fit: 'mark', anchor: TRAIL_BADGE_ANCHORS[0] }
}

export type TrailsInViewMap = MapLibreMap

export interface TrailInView {
  /** The trail's published name - the dedup key, and what the badge and the
   *  legend print. Never empty: an unnamed line is not listed, for the
   *  reason map/trailLabels.ts's filter gives. */
  name: string
  /** The pipeline's `source` key of the piece that named it; where a trail
   *  is drawn from more than one source, a through-route's piece wins. */
  source: string
  /** The published blaze, or null where the piece carries none. */
  blazeColor: string | null
  /** Whether the trail earns a badge - map/trailBadges.ts's BADGE_SOURCES. */
  throughRoute: boolean
  /** Whether a tap on this trail's legend row or badge can TAKE it -
   *  map/trailBadges.ts's trailIdForSource, deliberately narrower than
   *  throughRoute (#1307: the Long Path earns a badge without being
   *  takeable). A row this build cannot measure stays a row, never a
   *  button with nothing behind it. */
  takeable: boolean
  /** Whether the trail is in the chosen system, and so drawn solid. */
  chosen: boolean
  /** A vertex on the trail, in view, where its badge sits; null where none of
   *  the drawn geometry put a vertex inside the viewport. */
  anchor: [number, number] | null
  /** Which form the badge takes at that vertex: the full plate, or the mark
   *  alone where nothing wider had room (map/trailBadges.ts's header). */
  badgeFit: BadgeFit
  /** Which side of the vertex the badge sits, one of TRAIL_BADGE_ANCHORS -
   *  the placer's own choice, written on the feature for the layer's
   *  `text-anchor` (map/trailBadges.ts). THE ENGINE DOES NOT CHOOSE, since
   *  the review of #1374: with the layer allowed to overlap, MapLibre's
   *  variable-anchor pass accepts the first anchor on its list whatever the
   *  placer found room for - the phone frame at 05e9506a drew the plate
   *  off the right edge of the screen from a vertex the placer had given
   *  the mirror anchor. So the list is the placer's order alone. */
  badgeAnchor: string
  /** The published properties of the piece that named it, verbatim, so a tap
   *  on the badge can open the same sheet a tap on the line opens. */
  properties: Record<string, unknown>
}

interface Bounds {
  west: number
  south: number
  east: number
  north: number
}

/**
 * How much of each edge of the canvas the chrome covers, in CSS px - the
 * identity plate and what stacks under it at the top, the controls and the
 * count chip at the foot. MapView's `chromeInsets` prop carries it down.
 */
export interface ViewInsets {
  top: number
  right: number
  bottom: number
  left: number
}

/** No chrome anywhere: what a map with no shell over it gets. */
export const NO_INSETS: ViewInsets = { top: 0, right: 0, bottom: 0, left: 0 }

type Position = [number, number]

/** Every part of a LineString or MultiLineString, as separate runs. Both
 *  shapes are real here, for the reason export_trails.py gives. */
function partsOf(geometry: unknown): Position[][] {
  const shape = geometry as { type?: string; coordinates?: unknown } | null | undefined
  const coordinates = shape?.coordinates
  if (!Array.isArray(coordinates)) return []
  const asRun = (part: unknown): Position[] =>
    Array.isArray(part)
      ? part
          .filter((point): point is number[] => Array.isArray(point) && point.length >= 2)
          .map((point) => [point[0], point[1]] as Position)
      : []
  if (shape?.type === 'LineString') return [asRun(coordinates)]
  if (shape?.type === 'MultiLineString') return coordinates.map(asRun)
  return []
}

function inside(point: Position, bounds: Bounds): boolean {
  return (
    point[0] >= bounds.west &&
    point[0] <= bounds.east &&
    point[1] >= bounds.south &&
    point[1] <= bounds.north
  )
}

/** Planar distance in degrees with longitude scaled by the latitude, which
 *  is all "the middle of this run" needs on one screen; nothing here is a
 *  distance a hiker reads. */
function span(a: Position, b: Position): number {
  const scale = Math.cos((((a[1] + b[1]) / 2) * Math.PI) / 180)
  const dx = (a[0] - b[0]) * scale
  const dy = a[1] - b[1]
  return Math.hypot(dx, dy)
}

interface Run {
  points: Position[]
  length: number
}

/** The maximal runs of consecutive in-view vertices in one part. */
function visibleRuns(part: Position[], bounds: Bounds): Run[] {
  const runs: Run[] = []
  let current: Position[] = []
  const flush = () => {
    if (current.length === 0) return
    let length = 0
    for (let i = 1; i < current.length; i += 1) length += span(current[i - 1], current[i])
    runs.push({ points: current, length })
    current = []
  }
  for (const point of part) {
    if (inside(point, bounds)) current.push(point)
    else flush()
  }
  flush()
  return runs
}

function stringProp(properties: Record<string, unknown>, key: string): string | null {
  const value = properties[key]
  return typeof value === 'string' && value !== '' ? value : null
}

/**
 * The canvas minus the chrome, as a geographic rectangle: the corners of the
 * inset viewport unprojected. Axis-aligned in lng/lat, which is exact for
 * an unrotated, unpitched map and close enough for this map, which is never
 * either. Falls back to the whole view where the container reports no
 * size, which is what a map not yet laid out says.
 */
function clearViewOf(map: TrailsInViewMap, insets: ViewInsets, view: Bounds): Bounds {
  if (
    insets.top === 0 &&
    insets.right === 0 &&
    insets.bottom === 0 &&
    insets.left === 0
  ) {
    return view
  }
  const container = map.getContainer()
  const width = container.clientWidth
  const height = container.clientHeight
  if (width <= insets.left + insets.right || height <= insets.top + insets.bottom)
    return view

  const northWest = map.unproject([insets.left, insets.top])
  const southEast = map.unproject([width - insets.right, height - insets.bottom])
  return {
    west: Math.min(northWest.lng, southEast.lng),
    east: Math.max(northWest.lng, southEast.lng),
    south: Math.min(northWest.lat, southEast.lat),
    north: Math.max(northWest.lat, southEast.lat),
  }
}

/**
 * Every named trail the trail layers are drawing, one entry per name,
 * through-routes first, then the chosen system, then by name.
 *
 * Read off the four full-line layers - both halves of both splits
 * (style.ts's TAPPABLE_BLAZE_LAYER_IDS) - and not the sketches, which carry
 * no `name`. Empty where the layers are not in the style yet, which is a
 * cold start's honest answer.
 *
 * `insets` is the chrome over the canvas: the anchor prefers a vertex in the
 * clear, and the header explains why.
 */
export function trailsInView(
  map: TrailsInViewMap,
  insets: ViewInsets = NO_INSETS,
  chosen: readonly string[] = CHOSEN_SYSTEM_SOURCES,
): TrailInView[] {
  const layers = TAPPABLE_BLAZE_LAYER_IDS.filter((id) => map.getLayer(id) !== undefined)
  if (layers.length === 0) return []

  const bounds = map.getBounds()
  const view: Bounds = {
    west: bounds.getWest(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    north: bounds.getNorth(),
  }
  const clear = clearViewOf(map, insets, view)
  // The frame a plate must sit inside - the canvas less the chrome's bands -
  // and the point the search fans out from, its centre. Resolved once per
  // pass, with the pins: none of it moves between one trail and the next.
  const container = map.getContainer()
  const frame: Box = {
    x1: insets.left,
    y1: insets.top,
    x2: container.clientWidth - insets.right,
    y2: container.clientHeight - insets.bottom,
  }
  const centre = { x: (frame.x1 + frame.x2) / 2, y: (frame.y1 + frame.y2) / 2 }
  let obstacles: readonly Box[] | undefined
  const pins = () => (obstacles ??= obstacleBoxes(map))

  const features = map.queryRenderedFeatures(undefined, { layers })
  const byName = new Map<string, TrailInView & { runs: Run[]; clearRuns: Run[] }>()

  for (const feature of features) {
    const properties = (feature.properties ?? {}) as Record<string, unknown>
    const name = stringProp(properties, 'name')
    if (name === null) continue
    const source = stringProp(properties, 'source') ?? ''
    const throughRoute = BADGE_SOURCES.includes(source)
    const takeable = trailIdForSource(source) !== null
    const inChosenSystem = chosen.includes(source)

    // Every visible run of every part, kept: the badge may sit on any of
    // them (candidatesOf), so no piece is thrown away for being short.
    const runs: Run[] = []
    const clearRuns: Run[] = []
    for (const part of partsOf(feature.geometry)) {
      runs.push(...visibleRuns(part, view))
      if (clear !== view) clearRuns.push(...visibleRuns(part, clear))
    }

    const existing = byName.get(name)
    if (existing === undefined) {
      byName.set(name, {
        name,
        source,
        blazeColor: stringProp(properties, 'blaze_color'),
        throughRoute,
        takeable,
        chosen: inChosenSystem,
        anchor: null,
        badgeFit: 'full',
        badgeAnchor: TRAIL_BADGE_ANCHORS[0],
        properties,
        runs,
        clearRuns,
      })
      continue
    }
    // A second piece of the same trail, tile-clipped or a second feature:
    // its runs join the search, and the through-route's piece names it.
    existing.runs.push(...runs)
    existing.clearRuns.push(...clearRuns)
    if (throughRoute && !existing.throughRoute) {
      existing.throughRoute = true
      existing.takeable = takeable
      existing.source = source
      existing.blazeColor = stringProp(properties, 'blaze_color')
      existing.properties = properties
    }
    existing.chosen = existing.chosen || inChosenSystem
  }

  return [...byName.values()]
    .map(({ runs, clearRuns, ...trail }) => {
      // Only a through-route needs an anchor at all; the rest are listed,
      // not badged, and are spared the search. In the clear first: under
      // the chrome only when all of the trail is, which still beats no
      // badge - a plate at 94% shows a badge through it, faintly.
      if (!trail.throughRoute || runs.length === 0) return { ...trail, anchor: null }
      const placed = anchorWithRoom(
        candidatesOf(clearRuns, runs, map, centre),
        pins(),
        frame,
        trail.name,
      )
      if (placed === null) return { ...trail, anchor: null }
      return {
        ...trail,
        anchor: placed.point,
        badgeFit: placed.fit,
        badgeAnchor: placed.anchor,
      }
    })
    .sort((a, b) => {
      if (a.throughRoute !== b.throughRoute) return a.throughRoute ? -1 : 1
      if (a.chosen !== b.chosen) return a.chosen ? -1 : 1
      return a.name.localeCompare(b.name)
    })
}

/**
 * The badge points: one per through-route that has somewhere to sit.
 *
 * Each carries the line's own properties verbatim - so a tap on the badge
 * hands map/lineTaps.ts exactly what a tap on the line would - plus the two
 * image ids the layer's `coalesce` reads: the registry mark where the source
 * has one, and the blaze chip it falls through to.
 */
export function badgeFeatures(trails: readonly TrailInView[]): GeoJSON.FeatureCollection {
  return {
    type: 'FeatureCollection',
    features: trails
      .filter((trail) => trail.throughRoute && trail.anchor !== null)
      .map((trail) => ({
        type: 'Feature',
        properties: {
          ...trail.properties,
          [BADGE_NAME_PROPERTY]: trail.name,
          [BADGE_SOURCE_PROPERTY]: trail.source,
          [BADGE_MARK_PROPERTY]: trailMarkImageId(trail.source) ?? '',
          [BADGE_CHIP_PROPERTY]: blazeChipImageId(trail.blazeColor),
          [BADGE_FIT_PROPERTY]: trail.badgeFit,
          [BADGE_ANCHOR_PROPERTY]: trail.badgeAnchor,
        },
        geometry: { type: 'Point', coordinates: trail.anchor as Position },
      })),
  }
}

/**
 * Keeps the badge source and the caller current with the camera, and
 * returns a detach.
 *
 * Writes only on change: `idle` fires after every render, including the one
 * a `setData` here causes, so an unconditional write would chase its own
 * tail. Compared as the serialised list, which is what both consumers read.
 */
export function attachTrailsInView(
  map: TrailsInViewMap,
  onChange?: (trails: readonly TrailInView[]) => void,
  insets: ViewInsets = NO_INSETS,
  chosen: readonly string[] = CHOSEN_SYSTEM_SOURCES,
): () => void {
  let last = ''
  let listening = false

  const update = () => {
    const trails = trailsInView(map, insets, chosen)
    const key = JSON.stringify(trails)
    if (key === last) return
    last = key

    const source = map.getSource<GeoJSONSource>(TRAIL_BADGE_SOURCE_ID)
    if (source !== undefined && typeof source.setData === 'function') {
      source.setData(badgeFeatures(trails) as never)
    }
    onChange?.(trails)
  }

  const stopWaiting = whenStyleReady(
    map,
    () => map.getSource(TRAIL_BADGE_SOURCE_ID) !== undefined,
    () => {
      listening = true
      update()
      map.on('moveend', update)
      map.on('idle', update)
    },
    'Trail badges',
  )

  return () => {
    stopWaiting()
    if (!listening) return
    map.off('moveend', update)
    map.off('idle', update)
  }
}
