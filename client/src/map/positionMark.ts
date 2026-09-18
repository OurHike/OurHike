// The mark for where the hiker stands (#1581), as raw RGBA pixels.
//
// A HOLLOW RING, A CENTRE DOT, FOUR TICKS - and no hue of its own. Every
// place on this map is a filled accent disc (map/poiIcons.ts), so the one
// thing on it that is not a place is the one hollow thing, and it is drawn in
// the sheet's own ink rather than in a colour: stone-900 on the day sheets,
// bone-100 on the dark ones, the red-light amber under red light. The drawn
// record of why - the stock blue dot measured against the pins it had to be
// found among - is features/mockups/hiker-mark.html, option A.
//
// It is also the locate button's own glyph at map scale. MapLibre's icon for
// that control is a ring, a dot and four ticks, so the thing a hiker taps and
// the thing that appears are the same shape (map/mapChrome.ts draws the
// button's copy as SVG from the same proportions).
//
// SIZED TO SIT INSIDE A PIN, NOT AROUND ONE. The ring's radius is 11 px and
// the ticks reach 17, so the whole mark is a 36 px box - 2 px under a 38 px
// pin - and its ink is about a fifth of a pin disc's (224 px² against 1,134,
// measured as arithmetic on the geometry below). Standing at a shelter leaves
// the shelter readable through the ring. @unvalidated - the floor is a
// fingertip's guess, and what would settle it is whether 36 px is found in a
// quarter-second at arm's length in sun with a gloved thumb, which is the
// outdoor pass (#105) and nobody else.
//
// Its own tiny rasteriser rather than `buildPinImage`, for the reason
// map/disputeMark.ts gives: that function draws a PIN, and every part of a
// pin is a thing this deliberately is not. Supersampled 3x3 like the pins,
// because a 2.5 px ring at 2x with hard edges shows its stairs.

import {
  parseHex,
  PIN_EDGE_COLOR,
  PIN_HALO_COLOR,
  rimHasInk,
  type PoiIconImage,
} from './poiIcons'

/** Rendered size in CSS pixels: the box the ticks reach, plus their casing. */
export const POSITION_MARK_SIZE = 36

/** Drawn at 2x, like the pins, so the ring stays crisp on a phone. */
export const POSITION_MARK_PIXEL_RATIO = 2

/**
 * The ring's radius in CSS px, to the middle of its ink. Also the floor the
 * accuracy ring (map/positionLayers.ts) hides under: an error smaller than
 * the mark is drawn as the mark alone.
 */
export const RING_RADIUS = 11

/** The ring's ink, and the paper either side of it. */
const RING_INK = 2.5
const CASING = 1.5
/** The ticks, along the four axes: from just outside the ring's casing to
 *  the edge of the box. */
const TICK_FROM = 13
const TICK_TO = 17
const TICK_INK_HALF = 1
const TICK_CASING_HALF = 2.25
/** The centre dot. */
const DOT_INK = 2.5
const DOT_CASING = 3.75

/** Sub-samples per axis - the pins' own figure. */
const SUPERSAMPLE = 3

/**
 * Which ink the mark is drawn in - one family per kind of sheet, not one per
 * sheet. The dark sheets' backdrops run from #0c1410 to #191108 and a
 * near-black casing separates bone ink from every one of them; drawing ten
 * variants to match ten backdrops would be ten images for a difference no
 * panel shows.
 */
export type PositionInk = 'day' | 'night' | 'red'

export const POSITION_INK_FAMILIES: readonly PositionInk[] = ['day', 'night', 'red']

/**
 * The ink and the casing per family.
 *
 * Day is the pins' own hairline and halo, so the mark and the pins are drawn
 * from one pair of colours. Night is `--bone-100` on night_hike's backdrop
 * (map/style.ts's MAP_BACKDROP.dark), red light is RED_LIGHT_BLAZE_COLOR on
 * the red sheet's backdrop (map/liveTopo.ts) - written as hexes here rather
 * than imported, because this module is drawn by a rasteriser that style.ts
 * imports, and the pins keep their colours the same way.
 */
