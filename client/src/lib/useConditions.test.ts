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
import { CONDITIONS_REFRESH_MS, useConditions } from './useConditions'
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

  it('does not run the clock while offline', async () => {
    const drought = vi.spyOn(published, 'fetchPublishedDrought').mockResolvedValue(null)
    renderHook(() => useConditions(false))

    await act(async () => {
      vi.advanceTimersByTime(CONDITIONS_REFRESH_MS * 3)
    })
    // A wake-up in a dead spot should cost nothing at all - not one failed
    // fetch an hour, which is a radio switched on for no reason.
    expect(drought).not.toHaveBeenCalled()
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
