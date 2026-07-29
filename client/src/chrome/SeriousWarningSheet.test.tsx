import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { SeriousWarningSheet } from './SeriousWarningSheet'

// WIREFRAMES.md §8's detail sheet: a "Confirmed by club moderators" badge and
// date, the corroboration sentence, reporter names WITHHELD for anything
// about a person, and an explicit "why you weren't pinged."
//
// The last one is unusual and worth keeping. Someone reading a serious
// warning for the first time will reasonably wonder why their phone stayed
// silent - and an app that does not answer that leaves them assuming
// notifications are broken, which is worse than the silence itself. Saying it
// plainly is what makes the one-notification policy legible rather than a
// bug that has to be inferred.

const WARNING = {
  id: 'w1',
  type: 'animals' as const,
  note: 'A bear has been taking hung food bags overnight near the shelter.',
  mile: 1045,
  confirmedAt: new Date('2026-07-24T00:00:00Z'),
  corroboration: 'Several separate reports over four days.',
  aboutAPerson: false,
  reporterName: 'Switchback',
}

const PROPS = { warning: WARNING, onClose: vi.fn() }

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('SeriousWarningSheet', () => {
  it('carries the moderator-confirmed badge', () => {
    render(<SeriousWarningSheet {...PROPS} />)

    expect(screen.getByText(/confirmed by club moderators/i)).toBeInTheDocument()
  })

  it('dates the confirmation, so the warning can be weighed', () => {
    render(<SeriousWarningSheet {...PROPS} />)

    expect(screen.getByText(/July 24/)).toBeInTheDocument()
  })

  it('gives the corroboration sentence rather than a bare assertion', () => {
    render(<SeriousWarningSheet {...PROPS} />)

    expect(
      screen.getByText(/several separate reports over four days/i),
    ).toBeInTheDocument()
  })

  it('explains why the phone stayed silent', () => {
    render(<SeriousWarningSheet {...PROPS} />)

    expect(
      screen.getByText(/only.*wrong.way|didn.t.*notif|never sends/i),
    ).toBeInTheDocument()
  })

  it('names the reporter for a warning about trail conditions', () => {
    render(<SeriousWarningSheet {...PROPS} />)

    expect(screen.getByText(/Switchback/)).toBeInTheDocument()
  })

  it('withholds the reporter name when the warning is about a person', () => {
    // WIREFRAMES.md: names withheld for anything about a person. Naming who
    // reported being followed could put that person in danger from the
    // person they reported.
    render(
      <SeriousWarningSheet
        {...PROPS}
        warning={{ ...WARNING, aboutAPerson: true, type: 'bad_hikers' }}
      />,
    )

    expect(screen.queryByText(/Switchback/)).toBe(null)
  })

  it('says the name is withheld rather than silently omitting it', () => {
    render(
      <SeriousWarningSheet
        {...PROPS}
        warning={{ ...WARNING, aboutAPerson: true, type: 'bad_hikers' }}
      />,
    )

    expect(screen.getByText(/withheld/i)).toBeInTheDocument()
  })

  it('shows where the warning is', () => {
    render(<SeriousWarningSheet {...PROPS} />)

    expect(screen.getByText(/1,045\.0/)).toBeInTheDocument()
  })

  it('offers no way to hide or mute warnings', () => {
    render(<SeriousWarningSheet {...PROPS} />)

    expect(screen.queryByRole('button', { name: /hide|mute|stop showing/i })).toBe(null)
  })
})
