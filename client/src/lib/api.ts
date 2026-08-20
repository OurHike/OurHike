// The one place this app talks to OurHike's own backend.
//
// Until this existed there was no such place at all: no base URL among the
// build-time variables, no `Authorization` header anywhere in the client, and
// `flushOutbox` (lib/outbox.ts) referenced only by its own tests. A report
// reached IndexedDB and stayed there for the life of the install (#231).
//
// Distinct from lib/config.ts, which stays about the R2 bucket of published
// pipeline artifacts. Two different services with two different failure
// modes: the bucket is static files a hiker downloads once and reads offline
// forever, this is a live API reachable only with signal. Folding them into
// one module would put a "configured?" flag over both that is true for
// neither.
//
// Also distinct from lib/supabase.ts. Supabase is where a hiker AUTHENTICATES;
// this backend only ever verifies the JWT that comes back
// (backend/app/core/auth.py). The token is borrowed from there and sent here.

import { getAuthClient } from './supabase'
import type { OutboxItem, PhotoAction } from './outbox'
import type { BackendReportStatus } from './reportStatus'
import type { ClosureReason, ClosureStatus } from './closureBanner'
import { PHOTO_CONTENT_TYPE } from './reportPhoto'

const RAW_BASE: string = import.meta.env.VITE_API_BASE_URL ?? ''

export const API_BASE_URL = RAW_BASE.replace(/\/+$/, '')

/**
 * False when no backend was configured at build time.
 *
 * The same guard `DATA_CONFIGURED` provides for the data bucket, and for the
 * same reason: without it a blank base makes every path relative, so requests
 * resolve against the app's own origin and a report POST reaches the static
 * host that serves the PWA. That returns a cheerful 200 with an HTML body,
 * which is indistinguishable from success to anything checking `response.ok`
 * - and the outbox would then drop a report nobody received.
 */
export const API_CONFIGURED = API_BASE_URL !== ''

export function apiUrl(path: string): string {
  return `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`
}

/** A request that reached the server and came back refused.
 *
 * `detail` is the parsed response body, when there was one and it was JSON.
 * Carried because the status alone is not enough to say what happened: the
 * backend produces 422 for two unrelated reasons, and telling them apart
 * decides whether a hiker's report is worth retrying (#412). Left `undefined`
 * rather than defaulted, so "no body" and "a body saying nothing" stay
 * distinguishable.
 */
export class ApiError extends Error {
  readonly status: number
  readonly detail: unknown

  constructor(status: number, message: string, detail?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

/** No backend to talk to, established before any request is attempted. */
export class ApiNotConfiguredError extends Error {
  constructor() {
    super('This build has no OurHike backend configured.')
    this.name = 'ApiNotConfiguredError'
  }
}

/** Signed out, or signed in with a session that has since expired. */
export class NotSignedInError extends Error {
  constructor() {
    super('Sending needs an account, and this device is not signed in.')
    this.name = 'NotSignedInError'
  }
}

/**
 * The current Supabase access token, or null when there is no session.
 *
 * Read per request rather than held, because Supabase refreshes it in the
 * background (`autoRefreshToken`, lib/supabase.ts) and a cached copy would go
 * stale exactly during the long offline stretch this app is built around.
 */
export async function accessToken(): Promise<string | null> {
  const client = getAuthClient()
  if (client === null) return null

  const { data } = await client.auth.getSession()
  return data.session?.access_token ?? null
}

/**
 * A request to the backend, with the bearer token attached.
 *
 * **Throws on any non-2xx, and that is load-bearing rather than stylistic.**
 * `flushOutbox` tells sent from failed purely by whether `send` rejects, so a
 * `fetch` that resolves with a 500 would be counted as delivered and the
 * report removed from the queue. `fetch` only rejects on network failure, so
 * without this every server error silently destroys someone's report.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  if (!API_CONFIGURED) throw new ApiNotConfiguredError()

  const response = await fetch(apiUrl(path), init)

  if (!response.ok) {
    throw new ApiError(
      response.status,
      `${init.method ?? 'GET'} ${path} failed: ${response.status}`,
      await errorBody(response),
    )
  }
  return response
}

/**
 * The parsed body of a refused response, or undefined.
 *
 * Every failure here is swallowed on purpose. This runs while building the
 * error for a request that has ALREADY failed, and a body that is empty,
 * truncated, HTML from a proxy, or unreadable because the connection died
 * mid-read must not replace a useful `ApiError` with a parse exception. The
 * caller loses the extra detail and keeps the status, which is what it had
 * before this existed.
 */
async function errorBody(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    return undefined
  }
}

/** Like `apiFetch`, but refuses before spending a request when signed out. */
async function authedFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await accessToken()
  // Checked here rather than left to the server's 401, because the round trip
  // is the expensive part on a metered connection with one bar - and the
  // answer is knowable without it.
  if (token === null) throw new NotSignedInError()

