// A sign-in this app started, so a finished one can be told apart from a
// session restored at launch (#1902, features/EVENTING.md §0).
//
// Usage measurement counts sign-ins, and neither signal it could have used
// says "a sign-in just happened". An account restored from storage at launch
// arrives in App exactly as one that just signed in does. And supabase-js's
// own SIGNED_IN is, in its words, "emitted each time a user session is
// confirmed or re-established, including on user sign in and when refocusing
// a tab" (the onAuthStateChange docstring in @supabase/auth-js 2.115.0, the
// installed version, read 2026-10-27) - counting it would count every return
// to the app.
//
// What the app does know is when it STARTED a sign-in: the two doors in
// lib/auth.ts. An account that appears inside the window after that is the
// sign-in finishing - including across a provider's redirect, which reloads
// the page, which is why this is localStorage and not memory.

const KEY = 'ourhike:sign-in-started-at'

/**
 * Reasoned, not measured: an emailed code is read and typed within minutes,
 * and a provider round trip within seconds. Half an hour leaves room for the
 * slow email and stops a sign-in abandoned this morning from claiming the
 * next account restored this evening.
 */
export const SIGN_IN_WINDOW_MS = 30 * 60 * 1000

export function noteSignInStarted(now: number = Date.now()): void {
  try {
    window.localStorage.setItem(KEY, String(now))
  } catch {
    // Storage refused: this sign-in goes uncounted, which is the safe miss.
  }
}

/**
 * Whether a sign-in this app started has just finished. Consumes the marker
 * either way, so one sign-in is counted once.
 */
export function takeFinishedSignIn(now: number = Date.now()): boolean {
  try {
    const raw = window.localStorage.getItem(KEY)
    if (raw === null) return false
    window.localStorage.removeItem(KEY)
    const startedAt = Number(raw)
    return (
      Number.isFinite(startedAt) &&
      now >= startedAt &&
      now - startedAt <= SIGN_IN_WINDOW_MS
    )
  } catch {
    return false
  }
}
