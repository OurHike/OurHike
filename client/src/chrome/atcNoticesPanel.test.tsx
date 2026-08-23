import { describe, it, expect, afterEach } from 'vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { useAtcNoticesPanel } from './atcNoticesPanel'
import { ATC_ALERT_SILENCE_KEY } from '../lib/atcAlertsBanner'
import type { AtcUpdate } from '../lib/atcUpdates'

// #327 moved this feature out of App.tsx whole. These tests are about the
// seams the move created - what the hook hands back, and what it still has to
// decide - rather than about the library functions underneath it, which have
// their own suites (lib/atcUpdates.test.ts, lib/atcAlertsBanner.test.ts) and
// are not re-tested here.
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

/** No centerline. Every geometry path returns empty, which is what a phone
 *  looks like before the trail has loaded - and it keeps these tests about
 *  the panel rather than about `closureBands`. */
const NO_INDEX = null

function panel(updates: readonly AtcUpdate[]) {
  return renderHook(() =>
    useAtcNoticesPanel({ updates, reviewedAt: null, trailIndex: NO_INDEX, now: NOW }),
  )
}

afterEach(() => {
  cleanup()
  localStorage.clear()
})

describe('useAtcNoticesPanel', () => {
  it('counts every notice the app holds, not only the ones the map can draw', () => {
    // The count behind the legend's "ATC notices" entry. With no centerline
    // nothing is placed, so this is the case that separates "how many are
    // there" from "how many are drawn" - and the entry has to offer the list
    // even when the map shows none of it.
    const { result } = panel([update(), update({ atc_id: 'second' })])

    expect(result.current.mapScreen.atcNoticeCount).toBe(2)
    expect(result.current.mapScreen.atcUpdates).toEqual([])
    expect(result.current.mapScreen.atcUpdatePoints).toEqual([])
  })

  it('opens the full list, and counts that as having looked', () => {
    const { result } = panel([update()])

    expect(result.current.mapScreen.newAtcAlertCount).toBe(1)
    expect(result.current.mapScreen.atcNoticeList).toBeNull()

    act(() => result.current.mapScreen.onOpenAtcNotices?.())

    expect(result.current.mapScreen.atcNoticeList).not.toBeNull()
    // Opening the list silences the banner, exactly as its own dismiss does:
    // a hiker who went and read them has looked.
    expect(result.current.mapScreen.newAtcAlertCount).toBe(0)
    expect(localStorage.getItem(ATC_ALERT_SILENCE_KEY)).toBe(hoursBefore(1))
  })

  it('silences the banner without opening anything', () => {
    const { result } = panel([update()])

    act(() => result.current.mapScreen.onSilenceNewAtcAlerts?.())

    expect(result.current.mapScreen.newAtcAlertCount).toBe(0)
    // The dismiss is not a way into the list - it is the other answer to it.
    expect(result.current.mapScreen.atcNoticeList).toBeNull()
  })

  it('starts silenced when this phone has a watermark already', () => {
    localStorage.setItem(ATC_ALERT_SILENCE_KEY, hoursBefore(1))

    const { result } = panel([update()])

    expect(result.current.mapScreen.newAtcAlertCount).toBe(0)
  })

  it('holds a service-worker update only for the tapped sheet', () => {
    // `sheetOpen` is what the shell's `updateWouldCost` reads. The list is
    // deliberately not in it: a reload loses a list a hiker can reopen from
    // the legend in one tap, and holding an update for that would hold it
    // for as long as somebody left the list up.
    const { result } = panel([update()])

    expect(result.current.sheetOpen).toBe(false)

    act(() => result.current.mapScreen.onOpenAtcNotices?.())
    expect(result.current.sheetOpen).toBe(false)

    act(() => result.current.mapScreen.onSelectAtcUpdate?.('atc:harpers-ferry'))
    expect(result.current.sheetOpen).toBe(true)
  })

  it('draws no sheet for a band id no notice answers to', () => {
    // The map reports a band id; resolving it is this hook's job, and a stale
    // id - a notice withdrawn between the draw and the tap - resolves to
    // nothing rather than to a sheet about the wrong closure.
    const { result } = panel([update()])

    act(() => result.current.mapScreen.onSelectAtcUpdate?.('atc:not-a-real-notice'))

    expect(result.current.mapScreen.atcUpdateSheet).toBeNull()
    // Still "open" as far as the update hold is concerned, because the hiker
    // did tap something. An empty sheet is a rendering question; this is not.
    expect(result.current.sheetOpen).toBe(true)
  })
})
