import { describe, it, expect } from 'vitest'
import {
  ATC_UPDATE_BAR_RHYTHM,
  ATC_UPDATE_CASING_COLOR,
  ATC_UPDATE_CASING_LAYER_ID,
  ATC_UPDATE_CASING_WIDTH,
  ATC_UPDATE_COLOR,
  ATC_UPDATE_HALO_BLUR,
  ATC_UPDATE_HALO_LAYER_ID,
  ATC_UPDATE_HALO_OPACITY,
  ATC_UPDATE_HALO_RADIUS,
  ATC_UPDATE_HALO_SCALE,
  ATC_UPDATE_LAYER_ID,
  ATC_UPDATE_LINE_WIDTH,
  ATC_UPDATE_POINT_DIAMETER,
  ATC_UPDATE_POINT_LAYER_ID,
  ATC_UPDATE_POINT_RADIUS,
  buildAtcUpdateLayers,
} from './atcUpdateStyle'
import {
  CLOSURE_BAR_RHYTHM,
  CLOSURE_CASING_WIDTH,
  CLOSURE_COLOR,
  CLOSURE_LINE_WIDTH,
} from './closureStyle'

// #461 asks that an ATC update not look like an OurHike closure. This file
// holds the half of that answer which is NOT on the canvas, and the reasoning
// is worth restating because the obvious move is the wrong one: two barrier
// colours on a safety map read as two severities, not as two organisations,
// and a hiker who learns one shade of barrier is softer than the other has
// learned something false. Both mean the trail is shut. Whose claim it is
// gets answered where a hiker can read an answer - the banner and the sheet.

function paintOf(id: string): Record<string, unknown> {
  const layer = buildAtcUpdateLayers('atc-updates').find(
    (candidate) => candidate.id === id,
  )
  expect(layer).toBeDefined()
  return (layer as { paint: Record<string, unknown> }).paint
}

describe('an ATC band carries the same weight as a closure', () => {
  it('is exactly as wide', () => {
    // A narrower band would be the severity distinction this module refuses
    // to draw, arrived at by drift rather than by decision.
    expect(ATC_UPDATE_LINE_WIDTH).toBe(CLOSURE_LINE_WIDTH)
    expect(paintOf(ATC_UPDATE_LAYER_ID)['line-width']).toBe(CLOSURE_LINE_WIDTH)
  })

  it('is the same colour', () => {
    expect(ATC_UPDATE_COLOR).toBe(CLOSURE_COLOR)
  })

  it('has the same hard casing, drawn under it', () => {
    expect(ATC_UPDATE_CASING_WIDTH).toBe(CLOSURE_CASING_WIDTH)
    expect(paintOf(ATC_UPDATE_CASING_LAYER_ID)['line-width']).toBe(
      CLOSURE_LINE_WIDTH + CLOSURE_CASING_WIDTH * 2,
    )
  })
})

describe('and is still distinguishable', () => {
  it('runs a different rhythm', () => {
    expect(ATC_UPDATE_BAR_RHYTHM).not.toEqual(CLOSURE_BAR_RHYTHM)
    expect(paintOf(ATC_UPDATE_LAYER_ID)['line-dasharray']).toEqual(ATC_UPDATE_BAR_RHYTHM)
  })

  it('keeps that rhythm barred rather than solid', () => {
    // Still barrier tape, only slower. A solid line is what a trail looks
    // like, and the one thing this must never resemble is a route.
    const [bar, gap] = ATC_UPDATE_BAR_RHYTHM
    expect(bar).toBeGreaterThan(0)
    expect(gap).toBeGreaterThan(0)
  })

  it('reads as the same treatment at a glance', () => {
    // The intended reading order is "barrier" first and "whose" second, so
    // the two rhythms are the same shape at different scales rather than two
    // unrelated patterns.
    const atcRatio = ATC_UPDATE_BAR_RHYTHM[0] / ATC_UPDATE_BAR_RHYTHM[1]
    const closureRatio = CLOSURE_BAR_RHYTHM[0] / CLOSURE_BAR_RHYTHM[1]

    expect(Math.abs(atcRatio - closureRatio)).toBeLessThan(1)
  })
})

describe('the layers themselves', () => {
  it('draws the casing before the band', () => {
    // Otherwise the casing paints over the thing it is meant to outline.
    const ids = buildAtcUpdateLayers('atc-updates').map((layer) => layer.id)

    expect(ids.indexOf(ATC_UPDATE_CASING_LAYER_ID)).toBeLessThan(
      ids.indexOf(ATC_UPDATE_LAYER_ID),
    )
  })

  it('binds them all to the source it was given', () => {
    for (const layer of buildAtcUpdateLayers('atc-updates')) {
      expect((layer as { source: string }).source).toBe('atc-updates')
    }
  })

  it('does not collide with the closure layer ids', () => {
    expect(ATC_UPDATE_LAYER_ID).not.toBe('closure-band')
    expect(ATC_UPDATE_CASING_LAYER_ID).not.toBe('closure-casing')
  })
})

