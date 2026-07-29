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
import './reporting.css'

export type ReportFormType = ReportDraft['type']

const TITLES: Record<ReportFormType, string> = {
  blowdown: 'Blow down',
  flooding: 'Flooding',
  trash: 'Trash',
  shelter_repair: 'Shelter repair',
  animals: 'Animals',
  bad_hikers: 'Something unsafe happened',
  thanks: 'Say thanks',
}

export interface ReportFormLocation {
  lat: number
  lon: number
  mile: number
}

export interface ReportFormSubmission extends ReportDraft {
  authoredAt: Date
}

export interface ReportFormProps {
  type: ReportFormType
  trailName: string | null
  reporterType: ReportDraft['reporter_type']
  location: ReportFormLocation
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
  onSubmit,
  onCancel,
  online = true,
  stewards = null,
  now,
}: ReportFormProps) {
  // Captured once, on mount - see the note above.
  const [authoredAt] = useState(() => now ?? new Date())
  const [note, setNote] = useState('')

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

      <label className="reporting__field">
        <span className="reporting__field-label">Photo</span>
        <input type="file" accept="image/*" className="reporting__photo" />
      </label>

      <p className="reporting__meta">
        {`mi ${location.mile.toLocaleString('en-US', {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1,
        })}`}
      </p>

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
          onClick={() =>
            onSubmit({
              type,
              reporter_type: reporterType,
              note: note.trim() === '' ? undefined : note.trim(),
              lat: location.lat,
              lon: location.lon,
              authoredAt,
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
