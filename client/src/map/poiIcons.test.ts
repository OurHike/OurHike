import { describe, it, expect } from 'vitest'
import { POI_TYPES } from '../lib/config'
import { CLOSURE_COLOR } from '../lib/closureStyle'
import {
  buildPoiIcon,
  buildPoiIcons,
  poiIconId,
  POI_COLORS,
  POI_FALLBACK_COLOR,
  POI_PIN_PIXEL_RATIO,
  POI_PIN_SIZE,
  PIN_HALO_COLOR,
  UNKNOWN_POI_TYPE,
  type PoiConfidence,
} from './poiIcons'

// The two rules these pins have to keep, both from real constraints rather
// than taste:
//
//  1. SHAPE carries the meaning; colour only reinforces it. FEATURES.md asks
//     for colour-coded categories at WCAG AA, and WIREFRAMES.md `9d` requires
//     the map to survive a greyscale pass - which is what a phone in direct
//     sun approximates. Both hold only if the glyphs differ.
//  2. Confidence is the RIM. A pin nobody has verified must look provisional
//     without looking like a different category (WIREFRAMES.md §11).
//
// Contrast ratios are computed here rather than asserted from a comment, so a
// palette change that breaks AA fails the suite instead of shipping.

function channel(c: number): number {
  const s = c / 255
  return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4)
}

function luminance(hex: string): number {
  const value = Number.parseInt(hex.slice(1), 16)
  return (
    0.2126 * channel((value >> 16) & 0xff) +
    0.7152 * channel((value >> 8) & 0xff) +
    0.0722 * channel(value & 0xff)
  )
}

function contrastRatio(a: string, b: string): number {
  const [lighter, darker] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (lighter + 0.05) / (darker + 0.05)
}

/** Plain HSL hue in degrees. */
function hue(hex: string): number {
  const value = Number.parseInt(hex.slice(1), 16)
  const [r, g, b] = [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff].map(
    (c) => c / 255,
  )
  const max = Math.max(r, g, b)
  const span = max - Math.min(r, g, b)
  if (span === 0) return 0

  const degrees =
    max === r ? ((g - b) / span) % 6 : max === g ? (b - r) / span + 2 : (r - g) / span + 4
  return (degrees * 60 + 360) % 360
}

/** Shortest way round the colour wheel, so 350° and 10° read as 20° apart. */
function hueDistance(a: string, b: string): number {
  const raw = Math.abs(hue(a) - hue(b))
  return Math.min(raw, 360 - raw)
}

const PIXELS = POI_PIN_SIZE * POI_PIN_PIXEL_RATIO
const CENTER = PIXELS / 2

interface Pixel {
  r: number
  g: number
  b: number
  a: number
}

function pixelAt(data: Uint8ClampedArray, x: number, y: number): Pixel {
  const at = (y * PIXELS + x) * 4
  return { r: data[at], g: data[at + 1], b: data[at + 2], a: data[at + 3] }
}

/** Distance from the pin's centre, which is how the rim and the disc are told
 *  apart without reaching into the module's private radii. */
function radius(x: number, y: number): number {
  return Math.hypot(x + 0.5 - CENTER, y + 0.5 - CENTER)
}

/**
 * The glyph as a set of "x,y" keys: the near-white pixels well inside the
 * disc, which is the shape and nothing else.
 *
 * Sampling comfortably inside the disc rather than up to its edge keeps the
 * halo out of the set, so this measures the glyph and not the pin.
 */
function glyphMask(type: string, confidence: PoiConfidence = 'high'): Set<string> {
  const { data } = buildPoiIcon(type, confidence)
  const mask = new Set<string>()

  for (let y = 0; y < PIXELS; y += 1) {
    for (let x = 0; x < PIXELS; x += 1) {
      if (radius(x, y) > CENTER - 10) continue
      const { r, g, b, a } = pixelAt(data, x, y)
      if (a > 200 && r > 200 && g > 200 && b > 200) mask.add(`${x},${y}`)
    }
  }

  return mask
}

function shared(a: Set<string>, b: Set<string>): number {
  return [...a].filter((key) => b.has(key)).length
}

