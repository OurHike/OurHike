// Tests for chrome/DayHikePickBar.tsx - frame `1j`'s builder bar (#978).
//
// What is worth pinning here is the honesty of what it prints, not its layout:
//
//   The `≈` prefix, five-minute rounding and the word "walking" survive onto
//   this surface. A second builder that quietly dropped one would be the more
//   dangerous of the two, because a hiker has no way to know which screen was
//   the careful one.
//
//   No arrival clock and no difficulty score, mirroring Plan.test.tsx's
//   standing negative assertion onto the surface where that failure would
//   arrive if it ever did.
//
//   The refusal is shown, and #931's LATER row is drawn rather than omitted.

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { OFF_NETWORK_REFUSAL, type DayHikeDraft } from '../lib/dayHikeDraft'
import type { DraftStatus } from '../lib/dayHikeDraft'
import type { GraphRoute } from '../lib/trailGraph'
import { DayHikePickBar, walkingTime } from './DayHikePickBar'
import { paceEstimate, STANDARD_PACE, type PaceProfile } from '../lib/pace'

/**
 * An estimate for a walk that takes `minutes` at the standard pace.
 *
 * Priced through paceEstimate rather than written out, so what these tests
 * pin is the real formatter's ≈ and five-minute step. The distance is a
 * flat-ground one: at the standard 5 km/h it is exactly the minutes asked
 * for, and no ascent means no second term to reason about.
 */
const flatWalk = (minutes: number, pace: PaceProfile = STANDARD_PACE) =>
  paceEstimate({ distanceMi: (minutes / 60) * (5 / 1.609344), ascentFt: 0 }, pace)

afterEach(() => {
  cleanup()
})

const ORG_NAMES: Record<string, string> = {
  oprhp_trails: 'NYS Parks',
  nynjtc_long_path: 'NYNJTC',
}
const orgLabel = (source: string | null) =>
  source === null ? 'Unattributed' : (ORG_NAMES[source] ?? source)

const ROUTE: GraphRoute = {
  legs: [
    {
      name: 'Pine Meadow Trail',
      source: 'oprhp_trails',
      blaze_color: 'blue',
      trail_id: 'oprhp_trails:1',
      miles: 2.1,
    },
    {
      name: 'Seven Hills Trail',
      source: 'nynjtc_long_path',
      blaze_color: 'white',
      trail_id: 'nynjtc_long_path:2',
      miles: 1.6,
    },
    {
      name: 'Reeves Brook Trail',
      source: 'nynjtc_long_path',
      blaze_color: 'yellow',
      trail_id: 'nynjtc_long_path:3',
      miles: 1.1,
    },
  ],
  miles: 4.8,
  edgeIndices: [0, 1, 2],
  // One leg over all three edges. The bar never draws, so this only has to
  // be a valid shape; lib/trailGraph.test.ts is where sections are exercised.
  sections: [
    {
      edgeIndices: [0, 1, 2],
      from: { edgeIndex: 0, fraction: 0, at: { lon: 0, lat: 0 }, offNetworkFeet: 0 },
      to: { edgeIndex: 2, fraction: 1, at: { lon: 0, lat: 0 }, offNetworkFeet: 0 },
    },
  ],
  legsBySource: [
    { source: 'nynjtc_long_path', legs: 2 },
    { source: 'oprhp_trails', legs: 1 },
  ],
  // The bar takes its minutes as a prop rather than deriving them, so this
  // only has to be a valid GraphRoute. Null is the real state on a phone
  // holding no elevation artifact (#1011).
  climb: null,
}

const DRAFT: DayHikeDraft = {
  segments: [[]],
  refusal: null,
  looped: false,
  droppedMiles: 0,
}

/** One routed stretch, which is what a single-stretch walk now looks like to
 *  the bar. The totals travel beside the stretches rather than inside one
 *  combined route - see lib/dayHikeDraft.ts on why there is no such thing. */