  return apiFetch(path, {
    ...init,
    headers: {
      ...init.headers,
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  })
}

/**
 * Like `apiFetch`, but attaches the token only if there happens to be one.
 *
 * A third stance, and the reason reads could not just borrow `authedFetch`
 * (#286). That one refuses without a token, which is right for a write the
 * server would refuse anyway. A read must not: browsing has never needed an
 * account in this app, and `list_reports` is built to answer an anonymous
 * caller with the public set.
 *
 * But the token still goes when it exists, and that is not a nicety - it is
 * what lets a reporter see their own unmoderated report. Without it someone's
 * own report vanishes from the app between submitting it and a moderator
 * reaching it, which is precisely what "Waiting" on the More screen is
 * describing.
 */
async function readFetch(path: string, signal?: AbortSignal): Promise<Response> {
  const token = await accessToken()

  return apiFetch(path, {
    signal,
    headers: token === null ? {} : { Authorization: `Bearer ${token}` },
  })
}

/**
 * A write the server accepts with or without an account, carrying the token
 * when there is one.
 *
 * A fourth stance, and the only endpoint that wants it is `/app-failures`
 * (#848). `authedFetch` refuses without a token, which is right for a write
 * the server would refuse anyway - and this is a write the server would NOT
 * refuse, deliberately: a hiker reporting that the app nearly got them lost
 * may never have signed in, and browsing the map has never asked them to.
 * `readFetch` has the right token handling and is GET-shaped.
 *
 * The token still goes when it exists, because knowing which account filed a
 * report is the second way to reach somebody when the contact detail they
 * left turns out to be wrong.
 */
async function openFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await accessToken()

  return apiFetch(path, {
    ...init,
    headers: {
      ...init.headers,
      'Content-Type': 'application/json',
      ...(token === null ? {} : { Authorization: `Bearer ${token}` }),
    },
  })
}

/**
 * What `GET /reports` returns, limited to the fields this app reads.
 *
 * The backend sends more (`received_at`, `follow_up`, `club_id` and the rest
 * of `ReportOut`); declaring only what is consumed keeps this honest about
 * what the client actually depends on rather than mirroring a schema it does
 * not use.
 */
export interface ReportSummary {
  id: string
  type: string
  reporter_type: string
  status: BackendReportStatus
  severity: 'normal' | 'serious'
  lat: number | null
  lon: number | null
  /**
   * Miles from the southern terminus, as the reporting phone measured it
   * (#244) - or null.
   *
   * **Null is the common case and will stay common**, so nothing may treat
   * this as the only source of a mile. It is null for every report filed
   * before the field existed, for a fix that did not land on the trail, and
   * for a phone that had not downloaded the trail index yet. Where this app
   * holds the centerline it should prefer its own snap of `lat`/`lon`, which
   * is derived from the same index it measures the hiker against; this is
   * what answers the cases that snap cannot, chiefly a report with a
   * `poi_id` and no coordinates at all.
   */
  mile: number | null
  poi_id: string | null
  note: string | null
  /** ISO 8601, UTC-designated - the server stamps the `Z` on the way out. */
  timestamp: string
}

/**
 * Reports visible to this caller: public and moderated, plus their own at any
 * status when a token went with the request.
 *
 * **Throws rather than returning `[]` on failure, and that is the point.** An
 * empty list and a failed fetch draw the same map and mean opposite things on
 * the ground - the wrong one of those tells a hiker a closed stretch of trail
 * is open. The caller has to be able to say it does not know.
 */
export async function fetchReports(signal?: AbortSignal): Promise<ReportSummary[]> {
  const response = await readFetch('/reports', signal)
  return (await response.json()) as ReportSummary[]
}

