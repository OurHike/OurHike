// The preview's camera gets a suite (.claude/skills/pr-screenshot, #988).
//
// scripts/screenshot.mjs drives a browser, so most of it cannot be asserted
// cheaply - a real capture wants a Chromium, a dev server and about eight
// seconds, which is TESTING.md's argument against putting it in CI at all.
// What CAN be held is everything the script decides BEFORE it opens a
// browser, and that is deliberately where the mistakes live: a wrong flag
// default produces a screenshot of the wrong thing, and a wrong path produces
// a pull request with a broken image in it that nobody sees until review.
//
// So the pure decisions are exported and asserted here, and the browser half
// is left to pr-preview.yml, which runs it on every pull request - a break
// there shows up as a missing image in a comment rather than as a silent pass.

import { describe, it, expect } from 'vitest'
import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'
import {
  parseArgs,
  slug,
  budgetVerdict,
  usage,
  PHONE,
  PHONE_SMALL,
  DESKTOP,
  CAPTURE_SCALE,
  BYTE_BUDGET,
  DEFAULT_OUT_DIR,
  cspDirective,
  summariseCspReports,
  cspAnnotation,
} from '../../scripts/screenshot.mjs'

const SCRIPT = resolve(process.cwd(), 'scripts/screenshot.mjs')

describe('the defaults', () => {
  it('photographs a phone, because that is what the app is', () => {
    const { viewport, scale } = parseArgs(['whatever'])
    expect(viewport).toEqual(PHONE)
    expect(viewport.width).toBe(390)
    expect(scale).toBe(CAPTURE_SCALE)
  })

  it('skips first run, or every screenshot is of the same three cards', () => {
    expect(parseArgs(['whatever']).skipEntry).toBe(true)
    expect(parseArgs(['whatever', '--entry']).skipEntry).toBe(false)
  })

  it('writes somewhere gitignored, so a capture cannot be committed by accident', () => {
    // Inside dist/, which client/.gitignore ignores - and that is the rule
    // this default enforces rather than merely follows (#988). The previous
    // default wrote into a tracked directory and every screenshot became a
    // permanent, unretractable 79,290 bytes in a public tree.
    expect(parseArgs(['whatever']).outDir).toBe(DEFAULT_OUT_DIR)
    expect(DEFAULT_OUT_DIR).toBe(resolve('dist', '__screenshot'))
  })

  it('can photograph the built app, which is what CI deploys', () => {
    expect(parseArgs(['whatever']).dist).toBe(false)
    expect(parseArgs(['whatever', '--dist']).dist).toBe(true)
  })

  it('takes the smallest phone when asked, for a frame whose claim is that a screen fits on one', () => {
    expect(parseArgs(['whatever', '--small']).viewport).toEqual(PHONE_SMALL)
    expect(PHONE_SMALL).toMatchObject({ width: 375, height: 667, isMobile: true })
  })

  it('takes a laptop viewport for the marketing site', () => {
    expect(parseArgs(['whatever', '--desktop']).viewport).toEqual(DESKTOP)
  })

  it('reads the flags that carry values', () => {
    const parsed = parseArgs([
      'a-name',
      '--url=https://pr-9.example.pages.dev/',
      '--wait=6000',
      '--scale=1',
      '--out=/tmp/elsewhere',
      '--full',
      '--dist',
    ])
    expect(parsed).toMatchObject({
      name: 'a-name',
      url: 'https://pr-9.example.pages.dev/',
      waitMs: 6000,
      scale: 1,
      outDir: '/tmp/elsewhere',
      fullPage: true,
      dist: true,
    })
  })

  it('does not mistake a flag for the name', () => {
    expect(parseArgs(['--desktop', '--full']).name).toBeUndefined()
    expect(parseArgs(['--desktop', 'the-name']).name).toBe('the-name')
  })
})

describe('the file name', () => {
  // It becomes a path segment under /__screenshot/ on the preview host, and a
  // space there arrives as %20 in the comment's img src.
  it('survives being a URL', () => {
    expect(slug('Entry card, step 2')).toBe('entry-card-step-2')
    expect(slug('  Legend  ')).toBe('legend')
    expect(slug('already-fine')).toBe('already-fine')
  })
})

