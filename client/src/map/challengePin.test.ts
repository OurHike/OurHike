import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  buildPoiIcon,
  mixHex,
  parseHex,
  PIN_EDGE_COLOR,
  PIN_HALO_COLOR,
  POI_COLORS,
  POI_FALLBACK_COLOR,
  POI_PIN_INK_SIZE,
  POI_PIN_PIXEL_RATIO,
  POI_PIN_SIZE,
} from './poiIcons'
import { WORKDAY_COLOR } from './workdayPin'
import { WARNING_PIN } from '../lib/seriousWarnings'
import {
  buildChallengeIcon,
  CHALLENGE_CHECK_GLYPH,
  CHALLENGE_COLOR,
  CHALLENGE_EDGE_COLOR,
  CHALLENGE_EDGE_MIX,
  CHALLENGE_ICON_ID,
  CHALLENGE_TAGGED_ICON_ID,
} from './challengePin'

// The challenge-place pin (#1780). workdayPin.test.ts's posture: every claim
// map/challengePin.ts's header makes about its colour and its shape is
// COMPUTED here rather than taken from the comment - including the one bar
// it does not clear, which is recorded as a measurement with the two
// channels that stand in for it, so a later palette change that removes
// those channels fails here rather than in somebody's glare.

/** WCAG relative luminance - poiIcons.test.ts's, restated for workdayPin.test.ts's reason. */
function luminance(hex: string): number {
  const channel = (value: number) => {
    const c = value / 255
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  const [r, g, b] = parseHex(hex)
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function contrast(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (light + 0.05) / (dark + 0.05)
}

function hue(hex: string): number {
  const [r, g, b] = parseHex(hex).map((c) => c / 255)
  const max = Math.max(r, g, b)
  const span = max - Math.min(r, g, b)
  if (span === 0) return 0
  const raw =
    max === r ? ((g - b) / span) % 6 : max === g ? (b - r) / span + 2 : (r - g) / span + 4
  return (raw * 60 + 360) % 360
}

function hueGap(a: string, b: string): number {
  const raw = Math.abs(hue(a) - hue(b))
  return Math.min(raw, 360 - raw)
}

/** Every other colour a pin on this map is filled with. */
const OTHER_PINS: Record<string, string> = {
  ...POI_COLORS,
  fallback: POI_FALLBACK_COLOR,
  workday: WORKDAY_COLOR,
  warning: WARNING_PIN.color,
}

describe('the challenge pin’s colour', () => {
  it('is the design system’s --blaze-yellow, not a hex picked for the map', () => {
    const tokens = readFileSync(
      resolve(process.cwd(), 'src/design-system/tokens/colors.css'),
      'utf8',
    )
    expect(tokens).toContain(`--blaze-yellow:${CHALLENGE_COLOR};`)
    expect(tokens).toContain('--accent-blaze-yellow:var(--blaze-yellow);')
  })

  it('carries its tick in stone-900, because paper on this yellow fails WCAG AA', () => {
    // Every other filled pin draws its glyph in paper. On blaze-yellow that
    // is 2.42:1; stone-900 is 6.08:1.
    expect(contrast(PIN_HALO_COLOR, CHALLENGE_COLOR)).toBeLessThan(4.5)
    expect(contrast(PIN_EDGE_COLOR, CHALLENGE_COLOR)).toBeGreaterThanOrEqual(4.5)
  })

  it('edges both states at 3:1 on the paper round the pin, with the first step that gets there', () => {
    // WCAG 1.4.11's bar for a graphic, and the untagged pin's edge is the
    // only ink it has. Derived, as colors.css derives --stone-600: the first
    // 1% step from the yellow toward stone-900 that reaches the bar.
    expect(CHALLENGE_EDGE_COLOR).toBe(
      mixHex(CHALLENGE_COLOR, PIN_EDGE_COLOR, CHALLENGE_EDGE_MIX),
    )
    expect(contrast(CHALLENGE_EDGE_COLOR, PIN_HALO_COLOR)).toBeGreaterThanOrEqual(3)

    const oneStepLess = mixHex(CHALLENGE_COLOR, PIN_EDGE_COLOR, CHALLENGE_EDGE_MIX - 0.01)
    expect(contrast(oneStepLess, PIN_HALO_COLOR)).toBeLessThan(3)
  })

  it('misses the 30-degree hue bar against resupply and the workday, as the header records', () => {
    // A MEASUREMENT, NOT A GOAL. poiIcons.test.ts and workdayPin.test.ts
    // hold every other accent 30 degrees off its neighbours; this one is
    // 12.8 off resupply and 29.7 off the workday olive, and no yellow could
    // do better against both (the band that clears both is empty). Pinned so
    // a token change that moved it is noticed, and so the next test is read
    // as the reason it ships anyway.
    expect(hueGap(CHALLENGE_COLOR, POI_COLORS.resupply)).toBeCloseTo(12.8, 1)
    expect(hueGap(CHALLENGE_COLOR, WORKDAY_COLOR)).toBeCloseTo(29.7, 1)
  })

  it('is set apart by lightness from every pin whose hue it is near', () => {
    // What stands in for the hue: wherever the gap is under 30 degrees, the
    // yellow is lighter by more than 2.19:1 - the widest ratio poiIcons.ts
    // records between its own accents, which it calls one colour in glare.
    // That is the channel a greyscale pass keeps. The shape is the other,
    // held under "the shape" below.
    for (const [name, color] of Object.entries(OTHER_PINS)) {
      if (hueGap(CHALLENGE_COLOR, color) >= 30) continue
      expect(
        contrast(CHALLENGE_COLOR, color),
        `${name} (${color}) is ${Math.round(hueGap(CHALLENGE_COLOR, color))}° away and only ${contrast(CHALLENGE_COLOR, color).toFixed(2)}:1 apart`,
      ).toBeGreaterThan(2.19)
    }
  })

  it('stays clear of the closure red', () => {
    // poiIcons.test.ts's bar for every accent: a pin that reads at a glance
    // as "do not walk down there" is the worse failure.
    expect(hueGap(CHALLENGE_COLOR, WARNING_PIN.color)).toBeGreaterThan(15)
  })
})

// --- The shape ---------------------------------------------------------------

const RATIO = POI_PIN_PIXEL_RATIO
const PIXELS = POI_PIN_SIZE * RATIO
const CENTRE = PIXELS / 2

function alphaAt(data: Uint8ClampedArray, x: number, y: number): number {
  return data[(Math.floor(y) * PIXELS + Math.floor(x)) * 4 + 3]
}

function colourCount(data: Uint8ClampedArray, hex: string): number {
  const [r, g, b] = parseHex(hex)
  let count = 0
  for (let at = 0; at < data.length; at += 4) {
    if (
      data[at + 3] === 255 &&
      data[at] === r &&
      data[at + 1] === g &&
      data[at + 2] === b
    ) {
      count += 1
    }
  }
  return count
}

describe('the challenge pin’s shape', () => {
  it('is a diamond, which no waypoint is', () => {
    // Straight up from the centre, past the waypoint's radius: a diamond's
    // vertex is there (the apothem is the waypoint's radius, so the tips
    // reach √2 of it), and a round waypoint pin has nothing.
    const reach = (POI_PIN_INK_SIZE / 2) * RATIO * 1.2
    const diamond = buildChallengeIcon(false)
    const waypoint = buildPoiIcon('viewpoint', 'low')

    expect(alphaAt(diamond.data, CENTRE, CENTRE - reach)).toBe(255)
    expect(alphaAt(waypoint.data, CENTRE, CENTRE - reach)).toBe(0)
  })

  it('covers the whole of the round waypoint pin it is drawn over', () => {
    // Drawn concentric (map/challengeLayers.ts), every pixel the waypoint
    // inks, the diamond inks too - no sliver of a shelter's green pokes out.
    const diamond = buildChallengeIcon(false).data
    const waypoint = buildPoiIcon('shelter', 'high').data
    let uncovered = 0
    for (let at = 3; at < waypoint.length; at += 4) {
      // The waypoint's shadow is a 28% wash one sliver below it; the
      // diamond's own covers it, so compare the opaque ink.
      if (waypoint[at] === 255 && diamond[at] !== 255) uncovered += 1
    }
    expect(uncovered).toBe(0)
  })

  it('is the waypoint footprint, not a bigger pin', () => {
    // A challenge is opted into; a pin drawn larger than the waypoints
    // round it would be pressing on the walking view (principle 2).
    for (const tagged of [false, true]) {
      const icon = buildChallengeIcon(tagged)
      expect(icon.width).toBe(PIXELS)
      expect(icon.height).toBe(PIXELS)
    }
  })

  it('is hollow until tagged, and filled with a tick once it is', () => {
    const hollow = buildChallengeIcon(false).data
    const filled = buildChallengeIcon(true).data

    // Paper at the centre of the hollow pin; none of the yellow anywhere.
    const centre = (CENTRE * PIXELS + CENTRE) * 4
    expect([...hollow.slice(centre, centre + 3)]).toEqual([...parseHex(PIN_HALO_COLOR)])
    expect(colourCount(hollow, CHALLENGE_COLOR)).toBe(0)

    // The yellow fill and the dark tick on the tagged one.
    expect(colourCount(filled, CHALLENGE_COLOR)).toBeGreaterThan(200)
    expect(colourCount(filled, PIN_EDGE_COLOR)).toBeGreaterThan(50)
    expect(colourCount(hollow, PIN_EDGE_COLOR)).toBe(0)

    // The same edge on both, so the outline does not change when the
    // hiker tags - only what is inside it.
    expect(colourCount(hollow, CHALLENGE_EDGE_COLOR)).toBeGreaterThan(100)
    expect(colourCount(filled, CHALLENGE_EDGE_COLOR)).toBeGreaterThan(100)
  })

  it('draws the tick as one closed outline, because two strokes would cancel where they meet', () => {
    expect(CHALLENGE_CHECK_GLYPH).toHaveLength(1)
  })

  it('registers two images under ids of its own, away from the waypoints', () => {
    expect(CHALLENGE_ICON_ID).not.toBe(CHALLENGE_TAGGED_ICON_ID)
    for (const id of [CHALLENGE_ICON_ID, CHALLENGE_TAGGED_ICON_ID]) {
      expect(id.startsWith('poi-')).toBe(false)
    }
  })
})
