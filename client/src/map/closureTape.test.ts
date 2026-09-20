import { describe, it, expect } from 'vitest'
import {
  attachClosureTape,
  buildClosureTape,
  tapeGrounds,
  type TapeImage,
} from './closureTape'
import { MAP_BACKDROP, closureTapeGround, mapBackdrop } from './style'
import {
  CLOSURE_CASING_COLOR,
  CLOSURE_COLOR,
  CLOSURE_LAYER_ID,
  CLOSURE_TAPE_CADENCE,
  CLOSURE_TAPE_OVERVIEW_CADENCE,
  CLOSURE_TAPE_OVERVIEW_EDGE,
  CLOSURE_TAPE_PIXEL_RATIO,
  CLOSURE_TAPE_WIDTH,
  closureTapeImageId,
  tapeRedFraction,
} from '../lib/closureStyle'
import { ATC_UPDATE_TAPE_CADENCE, atcTapeImageId } from '../lib/atcUpdateStyle'

// What a hiker is owed by this image, checked in its bytes.
//
// The tape replaced a band whose defect was invisible in every test and
// obvious in a screenshot: a solid casing under a dashed line, filling every
// gap with the darkest ink on the sheet. Nothing here would have caught that,
// because nothing here existed - so these tests are written against the
// properties that failure had, not only against the ones the new drawing has.
//
// SINCE #1575 THE GAPS HOLD THE SHEET'S PAPER rather than nothing (option E,
// the maintainer's choice of 2026-09-17 - lib/closureStyle.ts's header). So
// "the ground shows through" became "the ground IS the paper, in the map's
// own colour": the tests below hold that it is paper and not casing, that it
// is the right paper for the sheet, and that the casing still edges nothing
// but a stripe.

/** The field day sheet's paper and night_hike's ink - the two anchor
 *  backdrops map/style.ts pins. */
const PAPER = MAP_BACKDROP.light
const INK = MAP_BACKDROP.dark

const tape = buildClosureTape(PAPER)

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

