import { describe, expect, it } from 'vitest'
import { earnedPlaces, seasonSummary, seasonWord, stateAtMile } from './seasonStrip'
import { ATC_CHALLENGE } from './challenges.fixtures'
import { EMPTY_CHALLENGE_STATE, join, tag, tagsFor } from './challengeProgress'
import type { TagPlace } from './wherePlace'

const item = (id: string) => ATC_CHALLENGE.items.find((entry) => entry.id === id)!

function earned(entries: { id: string; place?: TagPlace; how?: 'gps' | 'hand' }[]) {
  let state = join(
    EMPTY_CHALLENGE_STATE,
    ATC_CHALLENGE.id,
    new Date('2027-06-01T12:00:00Z'),
  )
  for (const entry of entries)
    state = tag(state, ATC_CHALLENGE, item(entry.id), {
      at: new Date('2027-07-02T15:00:00Z'),
      how: entry.how ?? 'hand',
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

  it('places a mile by the measured bands, both termini included', () => {
    expect(stateAtMile(0)).toBe('GA')
    expect(stateAtMile(714.9)).toBe('VA')
    expect(stateAtMile(2197.9)).toBe('ME')
    expect(stateAtMile(-1)).toBeNull()
  })

  it('puts Harpers Ferry in West Virginia and the NC/TN line’s North Carolina towns in North Carolina (review of #2020)', () => {
    // Harpers Ferry's published mile is 1,026.5 (preview-shots/fixtures/
    // challenges.mjs); the eyeballed bands said Maryland. Max Patch and Hot
    // Springs sit near miles 254 and 274 by general knowledge, not repo data,
    // and the eyeballed bands gave that whole stretch to Tennessee.
    expect(stateAtMile(1026.5)).toBe('WV')
    expect(stateAtMile(254)).toBe('NC')
    expect(stateAtMile(274)).toBe('NC')
  })

  it('never counts an item the walk earned as at home, and places a section walked at its middle', () => {
    const summary = seasonSummary(
      ATC_CHALLENGE,
      earned([
        { id: 'shelter-logbook', how: 'gps' },
        { id: 'summit-4000', how: 'gps' },
        { id: 'trail-crew', how: 'gps' },
      ]),
    )
    expect(summary).toEqual({ earned: 3, states: [], atHome: 0 })
    // The fixture has no section item; one is added for this case alone.
    const section = {
      ...item('trivia-quiz'),
      id: 'roanoke-section',
      match: {
        kind: 'section_walked' as const,
        trail: 'AT',
        fromMile: 700,
        toMile: 730,
        fromName: 'Catawba',
        toName: 'Daleville',
        minFraction: 0.9,
      },
    }
    const challenge = { ...ATC_CHALLENGE, items: [...ATC_CHALLENGE.items, section] }
    const state = tag(
      join(EMPTY_CHALLENGE_STATE, challenge.id, new Date('2027-06-01T12:00:00Z')),
      challenge,
      section,
      { at: new Date('2027-07-02T15:00:00Z'), how: 'gps' },
    ).state
    expect(seasonSummary(challenge, tagsFor(state, challenge.id))).toEqual({
      earned: 1,
      states: ['VA'],
      atHome: 0,
    })
  })

  it('names the season from the window', () => {
    expect(seasonWord({ opens: '2027-05-13', closes: '2027-09-07' })).toBe('summer')
    expect(seasonWord({ opens: '2027-09-20', closes: '2027-11-30' })).toBe('autumn')
    expect(seasonWord({ opens: null, closes: null })).toBe('season')
  })

  it('calls a window across the new year winter, and a whole year no one season (review of #2020)', () => {
    expect(seasonWord({ opens: '2027-11-15', closes: '2028-02-28' })).toBe('winter')
    expect(seasonWord({ opens: '2027-12-01', closes: '2028-03-31' })).toBe('winter')
    expect(seasonWord({ opens: '2027-01-01', closes: '2027-12-31' })).toBe('season')
  })
})

describe('where each earned item landed (#1965)', () => {
  it('asks the lookup it is given for a mile’s state, so the published runs replace the bands', () => {
    const tags = earned([
      { id: 'mcafee-knob' },
      { id: 'white-blaze-photo', place: { kind: 'here', mile: 719.6 } },
      { id: 'trivia-quiz' },
    ])
    const everywhereMaine = () => 'ME' as const
    const places = earnedPlaces(ATC_CHALLENGE, tags, everywhereMaine)
    expect(
      places.map((place) => [place.item.id, place.mile, place.state, place.onTrail]),
    ).toEqual([
      ['trivia-quiz', null, null, false],
      ['mcafee-knob', 714.92, 'ME', true],
      ['white-blaze-photo', 719.6, 'ME', true],
    ])
    expect(seasonSummary(ATC_CHALLENGE, tags, everywhereMaine).states).toEqual(['ME'])
  })
})
