import { describe, it, expect } from 'vitest'
import { createExpression, latest } from '@maplibre/maplibre-gl-style-spec'
import {
  CLOSURE_CASING_COLOR,
  CLOSURE_TAPE_WIDTH,
  CLOSURE_TAPE_FAR_WIDTH,
  CLOSURE_TAPE_FULL_WIDTH_ZOOM,
  CLOSURE_TAPE_OVERVIEW_CADENCE,
  CLOSURE_TAPE_OVERVIEW_EDGE,
  CLOSURE_TAPE_OVERVIEW_MAX_ZOOM,
  CLOSURE_OUTLINE_WIDTH,
  CLOSURE_STRIPE_EDGE,
  CLOSURE_TAPE_CADENCE,
  CLOSURE_TAPE_IMAGE_ID,
  CLOSURE_TAPE_PIXEL_RATIO,
  closureCasingId,
  closureTapeImageId,
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
import { POI_PIN_MIN_ZOOM } from '../map/poiLayers'

/** A zoom-dependent paint value, as MapLibre's own engine resolves it at
 *  `zoom` - compiled against the real `line-width` spec, so a taper this
 *  file reads is a taper the map would draw. The alternative is matching an
 *  expression's shape, which passes on an expression that is valid and
 *  wrong. */
function evaluateZoom(value: unknown, zoom: number): number {
  const compiled = createExpression(
    value as never,
    latest.paint_line['line-width'] as never,
  )
  if (compiled.result === 'error') throw new Error('line-width is not a valid expression')
  return compiled.value.evaluate({ zoom }, {} as never) as number
}

/** The same, for the band's `line-pattern` step. `resolvedImage` evaluates
 *  to an object, so it is named rather than compared directly. */
function patternAt(paint: Record<string, unknown>, zoom: number): string {
  const compiled = createExpression(
    paint['line-pattern'] as never,
    latest.paint_line['line-pattern'] as never,
  )
  if (compiled.result === 'error') {
    throw new Error('line-pattern is not a valid expression')
  }
  return String(compiled.value.evaluate({ zoom }, {} as never))
}

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

describe('how much of the tape is red', () => {
  it('puts down about half, which is where the maintainer moved it on 2026-09-20', () => {
    // A RANGE THAT MOVED, and the move is the thing worth reading. Until
    // #1598 this asserted UNDER a half, and the comment called that "the
    // direction this treatment was asked for in": the band before the tape
    // was 100% opaque along its length - 59% red, 41% near-black casing
    // showing through the bars - and less red was the answer to it.
    //
    // The maintainer read 28% on the map and asked for the opposite:
    // "the closures are not easily visible". The two directions are about
    // different marks, and #1575 is what separates them - the not-red half
    // of this tape is the sheet's own paper now, not the darkest ink on the
    // sheet. So half red on white is not a return to the black rope with
    // red ticks; it is the barrier that mark was trying to be.
    //
    // Bounded on both sides, still, and for the reason the second bound
    // always had: a tape at 100% red is a solid line, which is the one
    // thing a closure may not look like (the blaze comparisons above).
    expect(tapeRedFraction(CLOSURE_TAPE_CADENCE)).toBeGreaterThan(0.4)
    expect(tapeRedFraction(CLOSURE_TAPE_CADENCE)).toBeLessThan(0.6)
  })

  it('is the same red at both cadences, so the overview tape makes no softer claim', () => {
    // The whole point of scaling BOTH axes (CLOSURE_TAPE_OVERVIEW_SCALE).
    // Scaling only the pitch would thin the overview tape's red to a third,
    // and a closure would quietly look less closed at the zoom where it is
    // hardest to see - the same argument lib/atcUpdateStyle.ts makes for its
    // doubled tape, run the other way.
    expect(tapeRedFraction(CLOSURE_TAPE_OVERVIEW_CADENCE)).toBeCloseTo(
      tapeRedFraction(CLOSURE_TAPE_CADENCE),
      10,
    )
  })

  it('halves the pitch at the overview, so a 1.5 km closure has to cross a stripe', () => {
    // The measurement #1598 exists for, as arithmetic rather than a frame.
    // OPRHP's closed runs are 1.1 to 1.9 km; at latitude 41 that is 3 to 7
    // px at z8. A run shorter than one pitch can land entirely between two
    // stripes and draw as a blank slab of paper, so the pitch is the length
    // a closure must reach before the tape is guaranteed to say anything.
    expect(CLOSURE_TAPE_OVERVIEW_CADENCE.pitch).toBeLessThan(CLOSURE_TAPE_CADENCE.pitch)
    // 7 px is the longest of those runs at z8. Held as the number it is,
    // rather than as "small", so a pitch edited back up fails here.
    expect(CLOSURE_TAPE_OVERVIEW_CADENCE.pitch).toBeLessThanOrEqual(7)
  })

  it('tiles without a seam at the pixel ratio it is drawn at, at both cadences', () => {
    // map/closureTape.ts makes the image exactly one pitch wide, so a pitch
    // that is not a whole number of image pixels rounds - and a rounded tile
    // repeats at the wrong length, which shows as a stutter every few stripes.
    // Cheap to hold here, invisible until somebody photographs it. Both
    // cadences since #1598: halving a pitch is exactly the edit that can put
    // a half pixel into the second one.
    for (const cadence of [CLOSURE_TAPE_CADENCE, CLOSURE_TAPE_OVERVIEW_CADENCE]) {
      const pixels = cadence.pitch * CLOSURE_TAPE_PIXEL_RATIO
      expect(pixels).toBe(Math.round(pixels))
      const stripePixels = cadence.stripe * CLOSURE_TAPE_PIXEL_RATIO
      expect(stripePixels).toBe(Math.round(stripePixels))
    }
  })
})

describe('the two cadences and where the band swaps between them', () => {
  it('swaps at the seam, which is where the map’s own closure layers hand over', () => {
    // map/style.ts caps the network overview's band at POI_PIN_MIN_ZOOM and
    // starts the nearby network's there. Any zoom at which the cadence
    // changes will show the change, so it is spent at the one where every
    // other layer is changing too - and this is what stops the two nines
    // drifting apart, since lib/ cannot import the seam without dragging
    // map/poiLayers.ts in behind it.
    expect(CLOSURE_TAPE_OVERVIEW_MAX_ZOOM).toBe(POI_PIN_MIN_ZOOM)
  })

  it('keeps the same share of ink at both cadences, so the overview tape does not merge', () => {
    // The arithmetic CLOSURE_TAPE_OVERVIEW_EDGE exists for. Ink is the
    // stripe plus its two edges, and at a halved pitch an unhalved edge puts
    // it over 100% - neighbouring stripes meet, the paper between them
    // disappears, and the overview tape draws as one flat dark-red band that
    // says "closed" no more clearly than a red line does.
    const ink = (cadence: { stripe: number; pitch: number }, edge: number) =>
      tapeRedFraction({ stripe: cadence.stripe + edge * 2, pitch: cadence.pitch })

    expect(ink(CLOSURE_TAPE_OVERVIEW_CADENCE, CLOSURE_TAPE_OVERVIEW_EDGE)).toBeCloseTo(
      ink(CLOSURE_TAPE_CADENCE, CLOSURE_STRIPE_EDGE),
      10,
    )
    expect(ink(CLOSURE_TAPE_OVERVIEW_CADENCE, CLOSURE_TAPE_OVERVIEW_EDGE)).toBeLessThan(1)
    // What it would have been with the edge left alone, so the failure this
    // guards against is visible rather than described.
    expect(ink(CLOSURE_TAPE_OVERVIEW_CADENCE, CLOSURE_STRIPE_EDGE)).toBeGreaterThan(1)
  })
})

describe('buildClosureLayers', () => {
  const layers = buildClosureLayers('closures', { ground: '#ffffff' })
  /** The paint of one of the pair, by position - the outline is index 0 and
   *  the band index 1, which the first case below is what holds. */
  const paintAt = (index: number): Record<string, unknown> =>
    (layers[index] as { paint: Record<string, unknown> }).paint

  it('draws the band over an outline, and nothing else between them', () => {
    // TWO LAYERS SINCE #1598, WHERE THIS ASSERTED ONE. The one-layer rule
    // was about a casing showing through TRANSPARENT gaps, which is the
    // defect the tape replaced; #1575 filled the gaps with the sheet's own
    // paper, so a line under the band can only appear at its two edges.
    // What this holds now is the ordering that keeps that true: the outline
    // is first, so it is painted under, and the paper under-band is still in
    // the image rather than a third layer.
    expect(layers.map((l) => l.id)).toEqual([
      closureCasingId(CLOSURE_LAYER_ID),
      CLOSURE_LAYER_ID,
    ])
  })

  it('shows the outline as an edge and never as a band of its own', () => {
    // The old objection, made into a number: the outline may only ever be
    // what shows PAST the opaque band, so its width is the band's plus twice
    // CLOSURE_OUTLINE_WIDTH and not a pixel more. Compared at both ends of
    // the taper, because a widened stop on one and not the other is exactly
    // how an outline turns into a rope.
    const widthAt = (paint: Record<string, unknown>, zoom: number) =>
      evaluateZoom(paint['line-width'], zoom)
    const casing = paintAt(0)
    const band = paintAt(1)

    for (const zoom of [CLOSURE_TAPE_OVERVIEW_MAX_ZOOM, CLOSURE_TAPE_FULL_WIDTH_ZOOM]) {
      expect(widthAt(casing, zoom) - widthAt(band, zoom)).toBeCloseTo(
        CLOSURE_OUTLINE_WIDTH * 2,
        10,
      )
    }
    expect(casing['line-color']).toBe(CLOSURE_CASING_COLOR)
    expect(casing['line-pattern']).toBeUndefined()
  })

  it('grows the band with the zoom, and never shrinks it as a hiker zooms in', () => {
    // "Readily apparent at all the zoom levels" (the maintainer, 2026-09-20)
    // as a property rather than two numbers: the band is monotonic across
    // every zoom the map draws, so no camera move can make a closure lighter.
    const band = paintAt(1)['line-width']
    const widths = [0, 4, 8, 9, 11, 13, 16, 20].map((z) => evaluateZoom(band, z))

    expect(widths).toEqual([...widths].sort((a, b) => a - b))
    expect(evaluateZoom(band, 8)).toBeCloseTo(CLOSURE_TAPE_FAR_WIDTH, 10)
    expect(evaluateZoom(band, 16)).toBeCloseTo(CLOSURE_TAPE_WIDTH, 10)
  })

  it('reads from the source it was given', () => {
    expect(layers.every((l) => 'source' in l && l.source === 'closures')).toBe(true)
  })

  it('paints the band with the tape image rather than a flat colour, at each zoom’s cadence', () => {
    const paint = paintAt(1)

    // The overview tape below the seam and the near one from it in (#1598),
    // read by evaluating the step rather than by matching its shape.
    expect(patternAt(paint, 8)).toBe(closureTapeImageId('#ffffff', 'overview'))
    expect(patternAt(paint, CLOSURE_TAPE_OVERVIEW_MAX_ZOOM)).toBe(
      closureTapeImageId('#ffffff', 'near'),
    )
    expect(patternAt(paint, 16)).toBe(closureTapeImageId('#ffffff', 'near'))
    expect(evaluateZoom(paint['line-width'], 16)).toBeCloseTo(CLOSURE_TAPE_WIDTH, 10)
  })

  it('points the band at the tape drawn on the paper it was given (#1575)', () => {
    // One image per sheet paper, named from the stem: a night build asks for
    // the night tape, and the two are never the same image. Both cadences,
    // since a sheet change that swapped only one of them would draw the day
    // tape at the opening camera on a night sheet.
    const night = (
      buildClosureLayers('closures', { ground: '#0c1410' })[1] as {
        paint: Record<string, unknown>
      }
    ).paint

    for (const zoom of [8, 16]) {
      expect(patternAt(night, zoom)).not.toBe(patternAt(paintAt(1), zoom))
      expect(String(patternAt(night, zoom))).toContain('0c1410')
      expect(String(patternAt(night, zoom)).startsWith(CLOSURE_TAPE_IMAGE_ID)).toBe(true)
    }
  })

  it('does not data-drive colour off blaze_color - a closure is not a blaze', () => {
    // Guards against someone reusing the blaze match expression here for
    // consistency's sake, which would make a closure inherit a trail's hue.
    // Stronger than it was: with the red baked into the image there is no
    // `line-color` on the band at all, so the check is that none appeared.
    // The outline under it has one, and it is the sheet's darkest ink -
    // a constant, never anything read off a feature.
    const paint = paintAt(1)

    expect(paint['line-color']).toBeUndefined()
    expect(JSON.stringify(layers)).not.toContain('blaze_color')
  })

  it('keeps the closure red as the tape colour, wherever it is now drawn', () => {
    // The hue did not change and must not: the constant is still the one
    // map/closureTape.ts rasterises, and lib/atcUpdateStyle.ts still reads it
    // so the two feeds cannot drift into two severities.
    expect(CLOSURE_COLOR).toBe('#b2321f')
  })
})