/**
 * One community photo of a waypoint, as `GET /waypoints/{id}/photos` serves
 * it (backend app/schemas/poi_photo.py) - rung 2 of the card's ladder.
 *
 * `url` is a short-lived signed URL, so an entry is rendered soon or fetched
 * again, never cached for later. `attribution` is null while the
 * photographer's anonymity window holds - withheld by their request, which
 * is different from unknown, and the credit line renders the licence and
 * month without a name rather than inventing one.
 */
export interface PoiPhotoSummary {
  id: string
  poi_id: string
  url: string
  /** "YYYY-MM" - capture month where the original carried a date, else the
   *  month it was shared. Month precision is all this surface ever gets. */
  taken_month: string
  attribution: string | null
  license: string
  pinned: boolean
}

export async function fetchPoiPhotos(
  poiId: string,
  signal?: AbortSignal,
): Promise<PoiPhotoSummary[]> {
  const response = await readFetch(
    `/waypoints/${encodeURIComponent(poiId)}/photos`,
    signal,
  )
  return (await response.json()) as PoiPhotoSummary[]
}

/** What `GET /closures` returns, limited to the fields this app reads. */
export interface ClosureSummary {
  id: string
  reason_type: ClosureReason
  note: string | null
  status: ClosureStatus
  start_mile_marker: number
  end_mile_marker: number
  /**
   * Where the two ends physically are (#674).
   *
   * The miles above are a reading against one measurement of the centerline,
   * and the ATC re-measures — so a closure authored against last year's
   * measurement names a slightly different stretch under this year's. These
   * do not move, and `lib/closureProjection.ts` re-reads the miles from them
   * against whichever release this phone is holding.
   *
   * Null on every closure filed before the columns existed, and on every one
   * filed until this app grows a closure form — there is no create call in
   * this file, only fetch, verify and dismiss. A null pair means "show the
   * mile as stored", which is what every closure does today.
   *
   * **Optional as well as nullable, and the two mean different things.** The
   * live `GET /closures` always sends all four keys, null or not. The
   * published baseline this same type describes (`lib/publishedConditions.ts`)
   * is a file in a bucket, and one baked before these columns existed omits
   * the keys entirely — a phone holding last month's release reads
   * `undefined`, not `null`. Both must be treated as "no geometry", which is
   * why `lib/closureProjection.ts` tests for a number rather than against
   * null.
   */
  start_lat?: number | null
  start_lon?: number | null
  end_lat?: number | null
  end_lon?: number | null
  /** ISO 8601, UTC-designated. */
  reported_at: string
  verified_at: string | null
}

/**
 * Verified closures. Same throw-on-failure rule as `fetchReports`, and it
 * matters more here: a closure is the one thing on this map whose absence a
 * hiker would act on by walking into it.
 */
export async function fetchClosures(signal?: AbortSignal): Promise<ClosureSummary[]> {
  const response = await readFetch('/closures', signal)
  return (await response.json()) as ClosureSummary[]
}

/**
 * Sends one queued report.
 *
 * `authored_at` travels with it, and that is the reason this function exists
 * rather than the caller inlining a `fetch`. The outbox stores when a report
 * was WRITTEN and the backend accepts that as `authored_at`, specifically so a
 * blowdown written Monday and flushed Thursday still reads as Monday
 * (lib/outbox.ts, and backend `create_report`). Omitting the field is not a
 * visible failure: the server falls back to its own clock, so every offline
 * report would quietly become a fresh one and the bug would look like correct
 * data.
 */
export async function sendReport(item: OutboxItem): Promise<void> {
  await authedFetch('/reports', {
    method: 'POST',
    // `id` is an idempotency key, not decoration (#243). The server returns
    // the stored report instead of filing a second one, which is what makes
    // the outbox's "a resend is recognisably the same report" true rather
    // than aspirational - the classic trail failure is a request that
    // commits and whose response never arrives.
    body: JSON.stringify({ ...item.payload, id: item.id, authored_at: item.authoredAt }),
  })

  if (item.photo !== undefined) await sendReportPhoto(item.id, item.photo)
}

