import { describe, it, expect } from 'vitest'
import type { Challenge, ChallengeItem, ChallengePlace } from '../lib/challenges'
import {
  EMPTY_CHALLENGE_STATE,
  join,
  joinedChallenges,
  leave,
  tag,
  type ChallengeState,
} from '../lib/challengeProgress'
import { challengePinFeatures } from './challengePins'

// Which places the challenge layer pins, and which it fills (#1780,
// features/CHALLENGES.md frame #1). Three of these are the design's own
// "What proves it" lines: leaving a challenge removes its pins at once, a
// sealed mystery place draws nothing, and an off-trail place - a town - is
// still a place.

const TODAY = '2027-06-01'
const NOW = new Date('2027-06-01T18:00:00Z')

function place(poi: string, lon: number, lat: number, mile = 700): ChallengePlace {
  return { poi, name: `Name of ${poi}`, poiType: 'viewpoint', mile, lat, lon }
}

function placeItem(
  id: string,
  places: ChallengePlace[],
  extra: Partial<ChallengeItem> = {},
): ChallengeItem {
  return {
    id,
    section: 'experience',
    title: `Go to ${id}`,
    sealedTitle: null,
    note: null,
    noteBy: null,
    photo: null,
    match: {
      kind: places.length > 1 ? 'places_all' : 'place',
      radiusM: 150,
      offTrail: false,
      places,
    },
    mystery: null,
    ...extra,
  }
}

function challenge(id: string, items: ChallengeItem[], trail = 'AT'): Challenge {
  return {
    id,
    org: 'atc',
    orgName: 'Appalachian Trail Conservancy',
    orgShort: 'ATC',
    trail,
    name: `Challenge ${id}`,
    status: 'draft',
    summary: null,
    window: { opens: null, closes: null },
    finish: null,
    reward: null,
    photo: null,
    sections: [{ id: 'experience', title: 'Experience the A.T.', short: 'Anywhere' }],
    items,
    reviewed: '2026-09-30',
  }
}

const MCAFEE = place('atc_viewpoints:mcafee', -80.03, 37.39)
const TINKER = place('atc_viewpoints:tinker', -79.99, 37.44)
const DRAGONS = place('atc_viewpoints:dragons', -80.16, 37.34)
const MONSON = place('atc_communities:monson', -69.5, 45.28, 2077)

const TRIPLE_CROWN = placeItem('triple-crown', [DRAGONS, MCAFEE, TINKER])
const MCAFEE_ITEM = placeItem('mcafee-knob', [MCAFEE])
const SELF_REPORT: ChallengeItem = {
  ...placeItem('trivia', [MCAFEE]),
  match: { kind: 'self_report' },
}
const ANY_SHELTER: ChallengeItem = {
  ...placeItem('any-shelter', [MCAFEE]),
  match: { kind: 'poi_type', type: 'shelter', radiusM: 60 },
}

const BUCKET = challenge('bucket', [MCAFEE_ITEM, TRIPLE_CROWN, SELF_REPORT, ANY_SHELTER])

function joinedState(...ids: string[]): ChallengeState {
  return ids.reduce((state, id) => join(state, id, NOW), EMPTY_CHALLENGE_STATE)
}

function pins(joined: readonly Challenge[], state: ChallengeState, today = TODAY) {
  return challengePinFeatures(joined, state, today).features
}

function pinAt(joined: readonly Challenge[], state: ChallengeState, poi: string) {
  return pins(joined, state).find((feature) => feature.properties.poi === poi)
}

