// What sharing a photo means, said before it is done - the pure half of the
// share sheet (#577). The sheet renders these facts; this module owns them,
// so the strip under a shared photo and the sheet that shared it cannot
// drift apart about which phase the share is in.

/**
 * The cooling-off window, in hours - how long after the bytes land before
 * the photo is public.
 *
 * Deliberately duplicated from the backend (app/routers/poi_photos.py's
 * COOLING_OFF_HOURS) rather than fetched, the same reasoning as
 * MAX_PHOTO_BYTES: the whole point is to know the answer with no signal,
 * because the strip has to say "goes live in about 1h 40m" on a ridge. If
 * the two ever disagree the server's window wins - the strip is then early
 * or late about an event it does not control, which reads as imprecision
 * rather than breaking anything.
 *
 * Counted from the SHARE on this side and from the upload landing on the
 * server's - a share flushed days later goes live two hours after it
 * finally sends, and the phase below leans conservative about the one
 * claim that matters: it never says "take it back is a complete undo"
 * after that could have stopped being true.
 */
export const COOLING_OFF_HOURS = 2

export type SharePhase =
  | {
      /** Inside the window: nobody has it, taking it back is a true undo. */
      phase: 'cooling'
      /** Rounded up, so the strip never claims less time than remains. */
      remainingMinutes: number
    }
  | {
      /** Public - or possibly public, once the outbox has flushed. Stopping
       *  is always available; undoing no longer is. */
      phase: 'public'
    }

/**
 * Which phase a share is in, from when the hiker shared it.
 *
 * Conservative by construction: the clock starts at the SHARE, though the
 * server's starts at the upload landing - which is the same moment on a
 * connection and later on a ridge. So 'public' here can mean "still
 * cooling server-side", never the reverse: the strip stops promising a
 * complete undo at the earliest moment the promise could be stale, because
 * "you can still take it back entirely" said one minute too long is a lie
 * about somebody's photograph.
 */
export function sharePhase(sharedAtIso: string, now: Date = new Date()): SharePhase {
  const shared = new Date(sharedAtIso).getTime()
  const elapsed = now.getTime() - shared
  if (!Number.isFinite(elapsed) || elapsed < 0) return { phase: 'public' }

  const windowMs = COOLING_OFF_HOURS * 60 * 60 * 1000
  if (elapsed >= windowMs) return { phase: 'public' }
  return {
    phase: 'cooling',
    remainingMinutes: Math.max(1, Math.ceil((windowMs - elapsed) / 60000)),
  }
}

/** "1h 47m" / "40m", for the strip and the sheet. */
export function remainingLabel(remainingMinutes: number): string {
  if (remainingMinutes < 60) return `${remainingMinutes}m`
  const hours = Math.floor(remainingMinutes / 60)
  const minutes = remainingMinutes % 60
  return minutes === 0 ? `${hours}h` : `${hours}h ${minutes}m`
}

/**
 * The capture-date claim a share sends: the month, never the day.
 *
 * The sheet promises "the picture and the month" leave the phone, and the
 * claim is made true here rather than trusted to the server's rendering:
 * the exact day is coarsened to the first of its month before it is ever
 * queued. The gallery only prints months anyway, so nothing visible is
 * lost - what is lost is a day-precision location-and-time claim about
 * where somebody slept, which is the anonymity window's whole subject.
 */
export function takenClaimForShare(taken: string | null): string | null {
  if (taken === null) return null
  const match = /^(\d{4})-(\d{2})/.exec(taken)
  if (match === null) return null
  return `${match[1]}-${match[2]}-01`
}