/**
 * The photo, sent second, because the endpoint needs the row to exist (#234).
 *
 * **A throw from here keeps the whole item queued**, and that is correct
 * rather than wasteful: the next flush re-POSTs the report, which #243 made
 * idempotent, so a retry costs one duplicate request instead of a duplicate
 * report - and the alternative, dropping the item once the report lands,
 * would lose the photo on every hiker whose signal died between the two
 * requests, which out here is most of them.
 *
 * The exception is a refusal retrying cannot fix. The report is already
 * filed by then, so continuing to fail the item would tell a hiker their
 * report is "waiting to send" about one a moderator can already see - a
 * durable lie in exchange for bytes the server will never accept. So the
 * photo is dropped and the item completes.
 *
 * That branch should be unreachable, and it is worth being exact about why,
 * because a swallowed failure is worth suspecting. Every permanent code this
 * endpoint returns is one lib/reportPhoto.ts has already made impossible:
 * 415 needs a content type other than JPEG, which is what the canvas encodes;
 * 413 needs more than 2 MB, which is the ladder's exit condition; 400 needs
 * an empty body, which an encoded canvas is not. It is a valve for a bug in
 * this app's own preparation step, not a path a working client takes.
 */
async function sendReportPhoto(reportId: string, photo: Blob): Promise<void> {
  try {
    await authedFetchBytes(`/reports/${reportId}/photo`, photo)
  } catch (error) {
    if (error instanceof ApiError && PERMANENTLY_UNACCEPTABLE_PHOTO.has(error.status))
      return
    throw error
  }
}

/** The statuses that mean this photo will never be accepted, however often it
 *  is offered. NOT 503 - that is "no bucket on this deployment yet", which is
 *  precisely the case worth waiting out. */
const PERMANENTLY_UNACCEPTABLE_PHOTO = new Set([400, 413, 415])

/**
 * Sends one queued app-failure report (#848).
 *
 * `openFetch` rather than `authedFetch`, which is the whole difference: this
 * is the one write in the app that goes without an account. Signed out,
 * `authedFetch` would throw `NotSignedInError` before spending a request and
 * the report would wait in the queue for an account the hiker has no other
 * reason to make.
 *
 * `authored_at` travels for the same reason it does on a report, and it
 * matters at least as much here: this report is written where the app broke,
 * which is where there is no signal, so days between writing and sending is
 * the ordinary case rather than the edge one.
 */
export async function sendAppFailure(item: OutboxItem): Promise<void> {
  await openFetch('/app-failures', {
    method: 'POST',
    // Idempotent on `id`, exactly as `/reports` is - the request that commits
    // and whose response never arrives is the ordinary one-bar failure.
    body: JSON.stringify({
      ...item.appFailure,
      id: item.id,
      authored_at: item.authoredAt,
    }),
  })
}

/**
 * Sends one queued outbox item, whatever it carries.
 *
 * The outbox holds three families now: condition reports (the original
 * cargo), photo actions (#577/#579 - share, withdraw, report), and
 * app-failure reports (#848). One dispatcher, so `flushOutbox` keeps its
 * single `send` seam and the queue stays one queue - a hiker's unsent work is
 * one list, not three.
 */
export async function sendOutboxItem(item: OutboxItem): Promise<void> {
  if (item.action !== undefined) return sendPhotoAction(item.action, item.photo)
  if (item.appFailure !== undefined) return sendAppFailure(item)
  return sendReport(item)
}

async function sendPhotoAction(
  action: PhotoAction,
  photo: Blob | undefined,
): Promise<void> {
  const base = `/waypoints/${encodeURIComponent(action.poiId)}/photos`

  switch (action.kind) {
    case 'poi_photo_share': {
      try {
        // The two-phase flush #369 established: the row first, the bytes
        // second, either half retry-safe (the row upserts on its identity,
        // the object overwrites at its derived key).
        await authedFetch(base, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ taken: action.taken, flagged: action.flagged }),
        })
      } catch (error) {
        // 409 is "no trail name on the account yet". The sheet only offers
        // a share when the device holds one, so this is a sync gap that
        // heals itself - rethrown as a PLAIN error so the generic
        // classifier's 409 entry (written for duplicate report ids) cannot
        // mark it permanently failed with the wrong sentence.
        if (error instanceof ApiError && error.status === 409) {
          throw new Error('The account has no trail name yet; retried once it does.')
        }
        throw error
      }
      if (photo !== undefined) await authedFetchBytes(`${base}/mine`, photo)
      return
    }
    case 'poi_photo_withdraw':
      try {
        await authedFetch(`${base}/mine`, { method: 'DELETE' })
      } catch (error) {
        // Already gone is a wish already granted.
        if (error instanceof ApiError && error.status === 404) return
        throw error
      }
      return
    case 'poi_photo_report':
      try {
        await authedFetch(`${base}/${encodeURIComponent(action.photoId)}/report`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ reason: action.reason }),
        })
      } catch (error) {
        // The photo rolled out, was withdrawn, or was already taken down
        // between the report being written and the flush reaching signal.
        // Whatever removed it, the report's purpose is served.
        if (error instanceof ApiError && error.status === 404) return
        throw error
      }
      return
  }
}

