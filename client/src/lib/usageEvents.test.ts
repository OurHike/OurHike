import { describe, expect, it } from 'vitest'

import {
  CLUB_NOT_RECORDED,
  type ClubRunLike,
  clubAtTrailMile,
  clubId,
  FIX_MAX_AGE_MS,
  FRESH_HEARTBEAT,
  isoWeek,
  LEVEL_ONLY_EVENTS,
  milesByClub,
  NO_STAMP,
  sessionLength,
  sharesFromMiles,
  stampHeartbeat,
  USAGE_EVENTS,
  usableFix,
  usageDate,
  usageRow,
  usageVersion,
} from './usageEvents'

// The phone's half of usage measurement (#1902, features/EVENTING.md §0).
// What each test below pins is a promise a hiker was made or a number the
// report depends on: the heartbeat that counts phones without telling them
// apart, the fix that only ever describes the moment it was taken, and the
// club split the maintainer confirmed against a drawn example.

const RUNS: ClubRunLike[] = [
  { startMile: 1380, endMile: 1400, club: { acronym: 'NYNJTC' } },
  { startMile: 1400, endMile: 1402, club: null },
  { startMile: 1402, endMile: 1450, club: { acronym: 'AMC-NY' } },
]

describe('the registry', () => {
  it('names the six events #1902 asked to count, and the support choice #1876 added', () => {
    expect([...USAGE_EVENTS]).toEqual([
      'app_installed',
      'user_login',
      'hike_plan_made',
      'hike_plan_completed',
      'map_screen_viewed',
      'session',
      'support_chosen',
    ])
  })

  it('stamps a level-only row with no heartbeat flag', () => {
    expect(LEVEL_ONLY_EVENTS).toEqual(['support_chosen'])
    expect(Object.values(NO_STAMP).filter((flag) => flag === true)).toEqual([])
    expect(NO_STAMP.club_firsts).toEqual([])
  })
})

describe('isoWeek', () => {
  it('puts a Tuesday in late October 2026 in week 44', () => {
    expect(isoWeek(new Date(2026, 9, 27))).toBe('2026-W44')
  })

  it('keeps New Year 2027, a Friday, in the 53rd week of 2026', () => {
    expect(isoWeek(new Date(2027, 0, 1))).toBe('2026-W53')
    expect(isoWeek(new Date(2027, 0, 4))).toBe('2027-W01')
  })

  it('keeps a Saturday and the Sunday after it in one week', () => {
    expect(isoWeek(new Date(2026, 9, 24))).toBe(isoWeek(new Date(2026, 9, 25)))
  })
})

