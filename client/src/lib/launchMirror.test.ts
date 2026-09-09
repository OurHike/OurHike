import { afterEach, describe, expect, it } from 'vitest'
import {
  forgetLaunchMirror,
  LAUNCH_MIRROR_KEY,
  readLaunchMirror,
  writeLaunchMirror,
} from './launchMirror'

afterEach(() => {
  window.localStorage.clear()
})

describe('the launch mirror', () => {
  it('reads back what the record wrote', () => {
    writeLaunchMirror({ onboarding_completed: true, theme: 'dark' }, 'volunteer')

    expect(readLaunchMirror()).toEqual({
      onboardingCompleted: true,
      theme: 'dark',
      hikerMode: 'volunteer',
    })
  })

  it('is null on a phone that has never written one, so the launch waits for the record', () => {
    expect(readLaunchMirror()).toBe(null)
  })

  it('is null rather than a guess when what is stored is not a mirror', () => {
    window.localStorage.setItem(LAUNCH_MIRROR_KEY, 'not json')
    expect(readLaunchMirror()).toBe(null)

    window.localStorage.setItem(LAUNCH_MIRROR_KEY, JSON.stringify({ theme: 'dark' }))
    expect(readLaunchMirror()).toBe(null)

    window.localStorage.setItem(LAUNCH_MIRROR_KEY, 'null')
    expect(readLaunchMirror()).toBe(null)
  })

  it('repairs a theme or a mode this build does not know, the way the record is repaired', () => {
    window.localStorage.setItem(
      LAUNCH_MIRROR_KEY,
      JSON.stringify({ onboardingCompleted: true, theme: 'sepia', hikerMode: 'thru' }),
    )

    expect(readLaunchMirror()).toEqual({
      onboardingCompleted: true,
      theme: 'auto',
      // 'thru' is the middle mode's old word and maps forward (lib/hikerMode.ts).
      hikerMode: 'long',
    })
  })

  it('forgets on request, so a reset record is not contradicted by a stale mirror', () => {
    writeLaunchMirror({ onboarding_completed: true, theme: 'auto' }, 'day')
    forgetLaunchMirror()

    expect(readLaunchMirror()).toBe(null)
  })

  it('neither throws nor lies where storage is unreachable', () => {
    const original = Object.getOwnPropertyDescriptor(window, 'localStorage')
    Object.defineProperty(window, 'localStorage', {
      configurable: true,
      get() {
        throw new Error('blocked')
      },
    })
    try {
      expect(() =>
        writeLaunchMirror({ onboarding_completed: true, theme: 'auto' }, 'day'),
      ).not.toThrow()
      expect(readLaunchMirror()).toBe(null)
      expect(() => forgetLaunchMirror()).not.toThrow()
    } finally {
      if (original !== undefined) Object.defineProperty(window, 'localStorage', original)
    }
  })
})
