import { describe, it, expect } from 'vitest'
import { MockMap } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import {
  attachTrailBadgeImages,
  BADGE_SOURCES,
  BLAZE_CHIP_BAR_COLOR,
  BLAZE_CHIP_CORNER,
  buildBadgePlate,
  buildBlazeChip,
  buildBlazeChips,
  blazeChipImageId,
  TRAIL_BADGE_LAYER_ID,
  TRAIL_BADGE_MARK_GAP,
  TRAIL_BADGE_MARK_SIZE,
  TRAIL_BADGE_PLATE_BORDER,
  TRAIL_BADGE_PLATE_DAY,
  TRAIL_BADGE_PLATE_HEIGHT,
  TRAIL_BADGE_PLATE_NIGHT,
  TRAIL_BADGE_TEXT_FIT_PADDING,
  trailMarkImageId,
  WHITE_CHIP_GROUND,
} from './trailBadges'
import { PRIMARY_TRAIL_SOURCES } from './style'
import { THROUGH_ROUTE_SOURCES } from './trailLabels'
import { BLAZE_PALETTE_MEMBERS, NEUTRAL_BLAZE_COLOR, blazePaintColor } from '../lib/blaze'
import { parseHex, POI_PIN_PIXEL_RATIO, type PoiIconImage } from './poiIcons'
import { TRAILS } from '../lib/trails'

// The through-route badge (#1283): who earns one, and what the two images
// behind it are made of. The images are checked pixel by pixel the way
// atcNoticeMark.test.ts checks the burst, because "renders something" would
// pass over a chip whose blaze bar had vanished into its ground.

function pixel(
  image: PoiIconImage,
  x: number,
  y: number,
): [number, number, number, number] {
  const at = (y * image.width + x) * 4
  return [image.data[at], image.data[at + 1], image.data[at + 2], image.data[at + 3]]
}

function rgb(hex: string): [number, number, number] {
  return [...parseHex(hex)] as [number, number, number]
}

describe('who earns a badge', () => {
  it('is exactly the through-route tier the style keys width and sort order off', () => {
    // Restated rather than imported to avoid the import cycle; only safe
    // while the three lists cannot drift.
    expect(BADGE_SOURCES).toEqual(PRIMARY_TRAIL_SOURCES)
    expect(BADGE_SOURCES).toEqual(THROUGH_ROUTE_SOURCES)
  })

  it('keys the A.T. mark off `source`, because nothing publishes a trail_id yet', () => {
    expect(trailMarkImageId('centerline')).toBe(`trail-mark-${TRAILS.AT.id}`)
    expect(trailMarkImageId('oprhp_trails')).toBeNull()
    expect(trailMarkImageId(null)).toBeNull()
  })

  it('gives every palette member a chip, and the neutrals one grey chip between them', () => {
    for (const blaze of BLAZE_PALETTE_MEMBERS) {
      expect(blazeChipImageId(blaze)).toBe(`blaze-chip-${blaze}`)
    }
    expect(blazeChipImageId('None')).toBe('blaze-chip-neutral')
    expect(blazeChipImageId('Unknown')).toBe('blaze-chip-neutral')
    expect(blazeChipImageId(null)).toBe('blaze-chip-neutral')
    expect(buildBlazeChips().map((chip) => chip.id)).toEqual([
      ...BLAZE_PALETTE_MEMBERS.map((blaze) => `blaze-chip-${blaze}`),
      'blaze-chip-neutral',
    ])
  })
})

describe('the blaze chip', () => {
  const side = TRAIL_BADGE_MARK_SIZE * POI_PIN_PIXEL_RATIO
  const centre = Math.floor(side / 2)

  it('is the mark plus the gap to the name, at the pin pixel ratio', () => {
    const chip = buildBlazeChip('Blue')
    expect(chip.width).toBe(
      (TRAIL_BADGE_MARK_SIZE + TRAIL_BADGE_MARK_GAP) * POI_PIN_PIXEL_RATIO,
    )
    expect(chip.height).toBe(side)
    // The gap is transparent - it is spacing, not ink.
    expect(pixel(chip, chip.width - 2, centre)[3]).toBe(0)
  })

  it('carries the white blaze bar in the middle, over the blaze’s own ground', () => {
    const chip = buildBlazeChip('Blue')
    const [r, g, b, a] = pixel(chip, centre, centre)
    expect([r, g, b]).toEqual(rgb(BLAZE_CHIP_BAR_COLOR))
    expect(a).toBe(255)
    // Off the bar but inside the square: the blaze hue.
    const [gr, gg, gb] = pixel(chip, 3, centre)
    expect([gr, gg, gb]).toEqual(rgb(blazePaintColor('Blue')))
  })

  it('gives a White blaze a stone ground, so the bar still reads', () => {
    const chip = buildBlazeChip('White')
    const [r, g, b] = pixel(chip, 3, centre)
    expect([r, g, b]).toEqual(rgb(WHITE_CHIP_GROUND))
    expect(pixel(chip, centre, centre).slice(0, 3)).toEqual(rgb(BLAZE_CHIP_BAR_COLOR))
  })

  it('draws the neutral chip in the map’s own "we do not know" grey', () => {
    const chip = buildBlazeChip(null)
    expect(pixel(chip, 3, centre).slice(0, 3)).toEqual(rgb(NEUTRAL_BLAZE_COLOR))
  })

  it('rounds its corners like the app icon, and leaves them clear', () => {
    const chip = buildBlazeChip('Red')
    expect(pixel(chip, 0, 0)[3]).toBe(0)
    expect(BLAZE_CHIP_CORNER).toBeCloseTo(0.21)
    // Mid-edge is solid.
    expect(pixel(chip, 0, centre)[3]).toBeGreaterThan(200)
  })
})

