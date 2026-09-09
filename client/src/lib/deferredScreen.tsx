// A screen whose code arrives when it is first shown, or when the launch is
// idle enough to fetch it ahead - whichever comes first (#1302).
//
// WHY NOT React.lazy. The shape is the same - a component that renders its
// module's export once the import() lands - with one difference that matters
// to this codebase: `preload()`. React.lazy resolves on first RENDER and only
// then, so every test that renders the shell and reaches for a screen would
// have to wait a tick it never waited before, and so would a hiker's first
// tap on Plan. Here the module can be loaded ahead of any render - the shell
// does it on idle after the first frame, and src/test/appHarness.ts does it
// before every test - after which the screen renders synchronously, exactly
// as it did when it was a static import. map/mapEngineLoader.ts is the same
// idea for the map engine, and the reasoning about the second mount being
// synchronous is that file's.
//
// WHY AT ALL. Measured 2026-09-09 on production's own build: `main-*.js` was
// 989 KB raw, 283 KB compressed, and `src/screens/` was a quarter of it -
// Plan, More and its five destinations, Moderation, the report and closure
// forms, Find a hike, the volunteer screens - every one parsed before the
// first frame of a launch that shows Today. features/LAUNCH_BUDGET.md §2.1
// has the attribution and §3 the budget this helps meet.
//
// WHILE IT LOADS, NOTHING. A screen this wraps is a whole tab or a whole flow,
// and the beat between a tap and its chunk arriving is a cache read on any
// phone that has installed the app - every chunk is in the service worker's
// precache (vite.config.ts) or inside the Capacitor binary - so a spinner
// would flash for the width of a frame. An empty pane for that frame is
// honest; a placeholder screen would be a second thing to design and keep in
// step with the real one.
//
// IF THE CHUNK NEVER COMES - a build served half from one deploy and half from
// the next, a precache that was evicted mid-hike - the failure is thrown from
// render, so the nearest chrome/ErrorBoundary.tsx shows its named fallback
// with the tab bar still up, and the next mount tries the import again.

import {
  createElement,
  useEffect,
  useState,
  type ComponentType,
  type ReactElement,
} from 'react'

export interface DeferredScreen<P extends object> {
  (props: P): ReactElement | null
  /** Loads the module ahead of any render. Idempotent; shares one import. */
  preload(): Promise<void>
  displayName: string
}

export function deferredScreen<P extends object>(
  load: () => Promise<ComponentType<P>>,
  name: string,
): DeferredScreen<P> {
  let loaded: ComponentType<P> | null = null
  let pending: Promise<void> | null = null

  const ensure = (): Promise<void> => {
    if (loaded !== null) return Promise.resolve()
    if (pending === null) {
      pending = load().then(
        (component) => {
          loaded = component
        },
        (error: unknown) => {
          // Forgotten, so the next ask starts a fresh import rather than
          // replaying one failure for the rest of the session.
          pending = null
          throw error
        },
      )
    }
    return pending
  }

  function Screen(props: P): ReactElement | null {
    const [, arrived] = useState(0)
    const [failure, setFailure] = useState<unknown>(null)
    const Loaded = loaded

    useEffect(() => {
      if (Loaded !== null) return
      let live = true
      ensure().then(
        () => {
          if (live) arrived((count) => count + 1)
        },
        (error: unknown) => {
          if (live) setFailure(error instanceof Error ? error : new Error(String(error)))
        },
      )
      return () => {
        live = false
      }
    }, [Loaded])

    if (failure !== null) throw failure
    if (Loaded === null) return null
    return createElement(Loaded, props)
  }

  Screen.displayName = `Deferred(${name})`
  return Object.assign(Screen, { preload: ensure })
}
