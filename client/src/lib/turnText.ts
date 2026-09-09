// What a turn is called out loud (#1041, frames `D9` and `D10`).
//
// Separated from lib/dayHikeTurns.ts, which is geometry, for the reason
// lib/lineDetail.ts gives about the line sheet: every sentence a hiker reads
// at a junction is decided here, so the decisions can be tested without
// rendering anything.
//
// A HIKER CHECKS THE APP AGAINST THE BLAZE, NOT THE OTHER WAY ROUND, and
// that is what these sentences are shaped for. Frame `D10` names all three
// arms of a junction and says what each one ISN'T, because somebody standing
// at a fork is holding two facts - a painted mark on a tree and a phone - and
// the useful screen is the one that lets them agree or disagree. A card that
// named only the arm to take would be asking to be obeyed.
//
// NO PAINTED SWATCH, and this is a maintainer's decision rather than an
// omission. #782's blaze rows were removed from the legend on the request
// "the legend doesn't need the color of the blaze included... it's too much",
// and chrome/Legend.tsx records the reasoning that survives here: a blaze
// name IS a colour word, so "blue blaze" already carries the chip's whole
// content, and the map is still painting every line in its blaze. The
// storyboard draws a swatch beside each arm; these cards say the word.

import { blazeLabel } from './blaze'
import type { TurnArm, TurnSide } from './dayHikeTurns'

/**
 * What a trail with no published name is called.
 *
 * Not "Unknown trail", which reads as a data fault, and not omitted, which
 * would leave a hiker at a four-way junction reading three lines about two
 * arms. FEATURES.md's rule is that absent means unknown; the sentence says so
 * in words and keeps the arm on the card, because the arm is really there.
 */
const UNNAMED = 'an unnamed trail'

function armName(arm: TurnArm): string {
  return arm.name ?? UNNAMED
}

/** How an arm's direction is written when it leads a sentence. */
const LEADING: Record<TurnSide, string> = {
  left: 'Turn left',
  right: 'Turn right',
  straight: 'Straight on',
  back: 'Turn back',
}

/** And when it sits mid-sentence, describing where an arm goes. */
const DESCRIBING: Record<TurnSide, string> = {
  left: 'To the left',
  right: 'To the right',
  straight: 'Straight on',
  back: 'Behind you',
}

/**
 * The instruction itself: "Turn left onto Seven Hills Trail".
 *
 * With no side - an edge published before `trail_graph_geometry.json`, see
 * {@link TurnArm.side} - it becomes "Onto Seven Hills Trail", which is still
 * a true and useful thing to read at a junction where one arm is blue and the
 * rest are not. Inventing a side from the chord between two junctions would
 * send somebody the wrong way around a switchback.
 */
export function turnHeading(onto: TurnArm): string {
  if (onto.side === null) return `Onto ${armName(onto)}`
  return `${LEADING[onto.side]} onto ${armName(onto)}`
}

/** The turn as one short line for the card that is still 0.4 mi away:
 *  "left onto Seven Hills Trail". */
export function turnSummary(onto: TurnArm): string {
  if (onto.side === null) return `onto ${armName(onto)}`
  return `${LEADING[onto.side].toLowerCase()} onto ${armName(onto)}`
}

/** The blaze to look for, as the sheet that names a tapped line writes it. */
export function armBlaze(arm: TurnArm): string {
  return blazeLabel(arm.blaze_color)
}

/**
 * One of the arms that is NOT the route: "To the right is Pine Meadow Trail,
 * blue blaze — not your route."
 *
 * The trailing clause is the load-bearing half. A hiker reads the arms to
 * rule them out, and a line that merely names a trail leaves them deciding
 * which of the three the app meant.
 */
export function otherArmLine(arm: TurnArm): string {
  const where = arm.side === null ? 'Also here' : DESCRIBING[arm.side]
  return `${where} is ${armName(arm)}, ${armBlaze(arm).toLowerCase()} — not your route`
}

/** The arm the hiker walked in on. Same shape, different clause, because
 *  "the way you came" is the one arm they can rule out without looking. */
export function cameFromLine(arm: TurnArm): string {
  const where = arm.side === null ? 'Also here' : DESCRIBING[arm.side]
  return `${where} is ${armName(arm)}, ${armBlaze(arm).toLowerCase()} — the way you came`
}

/**
 * The check to make after taking the turn.
 *
 * Frame `D10` writes "The next blaze is about 80 ft along, on the left", and
 * that sentence is dropped rather than approximated: nothing in this
 * repository knows where a blaze is painted - not the junction graph, not any
 * published source - so a distance there would be a measurement nobody made,
 * on the screen a hiker uses to decide they are on the right trail.
 *
 * What survives is the rule of thumb, which reads as one. It turns a wrong
 * turn into a short mistake instead of a long one without claiming to know
 * anything about this particular tree.
 */
export function blazeCheckLine(onto: TurnArm): string {
  const colour = onto.blaze_color
  if (
    colour === null ||
    colour === 'Unknown' ||
    colour === 'None' ||
    colour === 'Other'
  ) {
    return 'Check the blazes as you go. If the marks change colour, you have taken a different trail.'
  }
  return `Check the blazes as you go. If you don't see ${colour.toLowerCase()} within a few minutes, you took a different trail.`
}
