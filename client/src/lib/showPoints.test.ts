import { describe, it, expect } from 'vitest'
import { POI_PIN_MIN_ZOOM } from '../map/poiLayers'
import {
  afterTap,
  afterZoom,
  NO_CHOICE_YET,
  waypointsDrawn,
  type ShowPoints,
} from './showPoints'

/**
 * The maintainer's rule, driven: "Zoom sets it, hiker overrides. But only set
 * for the hiker on first time zooming in (for that map view). Don't override a
 * setting the hiker chose."
 *
 * Every case below is a camera path a hiker can actually walk, written as the
 * path rather than as a state - a hiker pinches in, pinches out, taps, pinches
 * again, and the bug this module exists to prevent only shows up on the second
 * crossing.
 */
const SEAM = POI_PIN_MIN_ZOOM
const BELOW = SEAM - 1
const ABOVE = SEAM + 1

/** Walk a camera path from a fresh view, returning where the switch ends up. */
function walk(steps: ReadonlyArray<number | 'tap'>): ShowPoints {
  let state = NO_CHOICE_YET
  for (const step of steps) {
    state = step === 'tap' ? afterTap(state) : afterZoom(state, step, SEAM)
  }
  return state
}

describe('the Show points switch (2026-09-20)', () => {
  it('starts off, because the opening camera has no waypoints to claim', () => {
    // The corridor view is about z4.9, well below the seam. A switch that
    // opened reading "on" would be describing a screen that has none.
    expect(NO_CHOICE_YET.shown).toBe(false)
    expect(waypointsDrawn(NO_CHOICE_YET, 4.9, SEAM)).toBe(false)
  })

  it('turns itself on the first time the hiker zooms past the seam', () => {
    // Rule 1. This is the whole reason the switch is not simply manual: a
    // planner who crosses the seam wants the waypoints, and should not have to
    // find a control to get them.
    const state = walk([4.9, BELOW, ABOVE])

    expect(state.shown).toBe(true)
    expect(state.chosenByHiker).toBe(false)
    expect(state.crossedInward).toBe(true)
  })

  it('does not turn itself on again after the hiker switched it off', () => {
    // THE CASE THE RULE EXISTS FOR, and the one an auto-on that fires on every
    // crossing gets wrong while looking correct everywhere else. A hiker who
    // switched the points off to read the ground, then pinched out and back in,
    // used to get them all back.
    const state = walk([ABOVE, 'tap', BELOW, ABOVE])

    expect(state.shown).toBe(false)
    expect(state.chosenByHiker).toBe(true)
  })

  it('leaves a hiker’s "on" alone too, rather than only their "off"', () => {
    // The rule is about the CHOICE being final, not about one direction of it.
    // A hiker who turned points on below the seam and then crossed should not
    // have the auto-rule claim the credit and reset anything.
    const off = walk([ABOVE, 'tap'])
    const back = walk([ABOVE, 'tap', 'tap', BELOW, ABOVE])

    expect(off.shown).toBe(false)
    expect(back.shown).toBe(true)
    expect(back.chosenByHiker).toBe(true)
  })

  it('fires the auto-rule once per view, however many times the seam is crossed', () => {
    // "Only set for the hiker on first time zooming in (for that map view)."
    // Pinching back and forth is one of the most ordinary things a hiker does
    // on a map, and it must not toggle anything.
    const crossings: Array<number | 'tap'> = []
    for (let i = 0; i < 5; i += 1) crossings.push(BELOW, ABOVE)
    const state = walk(crossings)

    expect(state.shown).toBe(true)
    expect(state.crossedInward).toBe(true)
    expect(state.chosenByHiker).toBe(false)
  })

  it('keeps the hiker’s choice across a trip below the seam and back', () => {
    // Going out to the corridor view is not a reset. The switch remembers, so
    // a hiker returns to the map they left.
    const state = walk([ABOVE, 'tap', 2, 4.9, BELOW, ABOVE, 22])

    expect(state.shown).toBe(false)
  })

  it('draws nothing below the seam whatever the switch says', () => {
    // Both halves in one place, so no caller can draw waypoints on the
    // corridor view by consulting the switch alone. The layers' own floors are
    // the real gate; this is the shell agreeing with them.
    const on = walk([ABOVE])
    expect(on.shown).toBe(true)

    for (const zoom of [0, 2, 4.9, 6, SEAM - 0.1]) {
      expect({ zoom, drawn: waypointsDrawn(on, zoom, SEAM) }).toEqual({
        zoom,
        drawn: false,
      })
    }
    for (const zoom of [SEAM, SEAM + 0.1, 8, 12, 16, 22]) {
      expect({ zoom, drawn: waypointsDrawn(on, zoom, SEAM) }).toEqual({
        zoom,
        drawn: true,
      })
    }
  })

  it('treats the seam itself as inside, matching the layers’ own floors', () => {
    // MapLibre reads `minzoom` as inclusive, so a waypoint draws AT the seam.
    // A shell that treated the seam as outside would leave one zoom where the
    // map has pins and the switch says it has not.
    expect(walk([SEAM]).shown).toBe(true)
    expect(waypointsDrawn(walk([SEAM]), SEAM, SEAM)).toBe(true)
  })

  it('never mutates the state it is handed', () => {
    // The two movers return new values, so a component holding the old one in
    // a ref cannot observe a change it did not render.
    const before = walk([ABOVE])
    const snapshot = { ...before }

    afterTap(before)
    afterZoom(before, 22, SEAM)

    expect(before).toEqual(snapshot)
  })
})