describe('a point notice', () => {
  // Most of what ATC publishes is a single mile marker, and `trailSlice`
  // renders those as a few dozen feet of line - which is not a small band, it
  // is an invisible one. The circle layer is what makes them show up at all.

  it('is far wider than the band, which is what it was not', () => {
    // It used to be exactly half the band's width - "a barrier seen end-on" -
    // and that made the ATC's own word about the trail the smallest mark on a
    // map full of 38px waypoint pins. src/test/atcAlertProminence.test.ts is
    // where that comparison is actually held, against the pins themselves.
    expect(ATC_UPDATE_POINT_DIAMETER).toBeGreaterThan(ATC_UPDATE_LINE_WIDTH)
    expect(ATC_UPDATE_POINT_RADIUS * 2).toBe(ATC_UPDATE_POINT_DIAMETER)
    expect(paintOf(ATC_UPDATE_POINT_LAYER_ID)['circle-radius']).toBe(
      ATC_UPDATE_POINT_RADIUS,
    )
  })

  it('carries the band’s colour and its casing', () => {
    const paint = paintOf(ATC_UPDATE_POINT_LAYER_ID)

    expect(paint['circle-color']).toBe(ATC_UPDATE_COLOR)
    expect(paint['circle-stroke-color']).toBe(ATC_UPDATE_CASING_COLOR)
    expect(paint['circle-stroke-width']).toBe(ATC_UPDATE_CASING_WIDTH)
  })

  it('draws from the same source as the bands', () => {
    // A `line` layer ignores Point features and a `circle` layer ignores
    // lines, so one source carries both - and the tap has one place to look.
    const layers = buildAtcUpdateLayers('atc-updates')

    expect(layers.map((layer) => (layer as { source: string }).source)).toEqual([
      'atc-updates',
      'atc-updates',
      'atc-updates',
      'atc-updates',
    ])
  })

  it('is drawn last, over the bands and over its own glow', () => {
    expect(buildAtcUpdateLayers('atc-updates').map((layer) => layer.id)).toEqual([
      ATC_UPDATE_HALO_LAYER_ID,
      ATC_UPDATE_CASING_LAYER_ID,
      ATC_UPDATE_LAYER_ID,
      ATC_UPDATE_POINT_LAYER_ID,
    ])
  })
})

describe('the glow around a point notice', () => {
  // The half of "more pronounced" that is not size. A dot says where; the glow
  // is what makes an eye that was reading somewhere else look at the dot.

  it('reaches the dot’s own width past it, on every side', () => {
    expect(ATC_UPDATE_HALO_RADIUS).toBe(ATC_UPDATE_POINT_RADIUS * ATC_UPDATE_HALO_SCALE)
    expect(ATC_UPDATE_HALO_RADIUS).toBeGreaterThan(ATC_UPDATE_POINT_RADIUS)
    expect(paintOf(ATC_UPDATE_HALO_LAYER_ID)['circle-radius']).toBe(
      ATC_UPDATE_HALO_RADIUS,
    )
  })

  it('is a gradient with no edge, rather than a translucent disc', () => {
    // `circle-blur: 1` is MapLibre's "only the centerpoint is full opacity",
    // so the alpha ramps to nothing at the rim. Anything less leaves a visible
    // boundary, and a boundary here would be a claim about an area ATC never
    // made - they published a mile marker, not a radius.
    const paint = paintOf(ATC_UPDATE_HALO_LAYER_ID)

    expect(paint['circle-blur']).toBe(1)
    expect(ATC_UPDATE_HALO_BLUR).toBe(1)
    expect(paint['circle-stroke-width']).toBeUndefined()
  })

  it('is transparent, and stays transparent enough to see through', () => {
    // It is drawn over the waypoint pins now (map/style.ts). A glow that hid a
    // water source in order to announce a bear warning nearby would have
    // traded one safety mark for another.
    const opacity = paintOf(ATC_UPDATE_HALO_LAYER_ID)['circle-opacity']

    expect(opacity).toBe(ATC_UPDATE_HALO_OPACITY)
    expect(ATC_UPDATE_HALO_OPACITY).toBeGreaterThan(0)
    expect(ATC_UPDATE_HALO_OPACITY).toBeLessThan(1)
  })

  it('is the band’s red, so the glow is not a second severity', () => {
    expect(paintOf(ATC_UPDATE_HALO_LAYER_ID)['circle-color']).toBe(ATC_UPDATE_COLOR)
  })

  it('is drawn under the band, not over it', () => {
    // A barrier washed in translucent red exactly where a point notice
    // coincides with it is a barrier that has stopped being crisp at the one
    // place it most needs to be.
    const ids = buildAtcUpdateLayers('atc-updates').map((layer) => layer.id)

    expect(ids.indexOf(ATC_UPDATE_HALO_LAYER_ID)).toBeLessThan(
      ids.indexOf(ATC_UPDATE_LAYER_ID),
    )
  })
})
