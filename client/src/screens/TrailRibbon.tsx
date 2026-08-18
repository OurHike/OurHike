// The whole trail, above the rows (#790).
//
// THIS IS AN ORIENTATION, NEVER A MEASURING DEVICE, and the constraint is
// arithmetic rather than taste: a phone-width ribbon carrying the AT's
// 2,197 miles is roughly 7½ miles per pixel, so a three-day trip is eight
// pixels and a day is two or three. Nothing on it can be read as a figure,
// which is why nothing on it is drawn as one - every actual number stays in
// the rows underneath, where it has room to be read. The pressure to label
// this thing will be constant; the answer is here so it does not have to be
// re-argued each time.
//
// What it IS for: "where in this hike am I looking", and a way to get
// somewhere else. Tapping a band scrubs the rows to that piece.
//
// One band per piece, and a part-walked trip paints its walked ground
// inside its own band - so the ink says what happened and the hatching says
// what is only intended, at every scale the ribbon has.

import { spanFraction, type HikePiece, type Span } from '../lib/hikes'
import { stopLabel } from './../lib/planDisplay'
import './plan.css'

export interface TrailRibbonProps {
  pieces: readonly HikePiece[]
  /** The hike's own extent - the ribbon's frame, and what every fraction
   *  below is a fraction OF. */
  bounds: Span
  startLabel: string
  endLabel: string
  /** Miles walked and miles left, already formatted. Two numbers, no
   *  percentage and no pace: SEGMENTS.md's "a personal record, not a
   *  performance" survives the zoom out. */
  figures: string
  /** Where the hiker is, on the pipeline's mile axis - a marker only, and
   *  only when there is a fix inside this hike. */
  hereMile: number | null
  /** Scrub the rows to a piece. */
  onPick: (pieceId: string) => void
  /** The piece the rows are scrubbed to, if any. */
  pickedId: string | null
}

export function TrailRibbon({
  pieces,
  bounds,
  startLabel,
  endLabel,
  figures,
  hereMile,
  onPick,
  pickedId,
}: TrailRibbonProps) {
  const here =
    hereMile === null || hereMile < bounds.from || hereMile > bounds.to
      ? null
      : spanFraction({ from: bounds.from, to: hereMile }, bounds).length

  return (
    <div className="ribbon">
      <div className="ribbon__track">
        {pieces.map((piece) => {
          const { start, length } = spanFraction(piece.span, bounds)
          return (
            <button
              type="button"
              key={piece.id}
              className={`ribbon__band ribbon__band--${bandKind(piece)}`}
              style={{ left: `${start * 100}%`, width: `${length * 100}%` }}
              aria-label={bandLabel(piece)}
              aria-pressed={piece.id === pickedId}
              onClick={() => onPick(piece.id)}
            >
              {piece.kind === 'trip' &&
                piece.state === 'part' &&
                piece.walked.map((walked) => {
                  // Fractions of the PIECE, not of the hike - this sits
                  // inside the band's own box.
                  const inner = spanFraction(walked, piece.span)
                  return (
                    <span
                      key={`${walked.from}-${walked.to}`}
                      className="ribbon__band-walked"
                      style={{
                        left: `${inner.start * 100}%`,
                        width: `${inner.length * 100}%`,
                      }}
                    />
                  )
                })}
            </button>
          )
        })}
      </div>

      {here !== null && (
        <span
          className="ribbon__here"
          style={{ left: `${here * 100}%` }}
          role="img"
          aria-label="Where you are"
        />
      )}

      <p className="ribbon__ends">
        <span className="ribbon__end">{startLabel}</span>
        <span className="ribbon__figures">{figures}</span>
        <span className="ribbon__end">{endLabel}</span>
      </p>
    </div>
  )
}

function bandKind(piece: HikePiece): string {
  return piece.kind === 'gap' ? 'gap' : piece.state
}

/** What a band is, in words - because at seven miles to the pixel the
 *  drawing alone is not readable, and a screen reader gets nothing from
 *  hatching. */
function bandLabel(piece: HikePiece): string {
  if (piece.kind === 'gap') {
    const label = (ref: { mile: number; name?: string }) =>
      stopLabel({ mile: ref.mile, ...(ref.name === undefined ? {} : { name: ref.name }) })
    return `Not walked: ${label(piece.from)} to ${label(piece.to)}`
  }
  const state =
    piece.state === 'walked'
      ? 'walked'
      : piece.state === 'part'
        ? 'part walked'
        : 'planned'
  return `${piece.trip.name}, ${state}`
}
