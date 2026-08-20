// The club sheet (#598): who looks after the stretch of trail a hiker just
// tapped, and where the answer came from.
//
// features/CORRIDOR_VIEW.md specifies it; every sentence is decided in
// lib/clubDetail.ts, where it is testable without a canvas, and this component
// only lays them out. Rendered on LineSheet.tsx's own classes so the two read
// as one family - which is the same reason LineSheet uses AtcUpdateSheet's.
//
// Lines that are null are OMITTED, never placeholdered, the restraint every
// sheet in this app keeps. A club with no region shows no region; a stretch
// with no recorded club shows no maintained mileage, because it has none.

import type { ClubDetail } from '../lib/clubDetail'

export interface ClubSheetProps {
  detail: ClubDetail
  onClose: () => void
}

export function ClubSheet({ detail, onClose }: ClubSheetProps) {
  return (
    <div className="closure-sheet" role="dialog" aria-label="Who maintains this trail">
      <div className="legend__head">
        <h2 className="legend__title">{detail.heading}</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {detail.subtitle !== null && (
        <p className="closure-sheet__status">{detail.subtitle}</p>
      )}

      <p className="closure-sheet__range">{detail.rangeLine}</p>

      {detail.extentLine !== null && (
        <p className="closure-sheet__range">{detail.extentLine}</p>
      )}

      {/* The absence, in words. Kept above the scale line so a hiker reads
          what is unknown before how much of the trail shares it. */}
      {detail.absenceLine !== null && (
        <p className="closure-sheet__range">{detail.absenceLine}</p>
      )}
      {detail.scaleLine !== null && (
        <p className="closure-sheet__range">{detail.scaleLine}</p>
      )}

      {/* What this hiker has actually walked of it (#598's `visited`), worked
          out on the phone from the phone's own fixes and never uploaded - see
          lib/walkedMiles.ts. Above the provenance because it is about the
          hiker, and the provenance is about the data. */}
      {detail.walkedLine !== null && (
        <p className="closure-sheet__range">{detail.walkedLine}</p>
      )}

      {/* Two provenance lines rather than one, because they are two different
          claims: which club, and how the club's name is spelled. */}
      {detail.attributionSourceLine !== null && (
        <p className="closure-sheet__meta">{detail.attributionSourceLine}</p>
      )}
      {detail.nameSourceLine !== null && (
        <p className="closure-sheet__meta">{detail.nameSourceLine}</p>
      )}
    </div>
  )
}
