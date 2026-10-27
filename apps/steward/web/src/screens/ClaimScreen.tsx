import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from 'react'
import { useAccount } from '../account'
import type { ClaimDetail, PhotoPhase, StewardApi } from '../api'
import {
  PHOTO_POINTS,
  STATE_LABEL,
  daysLeft,
  isWorking,
  loadTicks,
  missingPhotos,
  photoAt,
  reminder,
  saveTicks,
} from '../claims'
import { SignInForm } from '../components/SignInForm'
import { siteName } from '../format'
import { BEFORE_YOU_GO, SOURCES, planFor } from '../guide'
import {
  flushPhotos,
  isOffline,
  queuePhoto,
  queuedBlob,
  queuedPhotos,
  saveClaim,
  savedClaim,
  type QueuedPhoto,
} from '../offline'
import { prepareForUpload } from '../photo'
import { joinHref, siteHref } from '../route'
import type { Site } from '../types'

const when = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' })

interface Props {
  id: string
  sites: Site[]
  /** A seam for tests: jsdom has no canvas to re-encode a photo with. */
  prepare?: (photo: Blob) => Promise<Blob>
}

/** One claim: the crew's workspace while it is open, and the reviewer's view once submitted. */
export function ClaimScreen({ id, sites, prepare = prepareForUpload }: Props) {
  const { api } = useAccount()
  const [claim, setClaim] = useState<ClaimDetail | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  /** When the claim on screen is the copy kept on this phone, the time it was kept. */
  const [savedAt, setSavedAt] = useState<string | null>(null)

  const show = useCallback((found: ClaimDetail) => {
    setClaim(found)
    setSavedAt(null)
    void saveClaim(found)
  }, [])

  useEffect(() => {
    if (!api) return
    let live = true
    api.claim(id).then(
      (found) => live && show(found),
      async (error: Error) => {
        if (!live) return
        const kept = isOffline(error) ? await savedClaim(id) : null
        if (!live) return
        if (kept) {
          setClaim(kept.claim)
          setSavedAt(kept.savedAt)
        } else {
          setProblem(
            isOffline(error)
              ? 'No signal, and this claim has not been opened on this phone before.'
              : error.message,
          )
        }
      },
    )
    return () => {
      live = false
    }
  }, [api, id, show])

  const act = useCallback(
    async (step: () => Promise<ClaimDetail>) => {
      try {
        show(await step())
        setProblem(null)
      } catch (error) {
        setProblem(
          isOffline(error)
            ? 'No signal. Try again when you have some.'
            : (error as Error).message,
        )
      }
    },
    [show],
  )

  if (!api) {
    return (
      <section className="card">
        <h1 style={{ fontSize: 28, marginBottom: 10 }}>A claim</h1>
        <SignInForm why="Sign in to see this claim." />
      </section>
    )
  }
  if (!claim)
    return problem ? (
      <p role="alert">{problem}</p>
    ) : (
      <p className="muted">Loading the claim…</p>
    )
  const site = sites.find((s) => s.rims_id === claim.rims_id)

  return (
    <>
      <header style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <a href={site ? siteHref(site.rims_id) : '#/'} style={{ fontWeight: 600 }}>
          ← {site ? siteName(site) : 'All sites'}
        </a>
        <h1 style={{ fontSize: 30 }}>
          {site ? siteName(site) : 'A site no longer in ATC’s inventory'}
        </h1>
        <div className="chips">
          <span className={`pill ${claim.state === 'verified' ? '' : 'plain'}`}>
            {STATE_LABEL[claim.state]}
          </span>
          <span className="muted">
            Claimed by {claim.claimer ?? 'a volunteer'}{' '}
            {when.format(new Date(claim.claimed_at))}
          </span>
        </div>
      </header>
      {problem && (
        <p role="alert" className="note" style={{ margin: 0, color: '#8a3a14' }}>
          {problem}
        </p>
      )}
      {savedAt && (
        <p className="note" role="status" style={{ margin: 0 }}>
          <b>No signal.</b> This is the claim as this phone saved it,{' '}
          {when.format(new Date(savedAt))}. Photos you take now wait on the phone and are
          sent when there is signal.
        </p>
      )}
      {claim.state === 'released' && claim.review_note && (
        <p className="note" style={{ margin: 0 }}>
          <b>Rejected by {claim.reviewed_by ?? 'a reviewer'}:</b> “{claim.review_note}”
        </p>
      )}
      {claim.review_note && claim.state === 'in_progress' && (
        <p className="note" style={{ margin: 0 }}>
          <b>Sent back by {claim.reviewed_by ?? 'a reviewer'}:</b> “{claim.review_note}”
          Retake the after photos, then submit again.
        </p>
      )}
      {claim.you_are_crew && isWorking(claim) ? (
        <Workspace claim={claim} site={site} api={api} act={act} prepare={prepare} />
      ) : (
        <Record claim={claim} site={site} api={api} act={act} />
      )}
    </>
  )
}

