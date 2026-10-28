import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from 'react'
import { useAccount } from '../account'
import type { ClaimDetail, FollowUp, PhotoPhase, RemediationApi } from '../api'
import {
  PHOTO_POINTS,
  STATE_LABEL,
  daysLeft,
  isWorking,
  loadTicks,
  missingPhotos,
  phasesOf,
  photoAt,
  saveTicks,
} from '../claims'
import { FollowUpList } from '../components/FollowUps'
import { SignInForm } from '../components/SignInForm'
import { siteName } from '../format'
import { BEFORE_YOU_GO, FOLLOW_UP, SOURCES, planFor } from '../guide'
import {
  discardPhoto,
  dropWaiting,
  flushPhotos,
  isOffline,
  newPhotoId,
  onOfflineChange,
  queuePhoto,
  queuedBlob,
  queuedPhotos,
  refusedPhotos,
  retryPhoto,
  SIGNAL_BACK,
  saveClaim,
  savedClaim,
  waitingPhotos,
  type QueuedPhoto,
} from '../offline'
import { prepareForUpload } from '../photo'
import { claimHref, siteHref } from '../route'
import type { Site } from '../types'

const when = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium', timeStyle: 'short' })

interface Props {
  id: string
  sites: Site[]
  /** A seam for tests: jsdom has no canvas to re-encode a photo with. */
  prepare?: (photo: Blob) => Promise<Blob>
}

/** One claim: the claimer's workspace while it is open, and the record once it is done. */
export function ClaimScreen({ id, sites, prepare = prepareForUpload }: Props) {
  const { api, session } = useAccount()
  const userId = session.state === 'signed_in' ? session.userId : ''
  const [claim, setClaim] = useState<ClaimDetail | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  /** When the claim on screen is the copy kept on this phone, the time it was kept. */
  const [savedAt, setSavedAt] = useState<string | null>(null)

  const show = useCallback(
    (found: ClaimDetail) => {
      setClaim(found)
      setSavedAt(null)
      void saveClaim(userId, found)
    },
    [userId],
  )

  useEffect(() => {
    if (!api) return
    let live = true
    api.claim(id).then(
      (found) => live && show(found),
      async (error: Error) => {
        if (!live) return
        const kept = isOffline(error) ? await savedClaim(userId, id) : null
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
  }, [api, id, show, userId])

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
          <span className={`pill ${claim.state === 'done' ? '' : 'plain'}`}>
            {STATE_LABEL[claim.state]}
          </span>
          <span className="muted">
            {claim.kind === 'follow_up' ? `Follow-up visit ${claim.visit} of 3 · ` : ''}
            {claim.state === 'done' && claim.done_at
              ? `Done ${when.format(new Date(claim.done_at))} by ${claim.claimer ?? 'a volunteer'}`
              : `Claimed by ${claim.claimer ?? 'a volunteer'} ${when.format(new Date(claim.claimed_at))}`}
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
      {claim.yours && isWorking(claim) ? (
        <Workspace
          claim={claim}
          site={site}
          api={api}
          act={act}
          prepare={prepare}
          userId={userId}
        />
      ) : (
        <Record claim={claim} site={site} api={api} act={act} />
      )}
      <NotSent claimId={claim.id} userId={userId} api={api} act={act} />
    </>
  )
}

/** This account's photos for this claim kept on the phone, as they are now. */
function useKept(userId: string, claimId: string): QueuedPhoto[] {
  const [kept, setKept] = useState<QueuedPhoto[]>([])
  useEffect(() => {
    let live = true
    const read = () =>
      void queuedPhotos(userId, claimId).then((found) => live && setKept(found))
    read()
    const stop = onOfflineChange(read)
    return () => {
      live = false
      stop()
    }
  }, [userId, claimId])
  return kept
}

const slotName = (photo: QueuedPhoto) =>
  photo.point === null
    ? 'An extra photo'
    : `${photo.phase === 'before' ? 'Before' : 'After'}, point ${photo.point}`

/**
 * Photos the API refused, kept on the phone until their owner decides: shown
 * whatever state the claim is in, since the usual reason is that it closed
 * (ran out, was marked done or released) while the phone had no signal.
 */
function NotSent({
  claimId,
  userId,
  api,
  act,
}: {
  claimId: string
  userId: string
  api: RemediationApi
  act: (step: () => Promise<ClaimDetail>) => Promise<void>
}) {
  const refused = refusedPhotos(useKept(userId, claimId))
  if (refused.length === 0) return null
  const again = async (photo: QueuedPhoto) => {
    await retryPhoto(photo)
    const result = await flushPhotos(api, userId, claimId)
    if (result.sent) await act(() => api.claim(claimId))
  }
  return (
    <section
      className="note"
      aria-labelledby="not-sent"
      style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
    >
      <h2 id="not-sent" className="eyebrow">
        Not sent · kept on this phone
      </h2>
      <p style={{ margin: 0 }}>
        The server did not take{' '}
        {refused.length === 1 ? 'this photo' : `these ${refused.length} photos`}. They
        stay on this phone until you save a copy or discard them.
      </p>
      {refused.map((photo) => (
        <NotSentPhoto
          key={photo.id}
          photo={photo}
          onRetry={() => void again(photo)}
          onDiscard={() => void discardPhoto(photo)}
        />
      ))}
    </section>
  )
}

function NotSentPhoto({
  photo,
  onRetry,
  onDiscard,
}: {
  photo: QueuedPhoto
  onRetry: () => void
  onDiscard: () => void
}) {
  const url = useObjectUrl(photo)
  const label = slotName(photo)
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        {url ? (
          <img
            src={url}
            alt={`${label}, not sent`}
            style={{ width: 96, borderRadius: 8, flex: 'none' }}
          />
        ) : (
          <div className="photo-empty" style={{ width: 96, flex: 'none' }} />
        )}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0 }}>
          <b>{label}</b>
          <span className="muted">
            Taken {when.format(new Date(photo.queuedAt))}. {photo.refused?.reason}
          </span>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button type="button" className="button" onClick={onRetry}>
          Try again
        </button>
        {url && (
          <a
            className="button"
            href={url}
            download={`site-remediation-${photo.phase}${photo.point ?? ''}-${photo.queuedAt.slice(0, 10)}.jpg`}
          >
            Save a copy
          </a>
        )}
        <button type="button" className="button" onClick={onDiscard}>
          Discard
        </button>
      </div>
    </div>
  )
}

