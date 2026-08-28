import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { VolunteerHours } from './VolunteerHours'
import type { VolunteerHoursSummary } from '../lib/volunteerHours'

afterEach(() => {
  cleanup()
})

const NOW = new Date('2026-08-20T12:00:00Z')

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

function renderHours(records: VolunteerHoursSummary[] | null = null) {
  const onLog = vi.fn()
  render(<VolunteerHours records={records} onLog={onLog} now={NOW} />)
  return onLog
}

describe('VolunteerHours', () => {
  it('logs a day with the four fields and nothing more required', () => {
    const onLog = renderHours()

    fireEvent.change(screen.getByTestId('hours-count'), { target: { value: '5.5' } })
    fireEvent.change(screen.getByTestId('hours-activity'), {
      target: { value: 'cleanup' },
    })
    fireEvent.change(screen.getByTestId('hours-note'), {
      target: { value: 'Packed out a fire ring.' },
    })
    fireEvent.click(screen.getByTestId('hours-log'))

    expect(onLog).toHaveBeenCalledWith({
      worked_on: '2026-08-20',
      hours: 5.5,
      activity: 'cleanup',
      note: 'Packed out a fire ring.',
    })
    expect(screen.getByText(/Logged\./)).toBeTruthy()
  })

  it('refuses to log zero, negative, or more than a day of hours at the keyboard', () => {
    renderHours()
    const button = screen.getByTestId('hours-log') as HTMLButtonElement

    expect(button.disabled).toBe(true)
    fireEvent.change(screen.getByTestId('hours-count'), { target: { value: '0' } })
    expect(button.disabled).toBe(true)
    fireEvent.change(screen.getByTestId('hours-count'), { target: { value: '40' } })
    expect(button.disabled).toBe(true)
    fireEvent.change(screen.getByTestId('hours-count'), { target: { value: '6' } })
    expect(button.disabled).toBe(false)
  })

  it('prints one labeled total - the unconfirmed slice rides with the number', () => {
    renderHours([
      record({ hours: 4, state: 'claimed' }),
      record({ hours: 3, state: 'confirmed', worked_on: '2026-08-17' }),
    ])

    const totals = screen.getByTestId('hours-totals')
    expect(totals.textContent).toContain('7 hours over 2 days')
    expect(totals.textContent).toContain('4 of them not yet confirmed by a club')
  })

  it('drops disputed hours from the total but keeps the record visible', () => {
    renderHours([
      record({ hours: 4, state: 'claimed' }),
      record({ hours: 8, state: 'disputed', worked_on: '2026-08-16' }),
    ])

    expect(screen.getByTestId('hours-totals').textContent).toContain('4 hours')
    expect(screen.getByText(/Disputed — worth a word with the club/)).toBeTruthy()
  })

  it('offers the record as a CSV export - a file the hiker hands over, never a page', () => {
    renderHours([record({})])

    const link = screen.getByTestId('hours-export')
    expect(link.getAttribute('download')).toBe('ourhike-volunteer-hours.csv')
    expect(link.getAttribute('href')).toContain('data:text/csv')
  })

  it('links out to NYNJTC’s own form rather than submitting on the hiker’s behalf', () => {
    renderHours()

    const link = screen.getByTestId('hours-nynjtc-link')
    expect(link.getAttribute('href')).toBe(
      'https://secure.nynjtc.org/webform/individual-trail-volunteer-report-form',
    )
    expect(link.getAttribute('target')).toBe('_blank')
    expect(link.getAttribute('rel')).toContain('noopener')
  })

  it('renders no lack-state: an empty logbook is just the form, not an accusation', () => {
    const { container } = render(
      <VolunteerHours records={null} onLog={vi.fn()} now={NOW} />,
    )

    expect(container.textContent).not.toMatch(/you haven.t|no hours yet|0 hours|streak/i)
    expect(screen.queryByTestId('hours-totals')).toBeNull()
  })
})
