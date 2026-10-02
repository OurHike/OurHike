import { describe, expect, it } from 'vitest'
import { ATC_CHALLENGE, RECORD_CHALLENGE } from './challenges.fixtures'
import {
  EMPTY_CHALLENGE_STATE,
  autoTags,
  browse,
  doneItems,
  hideSuggestion,
  isItemDone,
  join,
  joinedChallenges,
  leave,
  matchDay,
  planRows,
  progress,
  removeTag,
  setRegisterNote,
  storedChallengeState,
  suggestion,
  tag,
  untag,
  type ChallengeState,
} from './challengeProgress'
import { localDay } from './passedToday'

const NOW = new Date('2027-07-14T22:00:00Z')
const TODAY = '2027-07-14'
const item = (id: string) => ATC_CHALLENGE.items.find((entry) => entry.id === id)!
const joinedAtc = join(
  EMPTY_CHALLENGE_STATE,
  ATC_CHALLENGE.id,
  new Date('2027-06-01T12:00:00Z'),
)
const SHELTERS = [
  { id: 'atc_shelters:campbell', type: 'shelter', name: 'Campbell Shelter', mile: 713.9 },
  { id: 'atc_shelters:far', type: 'shelter', name: 'Far Shelter', mile: 900 },
]

describe('joining and leaving', () => {
  it('lists only the joined challenges', () => {
    expect(
      joinedChallenges([ATC_CHALLENGE, RECORD_CHALLENGE], joinedAtc).map((c) => c.id),
    ).toEqual([ATC_CHALLENGE.id])
  })

  it('joining twice changes nothing', () => {
    expect(join(joinedAtc, ATC_CHALLENGE.id, NOW)).toBe(joinedAtc)
  })

  it('leaving removes the camp-card rows at once and keeps the tags', () => {
    const tagged = tag(joinedAtc, ATC_CHALLENGE, item('springer-mountain'), {
      at: NOW,
      how: 'hand',
    }).state
    const left = leave(tagged, ATC_CHALLENGE.id)
    const input = {
      state: left,
      todayRanges: [{ startMile: 710, endMile: 716 }],
      trail: 'AT',
      pois: SHELTERS,
      today: TODAY,
    }
    expect(
      matchDay({ ...input, joined: joinedChallenges([ATC_CHALLENGE], left) }),
    ).toEqual([])
    expect(left.tags).toHaveLength(1)
  })
})

