import { describe, it, expect } from 'vitest'
import { buildAtcNoticeIcon, insideNoticeMark, ATC_NOTICE_GLYPH } from './atcNoticeMark'
import { parseHex, POI_PIN_PIXEL_RATIO } from './poiIcons'
import { WARNING_GLYPH } from './warningPin'
import {
  ATC_NOTICE_CASING_WIDTH,
  ATC_NOTICE_GLYPH_BOX,
  ATC_UPDATE_CASING_COLOR,
  ATC_UPDATE_COLOR,
  ATC_UPDATE_POINT_DRAWN_WIDTH,
} from '../lib/atcUpdateStyle'

// The ATC's point notice, measured on its own pixels.
//
// THIS FILE EXISTS BECAUSE THE GEOMETRY WAS RIGHT AND THE PICTURE WAS WRONG
// (#1071). The burst this mark used to be had eight spokes, an open centre
// and clear ground between the spokes by every number in
// lib/atcUpdateStyle.ts - and rendered as a black disc with red spokes on
// it, because it carried the band's 2px casing. Nothing in the spec could see
// that; only the alpha channel could.
//
// The mark is the hazard triangle since 2026-09-10 (the maintainer's call:
// the serious-warning pin's glyph, bare, for the ATC notices too), and what
// is asserted is still TRANSPARENCY sampled off the rendered image: the hole
// inside the band, off the exclamation, carries no ink at all; nothing
// outside the drawn width does; and the total is a measured fraction of what
// the disc put on the map. Those are the properties a hiker actually gets.

const IMAGE = buildAtcNoticeIcon()
const CENTER = IMAGE.width / 2

/** Everything below works in the image's own pixels, which are `sizePx` × 2. */
const BOX = ATC_NOTICE_GLYPH_BOX * POI_PIN_PIXEL_RATIO
const CASING = ATC_NOTICE_CASING_WIDTH * POI_PIN_PIXEL_RATIO

/** The pixel at a glyph-box coordinate (0-1, y down), as `[r, g, b, a]`. */
function at(gx: number, gy: number): [number, number, number, number] {
  const x = Math.round(CENTER + (gx - 0.5) * BOX - 0.5)
  const y = Math.round(CENTER + (gy - 0.5) * BOX - 0.5)
  if (x < 0 || y < 0 || x >= IMAGE.width || y >= IMAGE.height) {
    throw new Error(`at(${gx}, ${gy}) is outside the ${IMAGE.width}px image`)
  }
  const i = (y * IMAGE.width + x) * 4
  return [IMAGE.data[i], IMAGE.data[i + 1], IMAGE.data[i + 2], IMAGE.data[i + 3]]
}

/** Every pixel that carries any ink at all, as `{ dx, dy, alpha }` from the centre. */
function inkedPixels(): Array<{ dx: number; dy: number; alpha: number }> {
  const found: Array<{ dx: number; dy: number; alpha: number }> = []
  for (let index = 0; index < IMAGE.data.length; index += 4) {
    if (IMAGE.data[index + 3] === 0) continue
    const pixel = index / 4
    found.push({
      dx: (pixel % IMAGE.width) + 0.5 - CENTER,
      dy: Math.floor(pixel / IMAGE.width) + 0.5 - CENTER,
      alpha: IMAGE.data[index + 3],
    })
  }
  return found
}

function hex(channels: readonly number[]): string {
  return `#${channels
    .slice(0, 3)
    .map((value) => value.toString(16).padStart(2, '0'))
    .join('')}`
}

