// The report form (WIREFRAMES.md §6), shared by condition reports and by a
// thanks - which is a report type, not a separate model
// (features/SAYING_THANKS.md).
//
// The authoring time is taken at MOUNT, not at submit. Someone can start a
// report, walk on, and finish it twenty minutes later; and an offline report
// may not send for days. What matters is when they saw the thing, so that is
// the moment recorded - matching the `authored_at` field the reports API
// accepts and the authored timestamp the outbox carries.
//
// Nothing here blocks on network. Submitting while offline queues the report
// and says so, because on this trail that is the ordinary path.

import { useState } from 'react'
import type { ReportDraft } from '../lib/outbox'
import { PhotoUnusable, prepareReportPhoto } from '../lib/reportPhoto'
import './reporting.css'

export type ReportFormType = ReportDraft['type']

const TITLES: Record<ReportFormType, string> = {
  blowdown: 'Blow down',
  flooding: 'Flooding',
  trash: 'Trash',
  shelter_repair: 'Shelter repair',
  animals: 'Animals',
  invasive_species: 'Invasive species',
  bad_hikers: 'Something unsafe happened',
  thanks: 'Say thanks',
}

export interface ReportFormLocation {
  lat: number
  lon: number
  /**
   * Omitted when the fix cannot be placed on the centerline - off the trail,
   * or before the trail index has been downloaded. The coordinates are still
   * worth sending; only the mile is unknown.
   */
  mile?: number
}

export interface ReportFormSubmission extends ReportDraft {
  authoredAt: Date
  /** The prepared JPEG, if one was attached - bytes rather than a URL, see
   *  `OutboxItem.photo`. Absent is the ordinary case. */
  photo?: Blob
}

/**
 * What the form says about where the report will land.
 *
 * "mi 0.0" is Springer Mountain and 0,0 is the Atlantic off West Africa, so
 * neither is a stand-in for "we don't know yet" - this is the same rule the
 * header already keeps about the mile readout (chrome/Header.tsx). A
 * maintainer reading a queue of blowdowns needs to be able to tell the reports
 * with a place from the ones without, and both wrong answers hide that.
 */
function describeLocation(location: ReportFormLocation | null): string {
  if (location === null) return 'No GPS fix — this report will have no location'
  if (location.mile === undefined)
    return 'Location saved, but not matched to a trail mile'

  return `mi ${location.mile.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}`
}

export interface ReportFormProps {
  type: ReportFormType
  trailName: string | null
  reporterType: ReportDraft['reporter_type']
  /** Null when there is no GPS fix at all - see the note above. */
  location: ReportFormLocation | null
  /**
   * The place this report is about, when it started from a place's card
   * (FIELD_NOTES.md step 1). The soft reference `reports.poi_id` has carried
   * end to end since the schema landed, with nothing in the client
   * populating it - this is what does. Absent on every report that starts
   * from Settings, which is anchored by the fix alone exactly as before.
   */
  poiId?: string
  onSubmit: (submission: ReportFormSubmission) => void
  onCancel: () => void
  online?: boolean
  /** One line naming who looks after this stretch; only for a thanks. */
  stewards?: string | null
  /** Injectable so the authoring stamp is testable. */
  now?: Date
}

