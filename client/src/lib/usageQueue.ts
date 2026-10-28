// Where usage events wait for signal, and how they leave (#1902,
// features/EVENTING.md §0 and §8).
//
// ITS OWN QUEUE, NOT A CARGO TYPE IN THE OUTBOX, and deliberately. The outbox
// (lib/outbox.ts) is the hiker's own work - reports, notes, hours - and every
// item in it is counted on the More screen as "waiting to send". A usage row
// is not the hiker's work and must never be counted as theirs, and EVENTING.md
// §1 rule 4 says it may not compete with a report for storage, bandwidth or
// the sync: this queue is capped, drops its oldest rows first, and is only
// sent once the outbox is empty (lib/useUsageMeasurement.ts).
//
// FIRE AND FORGET. A refused batch (a 4xx other than a timeout or a rate
// limit) is dropped - the server will never take it, and nothing here is
// worth a retry loop or a message to the hiker. A batch that could not be
// delivered stays for the next chance. The server refuses ROWS rather than
// batches since #1902's accuracy pass, so one row with a wrong date costs
// that row and not the 199 sent with it - and the server counts what it
// refused, which is how a release that breaks a row shows up at all.

import { get, update } from 'idb-keyval'

import { accountTag } from './accountTag'
import { accessToken, apiFetch, API_CONFIGURED } from './api'
import {
  FRESH_HEARTBEAT,
  type Heartbeat,
  LEVEL_ONLY_EVENTS,
  normaliseHeartbeat,
  type QueuedUsageRow,
  type UsageDetails,
  type UsageRow,
} from './usageEvents'

export const USAGE_KEY = 'ourhike:usage'

/** EVENTING.md §8's cap: about 200 rows, the oldest dropped first. */
export const MAX_QUEUED = 200

/** The server's own per-batch ceiling (app/schemas/analytics.py). */
export const BATCH_SIZE = 200

/**
 * How long one batch may take before it is given up for the next chance.
 * Reasoned rather than measured: a full batch is 45 to 65 KB (#1903's second
 * review measured the golden rows at 326 bytes each), which is about 52 s at
 * 10 kbit/s, a bar of EDGE. Without one, a request that never answered held
 * the flush, and every later flush in that page waited on it.
 */
export const SEND_TIMEOUT_MS = 60_000

/**
 * How long to wait when the server says not now (503 or 429) without saying
 * for how long, or answers as if the route were not there (404, 405) or the
 * envelope were newer than it (422) - a server deployed after this build, or
 * rolled back past it. Each of those was a refusal before #1903's second
 * review, and a refusal drops the batch: every row a phone sent between the
 * app shipping and the server catching up would have been lost. The server's
 * own 503 says 3600 (app/routers/analytics.py), so its wait is honoured
 * instead, up to `MAX_WAIT_MS`.
 */
export const DEFAULT_WAIT_MS = 60 * 60 * 1000

/** The longest wait honoured. A `notBefore` further ahead than this was set by
 *  a clock since moved back, and is ignored rather than waited out. */
export const MAX_WAIT_MS = 6 * 60 * 60 * 1000

/** A visit in progress, kept so a phone that kills the app still reports it. */
export interface PendingSession {
  startedAt: number
  lastSeenAt: number
  pageviews: number
  /**
   * Who the visit belonged to, as it began: the account a row may be linked
   * to and whether one was signed in. Read when the visit ENDS, which can be
   * a launch later and after a sign-in or out - and a signed-out visit must
   * not come out linked because somebody signed in before it was sent.
   */
  linkedTo?: string | null
  signedIn?: boolean
  /**
   * The first fix the map held during the visit that measurement may use,
   * and the club under it. A fix checked at the visit's end against the
   * moment it began reads as one from the future and is dropped, which left
   * every visit row without a club (#1903's review).
   */
  fix?: UsageDetails['fix']
  clubs?: Record<string, number>
}

export interface UsageStore {
  rows: QueuedUsageRow[]
  heartbeat: Heartbeat
  session: PendingSession | null
  /**
   * Whether this install's first launch has been accounted for - an
   * `app_installed` sent, or the install found to predate measurement.
   */
  initialized: boolean
  /**
   * "Share usage statistics" was switched off, and has not been switched back
   * on, IN THE STORE every tab shares. A second tab still holding "on" in its
   * own state records nothing while this is set, and a flush stops at it -
   * the switch does not depend on every open copy of the app having heard.
   */
  off: boolean
  /** Nothing is sent before this moment (ms): the server asked for time. */
  notBefore: number
  /**
   * Rows this phone dropped and the server never saw: at the queue's cap
   * (`full`), or with a batch the server refused whole (`refused`). Sent with
   * the next batch and taken off once it is answered, so the nightly checks
   * can tell "less use" from "phones overflowed" (#1903's second review).
   */
  dropped: Dropped
}

