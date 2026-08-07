// One downloadable thing on the Downloads screen, in every state it can be
// in (#192).
//
// This is today's whole-screen download body, lifted out unchanged in
// behaviour and given a name and a summary, so the screen can hold more than
// one of them. What it renders is a THING A HIKER CHOSE - today the
// background (lib/packages.ts), which is several archives underneath and one
// download here. It deliberately knows nothing about archives: how N of them
// combine into the status handed in is lib/backgroundStatus.ts's job, and a
// card that knew would be a second place for that rule to be got wrong.
//
// Every honesty property the single-card screen had is a property of this
// card, and they are the reason it stays a pure render of the status it is
// handed:
//   - the real size is stated before anything is committed to
//   - a failed transfer offers RESUME, never restart (WIREFRAMES.md `7a`) -
//     re-fetching 314 MB from zero because the connection dropped at 90% is
//     precisely the failure someone on trailhead wifi cannot afford
//   - "Stopped at X of Y" says what is already on the phone
//   - an archive the OS reclaimed says so, rather than reading as one that
//     was never downloaded (#190)
//
// The detail picker is part of the card in every state, which is a change
// from #192's card and the reason is the tabs above it (#298): a control
// that comes and goes as a download progresses makes each tab a different
// shape, and a hiker comparing two maps is then comparing two layouts. What
// varies is whether it can be USED. Once bytes are on the phone or moving
// towards it, changing detail means re-downloading, so the levels grey out
// and the note says what would have to happen instead - which says more than
// an absent control ever did.

import { useState } from 'react'
import { facingFullDownload } from '../lib/backgroundStatus'
import { formatBytes, formatBytesLive } from '../lib/formatBytes'
import type { PersistenceState } from '../lib/storageHealth'
import { DetailPicker, type DetailOption } from './DetailPicker'

export type DownloadStatus =
  | { state: 'not-downloaded' }
  | { state: 'downloading'; receivedBytes: number; totalBytes: number }
  /** Reading back the bytes already on the phone, to check them against what
   *  was published, before asking the network for the rest. Its own state
   *  because it is local work that looks exactly like a stalled transfer -
   *  and someone in a dead spot needs to know which of the two it is
   *  (#197). */
  | { state: 'checking'; checkedBytes: number; totalBytes: number }
  | { state: 'failed'; receivedBytes: number; totalBytes: number }
  /** The download finished and its bytes matched no published build, so
   *  NOTHING was kept - resuming onto right-length-wrong-content bytes could
   *  only rebuild the same wrong archive (#238). Its own state because it is
   *  the one failure whose remedy is starting over, and it must never sit
   *  behind a Resume button. Session-only by design: a mismatch persists no
   *  record, so a reload lawfully returns to not-downloaded or evicted. */
  | { state: 'hash-mismatch' }
  | { state: 'downloaded'; totalBytes: number; completedAt: Date }
  /** An archive finished here and its bytes are gone - evicted by the OS,
   *  not deleted by the hiker (storageHealth.ts's marker tells the two
   *  apart, #190). completedAt is when it finished, when that survived. */
  | { state: 'evicted'; completedAt: Date | null }

export interface DownloadCardProps {
  /** What this download is called - the card's own label, so its buttons are
   *  reachable by the thing they belong to. Never rendered as a heading:
   *  with tabs the tab names the sheet, and with one sheet the surrounding
   *  copy has (screens/Downloads.tsx). */
  title: string
  status: DownloadStatus
  /** This download's own failure, in its own card. A shared notice could
   *  only ever say "a download failed" without saying which one. */
  error?: string | null
  /** This download's levels, its chosen one, and how to report a change.
   *  Every level the app knows comes through, with a null size where this
   *  download has none of it, so the picker is the same shape under every
   *  tab (DetailPicker). `name` keeps the two cards' radio groups apart. */
  detail: {
    options: readonly DetailOption[]
    value: string
    onChange: (id: string) => void
    name?: string
  }
  /** What asking for durable storage came to - null while unanswered. Drives
   *  wording only: best-effort storage is stated, never silently assumed
   *  away (#190). One answer for the origin, shown against each package that
   *  is actually holding bytes. */
  persistence?: PersistenceState | null
  onStart: () => void
  onResume: () => void
  onDelete: () => void
}