describe('tagging', () => {
  it('completes a single place on its one tag, and says so once', () => {
    const first = tag(joinedAtc, ATC_CHALLENGE, item('mcafee-knob'), {
      at: NOW,
      how: 'gps',
    })
    expect(first.completed).toBe(true)
    const again = tag(first.state, ATC_CHALLENGE, item('mcafee-knob'), {
      at: NOW,
      how: 'gps',
    })
    expect(again.completed).toBe(false)
    expect(again.state).toBe(first.state)
  })

  it('completes a Triple Crown only on its last peak, whatever days they fall on', () => {
    const crown = item('virginia-triple-crown')
    const places = crown.match.kind === 'places_all' ? crown.match.places : []
    let state = joinedAtc
    const completions = places.map((place, index) => {
      const result = tag(state, ATC_CHALLENGE, crown, {
        poi: place.poi,
        at: new Date(NOW.getTime() + index * 86_400_000),
        how: 'gps',
      })
      state = result.state
      return result.completed
    })
    expect(completions).toEqual([false, false, true])
    expect(isItemDone(crown, ATC_CHALLENGE.id, state.tags)).toBe(true)
  })

  it('un-tags a hand tag and leaves a tag the walk made', () => {
    const hand = tag(joinedAtc, ATC_CHALLENGE, item('trivia-quiz'), {
      at: NOW,
      how: 'hand',
    }).state
    expect(untag(hand, ATC_CHALLENGE.id, 'trivia-quiz').tags).toHaveLength(0)
    const walked = tag(joinedAtc, ATC_CHALLENGE, item('mcafee-knob'), {
      at: NOW,
      how: 'gps',
    }).state
    expect(untag(walked, ATC_CHALLENGE.id, 'mcafee-knob')).toBe(walked)
  })

  it('un-tags one Triple Crown peak from its own card and keeps the other two', () => {
    const crown = item('virginia-triple-crown')
    const places = crown.match.kind === 'places_all' ? crown.match.places : []
    let state = joinedAtc
    for (const place of places) {
      state = tag(state, ATC_CHALLENGE, crown, {
        poi: place.poi,
        at: NOW,
        how: 'hand',
      }).state
    }
    const after = untag(state, ATC_CHALLENGE.id, crown.id, places[1].poi)
    expect(after.tags.map((entry) => entry.poi)).toEqual([places[0].poi, places[2].poi])
  })

  it("un-tags a single place's hand tag from that place's own card", () => {
    // A tag of any kind but places_all is stored with no place, so the card's
    // POI id must not be what decides whether it matches.
    const knob = item('mcafee-knob')
    const poi = knob.match.kind === 'place' ? knob.match.places[0].poi : ''
    const hand = tag(joinedAtc, ATC_CHALLENGE, knob, { poi, at: NOW, how: 'hand' }).state
    expect(hand.tags[0].poi).toBeUndefined()
    expect(untag(hand, ATC_CHALLENGE.id, knob.id, poi).tags).toHaveLength(0)
    expect(removeTag(hand, ATC_CHALLENGE.id, knob.id, poi).tags).toHaveLength(0)
  })

  it('keeps the register line on the tag and nowhere else', () => {
    const tagged = tag(joinedAtc, ATC_CHALLENGE, item('mcafee-knob'), {
      at: NOW,
      how: 'gps',
    }).state
    const noted = setRegisterNote(
      tagged,
      ATC_CHALLENGE.id,
      'mcafee-knob',
      'Fog burned off right as we got there.',
    )
    expect(noted.tags[0].note).toBe('Fog burned off right as we got there.')
    expect(
      setRegisterNote(noted, ATC_CHALLENGE.id, 'mcafee-knob', '   ').tags[0].note,
    ).toBeUndefined()
  })
})

describe('progress', () => {
  it('counts the challenge’s own items against its own finish line', () => {
    let state = joinedAtc
    for (const id of [
      'springer-mountain',
      'mcafee-knob',
      'trivia-quiz',
      'white-blaze-photo',
      'pick-up-litter',
    ]) {
      state = tag(state, ATC_CHALLENGE, item(id), { at: NOW, how: 'hand' }).state
    }
    expect(progress(ATC_CHALLENGE, state)).toEqual({
      tagged: 5,
      finish: 5,
      eligible: true,
    })
  })

  it('never makes a record eligible for anything', () => {
    expect(progress(RECORD_CHALLENGE, EMPTY_CHALLENGE_STATE)).toEqual({
      tagged: 0,
      finish: null,
      eligible: false,
    })
  })

  it('never compares one hiker to anyone - its answer holds only their own counts', () => {
    // VOLUNTEERING.md §5 rule 1: there is no field in which a comparison
    // could hide, and this pins the shape so one cannot be added quietly.
    expect(Object.keys(progress(ATC_CHALLENGE, joinedAtc)).sort()).toEqual([
      'eligible',
      'finish',
      'tagged',
    ])
  })

  it('lists done items in the order they were done', () => {
    let state = tag(joinedAtc, ATC_CHALLENGE, item('mcafee-knob'), {
      at: new Date('2027-07-14T10:00:00Z'),
      how: 'gps',
    }).state
    state = tag(state, ATC_CHALLENGE, item('springer-mountain'), {
      at: new Date('2027-07-02T10:00:00Z'),
      how: 'gps',
    }).state
    expect(doneItems(ATC_CHALLENGE, state).map((entry) => entry.item.id)).toEqual([
      'springer-mountain',
      'mcafee-knob',
    ])
  })
})

