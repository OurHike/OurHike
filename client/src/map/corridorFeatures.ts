// The corridor view's features as GeoJSON: the miles ATC's centerline cannot
// attribute, the places responsibility changes hands, and the highlight marks
// (#598, #858, features/CORRIDOR_VIEW.md). Nothing here knows about MapLibre.
//
// SPLIT OUT OF map/corridorLayers.ts, for features/LAUNCH_BUDGET.md §4.4's
// rule: a constant the shell reads out of a screen-sized module belongs in a
// module of its own. App.tsx builds the corridor's collection itself
// (corridorWithHighlights, EMPTY_CORRIDOR) and hands it to the map screen, so
// while these lived beside the layer specs every launch parsed the layer
// builder, its tap handling and its source wiring on a Today screen that
// mounts no map. map/corridorLayers.ts imports the kinds and properties its
// filters and taps read from here and re-exports everything, the way
// map/style.ts re-exports map/styleIds.ts (#1591), so a reader that imported
// one from there still does. scripts/check-build-output.mjs refuses a string
// only the layer builder holds in any eager chunk, so it cannot drift back in.
//
// The division of labour is map/corridorLayers.ts's header's own, one step
// finer: lib/clubSections.ts is the data, lib/trailPosition.ts turns mile
// numbers into coordinates, this turns both into features, and
// map/corridorLayers.ts is the module that knows about MapLibre. The
// comments below travelled with the code they describe, unchanged.

import { clubBoundaryMiles, clubTimeline, type ClubSections } from '../lib/clubSections'
import { PROFILED_TRAIL } from '../lib/highlightDetail'
import type { Highlight } from '../lib/highlights'
import { trailPointAtMile, trailSlice, type TrailIndex } from '../lib/trailPosition'

/** Which of this source's two kinds of feature a layer wants. Both ride in one
 *  source because they are one answer - the corridor read end to end - and a
 *  second source would be a second thing to keep in step. */
export const CORRIDOR_KIND_PROPERTY = 'corridor_kind'
export const UNATTRIBUTED_KIND = 'unattributed'
export const BOUNDARY_KIND = 'boundary'
export const HIGHLIGHT_KIND = 'highlight'

/** Where a highlight marker carries its id, so a tap resolves to a record.
 *  A property rather than the GeoJSON feature id, for the reason
 *  CLOSURE_ID_PROPERTY gives: MapLibre runs a string feature id through
 *  parseInt, and a highlight id is a slug. */
export const HIGHLIGHT_ID_PROPERTY = 'highlight_id'

interface CorridorProperties {
  [CORRIDOR_KIND_PROPERTY]: string
  /** Present only on a highlight mark. */
  [HIGHLIGHT_ID_PROPERTY]?: string
}

export interface CorridorFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    geometry:
      | { type: 'MultiLineString'; coordinates: Array<Array<[number, number]>> }
      | { type: 'Point'; coordinates: [number, number] }
    properties: CorridorProperties
  }>
}

export const EMPTY_CORRIDOR: CorridorFeatureCollection = {
  type: 'FeatureCollection',
  features: [],
}

/**
 * The published attribution, in map coordinates.
 *
 * A run or a boundary the centerline index cannot place yields no coordinates
 * and is dropped. That is a gap in what this build knows rather than a
 * decision, and it is safe to drop for the reason closureBands gives about its
 * own: the words are elsewhere. A hiker who taps a stretch this declines to
 * draw still gets the club from lib/clubSections.ts, which never needed
 * geometry to answer.
 */
export function corridorFeatures(
  sections: ClubSections,
  index: TrailIndex,
): CorridorFeatureCollection {
  const timeline = clubTimeline(sections)

  const unattributed = sections.unattributed.flatMap((range) => {
    const lines = trailSlice(index, range.startMile, range.endMile)
    if (lines.length === 0) return []
    return [
      {
        type: 'Feature' as const,
        geometry: { type: 'MultiLineString' as const, coordinates: lines },
        properties: { [CORRIDOR_KIND_PROPERTY]: UNATTRIBUTED_KIND },
      },
    ]
  })

  const boundaries = clubBoundaryMiles(timeline).flatMap((mile) => {
    const point = trailPointAtMile(index, mile)
    if (point === null) return []
    return [
      {
        type: 'Feature' as const,
        geometry: { type: 'Point' as const, coordinates: point },
        properties: { [CORRIDOR_KIND_PROPERTY]: BOUNDARY_KIND },
      },
    ]
  })

  return { type: 'FeatureCollection', features: [...unattributed, ...boundaries] }
}

/**
 * The highlights, as one mark each at the start of the first A.T. leg (#858).
 *
 * A POINT rather than a line along the walk, and that is the two-colour
 * decision showing through: the trail's own colour means `blaze_color`, so a
 * highlight cannot recolour the ground it covers. It marks where the walk
 * BEGINS and the sheet says how far it runs - which is also the only thing
 * that stays true for a highlight whose other legs are on trails this map may
 * not be drawing (features/NEARBY_TRAILS.md: one chosen trail at a time).
 *
 * One mark, not every leg: a loop that leaves the A.T. and comes back is one
 * place on the corridor, and three marks for it would read as three walks.
 *
 * The FIRST leg that is on the A.T., rather than the first leg outright. All
 * ten entries published today are single-leg A.T. highlights, so nothing
 * exercises the difference yet - but a loop is naturally written in walking
 * order, and Franconia Ridge's is `[Falling Waters, A.T., Old Bridle Path]`.
 * Keyed off leg zero, that record would draw no mark at all and simply not be
 * on the map, which is the silent absence rather than the honest one.
 */
export function highlightFeatures(
  highlights: readonly Highlight[],
  index: TrailIndex,
): CorridorFeatureCollection {
  const features = highlights.flatMap((highlight) => {
    const leg = highlight.legs.find((candidate) => candidate.trail === PROFILED_TRAIL)
    // A highlight entirely off the A.T. has no place on this map to mark. It
    // still exists as a record; features/NEARBY_TRAILS.md's one-trail-at-a-time
    // rule is what would eventually draw it.
    if (leg === undefined) return []
    const point = trailPointAtMile(index, leg.startMile)
    if (point === null) return []
    return [
      {
        type: 'Feature' as const,
        geometry: { type: 'Point' as const, coordinates: point },
        properties: {
          [CORRIDOR_KIND_PROPERTY]: HIGHLIGHT_KIND,
          [HIGHLIGHT_ID_PROPERTY]: highlight.id,
        },
      },
    ]
  })
  return { type: 'FeatureCollection', features }
}

/** The corridor and the highlights in one collection - one source, because
 *  they are one answer about the same stretch of map. */
export function corridorWithHighlights(
  sections: ClubSections,
  highlights: readonly Highlight[],
  index: TrailIndex,
): CorridorFeatureCollection {
  const corridor = corridorFeatures(sections, index)
  return {
    type: 'FeatureCollection',
    features: [...corridor.features, ...highlightFeatures(highlights, index).features],
  }
}
