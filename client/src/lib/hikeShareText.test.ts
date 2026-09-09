// The plain-text card of a finished hike (#1317).

import { describe, expect, it } from 'vitest'

import { hikeShareText } from './hikeShareText'

const FACTS = {
  name: 'Springer → Katahdin',
  trailName: 'Appalachian Trail',
  walkedMi: 2198.4,
  toGoMi: 0,
  startedOn: '2024-03-14',
  finishedOn: '2026-08-12',
  daysWalking: 152,
  sections: 9,
  directions: ['NOBO'] as const,
}

describe('the card', () => {
  it('holds what was walked and when, and nothing about where anybody is', () => {
    const text = hikeShareText(FACTS, 'imperial')

    expect(text).toContain('Springer → Katahdin')
    expect(text).toContain('2,198.4 mi walked · 0.0 mi to go')
    expect(text).toContain('14 Mar 2024 – 12 Aug 2026')
    expect(text).toContain('152 days walking')
    expect(text).toContain('9 sections')
    // The separation both features depend on.
    expect(text).not.toMatch(/lat|lon|coordinate|where I am|right now/i)
  })

  it('reads a flip-flop as both directions, in the order they were walked', () => {
    // One direction for the whole hike would be wrong for at least one leg,
    // and there would be no way to tell which.
    const text = hikeShareText({ ...FACTS, directions: ['NOBO', 'SOBO'] }, 'imperial')
    expect(text).toContain('northbound, then southbound')
  })

  it('omits a leg that covered no ground rather than naming a direction for it', () => {
    const text = hikeShareText({ ...FACTS, directions: [null] }, 'imperial')
    expect(text).not.toMatch(/northbound|southbound/)
  })

  it('keeps the YEARS, because a hike that took two of them says so', () => {
    // "14 Mar – 12 Aug" for a walk from 2024 to 2026 hides the single most
    // striking fact about it.
    const text = hikeShareText(FACTS, 'imperial')
    expect(text).toContain('14 Mar 2024 – 12 Aug 2026')
  })

  it('omits the dates rather than printing a dash for them', () => {
    // "Dates: —" reads as a fact the app lost rather than one nobody entered.
    const text = hikeShareText(
      { ...FACTS, startedOn: null, finishedOn: null },
      'imperial',
    )
    expect(text).not.toContain('–')
    expect(text).toContain('9 sections')
  })

  it('carries no percentage, no rank and no comparison', () => {
    // The card leaves the app and cannot be corrected afterwards, which
    // makes it the worst possible place to invent a claim.
    const text = hikeShareText(FACTS, 'imperial')
    expect(text).not.toMatch(/%|rank|behind|ahead of|on track|streak|faster/i)
  })
})
