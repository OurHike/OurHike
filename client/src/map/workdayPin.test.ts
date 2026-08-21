import { describe, it, expect } from 'vitest'
import { POI_COLORS, PIN_HALO_COLOR, POI_PIN_SIZE, poiGlyphPath } from './poiIcons'
import { WARNING_PIN } from '../lib/seriousWarnings'
import {
  WORKDAY_COLOR,
  WORKDAY_GLYPH,
  WORKDAY_ICON_ID,
  buildWorkdayIcon,
} from './workdayPin'

// The workday pin (#760). warningPin.test.ts's posture: the two things this
// pin claims about itself - that it clears the contrast bar, and that it is
// not another pin wearing a different colour - are COMPUTED here rather than
// asserted in prose, because both are the kind of claim that reads as true
// right up until somebody looks at a real screen in real sun.

/** WCAG relative luminance. */
function luminance(hex: string): number {
  const channel = (value: number) => {
    const c = value / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  const int = Number.parseInt(hex.replace('#', ''), 16)
  return (
    0.2126 * channel((int >> 16) & 255) +
    0.7152 * channel((int >> 8) & 255) +
    0.0722 * channel(int & 255)
  )
}

function contrast(a: string, b: string): number {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (light + 0.05) / (dark + 0.05)
}

/** Hue in degrees, for the "not a second orange" check. */
function hue(hex: string): number {
  const int = Number.parseInt(hex.replace('#', ''), 16)
  const [r, g, b] = [
    ((int >> 16) & 255) / 255,
    ((int >> 8) & 255) / 255,
    (int & 255) / 255,
  ]
  const max = Math.max(r, g, b)
  const min = Math.min(r, g, b)
  if (max === min) return 0
  const d = max - min
  const raw =
    max === r ? ((g - b) / d) % 6 : max === g ? (b - r) / d + 2 : (r - g) / d + 4
  return (raw * 60 + 360) % 360
}

/** The shorter way round the wheel. */
function hueGap(a: string, b: string): number {
  const raw = Math.abs(hue(a) - hue(b))
  return Math.min(raw, 360 - raw)
}

describe('the workday pin’s colour', () => {
  it('clears WCAG AA against the halo drawn on top of it', () => {
    // The bar FEATURES.md's waypoint icon spec sets for every accent, and the
    // one poiIcons.test.ts already computes for the eight.
    expect(contrast(WORKDAY_COLOR, PIN_HALO_COLOR)).toBeGreaterThanOrEqual(4.5)
  })

  it('is nobody else’s hue, including the closure red', () => {
    // poiIcons.ts's "one colour in glare" failure: two accents a degree apart
    // are one accent to a hiker squinting at a wet screen, and colour is the
    // channel that fails first.
    const taken = { ...POI_COLORS, warning: WARNING_PIN.color }
    for (const [name, color] of Object.entries(taken)) {
      expect(
        hueGap(WORKDAY_COLOR, color),
        `${name} (${color}) is only ${Math.round(hueGap(WORKDAY_COLOR, color))}° away`,
      ).toBeGreaterThan(30)
    }
  })
})

describe('the workday glyph', () => {
  it('is one ring, because two would punch a hole through the hat', () => {
    // The rasteriser fills even-odd. A dome ring overlapping a brim ring
    // would cancel where they overlap, which is the middle of the hat.
    expect(WORKDAY_GLYPH).toHaveLength(1)
  })

  it('is wider than it is tall, which no waypoint glyph is', () => {
    const xs = WORKDAY_GLYPH[0].map(([x]) => x)
    const ys = WORKDAY_GLYPH[0].map(([, y]) => y)
    const width = Math.max(...xs) - Math.min(...xs)
    const height = Math.max(...ys) - Math.min(...ys)

    // The silhouette claim in the module header, measured. Shape is the
    // primary channel; this is the part of the shape that carries it.
    expect(width).toBeGreaterThan(height)
  })

  it('is not one of the waypoint silhouettes redrawn', () => {
    const hat = WORKDAY_GLYPH[0].map(([x, y]) => `${x},${y}`).join(' ')
    for (const type of Object.keys(POI_COLORS)) {
      expect(poiGlyphPath(type)).not.toBe(hat)
    }
  })

  it('sits flat along the bottom of the box', () => {
    const brim = WORKDAY_GLYPH[0].filter(([, y]) => y === 0.78)

    // Two corners at the same y is what makes a brim a brim rather than a
    // dome sitting on a point.
    expect(brim).toHaveLength(2)
  })
})

describe('the workday pin image', () => {
  it('is the waypoint pin at the waypoint size, not a bigger one', () => {
    const icon = buildWorkdayIcon(POI_PIN_SIZE, 2)

    // An invitation drawn larger than a shelter would be claiming a priority
    // over the hiker's own trail that this feature does not have.
    expect(icon.width).toBe(POI_PIN_SIZE * 2)
    expect(icon.height).toBe(POI_PIN_SIZE * 2)
    expect(WORKDAY_ICON_ID.startsWith('poi-')).toBe(false)
  })

  it('draws something in the middle of the disc', () => {
    const icon = buildWorkdayIcon(POI_PIN_SIZE, 2)
    const middle = ((icon.height / 2) * icon.width + icon.width / 2) * 4

    // The alpha channel at the centre. A glyph that rasterised to nothing
    // would still produce a perfectly plausible coloured disc.
    expect(icon.data[middle + 3]).toBeGreaterThan(0)
  })
})
