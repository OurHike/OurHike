// The census gets a census (#1454).
//
// `scripts/memo-census.mjs` answers a question client/README.md publishes as a
// measurement, so a defect in it is a wrong number in a document rather than a
// red test — the failure mode this repository's evidence standard exists to
// prevent. It classifies each memoised value four ways and three of those were
// added only because hand-checking the first run found them; nothing but a
// test keeps them from rotting back out.
//
// Each case runs the REAL script, the way `checkBuildOutput.test.ts` does,
// against a synthetic two-file tree (TESTING.md's synthetic-fixture rule)
// rather than against `App.tsx` — a test pinned to the shell's real numbers
// would go red every time somebody added a handler, which is the flaky gate
// CLAUDE.md warns about. What is asserted is the CLASSIFICATION, which is the
// part that has to stay true.

import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { execFileSync } from 'node:child_process'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

const SCRIPT = resolve(process.cwd(), 'scripts/memo-census.mjs')

/**
 * A shell holding one of each kind, and a child that depends on one prop.
 *
 * The four kinds are the whole point of the file under test:
 *   `local`          - its own name in a dependency array in this file
 *   `acrossBoundary` - passed as a prop some component keys an effect on
 *   `handedToHook`   - passed to a custom hook, which may key on it
 *   none of those    - the candidate set
 */
const SHELL = `
import { useCallback, useMemo, useEffect } from 'react'
import { Child } from './child'
import { useThing } from './thing'

export function Shell() {
  const localOne = useCallback(() => {}, [])
  useEffect(() => { localOne() }, [localOne])

  const overBoundary = useCallback(() => {}, [])
  const handedOver = useCallback(() => {}, [])
  const nobodyCares = useCallback(() => {}, [])

  // A generic call, which \`grep -c 'useMemo('\` misses and the AST does not.
  const generic = useMemo<number[]>(() => [], [])
  useEffect(() => {}, [generic])

  // Destructured: either name appearing anywhere makes the memo load-bearing.
  const { first, second } = useMemo(() => ({ first: 1, second: 2 }), [])
  useEffect(() => {}, [second])

  useThing(handedOver)

  return <Child onPoke={overBoundary} unwatched={nobodyCares} first={first} />
}
`

/** The child keys an effect on one prop and not the other. */
const CHILD = `
import { useEffect } from 'react'

export function Child({ onPoke, unwatched, first }) {
  useEffect(() => { onPoke() }, [onPoke])
  return null
}
`

let directory: string

function run(args: string[]): string {
  return execFileSync('node', [SCRIPT, ...args], { encoding: 'utf8' })
}

function classify(): Record<string, string> {
  const parsed = JSON.parse(run([join(directory, 'shell.tsx'), '--json'])) as {
    memos: {
      names: string[]
      local: boolean
      acrossBoundary: boolean
      handedToHook: boolean
    }[]
  }
  const byName: Record<string, string> = {}
  for (const memo of parsed.memos) {
    const kind = memo.local
      ? 'local'
      : memo.acrossBoundary
        ? 'acrossBoundary'
        : memo.handedToHook
          ? 'handedToHook'
          : 'none'
    for (const name of memo.names) byName[name] = kind
  }
  return byName
}

beforeEach(() => {
  directory = mkdtempSync(join(tmpdir(), 'memo-census-'))
  mkdirSync(directory, { recursive: true })
  writeFileSync(join(directory, 'shell.tsx'), SHELL)
  writeFileSync(join(directory, 'child.tsx'), CHILD)
})

afterEach(() => rmSync(directory, { recursive: true, force: true }))

