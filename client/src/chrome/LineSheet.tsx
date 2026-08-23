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
}

export function LineSheet({ detail, onClose }: LineSheetProps) {
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
    </div>
  )
}
