import { describe, it, expect } from 'vitest'
import { parseHex, POI_PIN_SIZE, RIM_DASHES } from './poiIcons'
import {
  buildPositionMark,
  POSITION_INK_FAMILIES,
  POSITION_INKS,
  POSITION_MARK_PIXEL_RATIO,
  POSITION_MARK_SIZE,
  positionMarkId,
  RING_RADIUS,
  type PositionInk,
} from './positionMark'

// The mark for where the hiker stands (#1581): a hollow ring, a centre dot,
// four ticks, in the sheet's ink and no hue of its own. The rules below come
// from features/mockups/hiker-mark.html's brief, and the two that matter most
// are that it is HOLLOW - every place on this map is a filled disc, so the
// one thing that is not a place is the one thing the ground shows through -
// and that it is smaller than a pin, so standing at a shelter leaves the
// shelter readable.

/** The pixel under a point (x, y) CSS px from the centre, as [r, g, b, a]. */
function pixelAt(ink: PositionInk, stale: boolean, x: number, y: number) {
  const image = buildPositionMark(ink, stale)
  const centre = image.width / 2
  const px = Math.floor(centre + x * POSITION_MARK_PIXEL_RATIO)
  const py = Math.floor(centre + y * POSITION_MARK_PIXEL_RATIO)
  const at = (py * image.width + px) * 4
  return Array.from(image.data.slice(at, at + 4))
}

const rgb = (pixel: number[]) => pixel.slice(0, 3)
const alpha = (pixel: number[]) => pixel[3]

describe('the mark', () => {
  it('is a 36 px box drawn at 2x, two pixels under a waypoint pin', () => {
    const image = buildPositionMark('day', false)

    expect(image.width).toBe(POSITION_MARK_SIZE * POSITION_MARK_PIXEL_RATIO)
    expect(image.height).toBe(image.width)
    expect(POSITION_MARK_SIZE).toBeLessThan(POI_PIN_SIZE)
  })

  it('is hollow: the ground shows through between the dot and the ring', () => {
    // Six px out is past the dot's casing (3.75) and short of the ring's
    // (8.25): nothing is drawn there, in any direction.
    for (const [x, y] of [
      [0, -6],
      [6, 0],
      [4.2, 4.2],
    ]) {
      expect(alpha(pixelAt('day', false, x, y))).toBe(0)
    }
  })

  it('inks the centre dot and the ring solid', () => {
    const ink = parseHex(POSITION_INKS.day.ink)

    expect(pixelAt('day', false, 0, 0)).toEqual([...ink, 255])
    expect(pixelAt('day', false, 0, -RING_RADIUS)).toEqual([...ink, 255])
    expect(pixelAt('day', false, RING_RADIUS, 0)).toEqual([...ink, 255])
  })

  it('edges the ring with paper on both sides, off the axes where no tick is', () => {
    const paper = parseHex(POSITION_INKS.day.paper)
    // On the 45-degree line, 13 px out sits in the ring's outer casing and
    // clear of every tick; 9 px out sits in its inner casing.
    const outer = 13 / Math.SQRT2
    const inner = 9 / Math.SQRT2

    expect(rgb(pixelAt('day', false, outer, -outer))).toEqual([...paper])
    expect(rgb(pixelAt('day', false, inner, inner))).toEqual([...paper])
  })

  it('reaches out along all four axes with a tick', () => {
    const ink = parseHex(POSITION_INKS.day.ink)

    for (const [x, y] of [
      [0, -15],
      [0, 15],
      [-15, 0],
      [15, 0],
    ]) {
      expect(rgb(pixelAt('day', false, x, y))).toEqual([...ink])
    }
  })

  it('names its images by ink family and by whether the fix is stale', () => {
    expect(positionMarkId('day', false)).toBe('hiker-mark-day')
    expect(positionMarkId('night', true)).toBe('hiker-mark-night-stale')
    expect(positionMarkId('red', false)).toBe('hiker-mark-red')
  })

  it.each(POSITION_INK_FAMILIES)(
    'draws the %s family in its own ink and paper',
    (family) => {
      const ink = parseHex(POSITION_INKS[family].ink)
      const paper = parseHex(POSITION_INKS[family].paper)
      const diagonal = 13 / Math.SQRT2

      expect(rgb(pixelAt(family, false, 0, 0))).toEqual([...ink])
      expect(rgb(pixelAt(family, false, diagonal, diagonal))).toEqual([...paper])
    },
  )
})

describe('the stale mark', () => {
  // The ring breaks into the pins' own eight dashes - the same rimHasInk the
  // unverified pins use, so a hiker who has learned what a broken rim means
  // on a pin is not taught a second rhythm here. The gaps are OPEN: no ink
  // and no paper, so the ground shows through them too.
  const sectors = RIM_DASHES * 2

  it('keeps ink in every other sector of the ring, and nothing in the rest', () => {
    for (let sector = 0; sector < sectors; sector += 1) {
      const angle = ((sector + 0.5) / sectors) * Math.PI * 2
      const x = RING_RADIUS * Math.cos(angle)
      const y = RING_RADIUS * Math.sin(angle)
      const covered = alpha(pixelAt('day', true, x, y))

      if (sector % 2 === 0) expect(covered).toBe(255)
      else expect(covered).toBe(0)
    }
  })

  it('keeps the dot and the ticks whole, so a stale mark is still a mark', () => {
    const ink = parseHex(POSITION_INKS.day.ink)

    expect(pixelAt('day', true, 0, 0)).toEqual([...ink, 255])
    expect(rgb(pixelAt('day', true, 0, -15))).toEqual([...ink])
  })

  it('is the live mark everywhere but the ring', () => {
    const live = buildPositionMark('night', false)
    const stale = buildPositionMark('night', true)
    let differing = 0
    for (let i = 3; i < live.data.length; i += 4) {
      if (live.data[i] !== stale.data[i]) differing += 1
    }
    // A pixel per gap edge or so; nowhere near the whole image. The exact
    // count is the rasteriser's business, the bound is this test's.
    expect(differing).toBeGreaterThan(0)
    expect(differing).toBeLessThan(live.data.length / 4 / 4)
  })
})