describe('the memoisation census', () => {
  it('counts a value its own file depends on as load-bearing here', () => {
    expect(classify().localOne).toBe('local')
  })

  it('follows a callback across the prop boundary to a child that keys on it', () => {
    // The case that would have made the published number wrong: `overBoundary`
    // is in no dependency array in its own file, and `Child` re-runs an effect
    // whenever its identity changes.
    expect(classify().overBoundary).toBe('acrossBoundary')
  })

  it('treats a value handed to a custom hook as possibly depended on', () => {
    // Deliberately an over-approximation - the script does not open the hook.
    // Erring this way cannot manufacture a deletion; erring the other way can.
    expect(classify().handedOver).toBe('handedToHook')
  })

  it('leaves a callback nothing depends on in the candidate set', () => {
    // `nobodyCares` IS passed to the child, as a prop the child never keys on.
    // Being passed somewhere is not the same as being depended on, and this is
    // the assertion that keeps those apart.
    expect(classify().nobodyCares).toBe('none')
  })

  it('counts a generic useMemo, which the grep in the README does not', () => {
    // `useMemo<number[]>(...)` has no `useMemo(` in its text at all. Finding
    // five of these is what showed the README's own figure was five short.
    expect(classify().generic).toBe('local')
  })

  it('counts a destructured memo once, under every name it binds', () => {
    // Only `second` appears in an array; `first` is passed to a child that
    // does not key on it. One memo, so both names carry its verdict.
    const kinds = classify()
    expect(kinds.first).toBe('local')
    expect(kinds.second).toBe('local')
  })

  it('goes red when the parse and the text disagree', () => {
    // The guard that makes every number above trustworthy. A parser reading
    // part of a file yields a confident wrong answer, so prove the alarm
    // sounds rather than assuming it would - confirm-red-once, applied to the
    // thing that certifies the measurement.
    //
    // JSX TEXT carrying the token is the shape that trips it, and it is a real
    // one rather than a contrivance: a component documenting its own hooks on
    // screen puts `useCallback(` in the text where the stripper cannot reach
    // it - it strips comments and string literals, and JSX text is neither.
    writeFileSync(
      join(directory, 'shell.tsx'),
      SHELL.replace('return <Child', 'return <p>useCallback( in prose</p> ?? <Child'),
    )

    let exitCode = 0
    let output = ''
    try {
      run([join(directory, 'shell.tsx'), '--check'])
    } catch (error) {
      const failure = error as { status: number; stderr: string }
      exitCode = failure.status
      output = failure.stderr
    }
    expect(exitCode).toBe(1)
    expect(output).toContain('the parse disagrees with the text')
  })

  it('agrees when the token appears only inside strings, which it must strip', () => {
    // The negative control for the alarm above: three occurrences that are not
    // calls. Without this, the previous test passes just as well against a
    // guard that fires on everything, which would be a guard worth deleting.
    writeFileSync(
      join(directory, 'shell.tsx'),
      `${SHELL}\nexport const decoy = 'useCallback(' + "useCallback(" + \`useCallback(\`\n`,
    )
    expect(run([join(directory, 'shell.tsx'), '--check'])).toContain('parse agrees')
  })

  it('does not see a hook imported under another name, and says so here', () => {
    // A KNOWN BLIND SPOT, written as a passing test rather than left for
    // somebody to discover in a wrong number. `import { useCallback as uc }`
    // makes the call `uc(...)`, which the AST reads as a call to `uc` and the
    // text side cannot see either - so both count zero, they AGREE, and the
    // memo is silently absent from the census.
    //
    // Nothing in client/src does this today, which is why the script does not
    // resolve import aliases. If that changes, this test is where the
    // assumption is recorded, and it will still pass while quietly being wrong
    // - so it asserts the blind spot explicitly instead.
    writeFileSync(
      join(directory, 'shell.tsx'),
      `
import { useCallback as uc } from 'react'
export function Aliased() {
  const hidden = uc(() => {}, [])
  return hidden
}
`,
    )
    const parsed = JSON.parse(run([join(directory, 'shell.tsx'), '--json'])) as {
      memos: unknown[]
    }
    expect(parsed.memos).toHaveLength(0)
    expect(run([join(directory, 'shell.tsx'), '--check'])).toContain('parse agrees')
  })
})
