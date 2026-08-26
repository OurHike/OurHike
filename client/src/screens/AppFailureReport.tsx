// "It broke while I was out there" - the report a hiker files when this
// software failed them on the trail (#848, features/APP_FAILURE_REPORTS.md).
//
// A SCREEN AND NOT A FIFTH LINK, WHICH IS THE WHOLE POINT. The four options
// in ReportBug.tsx are `<a href>`s into GitHub issue forms, and that file
// says plainly what is wrong with them here: "Each of these opens GitHub in
// your browser, so they need signal." The app failing while somebody
// navigates by it is, nearly always, the offline path failing - so the one
// report this project should most want to receive is the one its bug page
// could not accept. This queues in the same outbox a blowdown does and goes
// when the signal comes back.
//
// THE CONTACT FIELD IS WHY IT CANNOT GO WHERE THE OTHER FOUR GO. A GitHub
// issue is public and permanent. lib/bugReport.ts already declines to attach
// `navigator.userAgent` to one on the grounds that the device "is a fact
// about them"; an email address is a much stronger one. So this goes to the
// backend's own private table instead, and the form says so where the field
// is rather than in a policy nobody opens.
//
// WHAT IS ASKED RATHER THAN TAKEN. No GPS fix is attached, though the app has
// one and it would be more precise than anything typed. Same rule as above:
// where they were is a fact about them. The build and whether the phone was
// offline ARE attached, because those are facts about our software and its
// conditions - and bug_report.yml already asks for the second one in words.
//
// THE ACKNOWLEDGEMENT IS PART OF THE FEATURE, not politeness. This form asks
// somebody who has just been frightened to type, and the least it owes them
// is to say what happens next - including, when they left no contact, that
// nothing will, because a reply they are waiting for and never get is worse
// than being told plainly there will not be one.
//
// AND IT WAITS FOR THE SAVE, which is the same rule one step further down. The
// queue lives in IndexedDB and writing to it can genuinely fail - a phone with
// no space left is a real state in this app, which is why lib/storageHealth.ts
// exists - so an acknowledgement rendered before the write resolves would tell
// a hiker their report was kept at the exact moment it was not. It says so
// instead, and tells them to write it down somewhere else, because that is the
// only thing left that keeps the words.

import { useState } from 'react'
import {
  APP_FAILURE_MAX_CHARS,
  APP_FAILURE_SHORT_MAX_CHARS,
  type AppFailureDraft,
  type AppFailureHarm,
} from '../lib/outbox'
import { BUILD_INFO, buildSummary, type BuildInfo } from '../lib/buildInfo'
import './reporting.css'

/**
 * The four ways CLAUDE.md says this app can hurt somebody, in the words a
 * hiker would use rather than the tokens the wire carries.
 *
 * Offered as checkboxes rather than a required single choice for two
 * reasons: they co-occur - being lost is how you end up out of water - and a
 * required question is a way of turning somebody away who does not want to
 * answer it. Ticking none is a complete report.
 */
const HARMS: readonly { id: AppFailureHarm; label: string }[] = [
  { id: 'lost', label: 'I didn’t know where I was' },
  { id: 'water', label: 'I ran out of water, or nearly did' },
  { id: 'hazard', label: 'I was in front of something dangerous' },
  { id: 'stranded', label: 'I couldn’t get off the trail quickly' },
]

export interface AppFailureReportProps {
  /**
   * Queues the report. Called once, from the one button that files it.
   *
   * Awaited, and a rejection is shown rather than swallowed: the
   * acknowledgement below is a claim that the words are kept, and it may only
   * be made once something has actually kept them.
   */
  onSubmit: (draft: AppFailureDraft, authoredAt: Date) => void | Promise<void>
  onClose: () => void
  /** Whether the phone has signal. Travels with the report as `was_offline`,
   *  and words both the button and the acknowledgement. */
  online?: boolean
  /** Injectable for the reason AboutBuild.tsx gives: the real value is a live
   *  commit, so a test asserting on it would be asserting on when it ran. */
  build?: BuildInfo
  /** Injectable so the authoring stamp is testable. */
  now?: Date
}

