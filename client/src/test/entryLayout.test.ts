// The first-run layout's CSS contract.
//
// jsdom does no layout, so - as with appShellLayout.test.ts and
// siteLayout.test.ts - this asserts the contract rather than the pixels.
//
// The contract: the map stays visible behind the entry steps. App.tsx builds a
// whole extra MapLibre map to put it there, and every one of the three steps is
// a claim about it ("the whole trail's topo map lives on your phone", "pick how
// much detail", and the location step, which WIREFRAMES.md §5 specified as an
// overlay over the map so the reason for asking is visible). A stylesheet that
// covered the map would waste that build in silence and turn all three back
// into prose about a thing nobody has seen - which is exactly what the opaque
// full-page onboarding screen was, and the regression a later `min-height:
// 100svh` or a page background would quietly reintroduce.
//
// Resolved from the Vitest root (client/), which vite.config.ts pins.

import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const appCss = readFileSync(resolve(process.cwd(), 'src/App.css'), 'utf8')
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
  it('bounds the entry frame to the viewport, so the map keeps its share of it', () => {
    const rule = ruleFor(appCss, '.app__entry')

    expect(rule).toMatch(/(?<!min-)height:\s*100svh/)
    expect(rule).not.toMatch(/min-height:\s*100svh/)
    // The steps are positioned over the backdrop, which is absolute in this
    // same box - without a positioned ancestor it would escape to the viewport.
    expect(rule).toMatch(/position:\s*relative/)
  })

  it('lays the map behind the steps rather than above them', () => {
    const rule = ruleFor(appCss, '.app__entry-map')

    expect(rule).toMatch(/position:\s*absolute/)
    expect(rule).toMatch(/inset:\s*0/)
  })

  it('leaves the backdrop untappable, so no stray tap reaches the map controls', () => {
    // Paired with the `inert` App.tsx sets. A tap that got through to the
    // locate control would raise the OS location prompt before the step that
    // explains why we are asking.
    expect(ruleFor(appCss, '.app__entry-map')).toMatch(/pointer-events:\s*none/)
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

  it('drops the entry animation for anyone who has asked for less motion', () => {
    const at = onboardingCss.indexOf('@media (prefers-reduced-motion: reduce)')
    expect(at, 'no reduced-motion block').toBeGreaterThan(-1)

    const block = onboardingCss.slice(at, onboardingCss.indexOf('\n}', at))
    expect(block).toMatch(/\.onboarding__card/)
    expect(block).toMatch(/animation:\s*none/)
  })
})