describe('stampHeartbeat', () => {
  const view = 'map_screen_viewed' as const

  it('marks a phone’s first event ever as first of the week, the month and ever', () => {
    const { stamp } = stampHeartbeat(FRESH_HEARTBEAT, new Date(2026, 9, 27), [], view)

    expect(stamp).toEqual({
      week_first: true,
      month_first: true,
      ever_first: true,
      club_firsts: [],
      kind_month_first: true,
      month_returning: false,
    })
  })

  it('marks nothing on a second event of the same kind the same day', () => {
    const first = stampHeartbeat(FRESH_HEARTBEAT, new Date(2026, 9, 27), [], view)
    const { stamp } = stampHeartbeat(first.next, new Date(2026, 9, 27, 18), [], view)

    expect(stamp).toEqual({
      week_first: false,
      month_first: false,
      ever_first: false,
      club_firsts: [],
      kind_month_first: false,
      month_returning: false,
    })
  })

  it('marks a different kind of event as that kind’s first this month', () => {
    const first = stampHeartbeat(FRESH_HEARTBEAT, new Date(2026, 9, 27), [], view)
    const { stamp } = stampHeartbeat(
      first.next,
      new Date(2026, 9, 28),
      [],
      'hike_plan_made',
    )

    expect(stamp.kind_month_first).toBe(true)
    expect(stamp.month_first).toBe(false)
  })

  it('marks only the week when a new week starts inside the same month', () => {
    const first = stampHeartbeat(FRESH_HEARTBEAT, new Date(2026, 9, 14), [], view)
    const { stamp } = stampHeartbeat(first.next, new Date(2026, 9, 21), [], view)

    expect(stamp.week_first).toBe(true)
    expect(stamp.month_first).toBe(false)
  })

  it('counts a club once a month per phone, and again the next month', () => {
    const october = stampHeartbeat(
      FRESH_HEARTBEAT,
      new Date(2026, 9, 3),
      ['NYNJTC'],
      view,
    )
    const again = stampHeartbeat(
      october.next,
      new Date(2026, 9, 9),
      ['NYNJTC', 'GATC'],
      view,
    )
    const november = stampHeartbeat(again.next, new Date(2026, 10, 2), ['NYNJTC'], view)

    expect(october.stamp.club_firsts).toEqual(['NYNJTC'])
    expect(again.stamp.club_firsts).toEqual(['GATC'])
    expect(november.stamp.club_firsts).toEqual(['NYNJTC'])
    expect(november.stamp.month_returning).toBe(true)
  })

  it('does not count a visit from Sunday night twice when it is recorded after Monday’s first row', () => {
    // The ordering that double-counted every phone whose visit crossed a
    // week boundary before the heartbeat kept sets (usageHeartbeat.test.ts).
    const sunday = new Date(2026, 9, 25, 23, 40)
    const monday = new Date(2026, 9, 26, 0, 20)
    const sundayView = stampHeartbeat(FRESH_HEARTBEAT, sunday, [], view)
    const mondayView = stampHeartbeat(sundayView.next, monday, [], view)
    const visit = stampHeartbeat(mondayView.next, sunday, [], 'session')
    const later = stampHeartbeat(visit.next, new Date(2026, 9, 26, 9), [], view)

    expect([sundayView, mondayView, visit, later].map((s) => s.stamp.week_first)).toEqual(
      [true, true, false, false],
    )
  })
})

describe('sessionLength', () => {
  it('buckets a visit rather than sending its seconds', () => {
    expect(sessionLength(30_000)).toBe('under_1m')
    expect(sessionLength(3 * 60_000)).toBe('m1_to_5')
    expect(sessionLength(12 * 60_000)).toBe('m5_to_20')
    expect(sessionLength(45 * 60_000)).toBe('over_20m')
  })
})

describe('usableFix', () => {
  const now = new Date(2026, 9, 27, 12, 0)
  const fresh = {
    lat: 41.29871,
    lon: -74.1881,
    accuracy: 12,
    at: new Date(2026, 9, 27, 11, 58),
  }

  it('sends a fix the map already holds, exactly as it holds it', () => {
    expect(usableFix(fresh, now)).toEqual({
      lat: 41.29871,
      lon: -74.1881,
      accuracy_m: 12,
    })
  })

  it('sends no fix when location is off and the map holds none', () => {
    expect(usableFix(null, now)).toBeUndefined()
  })

  it('sends no fix older than ten minutes, which says where the phone was rather than is', () => {
    const stale = { ...fresh, at: new Date(now.getTime() - FIX_MAX_AGE_MS - 1) }

    expect(usableFix(stale, now)).toBeUndefined()
  })

  it('sends no fix vaguer than 100 m', () => {
    expect(usableFix({ ...fresh, accuracy: 250 }, now)).toBeUndefined()
  })

  it('sends no fix taken after the moment the event describes', () => {
    const later = { ...fresh, at: new Date(now.getTime() + 60_000) }

    expect(usableFix(later, now)).toBeUndefined()
  })
})

