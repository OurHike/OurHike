// Tests for useFinePointer.ts.
//
// Why this exists
// ---------------
// The hook decides whether the map screen offers zoom buttons, and the two
// wrong answers are not symmetrical. On a phone the buttons sit in the corner
// WIREFRAMES.md reserves for locate, which is the control that matters when
// someone is walking. On a desktop their absence leaves a mouse with the scroll
// wheel and nothing to press - the state this hook was written to fix. So the
// default when nothing can be determined is load-bearing and gets its own test.

import { renderHook, act } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { FINE_POINTER_MEDIA_QUERY, useFinePointer } from './useFinePointer'

type Listener = (event: MediaQueryListEvent) => void

/** A matchMedia jsdom does not provide, with a handle to change the answer. */
function stubMatchMedia(initial: boolean) {
  const listeners = new Set<Listener>()

  const query = {
    matches: initial,
    media: FINE_POINTER_MEDIA_QUERY,
    addEventListener: (_: string, listener: Listener) => listeners.add(listener),
    removeEventListener: (_: string, listener: Listener) => listeners.delete(listener),
  }

  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => query),
  )

  return {
    listenerCount: () => listeners.size,
    change(matches: boolean) {
      query.matches = matches
      act(() => {
        for (const listener of listeners) listener({ matches } as MediaQueryListEvent)
      })
    },
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useFinePointer', () => {
  it('is true where the primary pointer is a mouse', () => {
    stubMatchMedia(true)

    const { result } = renderHook(() => useFinePointer())

    expect(result.current).toBe(true)
  })

  it('is false on a touch screen, whatever its width', () => {
    stubMatchMedia(false)

    const { result } = renderHook(() => useFinePointer())

    expect(result.current).toBe(false)
  })

  it('asks about the pointer and not about the viewport', () => {
    stubMatchMedia(true)

    renderHook(() => useFinePointer())

    // A tablet is a wide touch screen and a half-width laptop window is still a
    // mouse, so a width query here would get both backwards.
    expect(window.matchMedia).toHaveBeenCalledWith('(pointer: fine)')
  })

  it('follows a mouse being plugged in', () => {
    const media = stubMatchMedia(false)
    const { result } = renderHook(() => useFinePointer())

    media.change(true)

    expect(result.current).toBe(true)
  })

  it('answers "touch" when the browser cannot be asked at all', () => {
    // The honest default: a phone that wrongly gets zoom buttons loses the
    // thumb zone, where a desktop that wrongly loses them still has a wheel.
    vi.stubGlobal('matchMedia', undefined)

    const { result } = renderHook(() => useFinePointer())

    expect(result.current).toBe(false)
  })

  it('stops listening when the component using it goes away', () => {
    const media = stubMatchMedia(true)
    const { unmount } = renderHook(() => useFinePointer())

    expect(media.listenerCount()).toBe(1)
    unmount()

    expect(media.listenerCount()).toBe(0)
  })
})
