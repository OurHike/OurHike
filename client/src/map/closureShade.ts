// The hatch a club's area closure is shaded with where no mapped trail runs
// inside it (decision 191, the maintainer's poll of 2026-10-14, "Shade them,
// no edge"), as pixels, and the one poke that registers it on a live map.
// map/clubClosureLayers.ts decides where it is drawn and why; this file only
// turns the chosen frame into a pattern image, the division map/closureCross.ts
// keeps with lib/closureStyle.ts.
//
// THE FRAME IS open-questions-1014.html's section 2, frame A, the picture the
// maintainer chose from: an SVG pattern of one line 1.3 px wide every 7 px,
// turned 45 degrees so the lines run up to the right, in the design system's
// stone-700 (#5a5346, `.claude/OurHike Design System/tokens/colors.css`) at
// 0.55 opacity, over a wash of its stone-500 (#8a8271) at 0.10. By day this
// draws exactly those values; the two other sheets keep the geometry and
// alphas and change the inks (SHADE_PALETTE).
//
// A COLOURED IMAGE, ONE PER SHEET, rather than closureCross.ts's distance
// field: a fill pattern takes no paint colour the way an `sdf` icon does, so
// a sheet change swaps which image the layer draws (map/style.ts's
// attachMapAppearance), as the through-route badge's plates are swapped
// (map/trailBadges.ts).
//
// SEAMLESS, because a pattern repeats its image edge to edge. Lines at 45
// degrees repeat across a square tile only when its side is a whole number
// of their spacing along an axis, which for a perpendicular spacing of s is
// s times root 2: 7 px would need 9.9. So the tile is SHADE_TILE_PX = 10
// CSS px and one line crosses it, 7.07 px from the next - frame A's 7 px to
// within a twentieth of a pixel (Reasoned).

import type { Map as MapLibreMap } from 'maplibre-gl'
import { clubClosureShadeImageId, SHADE_INKS, type ShadeInk } from './clubClosureLayers'
import { parseHex, POI_PIN_PIXEL_RATIO, type PoiIconImage } from './poiIcons'
import { RED_LIGHT_BLAZE_COLOR } from './sheetInks'

/** The pattern's side in CSS pixels: the smallest whole tile one 45-degree
 *  line per side repeats across with frame A's spacing (the header). */
export const SHADE_TILE_PX = 10

/** The hatch's stroke in CSS pixels, frame A's `stroke-width="1.3"`. */
export const SHADE_STROKE_PX = 1.3

/** Frame A's line opacity, `stroke-opacity="0.55"`. */
export const SHADE_LINE_ALPHA = 0.55

/** Frame A's wash opacity, `fill-opacity="0.10"`: enough to say the ground
 *  is set apart, little enough that contours read straight through it. */
export const SHADE_WASH_ALPHA = 0.1

/**
 * The line and wash inks per sheet. By day frame A's own stones. On a dark
 * sheet the line takes stone-300 (#c3baa4) over the same stone-500 wash:
 * at these alphas over night_hike's #0c1410 ground a stone-700 line stands
 * 1.50:1 off its wash and stone-300 3.58:1, against the day hatch's 2.49:1
 * on white paper (WCAG's luminance ratio, Reasoned from the hexes). Under
 * red light both take the mode's one hue (map/sheetInks.ts's
 * RED_LIGHT_BLAZE_COLOR), as every trail line does there. The two dark
 * variants are @unvalidated: drawn by reasoning from the day frame, which is
 * the only one anybody chose, and never looked at on a phone at night.
 */
export const SHADE_PALETTE: Readonly<Record<ShadeInk, { line: string; wash: string }>> = {
  day: { line: '#5a5346', wash: '#8a8271' },
  night: { line: '#c3baa4', wash: '#8a8271' },
  red: { line: RED_LIGHT_BLAZE_COLOR, wash: RED_LIGHT_BLAZE_COLOR },
}

/** Samples per pixel side: 4 x 4, so a 2.6-device-pixel stroke at 45
 *  degrees keeps an even edge. */
const SUPERSAMPLE = 4

/**
 * The hatch for one sheet, as straight-alpha RGBA at POI_PIN_PIXEL_RATIO,
 * ready for `map.addImage` (map/positionMark.ts's convention). Each pixel is
 * the wash with the line laid over it, by the fraction of the pixel's
 * samples the line covers: the line is every point whose distance to the
 * nearest of the lines x + y = k * side (screen axes, y down, so they run up
 * to the right) is within half the stroke.
 */
export function buildClosureShadeImage(ink: ShadeInk): PoiIconImage {
  const side = SHADE_TILE_PX * POI_PIN_PIXEL_RATIO
  const half = (SHADE_STROKE_PX * POI_PIN_PIXEL_RATIO) / 2
  const line = parseHex(SHADE_PALETTE[ink].line)
  const wash = parseHex(SHADE_PALETTE[ink].wash)
  const data = new Uint8ClampedArray(side * side * 4)
  for (let py = 0; py < side; py += 1) {
    for (let px = 0; px < side; px += 1) {
      let covered = 0
      for (let sy = 0; sy < SUPERSAMPLE; sy += 1) {
        for (let sx = 0; sx < SUPERSAMPLE; sx += 1) {
          const along = px + (sx + 0.5) / SUPERSAMPLE + (py + (sy + 0.5) / SUPERSAMPLE)
          const offset = along - Math.round(along / side) * side
          if (Math.abs(offset) / Math.SQRT2 <= half) covered += 1
        }
      }
      const lineAlpha = SHADE_LINE_ALPHA * (covered / (SUPERSAMPLE * SUPERSAMPLE))
      const alpha = lineAlpha + SHADE_WASH_ALPHA * (1 - lineAlpha)
      const i = (py * side + px) * 4
      for (let channel = 0; channel < 3; channel += 1) {
        data[i + channel] = Math.round(
          (line[channel] * lineAlpha +
            wash[channel] * SHADE_WASH_ALPHA * (1 - lineAlpha)) /
            alpha,
        )
      }
      data[i + 3] = Math.round(alpha * 255)
    }
  }
  return { width: side, height: side, data }
}

/**
 * Registers every sheet's hatch on a live map that does not hold it yet, so
 * a sheet change only swaps which one the layer names. Called with the data
 * (map/clubClosureTaps.ts), inside the wait for the style, before the first
 * shaded area reaches the source: a pattern the style names but the map
 * does not hold draws nothing and warns once. Never re-adds - images
 * outlive a style reload, and adding one twice throws.
 */
export function addClosureShadeImages(map: MapLibreMap): void {
  for (const ink of SHADE_INKS) {
    const id = clubClosureShadeImageId(ink)
    if (!map.hasImage(id)) {
      map.addImage(id, buildClosureShadeImage(ink), { pixelRatio: POI_PIN_PIXEL_RATIO })
    }
  }
}
