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
  onUndo: null,
  refusedTap: false,
  onBreakIntoDays: vi.fn(),
  onRecordWalked: vi.fn(),
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

    // Descent beside the climb (#973): Naismith gives descent no credit, so a
    // leg that reads easy on time can still be the one that hurts.
    expect(
      screen.getByText('19.6 mi · 4,200 ft ↑ · 2,900 ft ↓ · ≈13h 20m'),
    ).toBeInTheDocument()
    expect(
      screen.getByText('12.9 mi · 2,300 ft ↑ · 2,500 ft ↓ · ≈7h 50m'),
    ).toBeInTheDocument()
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

  it('says which of the two reasons it has no times (#1039)', () => {
    // "No elevation profile in this download" would send somebody looking
    // for a download they already have. A hole in the DEM is a different
    // fact about a route that crosses it.
    const bare = LEGS.map((leg) => ({
      ...leg,
      ascentFt: null,
      descentFt: null,
      minutes: null,
    }))
    render(<RouteStopsPanel {...PROPS} legs={bare} unpriced="unmeasured" />)

    expect(screen.getByText(/no elevation measured/)).toBeInTheDocument()
    expect(screen.queryByText(/No elevation profile in this download/)).toBeNull()
    expect(screen.queryByText(/walking/)).toBeNull()
    // The distance is untouched by a hole and stays.
    expect(screen.getByText('NOBO · 32.5 mi')).toBeInTheDocument()
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

    // The same stretch in the past tense (#789).
    await user.click(screen.getByRole('button', { name: 'I already walked this' }))
    expect(PROPS.onRecordWalked).toHaveBeenCalled()

    await user.click(screen.getByRole('button', { name: 'Close the route builder' }))
    expect(PROPS.onClose).toHaveBeenCalled()
  })

  it('counts the points and the legs, with the direction (#973)', () => {
    render(<RouteStopsPanel {...PROPS} />)
    expect(screen.getByText('NOBO · 3 points · 2 legs')).toBeInTheDocument()
  })

  describe('a route that is not a route yet (#973)', () => {
    it('asks for the first point, and offers nothing to break into days', () => {
      render(<RouteStopsPanel {...PROPS} stops={[]} legs={[]} direction={null} />)

      expect(screen.getByText('Tap the trail to drop a point.')).toBeInTheDocument()
      expect(screen.getByText('0 points')).toBeInTheDocument()

      // THE WHOLE BAR IS GONE, and this is the assertion that matters most
      // here: before #973 an empty stop list rendered "0.0 mi · ≈0m walking"
      // over two buttons whose handlers refuse below two stops. A total of
      // nothing, stated as a measurement, above controls that decline to act.
      expect(screen.queryByText(/0\.0 mi/)).toBeNull()
      expect(screen.queryByText(/walking/)).toBeNull()
      expect(screen.queryByRole('button', { name: 'Break into days' })).toBeNull()
      expect(screen.queryByRole('button', { name: 'I already walked this' })).toBeNull()
    })

    it('asks for the second point when one is down', () => {
      render(<RouteStopsPanel {...PROPS} stops={[STOPS[0]]} legs={[]} direction={null} />)

      expect(
        screen.getByText('Tap the trail again for where this stretch ends.'),
      ).toBeInTheDocument()
      expect(screen.getByText('1 point')).toBeInTheDocument()
      expect(screen.queryByText(/0\.0 mi/)).toBeNull()
      expect(screen.queryByRole('button', { name: 'Break into days' })).toBeNull()
      expect(screen.queryByRole('button', { name: 'I already walked this' })).toBeNull()
    })

    it('does not blame a missing elevation profile for having no legs', () => {
      // The no-profile note is about legs it could not price, and there are
      // none - printing it here would explain an absence that has a different
      // cause.
      render(<RouteStopsPanel {...PROPS} stops={[]} legs={[]} direction={null} />)
      expect(screen.queryByText(/No elevation profile/)).toBeNull()
    })
  })

  describe('undo (#973)', () => {
    it('is absent with nothing to undo, and wired when there is', async () => {
      const user = userEvent.setup()
      const { rerender } = render(<RouteStopsPanel {...PROPS} onUndo={null} />)
      expect(screen.queryByRole('button', { name: 'Undo the last change' })).toBeNull()

      const onUndo = vi.fn()
      rerender(<RouteStopsPanel {...PROPS} onUndo={onUndo} />)
      await user.click(screen.getByRole('button', { name: 'Undo the last change' }))
      expect(onUndo).toHaveBeenCalled()
    })
  })

  describe('the routable limitation (#973)', () => {
    it('is stated standing, before anybody taps the wrong thing', () => {
      render(<RouteStopsPanel {...PROPS} />)
      expect(
        screen.getByText(/Only the A\.T\. centerline can carry a route/),
      ).toBeInTheDocument()
    })

    it('becomes the refusal when a tap was refused - one sentence, not two', () => {
      render(<RouteStopsPanel {...PROPS} refusedTap />)

      expect(screen.getByRole('status').textContent).toMatch(
        /more than 3 mi from the trail/,
      )
      expect(screen.queryByText(/Only the A\.T\. centerline/)).toBeNull()
    })
  })

  it('never prints an arrival clock or a difficulty score', () => {
    const { container } = render(<RouteStopsPanel {...PROPS} />)
    expect(container.textContent).not.toMatch(/\d{1,2}:\d{2}\s*(am|pm)/i)
    expect(container.textContent).not.toMatch(/difficult|score|rating/i)
  })
})
