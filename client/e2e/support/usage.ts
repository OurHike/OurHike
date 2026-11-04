// The phone's usage queue, read out of IndexedDB - what e2e/usageCensus.spec.ts
// counts, and what e2e/supportRooms.spec.ts reads a $0 answer back from.
// One home for the read, so the two specs cannot disagree about where the
// queue lives (idb-keyval's store, the `ourhike:usage` key lib/usageQueue.ts
// writes).

import type { Page } from '@playwright/test'

/** One queued row as lib/usageEvents.ts's `usageRow` wrote it: its event
 *  name, and whatever details the event carried. */
export interface QueuedUsageRow {
  event: string
  [detail: string]: unknown
}

/** The rows waiting in the phone's usage queue, oldest first. */
export function queuedUsageRows(page: Page): Promise<QueuedUsageRow[]> {
  return page.evaluate(
    () =>
      new Promise<QueuedUsageRow[]>((resolve, reject) => {
        const open = indexedDB.open('keyval-store')
        open.onupgradeneeded = () => open.result.createObjectStore('keyval')
        open.onerror = () => reject(open.error)
        open.onsuccess = () => {
          const read = open.result
            .transaction('keyval', 'readonly')
            .objectStore('keyval')
            .get('ourhike:usage')
          read.onerror = () => reject(read.error)
          read.onsuccess = () => {
            const rows = (read.result?.rows ?? []) as Array<{ row: QueuedUsageRow }>
            resolve(rows.map((queued) => queued.row))
          }
        }
      }),
  )
}

/** The events waiting in the phone's usage queue, oldest first. */
export async function queuedEvents(page: Page): Promise<string[]> {
  return (await queuedUsageRows(page)).map((row) => row.event)
}

export function count(events: string[], event: string): number {
  return events.filter((name) => name === event).length
}
