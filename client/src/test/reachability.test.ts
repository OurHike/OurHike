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

/** Modules built before their door, by the phase of #1373 that mounts each. */
const NOT_YET_MOUNTED: Readonly<Record<string, string>> = {
  'chrome/ClosureSheet.tsx':
    'the closure tap sheet (WIREFRAMES.md §7), built and never mounted; F12 mounts it on the closure tape',
  'chrome/SeriousWarningSheet.tsx':
    'the serious-warning detail sheet (WIREFRAMES.md §8), built and never mounted; F12 mounts it on the pin',
  'chrome/Notice.tsx': 'phase 0 of #1373; F1 and F2 mount it',
  'chrome/PinnedBar.tsx': 'phase 0 of #1373; F2 mounts it on every Today state',
  'chrome/StepRail.tsx': 'phase 0 of #1373; F3 mounts it over the three steps',
  'chrome/PoiRow.tsx': 'phase 0 of #1373; F5 mounts it in the details list',
  'chrome/DayRow.tsx': 'phase 0 of #1373; F5 mounts it, then F7 and F8',
}

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

  it('reaches every screen module from main.tsx, except the ones built ahead of their door', () => {
    const orphans = unreached.filter((module) => !(module in NOT_YET_MOUNTED))

    expect(
      orphans,
      'A screen module nothing imports is code shipped to nobody. Give it a ' +
        'door, or list it in NOT_YET_MOUNTED with the phase that will.',
    ).toEqual([])
  })

  it('keeps the not-yet-mounted ledger honest: every entry is still unreached', () => {
    const stale = Object.keys(NOT_YET_MOUNTED).filter((module) =>
      reached.has(join(SRC, module)),
    )

    expect(
      stale,
      'These are mounted now. Delete their rows so the ledger says what is ' +
        'still waiting on a door.',
    ).toEqual([])
    for (const module of Object.keys(NOT_YET_MOUNTED)) {
      expect(existsSync(join(SRC, module)), `${module} is listed but gone`).toBe(true)
    }
  })
})
