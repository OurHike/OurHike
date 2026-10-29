import { readFileSync, writeFileSync } from 'node:fs'
import { resolve as resolvePath } from 'node:path'

import { describe, expect, it } from 'vitest'

import {
  type ClubRunLike,
  type HeartbeatStamp,
  milesByClub,
  sharesFromMiles,
  type UsageDetails,
  type UsageEventName,
  type UsagePlatform,
  type UsageRow,
  usableFix,
  usageRow,
} from './usageEvents'

// The golden batch (#1902): one row of every event, carrying every optional
// field, built by the phone's own code and checked in as
// usageBatch.golden.json. backend/tests/test_usage_golden_batch.py posts the
// SAME file to `POST /usage-events` and requires every row stored as sent.
//
// Why both halves read one file: a field renamed on either side does not fail
// loudly anywhere else. The server refuses the row, the phone drops it as it
// drops every refused row, and the count simply comes in low - for months,
// if nobody is looking. Here the phone's half goes red when what it builds
// changes, and the server's half goes red when the server stops taking it.
//
// When a change to the row is MEANT, rewrite the file and let the backend
// test judge the new one:
//
//   UPDATE_USAGE_GOLDEN=1 npx vitest run src/lib/usageBatch.golden.test.ts
//   npx prettier --write src/lib/usageBatch.golden.json

// `process.cwd()` rather than `import.meta.url`, the convention
// src/design-system/tokens/contrast.test.ts records: jsdom's is not a file URL.
const GOLDEN = resolvePath(process.cwd(), 'src/lib/usageBatch.golden.json')

const RUNS: ClubRunLike[] = [
  { startMile: 1380, endMile: 1400, club: { acronym: 'NYNJTC' } },
  { startMile: 1400, endMile: 1402, club: null },
  { startMile: 1402, endMile: 1450, club: { acronym: 'AMC-NY' } },
]

const NOW = new Date(2026, 9, 27, 12, 0)
const HELD = {
  lat: 41.29871,
  lon: -74.1881,
  accuracy: 12.34,
  at: new Date(2026, 9, 27, 11, 58),
}

function stamp(overrides: Partial<HeartbeatStamp> = {}): HeartbeatStamp {
  return {
    week_first: false,
    month_first: false,
    ever_first: false,
    club_firsts: [],
    kind_month_first: false,
    month_returning: false,
    ...overrides,
  }
}

function row(
  n: number,
  event: UsageEventName,
  platform: UsagePlatform,
  signedIn: boolean,
  rowStamp: HeartbeatStamp,
  details: UsageDetails,
): UsageRow {
  return usageRow({
    id: `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`,
    event,
    now: NOW,
    platform,
    version: '1.4.0',
    stamp: rowStamp,
    signedIn,
    details,
  })
}

function goldenBatch(): { identified: boolean; events: UsageRow[] } {
  const planClubs = sharesFromMiles(milesByClub(RUNS, 1380, 1410))
  return {
    identified: false,
    events: [
      row(
        1,
        'app_installed',
        'ios',
        false,
        stamp({
          week_first: true,
          month_first: true,
          ever_first: true,
          kind_month_first: true,
        }),
        {},
      ),
      row(2, 'user_login', 'android', true, stamp({ kind_month_first: true }), {}),
      row(
        3,
        'hike_plan_made',
        'web',
        true,
        stamp({
          club_firsts: ['NYNJTC', '_unrecorded', 'AMC-NY'],
          kind_month_first: true,
        }),
        { miles: 30, clubs: planClubs, fix: usableFix(HELD, NOW) },
      ),
      row(4, 'hike_plan_completed', 'ios', false, stamp(), {
        miles: 12.34,
        clubs: { _unrecorded: 1 },
      }),
      row(5, 'map_screen_viewed', 'android', false, stamp(), {
        clubs: { NYNJTC: 1 },
        fix: usableFix({ ...HELD, accuracy: null }, NOW),
      }),
      row(
        6,
        'session',
        'web',
        true,
        stamp({ month_first: true, month_returning: true, kind_month_first: true }),
        { pageviews: 7, session_length: 'm5_to_20' },
      ),
    ],
  }
}

describe('the golden batch', () => {
  it('is exactly what the phone builds today', () => {
    const built = goldenBatch()
    if (process.env.UPDATE_USAGE_GOLDEN === '1') {
      writeFileSync(GOLDEN, `${JSON.stringify(built, null, 2)}\n`)
    }

    expect(built).toEqual(JSON.parse(readFileSync(GOLDEN, 'utf8')))
  })

  it('carries every field a row can carry, so the server is asked about all of them', () => {
    const fields = new Set(goldenBatch().events.flatMap((event) => Object.keys(event)))

    expect([...fields].sort()).toEqual(
      [
        'app_version',
        'club_firsts',
        'clubs',
        'event',
        'ever_first',
        'fix',
        'id',
        'kind_month_first',
        'local_date',
        'miles',
        'month_first',
        'month_returning',
        'pageviews',
        'platform',
        'session_length',
        'signed_in',
        'week_first',
      ].sort(),
    )
  })
})
