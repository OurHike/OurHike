import { describe, expect, it } from 'vitest'
import { readRepoFile } from '../test/repoFile'
import { BLAZE_ICONS, BLAZE_ICON_NAMES, blazeIconPath } from './blazeIcons'

// The exporter admits an item's `icon` only from pipeline/lib/challenges.py's
// ICON_NAMES, and this module must draw every one of them: a name the
// exporter lets through that the shell cannot draw is a blank tile on every
// phone. Read out of the Python rather than retyped, so the two lists cannot
// drift apart without this going red.

describe('the blaze card’s icon set (#1962)', () => {
  it('draws exactly the names pipeline/lib/challenges.py ICON_NAMES admits, in the same order', () => {
    const source = readRepoFile('pipeline/lib/challenges.py')
    const block = source.match(/^ICON_NAMES = \(([\s\S]*?)^\)/m)
    expect(block).not.toBeNull()
    const names = [...block![1].matchAll(/"([a-z]+)"/g)].map((match) => match[1])
    expect(names.length).toBeGreaterThan(20)
    expect(BLAZE_ICON_NAMES).toEqual(names)
  })

  it('draws every glyph as one stroke path on the 24-unit box', () => {
    for (const name of BLAZE_ICON_NAMES) {
      expect(BLAZE_ICONS[name], name).toMatch(/^M[\d.]/)
      // Nothing a path cannot hold: no markup, no script, no URL.
      expect(BLAZE_ICONS[name], name).not.toMatch(/[<>&"']/)
    }
  })

  it('falls back to the learn glyph for a name it does not know, never to nothing', () => {
    expect(blazeIconPath('rocket')).toBe(BLAZE_ICONS.learn)
    expect(blazeIconPath(null)).toBe(BLAZE_ICONS.learn)
    expect(blazeIconPath('mountain')).toBe(BLAZE_ICONS.mountain)
  })
})