function routedFrom(route: GraphRoute, gapMiles = 0): DraftStatus {
  return {
    kind: 'routed',
    stretches: [{ points: [], route }],
    miles: route.miles,
    legs: route.legs,
    legsBySource: route.legsBySource,
    climb: route.climb,
    gapMiles,
  }
}

function renderBar(overrides: Partial<Parameters<typeof DayHikePickBar>[0]> = {}) {
  const props = {
    draft: DRAFT,
    status: routedFrom(ROUTE),
    units: 'imperial' as const,
    orgLabel,
    walking: flatWalk(135),
    onUndo: vi.fn(),
    onCloseLoop: vi.fn(),
    onStartStretch: vi.fn(),
    onDone: vi.fn(),
    onCancel: vi.fn(),
    canCloseLoop: true,
    canStartNew: false,
    drawing: false,
    onToggleDraw: vi.fn(),
    ...overrides,
  }
  const view = render(<DayHikePickBar {...props} />)
  return { ...props, ...view }
}

describe('the running total', () => {
  it('counts legs and prints the distance', () => {
    renderBar()

    expect(screen.getByText(/3 legs/)).toBeInTheDocument()
    expect(screen.getByText(/4\.8/)).toBeInTheDocument()
  })

  it('keeps the ≈ prefix and the word walking', () => {
    renderBar()

    expect(screen.getByText(/≈2h 15m walking/)).toBeInTheDocument()
  })

  it('says nothing about time at all when nothing can price the climb', () => {
    // No elevation profile means no honest Naismith figure. Omitting it beats
    // printing a number that prices every climb at zero.
    renderBar({ walking: null })

    expect(screen.queryByText(/walking/)).not.toBeInTheDocument()
    expect(screen.getByText(/3 legs/)).toBeInTheDocument()
  })

  it('says one leg rather than 1 legs', () => {
    renderBar({
      status: routedFrom({
        ...ROUTE,
        legs: [ROUTE.legs[0]],
        legsBySource: [{ source: 'oprhp_trails', legs: 1 }],
      }),
    })

    expect(screen.getByText(/1 leg ·/)).toBeInTheDocument()
  })
})

describe('the live organization tally', () => {
  it('names each organization and how many legs it keeps walkable', () => {
    renderBar()

    expect(screen.getByText(/NYNJTC · 2 legs/)).toBeInTheDocument()
    expect(screen.getByText(/NYS Parks · 1 leg/)).toBeInTheDocument()
  })

  it('has something to say about a leg no organization is named on', () => {
    renderBar({
      status: routedFrom({ ...ROUTE, legsBySource: [{ source: null, legs: 1 }] }),
    })

    expect(screen.getByText(/Unattributed · 1 leg/)).toBeInTheDocument()
  })
})

describe('what it refuses', () => {
  it('shows the off-network sentence when a tap did not land', () => {
    renderBar({
      draft: { ...DRAFT, refusal: OFF_NETWORK_REFUSAL },
      status: { kind: 'empty' },
    })

    expect(screen.getByRole('alert')).toHaveTextContent(
      /only builds routes on trails an organization maintains/,
    )
  })

  it('says so when two real taps cannot be connected', () => {
    renderBar({ status: { kind: 'unroutable' } })

    expect(screen.getByRole('alert')).toHaveTextContent(
      /no marked route between those points/i,
    )
  })

  it('offers no Done at all while the walk has no route', () => {
    // Not a disabled button - LineSheet.tsx's rule, which the A.T. builder now
    // carries too: a control that looks pressable and is not teaches a hiker
    // the app is broken. A control that does not apply is absent.
    renderBar({ status: { kind: 'started' } })

    expect(screen.queryByRole('button', { name: 'Done' })).not.toBeInTheDocument()
  })
})

