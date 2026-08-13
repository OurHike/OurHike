import { describe, it, expect } from 'vitest'
import { POI_TYPES } from '../lib/config'
import { CLOSURE_COLOR } from '../lib/closureStyle'
import { SITE_ANCHOR_TYPES, SITE_MEMBER_TYPES } from './poiSites'
import {
  badgeCenters,
  buildPoiIcon,
  buildPoiIcons,
  poiColor,
  poiGlyphPath,
  pinGeometry,
  poiIconId,
  siteMemberCombinations,
  sitePinPadding,
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
 * Rasterised pins, kept between calls.
 *
 * The two comparisons below are every ordered pair of categories, so the
 * rasteriser is asked for the same handful of pins n² times - and each pin is
 * a supersampled 76×76 draw. At five categories that was merely wasteful; the
 * three added with ATC's vista/parking/privy layers took it past the 5s
 * per-test budget, which is a fact about this loop rather than about the pins.
 * Caching makes the cost linear in categories again.
 */
const MASK_CACHE = new Map<string, Set<string>>()

/**
 * The glyph as a set of "x,y" keys: the near-white pixels well inside the
 * disc, which is the shape and nothing else.
 *
 * Sampling comfortably inside the disc rather than up to its edge keeps the
 * halo out of the set, so this measures the glyph and not the pin.
 */
function glyphMask(type: string, confidence: PoiConfidence = 'high'): Set<string> {
  const cached = MASK_CACHE.get(`${type}:${confidence}`)
  if (cached !== undefined) return cached

  const { data } = buildPoiIcon(type, confidence)
  const mask = new Set<string>()

  for (let y = 0; y < PIXELS; y += 1) {
    for (let x = 0; x < PIXELS; x += 1) {
      if (radius(x, y) > CENTER - 10) continue
      const { r, g, b, a } = pixelAt(data, x, y)
      if (a > 200 && r > 200 && g > 200 && b > 200) mask.add(`${x},${y}`)
    }
  }

  MASK_CACHE.set(`${type}:${confidence}`, mask)
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

    // The plain matrix, plus the site variants asserted below. Written as the
    // sum rather than as 46, so adding a POI type or a member category moves
    // this by construction instead of by someone remembering to.
    const sited = SITE_ANCHOR_TYPES.length * 2 * (2 ** SITE_MEMBER_TYPES.length - 1)
    expect(ids).toHaveLength(ALL_TYPES.length * 2 + sited)
    for (const type of ALL_TYPES) {
      expect(ids).toContain(poiIconId(type, 'high'))
      expect(ids).toContain(poiIconId(type, 'low'))
    }
  })

  // Site pins (#524). The style resolves `site_members` straight to an image id,
  // so an unregistered combination is a pin that draws nothing at all.
  it('registers every member combination an anchor can carry', () => {
    const ids = buildPoiIcons().map((icon) => icon.id)

    for (const type of SITE_ANCHOR_TYPES) {
      for (const members of siteMemberCombinations()) {
        expect(ids).toContain(poiIconId(type, 'high', members))
        expect(ids).toContain(poiIconId(type, 'low', members))
      }
    }
  })

  it('builds no site variant for a type that cannot anchor one', () => {
    // A viewpoint never anchors a site (pipeline ANCHOR_TYPES), so the full
    // matrix for it would be fourteen images the style can never ask for.
    const ids = buildPoiIcons().map((icon) => icon.id)

    expect(ids).not.toContain(poiIconId('viewpoint', 'high', ['privy']))
  })

  it('leaves a plain pin’s id exactly as it was', () => {
    // The old ids must not move: every existing `match` arm, every test and the
    // legend's own icon lookup resolve through them.
    expect(poiIconId('shelter', 'high', [])).toBe('poi-shelter-verified')
    expect(poiIconId('shelter', 'high')).toBe('poi-shelter-verified')
  })

  it('names a site pin by what it carries', () => {
    expect(poiIconId('shelter', 'high', ['privy', 'water'])).toBe(
      'poi-shelter-verified-privy+water',
    )
  })

  it('draws something different when it carries something', () => {
    // The failure this catches is a strip that computes but never reaches the
    // pixels - every id registered, every image identical, and a hiker told
    // nothing.
    const plain = buildPoiIcon('shelter', 'high')
    const sited = buildPoiIcon('shelter', 'high', ['privy'])

    expect(sited.data).not.toEqual(plain.data)
  })

  it('draws a member glyph big enough to read, at every member count', () => {
    // 5.7 CSS px was reported as hard to read on a real screen, which is the
    // review features/POI_SITES.md said this decision needed, and 7 is the floor
    // that came out of it. The badge now clears it by half again, because 7.1
    // was reported as too quiet on the same screen - so the floor is asserted
    // here and the ACTUAL size below it, which is what would catch a badge
    // quietly shrinking back towards the bar it stays clear of.
    //
    // A badge is the SAME SIZE whatever a pin carries, which is most of what
    // moving off the band bought: the strip's cell had to divide a fixed span
    // between the members, so a third member shrank all three. Asserted for all
    // three counts anyway, because the loop is what would catch a future layout
    // going back to dividing something.
    const g = pinGeometry(POI_PIN_SIZE * POI_PIN_PIXEL_RATIO)

    for (const count of [1, 2, 3]) {
      expect(
        g.badge.glyphBox / POI_PIN_PIXEL_RATIO,
        `${count} member(s)`,
      ).toBeGreaterThanOrEqual(7)
      expect(badgeCenters(count, g.badge)).toHaveLength(count)
    }

    // Bigger than the footer strip managed at its most generous (9.6 px at one
    // member), which is the bar this layout has to beat to have been worth it.
    expect(g.badge.glyphBox / POI_PIN_PIXEL_RATIO).toBeGreaterThan(9.6)
  })

  it('leaves the anchor own glyph exactly the size a plain pin draws it', () => {
    // The whole of #611. The footer band could only be made by shrinking the
    // anchor's own glyph to 11.1 CSS px, so a shelter carrying a privy was a
    // less legible shelter than one carrying nothing - and every site pin paid
    // it, including the 57% carrying a single member.
    const g = pinGeometry(POI_PIN_SIZE * POI_PIN_PIXEL_RATIO)

    expect(g.glyphBox / POI_PIN_PIXEL_RATIO).toBeCloseTo(17.72, 2)
    // And still the biggest thing on the pin. The margin has narrowed - 17.7
    // against 10.7, where the first badge size made it 17.7 against 7.1 - which
    // is the real cost of a badge a hiker can read: a site pin now says two
    // things loudly rather than one loudly and one quietly. It is a shelter
    // first, and this is where that stops being true if a badge grows again.
    expect(g.glyphBox).toBeGreaterThan(g.badge.glyphBox)
  })

  it('never lets a badge reach the disc', () => {
    // The invariant that keeps the anchor's glyph whole, and the one thing the
    // badge ring distance exists to buy. A badge crossing the disc would sit on
    // top of the silhouette this pin is mostly there to show.
    const g = pinGeometry(POI_PIN_SIZE * POI_PIN_PIXEL_RATIO)

    for (const count of [1, 2, 3]) {
      for (const { x, y } of badgeCenters(count, g.badge)) {
        expect(Math.hypot(x, y) - g.badge.radius, `${count} member(s)`).toBeGreaterThan(
          g.rDisc,
        )
      }
    }
  })

  it('keeps two badges off each other', () => {
    // The fan's pitch is derived from the badge size, so this catches a badge
    // grown without the spacing following it - which would draw two members as
    // one smudge and lose a category silently.
    const g = pinGeometry(POI_PIN_SIZE * POI_PIN_PIXEL_RATIO)

    for (const count of [2, 3]) {
      const spots = badgeCenters(count, g.badge)
      for (let i = 1; i < spots.length; i += 1) {
        const apart = Math.hypot(spots[i].x - spots[i - 1].x, spots[i].y - spots[i - 1].y)
        expect(apart, `${count} member(s)`).toBeGreaterThan(g.badge.radius * 2)
      }
    }
  })

  it('puts the badges in the upper right, however many there are', () => {
    // Where the maintainer asked for them, and the reason the fan is centred on
    // the 45 degree axis rather than growing from one end: one member lands
    // square in the corner, and the rest open out either side of it evenly.
    //
    // WHAT THIS DELIBERATELY DOES NOT ASSERT is `x >= 0 && y <= 0` - a badge
    // strictly inside the quarter turn between twelve and three - which is what
    // it said while the badge was 14 px across. Three badges half again that
    // size do not fit in a quarter turn without touching each other, so at three
    // members the outer two sit about 7 degrees past twelve and past three. That
    // is a consequence of the size, not a drift: what has to hold is that every
    // badge stays on the upper-right side of the pin, which is the anti-diagonal
    // below, and that none of them wanders more than 55 degrees off the corner.
    const g = pinGeometry(POI_PIN_SIZE * POI_PIN_PIXEL_RATIO)
    const AXIS = -Math.PI / 4

    // One member is exactly in the corner: as far right as it is up.
    const only = badgeCenters(1, g.badge)[0]
    expect(only.x).toBeCloseTo(-only.y, 6)

    for (const count of [1, 2, 3]) {
      const spots = badgeCenters(count, g.badge)

      for (const { x, y } of spots) {
        // Upper-right of the anti-diagonal through the pin's centre.
        expect(x - y, `${count} member(s)`).toBeGreaterThan(0)
        // And within 55 degrees of the corner itself, which is the room three
        // badges take. A fourth member category would break this, and should -
        // it is a layout decision, not a fraction to widen quietly.
        const off = Math.atan2(y, x) - AXIS
        expect(Math.abs(off) * (180 / Math.PI), `${count} member(s)`).toBeLessThan(55)
      }

      // Symmetric about the 45 degree axis: the first and last badge are the
      // same angle either side of it.
      const first = Math.atan2(spots[0].y, spots[0].x)
      const last = Math.atan2(spots[spots.length - 1].y, spots[spots.length - 1].x)
      expect((first + last) / 2, `${count} member(s)`).toBeCloseTo(AXIS, 6)
    }
  })

  it('pads a site pin symmetrically, and pads a plain pin not at all', () => {
    // Symmetry is what lets map/poiLayers.ts stay as it is: the disc is at the
    // centre of the image, so MapLibre's default anchor puts it on the hiker's
    // coordinate without an `icon-offset` to keep in step with the padding.
    expect(sitePinPadding(0)).toBe(0)
    expect(buildPoiIcon('shelter', 'high').width).toBe(POI_PIN_SIZE * POI_PIN_PIXEL_RATIO)

    let previous = 0
    for (const count of [1, 2, 3]) {
      const pad = sitePinPadding(count)
      const image = buildPoiIcon('shelter', 'high', SITE_MEMBER_TYPES.slice(0, count))

      expect(image.width, `${count} member(s)`).toBe(image.height)
      expect(image.width, `${count} member(s)`).toBe(
        (POI_PIN_SIZE + pad * 2) * POI_PIN_PIXEL_RATIO,
      )
      // A pin carrying one member should not be given the collision box of one
      // carrying three - that is 57% of sites evicting neighbours for room they
      // are not using.
      expect(pad, `${count} member(s)`).toBeGreaterThanOrEqual(previous)
      previous = pad
    }

    expect(sitePinPadding(1)).toBeLessThan(sitePinPadding(3))
  })

  it('clears WCAG AA between a badge and the glyph on it', () => {
    // A badge's whole colour argument: the glyph is PIN_HALO_COLOR and the disc
    // under it is that category's own accent, which is the SAME pair the
    // disc-versus-glyph assertion above already proves for every type. So this
    // is not a new bar, it is the existing one read the other way round -
    // measured at privy 8.51, water 5.41, campsite 5.09.
    for (const type of SITE_MEMBER_TYPES) {
      expect(contrastRatio(poiColor(type), PIN_HALO_COLOR)).toBeGreaterThanOrEqual(4.5)
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

describe('poiGlyphPath', () => {
  // The same silhouettes the rasteriser fills, handed to chrome as SVG - the
  // waypoint card's photo placeholder draws them. What matters is that they
  // stay the SAME shapes: a placeholder tent that drifted from the pin's tent
  // would be two shape languages claiming to be one.

  it.each(ALL_TYPES)('closes every ring of %s, so the fill has an inside', (type) => {
    const path = poiGlyphPath(type)

    // One M...Z subpath per ring and nothing outside them.
    expect(path).toMatch(/^(M[^MZ]+Z)+$/)
  })

  it('keeps the shelter’s doorway as its own subpath for the even-odd fill to cut out', () => {
    const subpaths = poiGlyphPath('shelter').match(/M[^MZ]+Z/g)

    expect(subpaths).toHaveLength(2)
  })

  it('stays inside the unit box the viewBox declares', () => {
    for (const type of ALL_TYPES) {
      const numbers = poiGlyphPath(type)
        .split(/[MLZ ]/)
        .filter((token) => token !== '')
        .map(Number)

      expect(numbers.length).toBeGreaterThan(0)
      for (const value of numbers) {
        expect(value).toBeGreaterThanOrEqual(0)
        expect(value).toBeLessThanOrEqual(1)
      }
    }
  })

  it('hands an unknown type the placeholder diamond, not an empty path', () => {
    // Same call the rasteriser makes: a category this build has never heard
    // of is already on the map as a neutral pin, and its card's placeholder
    // should show the same diamond rather than a blank slot.
    expect(poiGlyphPath('hot_springs')).toBe(poiGlyphPath(UNKNOWN_POI_TYPE))
  })
})
