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
