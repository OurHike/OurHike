import { describe, expect, it } from 'vitest'
import { seasonSummary, seasonWord, stateAtMile } from './seasonStrip'
import { ATC_CHALLENGE } from './challenges.fixtures'
import { EMPTY_CHALLENGE_STATE, join, tag, tagsFor } from './challengeProgress'
import type { TagPlace } from './wherePlace'

const item = (id: string) => ATC_CHALLENGE.items.find((entry) => entry.id === id)!

function earned(entries: { id: string; place?: TagPlace }[]) {
  let state = join(
    EMPTY_CHALLENGE_STATE,
    ATC_CHALLENGE.id,
    new Date('2027-06-01T12:00:00Z'),
  )
  for (const entry of entries)
    state = tag(state, ATC_CHALLENGE, item(entry.id), {
      at: new Date('2027-07-02T15:00:00Z'),
      how: 'hand',
      place: entry.place,
    }).state
  return tagsFor(state, ATC_CHALLENGE.id)
}

describe('the season strip’s summary (#1964)', () => {
  it('reads a named place’s state from its own mile, and the hiker’s answer otherwise', () => {
    const summary = seasonSummary(
      ATC_CHALLENGE,
      earned([
        { id: 'springer-mountain' },
        { id: 'mcafee-knob' },
        { id: 'white-blaze-photo', place: { kind: 'state', state: 'WV' } },
        { id: 'trivia-quiz' },
        { id: 'pick-up-litter', place: { kind: 'off' } },
      ]),
    )
    expect(summary).toEqual({ earned: 5, states: ['GA', 'VA', 'WV'], atHome: 2 })
  })

  it('counts nothing that is not earned, and prints states once each, south to north', () => {
    const summary = seasonSummary(
      ATC_CHALLENGE,
      earned([{ id: 'katahdin' }, { id: 'mcafee-knob' }]),
    )
    expect(summary.states).toEqual(['VA', 'ME'])
    expect(JSON.stringify(summary)).not.toMatch(/100|remaining|left/)
    expect(seasonSummary(ATC_CHALLENGE, earned([]))).toEqual({
      earned: 0,
      states: [],
      atHome: 0,
    })
  })

  it('places a mile by the approximate bands, which are a guess until slice 5', () => {
    expect(stateAtMile(0)).toBe('GA')
    expect(stateAtMile(714.9)).toBe('VA')
    expect(stateAtMile(2197.9)).toBe('ME')
    expect(stateAtMile(-1)).toBeNull()
  })

  it('names the season from the window', () => {
    expect(seasonWord({ opens: '2027-05-13', closes: '2027-09-07' })).toBe('summer')
    expect(seasonWord({ opens: '2027-09-20', closes: '2027-11-30' })).toBe('autumn')
    expect(seasonWord({ opens: null, closes: null })).toBe('season')
  })
})
