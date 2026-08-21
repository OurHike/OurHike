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
import type { ClosureDraft } from './closureDraft'
import type { FieldNoteDraft } from './fieldNotes'
import type { VolunteerHoursDraft } from './volunteerHours'

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

/**
 * A photo action waiting for signal (#577/#579) - the outbox's second
 * cargo, beside the reports it has always carried. One queue on purpose: a
 * hiker's unsent work is one list, flushed by one loop, surviving in one
 * IndexedDB key with the same atomicity (#288).
 *
 * A share carries its 640px bytes in the item's `photo` field, exactly as
 * a report's photo does, and flushes in the same two phases (#369): the
 * row, then the bytes. A withdrawal or a report is one idempotent request -
 * both are safe to say twice, and the server treats "already gone" as a
 * wish already granted.
 */
export type PhotoAction =
  | {
      kind: 'poi_photo_share'
      poiId: string
      /** "YYYY-MM-DD" capture-date claim, or null - lib/exifDate.ts. */
      taken: string | null
      /** What the on-device check found (#837), or null. */
      flagged: 'nudity' | 'faces' | null
    }
  | { kind: 'poi_photo_withdraw'; poiId: string }
  | {
      kind: 'poi_photo_report'
      poiId: string
      photoId: string
      reason: 'wrong_place' | 'person' | 'other'
    }

/**
 * The four ways ../../../CLAUDE.md says this app can hurt somebody: "Lost,
 * out of water, in front of something dangerous, or unable to get off the
 * trail quickly." One token each.
 *
 * The backend holds the same four (`app/models/app_failure.py`) and drops
 * any word it does not know rather than refusing the report, so the two ends
 * may drift without a hiker losing anything - but they are compared anyway,
 * by backend/tests/test_client_report_contract.py, because a harm this end
 * can send and that end silently discards is a triage signal that vanishes
 * with nobody told.
 */
export type AppFailureHarm = 'lost' | 'water' | 'hazard' | 'stranded'

/**
 * What the hiker may write before the field is cut.
 *
 * **Duplicated from `backend/app/schemas/app_failure.py` rather than
 * fetched**, the same trade `lib/reportPhoto.ts` makes about the photo cap:
 * the number is needed while composing, offline, and there is nothing to ask.
 * The two ends disagreeing is a bug worth having loudly, so
 * backend/tests/test_client_report_contract.py compares them.
 *
 * Enforced here as a `maxLength` on the field rather than as a refusal at
 * submit. The server truncates instead of rejecting (see that schema for
 * why), so the only question this number answers is whether the hiker finds
 * out at the keyboard or silently afterwards.
 */
export const APP_FAILURE_MAX_CHARS = 8000

/** The same, for the two short fields - where they were, how to reach them. */
export const APP_FAILURE_SHORT_MAX_CHARS = 500

/**
 * A report that this app failed somebody while they were out on the trail
 * (#848) - the outbox's third cargo, and the one that most needs to be here.
 *
 * The other two are queued because the trail has no signal. This one is
 * queued because the FAILURE has no signal: the app breaking while somebody
 * navigates by it is, nearly always, the offline path breaking, and the four
 * GitHub links in screens/ReportBug.tsx all need a browser and a connection.
 * A hiker who has just been lost cannot file any of them until town, by which
 * time the detail that would have let us reproduce it is gone.
 *
 * Deliberately NOT a `ReportDraft` with an eighth type. A report is about the
 * trail, is drawn on the map, and is public; this is about the software, is
 * drawn nowhere, and carries `contact` - a way to reach a real person, which
 * must never be one forgotten field away from the public serialisation
 * (features/IDENTITY_AND_PRIVACY.md, and #252 for what that costs).
 */
