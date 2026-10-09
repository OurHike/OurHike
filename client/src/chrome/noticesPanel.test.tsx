import { describe, it, expect, afterEach } from 'vitest'
import { act, cleanup, renderHook, waitFor } from '@testing-library/react'
import type { FeatureCollection } from 'geojson'
import { useNoticesPanel } from './noticesPanel'
import { ATC_SOURCE_KEY, noticeSilenceKey, type TrailNotice } from '../lib/notices'
import type { AtcUpdate } from '../lib/atcUpdates'
import type { Stewards } from '../lib/stewards'
import type { DayHike } from '../lib/dayHikes'
import { HAZARD_ADVISORIES } from '../lib/hazardAreas'
import { buildTrailIndex } from '../lib/trailPosition'

// #327 moved this feature out of App.tsx whole. These tests are about the
// seams the move created - what the hook hands back, and what it still has to
// decide - rather than about the library functions underneath it, which have
// their own suites (lib/atcUpdates.test.ts, lib/notices.test.ts) and are not
// re-tested here.
//
// #1083 gave the hook a second publisher, and the seam it added is the one
// worth guarding: only ATC's rows carry a mile, so only ATC's rows reach the
// geometry, while the list, the count and the banner take everybody's.
//
// The move itself is covered by the 4,477 tests that already existed: App's
// suites drive this feature through the rendered screen and passed unchanged
// across the extraction, which is the evidence that nothing moved that should
// have stayed.

const NOW = new Date('2026-08-13T12:00:00.000Z')

function hoursBefore(hours: number): string {
  return new Date(NOW.getTime() - hours * 60 * 60 * 1000).toISOString()
}

function update(overrides: Partial<AtcUpdate> = {}): AtcUpdate {
  return {
    atc_id: 'harpers-ferry-footbridge-closure',
    title: 'Harpers Ferry: Footbridge Closure',
    category: 'Detour',
    states: ['MD', 'WV'],
    start_mile_marker: 1026.7,
    end_mile_marker: 1026.7,
    obstructs_trail: true,
    updated_at: hoursBefore(1),
    source_url: 'https://appalachiantrail.org/trail-updates/harpers-ferry/',
    ...overrides,
  }
}

/** One real published NYNJTC row, from `conditions/nynjtc_alerts.json` read
 *  2026-08-27. `unplaced` and `unreviewed`, which is every row in that file. */
function orgNotice(overrides: Partial<TrailNotice> = {}): TrailNotice {
  return {
    notice_id: 'nynjtc_trail_alerts:a-t-detour-at-harriman-state-park',
    source_key: 'nynjtc_trail_alerts',
    title: 'A.T. Detour at Harriman State Park',
    category: null,
    locality: 'Harriman-Bear Mountain',
    place: { kind: 'unplaced' },
    obstructs_trail: false,
    updated_at: hoursBefore(2),
    source_url: 'https://www.nynjtc.org/trail-alerts/a-t-detour/',
    review_state: 'unreviewed',
    ...overrides,
  }
}

/** No centerline. Every geometry path returns empty, which is what a phone
 *  looks like before the trail has loaded - and it keeps these tests about
 *  the panel rather than about `closureBands`. */
const NO_INDEX = null

/** Any box. With no centerline `viewportMiles` is never called, so the list is
 *  unscoped - which is the state before the trail has loaded. */
const BBOX = { west: -75, south: 41, east: -73, north: 42 }

const STEWARDS: Stewards = [
  {
    provider: 'ATC',
    name: 'Appalachian Trail Conservancy',
    trust: null,
    licence: null,
    attribution: null,
    terms: null,
    termsSource: null,
    layers: [],
    keys: [ATC_SOURCE_KEY],
    support: null,
    store: null,
  },
  {
    provider: 'NYNJTC',
    name: 'New York-New Jersey Trail Conference',
    trust: 'authoritative',
    licence: null,
    attribution: null,
    terms: null,
    termsSource: null,
    layers: [],
    keys: ['nynjtc_trail_alerts'],
    support: null,
    store: null,
  },
]

