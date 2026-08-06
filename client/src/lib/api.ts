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
    body: JSON.stringify({ ...item.payload, authored_at: item.authoredAt }),
  })
}
