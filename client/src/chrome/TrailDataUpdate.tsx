// The ask before a hiker's map is replaced (#919).
//
// A published data fix used to reach nobody who already had the app: the
// download asked whether there was trail data and never which, so a phone that
// finished one download drew that release forever. #749's water gate is what
// made the cost concrete - the bucket served the corrected layer while every
// installed phone went on drawing 1,535 ungated OSM water points, some of them
// drinking fountains thirty miles away in Manhattan.
//
// WHY THIS IS AN ASK AND NOT A SILENT SWAP
//
// The maintainer's decision (2026-08-21): **nothing is replaced without the
// hiker being asked.** So the severity `lib/dataRefresh.ts` carries decides
// what this SAYS and never whether it appears. A routine release and a
// consequential one both stop here; one of them says a water point was
// removed.
//
// That is a real cost and worth naming: a hiker who never taps Update keeps
// the old map, which is the exact failure this whole mechanism exists to end.
// It is accepted because a map that rearranges itself under somebody at a
// junction is the worse of the two, and because "not now" is remembered
// against one version rather than forever - the next release asks again.
//
// A ROW, NOT A DIALOG
//
// The same shape as the ATC new-alerts row it sits beside (MapScreen.tsx), and
// for the reasons recorded there: at the foot of the main column, in flow
// rather than floating over a canvas that already has the locate stack and the
// credit strip in its corners, and `aria-live="polite"` because "there is newer
// data" is not "this changes what you do next".
//
// It carries its own two buttons rather than opening a sheet. What a hiker
// needs to decide is one sentence long - what changed, what it costs - and a
// sheet would put a tap between them and the answer for no gain.

import type { AvailableRefresh } from '../lib/dataRefresh'
import { CONSEQUENTIAL } from '../lib/dataManifest'

export interface TrailDataUpdateProps {
  /** The release on offer, or null to render nothing. */
  update: AvailableRefresh | null
  /** Whether to caution about the cost: not on wifi, and big enough to matter
   *  (lib/dataRefresh.warnsAboutData). */
  warnsAboutData: boolean
  /** True while the bytes are coming. */
  applying: boolean
  onApply: () => void
  onDecline: () => void
}

/** Bytes as a hiker reads them. One decimal below ten megabytes, none above -
 *  "5.8 MB" is a number somebody can weigh, "5.78 MB" is a measurement. */
export function describeSize(bytes: number | null): string | null {
  if (bytes === null) return null
  const mb = bytes / 1_000_000
  if (mb < 0.1) return '<0.1 MB'
  return mb < 10 ? `${mb.toFixed(1)} MB` : `${Math.round(mb)} MB`
}

/**
 * What changed, in the hiker's terms - or an honest admission that this cannot
 * say.
 *
 * The undescribed case is not a failure to render: it is a phone more than one
 * release behind, reading a manifest that describes a single hop it is not
 * making. Saying "the map has changed" there is the true sentence; listing
 * counts from somebody else's transition would be the plausible one.
 */
export function describeChange(update: AvailableRefresh): string {
  if (!update.described) return 'The map data has changed since this was downloaded.'

  const parts: string[] = []
  if (update.removed > 0) parts.push(`${update.removed} removed`)
  if (update.moved > 0) parts.push(`${update.moved} moved`)
  if (update.added > 0) parts.push(`${update.added} added`)
  if (update.edited > 0) parts.push(`${update.edited} corrected`)
  // Every count zero with the hashes differing is a real release: something
  // changed that the grading does not count, a reordering or a field nobody
  // diffs. "Updated" is what is true about it.
  if (parts.length === 0) return 'Waypoints and trail lines updated.'
  return `Waypoints: ${parts.join(', ')}.`
}

export function TrailDataUpdate({
  update,
  warnsAboutData,
  applying,
  onApply,
  onDecline,
}: TrailDataUpdateProps) {
  if (update === null) return null

  const size = describeSize(update.bytes)
  const serious = update.severity === CONSEQUENTIAL

  return (
    <div
      className={`trail-data-update${serious ? ' trail-data-update--serious' : ''}`}
      aria-live="polite"
    >
      <p className="trail-data-update__what">
        <strong>Newer trail data</strong> · {describeChange(update)}
      </p>
      {/* The cost, and only where it is worth a hiker's attention. `size` is
          null when the manifest publishes no size for one of the changed
          artifacts - it must read as "cannot say", never as free, which is why
          the caution below treats an unknown size as a large one. */}
      {warnsAboutData && (
        <p className="trail-data-update__cost">
          {size === null
            ? 'Downloading this may use mobile data.'
            : `About ${size}. This may use mobile data.`}
        </p>
      )}
      {!warnsAboutData && size !== null && (
        <p className="trail-data-update__cost">About {size}.</p>
      )}
      <div className="trail-data-update__actions">
        <button
          type="button"
          className="trail-data-update__apply"
          onClick={onApply}
          disabled={applying}
        >
          {applying ? 'Updating…' : 'Update'}
        </button>
        <button
          type="button"
          className="trail-data-update__decline"
          onClick={onDecline}
          disabled={applying}
        >
          Not now
        </button>
      </div>
    </div>
  )
}
