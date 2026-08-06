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
// The detail picker only appears when there is a download to start, and only
// where there are levels to pick. Once it is on the phone, changing detail
// means re-downloading, which is what Settings' "detail for new downloads"
// row is for - offering the choice here would imply it could be changed in
// place.

import { formatBytes, formatBytesLive } from '../lib/formatBytes'
import type { DetailLevel } from '../lib/downloadDetail'
import type { PersistenceState } from '../lib/storageHealth'
import { DetailPicker } from './DetailPicker'

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
  | { state: 'downloaded'; totalBytes: number; completedAt: Date }
  /** An archive finished here and its bytes are gone - evicted by the OS,
   *  not deleted by the hiker (storageHealth.ts's marker tells the two
   *  apart, #190). completedAt is when it finished, when that survived. */
  | { state: 'evicted'; completedAt: Date | null }

export interface DownloadCardProps {
  /** What this download is called, and one line on what the bytes buy. */
  title: string
  summary: string
  status: DownloadStatus
  /** This download's own failure, in its own card. A shared notice could
   *  only ever say "a download failed" without saying which one. */
  error?: string | null
  /** Present where the download has detail levels to choose between - the
   *  background does (downloadDetail.ts). Absent renders no picker. */
  detail?: { level: DetailLevel; onChange: (level: DetailLevel) => void }
  /** What asking for durable storage came to - null while unanswered. Drives
   *  wording only: best-effort storage is stated, never silently assumed
   *  away (#190). One answer for the origin, shown against each package that
   *  is actually holding bytes. */
  persistence?: PersistenceState | null
  /** False when this card is the only one on the screen and the surrounding
   *  copy has already named what is being downloaded. */
  showHeading?: boolean
  onStart: () => void
  onResume: () => void
  onDelete: () => void
}

function percent(received: number, total: number): number {
  return total === 0 ? 0 : Math.round((received / total) * 100)
}

function formatDay(date: Date): string {
  return date.toLocaleDateString('en-US', { month: 'long', day: 'numeric' })
}

export function DownloadCard({
  title,
  summary,
  status,
  error = null,
  detail,
  persistence = null,
  showHeading = true,
  onStart,
  onResume,
  onDelete,
}: DownloadCardProps) {
  return (
    // Labelled as a region so a card's buttons are reachable by the thing
    // they belong to - "Delete the map" says which map only because of what
    // it sits inside, for a screen reader and for a test alike.
    <section className="downloads__item" aria-label={title}>
      {showHeading && (
        <>
          <h3 className="downloads__item-title">{title}</h3>
          <p className="downloads__item-summary">{summary}</p>
        </>
      )}

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
          {detail !== undefined && (
            <DetailPicker value={detail.level} onChange={detail.onChange} />
          )}
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
          {detail !== undefined && (
            <DetailPicker value={detail.level} onChange={detail.onChange} />
          )}
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
          <button type="button" className="downloads__primary" onClick={onResume}>
            Resume
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
          <button type="button" className="downloads__secondary" onClick={onDelete}>
            Delete the map
          </button>
        </div>
      )}
    </section>
  )
}
