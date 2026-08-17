/**
 * The workflow's scope list, against what this suite actually reads.
 *
 * The client-suite half of the rule backend/tests/test_ci_scope.py and
 * pipeline/tests/test_ci_scope.py already enforce on themselves: a suite's
 * scope list includes every file its tests read. The reads are declared in
 * repoFile.ts rather than parsed out of test source - see its header for why
 * a source-scanner is the wrong mechanism here (#503).
 */
import { describe, it, expect } from 'vitest'
import { OUT_OF_TREE_READS, findRepoFile, readRepoFile } from './repoFile'

const CHANGED_PATHS_ACTION = '.github/actions/changed-paths'

/**
 * The `paths:` input handed to the changed-paths action.
 *
 * The word `paths` appears more than once in that file - the trigger comment
 * explains why the workflow deliberately has *no* `paths:` filter, which is
 * the opposite decision - so this anchors on the one step that uses the
 * changed-paths action and takes the input from its `with:` block. No YAML
 * parser in the client's dependencies; the guard-the-guard test below is
 * what keeps this from failing open if the file's shape changes.
 */
function scopePrefixes(): string[] {
  const lines = readRepoFile('.github/workflows/client-tests.yml').split('\n')
  const usesAt = lines.findIndex(
    (line) => line.includes(`uses:`) && line.includes(CHANGED_PATHS_ACTION),
  )
  expect(
    usesAt,
    `no step uses ${CHANGED_PATHS_ACTION} - if the scoping moved, fix this test rather than deleting it`,
  ).toBeGreaterThan(-1)

  for (let i = usesAt + 1; i < lines.length; i++) {
    const line = lines[i]
    // The step ends where the next step begins.
    if (/^\s*-\s/.test(line)) break
    const match = line.match(/^\s*paths:\s*(.+)$/)
    if (match) return match[1].trim().split(/\s+/)
  }
  throw new Error(`the ${CHANGED_PATHS_ACTION} step has no paths: input`)
}

describe('the CI scope list covers every out-of-tree read', () => {
  it('lists a prefix for each declared read', () => {
    const prefixes = scopePrefixes()
    const missing = OUT_OF_TREE_READS.filter(
      (read) => !prefixes.some((prefix) => read.startsWith(prefix)),
    )

    expect(
      missing,
      `client-tests.yml does not scope these files this suite reads, so a PR ` +
        `changing only them would skip the suite and the drift guard with it. ` +
        `The list today is: ${prefixes.join(' ')}`,
    ).toEqual([])
  })

  it('still scopes the suite itself and its own gate', () => {
    const prefixes = scopePrefixes()

    expect(prefixes).toContain('client/')
    expect(prefixes).toContain('.github/workflows/client-tests.yml')
    expect(prefixes).toContain(`${CHANGED_PATHS_ACTION}/`)
  })
})

describe('guards the guard', () => {
  it('is actually reading a scope list', () => {
    // A parse that returned nothing would pass everything above by finding
    // no files to be missing.
    expect(scopePrefixes().length).toBeGreaterThanOrEqual(5)
    expect(OUT_OF_TREE_READS.length).toBeGreaterThanOrEqual(3)
  })

  it('refuses an undeclared read, so the declaration list cannot rot', () => {
    // The type forbids this; the cast is how an undeclared read would arrive
    // in practice, so that is how it is exercised.
    expect(() => findRepoFile('pipeline/README.md' as never)).toThrow(/OUT_OF_TREE_READS/)
  })

  it('serves the declared reads it promises', () => {
    for (const read of OUT_OF_TREE_READS) {
      expect(readRepoFile(read).length, read).toBeGreaterThan(0)
    }
  })
})