export interface AppFailureDraft {
  /** What broke. The only field the server requires. */
  what_happened: string
  /** Where they were, in their own words. No GPS is attached - see
   *  features/APP_FAILURE_REPORTS.md for why this app asks rather than takes. */
  whereabouts?: string
  /** However they chose to be reachable. Never parsed, never required. */
  contact?: string
  /** Which of the four this came near, as the hiker answered. Empty is an
   *  answer ("none of these"), not an unanswered question. */
  harms: AppFailureHarm[]
  /** `buildSummary(BUILD_INFO)` - attached, so nobody retypes a commit. */
  build: string
  /**
   * Whether the phone thought it was offline while this was being written.
   *
   * Attached rather than asked: bug_report.yml asks for it in words, and for
   * this class of failure it is nearly always the answer.
   *
   * **A claim, and asymmetrically reliable.** `true` is trustworthy - the
   * browser says it has no connection and it does not. `false` is
   * `navigator.onLine`'s optimism, which lib/useOnline.ts already documents:
   * it reports a captive portal, or a bar of signal carrying no data, as
   * online. So a `false` here does not mean the request could have gone.
   */
  was_offline: boolean
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
  /** The condition report, on the items that are one. Exactly one of this
   *  and `action` is present; optional (rather than a union type over the
   *  whole item) so every item already sitting in a phone's IndexedDB -
   *  all of which predate `action` - stays valid without migration. */
  payload?: ReportDraft
  /** The photo action, on the items that are one (#577/#579). */
  action?: PhotoAction
  /**
   * The app-failure report, on the items that are one (#848).
   *
   * A third optional field rather than a discriminated union over the whole
   * item, for the reason `payload` gives above: every item already sitting in
   * a phone's IndexedDB predates this one, and a union would invalidate all
   * of them at once - on a device whose queue is the only copy of what
   * somebody wrote down.
   */
  appFailure?: AppFailureDraft
  /**
   * The field note, on the items that are one (features/FIELD_NOTES.md) -
   * the outbox's fourth cargo, and the one written most often with no
   * signal at all: a quick tap at a spring is exactly the moment
   * DATA_NUDGES.md designed the ask around. A fourth optional field rather
   * than a union, for `payload`'s reason above.
   *
   * `authoredAt` is the note's `observed_at` - the moment of the tap, which
   * on this cargo really is the moment of observation, since the whole
   * interaction is one tap while standing at the thing observed.
   */
  fieldNote?: FieldNoteDraft
  /**
   * A day's volunteer hours (#761) - the fifth cargo, and queued for the
   * plainest reason of all: hours are logged at camp, and camp has no
   * signal. The draft carries its own `worked_on` date, so `authoredAt`
   * here is only the idempotency clock, not the claim.
   */
  volunteerHours?: VolunteerHoursDraft
  /**
   * A closure somebody walked up to (#832) - the sixth cargo, and the one
   * whose subject is the reason the queue exists: a hiker standing in front
   * of a washout is, by definition, not standing anywhere with signal.
   *
   * `authoredAt` is the closure's `reported_at`, which is what the closure
   * sheet ages it by. That is why it travels rather than being stamped on
   * arrival: a closure filed on Monday and flushed on Thursday reads as
   * three days fresher than it is, in the direction that makes a hiker
   * trust it more.
   */
  closure?: ClosureDraft
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

/**
 * Queue a photo action (#577/#579). Same queue, same properties: the
 * authored time travels, a failed send leaves it queued, and the id makes
 * a resend recognisably the same act.
 */
export async function enqueueAction(
  action: PhotoAction,
  photo?: Blob,
  authoredAt: Date = new Date(),
): Promise<OutboxItem> {
  const item: OutboxItem = {
    id: crypto.randomUUID(),
    authoredAt: authoredAt.toISOString(),
    action,
    ...(photo !== undefined ? { photo } : {}),
  }

  await mutateQueue((queue) => [...queue, item])
  return item
}

/**
 * Queue a report that the app failed somebody on the trail (#848).
 *
 * Same queue and the same four properties, which is the point: the authored
 * time travels, a failed send leaves it queued, and the id makes a resend
 * recognisably the same report. A hiker's unsent work stays one list.
 */
export async function enqueueAppFailure(
  appFailure: AppFailureDraft,
  authoredAt: Date = new Date(),
): Promise<OutboxItem> {
  const item: OutboxItem = {
    id: crypto.randomUUID(),
    authoredAt: authoredAt.toISOString(),
    appFailure,
  }

  await mutateQueue((queue) => [...queue, item])
  return item
}

/**
 * Whether anything queued can be sent without an account (#848).
 *
 * lib/outboxSync.ts declines to flush at all while signed out, on the sound
 * grounds that every item would be refused. That stopped being true when the
 * app-failure report arrived: its endpoint takes no account, because a hiker
 * whose app just failed may never have signed in and asking them to fix that
 * first gets the priority backwards. Without this, their report would sit in
 * the queue until they made an account they had no other reason to want.
 *
 * Deliberately does not exclude items already marked `failure`. A permanently
 * failed item is skipped by the flush anyway, so the cost of including it is
 * one IndexedDB read and no request - and excluding it would silently undo
 * the build-changed retry rule flushOutbox implements.
 */
export async function hasWorkThatNeedsNoAccount(): Promise<boolean> {
  return (await readQueue()).some((item) => item.appFailure !== undefined)
}

/**
 * Queue a field note (features/FIELD_NOTES.md). Same queue and the same four
 * properties: the observed time travels as `authoredAt`, a failed send
 * leaves it queued, and the id makes a resend recognisably the same note -
 * `POST /field-notes` takes it as an idempotency key exactly as `/reports`
 * does.
 *
 * Deliberately NO photo parameter, unlike every other cargo. A note
 * publishes to every hiker with no moderation gate (FIELD_NOTES.md §5), and
 * an unmoderated public photo is the class of thing POI_PHOTOS.md spent a
 * whole design on - screening, licence, withdrawal. Until notes settle
 * those same questions, DATA_NUDGES.md's opted-in photo travels on the
 * report escalation instead, whose photos are moderated evidence with
 * settled rules.
 */
export async function enqueueFieldNote(
  fieldNote: FieldNoteDraft,
  authoredAt: Date = new Date(),
): Promise<OutboxItem> {
  const item: OutboxItem = {
    id: crypto.randomUUID(),
    authoredAt: authoredAt.toISOString(),
    fieldNote,
  }

  await mutateQueue((queue) => [...queue, item])
  return item
}

/**
 * Queue a day's volunteer hours (#761). Same queue, same four properties -
 * a resend is recognisably the same record because `POST /volunteer-hours`
 * takes the id as its idempotency key.
 */
export async function enqueueVolunteerHours(
  volunteerHours: VolunteerHoursDraft,
  authoredAt: Date = new Date(),
): Promise<OutboxItem> {
  const item: OutboxItem = {
    id: crypto.randomUUID(),
    authoredAt: authoredAt.toISOString(),
    volunteerHours,
  }

  await mutateQueue((queue) => [...queue, item])
  return item
}

/**
 * Queue a closure report (#832). Same queue, same four properties - and the
 * id matters more here than anywhere: `POST /closures` takes it as an
 * idempotency key, so the flush that commits and loses its response costs a
 * duplicate request rather than a second closure over the same stretch.
 */
export async function enqueueClosure(
  closure: ClosureDraft,
  authoredAt: Date = new Date(),
): Promise<OutboxItem> {
  const item: OutboxItem = {
    id: crypto.randomUUID(),
    authoredAt: authoredAt.toISOString(),
    closure,
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
