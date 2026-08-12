import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useAvailableBytes } from './useAvailableBytes'

// The capability read behind #555's greyed rung. What is worth testing is the
// part a plain `useEffect` would get wrong: there is no event for storage, so
// "comes back when the room does" depends entirely on re-reading at the two
// moments the answer can have changed.

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function stubEstimate(...answers: { quota: number; usage: number }[]) {
  let at = 0
  const estimate = vi.fn(async () => answers[Math.min(at++, answers.length - 1)])
  vi.stubGlobal('navigator', { ...globalThis.navigator, storage: { estimate } })
  return estimate
}

describe('useAvailableBytes', () => {
  it('reports what the browser says is free', async () => {
    stubEstimate({ quota: 1_000_000, usage: 250_000 })

    const { result } = renderHook(() => useAvailableBytes())

    await waitFor(() => expect(result.current.bytes).toBe(750_000))
  })

  it('starts as unknown rather than as zero', () => {
    // A zero would grey every rung on the first frame, which is a claim about
    // the phone made before anything has been asked.
    stubEstimate({ quota: 1_000_000, usage: 250_000 })

    const { result } = renderHook(() => useAvailableBytes())

    expect(result.current.bytes).toBeNull()
  })

  it('stays unknown where the browser will not say', async () => {
    vi.stubGlobal('navigator', { ...globalThis.navigator, storage: {} })

    const { result } = renderHook(() => useAvailableBytes())

    // Given a tick to answer, and the answer is still "cannot say" - which
    // offers every level rather than none.
    await waitFor(() => expect(result.current.bytes).toBeNull())
  })

  it('re-reads when the app asks, which is how a delete brings a rung back', async () => {
    // #554 measured that Chromium's own accounting may never notice a delete,
    // so an app-driven re-read is the only thing that will.
    const estimate = stubEstimate(
      { quota: 1_000_000, usage: 900_000 },
      { quota: 1_000_000, usage: 100_000 },
    )
    const { result } = renderHook(() => useAvailableBytes())
    await waitFor(() => expect(result.current.bytes).toBe(100_000))

    act(() => result.current.refresh())

    await waitFor(() => expect(result.current.bytes).toBe(900_000))
    expect(estimate).toHaveBeenCalledTimes(2)
  })

  it('re-reads on returning to the tab, which is where iOS frees space', async () => {
    // On iOS the remedy happens in Settings, not in this tab, so the rung has
    // to come back on return rather than at the next cold start.
    stubEstimate({ quota: 1_000_000, usage: 900_000 }, { quota: 1_000_000, usage: 0 })
    const { result } = renderHook(() => useAvailableBytes())
    await waitFor(() => expect(result.current.bytes).toBe(100_000))

    act(() => {
      vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
      document.dispatchEvent(new Event('visibilitychange'))
    })

    await waitFor(() => expect(result.current.bytes).toBe(1_000_000))
  })

  it('ignores the tab going away', async () => {
    // Hidden is not a moment anything changed, and re-reading then would just
    // be a wasted call on every backgrounding.
    const estimate = stubEstimate({ quota: 1_000_000, usage: 900_000 })
    const { result } = renderHook(() => useAvailableBytes())
    await waitFor(() => expect(result.current.bytes).toBe(100_000))

    act(() => {
      vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
      document.dispatchEvent(new Event('visibilitychange'))
    })

    expect(estimate).toHaveBeenCalledTimes(1)
  })

  it('stops listening when it goes away', async () => {
    stubEstimate({ quota: 1_000_000, usage: 900_000 })
    const remove = vi.spyOn(document, 'removeEventListener')
    const { unmount, result } = renderHook(() => useAvailableBytes())
    await waitFor(() => expect(result.current.bytes).toBe(100_000))

    unmount()

    expect(remove).toHaveBeenCalledWith('visibilitychange', expect.any(Function))
  })
})