describe('the byte budget', () => {
  // All measured 2026-08-25 at 390x844 scale 2. The last two are what CI
  // actually produced on pr-989, where the tile source is reachable and the
  // map renders; the first is the same app in a sandbox that cannot reach it.
  it.each([
    ['entry card with no map (sandbox)', 79_290],
    ['entry card over a real basemap (CI)', 310_289],
    ['trail screen, full basemap (CI)', 743_012],
  ])('passes %s', (_label, bytes) => {
    expect(budgetVerdict(bytes).overBudget).toBe(false)
  })

  it('leaves room above the largest real frame', () => {
    // The regression this pins: a budget set from a sandbox measurement was
    // 150 KB, and would have warned on every honest screenshot CI takes -
    // a map-heavy frame is nearly ten times an empty-canvas one.
    expect(BYTE_BUDGET).toBeGreaterThan(743_012)
  })

  it('says so, and says what it means, when a frame is too heavy', () => {
    const verdict = budgetVerdict(BYTE_BUDGET + 1)
    expect(verdict.overBudget).toBe(true)
    expect(verdict.message).toContain('smell test')
  })
})

describe('the script itself', () => {
  it('refuses to run without a name, rather than writing undefined.png', () => {
    let status: number | undefined
    let stderr = ''
    try {
      execFileSync('node', [SCRIPT], { encoding: 'utf8', stdio: 'pipe' })
    } catch (error) {
      const failure = error as { status?: number; stderr?: string }
      status = failure.status
      stderr = failure.stderr ?? ''
    }
    expect(status).toBe(2)
    expect(stderr).toContain(usage().split('\n')[0])
  })
})

// The Content-Security-Policy the preview serves is report-only (#1602), so
// every violation it finds is a console message and nothing else. Before the
// camera listened for them they went to the console of a browser inside a CI
// job that nobody opens, which is the same as nowhere.
//
// The browser half is not testable here - it needs a page under a real policy,
// which is what pr-preview.yml's camera is. What is testable is the reading:
// that a report is recognised, that two hundred refusals of the same kind
// become one line, and that a clean run says nothing at all rather than an
// empty warning nobody can act on.
describe('reading a Content-Security-Policy report', () => {
  const refusedImage =
    "[Report Only] Refused to load the image 'http://localhost/app/favicon.svg' because " +
    'it violates the following Content Security Policy directive: "img-src \'none\'".'
  const refusedConnect =
    "Refused to connect to 'https://example.org/' because it violates the following " +
    'Content Security Policy directive: "connect-src \'self\'".'

  it('names the directive a report blames', () => {
    expect(cspDirective(refusedImage)).toBe('img-src')
    expect(cspDirective(refusedConnect)).toBe('connect-src')
  })

  it('ignores a console message that is not about a policy', () => {
    expect(
      cspDirective('Failed to load resource: the server responded with 404'),
    ).toBeNull()
    expect(cspDirective('')).toBeNull()
    expect(cspDirective(undefined)).toBeNull()
  })

  it('keeps a policy report it cannot place rather than dropping it', () => {
    // A report nobody can categorise is still a report somebody should see -
    // silently discarding it is how this signal would go quiet again.
    expect(cspDirective('Content Security Policy: something new chromium says')).toBe(
      'unknown',
    )
  })

  it('counts repeats per directive, so one map screen is a line and not two hundred', () => {
    const summary = summariseCspReports([
      refusedImage,
      refusedImage,
      refusedImage,
      refusedConnect,
      'unrelated console noise',
    ])
    expect(summary).toEqual([
      { directive: 'img-src', count: 3 },
      { directive: 'connect-src', count: 1 },
    ])
  })

  it('reports nothing for a run that reported nothing', () => {
    expect(summariseCspReports([])).toEqual([])
    expect(summariseCspReports(['a 404', 'a warning about an image size'])).toEqual([])
  })

  it('warns with the shot name and every directive, so the log says which screen', () => {
    const annotation = cspAnnotation(
      'trail-screen',
      summariseCspReports([refusedImage, refusedConnect]),
    )
    expect(annotation).toContain('::warning::')
    expect(annotation).toContain('trail-screen')
    expect(annotation).toContain('img-src (1)')
    expect(annotation).toContain('connect-src (1)')
    // The reader has to know which of the two possible faults this is before
    // they can act, and the annotation is the only place that fits.
    expect(annotation).toContain('report-only')
  })

  it('says nothing at all when a shot was clean, rather than an empty warning', () => {
    expect(cspAnnotation('trail-screen', [])).toBeNull()
  })
})
