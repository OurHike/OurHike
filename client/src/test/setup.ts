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