describe('matchDay - the camp card lists what was passed and nothing else', () => {
  const day = (state: ChallengeState, startMile: number, endMile: number) =>
    matchDay({
      joined: joinedChallenges([ATC_CHALLENGE], state),
      state,
      todayRanges: [{ startMile, endMile }],
      trail: 'AT',
      pois: SHELTERS,
      today: TODAY,
    })

  it('offers a named place whose mile the day’s walk covered', () => {
    const rows = day(joinedAtc, 710, 716)
    expect(rows.map((row) => row.item.id)).toContain('mcafee-knob')
  })

  it('offers "any shelter" with the shelter the walk passed', () => {
    const shelterRow = day(joinedAtc, 710, 716).find(
      (row) => row.item.id === 'shelter-logbook',
    )
    expect(shelterRow?.place.name).toBe('Campbell Shelter')
  })

  it('offers each Triple Crown peak walked today, and not the ones that were not', () => {
    const peaks = day(joinedAtc, 710, 716).filter(
      (row) => row.item.id === 'virginia-triple-crown',
    )
    expect(peaks.map((row) => row.place.name)).toEqual(['McAfee Knob Summit'])
  })

  it('offers nothing when nothing was passed - no list of what was missed exists to show', () => {
    expect(day(joinedAtc, 1000, 1005)).toEqual([])
  })

  it('never offers a town, which a mile interval cannot place a hiker in', () => {
    expect(day(joinedAtc, 2070, 2090).map((row) => row.item.id)).not.toContain(
      'monson-visitor-center',
    )
  })

  it('never offers an at-home item, a sealed mystery or a self-tagging kind', () => {
    const ids = day(joinedAtc, 0, 2200).map((row) => row.item.id)
    for (const id of [
      'trivia-quiz',
      'mystery-1',
      'mystery-2',
      'summit-4000',
      'trail-crew',
    ])
      expect(ids).not.toContain(id)
  })

  it('stops offering what is already tagged', () => {
    const tagged = tag(joinedAtc, ATC_CHALLENGE, item('mcafee-knob'), {
      at: NOW,
      how: 'hand',
    }).state
    expect(day(tagged, 710, 716).map((row) => row.item.id)).not.toContain('mcafee-knob')
  })

  it('offers nothing on a day outside the challenge’s window', () => {
    const before = matchDay({
      joined: [ATC_CHALLENGE],
      state: joinedAtc,
      todayRanges: [{ startMile: 710, endMile: 716 }],
      trail: 'AT',
      pois: SHELTERS,
      today: '2027-05-14',
    })
    expect(before).toEqual([])
  })

  it('reads miles only against the trail they were measured on', () => {
    expect(
      matchDay({
        joined: [ATC_CHALLENGE],
        state: joinedAtc,
        todayRanges: [{ startMile: 710, endMile: 716 }],
        trail: 'LP',
        pois: [],
        today: TODAY,
      }),
    ).toEqual([])
  })
})

