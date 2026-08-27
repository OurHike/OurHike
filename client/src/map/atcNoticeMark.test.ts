import { describe, it, expect } from 'vitest'
import { buildAtcNoticeIcon, insideBurst } from './atcNoticeMark'
import { parseHex, POI_PIN_PIXEL_RATIO } from './poiIcons'
import {
  ATC_NOTICE_BURST,
  ATC_NOTICE_CASING_WIDTH,
  ATC_NOTICE_FILL_RADIUS,
  ATC_UPDATE_CASING_COLOR,
  ATC_UPDATE_COLOR,
  ATC_UPDATE_POINT_DRAWN_WIDTH,
} from '../lib/atcUpdateStyle'

// The ATC's point notice, measured on its own pixels (#1071).
//
// THIS FILE EXISTS BECAUSE THE GEOMETRY WAS RIGHT AND THE PICTURE WAS WRONG.
// The first version of this mark had eight spokes, an open centre and clear
// ground between the spokes by every number in lib/atcUpdateStyle.ts - and
// rendered as a black disc with red spokes on it, because it carried the band's
// 2px casing and a casing runs down BOTH sides of every spoke. Nothing in the
// spec could see that; only the alpha channel could.
//
// So what is asserted here is TRANSPARENCY, sampled off the rendered image: the
// ring between the hub and the spokes carries no ink at all, the gaps between
// the spokes carry none, and the total is a measured fraction of what the disc
// this replaced put on the map. Those are the properties a hiker actually gets,
// and they are the ones that were false while every constant was true.

const IMAGE = buildAtcNoticeIcon()
const CENTER = IMAGE.width / 2
/** Everything below works in the image's own pixels, which are `sizePx` × 2. */
const FILL_RADIUS = ATC_NOTICE_FILL_RADIUS * POI_PIN_PIXEL_RATIO
const CASING = ATC_NOTICE_CASING_WIDTH * POI_PIN_PIXEL_RATIO
const HUB = ATC_NOTICE_BURST.hubRadius * FILL_RADIUS
const INNER = ATC_NOTICE_BURST.innerRadius * FILL_RADIUS
const PITCH = (Math.PI * 2) / ATC_NOTICE_BURST.spokes

/** The pixel at a polar offset from the centre, as `[r, g, b, a]`.
 *
 *  Bounds-checked rather than trusting the caller, because `(y * width + x)`
 *  on an x past the last column silently reads the START of the next row - so
 *  a case sampling just outside the mark would read a pixel from inside it and
 *  pass or fail for a reason that has nothing to do with the mark. That
 *  happened while this file was being written. */
function sample(radius: number, bearing: number): [number, number, number, number] {
  const x = Math.round(CENTER + radius * Math.cos(bearing) - 0.5)
  const y = Math.round(CENTER + radius * Math.sin(bearing) - 0.5)
  if (x < 0 || y < 0 || x >= IMAGE.width || y >= IMAGE.height) {
    throw new Error(`sample(${radius}, ${bearing}) is outside the ${IMAGE.width}px image`)
  }
  const at = (y * IMAGE.width + x) * 4
  return [IMAGE.data[at], IMAGE.data[at + 1], IMAGE.data[at + 2], IMAGE.data[at + 3]]
}

/** Every pixel that carries any ink at all, as `{ x, y, radius, alpha }`. */
function inkedPixels(): Array<{ radius: number; alpha: number }> {
  const found: Array<{ radius: number; alpha: number }> = []
  for (let index = 0; index < IMAGE.data.length; index += 4) {
    if (IMAGE.data[index + 3] === 0) continue
    const pixel = index / 4
    const dx = (pixel % IMAGE.width) + 0.5 - CENTER
    const dy = Math.floor(pixel / IMAGE.width) + 0.5 - CENTER
    found.push({ radius: Math.hypot(dx, dy), alpha: IMAGE.data[index + 3] })
  }
  return found
}

/** The bearing of spoke `index`, so a case can aim down one or between two. */
function spokeBearing(index: number): number {
  return ATC_NOTICE_BURST.phase + PITCH * index
}

function hex(channels: readonly number[]): string {
  return `#${channels
    .slice(0, 3)
    .map((value) => value.toString(16).padStart(2, '0'))
    .join('')}`
}

