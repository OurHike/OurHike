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

import { get, set, update } from 'idb-keyval'

import { accessToken, apiFetch, API_CONFIGURED } from './api'
import {
  FRESH_HEARTBEAT,
  type Heartbeat,
  normaliseHeartbeat,
  type QueuedUsageRow,
  type UsageRow,
} from './usageEvents'

export const USAGE_KEY = 'ourhike:usage'

/** EVENTING.md §8's cap: about 200 rows, the oldest dropped first. */
export const MAX_QUEUED = 200

/** The server's own per-batch ceiling (app/schemas/analytics.py). */
export const BATCH_SIZE = 200

/** A visit in progress, kept so a phone that kills the app still reports it. */
export interface PendingSession {
  startedAt: number
  lastSeenAt: number
  pageviews: number
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
}

export const EMPTY_USAGE: UsageStore = {
  rows: [],
  heartbeat: FRESH_HEARTBEAT,
  session: null,
  initialized: false,
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

/** Add rows, keeping the newest `MAX_QUEUED`. */
export function withRows(store: UsageStore, rows: readonly QueuedUsageRow[]): UsageStore {
  const all = [...store.rows, ...rows]
  return {
    ...store,
    rows: all.length > MAX_QUEUED ? all.slice(all.length - MAX_QUEUED) : all,
  }
}

/**
 * Measurement switched off: everything waiting goes, and the heartbeat with
 * it. "Off means collection stops" (EVENTING.md §9) - rows recorded before the
 * switch was turned are not quietly sent afterwards.
 */
export async function clearUsage(): Promise<void> {
  try {
    await set(USAGE_KEY, { ...EMPTY_USAGE, initialized: true })
  } catch {
    // Nothing more to do: an unwritable store sends nothing either.
  }
}

/**
 * The hiker said no to linking: rows recorded under their yes leave without
 * the account. Still counted - "Share usage statistics" is still on, and a
 * no to linking is a no to the account, not to the count.
 */
export async function unlinkWaitingRows(): Promise<void> {
  await updateUsage((store) => ({
    ...store,
    rows: store.rows.map((queued) => ({ ...queued, linkedTo: null })),
  }))
}

export type SendResult = 'sent' | 'refused' | 'later'

/** The HTTP status an error carries, if any - lib/api.ts's ApiError has one. */
function statusOf(error: unknown): number | null {
  const status = (error as { status?: unknown } | null)?.status
  return typeof status === 'number' ? status : null
}

/**
 * One batch to `POST /usage-events`. A linked batch carries the token; no
 * other does.
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
  linked: boolean,
): Promise<SendResult> {
  try {
    if (!API_CONFIGURED) return 'later'
    const token = linked ? await accessToken() : null
    await apiFetch('/usage-events', {
      method: 'POST',
      credentials: 'omit',
      headers: {
        'Content-Type': 'application/json',
        ...(token === null ? {} : { Authorization: `Bearer ${token}` }),
      },
      body: JSON.stringify({ identified: token !== null, events: rows }),
    })
    return 'sent'
  } catch (error) {
    const status = statusOf(error)
    if (status !== null && status >= 400 && status < 500) {
      return status === 408 || status === 429 ? 'later' : 'refused'
    }
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
): Promise<number> {
  if (inFlight !== null) return inFlight
  inFlight = (async () => {
    let gone = 0
    try {
      const { rows } = await readUsage()
      const linkable = (queued: QueuedUsageRow) =>
        linkedAccount !== null && queued.linkedTo === linkedAccount
      for (const linked of [false, true]) {
        const waiting = rows.filter((queued) => linkable(queued) === linked)
        for (let start = 0; start < waiting.length; start += BATCH_SIZE) {
          const batch = waiting.slice(start, start + BATCH_SIZE)
          const result = await send(
            batch.map((queued) => queued.row),
            linked,
          )
          if (result === 'later') return gone
          const ids = new Set(batch.map((queued) => queued.row.id))
          await updateUsage((store) => ({
            ...store,
            rows: store.rows.filter((queued) => !ids.has(queued.row.id)),
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
