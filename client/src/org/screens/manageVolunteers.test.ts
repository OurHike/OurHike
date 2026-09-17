/**
 * The two pure helpers the manage-volunteers screens decide with.
 *
 * Both exist because a screen got a sentence wrong rather than a layout:
 * `lastReadLabel` is the difference between "last read 14 minutes ago" and
 * "1,412 minutes ago", and `matchesRoster` is the difference between a search
 * that answers "who has Pine Meadow" and one that looks broken.
 */

import { describe, expect, it } from 'vitest'
import { lastReadLabel } from './Workdays'
import { matchesRoster } from './Roster'
import type { RosterEntry } from '../orgApi'

const NOW = new Date('2026-09-17T12:00:00Z')

describe('lastReadLabel', () => {
  it('says "never read" when the mirror has never run', () => {
    expect(lastReadLabel(null, NOW)).toBe('never read')
  })

  it('says "never read" rather than "NaN" for an unparseable timestamp', () => {
    expect(lastReadLabel('not a date', NOW)).toBe('never read')
  })

  it('counts in minutes for a read inside the last hour', () => {
    expect(lastReadLabel('2026-09-17T11:46:00Z', NOW)).toBe('last read 14 minutes ago')
  })

  it('writes "1 minute ago" singular rather than "1 minutes ago"', () => {
    expect(lastReadLabel('2026-09-17T11:59:00Z', NOW)).toBe('last read 1 minute ago')
  })

  it('switches to hours at the hour rather than reporting 60 minutes', () => {
    expect(lastReadLabel('2026-09-17T11:00:00Z', NOW)).toBe('last read 1 hour ago')
  })

  it('switches to a date past a day, so nobody has to divide 1,412 by 60', () => {
    expect(lastReadLabel('2026-09-14T11:00:00Z', NOW)).toBe('last read Sep 14')
  })
})

const entry = (over: Partial<RosterEntry> = {}): RosterEntry => ({
  person_id: 'p-1',
  email: 'ana@example.org',
  display_name: 'Ana Reyes',
  full_name: 'Ana Reyes',
  roles: ['Maintainer'],
  sections: ['Pine Meadow North'],
  pending_invite: false,
  ...over,
})

describe('matchesRoster', () => {
  it('keeps everybody when the search box is empty', () => {
    expect(matchesRoster(entry(), '')).toBe(true)
    expect(matchesRoster(entry(), '   ')).toBe(true)
  })

  it('matches a section name, which is how an admin asks who holds a stretch', () => {
    expect(matchesRoster(entry(), 'Pine Meadow')).toBe(true)
  })

  it('matches a role name', () => {
    expect(matchesRoster(entry(), 'maintainer')).toBe(true)
  })

  it('matches an email fragment', () => {
    expect(matchesRoster(entry(), 'example.org')).toBe(true)
  })

  it('ignores case, because nobody types a roster search in title case', () => {
    expect(matchesRoster(entry(), 'ANA')).toBe(true)
  })

  it('answers false rather than throwing for a person with no name and no email', () => {
    expect(
      matchesRoster(entry({ display_name: null, full_name: null, email: null }), 'ana'),
    ).toBe(false)
  })

  it('still finds a nameless person by their section', () => {
    const nameless = entry({ display_name: null, full_name: null, email: null })
    expect(matchesRoster(nameless, 'Pine Meadow')).toBe(true)
  })
})