describe('the controls', () => {
  it('offers no Undo before there is anything to take back', () => {
    renderBar({ status: { kind: 'empty' } })

    expect(screen.queryByRole('button', { name: 'Undo' })).not.toBeInTheDocument()
  })

  it('undoes, closes the loop, finishes and cancels', () => {
    const props = renderBar({ draft: { ...DRAFT, segments: [[{} as never]] } })

    fireEvent.click(screen.getByRole('button', { name: 'Undo' }))
    expect(props.onUndo).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: 'Close the loop' }))
    expect(props.onCloseLoop).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: 'Done' }))
    expect(props.onDone).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(props.onCancel).toHaveBeenCalledTimes(1)
  })

  it('offers close-the-loop only when there is a loop to close', () => {
    renderBar({ canCloseLoop: false })

    expect(
      screen.queryByRole('button', { name: 'Close the loop' }),
    ).not.toBeInTheDocument()
  })
})

describe('roads and connectors', () => {
  it('says what is true rather than promising a feature that half ships', () => {
    // #931's row used to read "Roads and connectors · LATER" over something
    // that already shipped: map/liveTopo.ts draws roads, tracks and OSM paths
    // on the live sheet. A LATER tag over a drawn road is the bar telling the
    // hiker the opposite of what the map is showing them.
    renderBar()

    expect(screen.getByText(/Roads are drawn, never routed on/)).toBeInTheDocument()
    expect(screen.queryByText('LATER')).not.toBeInTheDocument()
  })

  it('gives it nothing to press', () => {
    const { container } = renderBar()
    const row = container.querySelector('.day-hike-bar__later')

    expect(row).not.toBeNull()
    expect(row?.querySelector('button')).toBeNull()
  })
})

describe('what it must never print', () => {
  it('gives no arrival clock and no difficulty score', () => {
    const { container } = renderBar()
    const text = container.textContent ?? ''

    // Plan.test.tsx's standing negative assertion, mirrored onto the surface
    // where it would arrive if it ever did.
    expect(text).not.toMatch(/\bbehind\b|\bahead\b|easy|moderate|strenuous|difficulty/i)
    // An arrival clock would be a time of day. Naismith knows a duration and
    // nothing about when somebody set off.
    expect(text).not.toMatch(/\b\d{1,2}:\d{2}\s?(am|pm)?\b/i)
  })
})

describe('walkingTime', () => {
  it('rounds to five minutes', () => {
    expect(walkingTime(flatWalk(133))).toBe('≈2h 15m walking')
    expect(walkingTime(flatWalk(137))).toBe('≈2h 15m walking')
    // Delegates to lib/naismith.ts's formatNaismithMinutes through
    // paceEstimate, so the two builders cannot round or print the same
    // minutes differently.
    expect(walkingTime(flatWalk(63))).toBe('≈1h 5m walking')
  })

  it('drops the hour when there is not one', () => {
    expect(walkingTime(flatWalk(43))).toBe('≈45m walking')
  })

  it('drops the minutes when they round away', () => {
    expect(walkingTime(flatWalk(119))).toBe('≈2h walking')
  })

  it('has nothing to say about a duration nothing computed', () => {
    expect(walkingTime(null)).toBeNull()
    expect(walkingTime({ minutes: 0, text: '', relativeLine: null })).toBeNull()
    expect(walkingTime({ minutes: Number.NaN, text: '', relativeLine: null })).toBeNull()
  })

  // The half this bar did not have (#1040). It priced with naismithMinutes,
  // so a hiker's own pace moved every A.T. screen and left this one alone.
  it("prints the hiker's own pace, and says what it was adjusted from", () => {
    const slow: PaceProfile = { ...STANDARD_PACE, flatPaceMph: 2 }
    const walk = flatWalk(120, slow)

    // 120 standard minutes of flat ground at 2 mph rather than 3.107.
    expect(walkingTime(walk)).toBe('≈3h 5m walking')
    expect(walk.relativeLine).toBe('was ≈2h · 1.6× standard')
  })
})

