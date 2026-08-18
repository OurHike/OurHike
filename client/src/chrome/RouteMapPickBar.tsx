// The picker's "choose on the map" door, open: a slim bar over the map that
// says what a tap will do, while the map underneath is the whole screen.
// The off-corridor refusal lives here now - the same gate, the same words
// the old route card used, said where the tap happened.

import { MAX_OFF_TRAIL_MILES } from '../lib/trailPosition'
import { formatDistance, type UnitSystem } from '../lib/units'

export interface RouteMapPickBarProps {
  /** The last tap was refused: more than 3 miles from any centerline
   *  vertex, so there is no honest mile to give it (lib/trailPosition.ts). */
  refusedTap: boolean
  units: UnitSystem
  /** Back to the picker's search screen, placing nothing. */
  onCancel: () => void
}

export function RouteMapPickBar({ refusedTap, units, onCancel }: RouteMapPickBarProps) {
  return (
    <div className="route-map-pick" role="dialog" aria-label="Choose on the map">
      <p className="route-map-pick__hint">
        {refusedTap ? (
          <span role="status">
            That tap is more than {formatDistance(MAX_OFF_TRAIL_MILES, units, 'trimmed')}{' '}
            from the trail &mdash; there&rsquo;s no honest mile to give it.
          </span>
        ) : (
          'Tap the trail where this stop goes.'
        )}
      </p>
      <button type="button" className="route-map-pick__cancel" onClick={onCancel}>
        Cancel
      </button>
    </div>
  )
}
