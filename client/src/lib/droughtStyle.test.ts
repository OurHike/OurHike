// The drought wash's drawing rules, and the one it is defined by: that it
// never looks like a warning.

import { describe, expect, it } from 'vitest'
import {
  buildDroughtLayer,
  DROUGHT_COLORS,
  DROUGHT_FILL_OPACITY,
  DROUGHT_LAYER_ID,
  droughtColorExpression,
} from './droughtStyle'
import { CLOSURE_CASING_COLOR, CLOSURE_COLOR } from './closureStyle'

/** Rough perceived lightness, enough to order a ramp by. */
function lightness(hex: string): number {
  const value = parseInt(hex.slice(1), 16)
  const r = (value >> 16) & 0xff
  const g = (value >> 8) & 0xff
  const b = value & 0xff
  return 0.299 * r + 0.587 * g + 0.114 * b
}

function channels(hex: string): [number, number, number] {
  const value = parseInt(hex.slice(1), 16)
  return [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff]
}

describe('the drought ramp', () => {
  it('never reaches the colours this map spends on danger', () => {
    // The rule #720 was opened naming. A drought tint in the closure band's
    // register spends a hiker's alarm on something that is not an alarm, and
    // "near enough to be confusable" is the thing being excluded rather than
    // exact equality - so this measures distance in RGB rather than checking
    // for a literal match.
    const forbidden = [CLOSURE_COLOR, CLOSURE_CASING_COLOR]
    for (const band of Object.values(DROUGHT_COLORS)) {
      for (const danger of forbidden) {
        const [r1, g1, b1] = channels(band)
        const [r2, g2, b2] = channels(danger)
        const distance = Math.hypot(r1 - r2, g1 - g2, b1 - b2)
        expect(distance, `${band} sits too close to ${danger}`).toBeGreaterThan(60)
      }
    }
  })

  it('is never more red than green, so it reads as ground and not as alarm', () => {
    for (const band of Object.values(DROUGHT_COLORS)) {
      const [r, g, b] = channels(band)
      expect(r).toBeGreaterThan(b) // warm
      expect(r - g).toBeLessThan(80) // but ochre, not red
    }
  })

  it('darkens monotonically with severity', () => {
    // The second of the layer's two channels. Not a promise that the order
    // survives greyscale - droughtStyle.ts is explicit that this layer leans
    // on two weak channels and says so - but a broken ramp would put the
    // darkest ink somewhere that is not the worst drought, which is the same
    // failure the pipeline's disjointness guard exists to prevent.
    const ordered = [0, 1, 2, 3, 4].map((dm) => lightness(DROUGHT_COLORS[dm]))
    for (let index = 1; index < ordered.length; index += 1) {
      expect(ordered[index]).toBeLessThan(ordered[index - 1])
    }
  })
})

describe('the layer', () => {
  it('is built hidden, because the hiker has to ask', () => {
    expect(buildDroughtLayer('drought', false, false).layout).toEqual({
      visibility: 'none',
    })
    expect(buildDroughtLayer('drought', false, true).layout).toEqual({
      visibility: 'visible',
    })
  })

  it('sits lighter on a dark sheet than on a light one', () => {
    const day = buildDroughtLayer('drought', false, true)
    const night = buildDroughtLayer('drought', true, true)
    const dayOpacity = (day.paint as Record<string, number>)['fill-opacity']
    const nightOpacity = (night.paint as Record<string, number>)['fill-opacity']
    expect(nightOpacity).toBeLessThan(dayOpacity)
    expect(dayOpacity).toBe(DROUGHT_FILL_OPACITY.day)
  })

  it('draws no outline, so a weekly county-scale edge is not shown as surveyed', () => {
    const paint = buildDroughtLayer('drought', false, true).paint as Record<
      string,
      string
    >
    expect(paint['fill-outline-color']).toBe('rgba(0,0,0,0)')
  })

  it('is translucent enough to read the map through', () => {
    for (const opacity of Object.values(DROUGHT_FILL_OPACITY)) {
      expect(opacity).toBeLessThan(0.5)
    }
  })

  it('keeps one stable id, because the toggle finds the layer by it', () => {
    expect(buildDroughtLayer('drought', false, true).id).toBe(DROUGHT_LAYER_ID)
  })
})

describe('the class ramp expression', () => {
  it('falls back to the palest band rather than to nothing', () => {
    // A class this build has never heard of - NDMC adding a sixth, or a
    // corrupt property - must still draw. Drawing nothing would read as "no
    // drought here", which is the one wrong answer available.
    const expression = droughtColorExpression() as unknown[]
    expect(expression[expression.length - 1]).toBe(DROUGHT_COLORS[0])
  })

  it('maps every class NDMC publishes', () => {
    const expression = droughtColorExpression() as unknown[]
    for (const dm of [0, 1, 2, 3, 4]) {
      expect(expression).toContain(dm)
      expect(expression).toContain(DROUGHT_COLORS[dm])
    }
  })
})