/** Like `authedFetch`, but sends raw bytes rather than JSON. */
async function authedFetchBytes(path: string, body: Blob): Promise<Response> {
  const token = await accessToken()
  if (token === null) throw new NotSignedInError()

  return apiFetch(path, {
    method: 'PUT',
    body,
    headers: {
      // Stated rather than left to the Blob's own type, which is whatever
      // `toBlob` happened to set. The server checks this header and refuses
      // anything else, so guessing is not an option available to us.
      'Content-Type': PHOTO_CONTENT_TYPE,
      Authorization: `Bearer ${token}`,
    },
  })
}

// An ALLOWLIST, and that is the whole design (#266).
//
// This began as "every 4xx except 401/408/429 is permanent", which stranded a
// report on any status nothing in this stack produces - a captive portal, a
// WAF or a proxy answering 400/451/494 would mark the entire queue
// unsendable, in exactly the network conditions this app exists for. It also
// contradicted the rule written directly below it.
//
// So only the two statuses THIS backend actually returns and means are here.
// Everything else - including 4xx codes that sound final - is somebody else's
// infrastructure talking, and gets retried:
//
//   401  the token was rejected; Supabase refreshes in the background.
//   403  create_report has no role gate, so this is never ours.
//   408  a network symptom wearing a 4xx.
//   413  `POST /reports` enforces no size limit. The photo endpoint does,
//        but a photo refused for size is handled where it happens
//        (`sendReportPhoto`) rather than here, because by then the report
//        itself has already been filed and must not be marked unsendable.
//   429  explicitly "later".
//
// Written for a hiker reading a phone on a ridge, not for a log: each says
// what happened and, where there is one, what they can do about it.
const PERMANENT_REASONS: Record<number, string> = {
  // The likeliest of the two, and partly fixable from their side: the server
  // refuses an authored time more than five minutes ahead, so a phone whose
  // clock runs fast has every report refused.
  //
  // Careful about what this promises. `authored_at` is stamped once when the
  // report is written and is deliberately never re-derived - a report written
  // Monday must still read as Monday when it flushes on Thursday. So fixing
  // the clock does NOT rewrite an already-queued item: it becomes acceptable
  // when real time catches up to the timestamp it is carrying. For a phone
  // seven minutes fast that is a couple of minutes; for one set a day ahead
  // it is a day. Saying "then try again" flatly was a promise this cannot
  // keep.
  422: 'Its date is in the future, so the server would not take it. Check your phone’s clock — if it was far out, this one may not send until that time has passed.',
  409: 'The server already has a different report filed under this one’s id.',
}

// The backend returns 422 for two unrelated reasons, and the entry above is
// written for only one of them (#412).
//
//   1. The `authored_at` refusal, which is this app's own rule and is about
//      the hiker's clock.
//   2. Request validation - a field this build does not send, a value this
//      build still sends and the server has stopped accepting. That is
//      version skew: an old client meeting a newer API, which RELEASING.md
//      §8c's support window exists to bound and cannot prevent past its edge.
//
// They want opposite handling. The clock case is about this one report and
// resolves when real time catches up. Skew is about the whole app, resolves
// when it updates, and telling somebody to check their clock sends them to
// look at a setting that is fine.
//
// Told apart by which field the server named. FastAPI reports validation
// failures as `detail: [{loc: [...], ...}]`, and the `authored_at` rule -
// being a field validator on ReportCreate - names that field in `loc`.
// backend/tests/test_report_authored_at_contract.py pins that shape from the
// other side, because this is a cross-boundary assumption and the client
// cannot notice on its own if the body ever changes.
const AUTHORED_AT_FIELD = 'authored_at'

/** The version-skew message. Exported so tests name it once. */
export const OUTDATED_CLIENT_REASON =
  'This version of the app is too old for the server to accept it. Update the app when you have signal, then try again — your report is kept until you do.'

