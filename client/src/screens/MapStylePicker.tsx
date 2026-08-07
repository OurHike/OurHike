// The five map styles, as a control (MAP_STYLE_SPEC.md).
//
// A segmented radio group like ThemePicker beside it, and a separate
// component for the reason that file gives about the background picker: this
// one is about which SHEET the map draws, that one is about every screen in
// the app, and one component serving both would be two components sharing a
// stylesheet spelled as one.
//
// The rows are the spec's own order and each style's hint is its mockup
// card's use-case line, compressed - the card already answered "when would I
// pick this", and the control's job is to keep that answer within reach.
//
// The red-light sub-mode is deliberately NOT a sixth segment here. It refines
// night_hike rather than standing beside it, so it renders as a toggle under
// this control (Settings.tsx), shown only while night_hike is chosen.

import type { MapStyle } from '../lib/userPreferences'

// "Night sheet" rather than "Dark sheet" for night_hike, deliberately: the
// theme control on the same screen has a radio named Dark, and two radios
// answering /dark/i is ambiguous for a screen reader user and for every query
// that reaches the screen the way one does.
const OPTIONS: ReadonlyArray<{ value: MapStyle; label: string; hint: string }> = [
  { value: 'quiet_pine', label: 'Quiet pine', hint: 'Calm sheet' },
  { value: 'field', label: 'Field', hint: 'Day sheet' },
  { value: 'night_hike', label: 'Night hike', hint: 'Night sheet' },
  { value: 'parchment', label: 'Parchment', hint: 'Print sheet' },
  { value: 'ridgeline', label: 'Ridgeline', hint: 'Terrain first' },
]

/**
 * What each choice means, in terms of what a hiker gets.
 *
 * The field line says what happens after dark, because the switch is
 * otherwise invisible until sunset does it: on the Auto theme the day sheet
 * becomes Night hike by itself. The night line says what choosing it outright
 * is FOR - readying night vision before dusk - so nobody has to discover that
 * by flipping the whole app dark. The other three carry their cards' own
 * one-line briefs.
 */
const DESCRIPTIONS: Record<MapStyle, string> = {
  quiet_pine:
    'Muted gray-green ink on calm paper, closest to the app itself — the blazes become the loudest thing on the sheet.',
  field:
    'High-contrast white paper, built for full sun at arm’s length. On the Auto theme it turns into Night hike by itself after dark.',
  night_hike:
    'The dark sheet, tuned to protect night vision. Choosing it here keeps the map dark whatever the theme — for readying your eyes before dusk.',
  parchment:
    'The USGS quad leaned into: warmer paper, inkier browns, the classic green woodland overprint. For trail pages and anything printed.',
  ridgeline:
    'Terrain does the talking — relief carried strong, contours promoted, colour saved for water and blazes. For judging a climb before committing.',
}

export interface MapStylePickerProps {
  value: MapStyle
  onChange: (next: MapStyle) => void
}

export function MapStylePicker({ value, onChange }: MapStylePickerProps) {
  return (
    <fieldset className="map-style-picker">
      <legend className="map-style-picker__legend">Map style</legend>

      <div className="map-style-picker__options">
        {OPTIONS.map((option) => (
          <label
            key={option.value}
            className="map-style-picker__option"
            data-selected={value === option.value}
          >
            <input
              type="radio"
              className="map-style-picker__input"
              name="map_style"
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <span className="map-style-picker__label">{option.label}</span>
            <span className="map-style-picker__hint">{option.hint}</span>
          </label>
        ))}
      </div>

      <p className="map-style-picker__description">{DESCRIPTIONS[value]}</p>
    </fieldset>
  )
}
