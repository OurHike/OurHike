import { describe, it, expect } from 'vitest'
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, relative, resolve } from 'node:path'

// One home per screen, as a check rather than a habit (#1373, the review's
// §05: "the app has one screen with no door at all").
//
// WHAT THIS PROVES. Starting from src/main.tsx and following every static
// `import … from './x'` and every deferred `import('./x')`, each screen
// module under src/screens, src/chrome and src/reporting is reached - some
// module the shell mounts, or something it mounts, imports it. A module
// nothing imports is code shipped to nobody: chrome/ClosureSheet.tsx and
// chrome/SeriousWarningSheet.tsx were exactly that when this test was
// written, each a finished safety sheet with no importer, which no other
// check could see because an unimported file typechecks, lints and tests
// fine.
//
// WHAT IT DOES NOT PROVE, and the sentence to keep true. Imported is weaker
// than rendered, and rendered is weaker than findable. screens/GpsTrace.tsx
// is the case that separates them: More.tsx imports it, so this test has
// always been green on it, and for a long time App.tsx passed nothing that
// rendered it (#1180 wired it; #1201 widened the gate). A door a hiker can
// find without knowing the screen exists is the review's standard, and that
// is read from the screens, not from this graph.
//
// THE LIST BELOW IS A LEDGER, NOT AN EXEMPTION. Each entry is a module built
// ahead of the screen that mounts it, with the phase that does. An entry is
// checked both ways: a module listed here must still be unreached, so the
// row is deleted the day the door opens rather than outliving it.

const SRC = resolve(process.cwd(), 'src')
const ROOT = join(SRC, 'main.tsx')
const SCREEN_DIRS = ['screens', 'chrome', 'reporting'] as const

const IMPORT_SPECIFIERS = [
  // import x from './y' · import { x } from './y' · export { x } from './y'
  /(?:import|export)\s[^'"]*?\sfrom\s+['"]([^'"]+)['"]/g,
  // import './y' (side-effect imports, which carry CSS and setup)
  /(?:^|\n)\s*import\s+['"]([^'"]+)['"]/g,
  // import('./y') - the deferred screens (screens/deferred.ts)
  /import\(\s*['"]([^'"]+)['"]\s*\)/g,
]

/** A relative specifier to the file it names, or null for anything that is
 *  not a TypeScript module of ours (a package, a stylesheet, an asset). */
function resolveModule(from: string, specifier: string): string | null {
  if (!specifier.startsWith('.')) return null
  const base = resolve(dirname(from), specifier)
  for (const candidate of [
    base,
    `${base}.ts`,
    `${base}.tsx`,
    join(base, 'index.ts'),
    join(base, 'index.tsx'),
  ]) {
    if (existsSync(candidate) && statSync(candidate).isFile()) {
      return /\.tsx?$/.test(candidate) ? candidate : null
    }
  }
  return null
}

function importsOf(file: string): string[] {
  const source = readFileSync(file, 'utf8')
  const found: string[] = []
  for (const pattern of IMPORT_SPECIFIERS) {
    for (const match of source.matchAll(pattern)) {
      const target = resolveModule(file, match[1])
      if (target !== null) found.push(target)
    }
  }
  return found
}

/** Every module the root reaches, by the import graph alone. */
function reachableFrom(root: string): Set<string> {
  const seen = new Set<string>()
  const queue = [root]
  while (queue.length > 0) {
    const file = queue.pop()!
    if (seen.has(file)) continue
    seen.add(file)
    queue.push(...importsOf(file))
  }
  return seen
}

function screenModules(): string[] {
  const modules: string[] = []
  for (const dir of SCREEN_DIRS) {
    for (const name of readdirSync(join(SRC, dir))) {
      if (name.endsWith('.tsx') && !name.endsWith('.test.tsx')) {
        modules.push(relative(SRC, join(SRC, dir, name)))
      }
    }
  }
  return modules.sort()
}

describe('every screen has a home', () => {
  const reached = reachableFrom(ROOT)
  const screens = screenModules()
  const unreached = screens.filter((module) => !reached.has(join(SRC, module)))

  it('walks a graph that actually reaches the shell', () => {
    // A parser that matched nothing would pass the assertion below by
    // reaching nothing and listing nothing - the fail-open shape #503 warns
    // about. So the graph is held to three things it must contain.
    expect(reached.has(join(SRC, 'App.tsx'))).toBe(true)
    expect(reached.has(join(SRC, 'screens/Today.tsx'))).toBe(true)
    // Through screens/deferred.ts's `import('./Plan')` - the dynamic form.
    expect(reached.has(join(SRC, 'screens/Plan.tsx'))).toBe(true)
  })

  it('reaches every screen module from main.tsx', () => {
    // A module built ahead of its door - F12's two sheets were, for a year
    // - belongs in a ledger here with the phase that will mount it, and the
    // ledger was retired the day it emptied: a screen with no door is a
    // defect this test names, not a state it keeps a shelf for.
    expect(
      unreached,
      'A screen module nothing imports is code shipped to nobody. Give it a door.',
    ).toEqual([])
  })
})