export interface Dropped {
  full: number
  refused: number
}

const NONE_DROPPED: Dropped = { full: 0, refused: 0 }

export const EMPTY_USAGE: UsageStore = {
  rows: [],
  heartbeat: FRESH_HEARTBEAT,
  session: null,
  initialized: false,
  off: false,
  notBefore: 0,
  dropped: NONE_DROPPED,
}

function count(raw: unknown): number {
  return typeof raw === 'number' && Number.isFinite(raw) && raw > 0 ? Math.floor(raw) : 0
}

function normaliseDropped(raw: unknown): Dropped {
  const dropped = (typeof raw === 'object' && raw !== null ? raw : {}) as Record<
    string,
    unknown
  >
  return { full: count(dropped.full), refused: count(dropped.refused) }
}

function queuedRow(raw: unknown): QueuedUsageRow | null {
  if (typeof raw !== 'object' || raw === null) return null
  const queued = raw as { row?: unknown; linkedTo?: unknown }
  if (typeof queued.row !== 'object' || queued.row === null) return null
  // A row written before rows were bound to an account carries no account to
  // check a token against, so it goes without one.
  return {
    row: queued.row as UsageRow,
    linkedTo: typeof queued.linkedTo === 'string' ? queued.linkedTo : null,
  }
}

function normalise(raw: unknown): UsageStore {
  if (typeof raw !== 'object' || raw === null) return EMPTY_USAGE
  const store = raw as Partial<Record<keyof UsageStore, unknown>>
  return {
    rows: Array.isArray(store.rows)
      ? store.rows.map(queuedRow).filter((row): row is QueuedUsageRow => row !== null)
      : [],
    heartbeat: normaliseHeartbeat(store.heartbeat),
    session: (store.session as PendingSession | null | undefined) ?? null,
    initialized: store.initialized === true,
    off: store.off === true,
    notBefore: count(store.notBefore),
    dropped: normaliseDropped(store.dropped),
  }
}

export async function readUsage(): Promise<UsageStore> {
  try {
    return normalise(await get(USAGE_KEY))
  } catch {
    return EMPTY_USAGE
  }
}

/** Read-modify-write in one IndexedDB transaction, so two writers cannot lose a row. */
export async function updateUsage(
  change: (store: UsageStore) => UsageStore,
): Promise<UsageStore> {
  let written = EMPTY_USAGE
  try {
    await update(USAGE_KEY, (raw) => {
      written = change(normalise(raw))
      return written
    })
  } catch {
    // Storage refused: measurement is the first thing a phone may lose.
  }
  return written
}

/**
 * Whether a row is the one that counts something no later row repeats: its
 * phone in some period or club, or a support answer, which is counted by its
 * one row and no other (`LEVEL_ONLY_EVENTS`).
 */
function countsAlone(row: UsageRow): boolean {
  return (
    LEVEL_ONLY_EVENTS.includes(row.event) ||
    row.week_first ||
    row.month_first ||
    row.ever_first ||
    row.kind_month_first === true ||
    // A row queued by an older build may predate the field.
    (Array.isArray(row.club_firsts) && row.club_firsts.length > 0)
  )
}

/**
 * Add rows, keeping `MAX_QUEUED` - and when some must go, the oldest rows
 * that count nothing go first.
 *
 * Oldest-first alone dropped exactly the wrong rows on a long stretch without
 * signal: a phone's first row of a week, a month or a club is its OLDEST, and
 * the heartbeat has already marked that period counted, so losing the row
 * lost the phone from the period entirely (#1903's review). A visit or a map
 * view after it in the same period counts nothing the first row did not.
 * Rows recorded while the switch is off are refused here, whichever tab
 * recorded them.
 */
export function withRows(store: UsageStore, rows: readonly QueuedUsageRow[]): UsageStore {
  if (store.off) return store
  const all = [...store.rows, ...rows]
  let excess = all.length - MAX_QUEUED
  if (excess <= 0) return { ...store, rows: all }
  const dropped = { ...store.dropped, full: store.dropped.full + excess }
  const keep = all.map(() => true)
  for (const pass of [false, true]) {
    for (let index = 0; index < all.length && excess > 0; index += 1) {
      if (keep[index] && countsAlone(all[index].row) === pass) {
        keep[index] = false
        excess -= 1
      }
    }
  }
  return { ...store, dropped, rows: all.filter((_, index) => keep[index]) }
}