const ATC_SILENCE_KEY = noticeSilenceKey(ATC_SOURCE_KEY)
const NYNJTC_SILENCE_KEY = noticeSilenceKey('nynjtc_trail_alerts')

function panel(updates: readonly AtcUpdate[], orgNotices: readonly TrailNotice[] = []) {
  return renderHook(() =>
    useNoticesPanel({
      updates,
      orgNotices,
      reviewedAt: null,
      stewards: STEWARDS,
      trailIndex: NO_INDEX,
      bbox: BBOX,
      now: NOW,
    }),
  )
}

afterEach(() => {
  cleanup()
  localStorage.clear()
})

describe('useNoticesPanel', () => {
  it('counts every notice the app holds, not only the ones the map can draw', () => {
    // The count behind the legend's "ATC notices" entry. With no centerline
    // nothing is placed, so this is the case that separates "how many are
    // there" from "how many are drawn" - and the entry has to offer the list
    // even when the map shows none of it.
    const { result } = panel([update(), update({ atc_id: 'second' })])

    expect(result.current.mapScreen.noticeCount).toBe(2)
    expect(result.current.mapScreen.atcUpdates).toEqual([])
    expect(result.current.mapScreen.atcUpdatePoints).toEqual([])
  })

  it('opens the full list, and counts that as having looked', () => {
    const { result } = panel([update()])

    expect(result.current.mapScreen.newNoticeCount).toBe(1)
    expect(result.current.mapScreen.noticeList).toBeNull()

    act(() => result.current.mapScreen.onOpenNotices?.())

    expect(result.current.mapScreen.noticeList).not.toBeNull()
    // Opening the list silences the dot - the one way to, since the banner
    // and its own dismiss went (2026-09-10): a hiker who went and read them
    // has looked.
    expect(result.current.mapScreen.newNoticeCount).toBe(0)
    expect(localStorage.getItem(ATC_SILENCE_KEY)).toBe(hoursBefore(1))
  })

  it('starts silenced when this phone has a watermark already', () => {
    localStorage.setItem(ATC_SILENCE_KEY, hoursBefore(1))

    const { result } = panel([update()])

    expect(result.current.mapScreen.newNoticeCount).toBe(0)
  })

  it('holds a service-worker update only for the tapped sheet', () => {
    // `sheetOpen` is what the shell's `updateWouldCost` reads. The list is
    // deliberately not in it: a reload loses a list a hiker can reopen from
    // the legend in one tap, and holding an update for that would hold it
    // for as long as somebody left the list up.
    const { result } = panel([update()])

    expect(result.current.sheetOpen).toBe(false)

    act(() => result.current.mapScreen.onOpenNotices?.())
    expect(result.current.sheetOpen).toBe(false)

    act(() =>
      result.current.mapScreen.onSelectAtcUpdate?.('atc_trail_updates:harpers-ferry'),
    )
    expect(result.current.sheetOpen).toBe(true)
  })

  it('draws no sheet for a band id no notice answers to', () => {
    // The map reports a band id; resolving it is this hook's job, and a stale
    // id - a notice withdrawn between the draw and the tap - resolves to
    // nothing rather than to a sheet about the wrong closure.
    const { result } = panel([update()])

    act(() =>
      result.current.mapScreen.onSelectAtcUpdate?.('atc_trail_updates:not-a-real-notice'),
    )

    expect(result.current.mapScreen.atcUpdateSheet).toBeNull()
    // Still "open" as far as the update hold is concerned, because the hiker
    // did tap something. An empty sheet is a rendering question; this is not.
    expect(result.current.sheetOpen).toBe(true)
  })
})

