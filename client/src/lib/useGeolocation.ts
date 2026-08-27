// The GPS watch behind the position readout.
//
// `enableHighAccuracy` is on deliberately, despite the battery cost. Under
// tree cover a coarse fix can be hundreds of feet out, and a mile marker that
// is wrong by a quarter mile at a junction is worse than no mile marker - the
// whole point of the number is deciding which way to turn.
//
// A denied permission is a settled state, not an error to retry. Watching
// anyway would prompt repeatedly and drain the battery for a fix that will
// never arrive, so `denied` simply stops.
//
// AND IT STOPS IN THE POCKET TOO (#313)
//
// High-accuracy GNSS is roughly 30-100 mW sustained. Nothing in this app used
// to respond to the tab being hidden - not one `visibilitychange` handler
// anywhere in the client - so the chipset was effectively pinned on for the
// life of the tab, drawing that whether the phone was in a hand or in a pack
// with the screen off. On a phone that has to last three days, hours of it in
// a pack is real distance off the battery.
//
// The trade is genuinely two-sided and worth stating rather than assuming: a
// wrong-way alert (#308, #93) WANTS fixes while the phone is pocketed, so
// "pause on hidden" is not permanently right. It is right today, because that
// monitor is not wired - and when it is, it needs a deliberate keep-alive
// story anyway, since a hidden tab's JS is throttled regardless and
// watchPosition-in-a-pocket was never a reliable alarm channel.
//
// The last fix is deliberately KEPT across a pause. Clearing it would blank
// the mile in the header every time the phone came out of a pocket, and the
// state a paused watch leaves behind is exactly the state a lost signal
// already leaves behind - which this hook has always kept.

import { useEffect, useState } from 'react'
import type { LonLat } from './trailPosition'

export type GeolocationState =
  | { status: 'unsupported' }
  | { status: 'idle' }
  | { status: 'locating' }
  | { status: 'denied' }
  | { status: 'unavailable' }
  | { status: 'located'; at: LonLat; accuracyFeet: number; fixedAt: Date }

const METERS_TO_FEET = 3.28084

export function useGeolocation(enabled: boolean): GeolocationState {
  const [state, setState] = useState<GeolocationState>({ status: 'idle' })
  /**
   * Whether the tab is on screen. State rather than a ref because it gates the
   * watch, and the watch lives in an effect that has to re-run when it flips.
   *
   * Defaults to visible where `document` has no answer - a runtime without the
   * API is not a phone in a pocket, and guessing "hidden" there would leave a
   * hiker with no position at all.
   */
  const [visible, setVisible] = useState(
    () => typeof document === 'undefined' || !document.hidden,
  )

  useEffect(() => {
    if (typeof document === 'undefined') return

    const update = () => setVisible(!document.hidden)
    document.addEventListener('visibilitychange', update)
    return () => document.removeEventListener('visibilitychange', update)
  }, [])

  useEffect(() => {
    if (!enabled) {
      setState({ status: 'idle' })
      return
    }
    if (!('geolocation' in navigator)) {
      setState({ status: 'unsupported' })
      return
    }
    // Paused, not stopped: the state stands, so the mile that was on screen
    // when the phone went into the pocket is the mile on screen when it comes
    // back out, until a fresh fix replaces it. See the header note above.
    if (!visible) return

    // Only from a standing start. Coming back from a pause with a fix already
    // in hand, "Looking for GPS…" would replace a position that is still the
    // best answer anyone has for a second or two.
    setState((current) =>
      current.status === 'located' ? current : { status: 'locating' },
    )

    const id = navigator.geolocation.watchPosition(
      (position) =>
        setState((current) => {
          const at = { lon: position.coords.longitude, lat: position.coords.latitude }
          // THE STATE WE ALREADY HAVE, where the fix says the phone is exactly
          // where it was (#1090). React bails out of the render when an updater
          // returns the state it was given, and every consumer of this hook
          // reads `status` and `at` and nothing else - so an identical position
          // arriving as a NEW object is a full re-render of a ~5,100-line App
          // component, every memo keyed on the fix recomputed, for an answer
          // that has not moved.
          //
          // WHAT THIS CATCHES, AND WHAT IT DOES NOT. It catches the platform
          // re-delivering an unchanged fix, which `maximumAge: 5_000` below
          // explicitly permits it to do. It does NOT catch GNSS jitter: a
          // stationary phone under tree cover reports coordinates that wobble,
          // and those are not equal. @unvalidated - nobody has measured how
          // often a watch here repeats a position exactly, so the size of this
          // is unknown and could be nothing.
          //
          // A NOISE RADIUS IS THE THING THAT WOULD CATCH JITTER, and it is
          // deliberately not written here. Suppressing every move smaller than
          // some threshold also suppresses the first N feet of somebody
          // starting to walk, and this app's four ways of hurting a hiker start
          // with "lost". Picking that number is the field measurement
          // HIKER_SAFETY.md §5 declines to guess at and #93 is already waiting
          // on, not something to infer from a fix cadence.
          //
          // `accuracyFeet` and `fixedAt` freeze along with the position when
          // this fires. Nothing reads either one today (grep: this file only),
          // and a fix at identical coordinates is the same answer about where
          // somebody is - but a caller that starts reading `fixedAt` as "how
          // fresh is this" needs to know that it stops advancing here.
          if (
            current.status === 'located' &&
            current.at.lon === at.lon &&
            current.at.lat === at.lat
          ) {
            return current
          }

          return {
            status: 'located',
            at,
            accuracyFeet: position.coords.accuracy * METERS_TO_FEET,
            fixedAt: new Date(position.timestamp),
          }
        }),
      (error) => {
        if (error.code === error.PERMISSION_DENIED) {
          // "Denied simply stops" - the header's claim, made true here. The
          // watch is released as well as reported: browsers go quiet on a
          // denied watch anyway, but a registration held for the life of the
          // tab is a promise about battery this hook should not leave to the
          // browser to keep.
          navigator.geolocation.clearWatch(id)
          setState({ status: 'denied' })
          return
        }
        // A timeout or a lost fix is weather, not a verdict - the watch stays,
        // and the next fix that lands flips this back to located.
        setState({ status: 'unavailable' })
      },
      { enableHighAccuracy: true, maximumAge: 5_000, timeout: 30_000 },
    )

    return () => navigator.geolocation.clearWatch(id)
  }, [enabled, visible])

  return state
}
