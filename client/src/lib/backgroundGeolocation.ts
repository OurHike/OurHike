// Fixes that keep arriving when the screen goes dark (#1182).
//
// WHY THIS IS A SECOND GEOLOCATION PATH, IN A REPOSITORY THAT SAYS NOT TO HAVE
// ONE.
//
// `capacitor.config.ts` states the posture and its reason: geolocation and
// IndexedDB both work inside WKWebView and Android WebView, "so a Capacitor
// plugin would be a second implementation of a thing that already works." That
// reasoning does not reach this module, because recording through a dark
// screen is precisely a thing that does NOT already work:
// `navigator.geolocation` is exposed on `Window` only, so no service worker
// can hold a watch, and a locked screen freezes the page. And
// TECHNICAL_ARCHITECTURE.md wrote the carve-out in advance - "if always-on
// background tracking becomes a priority later, Capacitor supports native GPS
// plugins to close most of that gap without a rewrite."
//
// It is still a second path, so it is fenced: nothing outside the trace
// recorder may use it. `useGeolocation` remains the app's single position
// source for the blue dot and the mile readout, and MapLibre's
// GeolocateControl runs a third watch internally that no plugin swap could
// reach - a half-migrated app would have three sources disagreeing about where
// somebody is, on the four paths that can hurt a hiker.
//
// THE NUMBER THIS PLUGIN REPORTS IS NOT THE NUMBER THE WEB API REPORTS.
//
// This is the trap in the whole exercise and it is worth the paragraph. The
// W3C Geolocation API defines `coords.accuracy` as a **95%** confidence
// radius. This plugin's `accuracy` is documented, in its own definitions file,
// as "radius of horizontal uncertainty in metres, with **68%** confidence".
// Same units, same name, different question.
//
// For a circular normal error the 95% radius is about 1.62x the 68% radius
// (Rayleigh: r95 = 2.448σ, r68 = 1.510σ), so an identical phone standing in an
// identical spot reports a number roughly 40% SMALLER through this plugin. A
// trace that mixed the two silently would make every threshold derived from it
// wrong in the optimistic direction - which is the exact failure FEATURES.md
// names, "a confidently wrong prediction is more dangerous than an honest
// unknown", arriving through the instrument built to prevent it.
//
// So nothing here converts. Every sample carries the convention it was
// measured under (`accuracy_confidence` in the CSV) alongside the source, and
// the analysis is required to look. Converting would bury a 1.62x factor
// inside a column nobody would think to question afterwards.
//
// WHAT IS NOT VERIFIED, AND CANNOT BE FROM HERE.
//
// There is no Android SDK and no device in the sandbox this was written in, so
// no line below has ever executed against the real plugin. The mapping, the
// platform gate and the teardown are unit-tested against a stub; everything
// that happens on the far side of `registerPlugin` is verified by a human on a
// phone or not at all. The plugin's own compatibility table stops at Capacitor
// v7 and this repository is on 8.5.0 - its peer range says `>=3.0.0`, which
// declares v8 by an open bound rather than by testing against it. A device
// build is the first thing that will find out.

import { Capacitor, registerPlugin } from '@capacitor/core'
import type {
  BackgroundGeolocationPlugin,
  Location as PluginLocation,
} from '@capacitor-community/background-geolocation'

/**
 * A fix from the native watch, in the recorder's own vocabulary.
 *
 * Deliberately not a `GeolocationPosition`: faking one would let a caller pass
 * a native fix to something expecting the web API's 95% radius, which is the
 * confusion the header exists to prevent. A different shape makes the
 * difference impossible to miss at the call site.
 */
export interface NativeFix {
  timestampMs: number
  lat: number
  lon: number
  /** 68% confidence, NOT the web API's 95%. See the header. */
  accuracyM: number
  altitudeM: number | null
  altitudeAccuracyM: number | null
  speedMps: number | null
  headingDeg: number | null
  /**
   * The platform says this position was produced by mock-location software
   * rather than by GNSS.
   *
   * Carried rather than dropped, and never silently: a developer-options mock
   * is a legitimate way to test the recorder, and a trace containing fakes
   * that does not say so is a trace that could be analysed as real.
   */
  simulated: boolean
}

/** Why a background watch is not running. Each names something different, and
 *  only one of them is the tester's to fix. */
export type BackgroundWatchProblem =
  /** Not a native shell - a browser, including the PR preview. */
  | 'not-native'
  /** The platform refused, or the permission was never granted. On Android
   *  10+ "Allow all the time" cannot be granted from an in-app prompt at all;
   *  it is a settings screen the person has to visit. */
  | 'not-authorized'
  /** The plugin threw something else. Kept distinct because "we do not know"
   *  is a different sentence from "you said no". */
  | 'failed'

export interface BackgroundWatchHandlers {
  onFix: (fix: NativeFix) => void
  onProblem: (problem: BackgroundWatchProblem) => void
}

/** The subset of the plugin this module uses, so a test can supply one. */
export interface BackgroundGeolocationLike {
  addWatcher: BackgroundGeolocationPlugin['addWatcher']
  removeWatcher: BackgroundGeolocationPlugin['removeWatcher']
}