/** Why the levels are greyed while bytes are here or on their way. Said in
 *  terms of what would have to happen to change it, because "you cannot" on
 *  its own leaves someone hunting for a setting that does not exist. */
function lockedNote(status: DownloadStatus): string {
  return status.state === 'downloaded'
    ? 'This map is on the phone. Deleting it and downloading again is how to change the detail.'
    : 'A download is under way. Its detail is fixed until it finishes.'
}

function percent(received: number, total: number): number {
  return total === 0 ? 0 : Math.round((received / total) * 100)
}

function formatDay(date: Date): string {
  return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })
}

export function DownloadCard({
  title,
  status,
  error = null,
  detail,
  persistence = null,
  onStart,
  onResume,
  onDelete,
}: DownloadCardProps) {
  // Deleting asks twice, and that is the whole design. DownloadsDialog.tsx
  // already names a mis-tap deleting a download as "the worst possible thing
  // for this particular window to get wrong" - and then guarded only the
  // backdrop, leaving the delete itself one tap. One tap, on a phone, on a
  // trail, destroying a map that took trailhead wifi to fetch and takes
  // signal to restore. The second ask states that cost at the moment it is
  // about to be paid; nothing else in this app confirms anything, because
  // nothing else it does is this hard to undo.
  const [confirmingDelete, setConfirmingDelete] = useState(false)

  const picker = (
    <DetailPicker
      options={detail.options}
      value={detail.value}
      onChange={detail.onChange}
      name={detail.name}
      locked={!facingFullDownload(status)}
      lockedNote={lockedNote(status)}
    />
  )

  return (
    // Labelled as a region so a card's buttons are reachable by the thing
    // they belong to - "Delete the map" says which map only because of what
    // it sits inside, for a screen reader and for a test alike.
    <section className="downloads__item" aria-label={title}>
      {/* The failure that belongs to THIS package, beside this package's
          button. Which download failed is half of what the sentence has to
          say once there is more than one. */}
      {error !== null && (
        <p role="alert" className="downloads__error">
          {error}
        </p>
      )}

      {status.state === 'not-downloaded' && (
        <>
          {picker}
          <button type="button" className="downloads__primary" onClick={onStart}>
            Download the map
          </button>
        </>
      )}

      {status.state === 'evicted' && (
        <div className="downloads__evicted">
          {/* The one sentence #190 exists for. "No map downloaded" here would
              be false - one WAS downloaded, and the phone removed it - and on
              a ridge that difference is the difference between re-downloading
              in town and staring at blank paper wondering what you did
              wrong. */}
          <p>
            {status.completedAt === null
              ? 'The map you downloaded is no longer on this phone.'
              : `The map you downloaded on ${formatDay(status.completedAt)} is no longer on this phone.`}{' '}
            The phone removed it to free up space — that can happen when storage runs low.
            Downloading it again is the only fix, and it needs signal.
          </p>
          {picker}
          <button type="button" className="downloads__primary" onClick={onStart}>
            Download it again
          </button>
        </div>
      )}

      {status.state === 'checking' && (
        <div className="downloads__progress">
          <p>Checking the part already on this phone.</p>
          <div
            role="progressbar"
            aria-label="Checking downloaded data"
            aria-valuenow={percent(status.checkedBytes, status.totalBytes)}
            aria-valuemin={0}
            aria-valuemax={100}
            className="downloads__bar"
          >
            <span
              className="downloads__bar-fill"
              style={{ width: `${percent(status.checkedBytes, status.totalBytes)}%` }}
            />
          </div>
          {/* Said plainly because the whole point of this state is telling a
              stalled phone from a stalled connection: someone on one bar who
              thinks this is the network will walk somewhere else for nothing,
              and someone who thinks a dead connection is this will stand
              still waiting for a download that is not happening. */}
          <p className="downloads__note">
            This part happens on the phone and needs no signal. The download carries on
            from where it stopped once it is done.
          </p>
          {picker}
        </div>
      )}

      {status.state === 'downloading' && (
        <div className="downloads__progress">
          <div
            role="progressbar"
            aria-label="Download progress"
            aria-valuenow={percent(status.receivedBytes, status.totalBytes)}
            aria-valuemin={0}
            aria-valuemax={100}
            className="downloads__bar"
          >
            <span
              className="downloads__bar-fill"
              style={{ width: `${percent(status.receivedBytes, status.totalBytes)}%` }}
            />
          </div>
          {/* The received figure changes on every chunk; formatBytesLive keeps
              its digits calm, and the reserved slot (sized to the total, the
              widest the counter can get, exact in ch because the font is
              monospace) keeps "of 314 MB" from shuffling sideways as 9 MB
              becomes 10 MB. */}
          <p className="downloads__bytes">
            <span
              className="downloads__bytes-received"
              style={{ minWidth: `${formatBytesLive(status.totalBytes).length}ch` }}
            >
              {formatBytesLive(status.receivedBytes)}
            </span>
            {` of ${formatBytes(status.totalBytes)}`}
          </p>
          {picker}
        </div>
      )}

      {status.state === 'failed' && (
        <div className="downloads__failed">
          <p className="downloads__bytes">
            {`Stopped at ${formatBytesLive(status.receivedBytes)} of ${formatBytes(
              status.totalBytes,
            )}.`}
          </p>
          <p>
            What you already have is kept — picking this up again carries on from there.
          </p>
          {picker}
          <button type="button" className="downloads__primary" onClick={onResume}>
            Resume
          </button>
        </div>
      )}

      {status.state === 'hash-mismatch' && (
        <div className="downloads__mismatch">
          {/* Every other failure on this card keeps what arrived; this one
              kept nothing, on purpose - the bytes were the right length and
              the wrong map. Saying so without hex, and offering a button that
              reads as a fresh start: a Resume here would promise to carry on
              from bytes that no longer exist. */}
          <p>
            The map that arrived is not the one the server published, so none of it was
            saved. Any map already on this phone is untouched. Downloading again fetches a
            fresh copy from the start.
          </p>
          {picker}
          <button type="button" className="downloads__primary" onClick={onStart}>
            Start the download over
          </button>
        </div>
      )}

      {status.state === 'downloaded' && (
        <div className="downloads__done">
          <p className="downloads__bytes">
            {`${formatBytes(status.totalBytes)} on this phone, finished ${formatDay(
              status.completedAt,
            )}.`}
          </p>
          {/* Durability, stated at its honest weight. `granted` earns no
              banner - protected is the expected state and saying so is
              noise. A denial or an old browser gets one calm sentence,
              because best-effort storage CAN be reclaimed by the OS and a
              hiker planning around this download deserves to know that
              before the trailhead, not from a blank map (#190). */}
          {(persistence === 'denied' || persistence === 'unsupported') && (
            <p className="downloads__note">
              This phone treats the download as reclaimable if storage runs very low. It
              was asked to protect it{persistence === 'denied' ? ' and declined' : ''} —
              if the map ever disappears, this screen will say so, and downloading again
              restores it.
            </p>
          )}
          {picker}
          {!confirmingDelete ? (
            <button
              type="button"
              className="downloads__secondary"
              onClick={() => setConfirmingDelete(true)}
            >
              Delete the map
            </button>
          ) : (
            <div className="downloads__confirm">
              <p className="downloads__confirm-question">
                {`Delete this ${formatBytes(status.totalBytes)} map from the phone? Getting it back means downloading the whole thing again, and that needs signal.`}
              </p>
              <div className="downloads__confirm-actions">
                {/* Keep first, styled as the primary: the safe answer is the
                    default read, and the destructive one never sits where the
                    finger just was. */}
                <button
                  type="button"
                  className="downloads__primary"
                  onClick={() => setConfirmingDelete(false)}
                >
                  Keep it
                </button>
                <button
                  type="button"
                  className="downloads__secondary"
                  onClick={() => {
                    setConfirmingDelete(false)
                    onDelete()
                  }}
                >
                  Yes, delete it
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  )
}
