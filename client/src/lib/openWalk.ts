// A walk that was being followed and never finished (#1373, frame 6d).
//
// WHY THIS EXISTS. Following is deliberately not persisted (App.tsx's
// `followingId`): a phone that wakes up three days later still saying "leg
// 2 of 3" would be a display outrunning its source. But that leaves one
// question nobody asks: a hiker who followed a walk yesterday and put the
// phone away at the trailhead has a walk that was never finished and never
// logged. The flow review's rule is that the ending is ASKED - at the
// finish, and again the next morning if nobody tapped anything - and never
// assumed. This is the smallest record that lets the next morning ask.
//
// WHAT IT HOLDS: which saved walk, and the day it was being followed. Not a
// position, not a time of day, not how far along - lib/lastOnTrail.ts's
// minimum, for the same privacy reason: the question is "did you finish
// yesterday's walk", and answering it needs neither where the phone was
// nor when it stopped. The design's "we stopped counting at 6:12pm near
// Gren Anderson Shelter" is the sentence this record cannot print, on
// purpose (CORRIDOR_VIEW.md's rule that the app keeps no movement record).
//
// DEVICE-LOCAL, beside `hikerMode` rather than in the synced store: a walk
// followed on this phone is a fact about this phone. Cleared by Finish, by
// Stop, and by the morning's own answer either way.
//
// NEVER AUTO-CLOSED. The design's frame 6c says the walk "closes the next
// morning"; the frame after it says dismissing the ask moves nothing, and so
// does every code rule around it (WelcomeBackCard, hikeResume, HikeDay). A
// walk nobody finished is a question, not a record - the morning asks, and
// "Not this time" forgets without logging anything.

import { del, get, set } from 'idb-keyval'

export const OPEN_WALK_KEY = 'ourhike:open-walk'

export interface OpenWalk {
  /** The saved day hike's id. */
  hikeId: string
  /** The ISO day (YYYY-MM-DD, device-local) it was being followed. */
  day: string
}

const DAY = /^\d{4}-\d{2}-\d{2}$/

/** The walk left open on this phone, or null. Anything this build does not
 *  recognise reads as none - the safe direction: an ask that does not fire. */
export async function loadOpenWalk(): Promise<OpenWalk | null> {
  const stored = (await get(OPEN_WALK_KEY)) as unknown
  if (typeof stored !== 'object' || stored === null) return null
  const { hikeId, day } = stored as Record<string, unknown>
  if (typeof hikeId !== 'string' || hikeId === '') return null
  if (typeof day !== 'string' || !DAY.test(day)) return null
  return { hikeId, day }
}

/** Note that `hikeId` is being followed today. Idempotent within a day. */
export async function noteOpenWalk(hikeId: string, day: string): Promise<void> {
  const open = await loadOpenWalk()
  if (open !== null && open.hikeId === hikeId && open.day === day) return
  await set(OPEN_WALK_KEY, { hikeId, day } satisfies OpenWalk)
}

export async function clearOpenWalk(): Promise<void> {
  await del(OPEN_WALK_KEY)
}

/**
 * Whether a walk left open is YESTERDAY'S (or older) - the case the morning
 * asks about. A walk opened today is still today's: following ended with
 * the session, and the hiker may simply have put the phone in a pocket.
 */
export function leftOpenBefore(open: OpenWalk | null, today: string): OpenWalk | null {
  if (open === null) return null
  return open.day < today ? open : null
}
