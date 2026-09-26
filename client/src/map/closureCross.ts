// The closure's cross (#1677), as a signed distance field, and the one
// imperative poke that registers it on a live map.
//
// lib/closureStyle.ts decides what the cross is - its arms, its stroke, the
// room it leaves for a halo - and why; this file only turns those numbers
// into pixels, the division map/atcNoticeMark.ts keeps with
// lib/atcUpdateStyle.ts.
//
// A DISTANCE FIELD RATHER THAN COLOURED PIXELS, which is the one departure
// from the other marks' images and the reason for it. A closure's ink and
// halo change with the sheet (map/style.ts's closureInk and
// closureTapeGround), and an `sdf` image takes both as paint properties -
// `icon-color` and `icon-halo-color` - that a sheet change repaints in place,
// exactly as it repaints the paper's `line-color`. A coloured image would need
// one image per sheet and a layout swap on every change, which is what the
// through-route badge's plates carry (map/trailBadges.ts) and what this mark
// does not need to.
//
// THE ENCODING IS MAPLIBRE'S GLYPH CONVENTION: the alpha channel holds 0.75 on
// the ink's edge and falls by 1/8 per unit of distance outward (and rises
// inward). MapLibre's symbol shader reads `icon-halo-width` in those same
// units divided by the icon's size, so encoding one unit per CSS pixel of the
// image at `icon-size: 1` makes a halo width in the style mean CSS pixels on
// screen at any size. The shader's constants are `SDF_PX = 8` and the 192/256
// edge in maplibre-gl's symbol_sdf fragment shader.

import type { Map as MapLibreMap } from 'maplibre-gl'
import {
  CLOSURE_CROSS_ARM,
  CLOSURE_CROSS_ICON_ID,
  CLOSURE_CROSS_STROKE,
  CLOSURE_LAYER_ID,
  closureCrossImageSize,
  closureCrossesId,
} from '../lib/closureStyle'
import { POI_PIN_PIXEL_RATIO, type PoiIconImage } from './poiIcons'
import { whenStyleReady } from './styleReady'

/** The field's value on the ink's edge, as a fraction of full alpha. */
export const SDF_EDGE = 0.75

/** Distance units per full alpha: one unit is one CSS pixel here. */
export const SDF_UNITS = 8

/** Distance from (px, py) to the segment (ax, ay)-(bx, by). */
function segmentDistance(
  px: number,
  py: number,
  ax: number,
  ay: number,
  bx: number,
  by: number,
): number {
  const vx = bx - ax
  const vy = by - ay
  const t = Math.max(
    0,
    Math.min(1, ((px - ax) * vx + (py - ay) * vy) / (vx * vx + vy * vy)),
  )
  return Math.hypot(px - (ax + t * vx), py - (ay + t * vy))
}

/**
 * Signed distance from a point to the cross's ink, in CSS pixels, with the
 * point measured from the cross's centre: negative inside the ink, zero on
 * its edge. Two round-ended strokes along the diagonals, so the distance is
 * the nearer stroke's centreline distance less half the stroke.
 */
export function crossDistance(x: number, y: number): number {
  const a = CLOSURE_CROSS_ARM
  const nearest = Math.min(
    segmentDistance(x, y, -a, -a, a, a),
    segmentDistance(x, y, a, -a, -a, a),
  )
  return nearest - CLOSURE_CROSS_STROKE / 2
}

/**
 * The cross as an `sdf` image at POI_PIN_PIXEL_RATIO: every channel white,
 * the distance in alpha. MapLibre reads only the alpha of an sdf image, and
 * white keeps the image honest if anything ever draws it without `sdf`.
 */
export function buildClosureCrossIcon(): PoiIconImage {
  const side = closureCrossImageSize() * POI_PIN_PIXEL_RATIO
  const data = new Uint8ClampedArray(side * side * 4)
  const half = side / 2
  for (let py = 0; py < side; py += 1) {
    for (let px = 0; px < side; px += 1) {
      const x = (px + 0.5 - half) / POI_PIN_PIXEL_RATIO
      const y = (py + 0.5 - half) / POI_PIN_PIXEL_RATIO
      const value = SDF_EDGE - crossDistance(x, y) / SDF_UNITS
      const i = (py * side + px) * 4
      data[i] = 255
      data[i + 1] = 255
      data[i + 2] = 255
      data[i + 3] = Math.round(Math.max(0, Math.min(1, value)) * 255)
    }
  }
  return { width: side, height: side, data }
}

/**
 * Registers the cross on a live map, and returns a detach.
 *
 * NOT gated on there being any closures, for the reason the ATC notice mark
 * is not (map/atcUpdateLayers.ts): the long-term closures arrive inside the
 * network tiles rather than through a data effect, so there is no moment
 * "the first closure arrived" to wait for, and a chain drawn before its
 * image exists draws nothing at all. Waits for the chain's layer, which is
 * the condition `addImage` actually requires, and never re-adds - images
 * outlive a style reload and adding one twice throws.
 */
export function attachClosureCrossIcon(map: MapLibreMap): () => void {
  return whenStyleReady(
    map,
    () => map.getLayer(closureCrossesId(CLOSURE_LAYER_ID)) !== undefined,
    () => {
      if (!map.hasImage(CLOSURE_CROSS_ICON_ID)) {
        map.addImage(CLOSURE_CROSS_ICON_ID, buildClosureCrossIcon(), {
          pixelRatio: POI_PIN_PIXEL_RATIO,
          sdf: true,
        })
      }
    },
    'closure cross image',
  )
}