// The same graph, walked with `import()` NOT followed: what a browser parses
// before the first frame (features/LAUNCH_BUDGET.md §4.4).
//
// WHY A SECOND WALK. A static value import puts the whole exporting module in
// the importer's chunk - Rollup cannot take one constant and leave the file -
// so the shell reading a number out of a screen drags the screen into the
// eager closure. `App.tsx` did exactly that: `import { FIT_PADDING } from
// './map/MapView'`, one integer used twice, and with it 14,808 raw bytes of
// map code on a Today screen that mounts no map (measured 2026-09-15 through
// the build's sourcemap; the figures and the breakdown are in §4.4).
//
// scripts/check-build-output.mjs could not see it. That check finds MapLibre
// in the eager closure BY NAME - two markers out of the library's own source -
// and nothing here is MapLibre; its other arm is the byte budget, which said
// only that the total was 159 bytes too big, not what had moved. So this test
// is the named half: the map view has a door, `chrome/MapScreen.tsx`, and that
// door is behind `import()`.
//
// DELIBERATELY ONE MODULE, NOT A RULE ABOUT THE DIRECTORY. Plenty of
// `src/map/` is eager on purpose - the shell composes the map's overlays
// itself, and screens/deferred.ts says which. Widening this to "no map module
// is eager" would fail on that design rather than on a defect.
const EAGER_FORBIDDEN = ['map/MapView.tsx'] as const

function staticImportsOf(file: string): string[] {
  const source = readFileSync(file, 'utf8')
  const found: string[] = []
  // The first two patterns only; the third is `import('./y')`, which is the
  // boundary this walk exists to stop at.
  for (const pattern of IMPORT_SPECIFIERS.slice(0, 2)) {
    for (const match of source.matchAll(pattern)) {
      // `import type … from './y'` is erased by the compiler and reaches no
      // bundle, so it is not something the first frame parses. Six panels
      // import `MapScreenProps` this way and none of them carries the map
      // screen's code; counting them would have this walk report a defect
      // that does not exist. A statement mixing a type in with values
      // (`import { X, type Y }`) still counts, correctly - it emits.
      if (/^(?:import|export)\s+type\s/.test(match[0].trimStart())) continue
      const target = resolveModule(file, match[1])
      if (target !== null) found.push(target)
    }
  }
  return found
}

function eagerFrom(root: string): Set<string> {
  const seen = new Set<string>()
  const queue = [root]
  while (queue.length > 0) {
    const file = queue.pop()!
    if (seen.has(file)) continue
    seen.add(file)
    queue.push(...staticImportsOf(file))
  }
  return seen
}

describe('what the first frame parses', () => {
  const eager = eagerFrom(ROOT)

  it('walks a graph that stops at import()', () => {
    // The same fail-open guard the walk above carries, plus the one thing
    // that separates this walk from that one: the shell is in it, and a
    // deferred screen is not.
    expect(eager.has(join(SRC, 'App.tsx'))).toBe(true)
    expect(eager.has(join(SRC, 'screens/Today.tsx'))).toBe(true)
    expect(eager.has(join(SRC, 'screens/Plan.tsx'))).toBe(false)
  })

  it('does not reach the map view', () => {
    const eagerly = EAGER_FORBIDDEN.filter((module) => eager.has(join(SRC, module)))
    expect(
      eagerly,
      'Something the shell imports statically reaches the map view, so every byte ' +
        'of it is parsed before a Today screen that mounts no map. A constant it ' +
        'exports belongs in a module of its own - map/fitPadding.ts is the one this ' +
        'test was written for. See features/LAUNCH_BUDGET.md §4.4.',
    ).toEqual([])
  })

  it('still reaches it through its door', () => {
    // The other half of the claim, so a MapView that nothing rendered at all
    // could not pass the assertion above by being unreachable.
    const reachedAnyhow = reachableFrom(ROOT)
    expect(reachedAnyhow.has(join(SRC, 'map/MapView.tsx'))).toBe(true)
  })
})