interface PartProps {
  claim: ClaimDetail
  site: Site | undefined
  api: StewardApi
  act: (step: () => Promise<ClaimDetail>) => Promise<void>
}

function Clock({ claim }: { claim: ClaimDetail }) {
  const left = daysLeft(claim.due_at)
  const nudge = reminder(claim.due_at)
  return (
    <section
      className={nudge ? 'note' : 'card'}
      aria-label="Time left"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 10,
        alignItems: 'baseline',
        padding: 14,
      }}
    >
      <b
        className="mono"
        style={{ fontSize: 28, color: nudge === 'warning' ? '#c23d17' : undefined }}
      >
        {left} {left === 1 ? 'day' : 'days'}
      </b>
      <span>
        left. Due {when.format(new Date(claim.due_at))}; not submitted by then, the site
        is released for someone else to claim.
      </span>
      {nudge === 'warning' && (
        <b style={{ flexBasis: '100%' }}>
          Submit today, or release the site so someone else can.
        </b>
      )}
      {nudge === 'nudge' && (
        <span style={{ flexBasis: '100%' }}>Under five days left.</span>
      )}
    </section>
  )
}

function Crew({ claim, api, act }: PartProps) {
  const [link, setLink] = useState<string | null>(null)
  const invite = async () => {
    try {
      const { token } = await api.invite(claim.id)
      setLink(`${window.location.origin}${window.location.pathname}${joinHref(token)}`)
    } catch (error) {
      await act(() => Promise.reject(error))
    }
  }
  return (
    <section
      className="card"
      aria-labelledby="crew"
      style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
    >
      <h2 id="crew" className="eyebrow">
        Crew
      </h2>
      <ul style={{ margin: 0, paddingLeft: 20 }}>
        {claim.crew.map((member, i) => (
          <li key={i}>
            {member.you ? 'You' : (member.name ?? 'A volunteer')}
            {member.hours !== null && <span className="muted"> · {member.hours} h</span>}
          </li>
        ))}
      </ul>
      <div>
        <button type="button" className="button" onClick={() => void invite()}>
          Invite someone
        </button>
      </div>
      {link && (
        <p className="note" style={{ margin: 0 }}>
          Anyone signed in who opens this link joins the crew. A new link stops this one
          working.{' '}
          <span className="mono" style={{ wordBreak: 'break-all' }}>
            {link}
          </span>{' '}
          <button
            type="button"
            className="button"
            onClick={() => void navigator.clipboard?.writeText(link)}
          >
            Copy
          </button>
        </p>
      )}
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>
        ATC’s volunteer protections cover people working through a maintaining club.
        Everyone going signs the club’s volunteer agreement (
        <a href="#/guide">the guide</a>).
      </p>
    </section>
  )
}

function BeforeYouGo({
  claimId,
  ticks,
  onChange,
}: {
  claimId: string
  ticks: number[]
  onChange: (t: number[]) => void
}) {
  const toggle = (index: number) => {
    const next = ticks.includes(index)
      ? ticks.filter((t) => t !== index)
      : [...ticks, index]
    saveTicks(claimId, next)
    onChange(next)
  }
  return (
    <section
      className="card"
      aria-labelledby="before"
      style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
    >
      <h2 id="before" className="eyebrow">
        Before you go · {ticks.length} of {BEFORE_YOU_GO.length}
      </h2>
      {BEFORE_YOU_GO.map((check, index) => (
        <label
          key={check.text}
          style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}
        >
          <input
            type="checkbox"
            checked={ticks.includes(index)}
            onChange={() => toggle(index)}
            style={{ marginTop: 4 }}
          />
          <span>
            {check.text}{' '}
            <a
              href={SOURCES[check.source].url}
              target="_blank"
              rel="noreferrer"
              style={{ fontSize: 13 }}
            >
              source
            </a>
          </span>
        </label>
      ))}
      <span className="muted" style={{ fontSize: 13 }}>
        Saved on this phone. The photo buttons open once everything is ticked.
      </span>
    </section>
  )
}