export const POSITION_INKS: Record<PositionInk, { ink: string; paper: string }> = {
  day: { ink: PIN_EDGE_COLOR, paper: PIN_HALO_COLOR },
  night: { ink: '#ece7db', paper: '#0c1410' },
  red: { ink: '#e8804a', paper: '#140503' },
}

/** Stable image id, and the string the layer's `icon-image` resolves to.
 *  Namespaced away from `poi-*`: this is not a waypoint. */
export function positionMarkId(ink: PositionInk, stale: boolean): string {
  return `hiker-mark-${ink}${stale ? '-stale' : ''}`
}

type Coverage = 'ink' | 'paper' | 'none'

/**
 * What a point at (x, y) CSS px from the centre is covered by.
 *
 * Ink anywhere wins over paper anywhere, so a tick's inner end is not clipped
 * by the ring's casing and the dot is not clipped by anything. A stale mark
 * loses the ring's ink AND its casing in the gaps, so the gaps are open
 * rather than paper-filled - the same `rimHasInk` the pins break their rim
 * with, at the same eight dashes.
 */
function coverageAt(x: number, y: number, stale: boolean): Coverage {
  const d = Math.hypot(x, y)
  const gap = stale && !rimHasInk(x, y, 'low')
  const along = Math.max(Math.abs(x), Math.abs(y))
  const across = Math.min(Math.abs(x), Math.abs(y))

  const ringInk = !gap && Math.abs(d - RING_RADIUS) <= RING_INK / 2
  const tickInk = along >= TICK_FROM && along <= TICK_TO && across <= TICK_INK_HALF
  const dotInk = d <= DOT_INK
  if (ringInk || tickInk || dotInk) return 'ink'

  const reach = TICK_CASING_HALF - TICK_INK_HALF
  const ringPaper = !gap && Math.abs(d - RING_RADIUS) <= RING_INK / 2 + CASING
  const tickPaper =
    along >= TICK_FROM - reach && along <= TICK_TO + reach && across <= TICK_CASING_HALF
  const dotPaper = d <= DOT_CASING
  return ringPaper || tickPaper || dotPaper ? 'paper' : 'none'
}

/**
 * The mark, as raw RGBA pixels, ready for `map.addImage`.
 *
 * Straight (un-premultiplied) alpha: an edge pixel carries the mix of ink and
 * paper that covered it and the fraction of it that was covered at all, which
 * is what MapLibre expects of an image and what keeps the hole in the middle
 * a hole rather than a paper disc.
 */
export function buildPositionMark(
  ink: PositionInk,
  stale: boolean,
  sizePx: number = POSITION_MARK_SIZE,
  pixelRatio: number = POSITION_MARK_PIXEL_RATIO,
): PoiIconImage {
  const pixels = Math.round(sizePx * pixelRatio)
  const data = new Uint8ClampedArray(pixels * pixels * 4)
  const inkRgb = parseHex(POSITION_INKS[ink].ink)
  const paperRgb = parseHex(POSITION_INKS[ink].paper)
  const centre = pixels / 2
  const samples = SUPERSAMPLE * SUPERSAMPLE

  for (let y = 0; y < pixels; y += 1) {
    for (let x = 0; x < pixels; x += 1) {
      let inkHits = 0
      let paperHits = 0
      for (let sy = 0; sy < SUPERSAMPLE; sy += 1) {
        for (let sx = 0; sx < SUPERSAMPLE; sx += 1) {
          const px = (x + (sx + 0.5) / SUPERSAMPLE - centre) / pixelRatio
          const py = (y + (sy + 0.5) / SUPERSAMPLE - centre) / pixelRatio
          const covered = coverageAt(px, py, stale)
          if (covered === 'ink') inkHits += 1
          else if (covered === 'paper') paperHits += 1
        }
      }
      const covered = inkHits + paperHits
      if (covered === 0) continue

      const at = (y * pixels + x) * 4
      for (let channel = 0; channel < 3; channel += 1) {
        data[at + channel] = Math.round(
          (inkRgb[channel] * inkHits + paperRgb[channel] * paperHits) / covered,
        )
      }
      data[at + 3] = Math.round((255 * covered) / samples)
    }
  }

  return { width: pixels, height: pixels, data }
}
