import { describe, it, expect } from 'vitest'
import {
  ATC_TAPE_IMAGE_ID,
  ATC_UPDATE_CASING_COLOR,
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
  ATC_UPDATE_TAPE_CADENCE,
  ATC_UPDATE_TAPE_SCALE,
  buildAtcUpdateLayers,
} from './atcUpdateStyle'
import {
  CLOSURE_CASING_WIDTH,
  CLOSURE_COLOR,
  CLOSURE_TAPE_CADENCE,
  CLOSURE_TAPE_IMAGE_ID,
  CLOSURE_TAPE_WIDTH,
  tapeRedFraction,
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

/**
 * A `circle-radius` read at one zoom.
 *
 * The radii are `interpolate` expressions now, so a test that compared the
 * paint value to a number would be asserting the shape of an expression rather
 * than the size of a dot. This evaluates the stops the way MapLibre would -
 * linear between them, clamped outside - which is what lets every case below
 * go on saying what a hiker sees at a given zoom.
 */
function radiusAt(id: string, zoom: number): number {
  const expression = paintOf(id)['circle-radius'] as unknown[]
  expect(expression[0]).toBe('interpolate')
  expect(expression[1]).toEqual(['linear'])
  expect(expression[2]).toEqual(['zoom'])

  const stops: Array<[number, number]> = []
  for (let at = 3; at < expression.length; at += 2) {
    stops.push([expression[at] as number, expression[at + 1] as number])
  }

  const first = stops[0]
  const last = stops[stops.length - 1]
  if (zoom <= first[0]) return first[1]
  if (zoom >= last[0]) return last[1]

  const upper = stops.findIndex(([stopZoom]) => stopZoom >= zoom)
  const [lowZoom, lowValue] = stops[upper - 1]
  const [highZoom, highValue] = stops[upper]
  const t = (zoom - lowZoom) / (highZoom - lowZoom)
  return lowValue + (highValue - lowValue) * t
}

/** The zoom at and above which everything on this map is at full size. */
const WALKING_ZOOM = 13

describe('an ATC band carries the same weight as a closure', () => {
  it('is exactly as wide', () => {
    // A narrower band would be the severity distinction this module refuses
    // to draw, arrived at by drift rather than by decision.
    expect(ATC_UPDATE_LINE_WIDTH).toBe(CLOSURE_TAPE_WIDTH)
    expect(paintOf(ATC_UPDATE_LAYER_ID)['line-width']).toBe(CLOSURE_TAPE_WIDTH)
  })

  it('is the same colour', () => {
    expect(ATC_UPDATE_COLOR).toBe(CLOSURE_COLOR)
  })

  it('lays down the same amount of red', () => {
    // The equality that makes "the same tape, slower" true rather than merely
    // intended. Scaling only the pitch would leave the ATC's band a third as
    // red as a closure's, and a fainter barrier reads as a softer claim -
    // which is the severity distinction this module exists to refuse.
    expect(tapeRedFraction(ATC_UPDATE_TAPE_CADENCE)).toBeCloseTo(
      tapeRedFraction(CLOSURE_TAPE_CADENCE),
      6,
    )
  })

  it('strokes its dot with the closure\u2019s own casing', () => {
    // The one mark in this vocabulary that still has a continuous edge - a
    // point notice is a circle, not tape - so this is where CLOSURE_CASING_WIDTH
    // still does work.
    expect(ATC_UPDATE_CASING_WIDTH).toBe(CLOSURE_CASING_WIDTH)
    expect(paintOf(ATC_UPDATE_POINT_LAYER_ID)['circle-stroke-width']).toBe(
      CLOSURE_CASING_WIDTH,
    )
  })
})

describe('and is still distinguishable', () => {
  it('runs a different cadence, and paints from its own image', () => {
    expect(ATC_UPDATE_TAPE_CADENCE).not.toEqual(CLOSURE_TAPE_CADENCE)
    expect(paintOf(ATC_UPDATE_LAYER_ID)['line-pattern']).toBe(ATC_TAPE_IMAGE_ID)
    expect(ATC_TAPE_IMAGE_ID).not.toBe(CLOSURE_TAPE_IMAGE_ID)
  })

  it('is still tape rather than a solid line', () => {
    // A solid line is what a trail looks like, and the one thing this must
    // never resemble is a route. Held on the cadence rather than on the
    // pixels: a stripe with no thickness or no gap is not tape.
    expect(ATC_UPDATE_TAPE_CADENCE.stripe).toBeGreaterThan(0)
    expect(ATC_UPDATE_TAPE_CADENCE.pitch).toBeGreaterThan(ATC_UPDATE_TAPE_CADENCE.stripe)
  })

  it('reads as the same treatment at a glance', () => {
    // The intended reading order is "barrier" first and "whose" second, so the
    // two cadences are the SAME tape at different scales rather than two
    // unrelated patterns - which here is not a resemblance but an identity,
    // since one is derived from the other by a single factor.
    expect(ATC_UPDATE_TAPE_CADENCE.stripe).toBe(
      CLOSURE_TAPE_CADENCE.stripe * ATC_UPDATE_TAPE_SCALE,
    )
    expect(ATC_UPDATE_TAPE_CADENCE.pitch).toBe(
      CLOSURE_TAPE_CADENCE.pitch * ATC_UPDATE_TAPE_SCALE,
    )
  })

  it('is coarser than a closure, never finer', () => {
    // The direction matters: the ATC's band is the slower of the two, so a
    // change that inverted the scale would swap which feed reads as the
    // detailed one without failing anything above.
    expect(ATC_UPDATE_TAPE_SCALE).toBeGreaterThan(1)
  })
})

describe('the layers themselves', () => {
  it('draws the glow before the band, never over it', () => {
    // The halo is a soft claim - "look over here" - and the band is a hard one.
    // Painting the soft one over the hard one washes a barrier in translucent
    // red exactly where the two coincide.
    const ids = buildAtcUpdateLayers('atc-updates').map((layer) => layer.id)

    expect(ids.indexOf(ATC_UPDATE_HALO_LAYER_ID)).toBeLessThan(
      ids.indexOf(ATC_UPDATE_LAYER_ID),
    )
  })

  it('draws the band as one layer, with no casing beneath it', () => {
    // Same reason buildClosureLayers does: a solid casing under tape with
    // transparent gaps shows through every one of them.
    const ids = buildAtcUpdateLayers('atc-updates').map((layer) => layer.id)

    expect(ids.filter((id) => id === ATC_UPDATE_LAYER_ID)).toHaveLength(1)
    expect(ids.some((id) => id.includes('casing'))).toBe(false)
  })

  it('binds them all to the source it was given', () => {
    for (const layer of buildAtcUpdateLayers('atc-updates')) {
      expect((layer as { source: string }).source).toBe('atc-updates')
    }
  })

  it('does not collide with the closure layer ids', () => {
    expect(ATC_UPDATE_LAYER_ID).not.toBe('closure-band')
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
    expect(radiusAt(ATC_UPDATE_POINT_LAYER_ID, WALKING_ZOOM)).toBe(
      ATC_UPDATE_POINT_RADIUS,
    )
  })

  it('shrinks with the camera, because the ground a pixel covers does', () => {
    // The fault two rounds of shaving the full-size number could not reach: at
    // z5 the whole corridor is on one screen and a walking-zoom dot is roughly
    // the width of Maryland. Five notices drawn that way are five craters over
    // four states.
    const walking = radiusAt(ATC_UPDATE_POINT_LAYER_ID, WALKING_ZOOM)

    expect(radiusAt(ATC_UPDATE_POINT_LAYER_ID, 5)).toBeLessThan(walking / 2)
    expect(radiusAt(ATC_UPDATE_POINT_LAYER_ID, 9)).toBeLessThan(walking)
    expect(radiusAt(ATC_UPDATE_POINT_LAYER_ID, 9)).toBeGreaterThan(
      radiusAt(ATC_UPDATE_POINT_LAYER_ID, 5),
    )
  })

  it('never shrinks to nothing, having no minzoom to hide behind', () => {
    // Unlike the waypoint pins, this layer is drawn at every zoom there is -
    // and zoomed out to plan a week is exactly when someone wants to know
    // where the ATC has posted something. Clamped at the bottom stop, so the
    // corridor view keeps a mark a hiker can actually find.
    const smallest = radiusAt(ATC_UPDATE_POINT_LAYER_ID, 0)

    expect(smallest).toBe(radiusAt(ATC_UPDATE_POINT_LAYER_ID, 5))
    expect(smallest * 2).toBeGreaterThan(ATC_UPDATE_LINE_WIDTH)
  })

  it('stops growing once everything else has', () => {
    // z13 is where map/poiLayers.ts stops interpolating too. Past it the
    // comparison with a waypoint pin is fixed, which is what makes
    // src/test/atcAlertProminence.test.ts's bounds mean anything.
    expect(radiusAt(ATC_UPDATE_POINT_LAYER_ID, 18)).toBe(
      radiusAt(ATC_UPDATE_POINT_LAYER_ID, WALKING_ZOOM),
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
    ])
  })

  it('is drawn last, over the bands and over its own glow', () => {
    expect(buildAtcUpdateLayers('atc-updates').map((layer) => layer.id)).toEqual([
      ATC_UPDATE_HALO_LAYER_ID,
      ATC_UPDATE_LAYER_ID,
      ATC_UPDATE_POINT_LAYER_ID,
    ])
  })
})

