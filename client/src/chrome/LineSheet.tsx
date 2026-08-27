// The line-detail sheet (#134): what a tapped trail line is, and - for a
// spur - the decision it exists to help with: is it worth walking down
// there, and how far back up?
//
// WIREFRAMES.md §3 specifies the sheet ("tapping any line opens a sheet
// naming the blaze and its source, and says plainly when it's unknown");
// features/SPUR_TRAILS.md §3 specifies the spur section. Every sentence
// here is decided in lib/lineDetail.ts, where it is testable without a
// canvas - this component only lays the lines out, on the same classes
// AtcUpdateSheet already renders with so the two sheets read as one family.
//
// Lines that are null are OMITTED, never placeholdered. A spur with no
// resolved destination shows no destination line at all - not "Unknown
// destination", which reads as a data error rather than the ordinary
// situation it is for ~12% of spurs (the same restraint describeStewards
// applies to an unassigned trail section).

import type { LineDetail } from '../lib/lineDetail'

export interface LineSheetProps {
  detail: LineDetail
  onClose: () => void
  /**
   * Add the tapped point on this trail to a day hike (#979, frame `1f`).
   *
   * OPTIONAL, AND ABSENT IS THE POINT. This sheet's own §2 refusal is this
   * codebase's canonical "a sentence, never a dead button", cited by name in
   * five other modules - so the action may not arrive as a control that is
   * sometimes greyed out. The shell passes a handler only when the tap can
   * genuinely become a point on a walk: a phone with the trail lines, a line
   * the router can use, and no long-term closure on it. Otherwise there is
   * nothing here, exactly as before.
   *
   * WHAT IT ADDS IS THE POINT, NOT THE TRAIL, and the copy says so. #979 asks
   * for "add that trail to a day hike", and the draft cannot express a whole
   * named trail: two endpoints plus a shortest path is not the trail (on a
   * network the shortest way between a trail's ends frequently leaves it),
   * and either workaround would be the app inventing a route the hiker did
   * not draw. What is honest is the tap they already made, on the trail they
   * already tapped - which is the useful half anyway, because the whole point
   * of this door is that it starts from a line already on the screen.
   */
  onAddToDayHike?: () => void
}

export function LineSheet({ detail, onClose, onAddToDayHike }: LineSheetProps) {
  return (
    <div className="closure-sheet" role="dialog" aria-label="Trail line">
      <div className="legend__head">
        <h2 className="legend__title">{detail.heading}</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {detail.name !== null && <p className="closure-sheet__status">{detail.name}</p>}

      {detail.destinationLine !== null && (
        <p className="closure-sheet__range">{detail.destinationLine}</p>
      )}
      {detail.roundTripLine !== null && (
        <p className="closure-sheet__range">{detail.roundTripLine}</p>
      )}
      {detail.junctionLine !== null && (
        <p className="closure-sheet__range">{detail.junctionLine}</p>
      )}

      {/* What this trail is and where - features/NEARBY_TRAILS.md §2's length
          and park. Above the closure, because a hiker reads down and "24.0 mi
          · Harriman State Park" is the line that tells them which trail the
          sheet is even about. */}
      {detail.extentLine !== null && (
        <p className="closure-sheet__range">{detail.extentLine}</p>
      )}

      {/* The long-term closure (§3). On `closure-sheet__status`, which is the
          class ClosureSheet gives its own "Closed" line - one vocabulary for
          "do not walk this", which is the argument §3 won: a hiker learns one
          mark, and the two kinds of closed are told apart by the SENTENCE
          here, never by a different-looking line on the map. */}
      {detail.closureLine !== null && (
        <p className="closure-sheet__status">{detail.closureLine}</p>
      )}

      {/* The provenance line, same shape as the waypoint card's - naming the
          source is half of what the sheet exists for. */}
      {detail.sourceLine !== null && (
        <p className="closure-sheet__meta">{detail.sourceLine}</p>
      )}

      {/* §2's refusal, last, and deliberately a sentence rather than a
          disabled button: a control that looks pressable and is not teaches a
          hiker at a junction that the app is broken, where a sentence naming
          where switching DOES live sends them somewhere. There is no action
          in this sheet at all, which is the whole decision. */}
      {detail.switchNote !== null && (
        <p className="closure-sheet__meta">{detail.switchNote}</p>
      )}

      {/* #979's action, and the ONE thing this sheet does. It is not a
          contradiction of the refusal above: adding a point to a walk is not
          switching the map's subject, which is what §2 refuses and what the
          picker owns.

          Never over a closed trail, whatever the shell passed. The closure
          line is right above this, and offering a hiker a walk down a trail
          the router will then decline to route is worse than offering
          nothing - it is the app promising with one sentence what it refuses
          with the next. */}
      {onAddToDayHike !== undefined && detail.closureLine === null && (
        <button type="button" className="line-sheet__add" onClick={onAddToDayHike}>
          Add this point to a day hike
        </button>
      )}
    </div>
  )
}