export function AppFailureReport({
  onSubmit,
  onClose,
  online = true,
  build = BUILD_INFO,
  now,
}: AppFailureReportProps) {
  // Captured at MOUNT, not at submit, for the reason ReportForm.tsx gives:
  // somebody can start this, walk on, and finish it twenty minutes later,
  // and what matters is when the thing happened.
  const [authoredAt] = useState(() => now ?? new Date())
  const [whatHappened, setWhatHappened] = useState('')
  const [whereabouts, setWhereabouts] = useState('')
  const [contact, setContact] = useState('')
  const [harms, setHarms] = useState<AppFailureHarm[]>([])
  const [filed, setFiled] = useState<{ withContact: boolean } | null>(null)
  const [filing, setFiling] = useState(false)
  const [failedToSave, setFailedToSave] = useState(false)

  const toggleHarm = (harm: AppFailureHarm) =>
    setHarms((current) =>
      current.includes(harm) ? current.filter((one) => one !== harm) : [...current, harm],
    )

  const trimmed = {
    whatHappened: whatHappened.trim(),
    whereabouts: whereabouts.trim(),
    contact: contact.trim(),
  }

  const file = async () => {
    setFiling(true)
    setFailedToSave(false)
    try {
      await onSubmit(
        {
          what_happened: trimmed.whatHappened,
          // Omitted rather than sent empty. An empty string is a claim that
          // they answered and had nothing to say; absent is the truth.
          ...(trimmed.whereabouts === '' ? {} : { whereabouts: trimmed.whereabouts }),
          ...(trimmed.contact === '' ? {} : { contact: trimmed.contact }),
          harms,
          build: buildSummary(build),
          was_offline: !online,
        },
        authoredAt,
      )
      setFiled({ withContact: trimmed.contact !== '' })
    } catch {
      // The form is left exactly as it was, with everything still in it, so
      // the one thing a hiker can do about this - copy the words somewhere
      // else - is still possible. Nothing is cleared on a failure.
      setFailedToSave(true)
    } finally {
      setFiling(false)
    }
  }

  if (filed !== null) {
    return (
      <main className="reporting">
        <h1 className="reporting__title">Thank you — that is saved</h1>

        <p className="reporting__stewards" role="status">
          {online
            ? 'It is on its way to the people who maintain OurHike.'
            : 'No signal, so it is waiting in your outbox. It will send itself the next time this phone has one, keeping the time you wrote it.'}
        </p>

        {/* Said plainly, both ways. A reply somebody is waiting for and never
            gets is worse than being told there will not be one. */}
        <p className="reporting__queued">
          {filed.withContact
            ? 'Somebody will get back to you using what you left. It may take a few days.'
            : 'You didn’t leave a way to reach you, so nobody can reply. The report still helps — it’s the part we can’t get any other way.'}
        </p>

        <div className="reporting__actions">
          <button type="button" className="reporting__primary" onClick={onClose}>
            Done
          </button>
        </div>
      </main>
    )
  }

  return (
    <main className="reporting">
      <h1 className="reporting__title">It broke while I was out there</h1>

      <p className="reporting__queued">
        The app failing while you are relying on it is not an ordinary bug, and this is
        not the ordinary form. It comes straight to the people who maintain OurHike rather
        than to the public issue tracker.
      </p>

      <label className="reporting__field">
        <span className="reporting__field-label">What happened?</span>
        <textarea
          className="reporting__note"
          value={whatHappened}
          rows={6}
          maxLength={APP_FAILURE_MAX_CHARS}
          placeholder="What the app did, and what you were trying to do at the time."
          onChange={(event) => setWhatHappened(event.target.value)}
        />
      </label>

      <label className="reporting__field">
        <span className="reporting__field-label">Where were you, and when?</span>
        <input
          type="text"
          className="reporting__input"
          value={whereabouts}
          maxLength={APP_FAILURE_SHORT_MAX_CHARS}
          placeholder="A mile, a shelter, a road crossing — whatever you have."
          onChange={(event) => setWhereabouts(event.target.value)}
        />
      </label>

      <label className="reporting__field">
        <span className="reporting__field-label">How can we reach you?</span>
        <input
          type="text"
          className="reporting__input"
          value={contact}
          maxLength={APP_FAILURE_SHORT_MAX_CHARS}
          placeholder="An email, a phone number, however you would rather."
          onChange={(event) => setContact(event.target.value)}
        />
        {/* Where the field is, not in a policy nobody opens. */}
        <span className="reporting__unavailable">
          Only the people who maintain OurHike see this. It never goes on the public issue
          tracker, and nothing else in the app uses it.
        </span>
      </label>

      <fieldset className="reporting__field reporting__checks">
        <legend className="reporting__field-label">
          Did it come close to any of these?
        </legend>
        {HARMS.map((harm) => (
          <label key={harm.id} className="reporting__check">
            <input
              type="checkbox"
              checked={harms.includes(harm.id)}
              onChange={() => toggleHarm(harm.id)}
            />
            {harm.label}
          </label>
        ))}
        <span className="reporting__unavailable">
          None of them is a complete answer. This only decides what gets read first.
        </span>
      </fieldset>

      {/* What travels without being typed, said out loud. A hiker should not
          have to guess what an app attaches on their behalf. */}
      <p className="reporting__meta">
        {`Attached: ${buildSummary(build)} · ${online ? 'had signal' : 'no signal'}`}
      </p>
      <p className="reporting__unavailable">
        Your location is not attached. If where you were matters, it is the box above.
      </p>

      {!online && (
        <p className="reporting__queued" role="status">
          No signal — this will wait in your outbox and send later, keeping the time you
          wrote it. You do not need an account.
        </p>
      )}

      {failedToSave && (
        <p className="reporting__error" role="alert">
          This phone could not save the report — it may be out of space. Your words are
          still in the boxes above; copy them somewhere else before you leave this screen,
          because nothing here is keeping them.
        </p>
      )}

      <div className="reporting__actions">
        <button
          type="button"
          className="reporting__primary"
          // The only thing that can hold this back. Everything else on the
          // form is optional, and a report with nothing in this box is not a
          // report - there is nothing to store and nothing to act on.
          disabled={trimmed.whatHappened === '' || filing}
          onClick={() => void file()}
        >
          {online ? 'Send' : 'Save to outbox'}
        </button>
        <button type="button" className="reporting__secondary" onClick={onClose}>
          Cancel
        </button>
      </div>
    </main>
  )
}