function PhotoSlot({
  claim,
  phase,
  point,
  queued,
  reference,
  disabled,
  onPick,
}: {
  claim: ClaimDetail
  phase: PhotoPhase
  point: number | null
  /** A photo for this slot waiting on the phone for signal. */
  queued?: QueuedPhoto
  /** For an after photo: the before photo to line up with (the photo-point outline, #1911). */
  reference?: string
  disabled: boolean
  onPick: (file: File) => void
}) {
  // An object URL for the waiting photo, made once per photo and revoked when it goes.
  const queuedUrl = useMemo(() => {
    if (!queued) return null
    try {
      return URL.createObjectURL(queuedBlob(queued))
    } catch {
      return null
    }
  }, [queued])
  useEffect(
    () => () => {
      if (queuedUrl) URL.revokeObjectURL(queuedUrl)
    },
    [queuedUrl],
  )
  const existing =
    point === null ? null : photoAt(claim, phase as 'before' | 'after', point)
  const label =
    point === null
      ? 'Add an extra photo'
      : `${phase === 'before' ? 'Before' : 'After'}, point ${point}`
  const pick = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (file) onPick(file)
  }
  return (
    <div className="photo-slot">
      {queued ? (
        <div className="photo-queued">
          {queuedUrl ? (
            <img src={queuedUrl} alt={`${label}, waiting to send`} />
          ) : (
            <div className="photo-empty" />
          )}
          <span className="pill plain">Waiting for signal</span>
        </div>
      ) : existing ? (
        <img src={existing.url} alt={label} />
      ) : (
        <div className="photo-empty" aria-hidden="true">
          {point === null ? '+' : 'No photo yet'}
        </div>
      )}
      <label className={`button ${disabled ? 'disabled' : ''}`}>
        {existing ? `Retake: ${label.toLowerCase()}` : label}
        <input
          type="file"
          accept="image/*"
          capture="environment"
          disabled={disabled}
          onChange={pick}
          className="visually-hidden"
          aria-label={label}
        />
      </label>
      {reference && !existing && (
        <figure className="photo-reference">
          <img
            src={reference}
            alt={`The before photo at point ${point}, to line up with`}
          />
          <figcaption>Stand where this was taken and face the same way.</figcaption>
        </figure>
      )}
    </div>
  )
}

