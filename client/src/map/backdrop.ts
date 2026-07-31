// The texture drawn where the map has no topo tile.
//
// style.ts already guarantees the map is never black: its background layer
// paints paper under everything. This module is the second half of that answer,
// and it exists because plain paper has a different problem - it looks like a
// finished map of an empty place. Off the corridor archive the honest claim is
// "no data here," not "nothing here," and value #4 (trustworthy above all) makes
// that distinction load-bearing rather than decorative.
//
// The trick is that no coverage maths is needed to draw it. The hatch is painted
// by the background layer, which sits UNDER the opaque topo raster - so it shows
// through exactly where a tile is missing and is hidden everywhere a tile
// rendered. The map tells the truth about its own coverage for free.
//
// The pattern is generated rather than shipped as an asset: it is 32x32 flat
// colour, an offline-first app should not spend a network round trip or a build
// step on that, and a pure function is testable in jsdom, which cannot rasterise
// an SVG or run a canvas.

import type { Map as MapLibreMap } from 'maplibre-gl'
import { BACKDROP_LAYER_ID, MAP_BACKGROUND_COLOR } from './style'

export const BACKDROP_PATTERN_ID = 'off-archive-hatch'

/** Tile edge in pixels. A power of two, and an exact multiple of the spacing
 *  below, so the diagonals meet seamlessly across tile joins. */
export const BACKDROP_TILE_SIZE = 32

/** Pixels between hatch lines, measured along the x+y diagonal. */
export const BACKDROP_HATCH_SPACING = 16

/**
 * `--stone-300` mixed 35% into `--paper-100`, precomputed rather than blended at
 * runtime with an alpha channel. A fully opaque tile is what keeps the promise:
 * a translucent pixel would let the black behind the canvas back in through the
 * very texture drawn to keep it out.
 */
export const BACKDROP_HATCH_COLOR: readonly [number, number, number] = [229, 223, 209]

export interface BackdropPattern {
  width: number
  height: number
  data: Uint8ClampedArray
}

function parseHex(hex: string): [number, number, number] {
  const value = Number.parseInt(hex.replace('#', ''), 16)
  return [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff]
}

/**
 * The RGBA pixels of one hatch tile: the style's own background colour, ruled
 * with faint 45° lines.
 *
 * Reads its base colour from {@link MAP_BACKGROUND_COLOR} instead of repeating
 * the hex, so the patterned areas and the flat fallback can never drift apart -
 * whichever one is showing, the paper is the same paper.
 */
export function buildBackdropPattern(): BackdropPattern {
  const [pr, pg, pb] = parseHex(MAP_BACKGROUND_COLOR)
  const [hr, hg, hb] = BACKDROP_HATCH_COLOR
  const data = new Uint8ClampedArray(BACKDROP_TILE_SIZE * BACKDROP_TILE_SIZE * 4)

  for (let y = 0; y < BACKDROP_TILE_SIZE; y += 1) {
    for (let x = 0; x < BACKDROP_TILE_SIZE; x += 1) {
      const onHatch = (x + y) % BACKDROP_HATCH_SPACING === 0
      const at = (y * BACKDROP_TILE_SIZE + x) * 4

      data[at] = onHatch ? hr : pr
      data[at + 1] = onHatch ? hg : pg
      data[at + 2] = onHatch ? hb : pb
      data[at + 3] = 255
    }
  }

  return { width: BACKDROP_TILE_SIZE, height: BACKDROP_TILE_SIZE, data }
}

/**
 * Hangs the hatch on the style's background layer, and returns a detach
 * function.
 *
 * Deliberately best-effort. `background-pattern` needs an image registered on a
 * loaded style, which is a later and more fragile moment than style
 * construction; if any of it fails the flat paper colour is still painted, which
 * is the part that actually has to hold. So a failure here costs texture, never
 * a black screen, and is warned about rather than thrown.
 */
export function attachMapBackdrop(map: MapLibreMap): () => void {
  let detached = false

  const apply = () => {
    if (detached) return

    try {
      if (!map.hasImage(BACKDROP_PATTERN_ID)) {
        map.addImage(BACKDROP_PATTERN_ID, buildBackdropPattern())
      }
      map.setPaintProperty(BACKDROP_LAYER_ID, 'background-pattern', BACKDROP_PATTERN_ID)
    } catch (error) {
      console.warn('Off-archive backdrop pattern not applied; paper only.', error)
    }
  }

  // `isStyleLoaded()` is checked first because a map that finished loading
  // before this ran will never fire `load` again - waiting for it would leave
  // the hatch permanently unapplied on exactly the fast path.
  if (map.isStyleLoaded()) apply()
  else map.on('load', apply)

  return () => {
    detached = true
    map.off('load', apply)
  }
}
