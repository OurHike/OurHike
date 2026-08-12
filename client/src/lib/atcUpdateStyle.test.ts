import { describe, it, expect } from 'vitest'
import {
  ATC_UPDATE_BAR_RHYTHM,
  ATC_UPDATE_CASING_LAYER_ID,
  ATC_UPDATE_CASING_WIDTH,
  ATC_UPDATE_COLOR,
  ATC_UPDATE_LAYER_ID,
  ATC_UPDATE_LINE_WIDTH,
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
    expect(buildAtcUpdateLayers('atc-updates').map((layer) => layer.id)).toEqual([
      ATC_UPDATE_CASING_LAYER_ID,
      ATC_UPDATE_LAYER_ID,
    ])
  })

  it('binds both to the source it was given', () => {
    for (const layer of buildAtcUpdateLayers('atc-updates')) {
      expect((layer as { source: string }).source).toBe('atc-updates')
    }
  })

  it('does not collide with the closure layer ids', () => {
    expect(ATC_UPDATE_LAYER_ID).not.toBe('closure-band')
    expect(ATC_UPDATE_CASING_LAYER_ID).not.toBe('closure-casing')
  })
})
