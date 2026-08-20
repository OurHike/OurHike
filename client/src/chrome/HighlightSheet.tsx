// The highlight sheet (#858): what a stretch worth going to is, how far and
// how much climbing, and who says it is worth going to.
//
// Every sentence is decided in lib/highlightDetail.ts, where it is testable
// without a canvas; this only lays them out, on ClubSheet's classes - which are
// LineSheet's, which are AtcUpdateSheet's - so all four read as one family.
//
// Lines that are null are OMITTED, never placeholdered. The absences here are
// ordinary rather than exceptional: a highlight that leaves the A.T. has no
// measurable climbing, a release may publish no citation, and most hikers have
// walked none of most of the trail.

import type { HighlightDetail } from '../lib/highlightDetail'

export interface HighlightSheetProps {
  detail: HighlightDetail
  onClose: () => void
}

export function HighlightSheet({ detail, onClose }: HighlightSheetProps) {
  return (
    <div className="closure-sheet" role="dialog" aria-label="Worth going to">
      <div className="legend__head">
        <h2 className="legend__title">{detail.heading}</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <p className="closure-sheet__status">{detail.subtitle}</p>

      {/* Always present: the distance comes from the legs' own mileposts, so
          there is at least that much to say even with no profile on the
          phone. What drops out is the ascent and the time. */}
      <p className="closure-sheet__derived">{detail.derivedLine}</p>

      {/* Whose estimate this is (#880). Directly under the figure it qualifies,
          because a hiker who set their pace optimistic in week one and forgot
          is exactly who the line is for. Absent at the standard pace - a
          caveat on every line reads like a caveat on none. */}
      {detail.paceRelativeLine !== null && (
        <p className="closure-sheet__pace">{detail.paceRelativeLine}</p>
      )}

      {/* The one line that must not be missed if it is there: the estimate
          above does not fit this ground (#851). Directly under the numbers it
          qualifies, rather than down with the provenance, because a hiker who
          reads only the top of the sheet is exactly who it is for. */}
      {detail.cautionLine !== null && (
        <p className="closure-sheet__caution">{detail.cautionLine}</p>
      )}

      {detail.derivedSourceLine !== null && (
        <p className="closure-sheet__meta">{detail.derivedSourceLine}</p>
      )}

      {/* Only for a highlight with more than one leg - a single-leg one would
          repeat its own subtitle. */}
      {detail.legLines.length > 0 && (
        <ul className="closure-sheet__legs">
          {detail.legLines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}

      {/* One basis, never two. Two chips would read as corroboration - two
          independent sources agreeing - when they are two different questions
          with one answer between them (lib/highlights.ts's strongestBasis). */}
      {detail.basisLabel !== null && (
        <p className="closure-sheet__basis">{detail.basisLabel}</p>
      )}
      {detail.basisLine !== null && (
        <p className="closure-sheet__note">{detail.basisLine}</p>
      )}

      {detail.walkedLine !== null && (
        <p className="closure-sheet__note">{detail.walkedLine}</p>
      )}

      {detail.citationLine !== null && (
        <p className="closure-sheet__meta">{detail.citationLine}</p>
      )}
      {detail.clubLine !== null && (
        <p className="closure-sheet__meta">{detail.clubLine}</p>
      )}
    </div>
  )
}
