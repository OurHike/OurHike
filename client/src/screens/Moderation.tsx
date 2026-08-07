// The moderation queue, which until now existed only as HTTP (#235).
//
// `moderation.py` has been able to list and act on everything waiting since
// #230, and `require_role(maintainer, club_admin)` has gated it the whole
// time. What did not exist was anywhere for a person to do it, which made the
// queue four endpoints somebody would have to reach with curl - and made
// `internal_only` a routing decision with no destination. This is the
// destination.
//
// WHY `bad_hikers` IS NOT A ROW IN THE SAME LIST
//
// #235 asks for this specifically, and the reason is worth keeping next to
// the code rather than in the issue: a `bad_hikers` report is about a PERSON.
// Everything else in this queue is about the trail. A screen that renders the
// two identically has quietly decided they are the same kind of decision, and
// REPORT_A_PROBLEM.md asks for a real conversation before that ships.
//
// So they get their own section, first, named for what they are. What this
// deliberately does NOT do is filter them out: the backend's queue includes
// them on purpose, because `internal_only` names exactly this audience, and a
// client that dropped them would re-open the hole #230 closed - a report
// about being followed on trail reaching nobody at all.
//
// Two questions stay open and are said out loud on screen rather than
// answered by omission: which club a `bad_hikers` report should route to
// (REPORT_A_PROBLEM.md's own open question), and how much corroboration
// should be wanted before escalating one (HIKER_SAFETY.md §1 calls that
// moderation policy, not a data-model question). This screen shows one
// club's worth of queue to any maintainer, which is what the backend does.
//
// WHY THERE IS NO SEVERITY DEFAULT
//
// Verify sends `severity` only when the moderator picked one (#251). An
// omitted field means "said nothing"; an explicit `normal` is a
// de-escalation, and sending one by default would silently clear the
// `serious` flag that puts a warning pin on every phone on the trail.

import { useCallback, useEffect, useState } from 'react'
import {
  dismissClosure,
  dismissReport,
  fetchModerationQueue,
  verifyClosure,
  verifyReport,
  type ModerationQueue,
  type QueuedClosure,
  type QueuedReport,
} from '../lib/api'
import './moderation.css'

export interface ModerationProps {
  onClose: () => void
}

/** How long ago, in the coarsest unit that is still useful.
 *
 *  Age is the field that says whether the queue is being kept up with, and a
 *  moderator reading "3d" knows something a timestamp does not tell them at a
 *  glance. Minutes below an hour, hours below a day, days after that. */
export function ageOf(iso: string, now: Date = new Date()): string {
  const minutes = Math.floor((now.getTime() - new Date(iso).getTime()) / 60000)
  if (!Number.isFinite(minutes) || minutes < 0) return 'just now'
  if (minutes < 60) return `${minutes}m`
  if (minutes < 60 * 24) return `${Math.floor(minutes / 60)}h`
  return `${Math.floor(minutes / (60 * 24))}d`
}

/** Where a report happened, in the words the form used - see ReportForm's
 *  `describeLocation` for why 0,0 is never a stand-in for "unknown". */
function placeOf(report: QueuedReport): string {
  if (report.poi_id !== null) return `at ${report.poi_id}`
  if (report.lat === null || report.lon === null) return 'no location'
  return `${report.lat.toFixed(4)}, ${report.lon.toFixed(4)}`
}

const TYPE_WORDS: Record<string, string> = {
  blowdown: 'Blow down',
  flooding: 'Flooding',
  trash: 'Trash',
  shelter_repair: 'Shelter repair',
  animals: 'Animals',
  invasive_species: 'Invasive species',
  bad_hikers: 'Someone unsafe',
}

