// Feet or metres, for every height and distance in the app (lib/units.ts).
//
// A segmented radio group like the three pickers beside it, for the reasons
// ThemePicker gives at length: arrow keys move within a radio group for free,
// the browser owns the roving tabstop, and a form control that IS a form
// control needs no aria re-implementation. Two segments rather than a
// checkbox, which is what this row was before it was built - a checkbox
// labelled "Units" says nothing about what checking it does, and the row it
// replaced had to carry a "Later" tag to be honest at all.
//
// NAMED BY THE UNIT, NOT THE SYSTEM. "Imperial" and "Metric" are the values in
// lib/userPreferences.ts, because that is what the backend's enum calls them
// and a wire contract is not a place for taste. They are the wrong words on a
// screen: a hiker asks "can I get this in metres?", not "is this app
// imperial?", and the segment they are looking for should be spelled the way
// they asked. The hint carries the other half of each pair, because the
// choice governs both - somebody choosing "Metres" is also choosing
// kilometres, and finding that out afterwards on the closure banner is a
// surprise the control could have spent four words preventing.
//
// The description states the exception rather than hiding it. Mile markers do
// not convert (lib/units.ts says why), and a metric hiker whose ribbon is in
// metres while the milepost under it still reads `mi 1,407.2` should be told
// that here, once, rather than left to decide the app is half-finished.

import type { UnitSystem } from '../lib/userPreferences'
import { unitSystemLabel } from '../lib/units'

/** The label comes from lib/units.ts, which is also what prints the `m` and
 *  the `ft` on every screen. One vocabulary: a picker that said "Metric" over
 *  a ribbon reading `366 m` would be naming a system rather than a unit, which
 *  is the mismatch this control's own header argues against. */
const OPTIONS: ReadonlyArray<{ value: UnitSystem; hint: string }> = [
  { value: 'imperial', hint: 'And miles' },
  { value: 'metric', hint: 'And kilometres' },
]

const DESCRIPTIONS: Record<UnitSystem, string> = {
  imperial:
    'Heights, climbs and distances in feet and miles — the units the trail is signed and measured in.',
  metric: 'Heights, climbs and distances in metres and kilometres.',
}

/** Said under both options, because it is true under both and it is the part
 *  that surprises somebody. A mile marker is where you are on the A.T., not a
 *  measurement of anything - it stays as everyone else on the trail says it. */
const MILE_MARKER_NOTE = 'Mile markers stay in miles either way.'

export interface UnitPickerProps {
  value: UnitSystem
  onChange: (next: UnitSystem) => void
}

export function UnitPicker({ value, onChange }: UnitPickerProps) {
  return (
    <fieldset className="unit-picker">
      <legend className="unit-picker__legend">Units</legend>

      <div className="unit-picker__options">
        {OPTIONS.map((option) => (
          <label
            key={option.value}
            className="unit-picker__option"
            data-selected={value === option.value}
          >
            <input
              type="radio"
              className="unit-picker__input"
              name="unit_system"
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <span className="unit-picker__label">{unitSystemLabel(option.value)}</span>
            <span className="unit-picker__hint">{option.hint}</span>
          </label>
        ))}
      </div>

      <p className="unit-picker__description">
        {`${DESCRIPTIONS[value]} ${MILE_MARKER_NOTE}`}
      </p>
    </fieldset>
  )
}
