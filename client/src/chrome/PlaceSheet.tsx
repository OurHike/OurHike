// The sheet that changes where a hiker hikes (#1373) - the door More → You
// promises on first run's frame 1b: "Change it any time in More → You."
//
// One field (chrome/PlaceField.tsx), the place currently kept named above
// it, and three ways out: take the row just chosen, forget the kept place,
// or close with nothing changed. Forgetting is offered because the fallback
// centre is a fact about this phone and a hiker who moved house should not
// have to pick a new one to stop the map opening on the old.

import { useState } from 'react'
import { PlaceField, placeTitle } from './PlaceField'
import { snapshotPlace, type DefaultPlace } from '../lib/defaultPlace'
import type { Place, PlacesDocument } from '../lib/places'
import type { UnitSystem } from '../lib/units'

export interface PlaceSheetProps {
  places: PlacesDocument
  settled: boolean
  online: boolean
  units: UnitSystem
  current: DefaultPlace | null
  onSave: (place: DefaultPlace) => void
  onClear: () => void
  onClose: () => void
}

export function PlaceSheet({
  places,
  settled,
  online,
  units,
  current,
  onSave,
  onClear,
  onClose,
}: PlaceSheetProps) {
  const [picked, setPicked] = useState<Place | null>(null)

  return (
    <div
      className="place-sheet"
      role="dialog"
      aria-label="Where you hike"
      onKeyDown={(event) => {
        if (event.key === 'Escape') onClose()
      }}
    >
      <div className="legend__head">
        <h2 className="legend__title">Where you hike</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      <p className="place-sheet__current">
        {current === null
          ? 'Not set. The map opens on the whole trail until it is.'
          : `Now ${placeTitle(current)}. The map opens here when there is no fix, and Today ranks hikes from here.`}
      </p>

      <PlaceField
        places={places}
        settled={settled}
        online={online}
        units={units}
        picked={picked === null ? current : snapshotPlace(picked)}
        onPick={setPicked}
        label="Where do you hike"
        autoFocus
      />

      <p className="place-sheet__note">
        Kept with your settings: on this phone, and with your account once you sign in. A
        place you named, never where you are standing.
      </p>

      <div className="place-sheet__actions">
        {picked !== null && (
          <button
            type="button"
            className="place-sheet__primary"
            onClick={() => onSave(snapshotPlace(picked))}
          >
            Use {picked.name}
          </button>
        )}
        {current !== null && (
          <button type="button" className="place-sheet__secondary" onClick={onClear}>
            Forget {current.name}
          </button>
        )}
      </div>
    </div>
  )
}