/**
 * Measurement switched off: everything waiting goes, the visit in progress
 * with it, and nothing is recorded or sent until it is switched back on.
 * "Off means collection stops" (EVENTING.md §9) - rows recorded before the
 * switch was turned are not quietly sent afterwards.
 *
 * WHICH PERIODS WERE ALREADY COUNTED STAYS - the weeks, months and kinds, and
 * whether this install ever counted. Clearing them made a phone switched off
 * and on again count as a new phone, a second time in the same week and
 * month (#1903's review). The clubs it was counted in go: they say where the
 * hiker has been, and nothing needs them once their month's rows are gone.
 */
export async function clearUsage(): Promise<void> {
  await updateUsage((store) => ({
    ...EMPTY_USAGE,
    heartbeat: { ...store.heartbeat, clubs: {} },
    initialized: true,
    off: true,
  }))
}

/** Measurement switched back on: recording and sending resume. */
export async function resumeUsage(): Promise<void> {
  await updateUsage((store) => (store.off ? { ...store, off: false } : store))
}

/**
 * The hiker said no to linking: rows recorded under their yes leave without
 * the account. Still counted - "Share usage statistics" is still on, and a
 * no to linking is a no to the account, not to the count. The visit still in
 * progress loses its account too: it is recorded with the account it began
 * with, so left alone it would end, after the no, carrying the tag of the
 * account that said it.
 */
export async function unlinkWaitingRows(): Promise<void> {
  await updateUsage((store) => ({
    ...store,
    rows: store.rows.map((queued) => ({ ...queued, linkedTo: null })),
    session: store.session === null ? null : { ...store.session, linkedTo: null },
  }))
}

/**
 * What became of a batch. `later`: not delivered, try at the next chance.
 * A `Wait`: the server asked for time, and nothing is sent until it passes.
 */
export type SendResult = 'sent' | 'refused' | 'later' | Wait

export interface Wait {
  waitMs: number
}

/** `Retry-After` in seconds, as this server sends it, bounded; or the default. */
function waitFor(retryAfter: unknown): Wait {
  const seconds = typeof retryAfter === 'string' ? Number(retryAfter.trim()) : NaN
  if (!Number.isFinite(seconds) || seconds <= 0) return { waitMs: DEFAULT_WAIT_MS }
  return { waitMs: Math.min(seconds * 1000, MAX_WAIT_MS) }
}

/**
 * The account a session token belongs to, as lib/accountTag.ts tags it, or
 * null. Read from the token's own payload - Supabase puts the address in its
 * `email` claim - so a token is matched to the account it was issued for and
 * not to whoever the app believes is signed in. Nothing is verified here; the
 * server does that. This only decides whether to attach the token at all.
 */
function tokenAccount(token: string): string | null {
  try {
    const part = token.split('.')[1]
    const json = atob(part.replace(/-/g, '+').replace(/_/g, '/'))
    const email = (JSON.parse(json) as { email?: unknown }).email
    return typeof email === 'string' && email !== '' ? accountTag(email) : null
  } catch {
    return null
  }
}

/** The HTTP status an error carries, if any - lib/api.ts's ApiError has one. */
function statusOf(error: unknown): number | null {
  const status = (error as { status?: unknown } | null)?.status
  return typeof status === 'number' ? status : null
}

/**
 * One batch to `POST /usage-events`. A linked batch carries the token - and
 * only when the session's token belongs to `account`, the account the rows
 * were recorded under; otherwise the batch goes without one. The check is
 * here, at the moment of sending, because a session can change between a
 * flush starting and its second batch leaving (another tab signing somebody
 * else in): one hiker's rows must never leave with another's token.
 *
 * NOTHING HERE MAY THROW, the whole body inside the `try` and the catch
 * reading `status` rather than `instanceof ApiError`. A count is the last
 * thing that may break anything (EVENTING.md §1 rule 4), and the App tests
 * proved the gap: they replace lib/api with partial mocks that export no
 * `apiFetch` and no `ApiError`, so reaching for either outside a `try` turned
 * a background flush into an unhandled error in CI (#1903's first runs).
 */