function Workspace({
  claim,
  site,
  api,
  act,
  prepare,
}: PartProps & { prepare: (photo: Blob) => Promise<Blob> }) {
  const [ticks, setTicks] = useState<number[]>(() => loadTicks(claim.id))
  const [steps, setSteps] = useState<string[]>(claim.steps_done)
  const [notes, setNotes] = useState(claim.notes ?? '')
  const you = claim.crew.find((m) => m.you)
  const [hours, setHours] = useState(you?.hours ? String(you.hours) : '')
  const [busy, setBusy] = useState(false)
  const [queued, setQueued] = useState<QueuedPhoto[]>([])
  const [notice, setNotice] = useState<string | null>(null)
  const ready = ticks.length === BEFORE_YOU_GO.length || claim.photos.length > 0
  const missing = missingPhotos(claim)
  const plan = planFor(site?.action ?? 'unknown')

  // Photos taken with no signal wait in queue (src/offline.ts) and go when
  // the phone is back online, or when this screen next opens with signal.
  const send = useCallback(async () => {
    const result = await flushPhotos(api, claim.id)
    setQueued(await queuedPhotos(claim.id))
    if (result.refused.length) {
      setNotice(
        `${result.refused.length} saved photo${result.refused.length === 1 ? ' was' : 's were'} not accepted: ${result.refused[0].reason}`,
      )
    }
    if (result.sent) await act(() => api.claim(claim.id))
  }, [api, claim.id, act])

  useEffect(() => {
    let live = true
    void queuedPhotos(claim.id).then((found) => {
      if (!live) return
      setQueued(found)
      if (found.length && navigator.onLine !== false) void send()
    })
    const online = () => void send()
    window.addEventListener('online', online)
    return () => {
      live = false
      window.removeEventListener('online', online)
    }
  }, [claim.id, send])

  const upload = async (phase: PhotoPhase, point: number | null, file: File) => {
    setBusy(true)
    const photo = await prepare(file)
    try {
      await act(async () => {
        try {
          return await api.uploadPhoto(claim.id, phase, point, photo)
        } catch (error) {
          if (!isOffline(error)) throw error
          await queuePhoto({ claimId: claim.id, phase, point, photo })
          setQueued(await queuedPhotos(claim.id))
          setNotice(
            'No signal: the photo is saved on this phone and will be sent when there is signal.',
          )
          return claim
        }
      })
    } finally {
      setBusy(false)
    }
  }
  const waiting = (phase: PhotoPhase, point: number | null) =>
    point === null
      ? undefined
      : [...queued].reverse().find((q) => q.phase === phase && q.point === point)

  return (
    <>
      <Clock claim={claim} />
      <div className="grid2">
        <BeforeYouGo claimId={claim.id} ticks={ticks} onChange={setTicks} />
        <Crew claim={claim} site={site} api={api} act={act} />
      </div>

      <section
        className="card"
        aria-labelledby="photos"
        style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
      >
        <h2 id="photos" className="eyebrow">
          Photos
        </h2>
        <p className="muted" style={{ margin: 0 }}>
          Two photo points: stand in the same place and face the same way for the before
          and the after, so a reviewer can compare them. Keep people out of the frame.
          Photos are shrunk and stripped of their location on this phone before they are
          sent.
        </p>
        {PHOTO_POINTS.map((point) => (
          <div key={point} className="photo-row">
            <PhotoSlot
              claim={claim}
              phase="before"
              point={point}
              queued={waiting('before', point)}
              disabled={!ready || busy}
              onPick={(f) => void upload('before', point, f)}
            />
            <PhotoSlot
              claim={claim}
              phase="after"
              point={point}
              queued={waiting('after', point)}
              reference={photoAt(claim, 'before', point)?.url}
              disabled={!ready || busy}
              onPick={(f) => void upload('after', point, f)}
            />
          </div>
        ))}
        <div className="photo-row">
          {claim.photos
            .filter((p) => p.phase === 'extra')
            .map((p) => (
              <div className="photo-slot" key={p.id}>
                <img src={p.url} alt="An extra photo" />
                <button
                  type="button"
                  className="button"
                  onClick={() => void act(() => api.deletePhoto(claim.id, p.id))}
                >
                  Remove
                </button>
              </div>
            ))}
          <PhotoSlot
            claim={claim}
            phase="extra"
            point={null}
            disabled={!ready || busy}
            onPick={(f) => void upload('extra', null, f)}
          />
        </div>
        {busy && <p className="muted">Sending the photo…</p>}
        {queued.length > 0 && (
          <p className="note" role="status" style={{ margin: 0 }}>
            {queued.length} photo{queued.length === 1 ? '' : 's'} waiting on this phone
            for signal.{' '}
            <button type="button" className="button" onClick={() => void send()}>
              Send now
            </button>
          </p>
        )}
        {notice && (
          <p className="muted" style={{ margin: 0 }}>
            {notice}
          </p>
        )}
      </section>

      <section
        className="card"
        aria-labelledby="done"
        style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
      >
        <h2 id="done" className="eyebrow">
          What got done
        </h2>
        {plan.map((step) => (
          <label key={step.title} style={{ display: 'flex', gap: 10 }}>
            <input
              type="checkbox"
              checked={steps.includes(step.title)}
              onChange={() =>
                setSteps(
                  steps.includes(step.title)
                    ? steps.filter((s) => s !== step.title)
                    : [...steps, step.title],
                )
              }
            />
            {step.title}
            {step.needsApproval && (
              <span className="approval"> · needs land-manager approval</span>
            )}
          </label>
        ))}
        <div className="field">
          <label htmlFor="notes">Notes for the reviewer</label>
          <textarea
            id="notes"
            rows={3}
            maxLength={1000}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
        <form
          className="field"
          onSubmit={(e) => {
            e.preventDefault()
            void act(() => api.logHours(claim.id, Number(hours)))
          }}
        >
          <label htmlFor="hours">Your hours on this site, all visits</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              id="hours"
              type="number"
              min={0.5}
              max={72}
              step={0.5}
              value={hours}
              onChange={(e) => setHours(e.target.value)}
              style={{ width: 110 }}
            />
            <button type="submit" className="button" disabled={!hours}>
              Save my hours
            </button>
          </div>
          <span className="muted" style={{ fontSize: 13 }}>
            Each person on the crew logs their own. They count once someone off the crew
            verifies the work.
          </span>
        </form>
      </section>

      <section
        className="card"
        style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}
      >
        <button
          type="button"
          className="button primary"
          disabled={missing.length > 0 || claim.state !== 'in_progress'}
          onClick={() =>
            void act(() => api.submit(claim.id, steps, notes.trim() || null))
          }
        >
          Submit for review
        </button>
        {missing.length > 0 && (
          <span className="muted">Still needed: {missing.join(', ')}.</span>
        )}
        <button
          type="button"
          className="button"
          style={{ marginLeft: 'auto' }}
          onClick={() => void act(() => api.releaseClaim(claim.id))}
        >
          Release this site
        </button>
      </section>
    </>
  )
}

