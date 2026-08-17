import { describe, it, expect } from 'vitest'
import { readRepoFile } from './repoFile'

// jsdom does not do layout, so this asserts the CSS CONTRACT that was broken:
// the list items must not be grid containers, because grid promotes every text
// run and inline element to its own item and shatters a sentence with a link.
// Read through repoFile.ts, which declares this out-of-tree read so
// ciScope.test.ts can hold the CI scope list to it (#503).
const html = readRepoFile('site/index.html')

function ruleFor(selector: string): string {
  const at = html.indexOf(`${selector} {`)
  expect(at, `${selector} not found`).toBeGreaterThan(-1)
  return html.slice(at, html.indexOf('}', at))
}

describe('install-section layout contract', () => {
  it('does not make .steps li a grid container', () => {
    const rule = ruleFor('.steps li')
    expect(rule).not.toMatch(/display:\s*grid/)
    expect(rule).toMatch(/position:\s*relative/)
    expect(rule).toMatch(/padding-left/)
  })

  it('does not make .checks li a grid container either', () => {
    const rule = ruleFor('.checks li')
    expect(rule).not.toMatch(/display:\s*grid/)
    expect(rule).toMatch(/position:\s*relative/)
  })

  it('keeps the markers out of flow so they cannot displace text', () => {
    expect(ruleFor('.steps li::before')).toMatch(/position:\s*absolute/)
    expect(ruleFor('.checks li::before')).toMatch(/position:\s*absolute/)
  })

  it('still has a step that contains a link - the case that broke', () => {
    expect(html).toMatch(/<li>\s*Open the app itself[^<]*<a href="\.\/app\/">/)
  })
})
