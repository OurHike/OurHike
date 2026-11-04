// The words a hiker reads for the act of marking a challenge item done
// (#1780, features/CHALLENGES.md; #1961, features/CHALLENGES_BLAZE_CARD.md).
//
// ONE PLACE, BECAUSE THE WORD HAS CHANGED ONCE ALREADY. The maintainer's
// revision of 2026-09-30: never "passport" - that is the ATC's own name for
// its stamp programme - and no digital stamp. The working term was "tag"
// until the blaze card: the maintainer's decision of 2026-11-03, confirmed by
// poll on 2026-11-04 from the Card and Tile frames edited both ways, is
// **earn** - "Earn it". Never "paint": painting blazes is maintainer work, and
// unauthorised blazing is a thing clubs fight.
//
// WHAT IS EARNED IS "TRAIL KARMA", AND NEVER A BLAZE. The brief called each
// earned item a blaze ("12 blazes earned", "Your blazes"); the maintainer
// retired that on 2026-11-04 - "blazes are official, lets not mess with them"
// - and chose **trail karma** by poll the same day, from a picture of four
// hiker-trash words in the four places this noun appears (the Challenges
// title, the season strip, the tile sheet, the share poster). Trail karma is
// what trail magic runs on, and the Protect items are exactly that. It is a
// MASS noun: never pluralised, and it takes a singular verb - "4 trail karma",
// "trail karma counts from then", "earn some karma".
//
// Every screen reads these rather than spelling the word, so choosing another
// one is an edit to this file and to the few sentences whose grammar depends
// on it, and nothing else.
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
  /** What earning gives, lower case, for running text and after a count:
   *  "4 trail karma", "trail karma you earn appears here". A mass noun - see
   *  the header - so there is no plural to reach for. */
  noun: 'trail karma',
  /** The noun after the verb: "Earn some karma", "until you earn some karma". */
  some: 'some karma',
  /** The past tense for running text: "earned Jul 14". */
  past: 'earned',
  /** The one-tap undo every earned item has (the brief's "Second look"). */
  takeBack: 'Take it back',
  /** More's destination and the list screen's title. */
  yours: 'Your trail karma',
} as const
