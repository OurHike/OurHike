import { describe, it, expect } from 'vitest'
import {
  CLOSURE_LINE_WIDTH,
  CLOSURE_CASING_WIDTH,
  CLOSURE_BAR_RHYTHM,
  CLOSURE_COLOR,
  buildClosureLayers,
  CLOSURE_LAYER_ID,
  CLOSURE_CASING_LAYER_ID,
} from './closureStyle'
import { BLAZE_LINE_WIDTH, CASING_LINE_WIDTH, BLAZE_DASH_RHYTHMS } from '../map/style'

// WIREFRAMES.md §7 and its Load-bearing values: "Closure = barred band + hard
// casing; blaze = thin dash + hairline casing."
//
// This file exists for one reason. A closure that reads as a red blaze is a
// safety failure - a hiker glancing at a phone in glare would see a side
// trail where the real message is "do not walk down there." So the two
// treatments must differ STRUCTURALLY (width, rhythm, casing), not only in
// hue: colour alone disappears in greyscale, in sunlight, and for a
// red-green colour-blind hiker, which between them cover a great many of the
// moments this warning matters most.

describe('closure vs blaze, as structural difference', () => {
  it('draws a closure markedly wider than any blaze', () => {
    expect(CLOSURE_LINE_WIDTH).toBeGreaterThan(BLAZE_LINE_WIDTH * 2)
  })

  it('gives a closure a hard casing where a blaze gets a hairline', () => {
    // Measured as the casing's overhang beyond its own line, which is what
    // actually reads as weight on screen.
    const closureOverhang = CLOSURE_CASING_WIDTH
    const blazeOverhang = (CASING_LINE_WIDTH - BLAZE_LINE_WIDTH) / 2

    expect(closureOverhang).toBeGreaterThan(blazeOverhang)
  })

  it('bars a closure on a rhythm no blaze uses', () => {
    const blazeRhythms = Object.values(BLAZE_DASH_RHYTHMS).map((r) => r.join('/'))

    expect(blazeRhythms).not.toContain(CLOSURE_BAR_RHYTHM.join('/'))
  })

  it('stays distinguishable with hue removed entirely', () => {
    // The greyscale test, made concrete: strip colour and the two must still
    // differ on at least two independent channels.
    //
    // Widened to `number` deliberately. Compared as const literals, tsc
    // narrows these to `6` and `2` and calls the check a tautology - which
    // would make it pass forever, including on the day someone sets the two
    // widths equal. This has to be a runtime comparison to be a guard at all.
    const closureWidth: number = CLOSURE_LINE_WIDTH
    const blazeWidth: number = BLAZE_LINE_WIDTH

    const differsOnWidth = closureWidth !== blazeWidth
    const differsOnRhythm =
      CLOSURE_BAR_RHYTHM.join('/') !== BLAZE_DASH_RHYTHMS.Red.join('/')

    expect(
      [differsOnWidth, differsOnRhythm].filter(Boolean).length,
    ).toBeGreaterThanOrEqual(2)
  })
})

describe('buildClosureLayers', () => {
  const layers = buildClosureLayers('closures')

  it('draws the casing beneath the band, never over it', () => {
    const ids = layers.map((l) => l.id)

    expect(ids.indexOf(CLOSURE_CASING_LAYER_ID)).toBeLessThan(
      ids.indexOf(CLOSURE_LAYER_ID),
    )
  })

  it('reads from the source it was given', () => {
    expect(layers.every((l) => 'source' in l && l.source === 'closures')).toBe(true)
  })

  it('paints the band in the closure red', () => {
    const band = layers.find((l) => l.id === CLOSURE_LAYER_ID)
    const paint = band?.paint as Record<string, unknown>

    expect(paint['line-color']).toBe(CLOSURE_COLOR)
  })

  it('bars the band rather than drawing it solid', () => {
    const band = layers.find((l) => l.id === CLOSURE_LAYER_ID)
    const paint = band?.paint as Record<string, unknown>

    expect(paint['line-dasharray']).toBeDefined()
  })

  it('does not data-drive colour off blaze_color - a closure is not a blaze', () => {
    // Guards against someone reusing the blaze match expression here for
    // consistency's sake, which would make a closure inherit a trail's hue.
    const band = layers.find((l) => l.id === CLOSURE_LAYER_ID)
    const paint = band?.paint as Record<string, unknown>

    expect(JSON.stringify(paint['line-color'])).not.toContain('blaze_color')
  })
})
