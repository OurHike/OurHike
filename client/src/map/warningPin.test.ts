import { describe, it, expect } from 'vitest'
import { POI_TYPES } from '../lib/config'
import { WARNING_PIN } from '../lib/seriousWarnings'
import { CLOSURE_COLOR } from '../lib/closureStyle'
import {
  buildPoiIcon,
  POI_PIN_PIXEL_RATIO,
  POI_PIN_SIZE,
  PIN_HALO_COLOR,
  UNKNOWN_POI_TYPE,
} from './poiIcons'
import { buildWarningIcon, WARNING_GLYPH, WARNING_ICON_ID } from './warningPin'

// The claim this file exists to check is the one poiIcons.test.ts makes for
// the waypoints: SHAPE is the primary channel, colour only reinforces it. It
// matters more here, not less. A serious warning is red, and red is exactly
// the hue a phone in direct sun and a red-green colour-blind hiker both have
// the most trouble with - so if the warning's silhouette were the campsite
// tent, a hiker would be relying on a channel that is missing in the moments
// the warning is for.
//
// The tent is the specific risk: it is a triangle, and so is a hazard sign.
// That is why WARNING_GLYPH is hollow, and why the overlap below is measured
// rather than argued.

function pixelAt(data: Uint8ClampedArray, size: number, x: number, y: number) {
  const at = (y * size + x) * 4
  return { r: data[at], g: data[at + 1], b: data[at + 2], a: data[at + 3] }
}

/**
 * A pin's glyph as a set of "x,y" keys in a size-independent grid.
 *
 * Normalised because the two pins are drawn at different sizes - 44px against
 * 38px - and comparing raw pixel sets would find them different for that
 * reason alone, which is not the question. Sampled well inside the disc so the
 * halo ring stays out of the set.
 */
