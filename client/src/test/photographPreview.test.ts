// The preview's shot list gets a suite (#998), the same split
// screenshotScript.test.ts holds: everything the runner decides BEFORE a
// browser opens is exported and asserted here, and the browser half is left
// to pr-preview.yml, where a break shows up as a missing image in a comment.
//
// The decisions worth pinning are the ones that would fail silently: a shot
// list that quietly stopped including what the pull request changed would
// look exactly like a pull request that changed nothing a camera can see —
// which is the failure #998 exists to end, not to re-implement.

import { describe, it, expect } from 'vitest'
import { existsSync } from 'node:fs'
import { resolve } from 'node:path'
import {
  planShots,
  normaliseRecipe,
  renderComment,
  parseRunnerArgs,
  escapeAttr,
  escapeCell,
  STANDING,
  RECIPE_DIR,
  PREVIEW_BASE_PLACEHOLDER,
  DISPLAY_WIDTH,
  DESKTOP_DISPLAY_WIDTH,
} from '../../scripts/photograph-preview.mjs'
import { DEFAULT_WAIT_MS, DESKTOP } from '../../scripts/screenshot.mjs'

const everything = () => true

describe('the shot list', () => {
  it('always carries the standing two, which really exist as recipes', () => {
    const { shots } = planShots({ exists: everything })
    expect(shots.map((s) => s.name)).toEqual(STANDING)
    expect(STANDING).toEqual(['first-run', 'trail-screen'])
    for (const name of STANDING) {
      // The names are a promise about files. A renamed recipe with a stale
      // STANDING entry would fail every preview's photograph step at once.
      expect(existsSync(resolve(RECIPE_DIR, `${name}.mjs`))).toBe(true)
    }
  })

  it('photographs the recipes the pull request touched, and leads with them', () => {
    const { shots } = planShots({
      changed: [
        'client/src/chrome/Legend.tsx',
        `client/${RECIPE_DIR}/legend.mjs`,
        'pipeline/export_poi.py',
      ],
      exists: everything,
    })
    expect(shots.map((s) => s.name)).toEqual(['legend', ...STANDING])
    expect(shots[0].changed).toBe(true)
    expect(shots[1].changed).toBe(false)
  })

  it('does not mistake other changed files for recipes', () => {
    const { shots } = planShots({
      // Neither a README beside the recipes, nor an .mjs elsewhere, nor a
      // nested path is a recipe - only preview-shots/*.mjs drives a camera.
      changed: [
        `client/${RECIPE_DIR}/README.md`,
        'client/scripts/screenshot.mjs',
        `client/${RECIPE_DIR}/deeper/nested.mjs`,
      ],
      exists: everything,
    })
    expect(shots.map((s) => s.name)).toEqual(STANDING)
  })

  it('shows a changed standing recipe once, in the changed section', () => {
    const { shots } = planShots({
      changed: [`client/${RECIPE_DIR}/first-run.mjs`],
      exists: everything,
    })
    expect(shots.map((s) => s.name)).toEqual(['first-run', 'trail-screen'])
    expect(shots[0].changed).toBe(true)
  })

  it('skips a deleted recipe rather than failing the run over it', () => {
    // A deletion arrives in the file list like any other touch; renames
    // arrive under both names. The old path must not error the camera.
    const gone = `${RECIPE_DIR}/water-card.mjs`
    const { shots, skipped } = planShots({
      changed: [`client/${gone}`],
      exists: (file: string) => file !== gone,
    })
    expect(shots.map((s) => s.name)).toEqual(STANDING)
    expect(skipped).toHaveLength(1)
    expect(skipped[0].file).toBe(gone)
  })

  it('nudges when client code changed and nobody pointed the camera', () => {
    const touched = { changed: ['client/src/screens/Plan.tsx'], exists: everything }
    expect(planShots(touched).nudge).toBe(true)
    expect(
      planShots({
        changed: [...touched.changed, `client/${RECIPE_DIR}/plan.mjs`],
        exists: everything,
      }).nudge,
    ).toBe(false)
    // A docs- or pipeline-only pull request has nothing to photograph and
    // gets no nudge - crying wolf here is how the line gets ignored.
    expect(
      planShots({ changed: ['pipeline/export_poi.py'], exists: everything }).nudge,
    ).toBe(false)
  })

  it('takes a locally asked recipe with or without the client/ prefix', () => {
    for (const asked of [`${RECIPE_DIR}/legend.mjs`, `client/${RECIPE_DIR}/legend.mjs`]) {
      const { shots } = planShots({ asked: [asked], exists: everything })
      expect(shots[0]).toMatchObject({ name: 'legend', changed: true })
    }
  })

  it('refuses a path that is not a recipe, naming it', () => {
    expect(() => planShots({ asked: ['src/App.tsx'], exists: everything })).toThrow(
      'src/App.tsx',
    )
  })
})

describe('the recipe contract', () => {
  it('fills what a minimal recipe leaves out', () => {
    expect(normaliseRecipe({}, 'water-card')).toEqual({
      drive: undefined,
      caption: 'water-card',
      alt: 'water-card',
      entry: false,
      desktop: false,
      wait: DEFAULT_WAIT_MS,
    })
  })

  it('photographs a phone unless the recipe asks for the wide layout', () => {
    // `desktop` is opt-in and strictly boolean, like `entry` beside it: a
    // recipe that means to photograph the wide layout says so, and a typo
    // ('desktop: 1280') falls back to the phone rather than quietly
    // photographing something else. Both are the same shape on purpose.
    expect(normaliseRecipe({}, 'x').desktop).toBe(false)
    expect(normaliseRecipe({ desktop: true }, 'x').desktop).toBe(true)
    expect(normaliseRecipe({ desktop: 1280 }, 'x').desktop).toBe(false)
  })

  it('lets alt default to the caption, which is the readable one', () => {
    const recipe = normaliseRecipe({ caption: 'The water card' }, 'water-card')
    expect(recipe.alt).toBe('The water card')
  })

  it('rejects a wrong shape as a sentence naming the recipe', () => {
    expect(() => normaliseRecipe({ default: 'tap the thing' }, 'x')).toThrow('recipe x')
    expect(() => normaliseRecipe({ caption: 42 }, 'x')).toThrow('caption')
    expect(() => normaliseRecipe({ wait: 'soon' }, 'x')).toThrow('wait')
  })
})

