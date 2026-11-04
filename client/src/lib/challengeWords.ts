// The words a hiker reads for the act of marking a challenge item done
// (#1780, features/CHALLENGES.md; #1961, features/CHALLENGES_BLAZE_CARD.md).
//
// ONE PLACE, BECAUSE THE WORD HAS CHANGED ONCE ALREADY. The maintainer's
// revision of 2026-09-30: never "passport" - that is the ATC's own name for
// its stamp programme - and no digital stamp. The working term was "tag"
// until the blaze card: the maintainer's decision of 2026-11-03, confirmed by
// poll on 2026-11-04 from the Card and Tile frames edited both ways, is
// **earn** - "Earn it", "12 blazes earned", "Your blazes". Never "paint":
// painting blazes is maintainer work, and unauthorised blazing is a thing
// clubs fight. Every screen reads these rather than spelling the word, so
// choosing another one is an edit to this file and nothing else.
// client/src/lib/challengeWords.test.ts holds that no challenge screen spells
// "stamp", "passport" or "paint" itself.

export const CHALLENGE_WORDS = {
  /** The button on a place card and a list row. */
  act: 'Earn it',
  /** The same button once pressed, and a row's state. */
  done: 'Earned',
  /** The camp card's one-tap answer. */
  actAll: 'Earn all',
  /** The bare verb for running text: "earn them?", "until you earn one". */
  verb: 'earn',
  /** A lower-case noun for running text: "a blaze", "your blazes". */
  noun: 'blaze',
  nounPlural: 'blazes',
  /** The past tense for running text: "earned Jul 14". */
  past: 'earned',
  /** The one-tap undo every blaze has (the brief's "Second look"). */
  takeBack: 'Take it back',
  /** More's destination and the list screen's title. */
  yours: 'Your blazes',
} as const
