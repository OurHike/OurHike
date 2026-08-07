// Full / Standard / Minimal: how much of the live sheet is drawn
// (MAP_STYLE_SPEC.md, map/mapDetail.ts).
//
// A segmented radio group like the pickers around it. What each level hides
// is decided in map/mapDetail.ts's matrix, not here - this control shows and
// writes the choice, and its descriptions have to keep saying what that
// matrix does, which is why the minimal line names what STAYS: a level that
// reads as "less map" would scare off exactly the hiker it is for.

import type { LayerDetailLevel } from '../lib/userPreferences'

const OPTIONS: ReadonlyArray<{
  value: LayerDetailLevel
  label: string
  hint: string
}> = [
  { value: 'full', label: 'Full', hint: 'Everything' },
  { value: 'standard', label: 'Standard', hint: 'Borders off' },
  { value: 'minimal', label: 'Minimal', hint: 'Essentials' },
]

const DESCRIPTIONS: Record<LayerDetailLevel, string> = {
  full: 'The whole sheet, state and county borders included.',
  standard: 'Everything but borders — wanted sometimes, distracting mostly. The default.',
  minimal:
    'The land and the way through it: index contours, side paths, peaks, places and water stay. Minor contours, tracks, small roads and water names go.',
}

export interface MapDetailPickerProps {
  value: LayerDetailLevel
  onChange: (next: LayerDetailLevel) => void
}

export function MapDetailPicker({ value, onChange }: MapDetailPickerProps) {
  return (
    <fieldset className="map-detail-picker">
      <legend className="map-detail-picker__legend">Map detail</legend>

      <div className="map-detail-picker__options">
        {OPTIONS.map((option) => (
          <label
            key={option.value}
            className="map-detail-picker__option"
            data-selected={value === option.value}
          >
            <input
              type="radio"
              className="map-detail-picker__input"
              name="layer_detail_level"
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <span className="map-detail-picker__label">{option.label}</span>
            <span className="map-detail-picker__hint">{option.hint}</span>
          </label>
        ))}
      </div>

      <p className="map-detail-picker__description">{DESCRIPTIONS[value]}</p>
    </fieldset>
  )
}
