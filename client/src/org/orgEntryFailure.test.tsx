/**
 * A chunk that never arrives must not take the whole app down with it.
 *
 * WHY THIS EXISTS. `lib/deferredScreen.tsx` states the failure every lazy
 * screen in this app is built to survive: "a build served half from one
 * deploy and half from the next, a precache that was evicted mid-hike - the
 * failure is thrown from render, so the nearest chrome/ErrorBoundary.tsx
 * shows its named fallback with the tab bar still up". That is a real state
 * for a PWA, not a hypothetical: a service worker holding a stale precache
 * will 404 a chunk whose hash moved.
 *
 * The organization surface did not get that. App.tsx returns it from an
 * EARLY RETURN - before its own ErrorBoundary and before all three
 * screen-level ones - so a failed `import('./org/OrgEntry')` unwound past
 * every boundary in App to the root one in main.tsx, whose own comment says
 * it "cannot offer the tab bar, because at this level the thing that renders
 * the tab bar is the thing that failed". A hiker who opened an org link on a
 * stale build lost the entire app rather than one screen.
 *
 * So this asserts the boundary is there and catches, which is the whole of
 * the repair. It is written against the boundary rather than against a real
 * failed import because a test cannot evict a service worker's precache.
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ErrorBoundary, ScreenFailed } from '../chrome/ErrorBoundary'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

afterEach(cleanup)

function Exploding(): never {
  throw new Error(
    'Failed to fetch dynamically imported module: /assets/OrgEntry-abc123.js',
  )
}

describe('the organization surface when its chunk never arrives', () => {
  it('shows a named fallback rather than unwinding to the root boundary', () => {
    // ErrorBoundary logs the failure by design; the console noise is not the
    // subject of this test.
    const quiet = vi.spyOn(console, 'error').mockImplementation(() => {})
    try {
      render(
        <ErrorBoundary fallback={() => <ScreenFailed what="The organization console" />}>
          <Exploding />
        </ErrorBoundary>,
      )
      expect(screen.getByText(/organization console/i)).toBeInTheDocument()
    } finally {
      quiet.mockRestore()
    }
  })
})

describe('App wires that boundary to the organization branch', () => {
  /** The branch itself, from its `if` to the close of its return.
   *
   *  Read from the source rather than rendered, for the reason
   *  `test/orgEmbeds.test.ts` reads its file: what is being asserted is the
   *  SHAPE of a wrapper around a lazy import, and a test that rendered it
   *  would have to defeat the bundler to make the import fail. The behaviour
   *  above proves the boundary catches; this proves it is in the path.
   */
  const branch = () => {
    // `readFileSync` rather than `test/repoFile.ts`: that helper is for files
    // OUTSIDE this package, and holds the CI scope list to each one it reads
    // (#503). App.tsx is in this suite's own tree, so editing it already runs
    // this test and there is no scope to declare.
    // From the package root rather than `import.meta.url`: under vitest that
    // is the dev server's http:// URL, not a file:// one.
    const app = readFileSync(resolve(process.cwd(), 'src/App.tsx'), 'utf8')
    const from = app.indexOf('if (inOrgSurface) {')
    expect(from).toBeGreaterThan(-1)
    return app.slice(from, app.indexOf('\n  }', from))
  }

  it('wraps the lazy org surface in an ErrorBoundary, outside the Suspense', () => {
    const source = branch()
    expect(source).toContain('<ErrorBoundary')
    // Outside, not inside: a boundary under Suspense still unwinds past it,
    // and the thing that fails here is the chunk Suspense is waiting for.
    expect(source.indexOf('<ErrorBoundary')).toBeLessThan(source.indexOf('<Suspense'))
  })

  it('names the surface in the fallback rather than saying "this screen"', () => {
    // The root boundary cannot say which screen failed. This one can, and a
    // hiker who followed an org link deserves to be told it was that and not
    // the app.
    expect(branch()).toContain('what="The organization console"')
  })
})
