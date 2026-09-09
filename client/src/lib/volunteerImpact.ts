// "What you've put back" - the impact panel wireframe 2e frame 2 asked for and
// #761 did not ship (#969, features/VOLUNTEERING.md §5).
//
// A LOGBOOK, NOT A SCOREBOARD, and this module is where that is enforced
// rather than intended. VOLUNTEERING.md §5 reconciles this panel with the four
// separate places this repository has written down "no per-hiker contribution
// counts shown anywhere": what those prohibit is comparison and pressure, not
// memory. Every one of the things they name - leaderboards, streaks, public
// profiles, ranking, messaging about what you have not done - works by putting
// a second person in the frame, or a future self you are failing. A private
// record of what you did is a logbook, and maintainers kept those long before
// there was an app to keep them in.
//
// The four rules, and what each one costs here:
//
//  1. NEVER COMPARATIVE. Nothing in this file takes another hiker's numbers as
//     an input, and there is nowhere for one to arrive: `impactTiles` sees one
//     person's own records and nothing else.
//  2. NEVER A LACK-STATE. A tile whose count is zero is not rendered, which is
//     the rule taken literally: "it shows what happened, it never shows what
//     did not". `Workdays 0` is a sentence about a hiker's June, and this panel
//     has no business writing one.
//  3. PRIVATE BY DEFAULT. Nothing here is shared, published or uploaded.
//     Sharing is the CSV export chrome/VolunteerHours.tsx already offers - a
//     hiker handing someone a file.
//  4. COUNTS REAL THINGS, NEVER POINTS. Two counts, each of something that
//     happened, and deliberately NO total across them: "the moment there is one
//     number there is a thing to maximise, and the feature has become the one
//     it promised not to be".
//
// WHAT IS NOT COUNTED, AND WHY IT IS SAID OUT LOUD. Frame 2 draws four tiles.
// Two of them - field notes filed, water reports - have no source at all: a
// note is enqueued into `ourhike:outbox` and removed the moment it sends, so
// the phone forgets what it filed (#967). Rendering those tiles as zero would
// break rule 2 AND be false; rendering nothing at all would leave a hiker who
// files notes weekly wondering why none of them are here. So the panel says
// which two are missing and whose fault it is - the app's, not theirs.
//
// AND "THE ONE THAT MATTERED" IS CUT, not deferred and not estimated. The
// wireframe's own annotation sets the standard: it "needs a real downstream
// count. If that can't be measured honestly, it's cut rather than estimated."
// "Your note about the dry spring is why 40-odd people carried an extra litre"
// is a claim about other people's behaviour; nothing in this app measures it,
// and #596 is the only thing that might. Estimated, it would be the most
// flattering sentence in the app and the least true.

import { hoursTotals, type VolunteerHoursSummary } from './volunteerHours'

export interface ImpactTile {
  /** What the number is, in the hiker's own terms. */
  label: string
  value: string
  /**
   * A qualifier that travels WITH the number rather than as a second line.
   *
   * The #761 decision it inherits: claimed hours count until a club disputes
   * them, and the state always travels where the number does. A total that
   * shed its "not yet confirmed" on the way to a summary tile would be the
   * panel making a firmer claim than the record under it.
   */
  caveat?: string
}

/** The panel's own heading and the promise under it, from frame 2. */
export const IMPACT_TITLE = "What you've put back"
export const IMPACT_SUBTITLE = 'Kept for you, seen by no one.'

/**
 * The two tiles frame 2 asks for that have no source, named rather than drawn
 * as zeroes (#967).
 *
 * One sentence, and it is about the app rather than the hiker - which is what
 * keeps it out of rule 2. "You have filed no notes" is a lack-state; "this app
 * does not keep a record of what you filed" is a confession.
 */
export const IMPACT_NOT_COUNTED =
  'Field notes and water reports are not counted here. The phone forgets what it filed the moment it sends it, so there is nothing to count yet — that is this app’s gap, not a gap in what you did.'

function plural(count: number, one: string, many: string): string {
  return count === 1 ? one : many
}

/**
 * What a hiker has put back, from their own hours records alone.
 *
 * Empty for a hiker with nothing logged, and the panel does not render at all
 * then - rule 2 again, one level up. An empty panel headed "what you've put
 * back" is the most pointed lack-state this screen could draw.
 *
 * WORKDAYS IS DISTINCT CALENDAR DAYS, NOT WORK PROJECTS, and that is a decision
 * with a source. `VolunteerHoursSummary` carries a `work_project_id`, so
 * "workdays attended" could be read as the organised ones a club scheduled -
 * but VOLUNTEERING.md §4 says plainly that "most maintenance is somebody going
 * out on a Tuesday because a blowdown needs clearing, and a design that only
 * counts organised workdays would miss the majority of the work it is trying to
 * honour". Counting scheduled workdays would make this tile read zero for
 * exactly the people it is most meant for.
 *
 * Two records on one Saturday are one day of showing up, which is
 * `hoursTotals`' own rule - reused rather than recounted here, so the two
 * surfaces cannot come to disagree about what a day is.
 */
export function impactTiles(
  records: readonly VolunteerHoursSummary[] | null,
): ImpactTile[] {
  if (records === null || records.length === 0) return []

  const totals = hoursTotals(records)
  const tiles: ImpactTile[] = []

  if (totals.daysWorked > 0) {
    tiles.push({
      label: plural(totals.daysWorked, 'Day out', 'Days out'),
      value: totals.daysWorked.toLocaleString('en-US'),
    })
  }

  if (totals.countedHours > 0) {
    const hours = totals.countedHours.toLocaleString('en-US', {
      maximumFractionDigits: 1,
    })
    tiles.push({
      label: 'Hours you wrote down',
      value: hours,
      ...(totals.unconfirmedHours > 0
        ? {
            caveat: `${totals.unconfirmedHours.toLocaleString('en-US', {
              maximumFractionDigits: 1,
            })} not yet confirmed by a club`,
          }
        : {}),
    })
  }

  return tiles
}