/** An object URL for a kept photo, made once per photo and revoked when it goes. */
function useObjectUrl(photo: QueuedPhoto | undefined): string | null {
  const url = useMemo(() => {
    if (!photo) return null
    try {
      return URL.createObjectURL(queuedBlob(photo))
    } catch {
      return null
    }
  }, [photo])
  useEffect(
    () => () => {
      if (url) URL.revokeObjectURL(url)
    },
    [url],
  )
  return url
}

interface PartProps {
  claim: ClaimDetail
  site: Site | undefined
  api: RemediationApi
  act: (step: () => Promise<ClaimDetail>) => Promise<void>
}

/** Days left on the claim. No reminders (decided 2026-10-28): just the clock. */
function Clock({ claim }: { claim: ClaimDetail }) {
  const left = daysLeft(claim.due_at)
  return (
    <section
      className="card"
      aria-label="Time left"
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        gap: 10,
        alignItems: 'baseline',
        padding: 14,
      }}
    >
      <b className="mono" style={{ fontSize: 28 }}>
        {left} {left === 1 ? 'day' : 'days'}
      </b>
      <span>
        left. Due {when.format(new Date(claim.due_at))}; not done by then, the site opens
        for someone else.
      </span>
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
      <span className="muted" style={{ fontSize: 13 }}>
        ATC’s volunteer protections cover people working through a maintaining club, so
        sign the club’s volunteer agreement before you go (<a href="#/guide">the guide</a>
        ).
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
  /** For an after photo: the photo to line up with (the photo-point outline,
   *  #1911): the before photo, or for a follow-up the restoration's after. */
  reference?: string | null
  disabled: boolean
  onPick: (file: File) => void
}) {
  const queuedUrl = useObjectUrl(queued)
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
        <PhotoImage url={existing.url} alt={label} />
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
          <PhotoImage
            url={reference}
            alt={`The earlier photo at point ${point}, to line up with`}
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
  userId,
}: PartProps & { prepare: (photo: Blob) => Promise<Blob>; userId: string }) {
  const [ticks, setTicks] = useState<number[]>(() => loadTicks(claim.id))
  const [steps, setSteps] = useState<string[]>(claim.steps_done)
  const [notes, setNotes] = useState(claim.notes ?? '')
  const [hours, setHours] = useState(claim.hours ? String(claim.hours) : '')
  const [busy, setBusy] = useState(false)
  const queued = waitingPhotos(useKept(userId, claim.id))
  const [notice, setNotice] = useState<string | null>(null)
  const ready = ticks.length === BEFORE_YOU_GO.length || claim.photos.length > 0
  const missing = missingPhotos(claim)
  const plan = claim.kind === 'follow_up' ? FOLLOW_UP : planFor(site?.action ?? 'unknown')

  // Photos taken with no signal wait in queue (src/offline.ts) and go when
  // the phone is back online, or when this screen next opens with signal.
  // flushPhotos runs one send at a time, however many of these ask at once.
  const send = useCallback(async () => {
    const result = await flushPhotos(api, userId, claim.id)
    if (result.refused.length) {
      setNotice(
        `${result.refused.length} saved photo${result.refused.length === 1 ? ' was' : 's were'} not accepted: ${result.refused[0].refused?.reason ?? ''} ${result.refused.length === 1 ? 'It is' : 'They are'} kept on this phone, below.`,
      )
    }
    if (result.sent) await act(() => api.claim(claim.id))
  }, [api, userId, claim.id, act])

  useEffect(() => {
    let live = true
    void queuedPhotos(userId, claim.id).then((found) => {
      if (live && waitingPhotos(found).length && navigator.onLine !== false) void send()
    })
    // The browser's online event, and a sign-in renewed after the signal came
    // back, which is the surer sign of the two that the API can be reached.
    const online = () => void send()
    window.addEventListener('online', online)
    window.addEventListener(SIGNAL_BACK, online)
    return () => {
      live = false
      window.removeEventListener('online', online)
      window.removeEventListener(SIGNAL_BACK, online)
    }
  }, [userId, claim.id, send])

  const upload = async (phase: PhotoPhase, point: number | null, file: File) => {
    setBusy(true)
    const photo = await prepare(file)
    try {
      const id = newPhotoId()
      await act(async () => {
        try {
          const updated = await api.uploadPhoto(claim.id, phase, point, photo, {
            clientId: id,
          })
          // Any older photo of this slot still waiting would replace this one.
          await dropWaiting(userId, claim.id, phase, point)
          return updated
        } catch (error) {
          if (!isOffline(error)) throw error
          // What the slot held as this phone last saw it: if the point is
          // photographed again from another phone before this is sent, that
          // newer photo is kept.
          const replaces =
            claim.photos.find((p) => p.phase === phase && p.point === point)?.id ??
            'nothing'
          await queuePhoto({
            id,
            userId,
            claimId: claim.id,
            phase,
            point,
            photo,
            replaces,
          })
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
      <BeforeYouGo claimId={claim.id} ticks={ticks} onChange={setTicks} />

      <section
        className="card"
        aria-labelledby="photos"
        style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
      >
        <h2 id="photos" className="eyebrow">
          Photos
        </h2>
        <p className="muted" style={{ margin: 0 }}>
          {claim.kind === 'follow_up'
            ? 'Two photo points: stand where the earlier photo was taken, face the same way, and take it again.'
            : 'Two photo points: stand in the same place and face the same way for the before and the after, so anyone can compare them.'}{' '}
          Keep people out of the frame. Photos are shrunk and stripped of their location
          on this phone before they are sent.
        </p>
        {PHOTO_POINTS.map((point) => (
          <div key={point} className="photo-row">
            {claim.kind === 'follow_up' && (
              // The restoration's after photo is what this visit lines up
              // with, so it gets the left column, as "Then and now" does.
              <figure className="photo-slot" style={{ margin: 0 }}>
                <PhotoImage
                  url={claim.reference.find((p) => p.point === point)?.url ?? null}
                  alt={`At the restoration, point ${point}`}
                />
                <figcaption>At the restoration, point {point}</figcaption>
              </figure>
            )}
            {phasesOf(claim).map((phase) => (
              <PhotoSlot
                key={phase}
                claim={claim}
                phase={phase}
                point={point}
                queued={waiting(phase, point)}
                reference={
                  phase === 'after' && claim.kind === 'restore'
                    ? photoAt(claim, 'before', point)?.url
                    : undefined
                }
                disabled={!ready || busy}
                onPick={(f) => void upload(phase, point, f)}
              />
            ))}
          </div>
        ))}
        <div className="photo-row">
          {claim.photos
            .filter((p) => p.phase === 'extra')
            .map((p) => (
              <div className="photo-slot" key={p.id}>
                <PhotoImage url={p.url} alt="An extra photo" />
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
          <label htmlFor="notes">Notes, public once the work is done</label>
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
            They count when you mark the work done.
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
            void act(() => api.finish(claim.id, steps, notes.trim() || null))
          }
        >
          Mark as done
        </button>
        {missing.length > 0 ? (
          <span className="muted">Still needed: {missing.join(', ')}.</span>
        ) : (
          <span className="muted">
            Done is public at once: the photos, the notes and your name.
            {claim.kind === 'restore' &&
              ' The site’s three follow-up visits are scheduled.'}
          </span>
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

/**
 * A photo from the bucket, through its signed link. Asked for with CORS so the
 * service worker may keep it for use with no signal (vite.config.ts); a link
 * Storage would not sign shows as not loaded, never as no photo.
 */
function PhotoImage({ url, alt }: { url: string | null; alt: string }) {
  return url ? (
    <img src={url} alt={alt} crossOrigin="anonymous" />
  ) : (
    <div className="photo-empty" role="img" aria-label={`${alt}: not loaded`}>
      Not loaded. Open the claim again with signal.
    </div>
  )
}

/** A claim seen by anyone but its claimer, or after the work: the photos side by side. */
function Record({ claim, api }: PartProps) {
  const extras = claim.photos.filter((p) => p.phase === 'extra')
  if (!claim.full)
    return (
      <p className="note" style={{ margin: 0 }}>
        {claim.state === 'released'
          ? 'This claim has ended, and the site is open to claim again.'
          : 'Someone is working on this site. Its photos and report are theirs until they mark it done; then they are public.'}
      </p>
    )
  type Photo = ClaimDetail['photos'][number]
  const columns: { label: string; photo: (point: number) => Photo | null }[] =
    claim.kind === 'follow_up'
      ? [
          {
            label: 'At the restoration',
            photo: (point) => claim.reference.find((p) => p.point === point) ?? null,
          },
          { label: 'This visit', photo: (point) => photoAt(claim, 'after', point) },
        ]
      : [
          { label: 'Before', photo: (point) => photoAt(claim, 'before', point) },
          { label: 'After', photo: (point) => photoAt(claim, 'after', point) },
        ]
  return (
    <>
      <section
        className="card"
        aria-labelledby="compare"
        style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
      >
        <h2 id="compare" className="eyebrow">
          {claim.kind === 'follow_up' ? 'Then and now' : 'Before and after'}
        </h2>
        {PHOTO_POINTS.map((point) => (
          <div key={point} className="photo-row">
            {columns.map((column) => {
              const photo = column.photo(point)
              const label = `${column.label}, point ${point}`
              return (
                <figure className="photo-slot" key={column.label} style={{ margin: 0 }}>
                  {photo ? (
                    <PhotoImage url={photo.url} alt={label} />
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
                <PhotoImage url={p.url} alt="An extra photo" />
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
          What was reported
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
          {claim.hours === null ? 'No hours logged.' : `${claim.hours} h on the site.`}
        </p>
      </section>
      {claim.state === 'done' && claim.kind === 'restore' && (
        <SiteFollowUps rimsId={claim.rims_id} api={api} />
      )}
    </>
  )
}

/** A done restoration's follow-up visits, with a way to take an open one. */
function SiteFollowUps({ rimsId, api }: { rimsId: string; api: RemediationApi }) {
  const [followUps, setFollowUps] = useState<FollowUp[] | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  useEffect(() => {
    let live = true
    api.followUps(rimsId).then(
      (found) => live && setFollowUps(found),
      (error: Error) => live && setProblem(isOffline(error) ? null : error.message),
    )
    return () => {
      live = false
    }
  }, [api, rimsId])
  if (problem) return <p role="alert">{problem}</p>
  if (!followUps || followUps.length === 0) return null
  const take = async (followUp: FollowUp) => {
    try {
      const taken = await api.takeFollowUp(followUp.id)
      window.location.hash = claimHref(taken.id)
    } catch (error) {
      setProblem((error as Error).message)
    }
  }
  return <FollowUpList followUps={followUps} onTake={(f) => void take(f)} />
}