/** Pixels painted exactly `hex`, opaque. */
function paintedIn(image: ReturnType<typeof buildClosureTape>, hex: string) {
  const want = parseHex(hex)
  return allPixels(image).filter(
    (p) => p.a === 255 && p.r === want.r && p.g === want.g && p.b === want.b,
  )
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

describe('the ground between the stripes is the sheet’s paper (#1575, option E)', () => {
  it('is the paper it was built on, opaque, and still a real share of the tile', () => {
    // The same count the transparent tape used to make of its clear pixels,
    // asked of the paper instead: the ground between the stripes is the
    // sheet's own paper rather than nothing, which is what stops a red line
    // showing through as more of the same red - the reason the maintainer
    // chose this treatment over the tape as it was.
    //
    // THE BAR MOVED FROM 0.4 TO 0.15 ON 2026-09-20 (#1598), and the drop is
    // the cost of the maintainer's other instruction. Exactly-paper pixels
    // were 47.4% of the tile at the 3.5/15 cadence (measured 2026-09-17);
    // at 5/12 they are 18.4% (measured 2026-09-20), because red went from
    // 28% of the tape's length to 51% and each stripe still carries its two
    // edges. What survives is the claim this test is actually for - that
    // there IS paper between the stripes, so the mark is textured rather
    // than a flat slab - and 0.15 is a floor under that rather than a
    // measurement of anything.
    expect(paintedIn(tape, PAPER).length / (tape.width * tape.height)).toBeGreaterThan(
      0.15,
    )
  })

  it('shows the same share of paper at the overview cadence, which is the point of halving the edge', () => {
    // "The same tape, smaller" as a pixel count rather than an intention.
    // An unhalved edge at a halved pitch merges the stripes and leaves no
    // paper at all - lib/closureStyle.ts's CLOSURE_TAPE_OVERVIEW_EDGE has
    // the arithmetic, and this is the same claim read off the image the map
    // is actually handed.
    const overview = buildClosureTape(
      PAPER,
      CLOSURE_TAPE_OVERVIEW_CADENCE,
      CLOSURE_TAPE_PIXEL_RATIO,
      CLOSURE_TAPE_OVERVIEW_EDGE,
    )
    const share = (image: TapeImage) =>
      paintedIn(image, PAPER).length / (image.width * image.height)

    // Both above the floor, and neither near zero, which is the claim.
    // They are NOT equal and cannot be: `paintedIn` counts pixels that are
    // EXACTLY the paper, and the one-pixel ramp each stripe fades through
    // costs a smaller tile proportionally more of its area. Measured
    // 2026-09-20: 18.4% on the near tape's 24 by 34 tile, 13.2% on the
    // overview's 12 by 34. The ink fractions the two share exactly are held
    // in closureStyle.test.ts, off the cadences rather than off the pixels.
    expect(share(overview)).toBeGreaterThan(0.1)
    expect(share(tape)).toBeGreaterThan(share(overview))
  })

  it('has no transparent pixel anywhere, which is the whole change', () => {
    expect(allPixels(tape).every((p) => p.a === 255)).toBe(true)
  })

  it('is the day paper on a dark sheet, and the sheet’s own ink only under red light (2026-09-18)', () => {
    // Option E was chosen on the day sheet; built as "the sheet's paper" it
    // put red stripes on near-black ink over a near-black map - the
    // maintainer's "it's really hard to tell it's a closure when the
    // background is black". Red light keeps its ink: a white band would be
    // the brightest thing on a screen built to spare night vision, and
    // closureTapeGround's docstring carries the open question.
    expect(closureTapeGround({ theme: 'dark' })).toBe(PAPER)
    expect(closureTapeGround({ mapStyle: 'night_hike' })).toBe(PAPER)
    expect(closureTapeGround({ theme: 'light' })).toBe(PAPER)
    expect(closureTapeGround({ mapStyle: 'parchment' })).toBe(
      mapBackdrop({ mapStyle: 'parchment' }),
    )
    const redLight = { mapStyle: 'night_hike', redLight: true } as const
    expect(closureTapeGround(redLight)).toBe(mapBackdrop(redLight))
    expect(closureTapeGround(redLight)).not.toBe(PAPER)

    // And the image built on that paper is that paper between the stripes:
    // no night ink anywhere in the tape a dark sheet draws. The share bar is
    // the one the test above carries and moved with it at #1598.
    const night = buildClosureTape(closureTapeGround({ theme: 'dark' }))
    expect(paintedIn(night, PAPER).length / (night.width * night.height)).toBeGreaterThan(
      0.15,
    )
    expect(paintedIn(night, INK)).toHaveLength(0)
  })

  it('never paints casing where there is no stripe to edge', () => {
    // The defect, stated as a property: dark pixels are permitted only beside
    // red ones. Scanned per row, because a stripe crosses every row exactly
    // once and "beside" is a distance along that row. On the paper tape, so a
    // ground pixel can never be mistaken for casing.
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
    expect(paintedIn(tape, CLOSURE_COLOR).length).toBeGreaterThan(0)
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
  const atc = buildClosureTape(PAPER, ATC_UPDATE_TAPE_CADENCE)

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

  it('lies on the same paper, and on more of it than the closure’s tape does', () => {
    // The ATC's tape doubles the cadence and keeps CLOSURE_STRIPE_EDGE, so
    // its edges are half as heavy relative to its stripes and it shows more
    // paper than the closure's does. That is the "softer claim" this module
    // is allowed to make and the closure's is not - and it is why
    // lib/atcUpdateStyle.ts leaves its edge alone where the overview tape
    // halves one.
    const share = (image: TapeImage) =>
      paintedIn(image, PAPER).length / (image.width * image.height)

    expect(share(atc)).toBeGreaterThan(0.3)
    expect(share(atc)).toBeGreaterThan(share(tape))
  })
})

describe('one tape per paper (#1575)', () => {
  it('lists every paper the sheet table can produce, once each, as a hex', () => {
    // Five today: four day sheets (night_hike has none) and red light's ink
    // - every other dark sheet takes the day paper since 2026-09-18 - the
    // figure the module comment carries, held here so a sheet added to
    // liveTopo.ts's table moves it in the open.
    const grounds = tapeGrounds()

    expect(grounds).toHaveLength(5)
    expect(new Set(grounds).size).toBe(grounds.length)
    for (const ground of grounds) expect(ground).toMatch(/^#[0-9a-f]{6}$/i)
  })

  it('includes the day paper and red light’s ink, and night ink no longer', () => {
    expect(tapeGrounds()).toContain(MAP_BACKDROP.light)
    // Night ink was a tape's paper until 2026-09-18; a tape drawn on it is
    // exactly the band the maintainer could not read as a closure.
    expect(tapeGrounds()).not.toContain(MAP_BACKDROP.dark)
    expect(tapeGrounds()).toContain(
      mapBackdrop({ mapStyle: 'night_hike', redLight: true }),
    )
  })

  it('names each paper’s tape apart from every other, from the ATC’s, and from its own overview', () => {
    expect(closureTapeImageId(PAPER)).not.toBe(closureTapeImageId(INK))
    expect(closureTapeImageId(PAPER)).not.toBe(atcTapeImageId(PAPER))
    // Case does not make a second image: the same paper is the same id.
    expect(closureTapeImageId('#FFFFFF')).toBe(closureTapeImageId('#ffffff'))
    // And the two cadences are two images on the same paper (#1598), which
    // is what lets one layer step between them.
    expect(closureTapeImageId(PAPER, 'overview')).not.toBe(
      closureTapeImageId(PAPER, 'near'),
    )
    expect(atcTapeImageId(PAPER, 'overview')).not.toBe(
      closureTapeImageId(PAPER, 'overview'),
    )
    // Absent means the navigation tape, which is what this id has always
    // meant - every caller that names one without a range still gets it.
    expect(closureTapeImageId(PAPER)).toBe(closureTapeImageId(PAPER, 'near'))
  })

  it('registers all four tapes on every paper before any band asks for one', async () => {
    // EVERY CADENCE, not the current one - the reason is the reason every
    // PAPER is registered, one zoom further out. A `line-pattern` naming an
    // image the map has not been given draws NOTHING, and since #1598 the
    // band steps between two images while a hiker is zooming, so a lazily
    // registered overview tape would open a window where a closure is
    // invisible at exactly the camera it is hardest to see at.
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const map = new MockMap({})
    map.layerIds = [CLOSURE_LAYER_ID]

    attachClosureTape(map as never)

    const expected = tapeGrounds().flatMap((ground) =>
      (['near', 'overview'] as const).flatMap((range) => [
        closureTapeImageId(ground, range),
        atcTapeImageId(ground, range),
      ]),
    )
    expect(expected).toHaveLength(20)
    for (const id of expected) expect(map.hasImage(id), id).toBe(true)
    expect(map.images.size).toBe(expected.length)
  })

  it('draws each overview tape at its own cadence rather than the near one', () => {
    // The failure this catches is a copy-paste in the registration table:
    // four ids, two images. An image is its cadence, so the widths are what
    // tell them apart.
    const near = buildClosureTape(PAPER, CLOSURE_TAPE_CADENCE)
    const overview = buildClosureTape(
      PAPER,
      CLOSURE_TAPE_OVERVIEW_CADENCE,
      CLOSURE_TAPE_PIXEL_RATIO,
      CLOSURE_TAPE_OVERVIEW_EDGE,
    )

    expect(overview.width).toBe(near.width / 2)
    expect(overview.height).toBe(near.height)
  })
})
