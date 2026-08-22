// Wires D4's pure detection maths (lib/wrongWay.ts) to the one push OurHike
// is allowed to send (lib/push.ts). WIREFRAMES.md §9.
//
// Three properties shape everything here:
//
// **A cue never pushes.** The in-app cue is the conservative first beat, and
// escalating to an interrupt is a separate decision made later, after longer
// divergence. If a cue could push, the graduated design collapses into a
// single alarm and the caution built into it is lost.
//
// **It won't ask again.** `detectWrongWay` reports 'push' for every sample
// once divergence is sustained, so without suppression this would fire on
// every GPS tick - turning the one notification OurHike sends into a stream
// of them. That is the fastest available way to spend the trust the whole
// feature was designed around (HIKER_SAFETY.md's framing of false-positive
// cost). One episode, one push; a return to the trail arms the next one.
//
// **The alert is local.** Detection is local maths, the notification is
// local. The backend relay is telemetry, and it is fire-and-forget: no signal
// is the ordinary condition on this trail, and a failed relay must never be
// able to swallow the alert.

import { detectWrongWay, type WrongWaySample } from './wrongWay'

export interface WrongWaySettings {
  /** The Settings toggle. Off means no cue and no push - one switch, whole feature. */
  enabled: boolean
  hikeId: string | null
  direction: 'NOBO' | 'SOBO'
}

export interface WrongWayEvent {
  hikeId: string
  at: string
}

export interface WrongWayDeps {
  publish: (alert: { title: string; body: string }) => Promise<boolean>
  relay: (event: WrongWayEvent) => Promise<unknown>
}

export interface WrongWayOutcome {
  cue: boolean
  pushed: boolean
}

export interface WrongWayMonitor {
  observe: (trace: WrongWaySample[]) => Promise<WrongWayOutcome>
}

export function createWrongWayMonitor(
  settings: WrongWaySettings,
  { publish, relay }: WrongWayDeps,
): WrongWayMonitor {
  // Scoped to the current episode of divergence, not to the session: cleared
  // the moment the hiker is back on track, so a genuinely new wrong turn
  // later can still be raised.
  let pushedThisEpisode = false

  return {
    async observe(trace: WrongWaySample[]): Promise<WrongWayOutcome> {
      const verdict = detectWrongWay(trace)

      if (verdict === 'silent') {
        pushedThisEpisode = false
        return { cue: false, pushed: false }
      }

      if (!settings.enabled) return { cue: false, pushed: false }

      if (verdict === 'cue') return { cue: true, pushed: false }

      if (pushedThisEpisode) return { cue: true, pushed: false }
      pushedThisEpisode = true

      await publish({
        title: 'You may be going the wrong way',
        body: `You have been heading away from your route. Your hike is set ${settings.direction}.`,
      })

      // Telemetry, and only for a real escalation. Deliberately not awaited
      // for its result and never allowed to throw - the alert has already
      // happened by this point and nothing here may undo it.
      //
      // `at` is read defensively because the reason it is safe is not local
      // (#315). `detectWrongWay` returns 'silent' for a trace too short to
      // judge, and 'silent' returned above, so by here the trace has samples
      // - which is a fact about ANOTHER function's early returns, three
      // branches away. Reading the last sample unguarded made this line
      // correct only for as long as nobody reorders those checks, and the
      // cost of being wrong is a throw on the escalation path: the push has
      // already fired, so an exception here would propagate out of `observe`
      // to a caller that has no idea the hiker was already told.
      //
      // The guard is not a claim that the trace can be empty. It is a refusal
      // to let a safety path depend on a check that is not in it.
      const last = trace.at(-1)
      if (settings.hikeId !== null && last !== undefined) {
        void relay({
          hikeId: settings.hikeId,
          at: new Date(last.timestampMs).toISOString(),
        }).catch(() => {
          // No signal is the ordinary case on this trail. The backend copy is
          // a nicety; the hiker already has what matters.
        })
      }

      return { cue: true, pushed: true }
    },
  }
}
