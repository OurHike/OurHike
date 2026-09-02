// Just the stretch a hiker is walking, as the second decision on the hiking
// sheet's panel (#558, features/OFFLINE_COVERAGE.md §4-§5).
//
// THE WHOLE TRAIL STAYS THE BUTTON ABOVE THIS, and this card exists under it
// rather than beside it. WIREFRAMES.md §4 retired the per-section list with
// one sentence - "sections were a choice somebody had to get right mile by
// mile, and a wrong answer cost them map where they were walking" - and this
// is what a stretch has to be to not re-earn it: DERIVED from the hike
// lib/plannedHike.ts already holds, never enumerated as rows. There is no
// list here to pick from, and nothing to get wrong; a hiker who changes their
// hike gets the question asked again from something they already said.
//
// A pure render of the offer it is handed, like DownloadCard: how the cells'
// states combine into one status is lib/backgroundStatus.ts's, which cells a
// hike crosses is lib/coverageCells.ts's, and what they cost comes off the
// manifest. Every state has a sentence, because a card that goes blank when
// there is no hike would read as a feature that is not there.

import { useState } from 'react'
import { downloadFillPercent, downloadPercent } from '../lib/downloadActivity'
import { formatBytes, formatBytesLive } from '../lib/formatBytes'
import { formatDistance, milesFromDisplay } from '../lib/units'
import type { UnitSystem } from '../lib/userPreferences'
import type { DownloadStatus } from './DownloadCard'

export interface StretchOffer {
  /** The hike the pieces are under, in one line (lib/plannedHike.ts's
   *  `hikeSummary`) - or null when the hiker has not set one. */
  hike: string | null
  /** Whether the pieces list has reached this phone at all. False on a phone
   *  that has never had signal since the cells were published, and on a
   *  release that carries none. */
  available: boolean
  /** How many cells the hike crosses, margin included. */
  pieces: number
  /** How many of them are not on this phone yet. */
  missing: number
  /** What the missing ones cost on the wire, or null where the manifest has
   *  not priced them - withheld, never guessed (#1167). */
  bytes: number | null
  /** How far past its own edge each piece reaches, from the index, in the
   *  cutter's own kilometres - the card says it in the hiker's units. */
  marginKm: number
  /** Feet or metres, for that one distance (lib/units.ts). */
  units: UnitSystem
  /** The pieces' combined state, in the card's own vocabulary. */
  status: DownloadStatus
  /** Whether the whole sheet is on the phone, which makes every stretch of
   *  it moot - the union of its cells is the sheet (OFFLINE_COVERAGE.md §5). */
  wholeSheetHere: boolean
  onTake: () => void
  onResume: () => void
  onRemove: () => void
}

/** The heading the card is labelled by - a region name, so its buttons are
 *  reachable by the thing they belong to, exactly as DownloadCard's are. */
export const STRETCH_TITLE = 'Just the stretch you’re walking'

/** What "pieces" are, said once where the number first appears: the 1°
 *  cells nobody sees, in words a hiker can use. */
function piecesWord(count: number): string {
  return count === 1 ? '1 piece' : `${count} pieces`
}