describe('a second publisher, through the same hook', () => {
  it('counts an unplaced notice into the list even though the map cannot draw it', () => {
    // The whole of #1083 in one assertion: a notice with no mile has no map
    // ink and no header line, and it still has to reach a hiker.
    const { result } = panel([update()], [orgNotice()])

    expect(result.current.mapScreen.noticeCount).toBe(2)
    expect(result.current.mapScreen.atcUpdates).toEqual([])
    expect(result.current.mapScreen.atcUpdatePoints).toEqual([])
  })

  it('names both organizations in one banner rather than raising a second', () => {
    // features/ORG_NOTICES.md §5: the banner is "a scarce surface rather than
    // a record". One line, both names, and the list keeps every row.
    const { result } = panel([update()], [orgNotice()])

    expect(result.current.mapScreen.newNoticeCount).toBe(2)
    expect(result.current.mapScreen.newNoticeLabel).toBe(
      '2 new trail notices · Appalachian Trail Conservancy and New York-New Jersey Trail Conference',
    )
  })

  it('keeps the single-publisher sentence when only one has posted', () => {
    const { result } = panel([update()])

    expect(result.current.mapScreen.newNoticeLabel).toBe(
      'Appalachian Trail Conservancy · New notice issued',
    )
  })

  it('writes one watermark per organization when a hiker reads the list', () => {
    // THE LIVE BUG #1083 NAMES. One shared key meant dismissing ATC silenced
    // NYNJTC too, for notices the hiker had never been shown. Reading the
    // list is the dismissal now (the banner's own × went with the banner,
    // 2026-09-10), and it still writes one watermark per organization shown.
    const { result } = panel([update()], [orgNotice()])

    act(() => result.current.mapScreen.onOpenNotices?.())

    expect(localStorage.getItem(ATC_SILENCE_KEY)).toBe(hoursBefore(1))
    expect(localStorage.getItem(NYNJTC_SILENCE_KEY)).toBe(hoursBefore(2))
    expect(result.current.mapScreen.newNoticeCount).toBe(0)
  })

  it('does not silence one organization when only the other was shown', () => {
    const { result } = panel([], [orgNotice()])

    act(() => result.current.mapScreen.onOpenNotices?.())

    expect(localStorage.getItem(NYNJTC_SILENCE_KEY)).toBe(hoursBefore(2))
    expect(localStorage.getItem(ATC_SILENCE_KEY)).toBeNull()
  })

  it('still shows one organization-s new notices after the other was silenced', () => {
    localStorage.setItem(ATC_SILENCE_KEY, hoursBefore(1))

    const { result } = panel([update()], [orgNotice()])

    expect(result.current.mapScreen.newNoticeCount).toBe(1)
    expect(result.current.mapScreen.newNoticeLabel).toBe(
      'New York-New Jersey Trail Conference · New notice issued',
    )
  })
})

