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
// THE CONSENT IS A CHECKBOX AND NOTHING MORE. "You can contact me for more
// information" carries no address: the account is how a club reaches them,
// and an unticked box is a no.

import { useState } from 'react'
import { SIGNED_NAME_MAX_CHARS } from '../lib/outbox'
import { signatureWords, type SignedAs } from '../lib/reporterSignature'
import type { ReporterType } from '../lib/userPreferences'
import './reporterDetails.css'

export interface ReporterDetailsProps {
  /** The two names on offer, from the preferences - null where none is set. */
  names: Record<SignedAs, string | null>
  signedAs: SignedAs
  onSignedAs: (kind: SignedAs) => void
  /** Keep a real name the hiker types here. Called when the field is left,
   *  not per keystroke: it is a preference write, and a sync. */
  onRealName: (name: string) => void
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
  names,
  signedAs,
  onSignedAs,
  onRealName,
  contactOk,
  onContactOk,
  reporterType,
  name = 'signed-as',
}: ReporterDetailsProps) {
  // Typed here, kept on blur. Local so a keystroke is not a preference write.
  const [realNameDraft, setRealNameDraft] = useState(names.real ?? '')
  const shown = {
    kind: signedAs,
    name:
      signedAs === 'real'
        ? realNameDraft.trim() === ''
          ? null
          : realNameDraft.trim()
        : names.trail,
  }

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
          <span className="reporter-details__meta">{names.trail ?? 'not set'}</span>
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
            {names.real ?? 'not set — type it below'}
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
            value={realNameDraft}
            maxLength={SIGNED_NAME_MAX_CHARS}
            autoComplete="name"
            onChange={(event) => setRealNameDraft(event.target.value)}
            onBlur={() => onRealName(realNameDraft)}
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
