// The map's own MapLibre controls: compass, locate, scale bar.
//
// Placement follows WIREFRAMES.md's one interaction rule for this screen -
// everything tapped mid-walk sits in the lower third, everything read but not
// touched sits above. So compass and locate stack bottom-right in the thumb
// zone, and the scale bar sits bottom-left, read but never pressed.
//
// Zoom buttons are web-only on purpose. Pinch already covers zoom on a phone,
// and the thumb zone is the most reachable real estate on the screen - spending
// it on the least necessary control is a bad trade when the user is walking.

import { GeolocateControl, NavigationControl, ScaleControl } from 'maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'

export type ScaleUnits = 'imperial' | 'metric'

export interface MapChromeOptions {
  /** Web only - touch platforms rely on pinch (see note above). */
  showZoomButtons: boolean
  units: ScaleUnits
  /**
   * Whether the hiker has location switched on (#312).
   *
   * With it off, the locate control is not attached at all - and that is the
   * point rather than a tidiness. It used to be added unconditionally, which
   * had three consequences the app never accounted for: it prompted for
   * browser permission on a phone whose owner had declined the location step
   * during onboarding, it fed its fix to MapLibre's blue dot and nowhere
   * else - so the map drew a position while the header still said "Looking
   * for GPS…" - and when both were live it was a SECOND high-accuracy watch
   * on one battery, beside `lib/useGeolocation`'s.
   *
   * Two subsystems disagreeing on screen about whether GPS exists is the
   * failure; not offering the control while location is off is the honest
   * shape of it, because the way back is the Settings row that governs both.
   */
  locationEnabled: boolean
}

/** WIREFRAMES.md: scale bar is 64px wide. */
const SCALE_MAX_WIDTH = 64

/**
 * Adds the map's controls and returns a detach function that removes every one
 * of them - so a remount cannot leave a second set stacked on the first.
 *
 * The detach tolerates a map that is already gone, and has to. MapView tears
 * the map down in its own effect's cleanup, and React runs that BEFORE this
 * one - the map-building effect is declared first, so its cleanup goes first
 * too. `Map.remove()` detaches every control on the way out, which leaves this
 * function removing controls that are no longer attached.
 */
export function attachMapChrome(
  map: MapLibreMap,
  { showZoomButtons, units, locationEnabled }: MapChromeOptions,
): () => void {
  const compass = new NavigationControl({
    showZoom: showZoomButtons,
    // Always present: tapping it resets north-up, which is the way back when
    // a rotated map has stopped matching the paper picture in someone's head.
    showCompass: true,
    visualizePitch: false,
  })

  const locate = locationEnabled
    ? new GeolocateControl({
        // Continuous, not a single fix - the blue dot has to follow the walk.
        trackUserLocation: true,
        showAccuracyCircle: true,
        positionOptions: { enableHighAccuracy: true },
      })
    : null

  const scale = new ScaleControl({ unit: units, maxWidth: SCALE_MAX_WIDTH })

  map.addControl(compass, 'bottom-right')
  if (locate !== null) map.addControl(locate, 'bottom-right')
  map.addControl(scale, 'bottom-left')

  return () => {
    for (const control of [compass, locate, scale].filter((c) => c !== null)) {
      // Asking first, because `removeControl` does not. It calls the control's
      // own `onRemove` whether or not the map still holds it, and every
      // MapLibre control's `onRemove` unsubscribes through a `_map` reference
      // it then deletes - so a second call reads `off` off undefined and
      // throws.
      //
      // Thrown from an effect cleanup with no error boundary above it, React
      // unmounts the whole root: leaving the map tab produced a white screen
      // with no tab bar to get back from, which read as "the Downloads tab
      // shows nothing". A control that is already detached is the outcome this
      // function wants, so there is nothing to do about it but skip.
      if (map.hasControl(control)) map.removeControl(control)
    }
  }
}