describe('with conditions/notices.json (#1805, decision 66)', () => {
  // NOW is noon UTC on 2026-08-13, which is that same calendar day in every
  // zone from UTC-11 to UTC+11, so a day hike dated that day is in the window.
  const TODAY = '2026-08-13'

  function dayHike(date: string | null): DayHike {
    return {
      id: 'hike-1',
      name: 'Harriman loop',
      date,
      segments: [
        [
          { coord: [-74.1, 41.25], poiId: null },
          { coord: [-74.09, 41.25], poiId: null },
        ],
      ],
      figures: {
        miles: 5,
        legs: [
          {
            name: 'Fixture Trail',
            source: 'nynjtc_trail_alerts',
            blaze_color: null,
            miles: 5,
          },
        ],
      },
      looped: false,
      recorded: 'planned',
      note: '',
    }
  }

  function clubPanel(
    clubNotices: readonly TrailNotice[] | null,
    dayHikes: readonly DayHike[],
  ) {
    return renderHook(() =>
      useNoticesPanel({
        updates: [update()],
        orgNotices: [orgNotice()],
        reviewedAt: null,
        stewards: STEWARDS,
        trailIndex: NO_INDEX,
        bbox: BBOX,
        now: NOW,
        clubNotices,
        clubNoticesGeneratedAt: NOW,
        dayHikes,
      }),
    )
  }

  it('keeps today’s list, row and count while the file has not reached this phone', () => {
    const { result } = clubPanel(null, [dayHike(TODAY)])
    expect(result.current.mapScreen.noticeRowLabel).toBeUndefined()
    expect(result.current.mapScreen.noticeCount).toBe(2)
    expect(result.current.hazardAreas).toEqual([])
  })

  // The rule loads behind import() once the file is here (the hook's
  // comment says why), so each test below waits on the count or the list
  // the loaded rule produces, never on a timer.
  it('counts only what touches a planned hike, and offers the row with nothing to count', async () => {
    const touching = orgNotice({
      notice_id: 'nynjtc_trail_alerts:near',
      updated_at: hoursBefore(3),
    })
    const elsewhere = orgNotice({
      notice_id: 'faraway_club:1',
      source_key: 'faraway_club',
      provider: 'Faraway Club',
    })

    const planned = clubPanel([touching, elsewhere], [dayHike(TODAY)])
    await waitFor(() => expect(planned.result.current.mapScreen.noticeCount).toBe(1))
    expect(planned.result.current.mapScreen.noticeRowLabel).toBe(
      'Notices for your planned hikes (1)',
    )
    // The dot counts what the panel shows, so opening it silences only that.
    expect(planned.result.current.mapScreen.newNoticeCount).toBe(1)
    cleanup()

    const none = clubPanel([touching, elsewhere], [dayHike(null)])
    expect(none.result.current.mapScreen.noticeCount).toBe(0)
    expect(none.result.current.mapScreen.noticeRowLabel).toBe(
      'Notices for your planned hikes',
    )
    expect(none.result.current.mapScreen.newNoticeCount).toBe(0)
  })

  it('opens the planned-hike panel rather than the list of everything', async () => {
    const { result } = clubPanel([orgNotice()], [dayHike(TODAY)])
    act(() => result.current.mapScreen.onOpenNotices?.())
    await waitFor(() => expect(result.current.mapScreen.noticeList).not.toBeNull())
    const list = result.current.mapScreen.noticeList as {
      type: { displayName?: string }
    }
    expect(list.type.displayName).toBe('Deferred(PlannedNoticeList)')
  })

  // Decision 77: a phone downloads conditions/notices.json only once a hike
  // is planned, and lib/useConditions.ts says when the bucket serves it
  // anyway (`clubNoticesListed`, a HEAD request's answer).
  function listedPanel(dayHikes: readonly DayHike[]) {
    return renderHook(() =>
      useNoticesPanel({
        updates: [update()],
        orgNotices: [orgNotice()],
        reviewedAt: null,
        stewards: STEWARDS,
        trailIndex: NO_INDEX,
        bbox: BBOX,
        now: NOW,
        clubNotices: null,
        clubNoticesGeneratedAt: null,
        clubNoticesListed: true,
        dayHikes,
      }),
    )
  }

  it('says no hike is planned, never the list of everything, when the bucket serves notices.json and nothing is planned', async () => {
    const { result } = listedPanel([])
    expect(result.current.mapScreen.noticeRowLabel).toBe('Notices for your planned hikes')
    expect(result.current.mapScreen.noticeCount).toBe(0)
    act(() => result.current.mapScreen.onOpenNotices?.())
    await waitFor(() => expect(result.current.mapScreen.noticeList).not.toBeNull())
    const list = result.current.mapScreen.noticeList as {
      type: { displayName?: string }
      props: {
        planned: { empty: string | null; hikes: unknown[] }
        generatedAt: Date | null
      }
    }
    expect(list.type.displayName).toBe('Deferred(PlannedNoticeList)')
    expect(list.props.planned.empty).toBe('nothing_planned')
    expect(list.props.planned.hikes).toEqual([])
    expect(list.props.generatedAt).toBeNull()
  })

  it('keeps today’s list for a planned hike whose notices.json has not arrived, rather than calling it clear', () => {
    // The file is what a planned hike's notices come from, so its absence
    // must never read as "nothing touches this hike".
    const { result } = listedPanel([dayHike(TODAY)])
    expect(result.current.mapScreen.noticeRowLabel).toBeUndefined()
    expect(result.current.mapScreen.noticeCount).toBe(2)
  })
})