export async function sendUsageBatch(
  rows: UsageRow[],
  account: string | null,
  dropped: Dropped = NONE_DROPPED,
): Promise<SendResult> {
  try {
    if (!API_CONFIGURED) return 'later'
    const session = account === null ? null : await accessToken()
    const token = session !== null && tokenAccount(session) === account ? session : null
    // A LINKED BATCH WITH NO TOKEN FOR ITS ACCOUNT WAITS. Sent without one it
    // was stored unlinked for good - a resend with a fresh token is a
    // duplicate, and cannot link it - after any hour offline long enough for
    // the token to expire and one bar too weak to refresh it (#1903's second
    // review). It cannot wait forever: a sign-out or a no to linking takes
    // the account off waiting rows (`unlinkWaitingRows`), and they go then.
    if (account !== null && token === null) return 'later'
    const abort = new AbortController()
    const timer = setTimeout(() => abort.abort(), SEND_TIMEOUT_MS)
    try {
      await apiFetch('/usage-events', {
        method: 'POST',
        credentials: 'omit',
        signal: abort.signal,
        headers: {
          'Content-Type': 'application/json',
          ...(token === null ? {} : { Authorization: `Bearer ${token}` }),
        },
        body: JSON.stringify({
          identified: token !== null,
          events: rows,
          ...(dropped.full + dropped.refused > 0 ? { dropped } : {}),
        }),
      })
    } finally {
      clearTimeout(timer)
    }
    return 'sent'
  } catch (error) {
    const status = statusOf(error)
    if (status === 503 || status === 429)
      return waitFor((error as { retryAfter?: unknown }).retryAfter)
    if (status === 404 || status === 405 || status === 422)
      return { waitMs: DEFAULT_WAIT_MS }
    if (status !== null && status >= 400 && status < 500 && status !== 408)
      return 'refused'
    return 'later'
  }
}

let inFlight: Promise<number> | null = null

/**
 * Send what is waiting, linked rows and anonymous rows in separate batches.
 * Returns how many rows left the queue. Overlapping calls share one flush.
 *
 * `linkedAccount` is `accountTag` of the account signed in now with its yes
 * standing, or null. A row goes linked only when it was recorded under that
 * same account; a row recorded under another account, or before a sign-out,
 * goes without one - counted, and never attributed to whoever holds the
 * phone today.
 */
export function flushUsage(
  send: typeof sendUsageBatch = sendUsageBatch,
  linkedAccount: string | null = null,
  holdLinked: () => Promise<boolean> = async () => false,
): Promise<number> {
  if (inFlight !== null) return inFlight
  inFlight = (async () => {
    let gone = 0
    try {
      const linkable = (queued: QueuedUsageRow) =>
        linkedAccount !== null && queued.linkedTo === linkedAccount
      // Each row is offered once per flush, so a store that refuses the write
      // removing a sent batch cannot turn this into a loop resending it.
      const offered = new Set<string>()
      // THE STORE IS READ AGAIN BEFORE EVERY BATCH, not once at the start. A
      // batch on one bar of signal takes seconds, and the switch turned off,
      // or a no to linking, during the first must reach the second: off stops
      // the flush, and a row unlinked meanwhile leaves without the account.
      for (const linked of [false, true]) {
        // Linked rows wait while a consent answer given here has not reached
        // the account: the server reads the account's answers, so a yes not
        // yet synced stored them unlinked for good, and an on after an off
        // had them declined and dropped (#1903's second review).
        if (linked && (await holdLinked())) return gone
        for (;;) {
          const store = await readUsage()
          if (store.off) return gone
          const now = Date.now()
          if (store.notBefore > now && store.notBefore - now <= MAX_WAIT_MS) return gone
          const batch = store.rows
            .filter(
              (queued) => !offered.has(queued.row.id) && linkable(queued) === linked,
            )
            .slice(0, BATCH_SIZE)
          if (batch.length === 0) break
          for (const queued of batch) offered.add(queued.row.id)
          const { dropped } = store
          const result = await send(
            batch.map((queued) => queued.row),
            linked ? linkedAccount : null,
            dropped,
          )
          if (result === 'later') return gone
          if (typeof result === 'object') {
            const waitMs = result.waitMs
            await updateUsage((current) => ({
              ...current,
              notBefore: Date.now() + waitMs,
            }))
            return gone
          }
          const ids = new Set(batch.map((queued) => queued.row.id))
          await updateUsage((current) => ({
            ...current,
            rows: current.rows.filter((queued) => !ids.has(queued.row.id)),
            // What went with this batch is the server's to count now - and a
            // refused batch's rows join what is dropped, for the next one.
            dropped: {
              full: Math.max(
                0,
                current.dropped.full - (result === 'sent' ? dropped.full : 0),
              ),
              refused:
                Math.max(
                  0,
                  current.dropped.refused - (result === 'sent' ? dropped.refused : 0),
                ) + (result === 'refused' ? batch.length : 0),
            },
          }))
          gone += batch.length
        }
      }
    } catch {
      // Whatever went wrong, the rows that had not gone are still queued for
      // the next chance - and a background count never rejects at its caller.
    }
    return gone
  })().finally(() => {
    inFlight = null
  })
  return inFlight
}
