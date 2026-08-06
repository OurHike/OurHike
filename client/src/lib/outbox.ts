// The offline outbox (WIREFRAMES.md Interactions, and `9c`).
//
// "Every write queues in an outbox with its authored timestamp and syncs
// later. Nothing blocks on network." On this trail that is the normal path,
// not the edge case - most reports are written with no signal at all.
//
// Four properties do the real work. The last three were promised by an
// earlier version of this comment and not actually kept; #243 is where each
// one got a mechanism.
//
//  1. The AUTHORED time travels with the item. A report written Monday and
//     flushed Thursday still reads as Monday, because the server accepts
//     `authored_at` rather than stamping arrival time. Without this a
//     maintainer reads a three-day-old blowdown as fresh.
//
//  2. A failed send leaves the item queued. The usual cause is no signal,
//     and the report is the only copy of something someone wrote down.
//
//  3. Flushing twice cannot file the same report twice. The item's `id`
//     goes to the server as an idempotency key, so a request that commits
//     and then loses its response - the classic one-bar failure - costs a
//     duplicate request rather than a duplicate report. This used to be
//     asserted here with nothing behind it: the id was never sent anywhere.
//
//  4. A report written DURING a flush survives it. Sent items are removed
//     one at a time rather than by writing back a snapshot taken before the
//     sending started; that snapshot erased anything enqueued in between.
//
// What is deliberately NOT here: retrying forever. A report the server will
// never accept is marked with a `failure` and shown to the hiker on the More
// screen, because "waiting to send" is a lie once it has stopped being true.

import { get, set } from 'idb-keyval'

export const OUTBOX_KEY = 'ourhike:outbox'

export interface ReportDraft {
  type:
    | 'blowdown'
    | 'trash'
    | 'bad_hikers'
    | 'flooding'
    | 'shelter_repair'
    | 'animals'
    // Problem plants or animals disrupting the local environment. Distinct
    // from 'animals', which is a safety encounter - see
    // features/REPORT_A_PROBLEM.md.
    | 'invasive_species'
    // A comment about a specific place rather than a trail condition - see
    // features/SAYING_THANKS.md. Shares this whole shape, which is why it is
    // a report type instead of a second model.
    | 'thanks'
  reporter_type: 'thru' | 'section' | 'day' | 'maintainer'
  note?: string
  poi_id?: string
  lat?: number
  lon?: number
  photo_url?: string
  /** Thanks only, and both optional - see SAYING_THANKS.md. Either may be
   *  absent: not knowing who to thank is the ordinary case, and the server
   *  resolves it from location and authored date instead. */
  maintainer_id?: string
  club_id?: string
}

/** Why a report will never be accepted, and when we found that out. */
export interface OutboxFailure {
  /** Shown to the hiker verbatim, so it has to read like a sentence. */
  reason: string
  at: string
}

export interface OutboxItem {
  /**
   * Stable across retries, so a resend is recognisably the same report -
   * and, since #243, actually sent: `POST /reports` takes it as an
   * idempotency key, so a request that commits server-side and loses its
   * response costs a duplicate request rather than a duplicate report.
   */
  id: string
  authoredAt: string
  payload: ReportDraft
  /**
   * Set when the server refused this in a way retrying cannot fix.
   *
   * A marked item is kept, not deleted - it is still the only copy of
   * something a hiker wrote down - but it is skipped by future flushes and
   * surfaced on the More screen, because "waiting to send" forever is a lie
   * a phone with a wrong clock would otherwise tell indefinitely.
   */
  failure?: OutboxFailure
}

export interface FlushResult {
  sent: number
  /** Everything not delivered this time round, `stuck` included. */
  failed: number
  /** Refused permanently and now marked. A subset of `failed`. */
  stuck: number
}

export type SendFn = (item: OutboxItem) => Promise<unknown>

/**
 * Classifies a thrown send error: a sentence to show the hiker if this can
 * never succeed, or null if it is worth retrying.
 *
 * Injected rather than imported so this module stays about storage and
 * knows nothing about HTTP - lib/api.ts owns the status codes, and
 * lib/outboxSync.ts is what introduces them to each other.
 */
export type ClassifyFn = (error: unknown) => string | null

/** Everything is worth retrying. The old behaviour, kept as the default so
 *  a caller that has no opinion cannot accidentally discard a report. */
const RETRY_EVERYTHING: ClassifyFn = () => null

async function readQueue(): Promise<OutboxItem[]> {
  // A fresh install has never written the key; that is not an error state.
  return (await get(OUTBOX_KEY)) ?? []
}

export async function listQueued(): Promise<OutboxItem[]> {
  return readQueue()
}

export async function enqueue(
  payload: ReportDraft,
  authoredAt: Date = new Date(),
): Promise<OutboxItem> {
  const item: OutboxItem = {
    id: crypto.randomUUID(),
    authoredAt: authoredAt.toISOString(),
    payload,
  }

  await set(OUTBOX_KEY, [...(await readQueue()), item])
  return item
}

export async function removeQueued(id: string): Promise<void> {
  const queue = await readQueue()
  await set(
    OUTBOX_KEY,
    queue.filter((item) => item.id !== id),
  )
}

/** Clears a permanent failure so the next flush tries the item again.
 *
 *  The escape hatch for the cause that is fixable from the hiker's side: a
 *  phone whose clock was wrong has every report refused, and once the clock
 *  is right there is nothing wrong with the reports. */
export async function retryQueued(id: string): Promise<void> {
  const queue = await readQueue()
  await set(
    OUTBOX_KEY,
    queue.map((item) => {
      if (item.id !== id) return item
      const { failure: _failure, ...cleared } = item
      return cleared
    }),
  )
}

export async function flushOutbox(
  send: SendFn,
  classify: ClassifyFn = RETRY_EVERYTHING,
): Promise<FlushResult> {
  const queue = await readQueue()
  if (queue.length === 0) return { sent: 0, failed: 0, stuck: 0 }

  let sent = 0
  let failed = 0
  let stuck = 0

  for (const item of queue) {
    // Already known to be unacceptable. Retrying it would spend signal to
    // be refused again, and would keep resetting a failure the hiker is
    // being shown.
    if (item.failure !== undefined) {
      failed += 1
      stuck += 1
      continue
    }

    try {
      await send(item)
      // Removed one at a time, and this is the fix rather than a tidy-up.
      // The old loop collected survivors and wrote the whole key at the end
      // (`set(OUTBOX_KEY, unsent)`), so a report written DURING a flush was
      // appended to the key and then overwritten by that final write - gone
      // from IndexedDB without ever being sent, which is the one thing an
      // outbox exists to prevent. removeQueued re-reads and filters, so it
      // cannot clobber an item it never saw.
      await removeQueued(item.id)
      sent += 1
    } catch (error) {
      failed += 1
      const reason = classify(error)
      if (reason === null) {
        // The usual cause is simply no signal. Left exactly as it was.
        continue
      }
      await markFailed(item.id, reason)
      stuck += 1
    }
  }

  return { sent, failed, stuck }
}

async function markFailed(id: string, reason: string): Promise<void> {
  const queue = await readQueue()
  await set(
    OUTBOX_KEY,
    queue.map((item) =>
      item.id === id
        ? { ...item, failure: { reason, at: new Date().toISOString() } }
        : item,
    ),
  )
}