export function ReportForm({
  type,
  trailName,
  reporterType,
  location,
  poiId,
  onSubmit,
  onCancel,
  online = true,
  stewards = null,
  now,
}: ReportFormProps) {
  // Captured once, on mount - see the note above.
  const [authoredAt] = useState(() => now ?? new Date())
  const [note, setNote] = useState('')
  const [photo, setPhoto] = useState<Blob | null>(null)
  const [preparing, setPreparing] = useState(false)
  const [photoError, setPhotoError] = useState<string | null>(null)

  /**
   * Shrink and re-encode the picked file, or say why it cannot be sent.
   *
   * Clearing the previous photo before starting is deliberate: a second pick
   * that fails must not leave the first one silently attached, which would
   * send a photo the hiker believes they replaced.
   */
  const choosePhoto = async (file: File | null) => {
    setPhoto(null)
    setPhotoError(null)
    if (file === null) return

    setPreparing(true)
    try {
      setPhoto(await prepareReportPhoto(file))
    } catch (error) {
      // The message is written for a hiker to read (lib/reportPhoto.ts);
      // anything else that got this far is not, so it does not get shown.
      setPhotoError(
        error instanceof PhotoUnusable
          ? error.message
          : 'That photo could not be prepared. Try taking another.',
      )
    } finally {
      setPreparing(false)
    }
  }

  const isThanks = type === 'thanks'

  return (
    <main className="reporting">
      <h1 className="reporting__title">{TITLES[type]}</h1>

      {isThanks && stewards !== null && <p className="reporting__stewards">{stewards}</p>}

      <label className="reporting__field">
        <span className="reporting__field-label">
          {isThanks ? 'What made the difference?' : 'Note'}
        </span>
        <textarea
          className="reporting__note"
          value={note}
          rows={4}
          onChange={(event) => setNote(event.target.value)}
        />
      </label>

      {/* The photo field, working at last (#234).

          It was a real `<input type="file">` with no onChange and no state
          behind it, so a hiker photographing a washed-out bridge got a control
          that accepted the photo and a report that arrived without it. #89
          disabled it and said so rather than removing it, on the grounds that
          somebody who took a photo specifically to attach would otherwise
          wonder whether they had missed the button. This is the wiring that
          note was waiting for.

          The shrink happens HERE, on pick, rather than during a flush that may
          be days away with the phone in a pocket. That is the whole reason:
          the only failure a hiker can do anything about is "take another one",
          and they can only do that while still standing in front of the thing
          they photographed. */}
      <label className="reporting__field">
        <span className="reporting__field-label">Photo</span>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic"
          className="reporting__photo"
          onChange={(event) => void choosePhoto(event.target.files?.[0] ?? null)}
          aria-describedby={photoError === null ? undefined : 'photo-error'}
        />
        {preparing && (
          <span className="reporting__meta" role="status">
            Shrinking the photo…
          </span>
        )}
        {photoError !== null && (
          <span className="reporting__unavailable" id="photo-error" role="alert">
            {photoError}
          </span>
        )}
        {photo !== null && !preparing && (
          <span className="reporting__meta">
            {`Photo attached — ${Math.round(photo.size / 1024)} KB. Location and camera details are not included.`}
          </span>
        )}
      </label>

      <p className="reporting__meta">{describeLocation(location)}</p>

      <p className="reporting__meta">
        {`Signed as ${trailName ?? 'not set'} · ${reporterType}`}
      </p>

      {!online && (
        <p className="reporting__queued" role="status">
          No signal — this will wait in your outbox and sync later, keeping the time you
          wrote it.
        </p>
      )}

      <div className="reporting__actions">
        <button
          type="button"
          className="reporting__primary"
          // Disabled only while the shrink is running, and only then. A photo
          // that failed leaves the button live on purpose: the note is what
          // carries the report, and refusing to send it because the picture
          // did not work would lose the words over the image.
          disabled={preparing}
          onClick={() =>
            onSubmit({
              type,
              reporter_type: reporterType,
              // Present exactly when the report started from a place's card
              // - the anchor a re-measured mile cannot move (FIELD_NOTES.md
              // step 1). Spread so an unanchored report has no key at all.
              ...(poiId !== undefined ? { poi_id: poiId } : {}),
              note: note.trim() === '' ? undefined : note.trim(),
              // Both omitted rather than zeroed with no fix. The reports API
              // takes lat and lon as optional for exactly this case, and a
              // report pinned at 0,0 is not a report with a missing location -
              // it is a report at a confident, wrong place in the Atlantic.
              lat: location?.lat,
              lon: location?.lon,
              // The mile this form has been computing all along, and used to
              // throw away here (#244). It is the value the serious-warnings
              // banner filters on, and nothing server-side can re-derive it -
              // the backend holds no centerline. Same omitted-not-zeroed rule
              // as the coordinates: mi 0 is Springer Mountain, not "unknown".
              mile: location?.mile,
              authoredAt,
              ...(photo !== null ? { photo } : {}),
            })
          }
        >
          {online ? 'Send' : 'Save to outbox'}
        </button>
        <button type="button" className="reporting__secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </main>
  )
}
