import { describe, it, expect } from 'vitest'
import { buildClosureTape } from './closureTape'
import {
  CLOSURE_CASING_COLOR,
  CLOSURE_COLOR,
  CLOSURE_TAPE_CADENCE,
  CLOSURE_TAPE_PIXEL_RATIO,
  CLOSURE_TAPE_WIDTH,
  tapeRedFraction,
} from '../lib/closureStyle'
import { ATC_UPDATE_TAPE_CADENCE } from '../lib/atcUpdateStyle'

// What a hiker is owed by this image, checked in its bytes.
//
// The tape replaced a band whose defect was invisible in every test and
// obvious in a screenshot: a solid casing under a dashed line, filling every
// gap with the darkest ink on the sheet. Nothing here would have caught that,
// because nothing here existed - so these tests are written against the
// properties that failure had, not only against the ones the new drawing has.

const tape = buildClosureTape()

/** The four channels at one pixel. */
function pixel(image: ReturnType<typeof buildClosureTape>, x: number, y: number) {
  const at = (y * image.width + x) * 4
  return {
    r: image.data[at],
    g: image.data[at + 1],
    b: image.data[at + 2],
    a: image.data[at + 3],
  }
}

function parseHex(hex: string) {
  const value = Number.parseInt(hex.slice(1), 16)
  return { r: (value >> 16) & 0xff, g: (value >> 8) & 0xff, b: value & 0xff }
}

/** Every pixel, as a flat list - these are small images and a scan is clearer
 *  than an index. */
function allPixels(image: ReturnType<typeof buildClosureTape>) {
  const out = []
  for (let y = 0; y < image.height; y += 1) {
    for (let x = 0; x < image.width; x += 1) out.push(pixel(image, x, y))
  }
  return out
}

describe('the image MapLibre is handed', () => {
  it('is one pitch wide and one tape tall, at the ratio it declares', () => {
    // MapLibre scales a line-pattern so the image HEIGHT becomes the line
    // width, then repeats along the line - so the height is what makes the
    // tape 14px and the width is what makes it tile at the right cadence.
    expect(tape.height).toBe(CLOSURE_TAPE_WIDTH * CLOSURE_TAPE_PIXEL_RATIO)
    expect(tape.width).toBe(CLOSURE_TAPE_CADENCE.pitch * CLOSURE_TAPE_PIXEL_RATIO)
  })

  it('fills its byte array completely', () => {
    expect(tape.data).toHaveLength(tape.width * tape.height * 4)
  })
})

describe('what is between the stripes', () => {
  it('lets the ground through over most of its area', () => {
    // THE TEST THE OLD BAND WOULD HAVE FAILED, and the reason this file
    // exists. Its casing was opaque along its whole length - 100%, no
    // exceptions - so a hiker could not see the trail through its own closure.
    //
    // Counted at half alpha rather than at zero because that is the question
    // being asked: a pixel the ground shows through is one the tape does not
    // own, and the stripes' anti-aliased edges are a couple of points either
    // way. The fully-clear count is held separately below.
    const open = allPixels(tape).filter((p) => (p.a ?? 0) < 128)

    expect(open.length / (tape.width * tape.height)).toBeGreaterThan(0.5)
  })

  it('is properly empty between the stripes, not merely faint', () => {
    // A design that hit the number above with soft edges everywhere would pass
    // it and look like a wash. Most of the open area has to be nothing at all.
    const clear = allPixels(tape).filter((p) => p.a === 0)

    expect(clear.length / (tape.width * tape.height)).toBeGreaterThan(0.4)
  })

  it('never paints casing where there is no stripe to edge', () => {
    // The defect, stated as a property: dark pixels are permitted only beside
    // red ones. Scanned per row, because a stripe crosses every row exactly
    // once and "beside" is a distance along that row.
    const dark = parseHex(CLOSURE_CASING_COLOR)
    const near = (a: number, b: number) => Math.abs(a - b) <= 12

    for (let y = 0; y < tape.height; y += 1) {
      const row = Array.from({ length: tape.width }, (_, x) => pixel(tape, x, y))
      const darkAt = row
        .map((p, x) => ({ p, x }))
        .filter(({ p }) => p.a > 200 && near(p.r, dark.r) && near(p.g, dark.g))

      for (const { x } of darkAt) {
        // Within the edge's own width of a red pixel, wrapping at the tile
        // seam - the pattern repeats, so the stripe past the right edge is the
        // one at the left.
        const reach = Math.ceil(CLOSURE_TAPE_CADENCE.stripe * CLOSURE_TAPE_PIXEL_RATIO)
        const window = Array.from(
          { length: reach * 2 + 1 },
          (_, i) => row[(x + i - reach + tape.width) % tape.width],
        )

        expect(window.some((p) => p !== undefined && p.a > 0 && p.r > p.b + 40)).toBe(
          true,
        )
      }
    }
  })
})

