import { describe, it, expect } from 'vitest'
import { createExpression, latest } from '@maplibre/maplibre-gl-style-spec'
import {
  ATC_UPDATE_BAND_LAYER_IDS,
  ATC_UPDATE_CASING_WIDTH,
  ATC_UPDATE_COLOR,
  ATC_NOTICE_CASING_RATIO,
  ATC_NOTICE_CASING_WIDTH,
  ATC_NOTICE_GLYPH_BOX,
  ATC_NOTICE_ICON_ID,
  ATC_UPDATE_LAYER_ID,
  ATC_UPDATE_POINT_DRAWN_WIDTH,
  ATC_UPDATE_POINT_LAYER_ID,
  ATC_UPDATE_POINT_MIN_ZOOM,
  ATC_UPDATE_SPACING_SCALE,
  buildAtcUpdateLayers,
} from './atcUpdateStyle'
import {
  CLOSURE_CASING_WIDTH,
  CLOSURE_COLOR,
  CLOSURE_INK,
  CLOSURE_LAYER_ID,
  CLOSURE_PAPER_WIDTH,
  buildClosureLayers,
  closureCrossesId,
  closureLayerIds,
} from './closureStyle'

// #461 asks that an ATC update not look like an OurHike closure. This file
// holds the half of that answer which is NOT on the canvas, and the reasoning
// is worth restating because the obvious move is the wrong one: two barrier
// colours on a safety map read as two severities, not as two organisations,
// and a hiker who learns one shade of barrier is softer than the other has
// learned something false. Both mean the trail is shut. Whose claim it is
// gets answered where a hiker can read an answer - the banner and the sheet.

/** The field day sheet's paper and the closure ink, the ground and ink every
 *  band here is built with. */
const GROUND = '#ffffff'
const INK = CLOSURE_INK

/** The ATC's layers as the style builds them. */
const atcLayers = () => buildAtcUpdateLayers('atc-updates', GROUND, INK)

/** A zoom-dependent `symbol-spacing` as MapLibre's own engine resolves it, so
 *  a cadence this file compares is one the map would draw rather than an
 *  expression that merely looks equal. */
function spacingAt(value: unknown, zoom: number): number {
  const compiled = createExpression(
    value as never,
    latest.layout_symbol['symbol-spacing'] as never,
  )
  if (compiled.result === 'error')
    throw new Error('symbol-spacing is not a valid expression')
  return compiled.value.evaluate({ zoom }, {} as never) as number
}

function layoutOf(id: string): Record<string, unknown> {
  const layer = atcLayers().find((candidate) => candidate.id === id)
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
  it('is the closure\u2019s own crossed-out mark, layer for layer', () => {
    // ONE MARK FOR "DO NOT WALK THIS" (features/NEARBY_TRAILS.md 3), as a
    // claim about the layer stack rather than about a few numbers: the band
    // is buildClosureLayers itself, so the paper, the trace, the cross size,
    // the halo and every colour are the closure's by construction (#1677).
    // Only the ids and the chain's spacing may differ.
    const band = atcLayers().slice(0, ATC_UPDATE_BAND_LAYER_IDS.length)
    const closure = buildClosureLayers('atc-updates', { ground: GROUND, ink: INK })
    const strip = (layers: typeof band) =>
      layers.map((layer) => {
        const {
          id: _id,
          layout,
          ...rest
        } = layer as {
          id: string
          layout?: Record<string, unknown>
        }
        return { ...rest, layout: { ...layout, 'symbol-spacing': undefined } }
      })

    expect(strip(band)).toEqual(strip(closure))
  })

  it('draws its point notice in the closure red', () => {
    expect(ATC_UPDATE_COLOR).toBe(CLOSURE_COLOR)
  })

  it('holds its notice mark lighter than the casing the band used to carry', () => {
    // WHAT IS LEFT OF CLOSURE_CASING_WIDTH, which paints nothing on this map
    // now. It survives as the weight the notice's hairline is held under.
    expect(ATC_UPDATE_CASING_WIDTH).toBe(CLOSURE_CASING_WIDTH)
    expect(ATC_NOTICE_CASING_WIDTH).toBeLessThan(ATC_UPDATE_CASING_WIDTH)
  })
})

describe('and is still distinguishable', () => {
  it('spaces its crosses further apart than a closure\u2019s, at every zoom', () => {
    // The same crosses, the same size, at twice the spacing: "barrier" at a
    // glance, and "whose" only on a closer look. Compared zoom by zoom, so a
    // cadence that matched up close and drifted far out is caught.
    const atc = layoutOf(closureCrossesId(ATC_UPDATE_LAYER_ID))['symbol-spacing']
    const closure = (
      buildClosureLayers('c', { ground: GROUND, ink: INK }).find(
        (layer) => layer.id === closureCrossesId(CLOSURE_LAYER_ID),
      ) as { layout: Record<string, unknown> }
    ).layout['symbol-spacing']
    for (const zoom of [11, 12, 13, 16]) {
      expect(spacingAt(atc, zoom), `z${zoom}`).toBe(
        ATC_UPDATE_SPACING_SCALE * spacingAt(closure, zoom),
      )
    }
  })

  it('is coarser than a closure, never finer', () => {
    // The direction matters: the ATC's band is the slower of the two, so a
    // change that inverted the scale would swap which feed reads as the
    // detailed one without failing anything above.
    expect(ATC_UPDATE_SPACING_SCALE).toBeGreaterThan(1)
  })
})