function jaccard(a: Set<string>, b: Set<string>): number {
  return shared(a, b) / (a.size + b.size - shared(a, b))
}

/** How much of `a` lies outside `b`. Zero means `a` is a strict subset. */
function outsideFraction(a: Set<string>, b: Set<string>): number {
  return (a.size - shared(a, b)) / a.size
}

const ALL_TYPES = [...POI_TYPES, UNKNOWN_POI_TYPE]

describe('the palette', () => {
  it('gives every POI type the pipeline publishes a colour of its own', () => {
    // Keyed off config.POI_TYPES rather than a list kept here, so adding a
    // category to the pipeline cannot leave it with no pin.
    for (const type of POI_TYPES) expect(POI_COLORS[type]).toMatch(/^#[0-9a-f]{6}$/i)
  })

  it('uses a different accent for each category', () => {
    const used = Object.values(POI_COLORS)

    expect(new Set(used).size).toBe(used.length)
  })

  it.each([...POI_TYPES, 'fallback'] as const)(
    'clears WCAG AA between the %s disc and the glyph drawn on it',
    (type) => {
      const disc = type === 'fallback' ? POI_FALLBACK_COLOR : POI_COLORS[type]

      expect(contrastRatio(disc, PIN_HALO_COLOR)).toBeGreaterThanOrEqual(4.5)
    },
  )

  it('leaves the closure red to closures, and takes none of it for a POI', () => {
    // A pin that reads at a glance as "do not walk down there" is a worse
    // failure than a dull palette.
    //
    // Judged by hue rather than by an equality check against one hex, because
    // a near-miss of the closure red is the actual risk. Resupply's burnt
    // orange is the closest at ~18 degrees, which is the same separation
    // WIREFRAMES.md's own blaze table accepts between Orange and Red - and
    // unlike those two, these also differ in glyph, and a closure is a line
    // rather than a pin at all.
    for (const hex of [...Object.values(POI_COLORS), POI_FALLBACK_COLOR]) {
      expect(hueDistance(hex, CLOSURE_COLOR)).toBeGreaterThan(15)
    }
  })
})

describe('shape as the primary channel', () => {
  it('draws a visibly different glyph for every category', () => {
    // The point of the whole exercise: these six accents sit within ~2:1 of
    // each other, so in glare or in greyscale they are one colour. If two
    // glyphs also coincided, those two categories would be indistinguishable
    // on a sunlit screen - which for water is a safety problem, not a polish
    // one.
    for (const type of ALL_TYPES) {
      for (const other of ALL_TYPES) {
        if (type === other) continue
        expect(jaccard(glyphMask(type), glyphMask(other))).toBeLessThan(0.7)
      }
    }
  })

  it('never lets one glyph be a subset of another', () => {
    // Sharper than the overlap bound above, and the reason the house has a
    // door: before it did, every pixel of the droplet sat inside the house.
    // A shape wholly contained in another can read as a half-drawn version of
    // it, which overlap alone does not catch - two shapes can overlap heavily
    // and still each have a part the other does not.
    for (const type of ALL_TYPES) {
      for (const other of ALL_TYPES) {
        if (type === other) continue
        expect(outsideFraction(glyphMask(type), glyphMask(other))).toBeGreaterThan(0.1)
      }
    }
  })

  it('draws a glyph at all for every category, rather than a bare disc', () => {
    for (const type of ALL_TYPES) expect(glyphMask(type).size).toBeGreaterThan(80)
  })

  it('keeps the glyph inside the disc, never spilling onto the rim', () => {
    // The glyph box is sized so its corners stay within the disc. If that ever
    // stops being true a glyph bleeds into the halo and the pin loses its edge.
    for (const type of ALL_TYPES) {
      const { data } = buildPoiIcon(type, 'high')

      for (let y = 0; y < PIXELS; y += 1) {
        for (let x = 0; x < PIXELS; x += 1) {
          if (radius(x, y) <= CENTER - 7) continue
          const { r, g, b, a } = pixelAt(data, x, y)
          // Outside the disc only the halo and the dark edge may appear, and
          // the halo is continuous - so any near-white pixel here belongs to
          // the rim, never to a glyph that escaped.
          if (a > 200 && r > 200 && g > 200 && b > 200) {
            expect(radius(x, y)).toBeGreaterThan(CENTER - 8)
          }
        }
      }
    }
  })
})

describe('confidence as a second, independent channel', () => {
  it('draws the same glyph whether or not a POI has been verified', () => {
    // Confidence must not change what the pin says it IS. A hiker reading an
    // unverified spring should see a spring somebody is unsure about, not a
    // different category.
    for (const type of ALL_TYPES) {
      expect(glyphMask(type, 'low')).toEqual(glyphMask(type, 'high'))
    }
  })

  it('breaks the rim of an unverified pin, and leaves a verified one solid', () => {
    const verified = buildPoiIcon('water', 'high')
    const unverified = buildPoiIcon('water', 'low')

    let solidRim = 0
    let brokenRim = 0
    for (let y = 0; y < PIXELS; y += 1) {
      for (let x = 0; x < PIXELS; x += 1) {
        if (radius(x, y) <= CENTER - 6 || radius(x, y) > CENTER - 1) continue
        if (pixelAt(verified.data, x, y).a > 200) solidRim += 1
        if (pixelAt(unverified.data, x, y).a > 200) brokenRim += 1
      }
    }

    expect(solidRim).toBeGreaterThan(0)
    // Half the rim, give or take the anti-aliased ends of each dash.
    expect(brokenRim).toBeLessThan(solidRim * 0.75)
    expect(brokenRim).toBeGreaterThan(solidRim * 0.25)
  })
})

describe('the images themselves', () => {
  it('is transparent in the corners, so the pin is a disc and not a tile', () => {
    const { data } = buildPoiIcon('water', 'high')

    for (const [x, y] of [
      [0, 0],
      [PIXELS - 1, 0],
      [0, PIXELS - 1],
      [PIXELS - 1, PIXELS - 1],
    ]) {
      expect(pixelAt(data, x, y).a).toBe(0)
    }
  })

  it('carries a full RGBA buffer at the declared size', () => {
    const image = buildPoiIcon('shelter', 'high')

    expect(image.width).toBe(PIXELS)
    expect(image.height).toBe(PIXELS)
    expect(image.data).toHaveLength(PIXELS * PIXELS * 4)
  })

  it('draws a POI type it has never heard of rather than nothing at all', () => {
    // A category added upstream should reach the map as a neutral pin, the
    // same call waypointLanes.ts makes when it drops an unknown type into the
    // ELSE lane. Silently drawing nothing would hide real data behind a client
    // release.
    const unknown = buildPoiIcon('yurt', 'high')

    expect(unknown.data).toEqual(buildPoiIcon(UNKNOWN_POI_TYPE, 'high').data)
    expect(pixelAt(unknown.data, CENTER, CENTER).a).toBeGreaterThan(200)
  })
})

describe('buildPoiIcons', () => {
  it('registers every published type plus the fallback, in both confidences', () => {
    const ids = buildPoiIcons().map((icon) => icon.id)

    expect(ids).toHaveLength(ALL_TYPES.length * 2)
    for (const type of ALL_TYPES) {
      expect(ids).toContain(poiIconId(type, 'high'))
      expect(ids).toContain(poiIconId(type, 'low'))
    }
  })

  it('gives every image a unique id, so none can quietly overwrite another', () => {
    const ids = buildPoiIcons().map((icon) => icon.id)

    expect(new Set(ids).size).toBe(ids.length)
  })

  it('declares the pixel ratio it was drawn at', () => {
    // Registered without it, a 60px badge is drawn 60 CSS px wide - twice the
    // intended size, and the biggest thing on the map.
    for (const icon of buildPoiIcons()) {
      expect(icon.pixelRatio).toBe(POI_PIN_PIXEL_RATIO)
    }
  })

  it('stays smaller than the serious-warning pin, which outranks it', () => {
    // WIREFRAMES.md §8 puts that pin at 44px - one full touch target, and the
    // biggest thing on the map. A water pin drawn larger, or merely drawn the
    // same, would outshout the one thing here that must never be outshouted.
    expect(POI_PIN_SIZE).toBeLessThan(44)
  })
})
