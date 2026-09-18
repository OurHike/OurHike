// The hiker's position on the canvas (#1581): one source, two layers, one
// GPS watch.
//
// WHAT THIS REPLACES. Until #1581 the only mark for where a hiker stood was
// MapLibre's `GeolocateControl` - a DOM marker styled by maplibre-gl.css and
// nothing of ours, fed by a `watchPosition` of its own that the header never
// saw. features/mockups/hiker-mark.html measured it: 15 px of `#1da1f2`, one
// degree of hue off the water pin, pulsing on a 2 s loop the design system's
// motion rule excludes, an accuracy disc with no floor, and a lost-fix state
// (`-stale`, grey, in place) that lib/positionLine.ts's `No GPS signal` could
// not agree with because the two ran on different watches. The control is
// gone (map/mapChrome.ts); what draws the hiker now reads the same
// `lib/useGeolocation.ts` state the header reads, so the mark cannot say
// something the header is not saying.
//
// TWO LAYERS, AND WHY EACH IS THE KIND IT IS.
//
//  - The accuracy ring is a `circle` layer, because a circle takes no part in
//    symbol placement (map/poiLayers.ts's dot rank is the precedent) and
//    because its radius is a distance on the ground: the 95 % radius the
//    platform reports, in pixels at the camera's zoom, floored at the mark's
//    own ring so an error smaller than the mark hides under it. At z14 a
//    10 m fix is 2.7 px and draws nothing of its own; a 100 m fix under
//    canopy is a 27 px ring past the floor - "somewhere in here", drawn.
//  - The mark is a `symbol` layer with `icon-allow-overlap` AND
//    `icon-ignore-placement`, like map/disputeLayers.ts and for the same two
//    reasons: the collision engine may never drop it (a hiker who cannot find
//    themselves is the first of CLAUDE.md's four ways this app hurts
//    somebody), and it may never push a pin aside (it is a viewer, not a
//    place, and the shelter under the hiker's feet is the pin they want).
//
// WHERE IT SITS: over every place, under the ATC's notices. map/style.ts
// draws both layers after the pins, the warnings and the workdays, and
// before buildAtcUpdateLayers - because "nothing on this map can cover" an
// ATC notice is a rule that was there first (src/test/atcAlertProminence
// .test.ts holds it), and a hiker standing on a closed shelter is better
// served by the closure drawn over their dot than by their dot drawn over
// the closure. The mark is hollow, so the notice hides its centre and
// nothing else: the ring and the ticks around it still say where they are.
//
// NO `minzoom`. Below the pin seam the opening camera draws lines only
// (#1292), so at z4.87 this is the only point on 2,197 miles of line - which
// is what somebody opening the app on a mountain wants it to be.
//
// LOST, NOT GONE. `useGeolocation` carries the last fix and when it landed
// through its `unavailable` state, and this draws it with the ring broken
// into the pins' eight dashes and the age printed under it, while the header
// keeps saying `No GPS signal`. Both are true at once: the phone has a last
// answer, and the answer is old. `denied`, `unsupported`, `idle` and
// `locating` draw nothing - there is no position to claim.

