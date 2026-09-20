/**
 * The "Show points" switch over the map (2026-09-20).
 *
 * The maintainer, having set the waypoint seam back to z7: *"Add a toggle over
 * the map to 'Show Points'."* The seam means the corridor view carries no
 * waypoint marks at all, and a map that goes quiet needs to say so on the
 * screen rather than leave a hiker deciding whether there is nothing there or
 * nothing drawn. This is that sentence, and it is also the control.
 *
 * lib/showPoints.ts holds the rule about when it moves on its own. This file
 * holds only what it looks like and how it is announced.
 *
 * A SWITCH RATHER THAN A BUTTON, in the accessibility sense: `role="switch"`
 * with `aria-checked`, because "Show points" is a state a hiker turns on and
 * off, not an action they perform. A button here would announce as "Show
 * points, button" every time and never say whether the points are showing -
 * which is the one fact the control exists to carry.
 *
 * IT IS ON THE SCREEN BELOW THE SEAM TOO, and disabled there rather than
 * hidden. The maintainer chose that from three drawn frames: a control that
 * vanishes leaves a hiker at the corridor view with no explanation for an
 * empty map, which is the failure this whole switch answers. Disabled, it says
 * both things at once - the points are off, and zooming in is what changes
 * that.
 */
import type { ReactElement } from 'react'

export type ShowPointsToggleProps = {
  /** Whether the waypoint layers are drawing. */
  shown: boolean
  /**
   * Whether the camera is below the waypoint seam.
   *
   * The same `belowPoiZoom` the legend takes, from the same place, so the
   * panel and this control cannot disagree about which side of the seam the
   * map is on.
   */
  belowSeam: boolean
  /** The hiker tapped it. */
  onToggle: () => void
}

export function ShowPointsToggle({
  shown,
  belowSeam,
  onToggle,
}: ShowPointsToggleProps): ReactElement {
  return (
    <button
      type="button"
      role="switch"
      className="show-points"
      aria-checked={shown && !belowSeam}
      // Disabled rather than absent below the seam - see the header. The
      // `title` is what a pointer gets; the description below is what a screen
      // reader gets, and they say the same thing because a hiker with either
      // needs the same fact.
      disabled={belowSeam}
      aria-describedby={belowSeam ? 'show-points-why' : undefined}
      onClick={onToggle}
    >
      <span className="show-points__track" aria-hidden="true">
        <span className="show-points__knob" />
      </span>
      Show points
      {belowSeam && (
        <span id="show-points-why" className="show-points__why">
          Zoom in to show waypoints
        </span>
      )}
    </button>
  )
}
