// Who a report is signed by, and whether they may be asked for more (#1563,
// the maintainer's additions of 2026-09-17).
//
// TWO QUESTIONS, ONE BLOCK, ON EVERY SURFACE THAT FILES. The report window
// asks them on its receipt - after the tap, with the note, because under 1a
// nothing may stand between a hiker and the tile (features/REPORT_A_PROBLEM.md)
// - and the long form asks them above Send. Both surfaces render this, so the
// words and the order cannot drift.
//
// THE NAME IS A CHOICE, NOT A FIELD. A hiker has a trail name, which is the
// identity this app shows other people and the default here, and may give a
// real name to put behind a report they want a club to be able to follow up
// on by it. The choice is per report; the real name, once typed, is kept in
// the preferences so the next report offers it (lib/reporterSignature.ts).
// Neither is ever shown to other hikers - the server withholds both like
// `reporter_id` - and the hint under the block says so where the choice is
// made rather than in a policy nobody opens.
//
// THE DRAFT IS THE HOST'S. The real name being typed lives in the surface
// that renders this, not here, because that surface has to know it at
// moments this component never sees: the report window's Escape, which
// closes without a blur, and the long form's Send. `onRealNameSettle` is the
// blur, for the host to persist on; `onRealNameChange` is every keystroke,
// for the host's own state only (review of #1571).
//
// THE CONSENT IS A CHECKBOX AND NOTHING MORE. "You can contact me for more
// information" carries no address: the account is how a club reaches them,
// and an unticked box is a no.

import { SIGNED_NAME_MAX_CHARS } from '../lib/outbox'
import { signatureWords, type SignedAs } from '../lib/reporterSignature'
import type { ReporterType } from '../lib/userPreferences'
import './reporterDetails.css'

export interface ReporterDetailsProps {
  /** The trail name from the preferences, or null where none is set. */
  trailName: string | null
  signedAs: SignedAs
  onSignedAs: (kind: SignedAs) => void
  /** The real name as typed so far - the host's draft, seeded from the
   *  preference. Trimmed and empty is no name. */
  realName: string
  onRealNameChange: (value: string) => void
  /** The field was left. The host persists the draft here; a keystroke is
   *  not a preference write, and a preference write is a sync. */
  onRealNameSettle: () => void
  contactOk: boolean
  onContactOk: (ok: boolean) => void
  /** The kind of hiker the report is signed as - the one attribution other
   *  hikers do see. Printed in the summary so the whole signature is in one
   *  sentence. */
  reporterType: ReporterType
  /** Groups the radios apart from any other set on the same screen. */
  name?: string
}

export function ReporterDetails({
  trailName,
  signedAs,
  onSignedAs,
  realName,
  onRealNameChange,
  onRealNameSettle,
  contactOk,
  onContactOk,
  reporterType,
  name = 'signed-as',
}: ReporterDetailsProps) {
  const typed = realName.trim() === '' ? null : realName.trim()
  const shown = { kind: signedAs, name: signedAs === 'real' ? typed : trailName }

  return (
    <fieldset className="reporter-details" data-testid="reporter-details">
      <legend className="reporter-details__legend">Signed as</legend>
      {/* The whole signature in one sentence, which is what the old static
          line said and what the tests and the flow spec read. */}
      <p className="reporter-details__summary" data-testid="report-signature">
        {`Signed as ${signatureWords(shown)} · ${reporterType}`}
      </p>

      <label className="reporter-details__choice">
        <input
          type="radio"
          name={name}
          value="trail"
          checked={signedAs === 'trail'}
          onChange={() => onSignedAs('trail')}
        />
        <span>
          <span className="reporter-details__choice-label">Trail name</span>
          <span className="reporter-details__meta">{trailName ?? 'not set'}</span>
        </span>
      </label>
      <label className="reporter-details__choice">
        <input
          type="radio"
          name={name}
          value="real"
          checked={signedAs === 'real'}
          onChange={() => onSignedAs('real')}
        />
        <span>
          <span className="reporter-details__choice-label">Real name</span>
          <span className="reporter-details__meta">
            {typed ?? 'not set — type it below'}
          </span>
        </span>
      </label>
      {signedAs === 'real' && (
        <label className="reporter-details__name">
          <span className="reporter-details__meta">Your name</span>
          <input
            type="text"
            className="reporter-details__input"
            data-testid="reporter-real-name"
            value={realName}
            maxLength={SIGNED_NAME_MAX_CHARS}
            autoComplete="name"
            onChange={(event) => onRealNameChange(event.target.value)}
            onBlur={onRealNameSettle}
          />
        </label>
      )}

      <label className="reporter-details__contact">
        <input
          type="checkbox"
          data-testid="reporter-contact-ok"
          checked={contactOk}
          onChange={(event) => onContactOk(event.target.checked)}
        />
        You can contact me for more information
      </label>

      <p className="reporter-details__hint">
        Only the club moderators who read this report see the name and this answer. Other
        hikers see what kind of hiker you are, and nothing else.
      </p>
    </fieldset>
  )
}