describe('the comment block', () => {
  const shot = (name: string, changed: boolean, extra = {}) => ({
    name,
    file: `${RECIPE_DIR}/${name}.mjs`,
    changed,
    caption: `The ${name}`,
    alt: `Alt for ${name}`,
    bytes: 1000,
    error: undefined,
    ...extra,
  })

  it('gives a desktop shot the width and the row a wide frame needs', () => {
    // Two 640px images do not fit the ~830px a comment gets, so a desktop
    // shot ends its row. The regression this catches is a desktop shot
    // pairing up with a phone one and being rendered at 320 - which looks
    // like a working shot in the markdown and like nothing in the comment.
    const block = renderComment(
      [shot('first-run-desktop', true, { desktop: true }), shot('legend', true)],
      {},
    )

    expect(block).toContain(
      `<img src="${PREVIEW_BASE_PLACEHOLDER}/__screenshot/first-run-desktop.png" width="${DESKTOP_DISPLAY_WIDTH}" alt="Alt for first-run-desktop">`,
    )
    expect(block).toContain(`width="${DISPLAY_WIDTH}" alt="Alt for legend"`)
    // Its own row: the desktop caption is not on a line with the phone one.
    const desktopRow = block
      .split('\n')
      .find((line) => line.includes('The first-run-desktop'))
    expect(desktopRow).toBe('| The first-run-desktop |')
    // And the footer stops claiming every frame is a phone.
    expect(block).toContain(`the wide ones at ${DESKTOP.width}x${DESKTOP.height}`)
  })

  it('keeps pairing phone shots when no desktop shot is among them', () => {
    const block = renderComment([shot('legend', true), shot('more', true)], {})
    expect(block).toContain('| The legend | The more |')
    expect(block).not.toContain('the wide ones at')
  })

  it('leads with the pull request’s own shots, standing after', () => {
    const block = renderComment([shot('legend', true), shot('first-run', false)], {})
    const own = block.indexOf('What this pull request changed')
    const standing = block.indexOf('The app, as every pull request shows it')
    expect(own).toBeGreaterThanOrEqual(0)
    expect(standing).toBeGreaterThan(own)
    expect(block.indexOf('legend.png')).toBeLessThan(block.indexOf('first-run.png'))
  })

  it('drops both headings when only the standing shots exist', () => {
    // The everyday case for a pipeline pull request - the block is then just
    // the two images, as it was before #998.
    const block = renderComment(
      [shot('first-run', false), shot('trail-screen', false)],
      {},
    )
    expect(block).not.toContain('####')
    expect(block).toContain('first-run.png')
    expect(block).toContain('trail-screen.png')
  })

  it('writes an <img> sized for a comment, from the placeholder base', () => {
    const block = renderComment([shot('legend', true)], {})
    expect(block).toContain(
      `<img src="${PREVIEW_BASE_PLACEHOLDER}/__screenshot/legend.png" width="${DISPLAY_WIDTH}" alt="Alt for legend">`,
    )
  })

  it('says so, in the comment, when a recipe could not drive', () => {
    const block = renderComment(
      [shot('first-run', false), shot('water-card', true, { error: 'no Water button' })],
      {},
    )
    expect(block).toContain('could not take `water-card`')
    expect(block).toContain('no Water button')
    expect(block).not.toContain('water-card.png')
  })

  it('carries the nudge only when the plan raised it', () => {
    const shots = [shot('first-run', false)]
    expect(renderComment(shots, { nudge: true })).toContain('no shot above is its own')
    expect(renderComment(shots, { nudge: false })).not.toContain(
      'no shot above is its own',
    )
  })

  it('survives a caption out to sabotage the table', () => {
    const hostile = shot('legend', true, {
      caption: 'Pipes | and\nnewlines',
      alt: 'Quotes " and <tags>',
    })
    const block = renderComment([hostile], {})
    expect(block).toContain('Pipes \\| and newlines')
    expect(block).toContain('alt="Quotes &quot; and &lt;tags&gt;"')
  })
})

describe('the flags', () => {
  it('reads what CI passes, and defaults the way a laptop wants', () => {
    const ci = parseRunnerArgs(['--dist', '--changed=/tmp/pr-files.txt'])
    expect(ci).toMatchObject({ dist: true, changedFile: '/tmp/pr-files.txt', asked: [] })
    const local = parseRunnerArgs([`${RECIPE_DIR}/legend.mjs`])
    expect(local).toMatchObject({ dist: false, asked: [`${RECIPE_DIR}/legend.mjs`] })
  })
})

describe('the escapes', () => {
  it('neutralise an attribute and a cell without touching plain text', () => {
    expect(escapeAttr('plain words')).toBe('plain words')
    expect(escapeAttr('a "b" & <c>')).toBe('a &quot;b&quot; &amp; &lt;c&gt;')
    expect(escapeCell('one | two')).toBe('one \\| two')
  })
})
