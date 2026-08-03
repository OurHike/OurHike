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
import {
  buildMapStyle,
  BLAZE_LINE_WIDTH,
  CASING_LINE_WIDTH,
  BLAZE_LAYER_ID,
} from '../map/style'

// WIREFRAMES.md §7 and its Load-bearing values: "Closure = barred band + hard
// casing; blaze = solid line + hairline casing."
//
// This file exists for one reason. A closure that reads as a red blaze is a
// safety failure - a hiker glancing at a phone in glare would see a side
// trail where the real message is "do not walk down there." So the two
// treatments must differ STRUCTURALLY (width, rhythm, casing), not only in
// hue: colour alone disappears in greyscale, in sunlight, and for a
// red-green colour-blind hiker, which between them cover a great many of the
// moments this warning matters most.

/** The blaze layer's own paint, read out of the real style rather than
 *  described here - the rhythm claims below are about what actually ships. */
function blazePaint(): Record<string, unknown> {
  const layer = buildMapStyle({
    topoArchiveUrl: 'pmtiles://ourhike-corridor',
    trailsUrl: '/data/trails.geojson',
  }).layers.find((l) => l.id === BLAZE_LAYER_ID)

  return (layer?.paint ?? {}) as Record<string, unknown>
}

describe('closure vs blaze, as structural difference', () => {
  it('draws a closure markedly wider than any blaze', () => {
    // BLAZE_LINE_WIDTH is the WIDEST blaze on the map, not one of them, so
    // this holds against the centerline rather than against a side trail.
    // Widening the AT line therefore has to widen the closure band with it,
    // and this is the test that says so.
    expect(CLOSURE_LINE_WIDTH).toBeGreaterThan(BLAZE_LINE_WIDTH * 2)
  })

  it('gives a closure a hard casing where a blaze gets a hairline', () => {
    // Measured as the casing's overhang beyond its own line, which is what
    // actually reads as weight on screen.
    const closureOverhang = CLOSURE_CASING_WIDTH
    const blazeOverhang = (CASING_LINE_WIDTH - BLAZE_LINE_WIDTH) / 2

    expect(closureOverhang).toBeGreaterThan(blazeOverhang)
  })

  it('bars a closure where every blaze is drawn solid', () => {
    // This used to compare two dash rhythms, and now compares having one
    // against having none - a stronger difference, and one that cannot drift
    // by someone editing a number. Read off the shipped style so it fails if
    // a dash is ever reintroduced on the trail lines.
    expect(CLOSURE_BAR_RHYTHM.length).toBeGreaterThan(0)
    expect(blazePaint()['line-dasharray']).toBeUndefined()
  })

  it('stays distinguishable with hue removed entirely', () => {
    // The greyscale test, made concrete: strip colour and the two must still
    // differ on at least two independent channels.
    //
    // Widened to `number` deliberately. Compared as const literals, tsc
    // narrows these to their exact values and calls the check a tautology -
    // which would make it pass forever, including on the day someone sets the
    // two widths equal. This has to be a runtime comparison to be a guard.
    const closureWidth: number = CLOSURE_LINE_WIDTH
    const blazeWidth: number = BLAZE_LINE_WIDTH

    const differsOnWidth = closureWidth !== blazeWidth
    const differsOnRhythm = blazePaint()['line-dasharray'] === undefined

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
