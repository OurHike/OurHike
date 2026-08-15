// The first-run layout's CSS contract.
//
// jsdom does no layout, so - as with appShellLayout.test.ts and
// siteLayout.test.ts - this asserts the contract rather than the pixels.
//
// The contract: the map stays visible behind the entry steps, and nothing else
// on the map screen does. Every one of the three steps is a claim about the map
// ("the whole trail's topo map lives on your phone", "pick how much detail",
// and the location step, which WIREFRAMES.md §5 specified as an overlay over the
// map so the reason for asking is visible). A stylesheet that covered the map
// would turn all three back into prose about a thing nobody has seen - which is
// exactly what the opaque full-page onboarding screen was, and the regression a
// later `min-height: 100svh` or a page background would quietly reintroduce.
//
// Rewritten for #721. This used to assert `.app__entry` and `.app__entry-map` -
// a frame holding a SECOND MapView. There is one map now: the map screen itself
// is the backdrop, hidden down to its canvas by `.map-screen--entering`, with
// the steps overlaid on top. The guarantees are the same ones; where they live
// is not.
//
// Resolved from the Vitest root (client/), which vite.config.ts pins.

import { describe, expect, it } from 'vitest'
import { ENTRY_CARD_MAX_VIEWPORT_FRACTION } from '../screens/Onboarding'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const chromeCss = readFileSync(resolve(process.cwd(), 'src/chrome/chrome.css'), 'utf8')
const onboardingCss = readFileSync(
  resolve(process.cwd(), 'src/screens/onboarding.css'),
  'utf8',
)

function ruleFor(css: string, selector: string): string {
  const at = css.indexOf(`${selector} {`)
  expect(at, `${selector} not found`).toBeGreaterThan(-1)
  return css.slice(at, css.indexOf('}', at))
}

describe('first-run layout contract', () => {
  it('bounds the map screen to the viewport, so the map keeps its share of it', () => {
    const rule = ruleFor(chromeCss, '.map-screen')

    expect(rule).toMatch(/(?<!min-)height:\s*100svh/)
    expect(rule).not.toMatch(/min-height:\s*100svh/)
  })

  it('hides the entry chrome by exclusion, so a control added later is hidden too', () => {
    // THE test in this file, and the reason #721's hiding is written with
    // `:not()` rather than a list of class names. A list goes stale the first
    // time somebody adds a button to the map screen, and the failure mode is a
    // stray control sitting behind a modal - the exact trap App.tsx's reasoning
    // rules out. Each selector below hides every child of a wrapper except the
    // one on the path down to the canvas.
    const entering = chromeCss.slice(
      chromeCss.indexOf('.map-screen--entering'),
      chromeCss.indexOf('.map-screen--entering .maplibregl-ctrl'),
    )

    expect(entering).toMatch(/\.map-screen--entering > :not\(\.map-screen__main\)/)
    expect(entering).toMatch(/\.map-screen__main > :not\(\.map-screen__body\)/)
    expect(entering).toMatch(/\.map-screen__body > :not\(\.map-screen__canvas\)/)
    expect(entering).toMatch(/display:\s*none/)
  })

  it('keeps the licence credit drawn, which is not chrome and is not optional', () => {
    // The live sheet's OSM data is ODbL and the credit is a condition of using
    // it, so a map that is drawn has to be credited whether or not anyone may
    // touch it. It is the one thing inside the canvas that survives the hiding
    // above, so it is named as an exception rather than left to luck.
    const rule = ruleFor(
      chromeCss,
      '.map-screen--entering .map-screen__canvas > :not(.map-view):not(.map-attribution)',
    )

    expect(rule).toMatch(/display:\s*none/)
  })

  it('hides the map own controls, which would be pictures of dead buttons', () => {
    // They stack in the bottom corners, which is exactly where the entry card
    // is, and a tap on the locate control would raise the OS location prompt
    // ahead of the step whose whole job is explaining why we are asking.
    expect(ruleFor(chromeCss, '.map-screen--entering .maplibregl-ctrl')).toMatch(
      /display:\s*none/,
    )
  })

  it('lays the steps over the map rather than beside it, and lets taps through', () => {
    const rule = ruleFor(onboardingCss, '.onboarding')

    // A sibling of the map screen now, not a child of a frame that positions
    // it - so it needs the viewport itself.
    expect(rule).toMatch(/position:\s*fixed/)
    expect(rule).toMatch(/inset:\s*0/)
    // The empty region around the card is a window onto the map, not a scrim.
    expect(rule).toMatch(/pointer-events:\s*none/)
    expect(ruleFor(onboardingCss, '.onboarding__card')).toMatch(/pointer-events:\s*auto/)
  })

  it('never paints a page background over the map', () => {
    // The steps' own container was an opaque `background: var(--bg-page)`
    // full-page screen, which is the thing that hid the map. Only the card
    // inside it is allowed to be paper.
    expect(ruleFor(onboardingCss, '.onboarding')).not.toMatch(/background:/)
  })

  it('caps the card short of the screen, so the map shows above it at any height', () => {
    const rule = ruleFor(onboardingCss, '.onboarding__card')
    const capped = /max-height:\s*(\d+)%/.exec(rule)

    expect(capped, 'the entry card needs a max-height, or it fills the screen').not.toBe(
      null,
    )
    expect(Number(capped![1])).toBeLessThan(100)
    // What makes the cap safe: contents past it scroll inside the card rather
    // than being pushed off the bottom of the screen with the way forward.
    expect(rule).toMatch(/overflow-y:\s*auto/)
  })

  it('keeps the card cap and the map padding the same number', () => {
    // The map behind the steps is fitted against the strip the card does NOT
    // cover (App.tsx's entryFitPadding), so this fraction lives in two places
    // that cannot see each other: a CSS `max-height` and a TypeScript constant.
    // Drift between them is silent and one-directional in the worst way - the
    // card grows, the padding does not, and the trail goes back to being fitted
    // to a canvas three quarters of which nobody can see.
    const rule = ruleFor(onboardingCss, '.onboarding__card')
    const capped = /max-height:\s*(\d+)%/.exec(rule)

    expect(capped, 'the entry card needs a max-height').not.toBe(null)
    expect(Number(capped![1]) / 100).toBe(ENTRY_CARD_MAX_VIEWPORT_FRACTION)
  })

  it('drops the entry animation for anyone who has asked for less motion', () => {
    const at = onboardingCss.indexOf('@media (prefers-reduced-motion: reduce)')
    expect(at, 'no reduced-motion block').toBeGreaterThan(-1)

    const block = onboardingCss.slice(at, onboardingCss.indexOf('\n}', at))
    expect(block).toMatch(/\.onboarding__card/)
    expect(block).toMatch(/animation:\s*none/)
  })
})
