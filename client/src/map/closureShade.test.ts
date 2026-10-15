// The hatch a club's area closure is shaded with where no mapped trail runs
// inside it (decision 191), held to open-questions-1014.html's frame A: its
// stone inks and opacities, its 45-degree lines running up to the right,
// and a tile that repeats with no seam.

import { describe, expect, it } from 'vitest'
import { MockMap } from '../test/mocks/maplibre-gl'
import { clubClosureShadeImageId, SHADE_INKS } from './clubClosureLayers'
import {
  addClosureShadeImages,
  buildClosureShadeImage,
  SHADE_LINE_ALPHA,
  SHADE_PALETTE,
  SHADE_TILE_PX,
  SHADE_WASH_ALPHA,
} from './closureShade'
import { parseHex, POI_PIN_PIXEL_RATIO } from './poiIcons'

const SIDE = SHADE_TILE_PX * POI_PIN_PIXEL_RATIO

function pixel(image: { data: Uint8ClampedArray }, x: number, y: number): number[] {
  const i = (y * SIDE + x) * 4
  return Array.from(image.data.slice(i, i + 4))
}

describe('the shade’s hatch', () => {
  it('is frame A by day: stone-700 lines at 0.55 over a stone-500 wash at 0.10, in the design system’s hexes', () => {
    expect(SHADE_PALETTE.day).toEqual({ line: '#5a5346', wash: '#8a8271' })
    expect(SHADE_LINE_ALPHA).toBe(0.55)
    expect(SHADE_WASH_ALPHA).toBe(0.1)

    const image = buildClosureShadeImage('day')
    expect([image.width, image.height]).toEqual([SIDE, SIDE])
    // Between two lines, the wash alone.
    expect(pixel(image, 4, 4)).toEqual([...parseHex('#8a8271'), Math.round(0.1 * 255)])
    // On a line's centre, the line over the wash.
    const [r, g, b, a] = pixel(image, 15, 4)
    expect(a).toBe(Math.round((0.55 + 0.1 * 0.45) * 255))
    const mixed = parseHex('#5a5346').map((line, channel) =>
      Math.round((line * 0.55 + parseHex('#8a8271')[channel] * 0.1 * 0.45) / 0.595),
    )
    expect([r, g, b]).toEqual(mixed)
  })

  it('runs its lines up to the right, as frame A’s pattern turned 45 degrees does', () => {
    // (15, 4) is on the line x + y = 20, and on no line of the other
    // diagonal; (4, 4) is on that other diagonal's line and on none of these.
    const image = buildClosureShadeImage('day')
    expect(pixel(image, 15, 4)[3]).toBeGreaterThan(pixel(image, 4, 4)[3])
    expect(pixel(image, 4, 15)[3]).toBe(pixel(image, 15, 4)[3])
  })

  it('repeats with no seam: every pixel matches its neighbour along the line, across the tile’s edge too', () => {
    for (const ink of SHADE_INKS) {
      const image = buildClosureShadeImage(ink)
      for (let y = 0; y < SIDE; y += 1) {
        for (let x = 0; x < SIDE; x += 1) {
          expect(
            pixel(image, (x + 1) % SIDE, (y + SIDE - 1) % SIDE),
            `${ink} ${x},${y}`,
          ).toEqual(pixel(image, x, y))
        }
      }
    }
  })

  it('keeps the geometry and the alphas on every sheet and changes only the inks', () => {
    const alphas = (ink: (typeof SHADE_INKS)[number]) => {
      const { data } = buildClosureShadeImage(ink)
      return Array.from({ length: SIDE * SIDE }, (_, index) => data[index * 4 + 3])
    }
    expect(alphas('night')).toEqual(alphas('day'))
    expect(alphas('red')).toEqual(alphas('day'))
    expect(pixel(buildClosureShadeImage('night'), 4, 4).slice(0, 3)).toEqual([
      ...parseHex(SHADE_PALETTE.night.wash),
    ])
    expect(pixel(buildClosureShadeImage('red'), 4, 4).slice(0, 3)).toEqual([
      ...parseHex(SHADE_PALETTE.red.wash),
    ])
  })

  it('is registered once per sheet at the phone’s pixel ratio, and never added twice', () => {
    const map = new MockMap({})
    const added: Array<[string, unknown]> = []
    const addImage = map.addImage.bind(map)
    map.addImage = (id: string, image: unknown, options?: unknown) => {
      added.push([id, options])
      return addImage(id, image, options)
    }

    addClosureShadeImages(map as never)
    addClosureShadeImages(map as never)

    expect(added).toEqual(
      SHADE_INKS.map((ink) => [
        clubClosureShadeImageId(ink),
        { pixelRatio: POI_PIN_PIXEL_RATIO },
      ]),
    )
  })
})
