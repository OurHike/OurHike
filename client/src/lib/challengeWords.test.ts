import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { CHALLENGE_WORDS } from './challengeWords'

// The maintainer's revision of 2026-09-30: never "passport" - the ATC's own
// word for its stamp programme - and no digital stamp. The card of tiles
// (2026-11-03, poll 2026-11-04) made the verb "earn" and ruled out "paint",
// because painting blazes is maintainer work; the same day's second poll
// made what is earned "trail karma" and retired "blaze" from the app's own
// words, because a blaze is official trail marking. The words are in
// lib/challengeWords.ts, so choosing another is an edit to one file. This
// holds the challenge surfaces to that: none of them spells any of the three
// in its own code. (A club's ITEM may - the ATC's 2025 list says "Collect
// A.T. passport stamps along the Trail", about the ATC's real programme -
// which is data, not the app's voice, so only code is scanned.)

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

  it.each(SURFACES)(
    '%s never says "stamp", "passport" or "paint" in its own voice',
    (path) => {
      expect(code(readFileSync(join(SRC, path), 'utf8'))).not.toMatch(
        /stamp|passport|paint/i,
      )
    },
  )

  it('names the act "earn", in one place', () => {
    expect(CHALLENGE_WORDS.act).toBe('Earn it')
    expect(CHALLENGE_WORDS.done).toBe('Earned')
    expect(CHALLENGE_WORDS.verb).toBe('earn')
    expect(CHALLENGE_WORDS.noun).toBe('trail karma')
    expect(CHALLENGE_WORDS.some).toBe('some karma')
    expect(CHALLENGE_WORDS.yours).toBe('Your trail karma')
  })

  it('never calls what a hiker earns a blaze - blazes are official trail marking', () => {
    // The maintainer, 2026-11-04: "blazes are official, lets not mess with
    // them". The ATC's own item text may still say "white blaze" (it means
    // the paint); these are OurHike's words, and none of them may.
    for (const word of Object.values(CHALLENGE_WORDS)) {
      expect(word).not.toMatch(/blaze/i)
    }
  })

  it('never names the paint or a leaderboard in any of its words', () => {
    for (const word of Object.values(CHALLENGE_WORDS)) {
      expect(word).not.toMatch(/paint|stamp|passport/i)
      expect(word).not.toMatch(/other hikers|behind|streak|rank|leaderboard/i)
    }
  })
})
