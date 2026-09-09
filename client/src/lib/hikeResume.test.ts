// Coming back to a long hike (#1317).

import { describe, expect, it } from 'vitest'

import {
  NOTICED_ABSENCE_DAYS,
  datedDaysAhead,
  pausedDays,
  resumeOffer,
} from './hikeResume'
import type { Hike } from './hikes'

const TODAY = '2026-09-09'

function hike(over: Partial<Hike> = {}): Hike {
  return {
    id: 'h1',
    name: 'Springer → Katahdin',
    type: 'thru',
    trailId: 'AT',
    points: [{ mile: 0 }, { mile: 2197.4 }],
    status: 'walking',
    tripIds: [],
    ...over,
  }
}

describe('whether to offer a hike back', () => {
  it('offers a paused hike, whatever the fixes say', () => {
    // The explicit trigger: they said they were stepping off, so the app can
    // say welcome back without guessing.
    expect(resumeOffer(hike({ status: 'paused' }), TODAY, TODAY, [])).toBe('paused')
  })

  it('notices an absence past the threshold', () => {
    // The trigger that makes the feature worth building: the hiker who did
    // not say, and simply stopped opening the app on the trail.
    const away = '2026-08-25' // 15 days
    expect(resumeOffer(hike(), away, TODAY, [])).toBe('noticed')
  })

  it('says nothing about an absence shorter than the threshold', () => {
    expect(resumeOffer(hike(), '2026-09-06', TODAY, [])).toBeNull()
  })

  it('fires exactly at the threshold, not a day either side', () => {
    const at = new Date(
      Date.parse(`${TODAY}T00:00:00Z`) - NOTICED_ABSENCE_DAYS * 86400000,
    )
      .toISOString()
      .slice(0, 10)
    const dayLater = new Date(
      Date.parse(`${TODAY}T00:00:00Z`) - (NOTICED_ABSENCE_DAYS - 1) * 86400000,
    )
      .toISOString()
      .slice(0, 10)

    expect(resumeOffer(hike(), at, TODAY, [])).toBe('noticed')
    expect(resumeOffer(hike(), dayLater, TODAY, [])).toBeNull()
  })

  it('treats a hike that has never had a fix as not away', () => {
    // A hike set up on a laptop in February has no fixes and nobody has gone
    // quiet. Offering to "pick it back up" would be answering a question
    // nobody asked.
    expect(resumeOffer(hike(), null, TODAY, [])).toBeNull()
  })

  it('offers once per hike, and per hike rather than globally', () => {
    expect(resumeOffer(hike({ status: 'paused' }), null, TODAY, ['h1'])).toBeNull()
    // A second hike is a second absence, and the first one's dismissal must
    // not silence it.
    expect(resumeOffer(hike({ id: 'h2', status: 'paused' }), null, TODAY, ['h1'])).toBe(
      'paused',
    )
  })

  it('never offers a finished hike back', () => {
    expect(resumeOffer(hike({ status: 'finished' }), '2020-01-01', TODAY, [])).toBeNull()
  })
})

describe('what the offer counts', () => {
  it('counts the dated days still ahead, and where they start', () => {
    const counted = datedDaysAhead(
      [
        {
          days: [{ date: '2026-08-28' }, { date: '2026-09-10' }, { date: '2026-09-11' }],
        },
        { days: [{ date: '2026-09-12' }, {}] },
      ],
      TODAY,
    )

    // The one behind today is not "still dated ahead".
    expect(counted).toEqual({ count: 3, from: '2026-09-10' })
  })

  it('counts nothing when nothing is dated', () => {
    expect(datedDaysAhead([{ days: [{}, {}] }], TODAY)).toBeNull()
  })

  it('says how long a hike has been paused, and refuses a future date', () => {
    expect(pausedDays(hike({ pausedOn: '2026-08-29' }), TODAY)).toBe(11)
    expect(pausedDays(hike(), TODAY)).toBeNull()
    expect(pausedDays(hike({ pausedOn: '2027-01-01' }), TODAY)).toBeNull()
  })
})