function namesAuthoredAt(detail: unknown): boolean {
  if (typeof detail !== 'object' || detail === null) return false
  const entries = (detail as { detail?: unknown }).detail
  if (!Array.isArray(entries)) return false

  return entries.some((entry) => {
    const loc = (entry as { loc?: unknown })?.loc
    return Array.isArray(loc) && loc.includes(AUTHORED_AT_FIELD)
  })
}

/**
 * Whether a failed send is worth retrying: a sentence to show the hiker if
 * it is not, or null if it is.
 *
 * The distinction exists because `flushOutbox` treated every failure the
 * same, so a report the server would never accept sat in the queue saying
 * "waiting to send" forever, indistinguishable from one waiting for signal
 * (#243). Anything unrecognised is treated as retryable: keeping a report
 * that might yet go is cheaper than stranding one that would have.
 */
export function permanentFailureReason(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null

  // A 422 that does not name `authored_at` is validation failing on some
  // other field, which this build cannot fix by trying again - but a newer
  // build can, so the message says so and `flushOutbox` retries it once the
  // app version changes rather than stranding it for good.
  if (error.status === 422 && !namesAuthoredAt(error.detail)) {
    return OUTDATED_CLIENT_REASON
  }

  return PERMANENT_REASONS[error.status] ?? null
}

// --- Moderation (#235) ----------------------------------------------------
//
// The queue could be acted on and read by the backend long before anything
// here could call it, so a `bad_hikers` report - one about being followed on
// trail - reached the audience `internal_only` names only if somebody ran
// curl. These are the calls the moderator screen makes.
//
// Every one of them is `authedFetch`: the backend gates all five behind
// `require_role(maintainer, club_admin)`, and this is the first place the
// client has ever cared what a role is.

/** The signed-in user's own profile. Only `role` is read today; the rest is
 *  what `GET /profiles/me` returns and is declared so it is not re-guessed. */
export interface ProfileSummary {
  id: string
  role: 'hiker' | 'maintainer' | 'club_admin'
  display_name: string | null
}

export async function fetchMyProfile(signal?: AbortSignal): Promise<ProfileSummary> {
  // Not `readFetch`: this endpoint IS the identity, so without a token there
  // is no question to ask, and a 401 is the honest answer rather than a
  // guess at an anonymous default.
  const response = await authedFetch('/profiles/me', { method: 'GET', signal })
  return (await response.json()) as ProfileSummary
}

/**
 * A report as a MODERATOR sees it - the whole record, not the public subset.
 *
 * Wider than `ReportSummary` deliberately, and the extra fields are the ones
 * the decision actually turns on: the note and the photo are the evidence,
 * `visibility` is what says this is an incident note about a person rather
 * than a blowdown, and `severity` is what a verify may change.
 */
export interface QueuedReport extends ReportSummary {
  visibility: 'public' | 'internal_only' | 'club_only'
  photo_url: string | null
  reporter_id: string | null
}

/** A closure awaiting review. A line along the trail rather than a pin, which
 *  is why it is a different shape and not a flag on the rows above. */
export interface QueuedClosure {
  id: string
  reason_type: ClosureReason
  note: string | null
  status: ClosureStatus
  start_mile_marker: number
  end_mile_marker: number
  reported_at: string
}

export interface ModerationQueue {
  reports: QueuedReport[]
  closures: QueuedClosure[]
}

/**
 * Everything waiting on a moderator.
 *
 * **Throws rather than returning an empty queue**, for the same reason
 * `fetchReports` does: "nothing is waiting" and "I could not ask" draw the
 * same empty screen and mean opposite things. Here the wrong one of those
 * tells a moderator there are no unreviewed safety reports.
 */
export async function fetchModerationQueue(
  signal?: AbortSignal,
): Promise<ModerationQueue> {
  const response = await authedFetch('/moderation/queue', { method: 'GET', signal })
  return (await response.json()) as ModerationQueue
}

/**
 * Verify a report, optionally saying something about its severity.
 *
 * **`severity` is omitted unless the moderator chose one, and that is not a
 * formality (#251).** The backend treats an absent field as "said nothing"
 * and an explicit `normal` as a de-escalation. Sending `normal` by default
 * would silently clear a `serious` flag another moderator set - which is the
 * flag that puts a warning pin on every phone on the trail.
 */
export async function verifyReport(
  reportId: string,
  severity?: 'normal' | 'serious',
): Promise<void> {
  await authedFetch(`/reports/${reportId}/verify`, {
    method: 'POST',
    body: JSON.stringify(severity === undefined ? {} : { severity }),
  })
}

