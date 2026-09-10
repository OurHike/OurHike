// Reports this phone has sent (#1373, frame 9d) - the ledger "Your reports"
// reads its sent rows from.
//
// WHY A LEDGER AND NOT A QUERY. `GET /reports` returns a signed-in hiker's
// own rows at any status alongside the public set, and nothing in the
// response says which rows are theirs: `ReportOut` carries no reporter id,
// deliberately (#252 - the id is an account UUID, withheld from everyone).
// So the phone remembers what it sent. The server keeps the client's id
// (`Report.id` is the outbox item's own UUID, the idempotency key of #243),
// which is what lets a row here find its status in the live list by id
// alone.
//
// WHAT IT HOLDS is facts about this phone's own acts: which report, of what
// type, at which place, written when and sent when. NOT a copy of the
// report - the note and the photo leave with the send and are not kept.
// **#967 — Decide what a phone keeps of the notes and photos its hiker has
// sent** is where retention gets decided, and until it does a "sent" row
// prints what the phone did rather than what it said. The status is the
// server's fact and is read from the live list where the id matches, never
// cached here (#1373, D14: figures never outrun their source).
//
// PHONE-LOCAL, like lib/hikerMode.ts: a report sent from this phone is a
// fact about this phone whatever account sent it, so signing out does not
// clear it, and nothing about it syncs.
//
// CAPPED at SENT_REPORTS_MAX, newest kept. @unvalidated - a round number,
// chosen so the store stays a small list to walk on a phone that reads it
// once per visit to the screen. What would settle it is the distribution of
// reports per account in the backend, which nobody has queried; the
// moderation queue's own pages would be the place to look.

import { get, set } from 'idb-keyval'

import type { OutboxItem, ReportDraft } from './outbox'

export const SENT_REPORTS_KEY = 'ourhike:sent-reports'
export const SENT_REPORTS_MAX = 200

export interface SentReport {
  /** The report's id - the outbox item's, which the server kept (#243). */
  id: string
  type: ReportDraft['type']
  poiId: string | null
  /** Miles from the southern terminus as the phone measured it, or null. */
  mile: number | null
  /** When it was written - the outbox item's `authoredAt`, the moment of
   *  the tap - so a report written Monday and sent Thursday still says
   *  Monday, the outbox's own rule. */
  authoredAt: string
  /** When this phone sent it. */
  sentAt: string
}

/** One stored entry, or null for anything this build cannot read - dropped
 *  one at a time rather than the ledger refused whole, `validateDayHikeStore`'s
 *  rule. */
function readable(candidate: unknown): SentReport | null {
  if (typeof candidate !== 'object' || candidate === null) return null
  const { id, type, poiId, mile, authoredAt, sentAt } = candidate as Record<
    string,
    unknown
  >
  if (typeof id !== 'string' || id === '') return null
  if (typeof type !== 'string' || type === '') return null
  if (typeof authoredAt !== 'string' || typeof sentAt !== 'string') return null
  return {
    id,
    type: type as ReportDraft['type'],
    poiId: typeof poiId === 'string' ? poiId : null,
    mile: typeof mile === 'number' && Number.isFinite(mile) ? mile : null,
    authoredAt,
    sentAt,
  }
}

/** Every report this phone has sent, newest first. Empty when nothing was
 *  ever recorded, and empty rather than a throw for a store this build
 *  cannot read. */
export async function listSentReports(): Promise<SentReport[]> {
  const stored = (await get(SENT_REPORTS_KEY)) as unknown
  if (!Array.isArray(stored)) return []
  return stored.map(readable).filter((entry): entry is SentReport => entry !== null)
}

/**
 * Record that `item` went.
 *
 * A no-op for anything that is not a condition report: photo actions, field
 * notes, hours, closures and app-failure reports each have their own surface
 * or none, and the screen this feeds lists reports. Idempotent on the id,
 * because a resend that lost its response is the same report (#243) and the
 * outbox may hand it over twice.
 */
export async function recordSentReport(
  item: OutboxItem,
  sentAt: string = new Date().toISOString(),
): Promise<void> {
  if (item.payload === undefined) return
  const before = await listSentReports()
  if (before.some((sent) => sent.id === item.id)) return
  const entry: SentReport = {
    id: item.id,
    type: item.payload.type,
    poiId: item.payload.poi_id ?? null,
    mile: item.payload.mile ?? null,
    authoredAt: item.authoredAt,
    sentAt,
  }
  await set(SENT_REPORTS_KEY, [entry, ...before].slice(0, SENT_REPORTS_MAX))
}
