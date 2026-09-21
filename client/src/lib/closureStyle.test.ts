import { describe, it, expect } from 'vitest'
import { createExpression, latest } from '@maplibre/maplibre-gl-style-spec'
import {
  CLOSURE_CASING_COLOR,
  CLOSURE_COLOR,
  CLOSURE_DASH,
  CLOSURE_DASH_OVERVIEW_SCALE,
  CLOSURE_LAYER_ID,
  CLOSURE_OUTLINE_WIDTH,
  CLOSURE_OVERVIEW_DASH,
  CLOSURE_TAPE_FAR_WIDTH,
  CLOSURE_TAPE_FULL_WIDTH_ZOOM,
  CLOSURE_TAPE_NEAR_MIN_ZOOM,
  CLOSURE_TAPE_WIDTH,
  buildClosureLayers,
  closureCasingId,
  closureGroundId,
  dashArray,
  dashRedFraction,
  scaleDash,
} from './closureStyle'
import {
  buildMapStyle,
  BLAZE_LINE_WIDTH,
  CASING_LINE_WIDTH,
  BLAZE_LAYER_ID,
} from '../map/style'

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

/** The same, for the band's `line-dasharray` step. */
function dashAt(paint: Record<string, unknown>, zoom: number): number[] {
  const compiled = createExpression(
    paint['line-dasharray'] as never,
    latest.paint_line['line-dasharray'] as never,
  )
  if (compiled.result === 'error') {
    throw new Error('line-dasharray is not a valid expression')
  }
  return [...(compiled.value.evaluate({ zoom }, {} as never) as number[])]
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
// THE QUESTIONS HAVE OUTLIVED THREE SPELLINGS OF THE MARK, which is the
// point of writing them as questions. These cases were first asked of a
// dashed line over a solid casing; then of barrier tape, where they asked
// about a `line-pattern`; and now of a barred band again, where they ask
// about a dasharray once more. lib/closureStyle.ts's header has all three
// and why each one ended. What has not moved is what is being asked: is a
// closure wider than any blaze, does it carry a harder edge, does it have a
// texture where a blaze has none, and do at least two of those survive with
// hue removed.

/** The blaze layer's own paint, read out of the real style rather than
 *  described here - the texture claims below are about what actually ships. */
function blazePaint(): Record<string, unknown> {
  const layer = buildMapStyle({
    topoArchiveUrl: 'pmtiles://ourhike-corridor',
    trailsUrl: '/data/trails.geojson',
  }).layers.find((l) => l.id === BLAZE_LAYER_ID)

  return (layer?.paint ?? {}) as Record<string, unknown>
}

/** The three layers one closure source produces, and the paint of one of
 *  them by position - the outline is index 0, the paper 1 and the ticks 2,
 *  which buildClosureLayers' first case below is what holds. */
const LAYERS = buildClosureLayers('closures', { ground: '#ffffff' })
const paintAt = (index: number): Record<string, unknown> =>
  (LAYERS[index] as { paint: Record<string, unknown> }).paint

describe('closure vs blaze, as structural difference', () => {
  it('draws a closure markedly wider than any blaze', () => {
    // BLAZE_LINE_WIDTH is the WIDEST blaze on the map, not one of them, so
    // this holds against the centerline rather than against a side trail.
    // Widening the AT line therefore has to widen the band with it, and this
    // is the test that says so.
    expect(CLOSURE_TAPE_WIDTH).toBeGreaterThan(BLAZE_LINE_WIDTH * 2)
    // At the bottom of the taper too, which is where a closure is hardest to
    // see and where a band that had quietly narrowed would say least.
    expect(CLOSURE_TAPE_FAR_WIDTH).toBeGreaterThan(BLAZE_LINE_WIDTH * 2)
  })

  it('gives a closure a harder edge than a blaze gets', () => {
    // Measured as the dark edge each mark carries beyond its own colour,
    // which is what actually reads as weight on screen. The closure's edge
    // has been three things - a casing under the whole band, then an outline
    // on every stripe, now a casing under the whole band again - and this
    // comparison is the one that had to be re-checked each time rather than
    // assumed.
    const blazeOverhang = (CASING_LINE_WIDTH - BLAZE_LINE_WIDTH) / 2

    expect(CLOSURE_OUTLINE_WIDTH).toBeGreaterThan(blazeOverhang)
  })

  it('textures a closure where every blaze is drawn solid', () => {
    // Having a texture against having none - a stronger difference than two
    // rhythms to tell apart, and one that cannot drift by someone editing a
    // number. Read off the shipped style so it fails if a dash or a pattern
    // is ever introduced on the trail lines.
    //
    // A BLAZE IS SOLID UNDER THE HUES, which is the appearance this reads:
    // the default sheet dashes its context trails (#1588), so the claim is
    // about the trail line a hiker takes, and blazePaint builds with no
    // appearance at all.
    const paint = blazePaint()

    expect(paint['line-dasharray']).toBeUndefined()
    expect(paint['line-pattern']).toBeUndefined()
    // And the closure has one, which is the other half of the sentence.
    expect(paintAt(2)['line-dasharray']).toBeDefined()
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
    const differsOnTexture = blazePaint()['line-dasharray'] === undefined

    expect(
      [differsOnWidth, differsOnTexture].filter(Boolean).length,
    ).toBeGreaterThanOrEqual(2)
  })
})

describe('how much of the band is red', () => {
  it('puts down about two fifths, which is where the maintainer moved it', () => {
    // A RANGE THAT MOVED TWICE, and the moves are the thing worth reading.
    // It asserted UNDER a half until #1598, and the comment called that "the
    // direction this treatment was asked for in": the 2026-08-27 band was
    // 100% opaque along its length - 59% red, 41% near-black casing showing
    // through the bars - and less red was the answer to it.
    //
    // The maintainer read 28% on the map and asked for the opposite:
    // "the closures are not easily visible". It went to 51%, photographed as
    // ropes at Bear Mountain, and came back to 41% on 2026-09-21.
    //
    // The two directions are about different marks, and #1575 is what
    // separates them: the not-red part of this band is the sheet's own paper
    // now, not the darkest ink on the sheet.
    //
    // Bounded on both sides, still, and for the reason the second bound
    // always had: a band at 100% red is a solid line, which is the one thing
    // a closure may not look like (the blaze comparisons above).
    expect(dashRedFraction(CLOSURE_DASH)).toBeCloseTo(0.407, 2)
    expect(dashRedFraction(CLOSURE_DASH)).toBeGreaterThan(0.35)
    expect(dashRedFraction(CLOSURE_DASH)).toBeLessThan(0.55)
  })

  it('is the same red at both rhythms, so the overview band makes no softer claim', () => {
    // The whole point of scaling BOTH numbers (CLOSURE_DASH_OVERVIEW_SCALE).
    // Scaling only the gap would thin the overview band's red, and a closure
    // would quietly look less closed at the zoom where it is hardest to see -
    // the same argument lib/atcUpdateStyle.ts makes for its slower rhythm,
    // run the other way.
    expect(dashRedFraction(CLOSURE_OVERVIEW_DASH)).toBeCloseTo(
      dashRedFraction(CLOSURE_DASH),
      10,
    )
    expect(CLOSURE_OVERVIEW_DASH).toEqual(
      scaleDash(CLOSURE_DASH, CLOSURE_DASH_OVERVIEW_SCALE),
    )
  })

  it('lands the tick on the weight the tape\u2019s own stripe carried', () => {
    // The rebuild changed the mark's ANGLE and not its weight, and this is
    // that claim as a number. The tape's stripe was 4 px measured across a
    // 55-degree lean, which covers 4 / sin(55) = 4.9 px ALONG the line; the
    // tick is square, so it covers its own length. At the full width the two
    // are the same ink.
    const tickPx = CLOSURE_DASH.tick * CLOSURE_TAPE_WIDTH

    expect(tickPx).toBeCloseTo(4 / Math.sin((55 * Math.PI) / 180), 1)
  })
})

describe('the two rhythms and where the band swaps between them', () => {
  it('swaps where the shortest closure on the map first clears one near pitch', () => {
    // The arithmetic the step zoom is derived from, re-run here rather than
    // trusted: a rhythm says nothing about a line shorter than one of its
    // pitches. OPRHP's shortest closed run is 1.1 km, and at latitude 41 a
    // zoom covers 117,610 / 2^z metres per pixel - so the run is 2.4 px at
    // z8 and 19.2 px at z11, first clearing the near pitch between z10 and
    // z11.
    //
    // This was POI_PIN_MIN_ZOOM's 9 until #1590 moved the seam to 7, which
    // would have left three zooms drawing the near rhythm over closures two
    // to ten pixels long. The tie to the seam was a convenience; this is the
    // reason, so this is what the constant follows.
    const SHORTEST_CLOSED_RUN_M = 1100
    const metresPerPixel = (zoom: number) => 117610 / 2 ** zoom
    const runInPixels = (zoom: number) => SHORTEST_CLOSED_RUN_M / metresPerPixel(zoom)
    const pitchPx = (CLOSURE_DASH.tick + CLOSURE_DASH.gap) * CLOSURE_TAPE_WIDTH

    expect(runInPixels(CLOSURE_TAPE_NEAR_MIN_ZOOM)).toBeGreaterThan(pitchPx)
    expect(runInPixels(CLOSURE_TAPE_NEAR_MIN_ZOOM - 1)).toBeLessThan(pitchPx)
  })

  it('steps the dasharray at that zoom and nowhere else', () => {
    // Read by EVALUATING the step through MapLibre's own engine rather than
    // by matching an expression's shape, which passes on an expression that
    // is valid and wrong.
    const band = paintAt(2)

    for (const zoom of [0, 7, 9, CLOSURE_TAPE_NEAR_MIN_ZOOM - 1]) {
      expect(dashAt(band, zoom), `z${zoom}`).toEqual(dashArray(CLOSURE_OVERVIEW_DASH))
    }
    for (const zoom of [CLOSURE_TAPE_NEAR_MIN_ZOOM, 13, 16, 22]) {
      expect(dashAt(band, zoom), `z${zoom}`).toEqual(dashArray(CLOSURE_DASH))
    }
  })
})

describe('buildClosureLayers', () => {
  const layers = LAYERS

  it('draws the ticks over the paper over an outline, and nothing else between them', () => {
    // THREE LAYERS AND ALL OF THEM PLAIN LINES (#1599). The order is the
    // claim: an outline that drew over the paper would be a bar across the
    // band, and paper over the ticks would be no mark at all. There is no
    // fourth layer, because the thing a fourth would be for - a texture - is
    // what tore at every bend.
    expect(layers.map((l) => l.id)).toEqual([
      closureCasingId(CLOSURE_LAYER_ID),
      closureGroundId(CLOSURE_LAYER_ID),
      CLOSURE_LAYER_ID,
    ])
    for (const layer of layers) {
      expect((layer.paint as Record<string, unknown>)['line-pattern']).toBeUndefined()
    }
  })

  it('shows the outline as an edge and never as a band of its own', () => {
    // The old objection to a casing under a band, made into a number: the
    // outline may only ever be what shows PAST the opaque paper, so its
    // width is the band's plus twice CLOSURE_OUTLINE_WIDTH and not a pixel
    // more. Compared at both ends of the taper, because a widened stop on
    // one and not the other is exactly how an outline turns into a rope.
    const casing = paintAt(0)
    const ground = paintAt(1)

    for (const zoom of [CLOSURE_TAPE_NEAR_MIN_ZOOM, CLOSURE_TAPE_FULL_WIDTH_ZOOM]) {
      expect(
        evaluateZoom(casing['line-width'], zoom) -
          evaluateZoom(ground['line-width'], zoom),
      ).toBeCloseTo(CLOSURE_OUTLINE_WIDTH * 2, 10)
    }
    expect(casing['line-color']).toBe(CLOSURE_CASING_COLOR)
    expect(casing['line-dasharray']).toBeUndefined()
  })

  it('runs the paper the whole length, which is what stops it being a railway', () => {
    // The 2026-08-27 band drew red ticks over a SOLID casing, so 41% of its
    // length was the darkest ink on the sheet and it read as a railway. The
    // ticks here are square too; what makes this a different mark is that the
    // layer under them is the sheet's paper, unbroken, and the casing is
    // reachable only at the two edges.
    const ground = paintAt(1)

    expect(ground['line-dasharray']).toBeUndefined()
    expect(ground['line-color']).toBe('#ffffff')
    expect(evaluateZoom(ground['line-width'], 13)).toBeCloseTo(CLOSURE_TAPE_WIDTH, 10)
  })

  it('grows the band with the zoom, and never shrinks it as a hiker zooms in', () => {
    // "Readily apparent at all the zoom levels" (the maintainer, 2026-09-20)
    // as a property rather than two numbers: the band is monotonic across
    // every zoom the map draws, so no camera move can make a closure lighter.
    const band = paintAt(2)['line-width']
    const widths = [0, 4, 7, 9, 11, 12, 13, 16, 20].map((z) => evaluateZoom(band, z))

    expect(widths).toEqual([...widths].sort((a, b) => a - b))
    expect(evaluateZoom(band, 8)).toBeCloseTo(CLOSURE_TAPE_FAR_WIDTH, 10)
    expect(evaluateZoom(band, 16)).toBeCloseTo(CLOSURE_TAPE_WIDTH, 10)
  })

  it('draws all three at one width, so the edge cannot drift off the band', () => {
    // The paper and the ticks share a width exactly; the outline is that
    // width plus its two edges. Held at both stops because one taper edited
    // and not the others is how a band and its ground come apart.
    for (const zoom of [8, 12, 16]) {
      expect(evaluateZoom(paintAt(1)['line-width'], zoom)).toBe(
        evaluateZoom(paintAt(2)['line-width'], zoom),
      )
    }
  })

  it('reads from the source it was given', () => {
    expect(layers.every((l) => 'source' in l && l.source === 'closures')).toBe(true)
  })

  it('paints the paper it was given, and a night build asks for its own (#1575)', () => {
    // One ground per sheet paper: a night build asks for the night paper, and
    // the two are never the same colour. It was an image id until #1599 and
    // is a `line-color` now, which is what lets map/style.ts repaint it on a
    // sheet change rather than re-point it.
    const night = buildClosureLayers('closures', { ground: '#0c1410' })

    expect((night[1] as { paint: Record<string, unknown> }).paint['line-color']).toBe(
      '#0c1410',
    )
    expect(paintAt(1)['line-color']).toBe('#ffffff')
  })

  it('does not data-drive colour off blaze_color - a closure is not a blaze', () => {
    // Guards against someone reusing the blaze match expression here for
    // consistency's sake, which would make a closure inherit a trail's hue.
    // Every colour in these three layers is a literal: the closure red, the
    // sheet's darkest ink, and the paper the caller passed.
    expect(JSON.stringify(layers)).not.toContain('blaze_color')
    expect(paintAt(2)['line-color']).toBe(CLOSURE_COLOR)
  })

  it('keeps the closure red as the band colour, wherever it is now drawn', () => {
    // The hue did not change and must not: lib/atcUpdateStyle.ts still reads
    // it so the two feeds cannot drift into two severities.
    expect(CLOSURE_COLOR).toBe('#b2321f')
  })
})
