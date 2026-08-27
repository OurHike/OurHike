import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'

const { publishedSnapshot } = vi.hoisted(() => ({ publishedSnapshot: vi.fn() }))
vi.mock('./dataManifest', () => ({ publishedSnapshot }))
vi.mock('./config', () => ({ DATA_CONFIGURED: true }))

import { usePublishedSizes, NO_PUBLISHED_SIZES } from './usePublishedSizes'

/** A promise this test settles by hand, so nothing is left pending at teardown
 *  and "before the bucket answered" is a state the test can actually stand in. */
function deferred<T>() {
  let settle!: (value: T) => void
  let fail!: (reason: unknown) => void
  const promise = new Promise<T>((resolve, reject) => {
    settle = resolve
    fail = reject
  })
  return { promise, settle, fail }
}

beforeEach(() => publishedSnapshot.mockReset())

describe('usePublishedSizes (#505)', () => {
  it('starts with nothing, so a caller reads its own constant until the bucket answers', async () => {
    const pending = deferred<{ sizes: Record<string, number> }>()
    publishedSnapshot.mockReturnValue(pending.promise)

    const { result } = renderHook(() => usePublishedSizes())

    expect(result.current).toEqual(NO_PUBLISHED_SIZES)
    pending.settle({ sizes: {} })
    await waitFor(() => expect(publishedSnapshot).toHaveBeenCalled())
  })

  it('hands back what the manifest measured', async () => {
    publishedSnapshot.mockResolvedValue({ sizes: { 'dem.pmtiles': 123_456 } })

    const { result } = renderHook(() => usePublishedSizes())

    await waitFor(() => expect(result.current['dem.pmtiles']).toBe(123_456))
  })

  it('stays empty when the manifest names no size, rather than reporting zero', async () => {
    // The distinction that matters: no answer means "use your constant", where
    // a zero would mean "this download is free" - the confidently wrong one.
    // publishedSnapshot resolves rather than throws on an unreadable manifest,
    // so this is the shape it really returns for one.
    publishedSnapshot.mockResolvedValue({ sizes: {} })

    const { result } = renderHook(() => usePublishedSizes())

    await waitFor(() => expect(publishedSnapshot).toHaveBeenCalled())
    expect(result.current).toEqual({})
  })

  it('aborts the in-flight read when the screen goes away', async () => {
    const pending = deferred<{ sizes: Record<string, number> }>()
    publishedSnapshot.mockReturnValue(pending.promise)

    const { unmount } = renderHook(() => usePublishedSizes())
    await waitFor(() => expect(publishedSnapshot).toHaveBeenCalled())

    const { signal } = publishedSnapshot.mock.calls[0][0] as { signal: AbortSignal }
    expect(signal.aborted).toBe(false)

    unmount()

    expect(signal.aborted).toBe(true)
    pending.settle({ sizes: {} })
  })

  // NOT TESTED HERE, deliberately: that the hook's `.catch` swallows the
  // AbortError the teardown above provokes. publishedSnapshot rethrows exactly
  // that one error and resolves for everything else (dataManifest.ts:248-251),
  // so the catch is real and needed - but a rejection routed through a
  // vi.mock'd module is reported as unhandled by this runner even once the
  // consumer has caught it. Verified instead with a standalone probe of the
  // identical chain shape and sequence, which passes; asserting it through the
  // module mock would mean testing the harness rather than the hook.
})
