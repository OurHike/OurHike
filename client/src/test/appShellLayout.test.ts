import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

// jsdom does not do layout, so - as with siteLayout.test.ts - this asserts the
// CSS CONTRACT that was broken rather than the pixels.
//
// The bug: .app__screen was `min-height: 100svh`. A floor is not a ceiling, so
// on a long screen (Settings, under the More tab) the column simply grew past
// the viewport, its content pane grew with it, `overflow-y: auto` therefore had
// nothing to scroll, and the document scrolled instead - carrying the tab bar
// below the fold. The only navigation in the app was off-screen until you
// scrolled to the bottom of Settings to find it.
//
// Resolved from the Vitest root (client/), which vite.config.ts pins.
const css = readFileSync(resolve(process.cwd(), 'src/App.css'), 'utf8')

function ruleFor(selector: string): string {
  const at = css.indexOf(`${selector} {`)
  expect(at, `${selector} not found`).toBeGreaterThan(-1)
  return css.slice(at, css.indexOf('}', at))
}

describe('app shell layout contract', () => {
  it('bounds the screen to the viewport rather than only flooring it', () => {
    const rule = ruleFor('.app__screen')

    expect(rule).toMatch(/(?<!min-)height:\s*100svh/)
    expect(rule).not.toMatch(/min-height:\s*100svh/)
  })

  it('gives the content pane the overflow, so the tab bar below it stays put', () => {
    const rule = ruleFor('.app__screen > :first-child')

    expect(rule).toMatch(/overflow-y:\s*auto/)
    // Without this a flex item cannot shrink below its content, which puts the
    // overflow back on the page and the tab bar back off the bottom of it.
    expect(rule).toMatch(/min-height:\s*0/)
  })

  it('makes the pane the containing block, so hidden controls cannot stretch the page', () => {
    // The bug above, back through a different door (#631). The pickers hide
    // their real radios as `position: absolute` boxes, and an absolute box
    // belongs to its nearest positioned ancestor - with none anywhere, to the
    // document, which the pane's overflow cannot clip. Measured in Chromium
    // at 1280x800: radios below the first viewport-full held the document at
    // 1271px, a page scrollbar beside the pane's own, and everything under
    // 100svh blank paper. hiddenInputContainment.test.ts anchors each radio
    // to its picker; this anchors the pane itself, for whatever is next.
    const rule = ruleFor('.app__screen > :first-child')

    expect(rule).toMatch(/position:\s*relative/)
  })
})
