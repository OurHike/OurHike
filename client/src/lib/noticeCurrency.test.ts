import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  NOT_CURRENT_LINES,
  isCurrentOn,
  isIsoDay,
  longDay,
  notCurrent,
} from './noticeCurrency'
import type { TrailNotice } from './notices'
import { localDay } from './passedToday'

// The phone's half of rules 2 and 4 (pipeline/ELT.md, "Status, water and
// expiry rules"): the pipeline publishes `current_until`, and this compares it
// with the phone's own calendar. The clock is mocked, as a phone's would be
// read, so each test says what a hiker sees on a given day without any new
// file arriving - the offline case the field exists for. Every notice here is
// invented.

function notice(extra: Partial<TrailNotice> = {}): TrailNotice {
  return {
    notice_id: 'fixture_club:1',
    source_key: 'fixture_club',
    title: 'Fixture bridge out',
    category: null,
    locality: '',
    place: { kind: 'unplaced' },
    obstructs_trail: true,
    updated_at: null,
    source_url: null,
    review_state: 'unreviewed',
    ...extra,
  }
}

/** The phone's day at a local wall-clock time, read through the mocked clock
 *  the way the shell reads it (lib/passedToday.ts's `localDay`). */
function phoneDayAt(year: number, month: number, day: number, hour: number): string {
  vi.setSystemTime(new Date(year, month - 1, day, hour, 30))
  return localDay(new Date())
}

afterEach(() => {
  vi.useRealTimers()
})

describe('isCurrentOn, against the phone’s own clock', () => {
  it('keeps a notice current all through its current_until day and greys it the next morning, offline', () => {
    vi.useFakeTimers()
    // Edited 2026-07-12; the pipeline's 90 days make 2026-10-10 its last day.
    const edited = notice({
      updated_at: '2026-07-12T12:00:00Z',
      current_until: '2026-10-10',
    })
    expect(isCurrentOn(edited, phoneDayAt(2026, 10, 10, 23))).toBe(true)
    expect(isCurrentOn(edited, phoneDayAt(2026, 10, 11, 0))).toBe(false)
    expect(notCurrent(edited, phoneDayAt(2026, 10, 11, 0))?.line).toBe(
      'Last reported July 12, 2026. It may no longer apply.',
    )
  })

  it('greys a notice whose own end date passed while the phone was offline, on the day after it', () => {
    vi.useFakeTimers()
    const ending = notice({ ends_on: '2026-10-12', current_until: '2026-10-12' })
    expect(notCurrent(ending, phoneDayAt(2026, 10, 12, 18))).toBeNull()
    expect(notCurrent(ending, phoneDayAt(2026, 10, 13, 7))).toEqual({
      line: 'Its source said it would end October 12, 2026. It may no longer apply.',
      saysUpdated: false,
    })
  })

  it('never reads a current_until of null as current, on any day', () => {
    const undated = notice({ current_until: null })
    expect(isCurrentOn(undated, '1999-01-01')).toBe(false)
    expect(isCurrentOn(undated, '2026-10-10')).toBe(false)
  })

  it('reads a notice with no current_until key as current: its file makes no claim', () => {
    // A copy of notices.json from before the field, or an atc_updates.json row.
    expect(isCurrentOn(notice(), '2030-01-01')).toBe(true)
    expect(notCurrent(notice(), '2030-01-01')).toBeNull()
  })

  it('never reads a current_until that is not a real ISO day as current', () => {
    expect(isCurrentOn(notice({ current_until: '2026-04-31' }), '2026-01-01')).toBe(false)
    expect(isCurrentOn(notice({ current_until: 'soon' }), '2026-01-01')).toBe(false)
  })
})

describe('notCurrent’s line, one for each step that set current_until', () => {
  const AFTER = '2026-10-10'

  it('says the maintainer’s "Its source gives no date. It may no longer apply." for no date at all', () => {
    expect(notCurrent(notice({ current_until: null }), AFTER)).toEqual({
      line: 'Its source gives no date. It may no longer apply.',
      saysUpdated: false,
    })
  })

  it('says "Its source gives no end or update date." where only a start was given', () => {
    // A burned area dated by its fire's start, which bounds nothing.
    expect(
      notCurrent(notice({ starts_on: '2026-08-26', current_until: null }), AFTER)?.line,
    ).toBe('Its source gives no end or update date. It may no longer apply.')
  })

  it('says the maintainer’s "Last reported <date>." from the edit stamp, in UTC, and carries it', () => {
    // 01:30 at -04:00 is 05:30 UTC, the same day as lib/atcNoticeText.ts's
    // longDate prints it on the row.
    expect(
      notCurrent(
        notice({ updated_at: '2026-03-05T01:30:00-04:00', current_until: '2026-06-03' }),
        AFTER,
      ),
    ).toEqual({
      line: 'Last reported March 5, 2026. It may no longer apply.',
      saysUpdated: true,
    })
  })

  it('says when its source said it would end, ahead of its edit date, once its own end has passed', () => {
    expect(
      notCurrent(
        notice({
          ends_on: '2026-10-03',
          updated_at: '2026-10-09T12:00:00Z',
          current_until: '2026-10-03',
        }),
        AFTER,
      )?.line,
    ).toBe('Its source said it would end October 3, 2026. It may no longer apply.')
  })

  it('says "The time its source gave ran out on <day>." for a stated duration with no edit stamp', () => {
    expect(
      notCurrent(
        notice({
          title: 'Fixture loop closed for 3 to 6 months',
          starts_on: '2025-01-06',
          current_until: '2025-07-06',
        }),
        AFTER,
      )?.line,
    ).toBe('The time its source gave ran out on July 6, 2025. It may no longer apply.')
  })

  it('ends every line with "It may no longer apply.", the frame’s second sentence', () => {
    for (const line of [
      NOT_CURRENT_LINES.lastReported('March 5, 2026'),
      NOT_CURRENT_LINES.noDate,
      NOT_CURRENT_LINES.ended('October 3, 2026'),
      NOT_CURRENT_LINES.ranOut('July 6, 2025'),
      NOT_CURRENT_LINES.startOnly,
    ]) {
      expect(line.endsWith(' It may no longer apply.')).toBe(true)
    }
  })
})

describe('isIsoDay and longDay', () => {
  it('accepts a real ISO day and refuses one no calendar has', () => {
    expect(isIsoDay('2028-02-29')).toBe(true)
    expect(isIsoDay('2026-02-29')).toBe(false)
    expect(isIsoDay('2026-10-1')).toBe(false)
    expect(isIsoDay(null)).toBe(false)
  })

  it('prints an ISO day as "October 1, 2026", and anything else as written', () => {
    expect(longDay('2026-10-01')).toBe('October 1, 2026')
    expect(longDay('late October')).toBe('late October')
  })
})
