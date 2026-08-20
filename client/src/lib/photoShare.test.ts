import { describe, it, expect } from 'vitest'
import {
  COOLING_OFF_HOURS,
  remainingLabel,
  sharePhase,
  takenClaimForShare,
} from './photoShare'

// The pure half of the share sheet (#577). The property that matters most:
// the phase is conservative about the one claim with consequences - "taking
// it back is a complete undo" must never be said a minute too long.

describe('sharePhase', () => {
  const shared = '2026-08-20T12:00:00.000Z'

  it('is cooling immediately after the share, with the whole window left', () => {
    const phase = sharePhase(shared, new Date('2026-08-20T12:00:30.000Z'))
    expect(phase.phase).toBe('cooling')
    if (phase.phase === 'cooling') {
      expect(phase.remainingMinutes).toBe(COOLING_OFF_HOURS * 60)
    }
  })

  it('rounds the remaining time up, never promising less than remains', () => {
    const phase = sharePhase(shared, new Date('2026-08-20T12:00:30.000Z'))
    if (phase.phase === 'cooling') expect(phase.remainingMinutes).toBeGreaterThan(0)
    const nearEnd = sharePhase(shared, new Date('2026-08-20T13:59:30.000Z'))
    expect(nearEnd).toEqual({ phase: 'cooling', remainingMinutes: 1 })
  })

  it('is public the moment the window closes', () => {
    expect(sharePhase(shared, new Date('2026-08-20T14:00:00.000Z'))).toEqual({
      phase: 'public',
    })
  })

  it('treats a garbage or future timestamp as public - the conservative error', () => {
    // A wrong clock must not resurrect the "complete undo" claim.
    expect(sharePhase('not a date').phase).toBe('public')
    expect(sharePhase('2999-01-01T00:00:00.000Z', new Date(shared)).phase).toBe('public')
  })
})

describe('remainingLabel', () => {
  it('says minutes below an hour and hours-with-minutes above', () => {
    expect(remainingLabel(40)).toBe('40m')
    expect(remainingLabel(60)).toBe('1h')
    expect(remainingLabel(107)).toBe('1h 47m')
  })
})

describe('takenClaimForShare', () => {
  it('coarsens the day to the first of its month', () => {
    // The sheet's "the picture and the month" is made true here: a
    // day-precision claim about where somebody slept never leaves.
    expect(takenClaimForShare('2026-06-18')).toBe('2026-06-01')
  })

  it('passes null through, and refuses garbage rather than inventing a date', () => {
    expect(takenClaimForShare(null)).toBeNull()
    expect(takenClaimForShare('June 2026')).toBeNull()
  })
})
