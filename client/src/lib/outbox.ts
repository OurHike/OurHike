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
//     Since #288 the removal itself is also atomic: every mutator goes
//     through mutateQueue below, whose get+put share ONE readwrite
//     transaction, so this property no longer has a sub-millisecond hole
//     where two overlapping mutators could interleave between a `get` and
//     its `set` and lose whichever wrote first.
//
// What is deliberately NOT here: retrying forever. A report the server will
// never accept is marked with a `failure` and shown to the hiker on the More
// screen, because "waiting to send" is a lie once it has stopped being true.

import { get, update } from 'idb-keyval'

import { BUILD_INFO } from './buildInfo'

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
  /**
   * Where along the trail, in miles from the southern terminus (#244).
   *
   * The form already snaps the fix to the centerline to render "mi 1,407.2",
   * and used to drop it here - so the one number the serious-warnings banner
   * filters on was computed and discarded in the same breath. Sent because
   * nothing server-side can re-derive it: the trail is a published artifact
   * the client and pipeline share, not a table the backend holds.
   *
   * Optional, and absent is ordinary rather than a gap: off the trail, or
   * before the trail index has downloaded. Zero would be Springer Mountain.
   */
  mile?: number
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
  /**
   * The build that gave up on this report - `BUILD_INFO.commit` (#412).
   *
   * Here so a later build can disagree. The reason a report is refused may be
   * the app rather than the report: an old client meeting a newer API gets a
   * 422 on a field it does not know about, and no amount of retrying by THAT
   * build will help while an update fixes it outright. Without this the
   * report sits marked unsendable until somebody happens to open More and
   * press "Try again", which is not a thing a hiker knows to do.
   *
   * The commit rather than the version, because `version` is `0.0.0` until
   * the first tag (RELEASING.md §13) and so cannot tell two builds apart.
   *
   * Optional: absent means the failure was stored before this existed, which
   * is treated as "not this build" - one retry on the next update, which is
   * the same answer that build would have got had it recorded anything.
   */
  build?: string
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
   * The photo, as bytes, already downscaled and re-encoded (lib/reportPhoto.ts).
   *
   * **The bytes and not a URL**, which is the whole reason this field exists
   * rather than `payload.photo_url` carrying it. `photo_url` is the shape for
   * a photo that has already been uploaded; out here the ordinary path is that
   * the report is written with no signal at all and flushes days later, so the
   * image has to survive in IndexedDB alongside the report it belongs to.
   * `idb-keyval` stores a `Blob` natively, so this costs nothing extra.
   *
   * Prepared at pick time rather than at flush time, deliberately: shrinking
   * it is the step that can fail in a way the hiker can do something about
   * (take another one), and they can only do that while they are still
   * standing in front of the thing they photographed.
   */
  photo?: Blob
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

/**
 * Every write to the queue goes through here, and through `update()`
 * specifically, whose get+put run inside one `readwrite` transaction. The
 * mutators used to be separate `get` → transform → `set` calls - two
 * IndexedDB transactions - so two of them overlapping could lose a write:
 * a report enqueued while a flush's `removeQueued` was between its read and
 * its write was gone from IndexedDB without ever being sent, and a queued
 * report is often the only copy of something written with no signal (#288).
 */
async function mutateQueue(
  transform: (queue: OutboxItem[]) => OutboxItem[],
): Promise<void> {
  await update<OutboxItem[]>(OUTBOX_KEY, (queue) => transform(queue ?? []))
}

export async function listQueued(): Promise<OutboxItem[]> {
  return readQueue()
}

export async function enqueue(
  payload: ReportDraft,
  authoredAt: Date = new Date(),
  photo?: Blob,
): Promise<OutboxItem> {
  const item: OutboxItem = {
    id: crypto.randomUUID(),
    authoredAt: authoredAt.toISOString(),
    payload,
    // Spread rather than `photo` outright so an item without one has no key
    // at all. The queue is compared and rewritten in several places, and an
    // explicit `photo: undefined` is a difference that reads as one.
    ...(photo !== undefined ? { photo } : {}),
  }

  await mutateQueue((queue) => [...queue, item])
  return item
}

export async function removeQueued(id: string): Promise<void> {
  await mutateQueue((queue) => queue.filter((item) => item.id !== id))
}

/** Clears a permanent failure so the item is eligible to be sent again.
 *
 *  Clearing the flag is all this does - App.tsx's handler is what actually
 *  flushes afterwards, and it has to, because nothing else will on a steady
 *  connection (#266).
 *
 *  Worth being exact about what a retry can achieve for the commonest cause.
 *  A wrong phone clock bakes a future `authoredAt` into the stored item, and
 *  that value is deliberately never re-derived - a report written Monday has
 *  to still read as Monday when it flushes on Thursday, so restamping it
 *  would make a three-day-old blowdown look fresh to a maintainer. Fixing the
 *  clock therefore does not repair an already-queued report; it stops the
 *  NEXT one being wrong, and this one becomes acceptable once real time
 *  passes the timestamp it is carrying. */
export async function retryQueued(id: string): Promise<void> {
  await mutateQueue((queue) =>
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
    //
    // **Unless a different build reached that verdict** (#412). The judgment
    // is the app's, not the report's, and an update can overturn it - a 422
    // on a field the previous build did not send is fixed by the build that
    // sends it. Bounded to one retry per update, so this is not the
    // resetting the rule above guards against: the failure is re-marked with
    // the current build if it fails again, and skipped from then on.
    if (item.failure !== undefined && item.failure.build === BUILD_INFO.commit) {
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
  await mutateQueue((queue) =>
    queue.map((item) =>
      item.id === id
        ? {
            ...item,
            failure: {
              reason,
              at: new Date().toISOString(),
              build: BUILD_INFO.commit,
            },
          }
        : item,
    ),
  )
}