describe('the mark is the serious-warning pin’s glyph, bare', () => {
  it('draws the same triangle warningPin.ts registers, not a copy of it', () => {
    // One triangle on the map, two weights of it: a second set of rings here
    // would drift into a second triangle the moment either was touched.
    expect(ATC_NOTICE_GLYPH).toBe(WARNING_GLYPH)
  })

  it('puts nothing in the hole inside the band, off the exclamation', () => {
    // What a notice is drawn ON lives here - the centerline it is placed on,
    // the shelter pin it is about, the ford. `toBe(0)`, not "faint": a wash
    // would be the disc back. Sampled either side of the exclamation, where
    // the inner triangle is widest and nothing of the glyph is drawn.
    for (const [gx, gy] of [
      [0.33, 0.72],
      [0.67, 0.72],
      [0.3, 0.78],
      [0.7, 0.78],
    ]) {
      expect(at(gx, gy)[3], `alpha at ${gx},${gy}`).toBe(0)
    }
  })

  it('puts nothing outside its own drawn width', () => {
    // The image is EXACTLY the mark's footprint - 40px across at 2x - so there
    // is no margin to sample; the test is that the triangle does not fill its
    // own bounding box. The top corners first, which lie outside any triangle
    // standing on its base.
    for (const x of [0, IMAGE.width - 1]) {
      expect(IMAGE.data[x * 4 + 3]).toBe(0)
    }
    // Then the real bound: no pixel outside the drawn square carries ink. Half
    // a pixel's diagonal of slop, because a pixel whose CENTRE sits just past
    // the edge can still be clipped by it and pick up partial coverage.
    const limit = (ATC_UPDATE_POINT_DRAWN_WIDTH * POI_PIN_PIXEL_RATIO) / 2 + Math.SQRT1_2
    for (const { dx, dy } of inkedPixels()) {
      expect(Math.abs(dx)).toBeLessThanOrEqual(limit)
      expect(Math.abs(dy)).toBeLessThanOrEqual(limit)
    }
  })
})

describe('and what ink there is says the right things', () => {
  it('marks the coordinate itself, with the exclamation’s bar', () => {
    // The mark is anchored at its centre, and the bar of the exclamation runs
    // through it - so the coordinate a notice names carries opaque red rather
    // than falling in the hole.
    const [r, g, b, a] = at(0.5, 0.5)
    expect(a).toBe(255)
    expect(hex([r, g, b])).toBe(ATC_UPDATE_COLOR)
  })

  it('draws the band down both sides and along the base', () => {
    // Three samples in the middle of the band - left leg, right leg, base -
    // each opaque red. A ring dropped from the glyph, or the fill rule going
    // wrong, shows up here as a missing side rather than a subtly wrong shape.
    for (const [gx, gy] of [
      [0.245, 0.6],
      [0.755, 0.6],
      [0.5, 0.89],
    ]) {
      const [r, g, b, a] = at(gx, gy)
      expect(a, `alpha at ${gx},${gy}`).toBe(255)
      expect(hex([r, g, b]), `colour at ${gx},${gy}`).toBe(ATC_UPDATE_COLOR)
    }
  })

  it('carries the closure red and nothing else, so it is not a second severity', () => {
    // lib/atcUpdateStyle.ts refuses a second barrier colour at length, and a
    // rasteriser is a new place for one to appear by accident.
    //
    // NOT "every opaque pixel is one of two hexes", which is false: where red
    // meets its own casing a pixel can be fully covered by a MIX of the two,
    // and the supersampler averages them. So what is held is that every opaque
    // pixel lies ON THE LINE between the two colours - a third hue anywhere in
    // the image fails, and the anti-aliasing that is supposed to be there does
    // not. Read off the constants rather than typed out.
    const red = parseHex(ATC_UPDATE_COLOR)
    const dark = parseHex(ATC_UPDATE_CASING_COLOR)
    for (let i = 0; i < IMAGE.data.length; i += 4) {
      if (IMAGE.data[i + 3] !== 255) continue
      const channels = [IMAGE.data[i], IMAGE.data[i + 1], IMAGE.data[i + 2]]
      const along = (channels[0] - dark[0]) / (red[0] - dark[0])
      expect(along).toBeGreaterThanOrEqual(-0.02)
      expect(along).toBeLessThanOrEqual(1.02)
      for (const channel of [1, 2]) {
        const expected = dark[channel] + along * (red[channel] - dark[channel])
        expect(
          Math.abs(channels[channel] - expected),
          `channel ${channel} of ${hex(channels)}`,
        ).toBeLessThanOrEqual(1)
      }
    }
  })

  it('edges the red in dark, outside the band and inside the hole alike', () => {
    // The map's ground is white and the topo under a notice can be blank, so
    // the mark needs an edge exactly where it is most exposed - the argument
    // map/poiIcons.ts's `PIN_EDGE_COLOR` makes for every pin. The casing is the
    // glyph grown by a hairline, so it runs along BOTH edges of the band: just
    // outside the left leg, and just inside it, in the hole.
    const outside = at(0.196 - CASING / 2 / BOX, 0.6)
    const inside = at(0.294 + CASING / 2 / BOX, 0.6)
    for (const [label, [r, g, b, a]] of [
      ['outside', outside],
      ['inside', inside],
    ] as const) {
      expect(a, label).toBeGreaterThan(0)
      expect(hex([r, g, b]), label).toBe(ATC_UPDATE_CASING_COLOR)
    }
  })
})

