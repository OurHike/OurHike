// Every visually-hidden radio, anchored to the option it lives in.
//
// The pickers keep a real <input type="radio"> for the arrow keys and the
// roving tabstop, hidden as a 1px `position: absolute` box behind its label.
// An absolute box belongs to its nearest POSITIONED ancestor, and with none
// it belongs to the document - where no screen's scroll pane can clip it, so
// a radio whose static position sits past 100svh hands the whole page a
// scrollbar of its own (#631). On Settings that put a scrollbar within a
// scrollbar, and the outer one scrolled the app frame up into blank paper.
//
// jsdom does no layout, so - as with appShellLayout.test.ts - this pins the
// contract in the text: wherever a stylesheet hides a `__input` as an
// absolute box, the matching `__option` must be `position: relative`. A sweep
// rather than five assertions, so the next picker copied from these fails the
// day it is pasted, not the day someone scrolls far enough to notice.
//
// Resolved from the Vitest root (client/), which vite.config.ts pins.

import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const SHEETS = ['src/screens/settings.css', 'src/chrome/chrome.css']

/** Top-level rules as [selector list, declarations] pairs, comments removed.
 *  Neither sheet nests rules inside at-rules; the desktop overrides live in
 *  desktop.css, whose positioning desktopLayout.test.ts asserts. */
function rulesOf(file: string): Array<[string, string]> {
  const bare = readFileSync(resolve(process.cwd(), file), 'utf8').replace(
    /\/\*[\s\S]*?\*\//g,
    '',
  )
  return [...bare.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map((m) => [m[1].trim(), m[2]])
}

describe.each(SHEETS)('hidden radios in %s', (sheet) => {
  const rules = rulesOf(sheet)

  // The hidden inputs: absolute boxes whose class is `<picker>__input`.
  const pickers = rules
    .filter(([, decls]) => /position:\s*absolute/.test(decls))
    .flatMap(([selectors]) => selectors.split(','))
    .map((selector) => selector.trim().match(/^\.([\w-]+)__input$/)?.[1])
    .filter((name): name is string => name !== undefined)

  it('finds them, so an empty sweep cannot pass as a clean one', () => {
    expect(pickers.length).toBeGreaterThan(0)
  })

  it.each(pickers)('anchors .%s__input to its own option', (picker) => {
    const option = rules.find(([selectors]) =>
      selectors.split(',').some((s) => s.trim() === `.${picker}__option`),
    )

    expect(option, `.${picker}__option has no rule in ${sheet}`).toBeDefined()
    expect(option?.[1]).toMatch(/position:\s*relative/)
  })
})