describe('decision 67’s areas from conditions/hazard_areas.json (decision 84)', () => {
  // Decision 77 downloads notices.json only once a hike is planned, and the
  // areas were drawn from it alone, so a phone with nothing planned drew
  // none. These hold the panel to the maintainer's answer: the areas' own
  // file, read whatever is planned, and never an area drawn twice.

  /** A centerline due north along 77° W, 34° to 35° N, as
   *  lib/hazardAreas.test.ts's own. */
  const INDEX = buildTrailIndex({
    type: 'FeatureCollection',
    features: [
      {
        type: 'Feature',
        properties: { source: 'centerline' },
        geometry: {
          type: 'LineString',
          coordinates: Array.from({ length: 101 }, (_, i) => [-77, 34 + i * 0.01]),
        },
      },
    ],
  } as FeatureCollection)

  /** An invented hunting area the centerline crosses at 34.3° N. */
  function huntingArea(id: string, west = -77.01, east = -76.99): TrailNotice {
    return orgNotice({
      notice_id: `oprhp_hunting_areas:${id}`,
      source_key: 'oprhp_hunting_areas',
      title: `Fixture hunting area ${id}`,
      hazard: 'hunting',
      updated_at: null,
      place: {
        kind: 'geometry',
        geometry: {
          type: 'Polygon',
          coordinates: [
            [
              [west, 34.3],
              [east, 34.3],
              [east, 34.31],
              [west, 34.31],
              [west, 34.3],
            ],
          ],
        },
      },
    })
  }

  function hazardPanel({
    clubNotices = null,
    clubNoticesGeneratedAt = null,
    hazardFile = null,
  }: {
    clubNotices?: readonly TrailNotice[] | null
    clubNoticesGeneratedAt?: Date | null
    hazardFile?: { items: readonly TrailNotice[]; generatedAt: Date } | null
  }) {
    return renderHook(() =>
      useNoticesPanel({
        updates: [],
        orgNotices: [],
        reviewedAt: null,
        stewards: STEWARDS,
        trailIndex: INDEX,
        bbox: BBOX,
        now: NOW,
        clubNotices,
        clubNoticesGeneratedAt,
        hazardFile,
      }),
    )
  }

  it('draws an area from hazard_areas.json, with its advisory on the tapped stretch, on a phone with no hike planned and no notices.json', async () => {
    const { result } = hazardPanel({
      hazardFile: { items: [huntingArea('1')], generatedAt: NOW },
    })
    await waitFor(() => expect(result.current.hazardAreas).toHaveLength(1))
    expect(result.current.mapScreen.hazardAreas).toBe(result.current.hazardAreas)
    expect(result.current.hazardAdvisoriesAt([-77, 34.305])).toEqual([
      { id: 'oprhp_hunting_areas:1', ...HAZARD_ADVISORIES.hunting },
    ])
    // The planned-hike panel is not what this file turns on: with neither
    // notices.json nor a plan the list stays today's.
    expect(result.current.mapScreen.noticeRowLabel).toBeUndefined()
  })

  it('draws an area once when both files hold it from one build', async () => {
    const area = huntingArea('1')
    const { result } = hazardPanel({
      clubNotices: [area],
      clubNoticesGeneratedAt: NOW,
      hazardFile: { items: [area], generatedAt: NOW },
    })
    await waitFor(() => expect(result.current.hazardAreas).toHaveLength(1))
    expect(result.current.hazardAdvisoriesAt([-77, 34.305])).toHaveLength(1)
  })

  it('takes the areas from whichever file is newer, so a copy kept from before decision 77 never outranks a fresh hazard file', async () => {
    const older = new Date(NOW.getTime() - 30 * 86_400_000)
    const fresh = hazardPanel({
      clubNotices: [huntingArea('kept-copy')],
      clubNoticesGeneratedAt: older,
      hazardFile: { items: [huntingArea('fresh')], generatedAt: NOW },
    })
    await waitFor(() => expect(fresh.result.current.hazardAreas).toHaveLength(1))
    expect(fresh.result.current.hazardAreas[0].notice.notice_id).toBe(
      'oprhp_hunting_areas:fresh',
    )
    cleanup()

    const newerNotices = hazardPanel({
      clubNotices: [huntingArea('this-hour')],
      clubNoticesGeneratedAt: NOW,
      hazardFile: { items: [huntingArea('last-month')], generatedAt: older },
    })
    await waitFor(() => expect(newerNotices.result.current.hazardAreas).toHaveLength(1))
    expect(newerNotices.result.current.hazardAreas[0].notice.notice_id).toBe(
      'oprhp_hunting_areas:this-hour',
    )
  })

  it('draws the areas from notices.json on a bucket without hazard_areas.json, never reading the missing file as no area', async () => {
    const { result } = hazardPanel({
      clubNotices: [huntingArea('1')],
      clubNoticesGeneratedAt: NOW,
    })
    await waitFor(() => expect(result.current.hazardAreas).toHaveLength(1))
  })
})

