// The bail sheet (#1373, the design's frame 3b, decision D8): "every exit
// from a half-built route shows the bail sheet - what it costs, in words."
//
// Bailing used to cost work silently, which is one of the six defects the
// rebuild exists to fix: a tab tap away from the builder kept the draft
// alive with nothing saying so, and opening the other kind of plan dropped
// it outright (App.tsx's `sweepForBuilder`, #997). This sheet is where the
// navigator (lib/navigator.ts) parks that move until the hiker has said
// which of three things they meant.
//
// THREE ANSWERS, NONE OF THEM ASSUMED. Keep it for later leaves the draft
// exactly where it is - "it waits on Today and on the Plan tab until you
// finish or delete it", which is what the Plan tab's "Back to your route"
// already offers. Discard it is the only way the draft goes, and it is a
// tap the hiker took. Stay here is the move not taken.
//
// TWO, WHERE KEEPING IS NOT ON OFFER (#1378). The header above names
// `sweepForBuilder` as one of the moves this sheet exists for, and it is the
// one move that cannot honour "Keep it for later": a sweep runs precisely
// because the hiker is starting the OTHER kind of plan, and only one route
// can be live (#997). Offering to keep a draft that the next line drops
// would be the sheet lying about what the button does, which is worse than
// not offering it. So `onKeep` is optional, and without it the sheet asks a
// narrower question, says why keeping is absent, and puts the focus on
// "Stay here" rather than on the destructive answer.
//
// What the route has cost so far is a sentence handed in by the shell,
// through the figures every other surface prints (lib/units.ts), or nothing
// where nothing has been routed yet - a sheet that said "0 mi so far" would
// be pricing an empty draft.

import type { KeyboardEvent } from 'react'
import './bailSheet.css'

export interface BailSheetProps {
  /** "2 legs · 4.1 mi so far", or null with nothing routed yet. */
  figures: string | null
  /** Absent where the move cannot leave the draft standing - see the header. */
  onKeep?: () => void
  onDiscard: () => void
  onStay: () => void
}

export function BailSheet({ figures, onKeep, onDiscard, onStay }: BailSheetProps) {
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') onStay()
  }
  const canKeep = onKeep !== undefined
  return (
    <div
      className="bail-sheet"
      role="dialog"
      aria-modal="true"
      aria-labelledby="bail-sheet-title"
      onKeyDown={onKeyDown}
    >
      <h2 id="bail-sheet-title" className="bail-sheet__title">
        {canKeep ? 'Keep this half-built route?' : 'Drop this half-built route?'}
      </h2>
      {figures !== null && <p className="bail-sheet__figures">{figures}</p>}
      <p className="bail-sheet__line">
        {canKeep
          ? 'Kept, it waits on Today and on the Plan tab until you finish or delete it.'
          : 'Starting the other kind of plan needs this one out of the way, so keeping it is not on offer here.'}
      </p>
      <div className="bail-sheet__actions">
        {canKeep && (
          <button
            type="button"
            className="bail-sheet__primary"
            onClick={onKeep}
            autoFocus
          >
            Keep it for later
          </button>
        )}
        <button type="button" className="bail-sheet__secondary" onClick={onDiscard}>
          Discard it
        </button>
        {/* Focused where there is nothing to keep, so the answer under the
            cursor is the one that costs nothing. */}
        <button
          type="button"
          className="bail-sheet__quiet"
          onClick={onStay}
          autoFocus={!canKeep}
        >
          Stay here
        </button>
      </div>
    </div>
  )
}