function glyphMask(image: { width: number; data: Uint8ClampedArray }): Set<string> {
  const size = image.width
  const centre = size / 2
  const grid = 64
  const mask = new Set<string>()

  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      // 0.72 of the radius: comfortably inside the disc at either size, which
      // a fixed pixel inset would not be.
      if (Math.hypot(x + 0.5 - centre, y + 0.5 - centre) > centre * 0.72) continue
      const { r, g, b, a } = pixelAt(image.data, size, x, y)
      if (a > 200 && r > 200 && g > 200 && b > 200) {
        mask.add(
          `${Math.floor(((x / size) * grid) | 0)},${Math.floor(((y / size) * grid) | 0)}`,
        )
      }
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

const ALL_POI_TYPES = [...POI_TYPES, UNKNOWN_POI_TYPE]

describe('the serious-warning pin', () => {
  it('is drawn at the size lib/seriousWarnings.ts specifies, not a number of its own', () => {
    const image = buildWarningIcon()

    expect(image.width).toBe(WARNING_PIN.sizePx * POI_PIN_PIXEL_RATIO)
    expect(image.height).toBe(image.width)
  })

  it('is bigger than every waypoint pin, which is the rule it exists to keep', () => {
    // WIREFRAMES.md §8 makes the warning the largest thing on the map. Checked
    // against the image really produced rather than against WARNING_PIN.sizePx,
    // so a rasteriser that quietly ignored the size would fail here.
    expect(buildWarningIcon().width).toBeGreaterThan(buildPoiIcon('water', 'high').width)
    expect(WARNING_PIN.sizePx).toBeGreaterThan(POI_PIN_SIZE)
  })

  it('is the closure red, so the two things that mean "stop" agree', () => {
    // poiIcons.test.ts holds the other half of this: no POI may come within 15
    // degrees of hue of it. Red on this map means the trail, or the person on
    // it, is a hazard - and it means nothing else.
    expect(WARNING_PIN.color).toBe(CLOSURE_COLOR)
  })

  it('carries a solid rim, because a moderator escalated it by hand', () => {
    // The broken rim is poiIcons.ts's "nobody has verified this exists". A
    // serious warning is the one thing on this map a person had to act on
    // before it could appear, so the provisional rim would be a false
    // statement about the strongest claim the map makes.
    //
    // Measured as ink all the way round the rim: an unverified pin's dashes
    // would leave whole angles empty.
    const image = buildWarningIcon()
    const size = image.width
    const centre = size / 2

    for (let degrees = 0; degrees < 360; degrees += 5) {
      const radians = (degrees * Math.PI) / 180
      const radius = centre * 0.94
      const x = Math.round(centre + radius * Math.cos(radians))
      const y = Math.round(centre + radius * Math.sin(radians))

      expect(pixelAt(image.data, size, x, y).a).toBeGreaterThan(200)
    }
  })
})

describe('shape as the primary channel', () => {
  const warning = glyphMask(buildWarningIcon())

  it('draws a glyph at all, rather than a bare red disc', () => {
    expect(warning.size).toBeGreaterThan(40)
  })

  it.each(ALL_POI_TYPES)('does not look like the %s pin', (type) => {
    expect(jaccard(warning, glyphMask(buildPoiIcon(type, 'high')))).toBeLessThan(0.7)
  })

  it.each(ALL_POI_TYPES)('is not a subset of the %s glyph, nor it of this', (type) => {
    // The bound that catches the tent. A solid triangle and a hazard triangle
    // overlap heavily whichever way they are drawn; what makes them different
    // shapes is that each has a part the other does not - the tent's filled
    // middle, and the warning's band where the tent has already ended.
    const other = glyphMask(buildPoiIcon(type, 'high'))

    expect(outsideFraction(warning, other)).toBeGreaterThan(0.1)
    expect(outsideFraction(other, warning)).toBeGreaterThan(0.1)
  })

  it('is hollow, which is what separates it from the tent in silhouette', () => {
    // Asserted on the geometry rather than the pixels so the reason survives:
    // the second ring is the hole, and the two after it are the exclamation
    // standing in it. Drawn as a single filled triangle this would be the
    // campsite pin in another colour.
    expect(WARNING_GLYPH).toHaveLength(4)

    const tent = glyphMask(buildPoiIcon('campsite', 'high'))

    // Sharper than the shared bound above, and specific to this pair: the
    // hollow warning covers far less of its own triangle than a solid tent
    // covers of the same outline.
    expect(warning.size).toBeLessThan(tent.size * 0.75)
  })

  it('leaves red showing all the way round the glyph, so the pin reads as a badge', () => {
    // The triangle is the widest glyph on this map - it fills its box out to
    // the corners, where a droplet or a bag does not - so it is the one that
    // could reach the rim and turn the pin into a white blob with a red
    // hairline. A ring of disc colour between the glyph and the halo is what
    // says it did not.
    //
    // Sampled just inside the disc's own edge. The 1/15 and 1/6 are
    // poiIcons.ts's rim proportions; reproduced here rather than exported
    // because what is being checked is what the IMAGE looks like, and a test
    // reading the same constant the drawing used could not tell a changed
    // proportion from a broken one.
    const image = buildWarningIcon()
    const size = image.width
    const centre = size / 2
    const rDisc = centre * (1 - 1 / 15 - 1 / 6)

    for (let degrees = 0; degrees < 360; degrees += 5) {
      const radians = (degrees * Math.PI) / 180
      const x = Math.round(centre + rDisc * 0.9 * Math.cos(radians))
      const y = Math.round(centre + rDisc * 0.9 * Math.sin(radians))
      const { r, g, b } = pixelAt(image.data, size, x, y)

      expect({ degrees, red: r > 140 && g < 110 && b < 110 }).toEqual({
        degrees,
        red: true,
      })
    }
  })
})

describe('the image id', () => {
  it('is namespaced away from the waypoint pins, which this is not one of', () => {
    expect(WARNING_ICON_ID).not.toMatch(/^poi-/)
  })
})

describe('the glyph itself', () => {
  it('stays inside the unit box the rasteriser draws it in', () => {
    for (const ring of WARNING_GLYPH) {
      for (const [x, y] of ring) {
        expect(x).toBeGreaterThanOrEqual(0)
        expect(x).toBeLessThanOrEqual(1)
        expect(y).toBeGreaterThanOrEqual(0)
        expect(y).toBeLessThanOrEqual(1)
      }
    }
  })

  it('draws the exclamation in the halo colour, not in a colour of its own', () => {
    // The glyph is punched out of the disc in PIN_HALO_COLOR by the shared
    // rasteriser. Asserting it here is what proves this pin went through that
    // rasteriser rather than a second one that happens to look similar.
    const image = buildWarningIcon()
    const size = image.width
    const halo = Number.parseInt(PIN_HALO_COLOR.slice(1), 16)
    // Dead centre is inside the exclamation bar at every size.
    const { r, g, b } = pixelAt(image.data, size, size / 2, Math.round(size * 0.52))

    expect(r).toBe((halo >> 16) & 0xff)
    expect(g).toBe((halo >> 8) & 0xff)
    expect(b).toBe(halo & 0xff)
  })
})
