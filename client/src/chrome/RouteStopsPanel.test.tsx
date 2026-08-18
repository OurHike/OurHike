// Tests for the editable route surface (#755, the "route by destination"
// flow's second screen): fields in walk order, honest per-leg figures, the
// "walking" qualifier on the total, and the degraded no-profile path.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { RouteStopsPanel, type RouteLegDisplay } from './RouteStopsPanel'

const STOPS = [
  { mile: 470.8, name: 'Damascus' },
  { mile: 490.4, name: 'Wise Shelter' },
  { mile: 503.3 },
]

const LEGS: RouteLegDisplay[] = [
  { distanceMi: 19.6, ascentFt: 4200, descentFt: 2900, minutes: 800 },
  { distanceMi: 12.9, ascentFt: 2300, descentFt: 2500, minutes: 470 },
]

const PROPS = {
  stops: STOPS,
  legs: LEGS,
  direction: 'NOBO' as const,
  units: 'imperial' as const,
  onEditStop: vi.fn(),
  onAddStop: vi.fn(),
  onBreakIntoDays: vi.fn(),
  onClose: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the editable route', () => {
  it('renders every stop as a field - names first, bare miles as markers', () => {
    render(<RouteStopsPanel {...PROPS} />)

    expect(screen.getByRole('button', { name: /Damascus/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Wise Shelter/ })).toBeInTheDocument()
    // The unnamed end is its mile marker (planDisplay.stopLabel's rule).
    expect(screen.getByRole('button', { name: /mi 503\.3/ })).toBeInTheDocument()
  })

  it('prices each leg between its fields - distance, ascent, moving time', () => {
    render(<RouteStopsPanel {...PROPS} />)

    expect(screen.getByText('19.6 mi · 4,200 ft ↑ · ≈13h 20m')).toBeInTheDocument()
    expect(screen.getByText('12.9 mi · 2,300 ft ↑ · ≈7h 50m')).toBeInTheDocument()
  })

  it('says direction, total and moving time in the bar - "walking" said', () => {
    render(<RouteStopsPanel {...PROPS} />)

    // 32.5 mi, 1270 unrounded minutes -> ≈21h 10m, and the qualifier that
    // keeps it honest: Naismith is moving time, not an elapsed day.
    expect(screen.getByText('NOBO · 32.5 mi · ≈21h 10m walking')).toBeInTheDocument()
  })

  it('drops times - never fakes them - on a download with no profile', () => {
    const bare = LEGS.map((leg) => ({
      ...leg,
      ascentFt: null,
      descentFt: null,
      minutes: null,
    }))
    render(<RouteStopsPanel {...PROPS} legs={bare} />)

    expect(screen.getByText('NOBO · 32.5 mi')).toBeInTheDocument()
    expect(screen.getByText('19.6 mi')).toBeInTheDocument()
    expect(screen.getByText(/No elevation profile in this download/)).toBeInTheDocument()
    expect(screen.queryByText(/walking/)).toBeNull()
  })

  it('wires editing, adding, breaking into days and closing', async () => {
    const user = userEvent.setup()
    render(<RouteStopsPanel {...PROPS} />)

    await user.click(screen.getByRole('button', { name: /Wise Shelter/ }))
    expect(PROPS.onEditStop).toHaveBeenCalledWith(1)

    await user.click(screen.getByRole('button', { name: /Add a stop on the way/ }))
    expect(PROPS.onAddStop).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Break into days' }))
    expect(PROPS.onBreakIntoDays).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Close the route builder' }))
    expect(PROPS.onClose).toHaveBeenCalled()
  })

  it('never prints an arrival clock or a difficulty score', () => {
    const { container } = render(<RouteStopsPanel {...PROPS} />)
    expect(container.textContent).not.toMatch(/\d{1,2}:\d{2}\s*(am|pm)/i)
    expect(container.textContent).not.toMatch(/difficult|score|rating/i)
  })
})
