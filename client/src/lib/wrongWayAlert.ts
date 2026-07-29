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
      if (settings.hikeId !== null) {
        void relay({
          hikeId: settings.hikeId,
          at: new Date(trace[trace.length - 1].timestampMs).toISOString(),
        }).catch(() => {
          // No signal is the ordinary case on this trail. The backend copy is
          // a nicety; the hiker already has what matters.
        })
      }

      return { cue: true, pushed: true }
    },
  }
}
