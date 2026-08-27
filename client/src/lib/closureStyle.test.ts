import { describe, it, expect } from 'vitest'
import {
  CLOSURE_TAPE_WIDTH,
  CLOSURE_STRIPE_EDGE,
  CLOSURE_TAPE_CADENCE,
  CLOSURE_TAPE_IMAGE_ID,
  CLOSURE_TAPE_PIXEL_RATIO,
  CLOSURE_COLOR,
  buildClosureLayers,
  tapeRedFraction,
  CLOSURE_LAYER_ID,
} from './closureStyle'
import {
  buildMapStyle,
  BLAZE_LINE_WIDTH,
  CASING_LINE_WIDTH,
  BLAZE_LAYER_ID,
} from '../map/style'

// WIREFRAMES.md §7 and its Load-bearing values: a closure is a barrier along
// the trail, a blaze is the trail.
//
// This file exists for one reason. A closure that reads as a red blaze is a
// safety failure - a hiker glancing at a phone in glare would see a side
// trail where the real message is "do not walk down there." So the two
// treatments must differ STRUCTURALLY (width, texture), not only in hue:
// colour alone disappears in greyscale, in sunlight, and for a red-green
// colour-blind hiker, which between them cover a great many of the moments
// this warning matters most.
//
// The band these tests were written against was a dashed line over a solid
// casing, so they asked about a dasharray. It is barrier tape now
// (lib/closureStyle.ts's header has the measurement that ended the band), so
// they ask about a pattern - but they ask the same QUESTIONS, which is the
// part that had to survive the change.

/** The blaze layer's own paint, read out of the real style rather than
 *  described here - the texture claims below are about what actually ships. */
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
    // Widening the AT line therefore has to widen the tape with it, and this
    // is the test that says so.
    expect(CLOSURE_TAPE_WIDTH).toBeGreaterThan(BLAZE_LINE_WIDTH * 2)
  })

  it('gives a closure a harder edge than a blaze gets', () => {
    // Measured as the dark edge each mark carries beyond its own colour, which
    // is what actually reads as weight on screen. The closure's edge used to be
    // a casing line under the whole band; it is now the outline on every
    // stripe, and it is thinner than that casing was - so this comparison is
    // the one that had to be re-checked rather than assumed.
    const blazeOverhang = (CASING_LINE_WIDTH - BLAZE_LINE_WIDTH) / 2

    expect(CLOSURE_STRIPE_EDGE).toBeGreaterThan(blazeOverhang)
  })

  it('textures a closure where every blaze is drawn solid', () => {
    // Having a texture against having none - a stronger difference than two
    // rhythms to tell apart, and one that cannot drift by someone editing a
    // number. Read off the shipped style so it fails if a dash or a pattern is
    // ever introduced on the trail lines.
    const paint = blazePaint()

    expect(paint['line-dasharray']).toBeUndefined()
    expect(paint['line-pattern']).toBeUndefined()
  })

  it('stays distinguishable with hue removed entirely', () => {
    // The greyscale test, made concrete: strip colour and the two must still
    // differ on at least two independent channels.
    //
    // Widened to `number` deliberately. Compared as const literals, tsc
    // narrows these to their exact values and calls the check a tautology -
    // which would make it pass forever, including on the day someone sets the
    // two widths equal. This has to be a runtime comparison to be a guard.
    const closureWidth: number = CLOSURE_TAPE_WIDTH
    const blazeWidth: number = BLAZE_LINE_WIDTH

    const differsOnWidth = closureWidth !== blazeWidth
    const differsOnTexture = blazePaint()['line-pattern'] === undefined

    expect(
      [differsOnWidth, differsOnTexture].filter(Boolean).length,
    ).toBeGreaterThanOrEqual(2)
  })
})

describe('the tape shows more ground than ink', () => {
  it('leaves most of its length transparent', () => {
    // The direction this treatment was asked for in, held as a number rather
    // than as an adjective. The band it replaced was 100% opaque along its
    // whole length - 59% red, 41% casing showing through the bars - so
    // anything under a half here is already a change in kind.
    expect(tapeRedFraction(CLOSURE_TAPE_CADENCE)).toBeLessThan(0.5)
  })

  it('still puts down enough red to read as a barrier', () => {
    // The other side of the same number, and the reason it is a range rather
    // than a ceiling: FEATURES.md's "a confidently wrong prediction is more
    // dangerous than an honest unknown" cuts both ways on a safety mark, and a
    // barrier nobody notices has failed exactly as badly as one nobody trusts.
    expect(tapeRedFraction(CLOSURE_TAPE_CADENCE)).toBeGreaterThan(0.2)
  })

  it('tiles without a seam at the pixel ratio it is drawn at', () => {
    // map/closureTape.ts makes the image exactly one pitch wide, so a pitch
    // that is not a whole number of image pixels rounds - and a rounded tile
    // repeats at the wrong length, which shows as a stutter every few stripes.
    // Cheap to hold here, invisible until somebody photographs it.
    const pixels = CLOSURE_TAPE_CADENCE.pitch * CLOSURE_TAPE_PIXEL_RATIO

    expect(pixels).toBe(Math.round(pixels))
  })
})

describe('buildClosureLayers', () => {
  const layers = buildClosureLayers('closures')

  it('draws the tape as ONE layer, with no casing beneath it', () => {
    // Not tidiness. A casing drawn as a second line under this one would show
    // through every transparent gap in the tape, which is the exact defect the
    // tape replaced - so "one layer" is the fix, and this is where it is held.
    expect(layers).toHaveLength(1)
    expect(layers[0]?.id).toBe(CLOSURE_LAYER_ID)
  })

  it('reads from the source it was given', () => {
    expect(layers.every((l) => 'source' in l && l.source === 'closures')).toBe(true)
  })

  it('paints the band with the tape image rather than a flat colour', () => {
    const paint = layers[0]?.paint as Record<string, unknown>

    expect(paint['line-pattern']).toBe(CLOSURE_TAPE_IMAGE_ID)
    expect(paint['line-width']).toBe(CLOSURE_TAPE_WIDTH)
  })

  it('does not data-drive colour off blaze_color - a closure is not a blaze', () => {
    // Guards against someone reusing the blaze match expression here for
    // consistency's sake, which would make a closure inherit a trail's hue.
    // Stronger than it was: with the red baked into the image there is no
    // `line-color` on this layer at all, so the check is that none appeared.
    const paint = layers[0]?.paint as Record<string, unknown>

    expect(paint['line-color']).toBeUndefined()
    expect(JSON.stringify(paint)).not.toContain('blaze_color')
  })

  it('keeps the closure red as the tape colour, wherever it is now drawn', () => {
    // The hue did not change and must not: the constant is still the one
    // map/closureTape.ts rasterises, and lib/atcUpdateStyle.ts still reads it
    // so the two feeds cannot drift into two severities.
    expect(CLOSURE_COLOR).toBe('#b2321f')
  })
})
