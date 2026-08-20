// The preload in the document head, against the key the app actually fetches.
//
// WHY THIS PAIR NEEDS A TEST
//
// `vite.config.ts` injects `<link rel="preload" as="fetch">` for the
// corridor-view centerline so the request overlaps the app's own boot (#869 -
// measured, first paint at 576 ms and the first launch request at ~1,560 ms,
// and the second between them is what the preload spends). The browser is
// what joins the two ends: it matches the preload to the app's later fetch by
// URL and by `as`, and neither end knows about the other.
//
// So both ways this can break are SILENT and cost exactly what the preload
// was worth:
//
//  - a URL that does not match is a file downloaded twice - the preload
//    warmed a cache nothing reads, and the map still waits.
//  - the wrong `as` is the same thing, plus a console warning nobody sees on
//    a phone. `fetch` is the one that matches `fetch()`; `fetchpriority` or
//    `as="image"` would not.
//
// Neither fails a build, a typecheck or any other test in this suite, because
// a preload is advice and a browser ignoring advice looks like nothing at
// all. This reads the config's own text and holds it to lib/config.ts's key.

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { TRAILS_OVERVIEW_KEY } from '../lib/config'

const config = readFileSync(resolve(process.cwd(), 'vite.config.ts'), 'utf8')

/** The preload the plugin builds, as it appears in the config's source. */
function preloadAttributes(): { href: string; as: string; rel: string } {
  const href = /href: `\$\{base\}\/([^`]+)`/.exec(config)
  const as = /as: '([^']+)'/.exec(config)
  const rel = /rel: '([^']+)'/.exec(config)
  expect(
    href,
    'Could not find the preload href in vite.config.ts. If the plugin was ' +
      'rewritten, fix the pattern here rather than deleting the test - what ' +
      'it guards cannot fail any other way.',
  ).not.toBeNull()
  expect(as).not.toBeNull()
  expect(rel).not.toBeNull()
  return { href: href![1], as: as![1], rel: rel![1] }
}

describe('the corridor-view centerline preload', () => {
  it('preloads the key the app fetches, spelled the same way', () => {
    expect(preloadAttributes().href).toBe(TRAILS_OVERVIEW_KEY)
  })

  it('preloads it as a fetch, which is what makes the browser reuse it', () => {
    const { rel, as } = preloadAttributes()

    expect(rel).toBe('preload')
    expect(as).toBe('fetch')
  })

  it('carries crossorigin, without which a cross-origin preload is fetched twice', () => {
    // The bucket is another origin (lib/config.ts's DATA_BASE_URL), and a
    // `as="fetch"` preload without `crossorigin` is made in a different mode
    // from the app's own CORS fetch - so the browser keeps them apart and
    // downloads the file twice.
    expect(config).toMatch(/crossorigin: 'anonymous'/)
  })

  it('emits nothing at all when no bucket is configured', () => {
    // A build with no VITE_DATA_BASE_URL would resolve the href against the
    // app's own origin, where it is a 404 on every launch - a wasted request
    // and a console error on the build with the least to spare. Asserted on
    // the guard rather than by building: `npm run build` runs in this suite's
    // own workflow, and a second one here would double its slowest step.
    expect(config).toMatch(/if \(base === ''\) return \[\]/)
  })
})
