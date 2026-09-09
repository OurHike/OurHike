import '@testing-library/jest-dom/vitest'

// jsdom has never implemented matchMedia, and accessing it throws rather than
// returning undefined - so a component that asks whether it is running as an
// installed app (lib/useInstallPrompt.ts) takes down the whole render.
//
// Polyfilled here rather than guarded in the app, because the gap is jsdom's:
// every browser this ships to has had matchMedia for over a decade, and code
// defending against its absence would be defending against nothing real.
// Reports "not standalone", which is what a test environment honestly is; a
// test that needs the other answer stubs it itself.
if (typeof window !== 'undefined' && typeof window.matchMedia !== 'function') {
  window.matchMedia = (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList
}

// jsdom has no requestIdleCallback either, and since #1324 the shell warms
// the map on one: the entry steps no longer build a map behind them, so what
// mounts it for a hiker who has just finished first run is an idle callback.
//
// Polyfilled for the same reason as matchMedia above - the gap is jsdom's,
// not the app's - but with a caveat matchMedia does not need. This runs the
// callback on the next macrotask, which is NOT what an idle callback is: a
// real browser waits for the frame to be free and can wait seconds on a busy
// page. So a test using this proves the callback is REACHED and what it then
// does; it proves nothing about when. The app's own fallback for browsers
// without it (Safari) is a one-second timer, and a test running against that
// would be a test racing `waitFor`'s default window.
//
// `deadline` reports an unlimited budget rather than a plausible one: a
// caller that trims its work to fit would take the wrong branch in every
// test, and this shim exists to run callbacks, not to model scheduling.
if (typeof window !== 'undefined' && typeof window.requestIdleCallback !== 'function') {
  window.requestIdleCallback = ((callback: IdleRequestCallback) =>
    setTimeout(
      () => callback({ didTimeout: false, timeRemaining: () => 50 }),
      0,
    ) as unknown as number) as typeof window.requestIdleCallback
  window.cancelIdleCallback = ((handle: number) =>
    clearTimeout(handle)) as typeof window.cancelIdleCallback
}

// Session storage is shared, mutable, per-FILE state in jsdom, and since #311
// the shell writes to it: the camera is remembered there so a reload the hiker
// did not ask for comes back to the view they left (lib/cameraMemory.ts).
//
// Without this, one test that pans the map decides where the map opens in
// every test after it - which is how four App.test.tsx cases about the opening
// view started failing for a reason none of them had anything to do with. The
// DOM is reset between tests by Testing Library's cleanup; this is the same
// courtesy for the other global the app now keeps state in.
import { afterEach } from 'vitest'

afterEach(() => {
  try {
    window.sessionStorage.clear()
    window.localStorage.clear()
  } catch {
    // A test that stubs storage to throw has already made its point.
  }
})

// TESTING.md promises "any unmocked request raises" and the pipeline suite
// enforces it; this is the client's half (#324). Only a handful of files stub
// fetch themselves (appHarness does it for every App test), and nothing
// structurally stopped a new test from reaching the wire - node ships a real
// global fetch, so an unstubbed call would have quietly hit the network.
// Tests that need fetch keep stubbing it (vi.stubGlobal restores over this
// and unstub returns to it); tests that never mention fetch now fail loudly
// instead of silently depending on the machine they run on.
globalThis.fetch = (input: RequestInfo | URL): Promise<Response> => {
  throw new Error(
    `Test tried to fetch ${String(input)} without stubbing fetch. ` +
      'Mock it (vi.stubGlobal, or the appHarness) - TESTING.md: tests never touch the network.',
  )
}