describe('the glow around a point notice', () => {
  // The half of "more pronounced" that is not size. A dot says where; the glow
  // is what makes an eye that was reading somewhere else look at the dot.

  it('reaches half the dot’s radius past it again, on every side', () => {
    expect(ATC_UPDATE_HALO_RADIUS).toBe(ATC_UPDATE_POINT_RADIUS * ATC_UPDATE_HALO_SCALE)
    expect(ATC_UPDATE_HALO_RADIUS).toBeGreaterThan(ATC_UPDATE_POINT_RADIUS)
    expect(radiusAt(ATC_UPDATE_HALO_LAYER_ID, WALKING_ZOOM)).toBe(ATC_UPDATE_HALO_RADIUS)
  })

  it('rides the dot’s zoom ramp, at every stop on it', () => {
    // Its own stops would come apart from the dot's the first time either
    // moved, and what that leaves is a translucent disc with a small mark in
    // the middle - a different drawing, and one that claims an area.
    for (const zoom of [0, 5, 7, 9, 11, 13, 18]) {
      expect(radiusAt(ATC_UPDATE_HALO_LAYER_ID, zoom)).toBeCloseTo(
        radiusAt(ATC_UPDATE_POINT_LAYER_ID, zoom) * ATC_UPDATE_HALO_SCALE,
        6,
      )
    }
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