describe('autoTags - the items that tag themselves', () => {
  const base = {
    joined: [ATC_CHALLENGE],
    trail: 'AT',
    today: TODAY,
    maxElevationFt: () => 3_197,
    hours: [] as {
      workedOn: string
      mile: number | null
      clubName: string | null
      disputed: boolean
    }[],
  }

  it('tags a 4,000 ft summit when the day’s miles reach it, and not below it', () => {
    const low = autoTags(
      { ...base, state: joinedAtc, todayRanges: [{ startMile: 710, endMile: 716 }] },
      NOW,
    )
    expect(low.completed).toEqual([])
    const high = autoTags(
      {
        ...base,
        maxElevationFt: () => 4_010,
        state: joinedAtc,
        todayRanges: [{ startMile: 1860, endMile: 1866 }],
      },
      NOW,
    )
    expect(high.completed.map((done) => done.item.id)).toEqual(['summit-4000'])
  })

  it('tags a Trail Crew item from logged hours on the trail since joining, and never from disputed ones', () => {
    const disputed = autoTags(
      {
        ...base,
        state: joinedAtc,
        todayRanges: [],
        hours: [{ workedOn: '2027-06-20', mile: 1400, clubName: null, disputed: true }],
      },
      NOW,
    )
    expect(disputed.completed).toEqual([])
    const before = autoTags(
      {
        ...base,
        state: joinedAtc,
        todayRanges: [],
        hours: [{ workedOn: '2027-05-01', mile: 1400, clubName: null, disputed: false }],
      },
      NOW,
    )
    expect(before.completed).toEqual([])
    const logged = autoTags(
      {
        ...base,
        state: joinedAtc,
        todayRanges: [],
        hours: [{ workedOn: '2027-06-20', mile: 1400, clubName: null, disputed: false }],
      },
      NOW,
    )
    expect(logged.completed.map((done) => done.item.id)).toEqual(['trail-crew'])
  })

  it('answers one workday item per logged day, in published order', () => {
    const workday = (id: string) => ({
      id,
      section: 'protect',
      title: id,
      sealedTitle: null,
      note: null,
      noteBy: null,
      photo: null,
      mystery: null,
      match: { kind: 'workday' as const, org: null, trail: 'AT' },
    })
    const three = {
      ...ATC_CHALLENGE,
      items: [
        ...ATC_CHALLENGE.items.filter((entry) => entry.match.kind !== 'workday'),
        workday('volunteer-event'),
        workday('trail-crew'),
        workday('invasive-removal'),
      ],
    }
    const logged = (...days: string[]) =>
      autoTags(
        {
          ...base,
          joined: [three],
          state: joinedAtc,
          todayRanges: [],
          hours: days.map((workedOn) => ({
            workedOn,
            mile: 1400,
            clubName: null,
            disputed: false,
          })),
        },
        NOW,
      ).completed.map((done) => done.item.id)
    expect(logged('2027-06-20')).toEqual(['volunteer-event'])
    // Two records on one day are still one day.
    expect(logged('2027-06-20', '2027-06-20')).toEqual(['volunteer-event'])
    expect(logged('2027-06-20', '2027-06-27')).toEqual(['volunteer-event', 'trail-crew'])
  })

  it('reads a summit only on a day the challenge is open', () => {
    const early = autoTags(
      {
        ...base,
        today: '2027-05-14',
        maxElevationFt: () => 4_010,
        state: joinedAtc,
        todayRanges: [{ startMile: 1860, endMile: 1866 }],
      },
      NOW,
    )
    expect(early.completed).toEqual([])
  })
})

describe('Plan', () => {
  const days = [
    { dayNumber: 5, startMile: 699, endMile: 713.9 },
    { dayNumber: 6, startMile: 713.9, endMile: 728 },
  ]

  it('lays a challenge’s places on the plan’s days', () => {
    const rows = planRows(ATC_CHALLENGE, days, TODAY)
    expect(rows.map((row) => [row.dayNumber, row.place.name])).toEqual([
      [5, 'Dragons Tooth Peak'],
      [6, 'McAfee Knob Summit'],
      [6, 'McAfee Knob Summit'],
      [6, 'Tinker Cliffs 2'],
    ])
  })

  it('suggests the one best challenge when none joined touches the route', () => {
    const picked = suggestion({
      challenges: [RECORD_CHALLENGE, ATC_CHALLENGE],
      state: EMPTY_CHALLENGE_STATE,
      days,
      hikeKey: 'hike-1',
      today: TODAY,
      maintainedMiles: () => 0,
    })
    expect(picked?.challenge.id).toBe(ATC_CHALLENGE.id)
  })

  it('suggests nothing once a joined challenge touches the route', () => {
    expect(
      suggestion({
        challenges: [RECORD_CHALLENGE, ATC_CHALLENGE],
        state: joinedAtc,
        days,
        hikeKey: 'hike-1',
        today: TODAY,
        maintainedMiles: () => 0,
      }),
    ).toBeNull()
  })

  it('remembers a hidden suggestion for that hike only', () => {
    const hidden = hideSuggestion(EMPTY_CHALLENGE_STATE, 'hike-1', ATC_CHALLENGE.id)
    const args = {
      challenges: [ATC_CHALLENGE],
      state: hidden,
      days,
      today: TODAY,
      maintainedMiles: () => 0,
    }
    expect(suggestion({ ...args, hikeKey: 'hike-1' })).toBeNull()
    expect(suggestion({ ...args, hikeKey: 'hike-2' })?.challenge.id).toBe(
      ATC_CHALLENGE.id,
    )
  })
})

