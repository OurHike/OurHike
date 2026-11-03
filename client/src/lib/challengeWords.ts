// The words a hiker reads for the act of marking a challenge place done
// (#1780, features/CHALLENGES.md).
//
// ONE PLACE, BECAUSE THE WORD IS NOT FINAL. The maintainer's revision of
// 2026-09-30: never "passport" - that is the ATC's own name for its stamp
// programme - and the working term is "tag", with the final word still the
// maintainer's to choose. Every screen reads these rather than spelling the
// word, so choosing a different one is an edit to this file and nothing else.
// client/src/lib/challengeWords.test.ts holds that no challenge screen spells
// "stamp" or "passport" itself.

export const CHALLENGE_WORDS = {
  /** The button on a place card and a list row. */
  act: 'Tag it',
  /** The same button once pressed, and a row's state. */
  done: 'Tagged',
  /** The camp card's one-tap answer. */
  actAll: 'Tag all',
  /** A lower-case noun for running text: "a tag", "your tags". */
  noun: 'tag',
  nounPlural: 'tags',
  /** The past tense for running text: "tagged Jul 14". */
  past: 'tagged',
  /** More's destination and the list screen's title. */
  yours: 'Your challenges',
} as const
