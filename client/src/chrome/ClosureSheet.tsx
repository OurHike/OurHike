// The closure tap sheet (WIREFRAMES.md §7).
//
// Two things here are not optional detail:
//
// **It says OurHike does not compute detours.** Staying quiet invites the
// assumption that the app is routing around the closure - the one wrong
// belief that could put someone somewhere worse than the closed trail. So it
// is stated, and there is deliberately no route/detour control to imply
// otherwise.
//
// **The sync age lives on the closure itself**, not only in the global status
// strip. A downloaded map is at its most dangerous when it is stale precisely
// about closures: the trail may have reopened, or far worse, closed since
// this copy was made. That is a fact about THIS closure, so it is shown here.

import { closureReasonLabel, type Closure } from '../lib/closureBanner'
import { syncAgeLabel } from '../lib/syncAge'

// The three extras beyond the shared `Closure` shape, each backed by a
// column as of #245. They were four; `marked_by` is gone.
//
// It rendered as "Marked by <name>", and the only sources for that name were
// `verified_by`/`reported_by` - profile ids, whose display names live behind
// `/profiles` and an anonymity position that is stored and not yet applied
// (#252). The other three are facts about the closure; this one was a fact
// about a person, and the app has not settled when it shows those. A field
// nothing can fill is a quiet lie the type system exists to prevent, and of
// the two ways to end it, deleting is the reversible one.
export interface ClosureDetail extends Closure {
  closed_since: Date | null
  expected_reopen: Date | null
  reroute_url: string | null
}

export interface ClosureSheetProps {
  closure: ClosureDetail
  lastSyncedAt: Date | null
  onClose: () => void
  now?: Date
}

const STATUS_WORDS: Record<Closure['status'], string> = {
  open: 'Open again',
  closed: 'Closed',
  reroute_available: 'Closed · reroute available',
}

function longDate(value: Date): string {
  return value.toLocaleDateString('en-US', {
    month: 'long',
    day: 'numeric',
    timeZone: 'UTC',
  })
}

function mile(value: number): string {
  return value.toLocaleString('en-US', {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })
}

export function ClosureSheet({
  closure,
  lastSyncedAt,
  onClose,
  now = new Date(),
}: ClosureSheetProps) {
  return (
    <div className="closure-sheet" role="dialog" aria-label="Trail closure">
      <div className="legend__head">
        <h2 className="legend__title">{closureReasonLabel(closure.reason_type)}</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <p className="closure-sheet__status">{STATUS_WORDS[closure.status]}</p>

      <p className="closure-sheet__range">
        {`mi ${mile(closure.start_mile_marker)} – ${mile(closure.end_mile_marker)}`}
      </p>

      {closure.note !== null && <p className="closure-sheet__note">{closure.note}</p>}

      {closure.closed_since !== null && (
        <p className="closure-sheet__meta">{`Closed since ${longDate(closure.closed_since)}`}</p>
      )}

      {/* Omitted rather than guessed - "expected reopen: unknown" reads as a
          promise nobody made. */}
      {closure.expected_reopen !== null && (
        <p className="closure-sheet__meta">
          {`Expected to reopen ${longDate(closure.expected_reopen)}`}
        </p>
      )}

      {closure.reroute_url !== null && (
        <a
          className="closure-sheet__link"
          href={closure.reroute_url}
          target="_blank"
          rel="noreferrer"
        >
          The club&rsquo;s reroute notice
        </a>
      )}

      <p className="closure-sheet__limit" role="note">
        OurHike does not work out detours. Follow the club&rsquo;s notice, or the signage
        on the ground.
      </p>

      <p className="closure-sheet__age">
        {`Your copy of this closure is ${syncAgeLabel(lastSyncedAt, now)}.`}
      </p>
    </div>
  )
}
