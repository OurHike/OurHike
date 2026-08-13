import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { SeriousWarningSheet } from './SeriousWarningSheet'

// WIREFRAMES.md §8's detail sheet: a "Confirmed by club moderators" badge and
// date, where the warning is, what it says, and an explicit "why you weren't
// pinged."
//
// The last one is unusual and worth keeping. Someone reading a serious
// warning for the first time will reasonably wonder why their phone stayed
// silent - and an app that does not answer that leaves them assuming
// notifications are broken, which is worse than the silence itself. Saying it
// plainly is what makes the one-notification policy legible rather than a
// bug that has to be inferred.
//
// The corroboration sentence and the reporter attribution used to be here.
// #292 removed both because nothing can fill them, and the tests that pinned
// them are replaced by tests pinning their ABSENCE - see the last block. A
// deleted field that quietly comes back is exactly what this file should
// catch, and a deletion nothing asserts is one nobody can see was deliberate.

const WARNING = {
  id: 'w1',
  type: 'animals' as const,
  note: 'A bear has been taking hung food bags overnight near the shelter.',
  mile: 1045,
  confirmedAt: new Date('2026-07-24T00:00:00Z'),
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

  it('explains why the phone stayed silent', () => {
    render(<SeriousWarningSheet {...PROPS} />)

    expect(
      screen.getByText(/only.*wrong.way|didn.t.*notif|never sends/i),
    ).toBeInTheDocument()
  })

  it('shows where the warning is', () => {
    render(<SeriousWarningSheet {...PROPS} />)

    expect(screen.getByText(/1,045\.0/)).toBeInTheDocument()
  })

  it('says what the warning is about', () => {
    render(<SeriousWarningSheet {...PROPS} />)

    expect(screen.getByText(/taking hung food bags/i)).toBeInTheDocument()
  })

  it('offers no way to hide or mute warnings', () => {
    render(<SeriousWarningSheet {...PROPS} />)

    expect(screen.queryByRole('button', { name: /hide|mute|stop showing/i })).toBe(null)
  })

  // #292: what the sheet must NOT say, now that nothing can fill it.

  it('attributes the warning to nobody, named or withheld', () => {
    // The whole paragraph went, not just the name. #245 deleted `marked_by`
    // off the closure sheet on the same grounds - a fact about a person,
    // sourced only from profile ids that #252 took off the public read path.
    render(<SeriousWarningSheet {...PROPS} />)

    expect(screen.queryByText(/reported by/i)).toBe(null)
    expect(screen.queryByText(/withheld/i)).toBe(null)
  })

  it('makes no claim about how many people reported it', () => {
    // A corroboration sentence with no count behind it is a fabricated
    // evidence claim on a safety warning, which is worse than saying less.
    render(<SeriousWarningSheet {...PROPS} />)

    expect(
      screen.queryByText(/separate reports|corroborat|several (other )?hikers/i),
    ).toBe(null)
  })
})
