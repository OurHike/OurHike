/**
 * Every read a client test makes outside client/, declared before it happens.
 *
 * TESTING.md's rule is that a suite's scope list includes every file its
 * tests read - #317 is what happens without it: this suite read
 * pipeline/reference/gain_vectors.json and site/index.html while scoped to
 * client/ alone, so a PR editing the shared elevation-gain vectors ran only
 * the Python half of a two-language drift guard.
 *
 * The Python suites enforce the rule by parsing their own workflow and
 * comparing it against the CLIENT_FILES_READ their contract tests declare.
 * Finding a Vitest suite's out-of-tree reads by parsing test source would be
 * a regex over dissimilar call shapes - the kind of parser that fails open
 * (#503). So this goes the other way: the read itself goes through
 * `readRepoFile`, which only serves paths declared in OUT_OF_TREE_READS, and
 * ciScope.test.ts asserts that list against the workflow's scope list. The
 * declaration is a precondition of doing the read at all, not something a
 * scanner infers afterwards.
 */
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

export const OUT_OF_TREE_READS = [
  'pipeline/reference/gain_vectors.json',
  // The list-layout contract and the step-with-a-link case moved with the
  // content when the one-page site became the built site (#116): the rules
  // live in the stylesheet, the markup in the install page.
  'site/src/styles/site.css',
  'site/src/pages/get-the-app.astro',
  // ciScope.test.ts reads the workflow to check the entries above are
  // scoped - which makes the workflow itself an out-of-tree read, held to
  // the same rule it enforces.
  '.github/workflows/client-tests.yml',
] as const

export type OutOfTreeRead = (typeof OUT_OF_TREE_READS)[number]

/**
 * Resolve a declared repo-relative path by walking up from the working
 * directory. Walked rather than resolved from import.meta.url: Vitest
 * transforms this module, so its import.meta.url is not a file: URL and
 * fileURLToPath throws on it. Walking also survives the suite being run from
 * the repo root instead of client/.
 */
export function findRepoFile(relative: OutOfTreeRead): string {
  if (!(OUT_OF_TREE_READS as readonly string[]).includes(relative)) {
    // The parameter type already forbids this, but a cast can smuggle a path
    // past the compiler, and an undeclared read is exactly the hole this
    // module exists to close - so the check is repeated where it cannot be
    // cast away.
    throw new Error(
      `${relative} is not declared in OUT_OF_TREE_READS. Add it there so ` +
        `ciScope.test.ts can hold the CI scope list to it - that is what ` +
        `keeps the suite running on PRs that only touch that file (#503).`,
    )
  }
  let dir = process.cwd()
  for (;;) {
    const candidate = resolve(dir, relative)
    if (existsSync(candidate)) return candidate
    const parent = dirname(dir)
    if (parent === dir) throw new Error(`${relative} not found above ${process.cwd()}`)
    dir = parent
  }
}

export function readRepoFile(relative: OutOfTreeRead): string {
  return readFileSync(findRepoFile(relative), 'utf8')
}