describe('browse', () => {
  const days = [{ dayNumber: 1, startMile: 635.4, endMile: 727.5 }]

  it('puts what touches the plan first, then the rest by distance, never by popularity', () => {
    const groups = browse({
      challenges: [ATC_CHALLENGE, RECORD_CHALLENGE],
      filters: { trail: 'AT', org: null, openNow: false },
      days,
      today: TODAY,
    })
    expect(groups.onPlan.map((entry) => entry.challenge.id)).toEqual([
      ATC_CHALLENGE.id,
      RECORD_CHALLENGE.id,
    ])
    expect(groups.onPlan[0].placesOnPlan).toBe(4)
  })

  it('narrows by club and by what is open today, and counts what the trail filter hides', () => {
    const club = browse({
      challenges: [ATC_CHALLENGE, RECORD_CHALLENGE],
      filters: { trail: null, org: 'rac', openNow: false },
      days: [],
      today: TODAY,
    })
    expect(club.elsewhere.map((entry) => entry.challenge.id)).toEqual([
      RECORD_CHALLENGE.id,
    ])
    const open = browse({
      challenges: [ATC_CHALLENGE],
      filters: { trail: null, org: null, openNow: true },
      days: [],
      today: '2027-10-01',
    })
    expect(open.elsewhere).toEqual([])
    const otherTrail = browse({
      challenges: [ATC_CHALLENGE],
      filters: { trail: 'LP', org: null, openNow: false },
      days: [],
      today: TODAY,
    })
    expect(otherTrail.hiddenByTrail).toBe(1)
  })
})

describe('the stored record', () => {
  it('reads back what it wrote and drops what it cannot read', () => {
    const tagged = tag(joinedAtc, ATC_CHALLENGE, item('mcafee-knob'), {
      at: NOW,
      how: 'gps',
    }).state
    expect(storedChallengeState(JSON.parse(JSON.stringify(tagged)))).toEqual(tagged)
    const damaged = storedChallengeState({
      joined: [{ challengeId: 1 }],
      tags: [{ challengeId: 'x' }],
      layerShown: 'yes',
    })
    expect(damaged.joined).toEqual([])
    expect(damaged.tags).toEqual([])
    expect(damaged.layerShown).toBe(false)
  })

  it('defaults the map layer off', () => {
    expect(storedChallengeState(undefined).layerShown).toBe(false)
  })
})

