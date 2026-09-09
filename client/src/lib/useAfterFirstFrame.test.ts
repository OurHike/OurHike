import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useAfterFirstFrame } from './useAfterFirstFrame'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('useAfterFirstFrame', () => {
  it('is false in the first render and true a frame later', async () => {
    const { result } = renderHook(() => useAfterFirstFrame())
    expect(result.current).toBe(false)
    await waitFor(() => expect(result.current).toBe(true))
  })

  it('releases a launch that never gets a frame, which is a hidden tab', async () => {
    // A browser runs no animation frames in a hidden document, and a hidden
    // launch is an ordinary one: a phone restoring its tabs, a link opened in
    // the background, an app resumed with the screen still off. Waiting on a
    // frame alone meant such a launch fetched no conditions at all until
    // somebody looked at it.
    vi.stubGlobal(
      'requestAnimationFrame',
      vi.fn(() => 1),
    )
    vi.stubGlobal('cancelAnimationFrame', vi.fn())

    const { result } = renderHook(() => useAfterFirstFrame())
    expect(result.current).toBe(false)

    await waitFor(() => expect(result.current).toBe(true), { timeout: 2_000 })
  })

  it('releases where there is no requestAnimationFrame at all', async () => {
    vi.stubGlobal('requestAnimationFrame', undefined)

    const { result } = renderHook(() => useAfterFirstFrame())

    await waitFor(() => expect(result.current).toBe(true), { timeout: 2_000 })
  })
})
