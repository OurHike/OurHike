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
// `@unvalidated` as a display choice: the longest-visible-run rule was
// chosen against the handoff's four cameras, not watched on a phone in a
// hiker's hand. What would settle it is somebody panning through a park
// with a badge on screen and reporting whether it jumps in a way that
// distracts - the alternative is anchoring to the vertex nearest the
// screen's centre, which is steadier under panning and sits exactly where a
// following hiker's own dot is.

import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { CHOSEN_SYSTEM_SOURCES } from './nearbyTrails'
import { TAPPABLE_BLAZE_LAYER_IDS } from './style'
import { whenStyleReady } from './styleReady'
import {
  BADGE_CHIP_PROPERTY,
  BADGE_MARK_PROPERTY,
  BADGE_NAME_PROPERTY,
  BADGE_SOURCE_PROPERTY,
  BADGE_SOURCES,
  TRAIL_BADGE_SOURCE_ID,
  blazeChipImageId,
  trailMarkImageId,
} from './trailBadges'

/** The real MapLibre map - see map/drawnPois.ts for why not a structural
 *  stand-in. */
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
  /** Whether the trail is in the chosen system, and so drawn solid. */
  chosen: boolean
  /** A vertex on the trail, in view, where its badge sits; null where none of
   *  the drawn geometry put a vertex inside the viewport. */
  anchor: [number, number] | null
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

/** The vertex at half the run's length along it. */
function midpoint(run: Run): Position {
  if (run.points.length === 1) return run.points[0]
  const half = run.length / 2
  let walked = 0
  for (let i = 1; i < run.points.length; i += 1) {
    const step = span(run.points[i - 1], run.points[i])
    if (walked + step >= half) {
      // The nearer of the segment's two ends: a vertex ON the line, which
      // is the whole promise, rather than a point interpolated between two.
      return half - walked < step / 2 ? run.points[i - 1] : run.points[i]
    }
    walked += step
  }
  return run.points[run.points.length - 1]
}

function stringProp(properties: Record<string, unknown>, key: string): string | null {
  const value = properties[key]
  return typeof value === 'string' && value !== '' ? value : null
}

/**
 * Every named trail the trail layers are drawing, one entry per name,
 * through-routes first, then the chosen system, then by name.
 *
 * Read off the four full-line layers - both halves of both splits
 * (style.ts's TAPPABLE_BLAZE_LAYER_IDS) - and not the sketches, which carry
 * no `name`. Empty where the layers are not in the style yet, which is a
 * cold start's honest answer.
 */
export function trailsInView(map: TrailsInViewMap): TrailInView[] {
  const layers = TAPPABLE_BLAZE_LAYER_IDS.filter((id) => map.getLayer(id) !== undefined)
  if (layers.length === 0) return []

  const bounds = map.getBounds()
  const view: Bounds = {
    west: bounds.getWest(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    north: bounds.getNorth(),
  }

  const features = map.queryRenderedFeatures(undefined, { layers })
  const byName = new Map<string, TrailInView & { best: Run | null }>()

  for (const feature of features) {
    const properties = (feature.properties ?? {}) as Record<string, unknown>
    const name = stringProp(properties, 'name')
    if (name === null) continue
    const source = stringProp(properties, 'source') ?? ''
    const throughRoute = BADGE_SOURCES.includes(source)
    const chosen = CHOSEN_SYSTEM_SOURCES.includes(source)

    let best: Run | null = null
    for (const part of partsOf(feature.geometry)) {
      for (const run of visibleRuns(part, view)) {
        if (best === null || run.length > best.length) best = run
      }
    }

    const existing = byName.get(name)
    if (existing === undefined) {
      byName.set(name, {
        name,
        source,
        blazeColor: stringProp(properties, 'blaze_color'),
        throughRoute,
        chosen,
        anchor: null,
        properties,
        best,
      })
      continue
    }
    // A second piece of the same trail: the badge goes on whichever piece
    // shows the most of it, and the through-route's piece names it.
    if (best !== null && (existing.best === null || best.length > existing.best.length)) {
      existing.best = best
    }
    if (throughRoute && !existing.throughRoute) {
      existing.throughRoute = true
      existing.source = source
      existing.blazeColor = stringProp(properties, 'blaze_color')
      existing.properties = properties
    }
    existing.chosen = existing.chosen || chosen
  }

  return [...byName.values()]
    .map(({ best, ...trail }) => ({
      ...trail,
      anchor: best === null ? null : midpoint(best),
    }))
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
): () => void {
  let last = ''
  let listening = false

  const update = () => {
    const trails = trailsInView(map)
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