export function Moderation({ onClose }: ModerationProps) {
  const [queue, setQueue] = useState<ModerationQueue | null>(null)
  // Three states, not two. An empty queue and a queue that could not be read
  // draw the same screen and mean opposite things - and here the wrong one
  // says there are no unreviewed safety reports.
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      setQueue(await fetchModerationQueue(signal))
      setFailed(false)
    } catch {
      setFailed(true)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void load(controller.signal)
    return () => controller.abort()
  }, [load])

  /** Acts, then re-reads rather than patching the list in place.
   *
   *  A second moderator working the same queue is the ordinary case for a
   *  club, so what this screen believes is waiting goes stale the moment
   *  somebody else verifies something. Re-reading costs one request and is
   *  the difference between an empty row and a 404 on the next click. */
  const act = async (id: string, action: () => Promise<void>) => {
    setBusy(id)
    try {
      await action()
      await load()
    } catch {
      setFailed(true)
    } finally {
      setBusy(null)
    }
  }

  const reportRow = (report: QueuedReport) => (
    <li key={report.id} className="moderation__item">
      <p className="moderation__headline">
        <span className="moderation__type">{TYPE_WORDS[report.type] ?? report.type}</span>
        <span className="moderation__meta">
          {`${report.reporter_type} · ${placeOf(report)} · ${ageOf(report.timestamp)}`}
        </span>
      </p>
      {report.note !== null && <p className="moderation__note">{report.note}</p>}
      {report.photo_url !== null && (
        // Named, not shown, and that is a gap rather than a design - see the
        // note at the foot of this file. Saying a photo exists is still worth
        // more than silence: a moderator who knows there is evidence they
        // cannot see yet can wait for it rather than deciding without it.
        <p className="moderation__attachment">
          Has a photo, which this screen cannot show yet.
        </p>
      )}
      <div className="moderation__actions">
        <button
          type="button"
          disabled={busy === report.id}
          onClick={() => void act(report.id, () => verifyReport(report.id))}
        >
          Confirm
        </button>
        <button
          type="button"
          disabled={busy === report.id}
          onClick={() => void act(report.id, () => verifyReport(report.id, 'serious'))}
        >
          Confirm as serious
        </button>
        <button
          type="button"
          className="moderation__dismiss"
          disabled={busy === report.id}
          onClick={() => void act(report.id, () => dismissReport(report.id))}
        >
          Dismiss
        </button>
      </div>
    </li>
  )

  const closureRow = (closure: QueuedClosure) => (
    <li key={closure.id} className="moderation__item">
      <p className="moderation__headline">
        <span className="moderation__type">{closure.reason_type}</span>
        <span className="moderation__meta">
          {`mi ${closure.start_mile_marker}–${closure.end_mile_marker} · ${ageOf(closure.reported_at)}`}
        </span>
      </p>
      {closure.note !== null && <p className="moderation__note">{closure.note}</p>}
      <div className="moderation__actions">
        <button
          type="button"
          disabled={busy === closure.id}
          onClick={() => void act(closure.id, () => verifyClosure(closure.id))}
        >
          Publish closure
        </button>
        <button
          type="button"
          className="moderation__dismiss"
          disabled={busy === closure.id}
          onClick={() => void act(closure.id, () => dismissClosure(closure.id))}
        >
          Dismiss
        </button>
      </div>
    </li>
  )

  if (failed) {
    return (
      <main className="moderation">
        <h1>Moderation queue</h1>
        <p role="alert" className="moderation__failed">
          The queue could not be read, so this is not a list of nothing waiting — it is no
          answer at all. Check the connection and try again.
        </p>
        <button type="button" onClick={() => void load()}>
          Try again
        </button>
        <button type="button" onClick={onClose}>
          Back to the map
        </button>
      </main>
    )
  }

  if (queue === null) {
    return (
      <main className="moderation">
        <h1>Moderation queue</h1>
        <p role="status">Reading the queue…</p>
      </main>
    )
  }

  const people = queue.reports.filter((report) => report.type === 'bad_hikers')
  const trail = queue.reports.filter((report) => report.type !== 'bad_hikers')

  return (
    <main className="moderation">
      <h1>Moderation queue</h1>

      <section className="moderation__section moderation__section--people">
        <h2>About a person</h2>
        <p className="moderation__preamble">
          These are incident notes about people, not trail conditions. They are kept out
          of the list below on purpose. Every maintainer sees every one of these: which
          club a report should reach, and how much corroboration to want before marking
          one serious, are both still undecided.
        </p>
        {people.length === 0 ? (
          <p className="moderation__empty">Nothing waiting.</p>
        ) : (
          <ul className="moderation__list">{people.map(reportRow)}</ul>
        )}
      </section>

      <section className="moderation__section">
        <h2>Trail conditions</h2>
        {trail.length === 0 ? (
          <p className="moderation__empty">Nothing waiting.</p>
        ) : (
          <ul className="moderation__list">{trail.map(reportRow)}</ul>
        )}
      </section>

      <section className="moderation__section">
        <h2>Closures</h2>
        {queue.closures.length === 0 ? (
          <p className="moderation__empty">Nothing waiting.</p>
        ) : (
          <ul className="moderation__list">{queue.closures.map(closureRow)}</ul>
        )}
      </section>

      <button type="button" onClick={onClose}>
        Back to the map
      </button>
    </main>
  )
}

// WHY THE PHOTO IS NAMED RATHER THAN SHOWN
//
// `GET /reports/{id}/photo` exists and works (#234), and an `<img src>`
// pointed at it would render the photo on a public, verified report. It would
// fail on exactly the reports this screen exists for.
//
// An `<img>` cannot carry an `Authorization` header, and the endpoint answers
// an anonymous caller with the PUBLIC answer - so an `internal_only`
// `bad_hikers` photo comes back 404 and renders as a broken image. The two
// cases would look identical to a moderator: no photo, and a photo they are
// not being shown.
//
// Doing it properly means fetching the bytes with the token and rendering an
// object URL, which works - and drags in a deployment step nobody has taken
// yet, because the redirect lands on a presigned R2 URL and a cross-origin
// `fetch` of it needs CORS on the photo bucket (LAUNCH_CHECKLIST 1.4 covers
// that for the published bucket only). That is its own change with its own
// checklist entry, not something to bolt onto a queue screen.