export function StretchCard({ stretch }: { stretch: StretchOffer }) {
  // Two taps to remove, on DownloadCard's reasoning: a map that took signal
  // to fetch is the one thing in this window that is hard to undo.
  const [confirmingRemove, setConfirmingRemove] = useState(false)

  const {
    hike,
    available,
    pieces,
    missing,
    bytes,
    marginKm,
    units,
    status,
    wholeSheetHere,
    onTake,
    onResume,
    onRemove,
  } = stretch

  // The index states the margin in kilometres (cut_cells.py's own unit); the
  // hiker reads it in theirs, through the one formatter every distance in
  // this app goes through. `milesFromDisplay` is that module's km-to-miles
  // half, which is exactly the conversion this is.
  const marginLine = `Each piece reaches about ${formatDistance(
    milesFromDisplay(marginKm, 'metric'),
    units,
  )} past its own edge, and the map draws a dashed line where it stops.`

  let body: React.ReactNode
  if (wholeSheetHere) {
    body = (
      <p className="downloads__note">
        The whole trail is on this phone, so every stretch of it is too.
      </p>
    )
  } else if (hike === null) {
    body = (
      <p className="downloads__note">
        Set the hike you’re on — More › Your hike — and this offers only the ground it
        crosses, instead of the whole trail.
      </p>
    )
  } else if (!available) {
    body = (
      <p className="downloads__note">
        The list of pieces hasn’t reached this phone yet. It arrives on its own with
        signal — the whole trail above is still one tap.
      </p>
    )
  } else if (pieces === 0) {
    body = (
      <p className="downloads__note">
        {`${hike} crosses no ground the pieces cover yet, so the whole trail above is the download for it.`}
      </p>
    )
  } else if (status.state === 'downloading') {
    body = (
      <div className="downloads__progress">
        <p className="downloads__note">{`${hike} · ${piecesWord(pieces)}`}</p>
        <div
          role="progressbar"
          aria-label="Stretch download progress"
          aria-valuenow={downloadPercent(status.receivedBytes, status.totalBytes)}
          aria-valuemin={0}
          aria-valuemax={100}
          className="downloads__bar"
        >
          <span
            className="downloads__bar-fill"
            style={{
              width: `${downloadFillPercent(status.receivedBytes, status.totalBytes)}%`,
            }}
          />
        </div>
        <p className="downloads__bytes">
          {`${formatBytesLive(status.receivedBytes)} of ${formatBytes(status.totalBytes)}`}
        </p>
      </div>
    )
  } else if (status.state === 'checking') {
    body = (
      <div className="downloads__progress">
        <p className="downloads__note">{`${hike} · ${piecesWord(pieces)}`}</p>
        <p>Checking the pieces already on this phone.</p>
        <div
          role="progressbar"
          aria-label="Checking downloaded pieces"
          aria-valuenow={downloadPercent(status.checkedBytes, status.totalBytes)}
          aria-valuemin={0}
          aria-valuemax={100}
          className="downloads__bar"
        >
          <span
            className="downloads__bar-fill"
            style={{
              width: `${downloadFillPercent(status.checkedBytes, status.totalBytes)}%`,
            }}
          />
        </div>
      </div>
    )
  } else if (status.state === 'failed') {
    body = (
      <div className="downloads__failed">
        <p className="downloads__bytes">
          {`${piecesWord(pieces - missing)} of ${pieces} here — stopped at ${formatBytesLive(
            status.receivedBytes,
          )} of ${formatBytes(status.totalBytes)}.`}
        </p>
        <p>
          What you already have is kept — picking this up again carries on from there.
        </p>
        <button type="button" className="downloads__primary" onClick={onResume}>
          Resume the stretch
        </button>
      </div>
    )
  } else if (status.state === 'downloaded') {
    body = (
      <div className="downloads__done">
        <p className="downloads__bytes">
          {`${hike} · ${piecesWord(pieces)} on this phone, ${formatBytes(status.totalBytes)}.`}
        </p>
        {/* The seam, said where the bytes are: a hiker who knows the map
            ends is a hiker who is not surprised by a dashed line on a
            ridge. The figure is the index's own, never a constant here. */}
        <p className="downloads__note">{marginLine}</p>
        {!confirmingRemove ? (
          <button
            type="button"
            className="downloads__secondary"
            onClick={() => setConfirmingRemove(true)}
          >
            Remove the stretch
          </button>
        ) : (
          <div className="downloads__confirm">
            <p className="downloads__confirm-question">
              {`Remove these ${piecesWord(pieces)} from the phone? Getting them back means downloading them again, and that needs signal.`}
            </p>
            <div className="downloads__confirm-actions">
              <button
                type="button"
                className="downloads__primary"
                onClick={() => setConfirmingRemove(false)}
              >
                Keep them
              </button>
              <button
                type="button"
                className="downloads__secondary"
                onClick={() => {
                  setConfirmingRemove(false)
                  onRemove()
                }}
              >
                Yes, remove them
              </button>
            </div>
          </div>
        )}
      </div>
    )
  } else {
    // not-downloaded, evicted and hash-mismatch: nothing usable is here, and
    // the offer is the same one - priced against what is missing, which for
    // all three is everything.
    body = (
      <>
        {status.state === 'evicted' && (
          <p className="downloads__note">
            The pieces you downloaded are no longer on this phone — the phone removed them
            to free up space.
          </p>
        )}
        {status.state === 'hash-mismatch' && (
          <p className="downloads__note">
            The pieces that arrived were not the ones the server published, so none of
            them were saved. Taking them again fetches a fresh copy.
          </p>
        )}
        <p className="downloads__note">{`${hike} · ${piecesWord(pieces)}`}</p>
        {/* The price of what is MISSING, never of the whole stretch
            (OFFLINE_COVERAGE.md §9): a hiker extending last week's stretch
            pays for the new ground only, and the figure says so. */}
        <p className="downloads__bytes">
          {bytes === null
            ? 'Size not known yet — it arrives with the manifest.'
            : missing < pieces
              ? `About ${formatBytes(bytes)} for the ${piecesWord(missing)} not here yet.`
              : `About ${formatBytes(bytes)}.`}
        </p>
        <p className="downloads__note">{marginLine}</p>
        <button type="button" className="downloads__primary" onClick={onTake}>
          {status.state === 'not-downloaded' ? 'Take this stretch' : 'Take it again'}
        </button>
      </>
    )
  }

  return (
    <section className="downloads__stretch" aria-label={STRETCH_TITLE}>
      <p className="downloads__stretch-title">{STRETCH_TITLE}</p>
      {body}
    </section>
  )
}
