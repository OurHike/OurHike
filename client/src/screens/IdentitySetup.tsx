// Trail name and reporter type, asked once, straight after sign-in
// (WIREFRAMES.md §6).
//
// Maintainer is selectable by anyone. It is deliberately NOT gated in the
// interface, because a UI gate would be security theatre - the real control
// is that the claim means nothing until a club confirms it. What the screen
// owes someone is honesty about that, so nobody walks away believing they
// have just granted themselves standing they do not have.

import { useState } from 'react'
import { REPORTER_TYPES } from '../lib/contributionFlow'
import type { ReportDraft } from '../lib/outbox'

export interface IdentitySetupProps {
  onSave: (identity: {
    trailName: string
    reporterType: ReportDraft['reporter_type']
  }) => void
  onSkip: () => void
}

export function IdentitySetup({ onSave, onSkip }: IdentitySetupProps) {
  const [trailName, setTrailName] = useState('')
  const [reporterType, setReporterType] = useState<ReportDraft['reporter_type']>('thru')

  const selected = REPORTER_TYPES.find((r) => r.id === reporterType)

  return (
    <main className="reporting">
      <h1 className="reporting__title">How should reports be signed?</h1>

      <label className="reporting__field">
        <span className="reporting__field-label">Trail name</span>
        <input
          type="text"
          className="reporting__input"
          value={trailName}
          onChange={(event) => setTrailName(event.target.value)}
        />
      </label>

      <fieldset className="detail-picker">
        <legend className="detail-picker__legend">Reporter type</legend>
        {REPORTER_TYPES.map((option) => (
          <label key={option.id} className="detail-picker__option">
            <input
              type="radio"
              name="reporter-type"
              value={option.id}
              checked={reporterType === option.id}
              onChange={() => setReporterType(option.id)}
            />
            <span className="detail-picker__name">{option.label}</span>
          </label>
        ))}
      </fieldset>

      {selected?.clubGranted && (
        <p className="reporting__limit" role="note">
          Maintainer stays unverified until a club confirms it. You can still report
          everything else in the meantime.
        </p>
      )}

      <div className="reporting__actions">
        <button
          type="button"
          className="reporting__primary"
          onClick={() => onSave({ trailName, reporterType })}
        >
          Save
        </button>
        <button type="button" className="reporting__secondary" onClick={onSkip}>
          Skip for now
        </button>
      </div>
    </main>
  )
}
