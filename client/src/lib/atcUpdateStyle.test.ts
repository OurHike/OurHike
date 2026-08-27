import { describe, it, expect } from 'vitest'
import {
  ATC_TAPE_IMAGE_ID,
  ATC_UPDATE_CASING_WIDTH,
  ATC_UPDATE_COLOR,
  ATC_NOTICE_BURST,
  ATC_NOTICE_CASING_RATIO,
  ATC_NOTICE_CASING_WIDTH,
  ATC_NOTICE_FILL_RADIUS,
  ATC_NOTICE_ICON_ID,
  ATC_UPDATE_LAYER_ID,
  ATC_UPDATE_LINE_WIDTH,
  ATC_UPDATE_POINT_DRAWN_WIDTH,
  ATC_UPDATE_POINT_LAYER_ID,
  ATC_UPDATE_TAPE_CADENCE,
  ATC_UPDATE_TAPE_SCALE,
  atcNoticeRimWidths,
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

function layoutOf(id: string): Record<string, unknown> {
  const layer = buildAtcUpdateLayers('atc-updates').find(
    (candidate) => candidate.id === id,
  )
  expect(layer).toBeDefined()
  return (layer as { layout: Record<string, unknown> }).layout
}

/**
 * The mark's drawn width at one zoom, in CSS pixels.
 *
 * The ramp moved from `circle-radius` to `icon-size` with #1071 - a symbol
 * layer scales one rasterised image rather than growing a circle - so this
 * evaluates the `icon-size` stops the way MapLibre would (linear between them,
 * clamped outside) and multiplies through by the size the image was drawn at.
 * Every case below then goes on saying what a hiker sees at a given zoom,
 * which is the thing worth asserting and the thing that did not change.
 */
function drawnWidthAt(id: string, zoom: number): number {
  const expression = layoutOf(id)['icon-size'] as unknown[]
  expect(expression[0]).toBe('interpolate')
  expect(expression[1]).toEqual(['linear'])
  expect(expression[2]).toEqual(['zoom'])

  const stops: Array<[number, number]> = []
  for (let at = 3; at < expression.length; at += 2) {
    stops.push([expression[at] as number, expression[at + 1] as number])
  }

  const clamped = Math.min(Math.max(zoom, stops[0][0]), stops[stops.length - 1][0])
  let scale = stops[stops.length - 1][1]
  for (let at = 0; at < stops.length - 1; at += 1) {
    const [lowZoom, lowScale] = stops[at]
    const [highZoom, highScale] = stops[at + 1]
    if (clamped <= highZoom) {
      const span = highZoom - lowZoom
      const along = span === 0 ? 0 : (clamped - lowZoom) / span
      scale = lowScale + along * (highScale - lowScale)
      break
    }
  }

  return ATC_UPDATE_POINT_DRAWN_WIDTH * scale
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

  it('holds its notice mark lighter than the casing the band used to carry', () => {
    // WHAT IS LEFT OF CLOSURE_CASING_WIDTH, which now paints nothing on this
    // map: the tape edges its own stripes, and #1071 took the point notice off
    // the disc that was the other consumer. It survives as the weight both
    // successors are held under, and this is the ATC half of that comparison.
    expect(ATC_UPDATE_CASING_WIDTH).toBe(CLOSURE_CASING_WIDTH)
    expect(ATC_NOTICE_CASING_WIDTH).toBeLessThan(ATC_UPDATE_CASING_WIDTH)
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
  // is an invisible one. This layer is what makes them show up at all.

  it('is far wider than the band, which is what it was not', () => {
    // It used to be exactly half the band's width - "a barrier seen end-on" -
    // and that made the ATC's own word about the trail the smallest mark on a
    // map full of 38px waypoint pins. src/test/atcAlertProminence.test.ts is
    // where that comparison is actually held, against the pins themselves.
    expect(ATC_UPDATE_POINT_DRAWN_WIDTH).toBeGreaterThan(ATC_UPDATE_LINE_WIDTH)
    expect(drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, WALKING_ZOOM)).toBe(
      ATC_UPDATE_POINT_DRAWN_WIDTH,
    )
  })

  it('shrinks with the camera, because the ground a pixel covers does', () => {
    // The fault two rounds of shaving the full-size number could not reach: at
    // z5 the whole corridor is on one screen and a walking-zoom mark is roughly
    // the width of Maryland. Five notices drawn that way are five craters over
    // four states.
    const walking = drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, WALKING_ZOOM)

    expect(drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, 5)).toBeLessThan(walking / 2)
    expect(drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, 9)).toBeLessThan(walking)
    expect(drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, 9)).toBeGreaterThan(
      drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, 5),
    )
  })

  it('never shrinks to nothing, having no minzoom to hide behind', () => {
    // Unlike the waypoint pins, this layer is drawn at every zoom there is -
    // and zoomed out to plan a week is exactly when someone wants to know
    // where the ATC has posted something. Clamped at the bottom stop, so the
    // corridor view keeps a mark a hiker can actually find.
    const smallest = drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, 0)

    expect(smallest).toBe(drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, 5))
    expect(smallest).toBeGreaterThan(ATC_UPDATE_LINE_WIDTH)
  })

  it('stops growing once everything else has', () => {
    // z13 is where map/poiLayers.ts stops interpolating too. Past it the
    // comparison with a waypoint pin is fixed, which is what makes
    // src/test/atcAlertProminence.test.ts's bounds mean anything.
    expect(drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, 18)).toBe(
      drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, WALKING_ZOOM),
    )
  })

  it('is drawn as an image, which is the only way it can have a hole', () => {
    // #1071. A MapLibre circle has no paint property that empties its middle,
    // so the open centre is not something the old layer could have been tuned
    // into - it is why this became a symbol layer at all.
    const layer = buildAtcUpdateLayers('atc-updates').find(
      (candidate) => candidate.id === ATC_UPDATE_POINT_LAYER_ID,
    )

    expect(layer?.type).toBe('symbol')
    expect(layoutOf(ATC_UPDATE_POINT_LAYER_ID)['icon-image']).toBe(ATC_NOTICE_ICON_ID)
  })

  it('never gives way to a waypoint pin that got there first', () => {
    // map/warningLayers.ts's reason, which applies here with more force: a
    // notice dropped by the collision engine is a notice nobody was shown, and
    // a hiker cannot tell that from there being none. As a circle this could
    // not be dropped at all, so `icon-allow-overlap` is what KEEPS the old
    // behaviour across the change rather than a new liberty.
    expect(layoutOf(ATC_UPDATE_POINT_LAYER_ID)['icon-allow-overlap']).toBe(true)
  })

  it('still pushes other symbols aside rather than ignoring them', () => {
    // The other half of that: `icon-ignore-placement` stays at its default, so
    // a waypoint pin under a notice yields instead of being drawn through it.
    expect(layoutOf(ATC_UPDATE_POINT_LAYER_ID)['icon-ignore-placement']).toBeUndefined()
  })

  it('draws from the same source as the bands', () => {
    // A `line` layer ignores Point features and a `symbol` layer ignores
    // lines, so one source carries both - and the tap has one place to look.
    const layers = buildAtcUpdateLayers('atc-updates')

    expect(layers.map((layer) => (layer as { source: string }).source)).toEqual([
      'atc-updates',
      'atc-updates',
    ])
  })

  it('is drawn last, over both bands', () => {
    expect(buildAtcUpdateLayers('atc-updates').map((layer) => layer.id)).toEqual([
      ATC_UPDATE_LAYER_ID,
      ATC_UPDATE_POINT_LAYER_ID,
    ])
  })
})

