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
import { POI_PIN_MIN_ZOOM } from './poiLayers'
import { REPORT_ICONS } from '../reporting/icons'
import type { IControl, Map as MapLibreMap } from 'maplibre-gl'

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
  /**
   * Opens the report window, or undefined where this shell has nowhere to
   * send one (#1438, D15).
   *
   * THE DOOR IS IN THE CHROME, NOT ON A SCREEN, and that is the whole
   * decision rather than a tidiness. Reporting was reachable by a long press
   * nobody is told about and by More -> Volunteer & report, two taps and a
   * word nobody standing at a dry spring goes looking for. D15 gives it a
   * named door on exactly two surfaces - Today and the map - and puts the
   * map's here because "a control that is part of the chrome cannot become a
   * control one map has and another does not". A button drawn on MapScreen
   * would be present on the map tab and absent from every other surface that
   * mounts a map.
   *
   * Undefined rather than a no-op handler: a control that looks pressable and
   * does nothing is the refusal-as-dead-control the review forbids (D10), so
   * with nowhere to go it is not attached at all.
   *
   * The long press keeps working and keeps raising chrome/PressPlate.tsx - it
   * stays the fast path for somebody already pointing at a spot.
   */
  onReport?: (() => void) | undefined
}

/**
 * The report door, as a MapLibre control (#1438, frame 9c).
 *
 * WHY IT IS A `ctrl-group` HOLDING ONE BUTTON AND NOTHING ELSE. The handoff
 * asks for "32x32, radius 6, card shadow, matching its neighbours exactly".
 * Those three properties are not this control's to hold: the radius and the
 * shadow come from maplibre-gl.css's `.maplibregl-ctrl-group`, and the size
 * comes from chrome.css's `--map-control-size` override, which is 42px rather
 * than the prototype's 32 because WIREFRAMES.md sized this stack for a thumb.
 * So the way to be indistinguishable from compass and locate is to be built
 * the same way they are; a hand-set width and radius would agree with them
 * until the day one of those two files changed, and then differ silently.
 *
 * The glyph is Lucide's flag from reporting/icons.ts - the same table the six
 * category tiles draw from, which is where path data lives - at the 1.5 stroke
 * the handoff specifies. It is painted `--danger`, which is
 * `--blaze-orange-dark` under the light theme (what the handoff names) and
 * `--blaze-orange-light` under the dark one, so the one token carries both
 * chips: `--surface-over-map` flips from white to `--ink-700` and a fixed hex
 * would be a 1.9:1 glyph after dark.
 */
export class ReportControl implements IControl {
  /** The element MapLibre mounts, once added. Exposed because the acceptance
   *  this control has to meet is about its construction, and jsdom does no
   *  layout - see map/mapChrome.test.ts. */
  container: HTMLElement | null = null
  private readonly onReport: () => void

  constructor(onReport: () => void) {
    this.onReport = onReport
  }

  onAdd(): HTMLElement {
    const container = document.createElement('div')
    container.className = 'maplibregl-ctrl maplibregl-ctrl-group map-report'

    const button = document.createElement('button')
    button.type = 'button'
    // Both, and the same words: `title` is the pointer's answer, `aria-label`
    // the screen reader's, and the neighbours in this stack carry both too.
    button.title = REPORT_LABEL
    button.setAttribute('aria-label', REPORT_LABEL)
    button.className = 'map-report__button'
    button.innerHTML = `<svg class="map-report__glyph" viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${REPORT_ICONS.flag}</svg>`
    button.addEventListener('click', this.onReport)

    container.appendChild(button)
    this.container = container
    return container
  }

  onRemove(): void {
    this.container?.remove()
    this.container = null
  }
}

/** One spelling of the door's name, so the map's control and Today's row
 *  cannot come to call the same act two things. */
export const REPORT_LABEL = 'Report a problem'

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
  { showZoomButtons, units, locationEnabled, onReport }: MapChromeOptions,
): () => void {
  const compass = new NavigationControl({
    showZoom: showZoomButtons,
    // Always present: tapping it resets north-up, which is the way back when
    // a rotated map has stopped matching the paper picture in someone's head.
    showCompass: true,
    visualizePitch: false,
  })

  /** How far in one tap of the locate control may take the camera (#315).
   *
   *  The zoom the waypoint pins start drawing at, so "where am I" lands on the
   *  closest view that also shows what is around them. Derived rather than
   *  chosen, which is why it is this constant and not a number. */
  const LOCATE_MAX_ZOOM = POI_PIN_MIN_ZOOM

  const locate = locationEnabled
    ? new GeolocateControl({
        // Continuous, not a single fix - the blue dot has to follow the walk.
        trackUserLocation: true,
        showAccuracyCircle: true,
        positionOptions: { enableHighAccuracy: true },
        // WHAT ONE TAP USED TO DO (#315): MapLibre's default is to fit the
        // accuracy circle, which for a good fix is a few metres across - so
        // the camera flew from the corridor view straight to roughly z15,
        // and a hiker who tapped "where am I" lost the whole picture of where
        // they were going in exchange for the answer.
        //
        // LOCATE_MAX_ZOOM caps that. Not a "nice framing" number: it is the
        // zoom the pin layer starts drawing at (map/poiLayers.ts's
        // POI_PIN_MIN_ZOOM), so the camera lands on the closest view where
        // the waypoints around the hiker are actually on screen - which is
        // what somebody asking where they are wants to see. A lower cap would
        // answer the question and show them nothing beside it.
        //
        // The re-centring half of that item is NOT fixed here and is reported
        // in #315: in ACTIVE_LOCK the control recentres on every jitter until
        // a user-initiated move, and whether lock should be the resting state
        // at all is a design decision rather than a parameter.
        fitBoundsOptions: { maxZoom: LOCATE_MAX_ZOOM },
      })
    : null

  const scale = new ScaleControl({ unit: units, maxWidth: SCALE_MAX_WIDTH })

  const report = onReport === undefined ? null : new ReportControl(onReport)

  map.addControl(compass, 'bottom-right')
  if (locate !== null) map.addControl(locate, 'bottom-right')
  // LAST, so it sits BELOW locate (#1438). MapLibre stacks a corner's
  // controls in the order they are added, and this corner grows away from the
  // thumb - so the order is a claim about which control a hiker reaches for
  // while walking. Locate is; filing a report is a thing somebody stops to do.
  if (report !== null) map.addControl(report, 'bottom-right')
  map.addControl(scale, 'bottom-left')

  return () => {
    for (const control of [compass, locate, report, scale].filter((c) => c !== null)) {
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