describe('the layers themselves', () => {
  it('names the band\u2019s layers the way the closure names its own', () => {
    expect(ATC_UPDATE_BAND_LAYER_IDS).toEqual(closureLayerIds(ATC_UPDATE_LAYER_ID))
    for (const layer of atcLayers()) {
      expect(
        (layer as { paint?: Record<string, unknown> }).paint?.['line-pattern'],
      ).toBeUndefined()
    }
  })

  it('binds them all to the source it was given', () => {
    for (const layer of atcLayers()) {
      expect((layer as { source: string }).source).toBe('atc-updates')
    }
  })

  it('does not collide with the closure layer ids', () => {
    const closureIds = closureLayerIds(CLOSURE_LAYER_ID)
    for (const id of ATC_UPDATE_BAND_LAYER_IDS) expect(closureIds).not.toContain(id)
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
    expect(ATC_UPDATE_POINT_DRAWN_WIDTH).toBeGreaterThan(CLOSURE_PAPER_WIDTH)
    expect(drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, WALKING_ZOOM)).toBe(
      ATC_UPDATE_POINT_DRAWN_WIDTH,
    )
  })

  it('shrinks with the camera, because the ground a pixel covers does', () => {
    // The fault two rounds of shaving the full-size number could not reach: a
    // walking-zoom mark at the seam covers ground it is not about. The z5
    // case that used to open this test went with the z5 stop: below the seam
    // the point is not drawn at all (#1292).
    const walking = drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, WALKING_ZOOM)
    const atSeam = drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, ATC_UPDATE_POINT_MIN_ZOOM)

    expect(atSeam).toBeLessThan(walking)
    expect(drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, 11)).toBeGreaterThan(atSeam)
  })

  it('is drawn at its seam size from the seam, and never smaller', () => {
    // The ramp's bottom stop is the seam itself: there is no zoom where this
    // draws smaller than it does at z9, because there is no zoom below the
    // seam where it draws at all (#1292). The case this replaces said the
    // opposite - "no minzoom to hide behind" - and the maintainer's call that
    // the opening camera shows trail lines only reversed it.
    const atSeam = drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, ATC_UPDATE_POINT_MIN_ZOOM)

    expect(drawnWidthAt(ATC_UPDATE_POINT_LAYER_ID, 0)).toBe(atSeam)
    expect(atSeam).toBeGreaterThan(CLOSURE_PAPER_WIDTH)
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
    const layer = atcLayers().find(
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

  it('stops the point at the seam, like every other mark on the map (#1292)', () => {
    // The opening camera shows trail lines only, by the maintainer's call of
    // 2026-09-08. The tape stays: a closure band is trail line, not a mark.
    const point = atcLayers().find(
      (candidate) => candidate.id === ATC_UPDATE_POINT_LAYER_ID,
    )
    const band = atcLayers().find((candidate) => candidate.id === ATC_UPDATE_LAYER_ID)
    expect(point?.minzoom).toBe(ATC_UPDATE_POINT_MIN_ZOOM)
    expect(band).not.toHaveProperty('minzoom')
  })

  it('draws from the same source as the bands', () => {
    // A `line` layer ignores Point features and a `symbol` layer ignores
    // lines, so one source carries both - and the tap has one place to look.
    const layers = atcLayers()

    expect(new Set(layers.map((layer) => (layer as { source: string }).source))).toEqual(
      new Set(['atc-updates']),
    )
  })

  it('is drawn last, over the whole band', () => {
    expect(atcLayers().map((layer) => layer.id)).toEqual([
      ...ATC_UPDATE_BAND_LAYER_IDS,
      ATC_UPDATE_POINT_LAYER_ID,
    ])
  })
})

describe('the mark geometry (#1071, and the triangle since 2026-09-10)', () => {
  // The numbers behind the shape, held here rather than in the rasteriser,
  // because they are decisions about what a hiker sees and not about pixels.
  // map/atcNoticeMark.test.ts checks that the image agrees with them.

  it('fills its drawn width with the glyph box and a casing on each side', () => {
    // The derivation, so the two cannot drift: the outer edge of the ink is
    // the drawn width, and the glyph's box follows from it.
    expect(ATC_NOTICE_GLYPH_BOX + 2 * ATC_NOTICE_CASING_WIDTH).toBe(
      ATC_UPDATE_POINT_DRAWN_WIDTH,
    )
    expect(ATC_NOTICE_GLYPH_BOX).toBeGreaterThan(ATC_UPDATE_POINT_DRAWN_WIDTH * 0.9)
  })

  it('carries the pins’ own hairline rather than the band’s casing', () => {
    // 1/15 of the radius is map/poiIcons.ts's `edgeWidth`. The band's 2px
    // closed the burst's gaps (#1071) because a casing runs down BOTH sides of
    // every edge, and the triangle's band would lose most of its red the same
    // way - so this is the constant whose drift would quietly undo the mark.
    expect(ATC_NOTICE_CASING_RATIO).toBe(1 / 15)
    expect(ATC_NOTICE_CASING_WIDTH).toBeLessThan(ATC_UPDATE_CASING_WIDTH)
  })

  it('has no glow layer left to draw', () => {
    // Deleted rather than dimmed (#1071): a 54px wash of red behind an open
    // burst is the solid disc back in a softer spelling. Asserted as an absence
    // because the next pass to reach for "make it louder" will reach here.
    const ids = atcLayers().map((layer) => layer.id)

    // Five: the band's paper, trace, chain and far mark, and the point. The
    // count has been three, two, three, four and five as the band was
    // respelled around it - which is exactly why this test names the GLOW
    // rather than trusting a count to catch its return.
    expect(ids).toHaveLength(5)
    expect(ids.some((id) => id.includes('halo'))).toBe(false)
    for (const layer of atcLayers()) {
      expect(
        (layer as { paint?: Record<string, unknown> }).paint?.['circle-blur'],
      ).toBeUndefined()
    }
  })
})