describe('the mark is mostly hole, which is the entire point', () => {
  it('puts nothing at all in the ring between the hub and the spokes', () => {
    // What a notice is drawn ON lives here - the centerline it is placed on,
    // the shelter pin it is about, the ford. Under the disc this replaced, all
    // of it was gone. `toBe(0)`, not "faint": a wash would be the disc back.
    const ring = (HUB + CASING + (INNER - CASING)) / 2

    for (let step = 0; step < 64; step += 1) {
      const bearing = (step / 64) * Math.PI * 2
      expect(sample(ring, bearing)[3], `alpha at bearing ${bearing}`).toBe(0)
    }
  })

  it('puts nothing between one spoke and the next', () => {
    // Sampled down the middle of every gap, at three radii along it, because
    // the spokes taper - a gap that is open at the rim can still be closed
    // near the hub, which is exactly what the first render did.
    for (let index = 0; index < ATC_NOTICE_BURST.spokes; index += 1) {
      const between = spokeBearing(index) + PITCH / 2
      for (const along of [0.25, 0.5, 0.9]) {
        const radius = INNER + (FILL_RADIUS - INNER) * along
        expect(sample(radius, between)[3], `alpha in gap ${index} at ${along}`).toBe(0)
      }
    }
  })

  it('puts nothing outside its own drawn width', () => {
    // The image is EXACTLY the mark's footprint - 40px across at 2x - so there
    // is no margin to sample; the test is that the burst does not fill its own
    // bounding box. Corners first, because a rasteriser that had quietly gone
    // back to drawing a disc would still pass every case above.
    for (const y of [0, IMAGE.height - 1]) {
      for (const x of [0, IMAGE.width - 1]) {
        expect(IMAGE.data[(y * IMAGE.width + x) * 4 + 3]).toBe(0)
      }
    }

    // Then the real bound: no pixel outside the drawn radius carries ink. Half
    // a pixel's diagonal of slop, because a pixel whose CENTRE sits just past
    // the edge can still be clipped by it and pick up partial coverage.
    const limit = FILL_RADIUS + CASING + Math.SQRT1_2
    for (const { radius } of inkedPixels()) {
      expect(radius).toBeLessThanOrEqual(limit)
    }
  })
})

describe('and what ink there is says the right things', () => {
  it('marks the coordinate itself, so it is not merely a ring', () => {
    // A ring reads as drawn AROUND something. A point notice names one mile
    // marker, and the dot is what says which.
    const [r, g, b, a] = sample(0, 0)

    expect(a).toBe(255)
    expect(hex([r, g, b])).toBe(ATC_UPDATE_COLOR)
  })

  it('draws every spoke, not merely some', () => {
    // Eight, each carrying opaque red down its own axis. A phase error or an
    // off-by-one in the nearest-spoke arithmetic shows up here as a missing
    // limb rather than as a subtly wrong shape.
    for (let index = 0; index < ATC_NOTICE_BURST.spokes; index += 1) {
      const bearing = spokeBearing(index)
      const radius = INNER + (FILL_RADIUS - INNER) * 0.6
      const [r, g, b, a] = sample(radius, bearing)

      expect(a, `alpha on spoke ${index}`).toBe(255)
      expect(hex([r, g, b]), `colour on spoke ${index}`).toBe(ATC_UPDATE_COLOR)
    }
  })

  it('carries the closure red and nothing else, so it is not a second severity', () => {
    // lib/atcUpdateStyle.ts refuses a second barrier colour at length, and a
    // rasteriser is a new place for one to appear by accident.
    //
    // NOT "every opaque pixel is one of two hexes", which is what this case
    // asserted first and is false: where red meets its own casing a pixel can
    // be fully covered by a MIX of the two, and the supersampler averages them.
    // Nine such blends showed up. So what is held is that every opaque pixel
    // lies ON THE LINE between the two colours - a third hue anywhere in the
    // image fails, and the anti-aliasing that is supposed to be there does not.
    // Read off the constants rather than typed out, so a colour change moves
    // this case with it instead of failing it.
    const red = parseHex(ATC_UPDATE_COLOR)
    const dark = parseHex(ATC_UPDATE_CASING_COLOR)

    for (let at = 0; at < IMAGE.data.length; at += 4) {
      if (IMAGE.data[at + 3] !== 255) continue

      const channels = [IMAGE.data[at], IMAGE.data[at + 1], IMAGE.data[at + 2]]
      // Read the blend off the red channel, which has the widest span of the
      // three and therefore the least rounding error, then check the other two
      // agree with it.
      const along = (channels[0] - dark[0]) / (red[0] - dark[0])
      expect(along).toBeGreaterThanOrEqual(-0.02)
      expect(along).toBeLessThanOrEqual(1.02)

      for (const channel of [1, 2]) {
        const expected = dark[channel] + along * (red[channel] - dark[channel])
        // One unit of slack, and it is spent on two roundings rather than on
        // slop: the supersampler divides a sum of integers by the number of
        // samples that hit, and Uint8ClampedArray rounds what comes out.
        expect(
          Math.abs(channels[channel] - expected),
          `channel ${channel} of ${hex(channels)}`,
        ).toBeLessThanOrEqual(1)
      }
    }
  })

  it('edges the red in dark, so it holds on pale paper', () => {
    // The map's ground is white (`MAP_BACKGROUND_COLOR`) and the topo under a
    // notice can be blank. Without the hairline the mark has no edge at all
    // exactly where it is most exposed - which is the same argument
    // map/poiIcons.ts's `PIN_EDGE_COLOR` makes for every pin.
    const [r, g, b, a] = sample(FILL_RADIUS + CASING / 2, spokeBearing(0))

    expect(a).toBeGreaterThan(0)
    expect(hex([r, g, b])).toBe(ATC_UPDATE_CASING_COLOR)
  })
})

