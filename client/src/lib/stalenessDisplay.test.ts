import { describe, it, expect } from 'vitest'
import {
  stalenessTreatment,
  stalenessPresentation,
  lastConfirmedText,
  confidenceTreatment,
} from './stalenessDisplay'

// WIREFRAMES.md §11. Staleness is a THIRD visual channel, independent of
// confidence:
//   - staleness  = when a human last said this was fine
//   - confidence = whether it was ever verified to exist (a dashed pin)
// A dashed (unverified) pin can still be Fresh; a verified pin can go Stale.
// Conflating them would tell someone a spring is unreliable when the real
// situation is that nobody has checked recently - a different claim.
//
// WIREFRAMES.md is also explicit that today staleness is DESCRIBED, never
// amplified: boosting stale POIs' prominence to solicit confirmations is Data
// Nudges, Post-MVP. So there is no prominence/boost output here at all.

const NOW = new Date('2026-07-29T12:00:00Z')

describe('stalenessTreatment', () => {
  it('rings a fresh pin in green', () => {
    expect(stalenessTreatment('fresh')).toMatchObject({ ring: 'green', opacity: 1 })
  })

  it('gives an ageing pin no ring at all - absence is the signal', () => {
    expect(stalenessTreatment('ageing')).toMatchObject({ ring: 'none', opacity: 1 })
  })

  it('fades a stale pin and dots its border', () => {
    expect(stalenessTreatment('stale')).toMatchObject({
      ring: 'grey-dotted',
      opacity: 0.5,
      borderStyle: 'dotted',
    })
  })

  it('never amplifies a stale pin - the invitation is a treatment, not a boost', () => {
    // Data Nudges ships now (#759), so the treatments ARE its passive
    // invitation - but the mechanism stays a restyle. Guards against a
    // well-meaning "make stale pins bigger so people confirm them" change,
    // which is the size/boost channel this design never uses.
    const treatment = stalenessTreatment('stale')

    expect(treatment).not.toHaveProperty('boost')
    expect(treatment).not.toHaveProperty('prominence')
    expect(treatment.opacity).toBeLessThanOrEqual(1)
  })

  it('renders never-confirmed as neutral - indistinguishable from ageing', () => {
    // Maintainer decision 2026-08-20 (#256): day one must not open stale.
    expect(stalenessTreatment('never')).toEqual(stalenessTreatment('ageing'))
  })
})

describe('stalenessPresentation', () => {
  it('gives never-confirmed water the subtle invite, in pixels and in words', () => {
    const presentation = stalenessPresentation('water', 'never')

    expect(presentation?.treatment.ring).toBe('faint-invite')
    expect(presentation?.treatment.opacity).toBe(1)
    expect(presentation?.words).toBe('No recent word')
  })

  it.each(['shelter', 'campsite', 'resupply'] as const)(
    'keeps a never-confirmed %s neutral until somebody has confirmed it once',
    (poiType) => {
      const presentation = stalenessPresentation(poiType, 'never')

      expect(presentation?.treatment).toEqual(stalenessTreatment('never'))
      expect(presentation?.words).toBe('Never confirmed')
    },
  )

  it('applies the fresh/ageing/stale ladder to a place with a confirmation history', () => {
    expect(stalenessPresentation('shelter', 'stale')?.treatment).toEqual(
      stalenessTreatment('stale'),
    )
    expect(stalenessPresentation('water', 'fresh')?.treatment).toEqual(
      stalenessTreatment('fresh'),
    )
  })

  it('says nothing at all for a type outside the nudge scope', () => {
    // A viewpoint has no condition to be stale about (DATA_NUDGES.md) - no
    // ring, no words, no exception for water's day-one invite either.
    expect(stalenessPresentation('viewpoint', 'never')).toBeNull()
    expect(stalenessPresentation('parking', 'stale')).toBeNull()
    expect(stalenessPresentation('privy', 'fresh')).toBeNull()
  })
})

describe('confidenceTreatment', () => {
  it('dashes the outline of something never verified to exist', () => {
    expect(confidenceTreatment('low')).toMatchObject({ outline: 'dashed' })
  })

  it('leaves a verified pin solid', () => {
    expect(confidenceTreatment('high')).toMatchObject({ outline: 'solid' })
  })

  it('is a separate channel - it says nothing about rings or fading', () => {
    // If confidence started emitting a ring or an opacity it would silently
    // start overriding staleness, and the two claims would blur together.
    const treatment = confidenceTreatment('low')

    expect(treatment).not.toHaveProperty('ring')
    expect(treatment).not.toHaveProperty('opacity')
  })
})

describe('lastConfirmedText', () => {
  it('states the month and the days elapsed, as WIREFRAMES.md words it', () => {
    const confirmed = new Date('2026-05-12T12:00:00Z')

    expect(lastConfirmedText(confirmed, NOW)).toBe('Last confirmed in May · 78 days ago')
  })

  it('says so plainly when nothing has ever confirmed it', () => {
    expect(lastConfirmedText(null, NOW)).toBe('Never confirmed')
  })

  it('says "today" rather than "0 days ago"', () => {
    expect(lastConfirmedText(new Date('2026-07-29T08:00:00Z'), NOW)).toBe(
      'Last confirmed in July · today',
    )
  })

  it('says "yesterday" rather than "1 days ago"', () => {
    expect(lastConfirmedText(new Date('2026-07-28T08:00:00Z'), NOW)).toBe(
      'Last confirmed in July · yesterday',
    )
  })

  it('always gives a number of days, however old - never just "a long time ago"', () => {
    expect(lastConfirmedText(new Date('2024-01-01T12:00:00Z'), NOW)).toMatch(
      /\d+ days ago/,
    )
  })
})
