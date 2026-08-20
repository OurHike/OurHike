import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { Volunteer, type PassedPlace } from './Volunteer'

afterEach(() => {
  cleanup()
})

// The Volunteer tab (features/VOLUNTEERING.md, #759). What these tests hold:
// the opt-in is a plain preference toggle, the passed-today list exists only
// behind consent, and the screen never counts anything - the guardrail four
// docs share, whose whole failure mode is a well-meaning number.

const PASSED: PassedPlace[] = [
  { id: 'w1', name: 'Icewater Spring', type: 'water', mile: 210.4 },
  { id: 's1', name: 'Peck’s Corner Shelter', type: 'shelter', mile: 217.9 },
]

function renderTab(overrides: Partial<Parameters<typeof Volunteer>[0]> = {}) {
  const props = {
    contributeConditions: false,
    onToggleContribute: vi.fn(),
    passedToday: PASSED,
    onOpenPlace: vi.fn(),
    units: 'imperial' as const,
    ...overrides,
  }
  render(<Volunteer {...props} />)
  return props
}

describe('Volunteer', () => {
  it('offers the contribution opt-in as a switch that reports the choice', () => {
    const { onToggleContribute } = renderTab()

    fireEvent.click(screen.getByRole('checkbox', { name: /ask me about conditions/i }))

    expect(onToggleContribute).toHaveBeenCalledWith(true)
  })

  it('says plainly that nothing here is a notification', () => {
    // HIKER_SAFETY.md pins the wrong-way alert as the only push this app
    // sends, and this tab is the feature most likely to grow a second one.
    renderTab()

    expect(screen.getByText(/never a notification/i)).toBeTruthy()
  })

  it('keeps the passed-today list behind the opt-in', () => {
    // The list is the "asked more thoroughly" surface; consent is what makes
    // it legitimate rather than nagging (DATA_NUDGES.md's opt-in mode).
    renderTab({ contributeConditions: false })

    expect(screen.queryByText('Places you passed today')).toBeNull()
  })

  it('lists the passed places for an opted-in hiker, and a tap opens the place', () => {
    const { onOpenPlace } = renderTab({ contributeConditions: true })

    fireEvent.click(screen.getByRole('button', { name: /icewater spring/i }))

    expect(screen.getByText('Places you passed today')).toBeTruthy()
    expect(screen.getByText('mi 217.9')).toBeTruthy()
    expect(onOpenPlace).toHaveBeenCalledWith('w1')
  })

  it('shows no section at all on a day with nothing passed - never an empty scold', () => {
    renderTab({ contributeConditions: true, passedToday: [] })

    expect(screen.queryByText('Places you passed today')).toBeNull()
  })

  it('never counts anything, anywhere on the screen', () => {
    // "It never counts, and it never mentions what was skipped"
    // (DATA_NUDGES.md) - the trap this list was named with. No "2 places",
    // no "0 answered", no progress of any kind.
    const { container } = (() => {
      const props = {
        contributeConditions: true,
        onToggleContribute: vi.fn(),
        passedToday: PASSED,
        onOpenPlace: vi.fn(),
        units: 'imperial' as const,
      }
      return render(<Volunteer {...props} />)
    })()

    expect(container.textContent).not.toMatch(/\d+ (places|of \d+|answered|skipped|left)/i)
  })
})
