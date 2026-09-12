import { describe, it, expect } from 'vitest'
import { existsSync, readdirSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'
import { FLOW_COVERAGE } from './flowCoverage'

// One flow-coverage answer per screen, as a check rather than a habit
// (#1386; features/FLOW_TESTING.md).
//
// WHAT THIS PROVES. Every screen module under src/screens, src/chrome and
// src/reporting - the same three directories reachability.test.ts walks, on
// purpose - has an entry in FLOW_COVERAGE saying whether the flow suite
// drives it, means to, or deliberately never will. It proves the ledger is
// complete in both directions: a screen with no entry fails here, and an
// entry naming a module that no longer exists fails here too, so a deleted
// screen cannot leave a row behind claiming coverage of nothing.
//
// WHAT IT DOES NOT PROVE, and the sentence to keep true: that any of it is
// TESTED. `planned` is an honest majority right now, and this test is
// content with it. What it refuses is the third state - a screen nobody has
// thought about, which is how a flow ships with nothing watching it and
// nobody able to say that was a decision. Being listed as `planned` is a
// decision; being absent is not.
//
// WHY THE LEDGER IS NOT DERIVED. Everything else in this repository prefers
// deriving a list to keeping one (CONTRIBUTING.md's one home per item), and
// the derivation here would be "which e2e spec touches which screen", which
// no static read can answer: a spec reaches a screen through a role query on
// a rendered tree, not through an import. So the entry is written by hand
// and this test holds the hand-written half to the derived half - the same
// trade repoFile.ts's OUT_OF_TREE_READS makes, and for the same reason.

const SRC = resolve(process.cwd(), 'src')
const CLIENT = resolve(process.cwd())
const SCREEN_DIRS = ['screens', 'chrome', 'reporting'] as const

function screenModules(): string[] {
  const modules: string[] = []
  for (const dir of SCREEN_DIRS) {
    for (const name of readdirSync(join(SRC, dir))) {
      if (name.endsWith('.tsx') && !name.endsWith('.test.tsx')) {
        modules.push(
          relative(SRC, join(SRC, dir, name))
            .split('\\')
            .join('/'),
        )
      }
    }
  }
  return modules.sort()
}

describe('every screen has a flow-coverage answer', () => {
  const modules = screenModules()
  const listed = Object.keys(FLOW_COVERAGE)

  it('walks a tree that actually holds screens', () => {
    // A reader that matched nothing would pass every assertion below by
    // comparing two empty sets - the fail-open shape #503 warns about, and
    // the one reachability.test.ts guards itself against the same way.
    expect(modules.length).toBeGreaterThan(50)
    expect(modules).toContain('screens/Today.tsx')
    expect(modules).toContain('chrome/BailSheet.tsx')
  })

  it('has an entry for every screen module', () => {
    const missing = modules.filter((module) => FLOW_COVERAGE[module] === undefined)
    expect(
      missing,
      'A screen with no flow-coverage entry is a flow nobody has said how to ' +
        'drive. Add it to src/test/flowCoverage.ts - `planned` is a real ' +
        'answer, absence is not (features/FLOW_TESTING.md).',
    ).toEqual([])
  })

  it('lists no screen that has gone', () => {
    const stale = listed.filter((module) => !modules.includes(module))
    expect(
      stale,
      'A flow-coverage entry naming a module that no longer exists claims ' +
        'coverage of nothing. Delete the row with the screen.',
    ).toEqual([])
  })

  it('names a spec file that exists for everything claimed covered', () => {
    const broken = listed.filter((module) => {
      const entry = FLOW_COVERAGE[module]
      return entry.flow.status === 'covered' && !existsSync(join(CLIENT, entry.flow.spec))
    })
    expect(
      broken,
      'A `covered` entry points at a spec that is not there, so the claim is ' +
        'unbacked. Point it at the spec that drives the screen, or drop the ' +
        'status back to `planned`.',
    ).toEqual([])
  })

  it('gives a reason for every deliberate exemption', () => {
    const unreasoned = listed.filter((module) => {
      const entry = FLOW_COVERAGE[module]
      return entry.flow.status === 'unit-only' && entry.flow.why.trim().length === 0
    })
    expect(
      unreasoned,
      '`unit-only` is a decision somebody may disagree with, so it carries ' +
        'the sentence that lets them.',
    ).toEqual([])
  })
})
