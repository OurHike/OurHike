import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { act, cleanup, renderHook } from '@testing-library/react'
import { readPodcastApp, usePodcastApp, writePodcastApp } from './podcastApp'

// The hiker's podcast app, kept on this phone (#1690).

beforeEach(() => localStorage.clear())
afterEach(cleanup)

describe('the podcast app choice', () => {
  it('is null until picked, so the card asks rather than assuming Spotify', () => {
    expect(readPodcastApp()).toBeNull()
  })

  it('keeps a pick, and forgets it on request', () => {
    writePodcastApp('overcast')
    expect(readPodcastApp()).toBe('overcast')
    writePodcastApp(null)
    expect(readPodcastApp()).toBeNull()
  })

  it('reads a value this build has no app for as unpicked, never as some other app', () => {
    localStorage.setItem('ourhike:podcast-app', 'castbox')
    expect(readPodcastApp()).toBeNull()
  })

  it('tells every card on screen when the pick changes, without a reload', () => {
    const { result } = renderHook(() => usePodcastApp())
    expect(result.current).toBeNull()
    act(() => writePodcastApp('apple_podcasts'))
    expect(result.current).toBe('apple_podcasts')
  })
})