describe('challengePinFeatures', () => {
  it('draws one point per place of each place item, where the published POI is', () => {
    const features = pins([BUCKET], joinedState('bucket'))

    // McAfee Knob is named by two items and drawn once; the self-report line
    // and "any shelter" name no one place and draw nothing.
    expect(features.map((feature) => feature.properties.poi).sort()).toEqual(
      [MCAFEE.poi, TINKER.poi, DRAGONS.poi].sort(),
    )
    const mcafee = features.find((feature) => feature.properties.poi === MCAFEE.poi)!
    expect(mcafee.geometry).toEqual({
      type: 'Point',
      coordinates: [MCAFEE.lon, MCAFEE.lat],
    })
    expect(mcafee.properties).toEqual({
      poi: MCAFEE.poi,
      name: MCAFEE.name,
      tagged: false,
      // The first item naming it, in published order.
      challengeId: 'bucket',
      itemId: 'mcafee-knob',
    })
  })

  it('takes a challenge’s pins off the map the moment the hiker leaves it', () => {
    const other = challenge('club-list', [placeItem('monson', [MONSON])])
    const all = [BUCKET, other]
    const state = joinedState('bucket', 'club-list')
    expect(pins(joinedChallenges(all, state), state)).toHaveLength(4)

    const left = leave(state, 'bucket')

    expect(
      pins(joinedChallenges(all, left), left).map((feature) => feature.properties.poi),
    ).toEqual([MONSON.poi])
  })

  it('draws nothing for a challenge nobody joined', () => {
    expect(pins([], EMPTY_CHALLENGE_STATE)).toEqual([])
  })

  it('draws no pin for a sealed mystery place, and draws it from its reveal date', () => {
    // A pin at a place is the answer to the mystery, so it waits exactly as
    // the title does (lib/challenges.ts's isSealed).
    const mystery = placeItem('mystery-1', [MONSON], {
      title: null,
      sealedTitle: btoa('Visit Monson'),
      mystery: { number: 1, revealOn: '2027-07-20' },
    })
    const withMystery = challenge('bucket', [mystery])
    const state = joinedState('bucket')

    expect(pins([withMystery], state, '2027-07-19')).toEqual([])
    expect(
      pins([withMystery], state, '2027-07-20').map((feature) => feature.properties.poi),
    ).toEqual([MONSON.poi])
  })

  it('never draws a mystery the club has given no date, which stays sealed', () => {
    const undated = placeItem('mystery-2', [MONSON], {
      title: null,
      mystery: { number: 2, revealOn: null },
    })
    expect(
      pins([challenge('bucket', [undated])], joinedState('bucket'), '2099-01-01'),
    ).toEqual([])
  })

  it('still draws a place off the trail - a town can only be tagged by hand, but it is there', () => {
    const town: ChallengeItem = {
      ...placeItem('monson-visitor-center', [MONSON]),
      match: { kind: 'place', radiusM: 800, offTrail: true, places: [MONSON] },
    }
    expect(
      pins([challenge('bucket', [town])], joinedState('bucket')).map(
        (f) => f.properties.poi,
      ),
    ).toEqual([MONSON.poi])
  })

  it('fills a place once the hiker has tagged it, and leaves the rest hollow', () => {
    const tagged = tag(joinedState('bucket'), BUCKET, TRIPLE_CROWN, {
      poi: DRAGONS.poi,
      at: NOW,
      how: 'hand',
    }).state

    // Dragon's Tooth is tagged for the Triple Crown even though the item is
    // not done until the other two are: the pin is about the place.
    expect(pinAt([BUCKET], tagged, DRAGONS.poi)?.properties.tagged).toBe(true)
    expect(pinAt([BUCKET], tagged, TINKER.poi)?.properties.tagged).toBe(false)
  })

  it('keeps a place hollow until every item there is done', () => {
    // McAfee Knob is its own item and a third of the Triple Crown. Tagging
    // one of them leaves the other owed, and a filled pin would say nothing
    // was left to do there.
    let state = joinedState('bucket')
    state = tag(state, BUCKET, MCAFEE_ITEM, { at: NOW, how: 'gps' }).state
    expect(pinAt([BUCKET], state, MCAFEE.poi)?.properties.tagged).toBe(false)

    state = tag(state, BUCKET, TRIPLE_CROWN, {
      poi: MCAFEE.poi,
      at: NOW,
      how: 'gps',
    }).state
    expect(pinAt([BUCKET], state, MCAFEE.poi)?.properties.tagged).toBe(true)
  })

  it('draws a place two challenges share once, filled only when both are done', () => {
    const second = challenge('club-list', [placeItem('club-mcafee', [MCAFEE])])
    let state = joinedState('bucket', 'club-list')
    state = tag(state, BUCKET, MCAFEE_ITEM, { at: NOW, how: 'gps' }).state
    state = tag(state, BUCKET, TRIPLE_CROWN, {
      poi: MCAFEE.poi,
      at: NOW,
      how: 'gps',
    }).state

    const shared = pins([BUCKET, second], state).filter(
      (f) => f.properties.poi === MCAFEE.poi,
    )
    expect(shared).toHaveLength(1)
    expect(shared[0].properties.tagged).toBe(false)

    state = tag(state, second, second.items[0], { at: NOW, how: 'hand' }).state
    expect(pinAt([BUCKET, second], state, MCAFEE.poi)?.properties.tagged).toBe(true)
  })

  it('draws a place-kind item naming alternatives as done at each once it is done', () => {
    // A `place` item with two places is "either of these"; once it is done,
    // neither is still owed.
    const either: ChallengeItem = {
      ...placeItem('either', [TINKER]),
      match: { kind: 'place', radiusM: 150, offTrail: false, places: [TINKER, DRAGONS] },
    }
    const list = challenge('bucket', [either])
    const state = tag(joinedState('bucket'), list, either, { at: NOW, how: 'hand' }).state

    expect(pins([list], state).map((f) => f.properties.tagged)).toEqual([true, true])
  })
})
