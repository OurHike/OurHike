// The offline outbox (WIREFRAMES.md Interactions, and `9c`).
//
// "Every write queues in an outbox with its authored timestamp and syncs
// later. Nothing blocks on network." On this trail that is the normal path,
// not the edge case - most reports are written with no signal at all.
//
// Two properties do the real work:
//
//  1. The AUTHORED time travels with the item. A report written Monday and
//     flushed Thursday still reads as Monday, because the server accepts
//     `authored_at` rather than stamping arrival time. Without this a
//     maintainer reads a three-day-old blowdown as fresh.
//
//  2. A failed send leaves the item queued. The queue is rewritten to exactly
//     the items that did NOT get through, so a flush that half-succeeds
//     neither loses the successes nor drops the failures - and flushing twice
//     cannot file the same report twice.

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

export interface OutboxItem {
  /** Stable across retries, so a resend is recognisably the same report. */
  id: string
  authoredAt: string
  payload: ReportDraft
}

export interface FlushResult {
  sent: number
  failed: number
}

export type SendFn = (item: OutboxItem) => Promise<unknown>

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

export async function flushOutbox(send: SendFn): Promise<FlushResult> {
  const queue = await readQueue()
  if (queue.length === 0) return { sent: 0, failed: 0 }

  const unsent: OutboxItem[] = []
  let sent = 0

  for (const item of queue) {
    try {
      await send(item)
      sent += 1
    } catch {
      // Kept, not dropped - the usual cause is simply no signal, and the
      // report is the only copy of something a hiker took the trouble to
      // write down.
      unsent.push(item)
    }
  }

  await set(OUTBOX_KEY, unsent)
  return { sent, failed: unsent.length }
}
