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

const NOW = new Date('2026-08-20T12:00:00Z')

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
    // OurHike sends no push notifications at all, and this tab is the
    // feature most likely to grow one.
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

  it('never counts contributions, anywhere on the screen', () => {
    // "It never counts, and it never mentions what was skipped"
    // (DATA_NUDGES.md) - the trap this list was named with. No "2 places",
    // no "0 answered", no progress of any kind. (A workday's own capacity
    // is a club's stated fact about their crew, not a count of the hiker.)
    const { container } = (() => {
      const props = {
        contributeConditions: true,
        onToggleContribute: vi.fn(),
        passedToday: PASSED,
        onOpenPlace: vi.fn(),
        units: 'imperial' as const,
        opportunities: [] as const,
        opportunitiesAsOf: NOW,
        gpsMile: null,
        now: NOW,
      }
      return render(<Volunteer {...props} />)
    })()

    expect(container.textContent).not.toMatch(
      /\d+ (places|of \d+|answered|skipped|left)/i,
    )
  })

  it('no longer holds the workday list, which is Today\u2019s now (#1440, D22)', () => {
    // THE SPLIT THIS PAGE EXISTS FOR, pinned so the section cannot drift
    // back. Today answers "what is happening" - the crews out now, the
    // switch, the window and the views. This page answers "what have I done,
    // and what can I hand back", which is why it still opens on the smallest
    // possible act rather than on a calendar.
    renderTab()

    expect(screen.queryByText('Workdays in the next two weeks')).toBeNull()
    expect(screen.queryByText(/No workdays are posted here yet/)).toBeNull()
    expect(screen.queryByRole('link', { name: /ask the crew/i })).toBeNull()
    // And the half it keeps is still here.
    expect(screen.getByText(/Ask me about conditions as I pass things/)).toBeTruthy()
  })
})
