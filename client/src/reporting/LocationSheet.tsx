// The location picker as a window of its own, over whichever surface asked
// (#1563, the maintainer's steer of 2026-09-17: "the location should be
// exposed as a second emergent window").
//
// WHAT THIS REPLACES. The picker first shipped as a drawer inside the report
// window, above the tiles, and inside the long form under its location line.
// That cost the one thing #1480 had just bought: on the smallest phone the
// tile frame scrolled again the moment the drawer opened, and the picker was
// competing for room with the six tiles it exists to serve. A window of its
// own has the whole screen, closes back onto exactly the surface that opened
// it, and leaves that surface's frame the size it was measured at.
//
// ONE SHEET, THREE HOSTS. The report window, the long form and the closure
// form each render this over themselves; none of them draws a picker inline
// any more. The picker inside is reporting/LocationPicker.tsx unchanged, so
// what it offers and in what order is decided once; the frame around it is
// reporting/Sheet.tsx, shared with the keep-this-spot window.
//
// WHO OWNS WHAT. The host owns the choice, the words and whether this is open
// - it hands them down and takes them back through the picker's callbacks -
// and this owns nothing but the frame. Escape closes it: the host with its
// own Escape handler (the report window) already peels this layer first, and
// this closes itself as well, which is the same answer twice rather than a
// race.
//
// STANDS ASIDE WITH ITS HOST. Rendered inside the host's own overlay, so when
// the host hides and goes inert for the map's crosshair this goes with it,
// and the point kept on the map arrives back as a new choice that closes it.

import { LocationPicker, type LocationPickerProps } from './LocationPicker'
import { Sheet } from './Sheet'
import './locationSheet.css'

export interface LocationSheetProps extends LocationPickerProps {
  /** Close without changing anything - Done, Escape, or the scrim. */
  onClose: () => void
  /** False while the host stands aside for the map's crosshair: the sheet
   *  stays mounted with its words and its refusal, and hears no keys. */
  active?: boolean
}

export function LocationSheet({ onClose, active = true, ...picker }: LocationSheetProps) {
  return (
    <Sheet
      name="location-sheet"
      title="Where is this?"
      action={{ label: 'Done', onClick: onClose, testId: 'location-sheet-done' }}
      onDismiss={onClose}
      active={active}
      className="location-sheet"
    >
      <LocationPicker {...picker} />
    </Sheet>
  )
}