describe('several stretches (#935, #983)', () => {
  it('prints the gap apart from the miles, and never inside them', () => {
    // The assertion this whole model exists for. One figure is ground an
    // organization maintains and measures; the other is ground the app
    // declined to route. A single total would launder the second into the
    // first.
    renderBar({ status: routedFrom(ROUTE, 0.3), canStartNew: true })

    expect(screen.getByText(/4\.8 mi/)).toBeInTheDocument()
    expect(screen.getByText(/no trail under it/)).toBeInTheDocument()
    expect(screen.getByText(/on your own/)).toBeInTheDocument()
    expect(screen.queryByText(/5\.1 mi/)).not.toBeInTheDocument()
  })

  it('says nothing about a gap on a walk that has none', () => {
    renderBar({ status: routedFrom(ROUTE, 0) })

    expect(screen.queryByText(/no trail under it/)).not.toBeInTheDocument()
  })

  it('offers the new-stretch control only when a stretch is ready to end', () => {
    // The no-dead-controls rule this bar already keeps: absent, not disabled.
    renderBar({ canStartNew: false })
    expect(
      screen.queryByRole('button', { name: 'Start a new stretch' }),
    ).not.toBeInTheDocument()
  })

  it('starts a new stretch when asked', () => {
    const props = renderBar({ canStartNew: true })

    fireEvent.click(screen.getByRole('button', { name: 'Start a new stretch' }))
    expect(props.onStartStretch).toHaveBeenCalledTimes(1)
  })
})

describe('drawing, and the gap a hiker takes on (#983)', () => {
  it('changes what the bar asks for in draw mode', () => {
    renderBar({ drawing: true })

    expect(screen.getByText(/Drag to draw/)).toBeInTheDocument()
    expect(screen.queryByText(/Tap a trail to walk it/)).not.toBeInTheDocument()
  })

  it('says what a drawn line lost, in the frame\u2019s own words', () => {
    renderBar({ draft: { ...DRAFT, droppedMiles: 0.3 }, status: routedFrom(ROUTE) })

    expect(screen.getByText(/had no trail under it/)).toBeInTheDocument()
    expect(screen.getByText(/rather than guess a way across/)).toBeInTheDocument()
  })

  it('asks the hiker to take the crossing on before it saves', () => {
    // The maintainer's decision of 2026-08-27, and the reason it is a step
    // rather than a banner: the difference between reading that the app has
    // not checked the ground and answering it.
    const props = renderBar({
      draft: { ...DRAFT, droppedMiles: 0.3 },
      status: routedFrom(ROUTE, 0.3),
    })

    fireEvent.click(screen.getByRole('button', { name: 'Done' }))

    expect(props.onDone).not.toHaveBeenCalled()
    expect(screen.getByText(/cannot say it is walkable/)).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /find my own way/ }))
    expect(props.onDone).toHaveBeenCalledTimes(1)
  })

  it('lets the hiker go back to the map instead of taking it on', () => {
    const props = renderBar({
      draft: { ...DRAFT, droppedMiles: 0.3 },
      status: routedFrom(ROUTE, 0.3),
    })

    fireEvent.click(screen.getByRole('button', { name: 'Done' }))
    fireEvent.click(screen.getByRole('button', { name: 'Back to the map' }))

    expect(props.onDone).not.toHaveBeenCalled()
    expect(screen.getByText(/3 legs/)).toBeInTheDocument()
  })

  it('does not ask about a walk with no gap in it', () => {
    // A question with no consequence is one a hiker learns to dismiss, and
    // this one has to keep its weight for the walks that do cross something.
    const props = renderBar({ status: routedFrom(ROUTE, 0) })

    fireEvent.click(screen.getByRole('button', { name: 'Done' }))

    expect(props.onDone).toHaveBeenCalledTimes(1)
    expect(screen.queryByText(/cannot say it is walkable/)).not.toBeInTheDocument()
  })
})