import type {
  GeoJSONSourceSpecification,
  LayerSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import type { GeolocationState } from '../lib/useGeolocation'
import type { PoiIconImage } from './poiIcons'
import {
  buildPositionMark,
  POSITION_INK_FAMILIES,
  POSITION_INKS,
  POSITION_MARK_PIXEL_RATIO,
  positionMarkId,
  RING_RADIUS,
  type PositionInk,
} from './positionMark'
import { whenStyleReady } from './styleReady'

export const POSITION_SOURCE_ID = 'hiker-position'
export const POSITION_ACCURACY_LAYER_ID = 'hiker-accuracy'
export const POSITION_LAYER_ID = 'hiker-mark'

/** The accuracy ring hides under the mark's own ring: below this many pixels
 *  the error is smaller than the mark, and drawing it would be a second ring
 *  on top of the first saying the same thing. */
export const ACCURACY_FLOOR_PX = RING_RADIUS

/** The one fontstack every label on this map uses (map/poiLabels.ts,
 *  map/liveTopo.ts), bundled under public/glyphs/ so the age prints offline. */
const FONT = ['Noto Sans Regular']

const EQUATOR_METRES = 40_075_016.686
/** MapLibre's tiles are 512 px, so its z0 is the whole equator in 512 px. */
const TILE_SIZE = 512
const METRES_PER_FOOT = 0.3048
/** The last zoom stop the radius expression is written out to - MapLibre's
 *  own maximum, so the curve never has to extrapolate. */
const MAX_ZOOM_STOP = 22

/**
 * A ground distance as pixels at zoom 0, at a latitude.
 *
 * The radius at any zoom is then r0 * 2^zoom exactly, which is what lets the
 * paint expression below carry the whole ramp with one property per feature
 * rather than a recompute on every camera move.
 */
export function accuracyRadiusAtZoomZero(metres: number, lat: number): number {
  return (metres * TILE_SIZE) / (EQUATOR_METRES * Math.cos((lat * Math.PI) / 180))
}

/**
 * How long ago a fix landed, in the mark's own words.
 *
 * Minutes rather than seconds: the tick that re-prints it (map/MapView.tsx)
 * runs once a minute, the cadence lib/useClock.ts already keeps for the
 * status strip, and a number that changed faster than it could be redrawn
 * would be a promise the mark cannot keep.
 */
export function fixAge(fixedAt: Date, now: Date): string {
  const minutes = Math.max(0, Math.floor((now.getTime() - fixedAt.getTime()) / 60_000))
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes} min ago`
  return `${Math.floor(minutes / 60)} h ago`
}

export interface PositionProperties {
  /** Whether this is the last fix of a lost signal rather than a live one. */
  stale: boolean
  /** The 95 % accuracy radius as pixels at zoom 0 - see accuracyRadiusAtZoomZero. */
  r0: number
  /** The age, printed under a stale mark; empty on a live one. */
  age: string
}

export interface PositionFeatureCollection {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    geometry: { type: 'Point'; coordinates: [number, number] }
    properties: PositionProperties
  }>
}

/**
 * The fix as the canvas draws it: one feature, or none.
 *
 * `now` is passed in rather than read, so a stale mark's age is a pure
 * function of two dates - and so a test can move the clock.
 */
export function positionFeatureCollection(
  fix: GeolocationState,
  now: Date,
): PositionFeatureCollection {
  const drawn =
    fix.status === 'located'
      ? { at: fix.at, accuracyFeet: fix.accuracyFeet, stale: false, age: '' }
      : fix.status === 'unavailable' && fix.last !== undefined
        ? {
            at: fix.last.at,
            accuracyFeet: fix.last.accuracyFeet,
            stale: true,
            age: fixAge(fix.last.fixedAt, now),
          }
        : null

  if (drawn === null) return { type: 'FeatureCollection', features: [] }

  return {
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        geometry: { type: 'Point', coordinates: [drawn.at.lon, drawn.at.lat] },
        properties: {
          stale: drawn.stale,
          r0: accuracyRadiusAtZoomZero(
            drawn.accuracyFeet * METRES_PER_FOOT,
            drawn.at.lat,
          ),
          age: drawn.age,
        },
      },
    ],
  }
}

export function buildPositionSource(): GeoJSONSourceSpecification {
  return { type: 'geojson', data: { type: 'FeatureCollection', features: [] } }
}

/**
 * `circle-radius` for the accuracy ring: max(floor, r0 * 2^zoom).
 *
 * A stop per integer zoom rather than two stops with base-2 interpolation
 * between them, because the floor has to be inside the outputs: MapLibre
 * allows `["zoom"]` only as the input of a top-level interpolate, so
 * `max(floor, interpolate(...))` is not an expression it will take. With
 * base-2 interpolation between stops whose outputs are both r0 * 2^z the
 * curve between them is exact; only in the one zoom band where the floor
 * takes over is it approximate, and there the ring is hiding under the mark.
 */
export function accuracyRadiusExpression(): unknown[] {
  const stops: unknown[] = []
  for (let zoom = 0; zoom <= MAX_ZOOM_STOP; zoom += 1) {
    stops.push(zoom, ['max', ACCURACY_FLOOR_PX, ['*', ['get', 'r0'], 2 ** zoom]])
  }
  return ['interpolate', ['exponential', 2], ['zoom'], ...stops]
}

/** Which image the mark draws, by whether the fix is live or the last one. */
export function positionIconExpression(ink: PositionInk): unknown[] {
  return ['case', ['get', 'stale'], positionMarkId(ink, true), positionMarkId(ink, false)]
}

export function buildPositionAccuracyLayer(
  ink: PositionInk = 'day',
  sourceId: string = POSITION_SOURCE_ID,
): LayerSpecification {
  return {
    id: POSITION_ACCURACY_LAYER_ID,
    type: 'circle',
    source: sourceId,
    paint: {
      'circle-radius': accuracyRadiusExpression() as unknown as number,
      // A wash with an edge, in the mark's own ink: faint enough to sit under
      // pins without hiding them, edged so its size can be read.
      'circle-color': POSITION_INKS[ink].ink,
      'circle-opacity': 0.07,
      'circle-stroke-color': POSITION_INKS[ink].ink,
      'circle-stroke-opacity': 0.45,
      'circle-stroke-width': 1,
    },
  }
}

export function buildPositionLayer(
  ink: PositionInk = 'day',
  sourceId: string = POSITION_SOURCE_ID,
): LayerSpecification {
  return {
    id: POSITION_LAYER_ID,
    type: 'symbol',
    source: sourceId,
    // No minzoom - see the header.
    layout: {
      'icon-image': positionIconExpression(ink) as unknown as string,
      'icon-size': 1,
      // See the header: never dropped, and never pushes a pin aside.
      'icon-allow-overlap': true,
      'icon-ignore-placement': true,
      // The age, under a stale mark only - a live one carries an empty string
      // and MapLibre draws no label for it.
      'text-field': ['get', 'age'] as unknown as string,
      'text-font': FONT,
      'text-size': 11,
      'text-anchor': 'top',
      // In ems of the text size: 1.7 * 11 px puts the top of the label just
      // under the ticks, which reach 17 px below the centre.
      'text-offset': [0, 1.7],
      'text-allow-overlap': true,
      'text-ignore-placement': true,
    },
    paint: {
      // A stale mark stands back a little as well as breaking its ring, the
      // way a stale pin fades (poiLayers.ts's POI_ICON_OPACITY_EXPRESSION).
      'icon-opacity': ['case', ['get', 'stale'], 0.8, 1] as unknown as number,
      'text-color': POSITION_INKS[ink].ink,
      'text-halo-color': POSITION_INKS[ink].paper,
      'text-halo-width': 1.4,
    },
  }
}

/**
 * Every mark image - three ink families, live and stale - built once per
 * page, whoever asks.
 *
 * WHAT IT COSTS, MEASURED: 53 ms for the six, cold, in the test runner on
 * a shared core (2026-09-17; 21 ms warm), which on a phone at a 4x throttle
 * is the better part of a frame's budget several times over. Paid at every
 * map mount it would sit in the launch path - the place map/poiIconImages.ts
 * moved the pins' 2,521 ms out of. So it is paid once, here, and never
 * before there is a fix to draw (map/MapView.tsx gates the attach on one),
 * which puts it seconds after launch, off the three-tap path. A worker
 * would take it off the main thread altogether; at 53 ms once, the
 * plumbing costs more than it saves.
 */
const builtMarks = new Map<string, PoiIconImage>()

export function positionMarkImage(ink: PositionInk, stale: boolean): PoiIconImage {
  const id = positionMarkId(ink, stale)
  let image = builtMarks.get(id)
  if (image === undefined) {
    image = buildPositionMark(ink, stale)
    builtMarks.set(id, image)
  }
  return image
}

/**
 * Registers every mark image on a live map, and returns a detach.
 *
 * All six at once rather than the current sheet's pair, so a theme switch is
 * a layout-property write (applyPositionInk) and never a rasterise while
 * somebody is walking.
 */
export function attachPositionImages(map: MapLibreMap): () => void {
  return whenStyleReady(
    map,
    () => map.getLayer(POSITION_LAYER_ID) !== undefined,
    () => {
      for (const ink of POSITION_INK_FAMILIES) {
        for (const stale of [false, true]) {
          const id = positionMarkId(ink, stale)
          if (map.hasImage(id)) continue
          map.addImage(id, positionMarkImage(ink, stale), {
            pixelRatio: POSITION_MARK_PIXEL_RATIO,
          })
        }
      }
    },
    'hiker mark images',
  )
}

/** Pushes the fix onto the live map, and returns a detach. */
export function attachPositionData(
  map: MapLibreMap,
  fix: GeolocationState,
  now: Date,
): () => void {
  return whenStyleReady(
    map,
    () => map.getSource(POSITION_SOURCE_ID) !== undefined,
    () => {
      const source = map.getSource<GeoJSONSource>(POSITION_SOURCE_ID)
      if (source === undefined || typeof source.setData !== 'function') return

      source.setData(positionFeatureCollection(fix, now) as never)
    },
    'hiker position',
  )
}

/**
 * Re-inks both layers for a sheet family, on a map that is already built.
 *
 * Called from map/style.ts's attachMapAppearance beside every other repaint,
 * and guarded per layer for the reason that function guards: the backdrop
 * proves the style takes writes, not that this layer is in it.
 */
export function applyPositionInk(map: MapLibreMap, ink: PositionInk): void {
  if (map.getLayer(POSITION_LAYER_ID) !== undefined) {
    map.setLayoutProperty(
      POSITION_LAYER_ID,
      'icon-image',
      positionIconExpression(ink) as never,
    )
    map.setPaintProperty(POSITION_LAYER_ID, 'text-color', POSITION_INKS[ink].ink as never)
    map.setPaintProperty(
      POSITION_LAYER_ID,
      'text-halo-color',
      POSITION_INKS[ink].paper as never,
    )
  }
  if (map.getLayer(POSITION_ACCURACY_LAYER_ID) !== undefined) {
    map.setPaintProperty(
      POSITION_ACCURACY_LAYER_ID,
      'circle-color',
      POSITION_INKS[ink].ink as never,
    )
    map.setPaintProperty(
      POSITION_ACCURACY_LAYER_ID,
      'circle-stroke-color',
      POSITION_INKS[ink].ink as never,
    )
  }
}
