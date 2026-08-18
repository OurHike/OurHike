// Tests for the route builder's card (#755). The figures' honesty rules are
// the point: ≈ on every time, "walking" on the total, nulls said out loud
// rather than zero-filled, and the off-corridor refusal explained in the
// hiker's own units.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { RouteSheet } from './RouteSheet'

const PROPS = {
  legs: [],
  pointCount: 0,
  direction: null,
  units: 'imperial' as const,
  refusedTap: false,
  onUndo: vi.fn(),
  onCancel: vi.fn(),
  onBreakIntoDays: vi.fn(),
}

const LEGS = [
  { distanceMi: 15.4, ascentFt: 2900, descentFt: 1750, minutes: 425 },
  { distanceMi: 17.2, ascentFt: 4100, descentFt: 2200, minutes: 512 },
]

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('before any legs exist', () => {
  it('teaches the one rule: first tap starts, last ends, between inserts', () => {
    render(<RouteSheet {...PROPS} />)

    expect(screen.getByText(/first tap is the start/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Break into days' })).toBeDisabled()
    expect(screen.getByRole('button', { name: /Undo point/ })).toBeDisabled()
  })

  it('withholds a direction for a single point', () => {
    const { container } = render(<RouteSheet {...PROPS} pointCount={1} />)

    expect(container.querySelector('.route-sheet__direction')).toBeNull()
  })
})

describe('with legs', () => {
  it('prints each leg’s distance, climb both ways, and an ≈ moving time', () => {
    render(<RouteSheet {...PROPS} legs={LEGS} pointCount={3} direction="NOBO" />)

    expect(
      screen.getByText(/15\.4 mi · 2,900 ft ↑ · 1,750 ft ↓ · ≈7h 5m/),
    ).toBeInTheDocument()
    expect(screen.getByText('NOBO')).toBeInTheDocument()
  })

  it('totals unrounded minutes and says the time is walking time', () => {
    render(<RouteSheet {...PROPS} legs={LEGS} pointCount={3} direction="NOBO" />)

    // 425 + 512 = 937 → ≈15h 35m. Summing the two displayed (already
    // rounded) legs instead would drift - the total is computed from the
    // unrounded minutes and rounded once.
    expect(screen.getByText(/32\.6 mi · ≈15h 35m walking/)).toBeInTheDocument()
  })

  it('never shows an arrival clock', () => {
    const { container } = render(
      <RouteSheet {...PROPS} legs={LEGS} pointCount={3} direction="NOBO" />,
    )

    expect(container.textContent).not.toMatch(/\d{1,2}:\d{2}/)
  })

  it('says why climb and time are missing rather than zero-filling them', () => {
    render(
      <RouteSheet
        {...PROPS}
        legs={[{ distanceMi: 12, ascentFt: null, descentFt: null, minutes: null }]}
        pointCount={2}
        direction="NOBO"
      />,
    )

    expect(screen.getByText(/no elevation profile/)).toBeInTheDocument()
    expect(screen.queryByText(/≈/)).toBeNull()
  })
})

describe('the refused tap', () => {
  it('states the gate in the hiker’s units', () => {
    render(<RouteSheet {...PROPS} refusedTap units="metric" />)

    expect(screen.getByRole('status').textContent).toMatch(/4\.8 km/)
  })
})

describe('the limitation', () => {
  it('says only the centerline is routable, where the planning happens', () => {
    render(<RouteSheet {...PROPS} />)

    expect(
      screen.getByText(/Only the AT centerline can carry a route/),
    ).toBeInTheDocument()
  })
})

describe('actions', () => {
  it('fires undo, cancel and break-into-days', async () => {
    const user = userEvent.setup()
    render(<RouteSheet {...PROPS} legs={LEGS} pointCount={3} direction="NOBO" />)

    await user.click(screen.getByRole('button', { name: /Undo point/ }))
    expect(PROPS.onUndo).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Break into days' }))
    expect(PROPS.onBreakIntoDays).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Close the route builder' }))
    expect(PROPS.onCancel).toHaveBeenCalled()
  })
})