describe('the burst geometry (#1071)', () => {
  // The numbers behind the shape, held here rather than in the rasteriser,
  // because they are decisions about what a hiker sees and not about pixels.
  // map/atcNoticeMark.test.ts checks that the image agrees with them.

  it('leaves the middle open, which is the whole change', () => {
    // A spoke starts halfway out, so the inner half of the mark is a ring of
    // clear ground with a small dot in it. What a notice is drawn ON - the
    // centerline, a shelter pin, a ford - sits in that hole.
    expect(ATC_NOTICE_BURST.innerRadius).toBeGreaterThan(ATC_NOTICE_BURST.hubRadius * 2)
    expect(ATC_NOTICE_BURST.innerRadius).toBeLessThan(1)
  })

  it('keeps a dot on the coordinate, so it marks rather than encircles', () => {
    // Without it the mark is a ring, and a ring reads as drawn AROUND
    // something. A point notice names one mile marker.
    expect(ATC_NOTICE_BURST.hubRadius).toBeGreaterThan(0)
    expect(ATC_NOTICE_BURST.hubRadius * ATC_NOTICE_FILL_RADIUS).toBeGreaterThan(2)
  })

  it('tapers outward rather than running parallel', () => {
    // A parallel-sided spoke reads as a cog. The taper is what makes it read
    // as radiating, which is the thing the mark is saying.
    expect(ATC_NOTICE_BURST.tipHalfWidth).toBeGreaterThan(ATC_NOTICE_BURST.innerHalfWidth)
  })

  it('leaves real daylight between neighbouring spokes at walking zoom', () => {
    // THE PROPERTY THE CHANGE IS BOUGHT WITH, and it was false the first time
    // this was rendered: with the band's 2px casing the gaps came out 1.7px
    // wide at the half-width of the day and the mark was a dark disc with red
    // spokes on it. Measured 2026-08-27 on the shipped geometry: 7.5px of red
    // against 4.5px of clear ground - and 2.9px of gap if the band's casing is
    // put back, which is what makes this case the guard on that constant.
    const { spoke, gap } = atcNoticeRimWidths()

    expect(gap).toBeGreaterThan(3)
    expect(spoke).toBeGreaterThan(gap)
    expect(spoke).toBeLessThan(gap * 2)
  })

  it('still has daylight at the bottom of the zoom ramp', () => {
    // Where a spoke count is really decided. At z5 the whole mark is 16px, and
    // this is the bound that rules out the finer eleven-spoke burst: gaps that
    // close here turn the corridor view back into a solid blob.
    const { gap } = atcNoticeRimWidths(ATC_UPDATE_POINT_DRAWN_WIDTH * 0.4)

    expect(gap).toBeGreaterThan(1)
  })

  it('carries the pins’ own hairline rather than the band’s casing', () => {
    // 1/15 of the radius is map/poiIcons.ts's `edgeWidth`. Using the band's 2px
    // here is exactly what closed the gaps, because a casing runs down BOTH
    // sides of every spoke - so this is the constant whose drift would quietly
    // undo the test above.
    expect(ATC_NOTICE_CASING_RATIO).toBe(1 / 15)
    expect(ATC_NOTICE_CASING_WIDTH).toBeLessThan(ATC_UPDATE_CASING_WIDTH)
    expect(ATC_NOTICE_FILL_RADIUS + ATC_NOTICE_CASING_WIDTH).toBe(
      ATC_UPDATE_POINT_DRAWN_WIDTH / 2,
    )
  })

  it('has no glow layer left to draw', () => {
    // Deleted rather than dimmed (#1071): a 54px wash of red behind an open
    // burst is the solid disc back in a softer spelling. Asserted as an absence
    // because the next pass to reach for "make it louder" will reach here.
    const ids = buildAtcUpdateLayers('atc-updates').map((layer) => layer.id)

    // Two, not the three this asserted when it was written: the casing line
    // under the band went the same way and for the same reason, once the band
    // became tape with transparent gaps for a casing to show through.
    expect(ids).toHaveLength(2)
    expect(ids.some((id) => id.includes('halo'))).toBe(false)
    for (const layer of buildAtcUpdateLayers('atc-updates')) {
      expect(
        (layer as { paint?: Record<string, unknown> }).paint?.['circle-blur'],
      ).toBeUndefined()
    }
  })
})