describe('the plate', () => {
  it('is a 9-slice pill: rounded caps around one stretchable column, with a border outside its content', () => {
    const { image, options } = buildBadgePlate(TRAIL_BADGE_PLATE_DAY)
    const ratio = POI_PIN_PIXEL_RATIO
    const radius = TRAIL_BADGE_PLATE_HEIGHT / 2

    expect(image.height).toBe(TRAIL_BADGE_PLATE_HEIGHT * ratio)
    expect(image.width).toBe((radius * 2 + 1) * ratio)
    expect(options.pixelRatio).toBe(ratio)
    expect(options.stretchX).toEqual([[radius * ratio, (radius + 1) * ratio]])
    expect(options.content).toEqual([
      TRAIL_BADGE_PLATE_BORDER * ratio,
      TRAIL_BADGE_PLATE_BORDER * ratio,
      (radius * 2 + 1 - TRAIL_BADGE_PLATE_BORDER) * ratio,
      (TRAIL_BADGE_PLATE_HEIGHT - TRAIL_BADGE_PLATE_BORDER) * ratio,
    ])
  })

  it('fills with the sheet’s paper at 95% and edges it in the border token', () => {
    for (const face of [TRAIL_BADGE_PLATE_DAY, TRAIL_BADGE_PLATE_NIGHT]) {
      const { image } = buildBadgePlate(face)
      const middle = pixel(
        image,
        Math.floor(image.width / 2),
        Math.floor(image.height / 2),
      )
      expect(middle.slice(0, 3)).toEqual(rgb(face.fill))
      expect(middle[3]).toBe(Math.round(0.95 * 255))
      // The outermost row of the straight edge: border ink, opaque.
      const edge = pixel(image, Math.floor(image.width / 2), 0)
      expect(edge.slice(0, 3)).toEqual(rgb(face.border))
      // Corners are outside the pill.
      expect(pixel(image, 0, 0)[3]).toBe(0)
    }
  })

  it('pads the text so the plate is the mark plus four px of paper each way', () => {
    const [top, right, bottom, left] = TRAIL_BADGE_TEXT_FIT_PADDING
    expect(top + bottom + TRAIL_BADGE_PLATE_BORDER * 2 + TRAIL_BADGE_MARK_SIZE).toBe(
      TRAIL_BADGE_PLATE_HEIGHT,
    )
    expect(left + TRAIL_BADGE_PLATE_BORDER).toBe(4)
    expect(right + TRAIL_BADGE_PLATE_BORDER).toBe(10)
  })
})

describe('attachTrailBadgeImages', () => {
  it('registers both plates and every chip once the layer is in the style, never twice', () => {
    const map = new MockMap({
      style: { layers: [{ id: TRAIL_BADGE_LAYER_ID }], sources: {} },
    })

    attachTrailBadgeImages(map as unknown as MapLibreMap)

    expect(map.hasImage(TRAIL_BADGE_PLATE_DAY.id)).toBe(true)
    expect(map.hasImage(TRAIL_BADGE_PLATE_NIGHT.id)).toBe(true)
    for (const { id } of buildBlazeChips()) expect(map.hasImage(id)).toBe(true)
    const plate = map.imageOptions.get(TRAIL_BADGE_PLATE_DAY.id) as { stretchX: unknown }
    expect(plate.stretchX).toBeDefined()

    const before = map.images.size
    attachTrailBadgeImages(map as unknown as MapLibreMap)
    expect(map.images.size).toBe(before)
  })

  it('waits for the layer, and registers nothing after detaching', () => {
    const map = new MockMap({})
    const detach = attachTrailBadgeImages(map as unknown as MapLibreMap)
    expect(map.images.size).toBe(0)

    detach()
    map.layerIds = [TRAIL_BADGE_LAYER_ID]
    map.emit('styledata')
    expect(map.images.size).toBe(0)
  })
})