export async function dismissReport(reportId: string): Promise<void> {
  await authedFetch(`/reports/${reportId}/dismiss`, { method: 'POST', body: '{}' })
}

/**
 * A URL that fetches one report's photo, good for a few minutes (#385).
 *
 * **The reason this is not just `<img src={apiUrl('/reports/x/photo')}>`.**
 * That endpoint uses optional auth and an `<img>` cannot carry a token, so
 * the request goes out anonymous and gets the PUBLIC answer - which for an
 * `internal_only` `bad_hikers` photo is a 404 that renders as a broken image.
 * A moderator would have no way to tell "there is no evidence" from "there is
 * evidence and you are not being shown it", on the one screen built to tell
 * those apart.
 *
 * So the token travels here, on a `fetch` that can carry it, and the URL it
 * answers with goes in `src`. Images are exempt from CORS, so nothing new is
 * needed on the private photo bucket - fetching the bytes cross-origin
 * instead would have needed a CORS policy on the one bucket whose whole
 * design is that nothing reaches it without a check.
 *
 * `readFetch`, not `authedFetch`: the endpoint answers an anonymous caller
 * for a public photo, and a hiker looking at their own report is signed in
 * without being a moderator. The token goes when there is one.
 *
 * **Throws on refusal rather than returning null**, so a caller cannot draw
 * "no photo" over a photo it was refused - the whole failure this replaces.
 */
export async function fetchReportPhotoLink(
  reportId: string,
  signal?: AbortSignal,
): Promise<{ url: string; expiresIn: number }> {
  const response = await readFetch(`/reports/${reportId}/photo/link`, signal)
  const body = (await response.json()) as { url: string; expires_in: number }
  return { url: body.url, expiresIn: body.expires_in }
}

export async function verifyClosure(closureId: string): Promise<void> {
  // No body. A closure is born `closed`, so verifying one says everything
  // that needs saying; the optional `status` covers confirming a reroute,
  // which is a judgment this screen does not yet offer.
  await authedFetch(`/closures/${closureId}/verify`, { method: 'POST', body: '{}' })
}

export async function dismissClosure(closureId: string): Promise<void> {
  await authedFetch(`/closures/${closureId}/dismiss`, { method: 'POST', body: '{}' })
}

/**
 * One row of the photo half of the queue (#579): `PoiPhotoSummary`'s
 * fields plus what a moderator's decision needs. `held` is the one state
 * where a photo exists and no hiker can see it - a nudity flag waiting on
 * its one human glance (#837) - and it sorts first because nothing is
 * published while it waits.
 */
export interface PoiPhotoQueueEntry extends PoiPhotoSummary {
  /** ISO 8601, UTC-designated - when the share landed. */
  shared_at: string
  flagged: string | null
  held: boolean
  reported_reason: string | null
}

export async function fetchPhotoQueue(
  signal?: AbortSignal,
): Promise<PoiPhotoQueueEntry[]> {
  const response = await authedFetch('/moderation/poi-photos', { signal })
  return (await response.json()) as PoiPhotoQueueEntry[]
}

async function photoQueueAction(
  photoId: string,
  verb: string,
): Promise<PoiPhotoQueueEntry> {
  const response = await authedFetch(
    `/moderation/poi-photos/${encodeURIComponent(photoId)}/${verb}`,
    { method: 'POST', body: '{}' },
  )
  return (await response.json()) as PoiPhotoQueueEntry
}

/** Make this one of the place's pinned three. A 409 is the cap: the place
 *  already has three pins, and choosing which comes down is the person's
 *  call, not recency's. */
export async function pinPhoto(photoId: string): Promise<PoiPhotoQueueEntry> {
  return photoQueueAction(photoId, 'pin')
}

export async function unpinPhoto(photoId: string): Promise<PoiPhotoQueueEntry> {
  return photoQueueAction(photoId, 'unpin')
}

/** "Leave it in the twelve": one human looked, the photo is fine where it
 *  is. Clears a hold and answers a report without acting on it. */
export async function reviewPhoto(photoId: string): Promise<PoiPhotoQueueEntry> {
  return photoQueueAction(photoId, 'review')
}

/** The takedown - "Refuse it" on the queue. */
export async function dismissPhoto(photoId: string): Promise<PoiPhotoQueueEntry> {
  return photoQueueAction(photoId, 'dismiss')
}
