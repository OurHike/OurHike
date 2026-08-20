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
  ApiError,
  dismissClosure,
  dismissPhoto,
  dismissReport,
  fetchModerationQueue,
  fetchPhotoQueue,
  fetchReportPhotoLink,
  pinPhoto,
  reviewPhoto,
  unpinPhoto,
  verifyClosure,
  verifyReport,
  type ModerationQueue,
  type PoiPhotoQueueEntry,
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

/** The photo a moderator is deciding on (#385).
 *
 *  **The one thing this must never do is draw nothing.** `<img src>` pointed
 *  at `/reports/{id}/photo` cannot carry the token, so the request goes out
 *  anonymous, an `internal_only` photo comes back 404, and the moderator sees
 *  a broken image identical to a report with no photo. Every branch here
 *  either shows the image or says in words why it is not showing it.
 *
 *  So the URL is asked for over an authenticated `fetch`
 *  (`fetchReportPhotoLink`) and handed to `src`. Images are exempt from CORS,
 *  which is why nothing had to change on the private bucket.
 *
 *  WHY A REPORT ABOUT A PERSON IS NOT SHOWN UNTIL IT IS ASKED FOR
 *
 *  #385 leaves this open and it is the same kind of question as the two this
 *  section already says out loud: a `bad_hikers` photo is a photo of a
 *  PERSON, and a queue that renders twenty of them as thumbnails has decided
 *  a moderator scrolling past is the same act as a moderator looking. Waiting
 *  for a click is the answer that can be undone later; a wall of faces is not.
 *  It is not a privacy control - whoever clicks sees it - it is a deliberate
 *  step, and it is marked as an open policy question rather than a settled
 *  design.
 *
 *  It also answers #385's other question for free. A link is good for minutes
 *  and a queue is worked through over an hour, so one minted when the screen
 *  loaded is dead by the last row. Minting it when the moderator asks costs
 *  one request against a check that has to run every time anyway - which is
 *  why the TTL did not need lengthening, and app/core/photos.py records why
 *  lengthening it would have been the wrong trade. */
function ReportPhoto({ report }: { report: QueuedReport }) {
  // Photos of people wait to be asked for; a blowdown does not.
  const sensitive = report.type === 'bad_hikers'
  const [asked, setAsked] = useState(!sensitive)
  const [url, setUrl] = useState<string | null>(null)
  const [refused, setRefused] = useState(false)
  // Bumped to ask for a FRESH link. A previous one may simply have expired.
  const [request, setRequest] = useState(0)
  // Whether the current link already failed to render once, so a second
  // failure is reported rather than retried around forever.
  const [brokeOnce, setBrokeOnce] = useState(false)

  // `photo_url` is checked here as well as at the early return below, because
  // the early return comes after the hooks - so without it a report with no
  // photo would still spend a request asking for one.
  const has = report.photo_url !== null

  useEffect(() => {
    if (!has || !asked) return
    let live = true
    const controller = new AbortController()

    fetchReportPhotoLink(report.id, controller.signal)
      .then((link) => {
        if (!live) return
        setUrl(link.url)
        setRefused(false)
      })
      .catch(() => {
        // Including a 404, which here means the server would not serve a
        // photo the queue said exists - reported, never drawn as absence.
        if (live) setRefused(true)
      })

    return () => {
      live = false
      controller.abort()
    }
  }, [has, asked, request, report.id])

  const askAgain = () => {
    setRefused(false)
    setBrokeOnce(false)
    setUrl(null)
    setRequest((n) => n + 1)
  }

  if (!has) return null

  if (!asked) {
    return (
      <div className="moderation__photo">
        <button type="button" onClick={() => setAsked(true)}>
          Show the photo
        </button>
        <p className="moderation__attachment">
          This report has a photo, and it is a photo of a person. Whether one belongs in a
          queue at all is still undecided, so nothing is fetched until you ask.
        </p>
      </div>
    )
  }

  if (refused) {
    return (
      <div className="moderation__photo">
        <p className="moderation__attachment moderation__refused" role="status">
          There is a photo on this report and it could not be loaded. This is not a report
          filed without evidence — decide with that in mind, or try again.
        </p>
        <button type="button" onClick={askAgain}>
          Try the photo again
        </button>
      </div>
    )
  }

  if (url === null) {
    return (
      <p className="moderation__attachment" role="status">
        Loading the photo…
      </p>
    )
  }

  return (
    <img
      className="moderation__photo-image"
      src={url}
      // Named rather than empty: a moderator on a screen reader is deciding
      // the same thing, and "" would say this image carries no information.
      alt={`Attached to this ${(TYPE_WORDS[report.type] ?? report.type).toLowerCase()} report`}
      onLoad={() => setBrokeOnce(false)}
      onError={() => {
        // First failure is almost always an expired link, because a queue is
        // worked through slowly - ask for a new one. A second in a row is
        // something else: an object that never landed, or R2 refusing.
        if (brokeOnce) {
          setRefused(true)
          return
        }
        setBrokeOnce(true)
        setUrl(null)
        setRequest((n) => n + 1)
      }}
    />
  )
}

