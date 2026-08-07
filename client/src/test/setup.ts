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
