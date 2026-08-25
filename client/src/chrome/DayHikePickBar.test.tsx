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
  legsBySource: [
    { source: 'nynjtc_long_path', legs: 2 },
    { source: 'oprhp_trails', legs: 1 },
  ],
}

const DRAFT: DayHikeDraft = { points: [], refusal: null, looped: false }

function renderBar(overrides: Partial<Parameters<typeof DayHikePickBar>[0]> = {}) {
  const props = {
    draft: DRAFT,
    status: { kind: 'routed', route: ROUTE } as DraftStatus,
    units: 'imperial' as const,
    orgLabel,
    walkingMinutes: 135,
    onUndo: vi.fn(),
    onCloseLoop: vi.fn(),
    onDone: vi.fn(),
    onCancel: vi.fn(),
    canCloseLoop: true,
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
    renderBar({ walkingMinutes: null })

    expect(screen.queryByText(/walking/)).not.toBeInTheDocument()
    expect(screen.getByText(/3 legs/)).toBeInTheDocument()
  })

  it('says one leg rather than 1 legs', () => {
    renderBar({
      status: {
        kind: 'routed',
        route: {
          ...ROUTE,
          legs: [ROUTE.legs[0]],
          legsBySource: [{ source: 'oprhp_trails', legs: 1 }],
        },
      },
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
      status: {
        kind: 'routed',
        route: { ...ROUTE, legsBySource: [{ source: null, legs: 1 }] },
      },
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

  it('will not let a hiker finish a walk that has no route', () => {
    renderBar({ status: { kind: 'started' } })

    expect(screen.getByRole('button', { name: 'Done' })).toBeDisabled()
  })
})

describe('the controls', () => {
  it('undoes, closes the loop, finishes and cancels', () => {
    const props = renderBar({ draft: { ...DRAFT, points: [{} as never] } })

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
  it('names the gap rather than omitting it', () => {
    // #931. A missing capability the app is silent about reads as a bug; one
    // the app names reads as a boundary.
    renderBar()

    expect(screen.getByText('Roads and connectors')).toBeInTheDocument()
    expect(screen.getByText('LATER')).toBeInTheDocument()
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
    expect(walkingTime(133)).toBe('≈2h 15m walking')
    expect(walkingTime(137)).toBe('≈2h 15m walking')
  })

  it('drops the hour when there is not one', () => {
    expect(walkingTime(43)).toBe('≈45m walking')
  })

  it('drops the minutes when they round away', () => {
    expect(walkingTime(119)).toBe('≈2h walking')
  })

  it('has nothing to say about a duration nothing computed', () => {
    expect(walkingTime(null)).toBeNull()
    expect(walkingTime(0)).toBeNull()
    expect(walkingTime(Number.NaN)).toBeNull()
  })
})
