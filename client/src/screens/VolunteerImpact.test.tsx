import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { VolunteerImpact } from './VolunteerImpact'
import type { VolunteerHoursSummary } from '../lib/volunteerHours'

// The panel #761 asked for and did not ship (#969). lib/volunteerImpact.test.ts
// holds the arithmetic and the guardrail; this file is about the two things a
// component can get wrong on its own - whether it draws at all, and whether the
// off switch turns off a display or a logbook.

function record(overrides: Partial<VolunteerHoursSummary>): VolunteerHoursSummary {
  return {
    id: crypto.randomUUID(),
    club_id: null,
    worked_on: '2026-08-18',
    hours: 4,
    work_project_id: null,
    activity: 'maintenance',
    note: null,
    mile: null,
    lat: null,
    lon: null,
    state: 'claimed',
    confirmed_at: null,
    recorded_at: '2026-08-18T22:00:00Z',
    ...overrides,
  }
}

const RECORDS = [
  record({ hours: 4, worked_on: '2026-08-18' }),
  record({ hours: 3.5, worked_on: '2026-08-17', state: 'confirmed' }),
]

afterEach(cleanup)

describe('VolunteerImpact', () => {
  it('shows what a hiker put back, and who can see it', () => {
    render(<VolunteerImpact records={RECORDS} shown onToggleShown={vi.fn()} />)

    expect(screen.getByText("What you've put back")).toBeInTheDocument()
    expect(screen.getByText('Kept for you, seen by no one.')).toBeInTheDocument()
    expect(screen.getByText('7.5')).toBeInTheDocument()
    expect(screen.getByText('Hours you wrote down')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('Days out')).toBeInTheDocument()
  })

  it('renders nothing at all for a hiker with nothing logged', () => {
    // Rule 2 at the component level. A panel headed "what you've put back" over
    // a row of dashes is the most pointed lack-state this screen could draw -
    // and it would appear to every hiker who has never logged an hour, which is
    // most of them.
    const { container } = render(
      <VolunteerImpact records={null} shown onToggleShown={vi.fn()} />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('renders nothing when every record is disputed', () => {
    const { container } = render(
      <VolunteerImpact
        records={[record({ state: 'disputed' })]}
        shown
        onToggleShown={vi.fn()}
      />,
    )

    expect(container).toBeEmptyDOMElement()
  })

  it('names the two tiles it cannot fill, as the app’s gap', () => {
    render(<VolunteerImpact records={RECORDS} shown onToggleShown={vi.fn()} />)

    expect(screen.getByText(/forgets what it filed/i)).toBeInTheDocument()
  })

  describe('the off switch', () => {
    it('hides the numbers and keeps the switch reachable', () => {
      // The switch has to survive its own use. Rendering nothing when off would
      // make it a one-way door: a hiker could turn the panel off and have
      // nowhere to turn it back on, because the control lives in the panel.
      render(<VolunteerImpact records={RECORDS} shown={false} onToggleShown={vi.fn()} />)

      expect(screen.queryByTestId('impact-tiles')).not.toBeInTheDocument()
      expect(
        screen.getByRole('checkbox', { name: /show what i.ve put back/i }),
      ).toBeInTheDocument()
    })

    it('says the record is still there, without printing the number it hid', () => {
      // Putting the total into the sentence that hides it would make the switch
      // decorative - and would be the app arguing with the hiker's choice.
      render(<VolunteerImpact records={RECORDS} shown={false} onToggleShown={vi.fn()} />)

      const off = screen.getByTestId('impact-off')
      expect(off).toHaveTextContent(/still logged/i)
      expect(off).toHaveTextContent(/still yours/i)
      expect(off).not.toHaveTextContent('7.5')
    })

    it('reports the hiker’s choice rather than toggling itself', () => {
      // The preference is the source of truth (`impact_panel_shown`), so this
      // control is bound to it and reports upward - a local `useState` here
      // would forget the choice on the next visit, which is exactly what the
      // switch exists to prevent.
      const onToggleShown = vi.fn()
      render(<VolunteerImpact records={RECORDS} shown onToggleShown={onToggleShown} />)

      fireEvent.click(screen.getByRole('checkbox', { name: /show what i.ve put back/i }))

      expect(onToggleShown).toHaveBeenCalledWith(false)
      expect(screen.getByTestId('impact-tiles')).toBeInTheDocument()
    })
  })
})
