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
    opportunities: [] as const,
    opportunitiesAsOf: NOW,
    gpsMile: null,
    now: NOW,
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

  const WORKDAY = {
    id: 'sample:one',
    club_name: 'NY-NJ Trail Conference',
    title: 'Bear Mountain steps',
    description: 'Gloves provided.',
    lat: 41.31,
    lon: -73.99,
    mile: 1407.6,
    starts_on: '2026-08-24',
    ends_on: '2026-08-24',
    status: 'upcoming' as const,
    capacity: 12,
    signup_mode: 'contact' as const,
    signup_contact: 'mailto:volunteer@example.org',
  }

  it('lists an upcoming workday with the club’s own signup channel', () => {
    renderTab({ opportunities: [WORKDAY], gpsMile: 1400.0 })

    expect(screen.getByText('Bear Mountain steps')).toBeTruthy()
    expect(screen.getByText(/NY-NJ Trail Conference/)).toBeTruthy()
    expect(screen.getByText(/7\.6 trail mi away/)).toBeTruthy()
    // An introduction, not an enrolment: the link is the club's channel, and
    // no green tick of the app's invention appears anywhere.
    const link = screen.getByRole('link', { name: /ask the crew/i })
    expect(link.getAttribute('href')).toBe('mailto:volunteer@example.org')
  })

  it('replaces the whole list once the artifact is older than the ceiling', () => {
    // A hedged invitation still reads as an invitation (#760): past 48 hours
    // the rows go away entirely and the age is said out loud.
    const twoAndAHalfDaysAgo = new Date(NOW.getTime() - 60 * 60 * 60 * 1000)
    renderTab({ opportunities: [WORKDAY], opportunitiesAsOf: twoAndAHalfDaysAgo })

    expect(screen.queryByText('Bear Mountain steps')).toBeNull()
    expect(screen.getByText(/out of date/i)).toBeTruthy()
  })

  it('says it could not check, which is not the same as no workdays', () => {
    renderTab({ opportunities: null, opportunitiesAsOf: null })

    expect(screen.getByText(/needs signal/i)).toBeTruthy()
    expect(screen.queryByText(/No workdays are posted/i)).toBeNull()
  })

  it('says plainly when nothing is posted, without inventing urgency', () => {
    renderTab({ opportunities: [] })

    expect(screen.getByText(/No workdays are posted here yet/)).toBeTruthy()
  })
})
