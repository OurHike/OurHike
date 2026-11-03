import { beforeEach, describe, expect, it } from 'vitest'

import { noteSignInStarted, SIGN_IN_WINDOW_MS, takeFinishedSignIn } from './signInMarker'

// What lets usage measurement count a sign-in and not a session restored at
// launch (#1902): only a sign-in this app started, finishing inside the window.

beforeEach(() => window.localStorage.clear())

describe('signInMarker', () => {
  it('counts a sign-in this app started and that has just finished', () => {
    noteSignInStarted(1_000)

    expect(takeFinishedSignIn(61_000)).toBe(true)
  })

  it('counts it once', () => {
    noteSignInStarted(1_000)
    takeFinishedSignIn(2_000)

    expect(takeFinishedSignIn(3_000)).toBe(false)
  })

  it('does not count an account nobody signed into here, such as one restored at launch', () => {
    expect(takeFinishedSignIn(1_000)).toBe(false)
  })

  it('does not let a sign-in abandoned long ago claim the next account restored', () => {
    noteSignInStarted(0)

    expect(takeFinishedSignIn(SIGN_IN_WINDOW_MS + 1)).toBe(false)
  })
})
