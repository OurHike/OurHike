import { describe, it, expect } from 'vitest'
import { readRepoFile } from './repoFile'

// jsdom does not do layout, so this asserts the CSS CONTRACT that was broken
// once on the original landing page: list items must not be grid containers,
// because grid promotes every text run and inline element to its own item
// and shatters a sentence with a link. The rules moved into the built site's
// stylesheet (#116) and the contract moved with them. Read through
// repoFile.ts, which declares these out-of-tree reads so ciScope.test.ts can
// hold the CI scope list to them (#503).
const css = readRepoFile('site/src/styles/site.css')
const installPage = readRepoFile('site/src/pages/get-the-app.astro')

function ruleFor(selector: string): string {
  const at = css.indexOf(`${selector} {`)
  expect(at, `${selector} not found`).toBeGreaterThan(-1)
  return css.slice(at, css.indexOf('}', at))
}

describe('install-section layout contract', () => {
  it('does not make .steps li a grid container', () => {
    const rule = ruleFor('.steps li')
    expect(rule).not.toMatch(/display:\s*grid/)
    // The numbering is a ::marker now - native list markers cannot displace
    // the text they mark, which is the same guarantee the old absolutely
    // positioned ::before bought, without the positioning.
    expect(ruleFor('.steps li::marker')).toBeTruthy()
  })

  it('does not make .checks li a grid container either', () => {
    const rule = ruleFor('.checks li')
    expect(rule).not.toMatch(/display:\s*grid/)
    expect(rule).toMatch(/position:\s*relative/)
    expect(rule).toMatch(/padding-left/)
  })

  it('keeps the check markers out of flow so they cannot displace text', () => {
    expect(ruleFor('.checks li::before')).toMatch(/position:\s*absolute/)
  })

  it('still has a step that contains a link - the case that broke', () => {
    expect(installPage).toMatch(/<li>\s*Open the app itself[^<]*<a href="\/app\/">/)
  })
})
