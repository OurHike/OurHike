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
import type { OutboxItem } from './outbox'
import type { BackendReportStatus } from './reportStatus'
import type { ClosureReason, ClosureStatus } from './closureBanner'

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

/** A request that reached the server and came back refused. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
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
    )
  }
  return response
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
 * What `GET /reports` returns, limited to the fields this app reads.
 *
 * The backend sends more (`received_at`, `follow_up`, `club_id` and the rest
 * of `ReportOut`); declaring only what is consumed keeps this honest about
 * what the client actually depends on rather than mirroring a schema it does
 * not use.
 *
 * `mile` is deliberately absent, because the backend does not send one - see
 * #244. Anything wanting to place a report along the trail has to derive it.
 */
export interface ReportSummary {
  id: string
  type: string
  reporter_type: string
  status: BackendReportStatus
  severity: 'normal' | 'serious'
  lat: number | null
  lon: number | null
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

/** What `GET /closures` returns, limited to the fields this app reads. */
export interface ClosureSummary {
  id: string
  reason_type: ClosureReason
  note: string | null
  status: ClosureStatus
  start_mile_marker: number
  end_mile_marker: number
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
//   413  no size limit is enforced yet; revisit when photos land (#234).
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

  return PERMANENT_REASONS[error.status] ?? null
}
