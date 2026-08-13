// A serious warning's detail sheet (WIREFRAMES.md §8).
//
// Two things here are deliberate rather than decorative:
//
// **The confirmation date.** A serious warning is a strong claim, and a hiker
// weighing one is entitled to know when somebody stood behind it. It is
// backed by `verified_at`, stamped when a moderator confirms the report.
//
// **It explains why the phone stayed silent.** Someone reading a serious
// warning for the first time will reasonably wonder why they were not
// notified; an app that leaves that unanswered invites the conclusion that
// notifications are broken - worse than the silence. Saying it plainly makes
// the one-notification policy legible instead of something to infer.
//
// It used to say two more things, and #292 removed both. The shape below is
// what a backend can actually fill.
//
// **The corroboration sentence** ("several separate reports over four days")
// rested on a count that does not exist and cannot be derived - the issue's
// own words, "no field, and no count exists to derive one from". Producing
// one means designing a corroboration model, which HIKER_SAFETY.md §1 calls
// "real moderation policy, not a data-model question" and defers to #235.
// With no source, the two options were a hard-coded string - a fabricated
// evidence claim, on a safety warning about a named person - or a blank
// where the justification should be. Nothing honest is left to render.
//
// **The reporter attribution** went the way `marked_by` went off the closure
// sheet in #245, for the same reason and with the same precedent: it was a
// fact about a person, the only sources for the name were profile ids behind
// `/profiles`, and #252 closed by removing reporter identity from the public
// read path entirely. Note what that changes about the old "name withheld -
// this warning is about a person" line: identity is now withheld from EVERY
// report, so a sentence explaining why THIS one is anonymous implies the
// others are named. It was true when written and is misdirection now.

export interface SeriousWarning {
  id: string
  type: string
  note: string
  mile: number
  confirmedAt: Date
}

export interface SeriousWarningSheetProps {
  warning: SeriousWarning
  onClose: () => void
}

export function SeriousWarningSheet({ warning, onClose }: SeriousWarningSheetProps) {
  return (
    <div className="warning-sheet" role="dialog" aria-label="Serious warning">
      <div className="legend__head">
        <h2 className="legend__title">Serious warning</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <p className="warning-sheet__badge">
        {`Confirmed by club moderators · ${warning.confirmedAt.toLocaleDateString(
          'en-US',
          {
            month: 'long',
            day: 'numeric',
            timeZone: 'UTC',
          },
        )}`}
      </p>

      <p className="closure-sheet__range">
        {`mi ${warning.mile.toLocaleString('en-US', {
          minimumFractionDigits: 1,
          maximumFractionDigits: 1,
        })}`}
      </p>

      <p className="warning-sheet__note">{warning.note}</p>

      <p className="closure-sheet__limit" role="note">
        Your phone didn&rsquo;t buzz for this. OurHike only ever sends one kind of
        notification — the wrong-way alert — so warnings appear here on the map instead.
      </p>
    </div>
  )
}
