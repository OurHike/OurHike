import { describe, it, expect, afterEach } from 'vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { useNoticesPanel } from './noticesPanel'
import { ATC_SOURCE_KEY, noticeSilenceKey, type TrailNotice } from '../lib/notices'
import type { AtcUpdate } from '../lib/atcUpdates'
import type { Stewards } from '../lib/stewards'

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
    layers: [],
    keys: [ATC_SOURCE_KEY],
  },
  {
    provider: 'NYNJTC',
    name: 'New York-New Jersey Trail Conference',
    trust: 'authoritative',
    licence: null,
    attribution: null,
    layers: [],
    keys: ['nynjtc_trail_alerts'],
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
    // Opening the list silences the banner, exactly as its own dismiss does:
    // a hiker who went and read them has looked.
    expect(result.current.mapScreen.newNoticeCount).toBe(0)
    expect(localStorage.getItem(ATC_SILENCE_KEY)).toBe(hoursBefore(1))
  })

  it('silences the banner without opening anything', () => {
    const { result } = panel([update()])

    act(() => result.current.mapScreen.onSilenceNewNotices?.())

    expect(result.current.mapScreen.newNoticeCount).toBe(0)
    // The dismiss is not a way into the list - it is the other answer to it.
    expect(result.current.mapScreen.noticeList).toBeNull()
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

  it('writes one watermark per organization when a hiker dismisses the banner', () => {
    // THE LIVE BUG #1083 NAMES. One shared key meant dismissing ATC silenced
    // NYNJTC too, for notices the hiker had never been shown.
    const { result } = panel([update()], [orgNotice()])

    act(() => result.current.mapScreen.onSilenceNewNotices?.())

    expect(localStorage.getItem(ATC_SILENCE_KEY)).toBe(hoursBefore(1))
    expect(localStorage.getItem(NYNJTC_SILENCE_KEY)).toBe(hoursBefore(2))
    expect(result.current.mapScreen.newNoticeCount).toBe(0)
  })

  it('does not silence one organization when the other is dismissed on its own', () => {
    const { result } = panel([], [orgNotice()])

    act(() => result.current.mapScreen.onSilenceNewNotices?.())

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