describe('against the disc it replaces', () => {
  /** Opaque coverage in CSS px², summed off the alpha channel. */
  const ink = (() => {
    let total = 0
    for (let i = 3; i < IMAGE.data.length; i += 4) total += IMAGE.data[i] / 255
    return total / (POI_PIN_PIXEL_RATIO * POI_PIN_PIXEL_RATIO)
  })()
  const discInk = Math.PI * (ATC_UPDATE_POINT_DRAWN_WIDTH / 2) ** 2

  it('gives back more than a third of the ground the disc took', () => {
    // MEASURED off the rendered alpha rather than derived from the geometry:
    // the burst put 760.1 px² on the map against the disc's 1,256.6 px²
    // (60.5%, 2026-08-27); the triangle puts 688.7 px² (54.8%, measured
    // 2026-09-10 the same way). The bound is loose on purpose - the number is
    // evidence, and pinning it exactly would fail on a change to the glyph
    // that was fine.
    expect(ink).toBeLessThan(discInk * 0.7)
    expect(ink).toBeGreaterThan(discInk * 0.3)
  })

  it('still reaches as far as the disc did, which is what size was for', () => {
    // The reach is what makes an eye land here rather than on the shelter pin
    // beside it, and src/test/atcAlertProminence.test.ts holds it against both
    // pins. Giving ground back must not quietly shrink the mark instead. The
    // triangle's base is its widest span: 0.98 of the box plus the casing on
    // both ends.
    const widest = Math.max(...inkedPixels().map(({ dx }) => Math.abs(dx)))
    const drawnWidth = (widest * 2) / POI_PIN_PIXEL_RATIO
    expect(drawnWidth).toBeGreaterThan(ATC_UPDATE_POINT_DRAWN_WIDTH - 2)
    expect(drawnWidth).toBeLessThanOrEqual(
      ATC_UPDATE_POINT_DRAWN_WIDTH + 2 / POI_PIN_PIXEL_RATIO,
    )
  })
})

describe('the predicate the whole shape is made of', () => {
  it('grows by the same number of pixels on every edge', () => {
    // THE REASON IT IS AN EDGE DISTANCE and not a scaled outline: growing the
    // glyph by `grow` adds `grow` pixels outside every ring and `grow` pixels
    // into every hole, so the hairline has one width down the outside of the
    // band and up the inside of it. Walk in from the left along a row through
    // the legs: the grown shape starts `grow` pixels before the bare one.
    const grow = 3
    const y = 0.1 * BOX
    const leftEdge = (g: number) => {
      let x = -0.5 * BOX
      while (x < 0 && !insideNoticeMark(BOX, x, y, g)) x += 0.01
      return x
    }
    expect(leftEdge(0) - leftEdge(grow)).toBeCloseTo(grow, 0)
  })

  it('holds the hole open under growth too', () => {
    // The casing pass runs the same predicate with everything dilated, so a
    // mistake here would fill the hole with dark rather than red - the failure
    // would look different and be exactly as bad.
    expect(insideNoticeMark(BOX, (0.33 - 0.5) * BOX, (0.72 - 0.5) * BOX, CASING)).toBe(
      false,
    )
    expect(insideNoticeMark(BOX, (0.67 - 0.5) * BOX, (0.72 - 0.5) * BOX, CASING)).toBe(
      false,
    )
  })
})