describe('the "new notices" banner with conditions/notices.json (decision 87)', () => {
  // A notice with no `updated_at` of its own counts as new only if OurHike
  // first saw it after its source's earliest row in the file, and is
  // announced with no verb, never "issued".
  // Invented rows shaped like soak run 536's: every first_seen_at between
  // 2026-10-03T20:24Z and 2026-10-05T00:23Z, the file generated at 00:23:54Z.
  const LATER = new Date('2026-10-05T00:30:00Z')
  const DAY = '2026-10-05'

  function hike(): DayHike {
    return {
      id: 'hike-1',
      name: 'Harriman loop',
      date: DAY,
      segments: [
        [
          { coord: [-74.1, 41.25], poiId: null },
          { coord: [-74.09, 41.25], poiId: null },
        ],
      ],
      figures: {
        miles: 5,
        legs: [
          {
            name: 'Fixture Trail',
            source: 'nynjtc_trail_alerts',
            blaze_color: null,
            miles: 5,
          },
        ],
      },
      looped: false,
      recorded: 'planned',
      note: '',
    }
  }

  /** NYNJTC's unplaced notices touch a hike on NYNJTC's trails. */
  function seen(id: string, firstSeenAt: string): TrailNotice {
    return orgNotice({
      notice_id: `nynjtc_trail_alerts:${id}`,
      updated_at: null,
      first_seen_at: firstSeenAt,
      changed_at: firstSeenAt,
    })
  }

  const INITIAL_LOAD = [
    seen('one', '2026-10-03T20:24:05Z'),
    seen('two', '2026-10-03T20:24:05Z'),
  ]

  function bannerPanel(clubNotices: readonly TrailNotice[]) {
    return renderHook(() =>
      useNoticesPanel({
        updates: [],
        orgNotices: [],
        reviewedAt: null,
        stewards: STEWARDS,
        trailIndex: NO_INDEX,
        bbox: BBOX,
        now: LATER,
        clubNotices,
        clubNoticesGeneratedAt: new Date('2026-10-05T00:23:54Z'),
        dayHikes: [hike()],
      }),
    )
  }

  it('stays dark for the notices OurHike first saw with their source, the file’s initial load', async () => {
    const { result } = bannerPanel(INITIAL_LOAD)
    await waitFor(() => expect(result.current.mapScreen.noticeCount).toBe(2))
    expect(result.current.mapScreen.newNoticeCount).toBe(0)
  })

  it('counts a closure with no updated_at that OurHike first saw in a later build as "New notice", and silences it once the list is read', async () => {
    const { result } = bannerPanel([
      ...INITIAL_LOAD,
      seen('closure', '2026-10-04T22:01:56Z'),
    ])
    await waitFor(() => expect(result.current.mapScreen.newNoticeCount).toBe(1))
    expect(result.current.mapScreen.newNoticeLabel).toBe(
      'New York-New Jersey Trail Conference · New notice',
    )

    act(() => result.current.mapScreen.onOpenNotices?.())
    expect(result.current.mapScreen.newNoticeCount).toBe(0)
    expect(localStorage.getItem(`${NYNJTC_SILENCE_KEY}:seen`)).toBe(
      '2026-10-04T22:01:56.000Z',
    )
    // The club's own clock is not touched by a first-seen dismissal.
    expect(localStorage.getItem(NYNJTC_SILENCE_KEY)).toBeNull()
  })
})