describe('the stripes themselves', () => {
  it('paints them in the closure red', () => {
    const red = parseHex(CLOSURE_COLOR)
    const opaque = allPixels(tape).filter((p) => p.a === 255)
    const matching = opaque.filter(
      (p) =>
        Math.abs((p.r ?? 0) - red.r) <= 2 &&
        Math.abs((p.g ?? 0) - red.g) <= 2 &&
        Math.abs((p.b ?? 0) - red.b) <= 2,
    )

    expect(matching.length).toBeGreaterThan(0)
  })

  it('covers about the fraction of the tape the spec computes', () => {
    // The image checked against lib/closureStyle.ts's arithmetic rather than
    // against a number typed twice. Measured on the tape's CENTRE ROW, which
    // is the one place the along-line fraction is exactly the spec's figure -
    // a stripe's ends are clipped by the tape's edges, so a whole-image count
    // would run lower for a reason that is geometry rather than a defect.
    const middle = Math.floor(tape.height / 2)
    const row = Array.from({ length: tape.width }, (_, x) => pixel(tape, x, middle))
    const red = row.filter((p) => (p.a ?? 0) > 128 && (p.r ?? 0) > (p.b ?? 0) + 40)

    expect(red.length / tape.width).toBeCloseTo(tapeRedFraction(CLOSURE_TAPE_CADENCE), 1)
  })

  it('is built at a width that tiles, rather than one that rounds', () => {
    // Where a seam would come from. The image is exactly one pitch wide, so
    // translating it by its own width moves the stripes by exactly one period
    // and the repeat is seamless BY CONSTRUCTION - but only while the pitch
    // lands on a whole number of image pixels. If it does not, the width
    // rounds, the two stop being equal, and the tape stutters every few
    // stripes. lib/closureStyle.test.ts holds the pitch itself; this holds
    // that the rasteriser did not round it away.
    expect(tape.width).toBe(CLOSURE_TAPE_CADENCE.pitch * CLOSURE_TAPE_PIXEL_RATIO)
  })
})

describe('the ATC tape is the same tape, slower', () => {
  const atc = buildClosureTape(ATC_UPDATE_TAPE_CADENCE)

  it('is drawn at the same width', () => {
    // lib/atcUpdateStyle.ts refuses to say one barrier is softer than the
    // other, and width is the loudest way it could accidentally say it.
    expect(atc.height).toBe(tape.height)
  })

  it('puts down the same fraction of red', () => {
    // The equality that makes "the same tape at a slower cadence" true rather
    // than intended: scaling only the pitch would thin the ATC's band to a
    // third of the closure's red, which reads as a softer claim.
    expect(tapeRedFraction(ATC_UPDATE_TAPE_CADENCE)).toBeCloseTo(
      tapeRedFraction(CLOSURE_TAPE_CADENCE),
      6,
    )
  })

  it('is a genuinely different image, not the same one twice', () => {
    // Two feeds must be tellable apart on a close look (features/
    // SOURCE_REGISTRY.md's show-one-disclose-the-other rule is answered by the
    // sheet, but the line may not be identical either).
    expect(atc.width).not.toBe(tape.width)
  })
})
