// The pull request's camera gets a suite (.claude/skills/pr-screenshot).
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
// is left to the person running it, who is looking at the output anyway.

import { describe, it, expect } from 'vitest'
import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'
import {
  parseArgs,
  slug,
  markdownFor,
  budgetVerdict,
  repoPath,
  usage,
  PHONE,
  DESKTOP,
  CAPTURE_SCALE,
  BYTE_BUDGET,
  DEFAULT_OUT_DIR,
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

  it('writes where a screenshot can be committed without running a suite', () => {
    // `.github/` is in no suite's scope while every path under `client/` is in
    // the client suite's (scripts/suite_scopes.py), so a screenshot committed
    // under the client tree would run the whole client suite to prove a PNG
    // still parses. Asserting the client tree specifically, rather than that
    // the string contains '.github', is what would actually catch a default
    // moved back inside client/.
    expect(parseArgs(['whatever']).outDir).toBe(DEFAULT_OUT_DIR)
    expect(DEFAULT_OUT_DIR.startsWith(`${resolve('.')}/`)).toBe(false)
    expect(DEFAULT_OUT_DIR).toBe(resolve('..', '.github', 'pr-screenshots'))
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
    ])
    expect(parsed).toMatchObject({
      name: 'a-name',
      url: 'https://pr-9.example.pages.dev/',
      waitMs: 6000,
      scale: 1,
      outDir: '/tmp/elsewhere',
      fullPage: true,
    })
  })

  it('does not mistake a flag for the name', () => {
    expect(parseArgs(['--desktop', '--full']).name).toBeUndefined()
    expect(parseArgs(['--desktop', 'the-name']).name).toBe('the-name')
  })
})

describe('the file name', () => {
  // A space here becomes %20 inside a raw githubusercontent URL, and the
  // markdown around it stops being copy-pasteable.
  it('survives being a URL', () => {
    expect(slug('Entry card, step 2')).toBe('entry-card-step-2')
    expect(slug('  Legend  ')).toBe('legend')
    expect(slug('already-fine')).toBe('already-fine')
  })
})

describe('the line that goes in the pull request', () => {
  it('is an img tag, because markdown image syntax carries no width', () => {
    const line = markdownFor({
      owner: 'OurHike',
      repo: 'OurHike',
      sha: 'abc123',
      path: '.github/pr-screenshots/legend.png',
      width: 390,
      alt: 'legend',
    })
    expect(line).toBe(
      '<img src="https://raw.githubusercontent.com/OurHike/OurHike/abc123/' +
        '.github/pr-screenshots/legend.png" width="390" alt="legend">',
    )
  })

  it('pins a commit rather than a branch', () => {
    // A branch is deleted when the pull request merges; the commit it pointed
    // at survives in main's history, and so does the URL naming it.
    const line = markdownFor({
      owner: 'OurHike',
      repo: 'OurHike',
      sha: 'deadbee',
      path: 'a.png',
      width: 390,
      alt: 'a',
    })
    expect(line).toContain('/deadbee/')
  })
})

describe('where the capture landed', () => {
  const root = '/repo'

  it('gives a path a raw URL can use', () => {
    expect(repoPath('/repo/.github/pr-screenshots/a.png', root)).toBe(
      '.github/pr-screenshots/a.png',
    )
  })

  it('refuses to pretend /tmp is in the repository', () => {
    // The failure this prevents: a plausible raw URL pointing at a path that
    // was never committed, which renders as a broken image in review.
    expect(repoPath('/tmp/scratch/a.png', root)).toBeNull()
    expect(repoPath('/repo', root)).toBeNull()
  })
})

describe('the byte budget', () => {
  it('passes a capture the size of a real one', () => {
    // 79,290 bytes measured 2026-08-25 on the first-run entry card at 390x844
    // scale 2 - the densest DOM-only frame the app has.
    expect(budgetVerdict(79_290).overBudget).toBe(false)
  })

  it('says so, and says what to do, when a frame is too heavy', () => {
    const verdict = budgetVerdict(BYTE_BUDGET + 1)
    expect(verdict.overBudget).toBe(true)
    expect(verdict.message).toContain('Crop it')
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