describe('against the disc it replaces', () => {
  /** Opaque coverage in CSS px², summed off the alpha channel. */
  const ink = (() => {
    let total = 0
    for (let at = 3; at < IMAGE.data.length; at += 4) total += IMAGE.data[at] / 255
    return total / (POI_PIN_PIXEL_RATIO * POI_PIN_PIXEL_RATIO)
  })()

  const discInk = Math.PI * (ATC_UPDATE_POINT_DRAWN_WIDTH / 2) ** 2

  it('gives back more than a third of the ground the disc took', () => {
    // MEASURED off the rendered alpha rather than derived from the geometry:
    // 760.1 px² against the disc's 1,256.6 px², which is 60.5%. The bound is loose
    // on purpose - the number is evidence, and pinning it exactly would fail
    // on a change to the taper that was fine.
    expect(ink).toBeLessThan(discInk * 0.7)
    expect(ink).toBeGreaterThan(discInk * 0.4)
  })

  it('still reaches as far as the disc did, which is what size was for', () => {
    // The reach is what makes an eye land here rather than on the shelter pin
    // beside it, and src/test/atcAlertProminence.test.ts holds it against both
    // pins. Giving ground back must not quietly shrink the mark instead.
    const furthest = Math.max(...inkedPixels().map(({ radius }) => radius))
    const drawnWidth = (furthest * 2) / POI_PIN_PIXEL_RATIO

    expect(drawnWidth).toBeGreaterThan(ATC_UPDATE_POINT_DRAWN_WIDTH - 1)
    // Measured to the CENTRE of the outermost inked pixel, which for a partly
    // covered one sits outside the shape - so the ceiling carries one source
    // pixel of anti-aliasing rather than pretending the edge is hard.
    expect(drawnWidth).toBeLessThanOrEqual(
      ATC_UPDATE_POINT_DRAWN_WIDTH + 2 / POI_PIN_PIXEL_RATIO,
    )
  })
})

describe('the predicate the whole shape is made of', () => {
  it('grows by the same number of pixels at every radius', () => {
    // THE REASON THIS IS POLAR. `casing / r` radians is `casing` pixels of
    // outline whether it is asked for near the hub or out at the rim, so the
    // hairline has one width. A scaled-up outline - the obvious polygon
    // shortcut - would be thin at the hub and fat at the tip, and this is the
    // case that would catch that if anyone tried it.
    const grow = 3

    for (const radius of [INNER + 2, (INNER + FILL_RADIUS) / 2, FILL_RADIUS - 2]) {
      const bearing = spokeBearing(0)
      let bare = 0
      let grown = 0
      // Walk outward in angle from the spoke's axis until each version stops
      // claiming the point, and convert the difference back into pixels.
      for (let off = 0; off < PITCH / 2; off += 0.0005) {
        const dx = radius * Math.cos(bearing + off)
        const dy = radius * Math.sin(bearing + off)
        if (insideBurst(ATC_NOTICE_BURST, FILL_RADIUS, dx, dy, 0)) bare = off
        if (insideBurst(ATC_NOTICE_BURST, FILL_RADIUS, dx, dy, grow)) grown = off
      }

      expect((grown - bare) * radius).toBeCloseTo(grow, 1)
    }
  })

  it('holds the hole open under growth too', () => {
    // The casing pass runs the same predicate with everything dilated, so a
    // mistake here would fill the open centre with dark rather than red - the
    // failure would look different and be exactly as bad.
    const ring = (HUB + CASING + (INNER - CASING)) / 2

    expect(insideBurst(ATC_NOTICE_BURST, FILL_RADIUS, ring, 0, CASING)).toBe(false)
    expect(insideBurst(ATC_NOTICE_BURST, FILL_RADIUS, 0, ring, CASING)).toBe(false)
  })
})
