// A serious warning's detail sheet (WIREFRAMES.md §8).
//
// Three things here are deliberate rather than decorative:
//
// **The corroboration sentence.** A serious warning is a strong claim, and
// showing what it rests on ("several separate reports over four days") is
// what lets a hiker weigh it instead of taking it on faith.
//
// **Reporter names are withheld for anything about a person.** Naming who
// reported being followed could expose them to the person they reported. The
// sheet says the name is withheld rather than silently omitting it, so the
// absence reads as a decision rather than missing data.
//
// **It explains why the phone stayed silent.** Someone reading a serious
// warning for the first time will reasonably wonder why they were not
// notified; an app that leaves that unanswered invites the conclusion that
// notifications are broken - worse than the silence. Saying it plainly makes
// the one-notification policy legible instead of something to infer.

export interface SeriousWarning {
  id: string
  type: string
  note: string
  mile: number
  confirmedAt: Date
  corroboration: string
  aboutAPerson: boolean
  reporterName: string | null
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

      <p className="closure-sheet__meta">{warning.corroboration}</p>

      <p className="closure-sheet__meta">
        {warning.aboutAPerson
          ? 'Reporter name withheld — this warning is about a person.'
          : `Reported by ${warning.reporterName ?? 'a hiker'}`}
      </p>

      <p className="closure-sheet__limit" role="note">
        Your phone didn&rsquo;t buzz for this. OurHike only ever sends one kind of
        notification — the wrong-way alert — so warnings appear here on the map instead.
      </p>
    </div>
  )
}