describe('clubs', () => {
  it('passes ATC’s acronyms through and drops what the server would refuse', () => {
    expect(clubId('NYNJTC')).toBe('NYNJTC')
    expect(clubId('AMC-WMA')).toBe('AMC-WMA')
    expect(clubId('NY NJ Trail Conf.')).toBe('NYNJTrailConf.')
    expect(clubId('—')).toBeNull()
    expect(clubId(null)).toBeNull()
  })

  it('names the club at a mile, and says "not recorded" where ATC does not', () => {
    expect(clubAtTrailMile(RUNS, 1390)).toBe('NYNJTC')
    expect(clubAtTrailMile(RUNS, 1401)).toBe(CLUB_NOT_RECORDED)
    expect(clubAtTrailMile(RUNS, 1450)).toBe('AMC-NY')
    expect(clubAtTrailMile(RUNS, 1200)).toBeNull()
  })

  it('splits a 30-mile plan as 20 miles in one club and 10 in the next', () => {
    const miles = milesByClub(RUNS, 1380, 1410)

    expect(miles).toEqual({ NYNJTC: 20, [CLUB_NOT_RECORDED]: 2, 'AMC-NY': 8 })
  })

  it('splits a southbound plan the same as a northbound one', () => {
    expect(milesByClub(RUNS, 1410, 1380)).toEqual(milesByClub(RUNS, 1380, 1410))
  })

  it('turns miles into shares that add up to exactly one plan', () => {
    const shares = sharesFromMiles({ NYNJTC: 20, 'AMC-NY': 10 }) ?? {}

    expect(shares.NYNJTC).toBeCloseTo(2 / 3, 3)
    expect(Object.values(shares).reduce((sum, share) => sum + share, 0)).toBeCloseTo(
      1,
      10,
    )
  })

  it('gives a plan on no club’s trail no clubs at all', () => {
    expect(sharesFromMiles({})).toBeUndefined()
  })

  it('never sends a share of zero for a plan ending a sliver past a club boundary, which the server would refuse', () => {
    // #1903's review: 480.1 to 512.3000000001 on the A.T. came out
    // {GATC: 1, NYNJTC: 0}, and the row was refused and dropped.
    const shares = sharesFromMiles({ GATC: 32.2, NYNJTC: 1e-10 }) ?? {}

    expect(shares).toEqual({ GATC: 1 })
  })

  it('keeps every share above zero and summing to one across many clubs and uneven miles', () => {
    let seed = 1902
    const random = () => {
      seed = (seed * 16807) % 2147483647
      return seed / 2147483647
    }
    for (let plan = 0; plan < 2_000; plan += 1) {
      const miles: Record<string, number> = {}
      const clubs = 2 + Math.floor(random() * 11)
      for (let club = 0; club < clubs; club += 1)
        miles[`C${club}`] = club === 0 ? random() * 0.3 : random() * 40
      const shares = sharesFromMiles(miles) ?? {}
      const values = Object.values(shares)
      expect(values.every((share) => share > 0 && share <= 1)).toBe(true)
      expect(values.reduce((sum, share) => sum + share, 0)).toBeCloseTo(1, 6)
    }
  })
})

describe('usageRow', () => {
  const stamp = {
    week_first: true,
    month_first: false,
    ever_first: false,
    club_firsts: [],
    kind_month_first: true,
    month_returning: false,
  }

  it('dates a row by the phone’s calendar and carries no account or time of day', () => {
    const row = usageRow({
      id: 'e1',
      event: 'map_screen_viewed',
      now: new Date(2026, 9, 27, 23, 30),
      platform: 'android',
      version: '1.4.0',
      stamp,
      signedIn: true,
      details: {},
    })

    expect(row.local_date).toBe('2026-10-27')
    expect(row.signed_in).toBe(true)
    expect(Object.keys(row).sort()).toEqual(
      [
        'app_version',
        'club_firsts',
        'event',
        'ever_first',
        'id',
        'kind_month_first',
        'local_date',
        'month_first',
        'month_returning',
        'platform',
        'signed_in',
        'week_first',
      ].sort(),
    )
  })

  it('rounds a plan’s miles to a tenth', () => {
    const row = usageRow({
      id: 'e2',
      event: 'hike_plan_made',
      now: new Date(2026, 9, 27),
      platform: 'ios',
      version: '1.4.0',
      stamp,
      signedIn: false,
      details: { miles: 12.3456 },
    })

    expect(row.miles).toBe(12.3)
  })

  it('leaves out a version string the server would refuse rather than losing the batch', () => {
    expect(usageVersion('1.4.0')).toBe('1.4.0')
    expect(usageVersion('1.5.0-rc.1')).toBe('1.5.0-rc.1')
    expect(usageVersion('1.4.0 (beta; Pixel 8)')).toBeUndefined()
    expect(usageVersion('unknown')).toBeUndefined()
    expect(usageVersion('www.ourhike-security-update.com')).toBeUndefined()
    expect(usageVersion('1.4.0\n')).toBeUndefined()
  })

  it('reads the date off the phone’s own calendar', () => {
    expect(usageDate(new Date(2026, 0, 5))).toBe('2026-01-05')
  })
})
