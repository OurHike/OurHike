import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { CHALLENGE_WORDS } from './challengeWords'

// The maintainer's revision of 2026-09-30: never "passport" - the ATC's own
// word for its stamp programme - and no digital stamp. The working word is
// "tag", in lib/challengeWords.ts, so choosing the final word is an edit to
// one file. This holds the challenge surfaces to that: none of them spells
// either word in its own code. (A club's ITEM may - the ATC's 2025 list says
// "Collect A.T. passport stamps along the Trail", about the ATC's real
// programme - which is data, not the app's voice, so only code is scanned.)

const SRC = resolve(process.cwd(), 'src')
const SURFACES = [
  ...['screens', 'chrome', 'org/screens'].flatMap((dir) =>
    readdirSync(join(SRC, dir))
      .filter(
        (name) =>
          /challenge/i.test(name) && /\.tsx?$/.test(name) && !/\.test\./.test(name),
      )
      .map((name) => join(dir, name)),
  ),
  'lib/challengeText.ts',
  'lib/challenges.ts',
  'lib/challengeProgress.ts',
]

/** Code with its comments blanked, so a comment explaining the rule is not
 *  mistaken for a breach of it. */
function code(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
}

describe('the words a challenge surface uses', () => {
  it('finds the surfaces it is meant to scan', () => {
    expect(SURFACES).toEqual(
      expect.arrayContaining([
        'screens/ChallengeDetail.tsx',
        'chrome/ChallengeParts.tsx',
        'chrome/PoiChallenges.tsx',
      ]),
    )
  })

  it.each(SURFACES)('%s never says "stamp" or "passport" in its own voice', (path) => {
    expect(code(readFileSync(join(SRC, path), 'utf8'))).not.toMatch(/stamp|passport/i)
  })

  it('names the act one way, in one place', () => {
    expect(CHALLENGE_WORDS.act).toBe('Tag it')
    expect(CHALLENGE_WORDS.done).toBe('Tagged')
  })
})