/**
 * What the persistent Android notification says.
 *
 * Required by the platform rather than chosen: Android will not deliver
 * background location without a foreground service, and a foreground service
 * shows a notification the person cannot dismiss. So the only decision left is
 * what it says, and it says the true thing - this is on, it costs battery, and
 * here is how to end it. A notification that undersold either would be the
 * "never let a display outrun its source" failure on the one surface a hiker
 * sees when the app is not open.
 */
export const BACKGROUND_TITLE = 'OurHike is recording a GPS trace'
export const BACKGROUND_MESSAGE =
  'Recording where your phone thinks you are, with the screen off. This uses extra battery. Stop it in Settings → Record a GPS trace.'

/** Whether a native background watch could run at all here. False in every
 *  browser, which includes the PR preview every field test has used so far. */
export const backgroundWatchAvailable = (): boolean => Capacitor.isNativePlatform()

/**
 * Maps the plugin's location onto ours.
 *
 * `bearing` becomes `headingDeg`: the plugin calls it deviation from true
 * north, which is what the web API calls heading. Renamed at the boundary so
 * one word means one thing inside the app.
 *
 * A null `time` falls back to the wall clock. The plugin types it nullable and
 * the recorder's whole point is that `timestampMs` is the PLATFORM's fix time
 * rather than `Date.now()` - substituting folds delivery latency into the
 * cadence for that one sample. @unvalidated: nobody has seen a null `time`
 * from this plugin, so how often this happens is unknown, and a `fix_source`
 * of `native` is the flag that it could have.
 */
export function fixFromPluginLocation(
  location: PluginLocation,
  now: () => number = Date.now,
): NativeFix {
  return {
    timestampMs: location.time ?? now(),
    lat: location.latitude,
    lon: location.longitude,
    accuracyM: location.accuracy,
    altitudeM: location.altitude,
    altitudeAccuracyM: location.altitudeAccuracy,
    speedMps: location.speed,
    headingDeg: location.bearing,
    simulated: location.simulated,
  }
}

/**
 * Starts a background watch, and returns how to stop it.
 *
 * Resolves as soon as the watcher is registered, not when the first fix
 * arrives - the caller has a screen to keep honest in the meantime.
 *
 * The returned stop is safe to call before the watcher id has arrived: a
 * recording that is started and stopped inside one second would otherwise
 * leave a foreground service and its notification running for the life of the
 * app, which is the same class of leak `useWakeLock`'s `cancelled` flag exists
 * for and considerably more visible.
 */
export function startBackgroundWatch(
  handlers: BackgroundWatchHandlers,
  plugin: BackgroundGeolocationLike = lazyPlugin(),
): () => void {
  let stopped = false
  let watcherId: string | null = null

  void plugin
    .addWatcher(
      {
        // Its presence is what makes this a background watch at all - without
        // `backgroundMessage` the plugin only guarantees foreground updates,
        // on both platforms. So this is load-bearing, not decoration.
        backgroundMessage: BACKGROUND_MESSAGE,
        backgroundTitle: BACKGROUND_TITLE,
        requestPermissions: true,
        // Every fix, including the ones that have not moved. `distanceFilter`
        // is the plugin's own version of the noise gate `useGeolocation`
        // deliberately does not have: suppressing small movements also
        // suppresses the first metres of somebody starting to walk, and
        // measuring how much a STATIONARY phone appears to wander is the
        // single thing this instrument most needs and has least of.
        distanceFilter: 0,
        // A stale fix delivered while the chipset warms up would be recorded
        // with an old timestamp and read afterwards as a cadence gap that
        // never happened.
        stale: false,
      },
      (location, error) => {
        if (stopped) return
        if (error) {
          handlers.onProblem(
            error.code === 'NOT_AUTHORIZED' ? 'not-authorized' : 'failed',
          )
          return
        }
        if (location) handlers.onFix(fixFromPluginLocation(location))
      },
    )
    .then((id) => {
      watcherId = id
      // Stopped while the registration was still in flight. Remove it now,
      // or the notification outlives the recording that asked for it.
      if (stopped) void plugin.removeWatcher({ id }).catch(() => {})
    })
    .catch(() => {
      if (!stopped) handlers.onProblem('failed')
    })

  return () => {
    stopped = true
    if (watcherId !== null) {
      const id = watcherId
      watcherId = null
      void plugin.removeWatcher({ id }).catch(() => {})
    }
  }
}

/**
 * The real plugin, registered on first use.
 *
 * Lazily, because `registerPlugin` on the web returns a proxy that throws
 * "not implemented" the moment anything is called on it - harmless to hold,
 * and there is no reason to hold it in a browser where
 * `backgroundWatchAvailable()` already said no.
 */
let registered: BackgroundGeolocationPlugin | null = null
function lazyPlugin(): BackgroundGeolocationLike {
  registered ??= registerPlugin<BackgroundGeolocationPlugin>('BackgroundGeolocation')
  return registered
}