/** A claim seen from outside the crew, or after the work: the photos side by side, and the review when it is waiting. */
function Record({ claim, api, act }: PartProps) {
  const [note, setNote] = useState('')
  const extras = claim.photos.filter((p) => p.phase === 'extra')
  return (
    <>
      {claim.state === 'submitted' && claim.you_are_crew && (
        <p className="note" style={{ margin: 0 }}>
          Submitted {claim.submitted_at ? when.format(new Date(claim.submitted_at)) : ''}.
          The clock has stopped; someone off the crew will review it.
        </p>
      )}
      <section
        className="card"
        aria-labelledby="compare"
        style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
      >
        <h2 id="compare" className="eyebrow">
          Before and after
        </h2>
        {PHOTO_POINTS.map((point) => (
          <div key={point} className="photo-row">
            {(['before', 'after'] as const).map((phase) => {
              const photo = photoAt(claim, phase, point)
              const label = `${phase === 'before' ? 'Before' : 'After'}, point ${point}`
              return (
                <figure className="photo-slot" key={phase} style={{ margin: 0 }}>
                  {photo ? (
                    <img src={photo.url} alt={label} />
                  ) : (
                    <div className="photo-empty">No photo</div>
                  )}
                  <figcaption>{label}</figcaption>
                </figure>
              )
            })}
          </div>
        ))}
        {extras.length > 0 && (
          <div className="photo-row">
            {extras.map((p) => (
              <figure className="photo-slot" key={p.id} style={{ margin: 0 }}>
                <img src={p.url} alt="An extra photo" />
              </figure>
            ))}
          </div>
        )}
      </section>
      <section
        className="card"
        aria-labelledby="reported"
        style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
      >
        <h2 id="reported" className="eyebrow">
          What the crew reported
        </h2>
        {claim.steps_done.length > 0 ? (
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {claim.steps_done.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ul>
        ) : (
          <p className="muted" style={{ margin: 0 }}>
            No steps ticked.
          </p>
        )}
        {claim.notes && <p style={{ margin: 0 }}>“{claim.notes}”</p>}
        <p className="muted" style={{ margin: 0 }}>
          Crew of {claim.crew_size}; hours logged:{' '}
          {claim.crew.map((m) => (m.hours === null ? '—' : `${m.hours} h`)).join(', ')}
        </p>
      </section>
      {claim.you_may_review && (
        <section
          className="card"
          aria-labelledby="review"
          style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
        >
          <h2 id="review" className="eyebrow">
            Your review
          </h2>
          <p className="muted" style={{ margin: 0 }}>
            You can review this because you are not on its crew. Verify when the after
            photos show the site hidden and the way in blocked; it confirms the crew’s
            hours.
          </p>
          <div className="field">
            <label htmlFor="review-note">
              Note to the crew (needed to send back or reject)
            </label>
            <textarea
              id="review-note"
              rows={2}
              maxLength={500}
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              className="button primary"
              onClick={() =>
                void act(() => api.review(claim.id, 'verify', note.trim() || null))
              }
            >
              Verify
            </button>
            <button
              type="button"
              className="button"
              disabled={!note.trim()}
              onClick={() =>
                void act(() => api.review(claim.id, 'send_back', note.trim()))
              }
            >
              Send back
            </button>
            <button
              type="button"
              className="button"
              style={{ marginLeft: 'auto' }}
              disabled={!note.trim()}
              onClick={() => void act(() => api.review(claim.id, 'reject', note.trim()))}
            >
              Reject: the work was not done
            </button>
          </div>
          <p className="muted" style={{ margin: 0, fontSize: 13 }}>
            Send back when it is nearly there: the crew retakes the after photos. Reject
            when the photos do not show this site restored: the site opens for someone
            else and no hours count.
          </p>
        </section>
      )}
      {claim.state === 'verified' && (
        <p className="note" style={{ margin: 0 }}>
          Verified by {claim.reviewed_by ?? 'a volunteer'}
          {claim.verified_at ? ` on ${when.format(new Date(claim.verified_at))}` : ''}.
          {claim.review_note && ` “${claim.review_note}”`}
        </p>
      )}
    </>
  )
}
