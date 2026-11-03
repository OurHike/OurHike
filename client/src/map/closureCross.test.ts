import { describe, it, expect } from 'vitest'
import { MockMap } from '../test/mocks/maplibre-gl'
import {
  attachClosureCrossIcon,
  buildClosureCrossIcon,
  crossDistance,
  SDF_EDGE,
  SDF_UNITS,
} from './closureCross'
import { POI_PIN_PIXEL_RATIO } from './poiIcons'
import {
  CLOSURE_CROSS_ARM,
  CLOSURE_CROSS_HALO_WIDTH,
  CLOSURE_CROSS_ICON_ID,
  CLOSURE_CROSS_PADDING,
  CLOSURE_CROSS_STROKE,
  CLOSURE_LAYER_ID,
  CLOSURE_MARK_HALO_WIDTH,
  CLOSURE_MARK_SIZE,
  closureCrossImageSize,
  closureCrossesId,
} from '../lib/closureStyle'

// The closure's cross (#1677), measured on its own pixels. The image is a
// distance field, so what is asserted is the FIELD: where the ink's edge
// falls, that it falls the same way on every arm, and that the image leaves
// room for the halos the style asks for. The picture a hiker sees is the
// shader's reading of these numbers; closureStyle.test.ts holds the style.

const IMAGE = buildClosureCrossIcon()
const SIDE = IMAGE.width

/** The field's value, 0-1, at a point given in CSS pixels from the centre. */
function fieldAt(x: number, y: number): number {
  const px = Math.floor(SIDE / 2 + x * POI_PIN_PIXEL_RATIO)
  const py = Math.floor(SIDE / 2 + y * POI_PIN_PIXEL_RATIO)
  return IMAGE.data[(py * SIDE + px) * 4 + 3] / 255
}

describe('the closure cross image', () => {
  it('is the size the style is told it is, at the pins’ pixel ratio', () => {
    expect(IMAGE.width).toBe(closureCrossImageSize() * POI_PIN_PIXEL_RATIO)
    expect(IMAGE.height).toBe(IMAGE.width)
    expect(IMAGE.data.length).toBe(IMAGE.width * IMAGE.height * 4)
  })

  it('is ink at the centre and along both diagonals, and ground off them', () => {
    // Inside the ink the field is over the edge value; off it, under.
    expect(fieldAt(0, 0)).toBeGreaterThan(SDF_EDGE)
    for (const [sx, sy] of [
      [1, 1],
      [-1, 1],
      [1, -1],
      [-1, -1],
    ]) {
      const along = CLOSURE_CROSS_ARM * 0.7
      expect(fieldAt(sx * along, sy * along), `${sx},${sy}`).toBeGreaterThan(SDF_EDGE)
    }
    // Straight up from the centre, past the strokes: not ink.
    expect(fieldAt(0, -CLOSURE_CROSS_ARM)).toBeLessThan(SDF_EDGE)
  })

  it('puts the edge half a stroke off each centreline, the same on every arm', () => {
    // The signed distance the image encodes, checked against the geometry
    // it was built from: zero on the edge, one unit per CSS pixel.
    // At the centre, half a stroke inside; one CSS pixel past the round end
    // of each of the four arms, exactly one unit outside.
    expect(crossDistance(0, 0)).toBeCloseTo(-CLOSURE_CROSS_STROKE / 2, 10)
    const tip = CLOSURE_CROSS_ARM + (CLOSURE_CROSS_STROKE / 2 + 1) / Math.SQRT2
    for (const [sx, sy] of [
      [1, 1],
      [-1, 1],
      [1, -1],
      [-1, -1],
    ]) {
      expect(crossDistance(sx * tip, sy * tip), `${sx},${sy}`).toBeCloseTo(1, 10)
    }
    expect(SDF_UNITS).toBe(8)
  })

  it('leaves room in the image for both halos the style asks for', () => {
    // A halo reaches `icon-halo-width / icon-size` units past the edge, and
    // the field must still be above zero there or the halo is clipped flat.
    const reachNeeded = Math.max(
      CLOSURE_CROSS_HALO_WIDTH,
      CLOSURE_MARK_HALO_WIDTH / CLOSURE_MARK_SIZE,
    )
    expect(reachNeeded).toBeLessThanOrEqual(CLOSURE_CROSS_PADDING)
    expect(SDF_EDGE - reachNeeded / SDF_UNITS).toBeGreaterThan(0)
  })

  it('carries the distance in alpha alone, with white in every colour channel', () => {
    for (let i = 0; i < IMAGE.data.length; i += 4) {
      expect(IMAGE.data[i]).toBe(255)
      expect(IMAGE.data[i + 1]).toBe(255)
      expect(IMAGE.data[i + 2]).toBe(255)
    }
  })
})

describe('attachClosureCrossIcon', () => {
  it('registers the cross as a distance field once the chain layer exists', () => {
    const map = new MockMap({})
    map.layerIds = [closureCrossesId(CLOSURE_LAYER_ID)]
    const detach = attachClosureCrossIcon(map as never)

    expect(map.hasImage(CLOSURE_CROSS_ICON_ID)).toBe(true)
    expect(map.imageOptions.get(CLOSURE_CROSS_ICON_ID)).toEqual({
      pixelRatio: POI_PIN_PIXEL_RATIO,
      sdf: true,
    })
    detach()
  })

  it('never adds the image twice, which MapLibre throws on', () => {
    const map = new MockMap({})
    map.layerIds = [closureCrossesId(CLOSURE_LAYER_ID)]
    attachClosureCrossIcon(map as never)()
    const first = map.images.get(CLOSURE_CROSS_ICON_ID)
    attachClosureCrossIcon(map as never)()

    expect(map.images.get(CLOSURE_CROSS_ICON_ID)).toBe(first)
  })
})