export function Moderation({ onClose }: ModerationProps) {
  const [queue, setQueue] = useState<ModerationQueue | null>(null)
  // Three states, not two. An empty queue and a queue that could not be read
  // draw the same screen and mean opposite things - and here the wrong one
  // says there are no unreviewed safety reports.
  const [failed, setFailed] = useState(false)
  const [busy, setBusy] = useState<string | null>(null)

  // The photo half (#579), on its own tri-state for the same reason - and
  // its own failure flag, because "the photo queue could not be read" must
  // not draw the whole screen as unreadable when the safety half loaded.
  const [photos, setPhotos] = useState<PoiPhotoQueueEntry[] | null>(null)
  const [photosFailed, setPhotosFailed] = useState(false)
  // The pinned-three collision, shown on the row that hit it: the server
  // refuses a fourth pin and says why, and that sentence belongs beside
  // the button that earned it, not in a global error state.
  const [pinRefusal, setPinRefusal] = useState<{ id: string; message: string } | null>(
    null,
  )

  const load = useCallback(async (signal?: AbortSignal) => {
    try {
      setQueue(await fetchModerationQueue(signal))
      setFailed(false)
    } catch {
      setFailed(true)
    }
    try {
      setPhotos(await fetchPhotoQueue(signal))
      setPhotosFailed(false)
    } catch {
      setPhotosFailed(true)
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
      <ReportPhoto report={report} />
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

  /** A photo action, with the 409 the pin cap returns rendered beside the
   *  row rather than as a screen-level failure. */
  const actOnPhoto = async (id: string, action: () => Promise<unknown>) => {
    setBusy(id)
    setPinRefusal(null)
    try {
      await action()
      await load()
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const detail = (error.detail as { detail?: unknown } | undefined)?.detail
        setPinRefusal({
          id,
          message:
            typeof detail === 'string'
              ? detail
              : 'This place already has three pins. Unpin one first.',
        })
      } else {
        setPhotosFailed(true)
      }
    } finally {
      setBusy(null)
    }
  }

  const REPORT_WORDS: Record<string, string> = {
    wrong_place: 'reported: not this place',
    person: 'reported: somebody in it did not agree to this',
    other: 'reported: should not be public',
  }

  const photoRow = (photo: PoiPhotoQueueEntry) => (
    <li key={photo.id} className="moderation__item moderation__item--photo">
      {/* The signed URL carries its own authorisation, so a plain <img>
          works here - the same reasoning as ReportPhoto's link form,
          without the extra hop, because the queue endpoint already minted
          the URL with the moderator's token. */}
      <img className="moderation__photo-image" src={photo.url} alt="" />
      <div className="moderation__photo-facts">
        <p className="moderation__headline">
          <span className="moderation__type">{photo.poi_id}</span>
          <span className="moderation__meta">
            {`taken ${photo.taken_month} · offered ${ageOf(photo.shared_at)} ago`}
          </span>
        </p>
        <p className="moderation__meta">
          {photo.attribution !== null
            ? `by ${photo.attribution}`
            : 'name withheld by the photographer’s request'}
          {photo.pinned && ' · pinned'}
        </p>
        {photo.held && (
          <p className="moderation__note moderation__note--flagged">
            Flagged on the hiker’s phone · {photo.flagged}. The check is often wrong about
            this, and it did not decide anything — it only put this in front of you first.
            Nothing is published while it waits here.
          </p>
        )}
        {!photo.held && photo.reported_reason !== null && (
          <p className="moderation__note moderation__note--flagged">
            {REPORT_WORDS[photo.reported_reason] ?? 'reported'}
          </p>
        )}
        {pinRefusal !== null && pinRefusal.id === photo.id && (
          <p className="moderation__note moderation__note--flagged" role="alert">
            {pinRefusal.message} Pinning this one takes another down — pick which, or
            leave this in the rolling twelve where it ages out on its own.
          </p>
        )}
        <div className="moderation__actions">
          {photo.pinned ? (
            <button
              type="button"
              disabled={busy === photo.id}
              onClick={() => void actOnPhoto(photo.id, () => unpinPhoto(photo.id))}
            >
              Unpin
            </button>
          ) : (
            <button
              type="button"
              disabled={busy === photo.id}
              onClick={() => void actOnPhoto(photo.id, () => pinPhoto(photo.id))}
            >
              Pin it
            </button>
          )}
          <button
            type="button"
            disabled={busy === photo.id}
            onClick={() => void actOnPhoto(photo.id, () => reviewPhoto(photo.id))}
          >
            Leave it in the twelve
          </button>
          <button
            type="button"
            className="moderation__dismiss"
            disabled={busy === photo.id}
            onClick={() => void actOnPhoto(photo.id, () => dismissPhoto(photo.id))}
          >
            Refuse it
          </button>
        </div>
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

      <section className="moderation__section">
        <h2>Photos offered as a pin</h2>
        <p className="moderation__preamble">
          Newest first. Recency orders this list and never promotes anything. Only pins
          are pre-moderated: the other twelve photos a place can hold go straight up and
          come down when somebody reports one — pre-approving every photo on every
          waypoint is more decisions than volunteers can work, and a queue nobody can
          clear protects nobody.
        </p>
        {photosFailed ? (
          <p role="alert" className="moderation__failed">
            The photo queue could not be read — this is no answer, not an empty one.
          </p>
        ) : photos === null ? (
          <p role="status">Reading the photos…</p>
        ) : photos.length === 0 ? (
          <p className="moderation__empty">Nothing waiting.</p>
        ) : (
          <ul className="moderation__list">{photos.map(photoRow)}</ul>
        )}
        <p className="moderation__preamble">
          Nothing on this screen touches the Commons photos the pipeline fetches. Those
          still reach a hiker&rsquo;s card with no person in the loop at all.
        </p>
      </section>

      <button type="button" onClick={onClose}>
        Back to the map
      </button>
    </main>
  )
}

// WHY THE PHOTO IS FETCHED AS A URL RATHER THAN POINTED AT (#385)
//
// This is the note that used to say the photo could not be shown, kept as the
// reason the shape above is what it is rather than deleted.
//
// `GET /reports/{id}/photo` exists and works (#234), and an `<img src>`
// pointed at it renders the photo on a public, verified report. It fails on
// exactly the reports this screen exists for: an `<img>` cannot carry an
// `Authorization` header, so the endpoint's optional auth gives the anonymous
// caller the PUBLIC answer - and an `internal_only` `bad_hikers` photo comes
// back 404 and renders as a broken image, indistinguishable from a report
// with no photo.
//
// Fetching the BYTES with the token and rendering an object URL also works,
// and costs a deployment step: the endpoint answers 302 to a presigned R2
// URL, and a cross-origin `fetch` that follows that redirect needs CORS on
// the photo bucket - which LAUNCH_CHECKLIST 1.7 deliberately left off, on a
// bucket whose whole design is that nothing reaches it without a check.
//
// So the endpoint hands back the URL instead of redirecting to it, when asked
// (`GET /reports/{id}/photo/link`). The token travels on the JSON call, where
// it can; the URL goes in `src`, where images are exempt from CORS; and the
// bytes still come straight from R2, so egress stays free - the reason R2 was
// chosen at all (#234). The redirect form is unchanged and is still what
// anything able to follow a hop should use.
