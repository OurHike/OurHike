// The map's own MapLibre controls: compass, locate, report, scale bar.
//
// Placement follows WIREFRAMES.md's one interaction rule for this screen -
// everything tapped mid-walk sits in the lower third, everything read but not
// touched sits above. So compass and locate stack bottom-right in the thumb
// zone, and the scale bar sits bottom-left, read but never pressed.
//
// Zoom buttons are web-only on purpose. Pinch already covers zoom on a phone,
// and the thumb zone is the most reachable real estate on the screen - spending
// it on the least necessary control is a bad trade when the user is walking.
//
// THE LOCATE CONTROL IS OURS, NOT MAPLIBRE'S (#1581). It was a
// `GeolocateControl`, and that control does two things: it draws a blue dot,
// and it runs a `watchPosition` of its own to feed it. Neither is wanted any
// more. The dot is drawn by map/positionLayers.ts from the same
// lib/useGeolocation.ts state the header reads - so the canvas cannot
// disagree with the mono line about whether there is a fix - and the second
// high-accuracy watch that this file called "a SECOND high-accuracy watch on
// one battery" for a month is simply gone. What is left of the control is a
// button: put the camera on the hiker. It is built the way ReportControl is,
// and it wears the mark's own glyph, so the thing tapped and the thing that
// appears are the same shape.

import { NavigationControl, ScaleControl } from 'maplibre-gl'
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
   * The watch is gone now (#1581, see the header), but the gate stays: a
   * button that centres the map on a fix the hiker has said not to take is
   * a door with nothing behind it. The way back is the Settings row that
   * governs both.
   */
  locationEnabled: boolean
  /**
   * Puts the camera on the hiker (#1581), or undefined where this shell has
   * no fix to put it on - App.tsx's handleLocate, which reads the same
   * watch the mark is drawn from. Undefined leaves the control off, for
   * ReportControl's reason: a control that looks pressable and does nothing
   * is the refusal-as-dead-control D10 forbids.
   */
  onLocate?: (() => void) | undefined
  /**
   * Whether there is a fix to centre on right now. False disables the button
   * rather than hiding it, so the corner does not rearrange itself the
   * moment a fix lands: the control is present and plainly off while the
   * header says "Looking for GPS…", and live once it says a mile. Defaults
   * to false.
   */
  fixAvailable?: boolean
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

/** What the locate button is for, in the words a pointer and a screen reader
 *  both get. */
export const LOCATE_LABEL = 'Center the map on me'

/** The same button while there is nothing to centre on - the header's own
 *  vocabulary for the state (lib/positionLine.ts), so the two agree. */
export const LOCATE_WAITING_LABEL = 'No GPS fix yet'

// How far one tap of locate brings the camera is LOCATE_MIN_ZOOM in
// map/poiLayers.ts - not here, because App.tsx reads it and this module
// imports maplibre-gl, which the shell must never reach statically
// (map/mapEngineLoader.ts, #1300; scripts/check-build-output.mjs holds it).

/**
 * The mark's glyph at button scale: the same ring, dot and four ticks
 * map/positionMark.ts rasterises, in a 24-box. Proportions follow the mark
 * (ring at 11/18 of the half-box, ticks from 13 to 17), so the button and
 * the mark on the canvas are one drawing at two sizes.
 */
export const LOCATE_GLYPH =
  '<circle cx="12" cy="12" r="7.3" fill="none" stroke="currentColor" stroke-width="1.7"/>' +
  '<circle cx="12" cy="12" r="1.7" fill="currentColor"/>' +
  '<path d="M12 1.3v2.7M12 20v2.7M1.3 12h2.7M20 12h2.7" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>'

/**
 * The locate button (#1581): one `ctrl-group`, one button, built exactly as
 * ReportControl is and for its reasons. `setFixAvailable` is what MapView
 * calls as the fix comes and goes, so the button is disabled - present,
 * plainly off - rather than absent while the header says "Looking for GPS…".
 */
export class LocateControl implements IControl {
  container: HTMLElement | null = null
  private button: HTMLButtonElement | null = null
  private readonly onLocate: () => void
  private available: boolean

  constructor(onLocate: () => void, fixAvailable = false) {
    this.onLocate = onLocate
    this.available = fixAvailable
  }

  onAdd(): HTMLElement {
    const container = document.createElement('div')
    container.className = 'maplibregl-ctrl maplibregl-ctrl-group map-locate'

    const button = document.createElement('button')
    button.type = 'button'
    button.className = 'map-locate__button'
    button.innerHTML = `<svg class="map-locate__glyph" viewBox="0 0 24 24" width="22" height="22" aria-hidden="true" focusable="false">${LOCATE_GLYPH}</svg>`
    button.addEventListener('click', () => {
      if (this.available) this.onLocate()
    })

    container.appendChild(button)
    this.container = container
    this.button = button
    this.setFixAvailable(this.available)
    return container
  }

  onRemove(): void {
    this.container?.remove()
    this.container = null
    this.button = null
  }

  /** Whether there is a fix to centre on. Disabled, not hidden - see the
   *  class note. */
  setFixAvailable(available: boolean): void {
    this.available = available
    const button = this.button
    if (button === null) return
    button.disabled = !available
    const label = available ? LOCATE_LABEL : LOCATE_WAITING_LABEL
    button.title = label
    button.setAttribute('aria-label', label)
  }
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
  {
    showZoomButtons,
    units,
    locationEnabled,
    onLocate,
    fixAvailable = false,
    onReport,
  }: MapChromeOptions,
): () => void {
  const compass = new NavigationControl({
    showZoom: showZoomButtons,
    // Always present: tapping it resets north-up, which is the way back when
    // a rotated map has stopped matching the paper picture in someone's head.
    showCompass: true,
    visualizePitch: false,
  })

  // Both gates, and both are the same sentence: the hiker has location on,
  // AND the shell has a watch to centre on. Attached with no fix yet, it is
  // disabled rather than missing (LocateControl).
  const locate =
    locationEnabled && onLocate !== undefined
      ? new LocateControl(onLocate, fixAvailable)
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