describe('the edges of plan suggestions, Browse distance, workday stamps and removeTag', () => {
  const OTHER_TRAIL = { ...ATC_CHALLENGE, id: 'lp-list', trail: 'LP' }

  it('lays nothing from another trail on an A.T. plan, however its miles line up', () => {
    const days = [{ dayNumber: 1, startMile: 700, endMile: 725 }]
    expect(planRows(OTHER_TRAIL, days, TODAY, 'AT')).toEqual([])
    expect(planRows(ATC_CHALLENGE, days, TODAY, 'AT').length).toBeGreaterThan(0)
  })

  it('never suggests a challenge that has closed', () => {
    const picked = suggestion({
      challenges: [ATC_CHALLENGE],
      state: EMPTY_CHALLENGE_STATE,
      days: [{ dayNumber: 1, startMile: 700, endMile: 725 }],
      hikeKey: 'hike',
      today: '2027-09-02',
      maintainedMiles: () => 0,
    })
    expect(picked).toBeNull()
  })

  it("measures Browse distance from the nearest planned day to the list's nearest place", () => {
    const groups = browse({
      challenges: [ATC_CHALLENGE],
      filters: { trail: null, org: null, openNow: false },
      // A gap from 600 to 900 holds McAfee Knob (mile 714.9) between two days.
      days: [
        { dayNumber: 1, startMile: 590, endMile: 600 },
        { dayNumber: 2, startMile: 900, endMile: 910 },
      ],
      today: TODAY,
      planTrail: 'AT',
    })
    const [entry] = groups.elsewhere
    // Dragon's Tooth (mile 703.114) is the list's nearest place, 103.114
    // miles past day 1's end - not McAfee Knob, and not zero.
    expect(entry.milesFromPlan).toBeCloseTo(103.114, 3)
  })

  it('never offers an off-trail "any waypoint" item at camp', () => {
    const towns = {
      ...ATC_CHALLENGE,
      items: ATC_CHALLENGE.items.map((entry) =>
        entry.match.kind === 'poi_type'
          ? { ...entry, match: { ...entry.match, offTrail: true } }
          : entry,
      ),
    }
    const rows = matchDay({
      joined: [towns],
      state: joinedAtc,
      todayRanges: [{ startMile: 710, endMile: 716 }],
      trail: 'AT',
      pois: SHELTERS,
      today: TODAY,
    })
    expect(rows.some((row) => row.item.match.kind === 'poi_type')).toBe(false)
  })

  it('stamps a workday tag on the day worked, not the day the phone noticed', () => {
    const result = autoTags(
      {
        joined: [ATC_CHALLENGE],
        state: joinedAtc,
        todayRanges: [],
        trail: 'AT',
        today: '2027-09-05',
        maxElevationFt: () => null,
        hours: [{ workedOn: '2027-08-31', mile: 1400, clubName: null, disputed: false }],
      },
      new Date('2027-09-05T20:00:00Z'),
    )
    const made = result.state.tags.find((entry) => entry.itemId === 'trail-crew')
    expect(made).toBeDefined()
    expect(localDay(new Date(made!.at))).toBe('2027-08-31')
  })

  it("never stamps today's workday later than the moment it was noticed", () => {
    // Hours for today logged at 9 am: noon has not happened yet.
    const morning = new Date(2027, 7, 20, 9, 0)
    const result = autoTags(
      {
        joined: [ATC_CHALLENGE],
        state: joinedAtc,
        todayRanges: [],
        trail: 'AT',
        today: '2027-08-20',
        maxElevationFt: () => null,
        hours: [{ workedOn: '2027-08-20', mile: 1400, clubName: null, disputed: false }],
      },
      morning,
    )
    const made = result.state.tags.find((entry) => entry.itemId === 'trail-crew')
    expect(made?.at).toBe(morning.toISOString())
  })

  it('counts no workday for a challenge with no join record', () => {
    const result = autoTags(
      {
        joined: [ATC_CHALLENGE],
        state: EMPTY_CHALLENGE_STATE,
        todayRanges: [],
        trail: 'AT',
        today: TODAY,
        maxElevationFt: () => null,
        hours: [{ workedOn: '2020-06-01', mile: 1400, clubName: null, disputed: false }],
      },
      NOW,
    )
    expect(result.completed).toEqual([])
  })

  it('takes a walked tag back with removeTag, which untag will not', () => {
    const walked = tag(joinedAtc, ATC_CHALLENGE, item('mcafee-knob'), {
      at: NOW,
      how: 'gps',
    }).state
    expect(untag(walked, ATC_CHALLENGE.id, 'mcafee-knob')).toBe(walked)
    expect(removeTag(walked, ATC_CHALLENGE.id, 'mcafee-knob').tags).toHaveLength(0)
  })
})
