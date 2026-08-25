// The clock that makes an hourly publish reach a phone (#720).
//
// This is the half of the cadence change that is easy to leave out and
// impossible to notice missing: the pipeline can publish every hour into the
// bucket and a hiker will still be reading breakfast's closures at dusk,
// because the reads used to run once per online transition. Nothing about the
// bucket looks wrong when that happens.
//
// The drought reader is here too, and what it is really testing is the
// distinction the pipeline went out of its way to preserve - that an empty
// band list and an unreachable artifact are different answers.

import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  CONDITIONS_REFRESH_MS,
  VISIBILITY_REFRESH_MIN_MS,
  useConditions,
} from './useConditions'
import * as published from './publishedConditions'

function baseline() {
  vi.spyOn(published, 'fetchPublishedClosures').mockResolvedValue(null)
  vi.spyOn(published, 'fetchPublishedReports').mockResolvedValue(null)
  vi.spyOn(published, 'fetchPublishedAtcUpdates').mockResolvedValue(null)
}

describe('the refresh clock', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    baseline()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('re-reads the published baselines on the publish cadence', async () => {
    const drought = vi.spyOn(published, 'fetchPublishedDrought').mockResolvedValue(null)
    renderHook(() => useConditions(true))

    await vi.waitFor(() => expect(drought).toHaveBeenCalledTimes(1))

    await act(async () => {
      vi.advanceTimersByTime(CONDITIONS_REFRESH_MS)
    })
    expect(drought).toHaveBeenCalledTimes(2)

    await act(async () => {
      vi.advanceTimersByTime(CONDITIONS_REFRESH_MS)
    })
    expect(drought).toHaveBeenCalledTimes(3)
  })

  it('coalesces hours that elapsed together into one re-read', async () => {
    // Real React behaviour, asserted rather than worked around, because it is
    // the behaviour worth having: a phone that was asleep for six hours wakes
    // up owing one fetch, not six. The ticks land in one batch, the counter
    // moves once, and the effect runs once.
    const drought = vi.spyOn(published, 'fetchPublishedDrought').mockResolvedValue(null)
    renderHook(() => useConditions(true))
    await vi.waitFor(() => expect(drought).toHaveBeenCalledTimes(1))

    await act(async () => {
      vi.advanceTimersByTime(CONDITIONS_REFRESH_MS * 6)
    })
    expect(drought).toHaveBeenCalledTimes(2)
  })

  it('does not run the clock while offline, and asks the radio for nothing', async () => {
    const drought = vi.spyOn(published, 'fetchPublishedDrought').mockResolvedValue(null)
    renderHook(() => useConditions(false))

    await act(async () => {
      vi.advanceTimersByTime(CONDITIONS_REFRESH_MS * 3)
    })
    // Once, at mount, and not again for three hours: the clock is what this
    // case is about, and it does not tick without signal.
    expect(drought).toHaveBeenCalledTimes(1)
    // And that one call is routed to the copy this phone kept (#447), never
    // to the network - `{ online: false }` is what makes `fetchPublished`
    // skip the request entirely. The property this case has always held is
    // that a wake-up in a dead spot costs no radio; before #447 that meant
    // asking for nothing at all, and now it means asking IndexedDB.
    expect(drought).toHaveBeenLastCalledWith(undefined, { online: false })
  })

  it('matches the pipeline cadence rather than beating it', () => {
    // The pairing publish-conditions.yml's cron comment names. A shorter
    // interval spends battery re-reading bytes that cannot have changed.
    expect(CONDITIONS_REFRESH_MS).toBe(60 * 60 * 1000)
  })
})

describe('the drought bands', () => {
  beforeEach(baseline)
  afterEach(() => vi.restoreAllMocks())

  it('carries NDMC’s week rather than the bake’s clock', async () => {
    vi.spyOn(published, 'fetchPublishedDrought').mockResolvedValue({
      generatedAt: new Date('2026-08-15T09:00:00Z'),
      validWeek: { start: new Date('2026-08-11'), end: new Date('2026-08-17') },
      items: [
        {
          type: 'Feature',
          geometry: { type: 'Polygon', coordinates: [] },
          properties: { dm: 2, label: 'Severe drought', trail_miles: 205.8 },
        },
      ],
    })

    const { result } = renderHook(() => useConditions(true))
    await waitFor(() => expect(result.current.drought).toHaveLength(1))

    expect(result.current.drought[0]).toEqual({
      dm: 2,
      label: 'Severe drought',
      trailMiles: 205.8,
      geometry: { type: 'Polygon', coordinates: [] },
    })
    // The bake ran on the 15th; the claim is about the week beginning the
    // 11th, and it is the second one a hiker is shown.
    expect(result.current.droughtWeek?.start.toISOString()).toBe(
      '2026-08-11T00:00:00.000Z',
    )
  })

  it('tells an empty week apart from an unreachable one', async () => {
    // Both draw an empty map and only one is good news. The empty band list
    // still carries a week, which is what says somebody looked.
    vi.spyOn(published, 'fetchPublishedDrought').mockResolvedValue({
      generatedAt: new Date('2026-08-15T09:00:00Z'),
      validWeek: { start: new Date('2026-08-11'), end: new Date('2026-08-17') },
      items: [],
    })

    const { result } = renderHook(() => useConditions(true))
    await waitFor(() => expect(result.current.droughtWeek).not.toBeNull())
    expect(result.current.drought).toEqual([])
  })

  it('leaves the week null when the artifact could not be read', async () => {
    vi.spyOn(published, 'fetchPublishedDrought').mockResolvedValue(null)
    const { result } = renderHook(() => useConditions(true))

    await waitFor(() => expect(result.current.closures).toBeNull())
    expect(result.current.drought).toEqual([])
    expect(result.current.droughtWeek).toBeNull()
  })
})

describe('coming back to the app (#963)', () => {
  // A backgrounded PWA has its timers throttled or suspended, so the hourly
  // re-read stops while the screen is off. These are about the moment a hiker
  // takes the phone back out, which is when the answer matters most and is
  // least likely to have been refetched.

  beforeEach(() => {
    vi.useFakeTimers()
    baseline()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('re-reads the published baselines when the app becomes visible again', async () => {
    const reads = vi.spyOn(published, 'fetchPublishedAtcUpdates').mockResolvedValue(null)
    renderHook(() => useConditions(true))
    await act(async () => {})
    const before = reads.mock.calls.length

    // Long enough in a pocket that the throttle does not swallow it.
    await act(async () => {
      vi.advanceTimersByTime(VISIBILITY_REFRESH_MIN_MS + 1000)
      document.dispatchEvent(new Event('visibilitychange'))
    })

    expect(reads.mock.calls.length).toBeGreaterThan(before)
  })

  it('does not refetch on every app switch', async () => {
    const reads = vi.spyOn(published, 'fetchPublishedAtcUpdates').mockResolvedValue(null)
    renderHook(() => useConditions(true))
    await act(async () => {
      vi.advanceTimersByTime(VISIBILITY_REFRESH_MIN_MS + 1000)
      document.dispatchEvent(new Event('visibilitychange'))
    })
    const before = reads.mock.calls.length

    // Two more flicks straight away, the way somebody checks a message.
    await act(async () => {
      document.dispatchEvent(new Event('visibilitychange'))
      document.dispatchEvent(new Event('visibilitychange'))
    })

    expect(reads.mock.calls.length).toBe(before)
  })
})
