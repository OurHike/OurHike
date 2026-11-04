// The phone's usage queue, read out of IndexedDB - what e2e/usageCensus.spec.ts
// counts, and what e2e/supportRooms.spec.ts reads a $0 answer back from.
// One home for where the queue lives (idb-keyval's store, opened only by
// e2e/support/idb.ts, under the key lib/usageQueue.ts writes), so the two
// specs cannot disagree about it.

import { expect, type Page } from '@playwright/test'
import { readIDBEntry, replaceIDBEntry } from './idb'

/** lib/usageQueue.ts's USAGE_KEY. Not imported, for support/seed.ts's
 *  reason: the key is the wire contract with idb-keyval. */
const USAGE_KEY = 'ourhike:usage'

/** One queued row as lib/usageEvents.ts's `usageRow` wrote it: its event
 *  name, and whatever details the event carried. */
export interface QueuedUsageRow {
  event: string
  [detail: string]: unknown
}

/** The part of lib/usageQueue.ts's UsageStore these helpers touch. */
interface StoredUsage {
  rows?: Array<{ row: QueuedUsageRow }>
  session?: { startedAt: number; lastSeenAt: number } | null
}

/** The rows waiting in the phone's usage queue, oldest first. */
export async function queuedUsageRows(page: Page): Promise<QueuedUsageRow[]> {
  const usage = (await readIDBEntry(page, USAGE_KEY)) as StoredUsage | undefined
  return (usage?.rows ?? []).map((queued) => queued.row)
}

/** The events waiting in the phone's usage queue, oldest first. */
export async function queuedEvents(page: Page): Promise<string[]> {
  return (await queuedUsageRows(page)).map((row) => row.event)
}

export function count(events: string[], event: string): number {
  return events.filter((name) => name === event).length
}

/** Moves the visit in progress `minutes` into the past, as if the phone had
 *  been put away that long - the idle gap is half an hour
 *  (lib/usageEvents.ts `SESSION_IDLE_MS`), and a test does not wait it out. */
export async function ageVisit(page: Page, minutes: number): Promise<void> {
  const ms = minutes * 60_000
  await expect
    .poll(async () => {
      const usage = (await readIDBEntry(page, USAGE_KEY)) as StoredUsage | undefined
      const session = usage?.session
      // No visit in progress: nothing to move.
      if (!session) return true
      const aged = {
        ...usage,
        session: {
          ...session,
          startedAt: session.startedAt - ms,
          lastSeenAt: session.lastSeenAt - ms,
        },
      }
      return replaceIDBEntry(page, USAGE_KEY, usage, aged)
    })
    .toBe(true)
}
