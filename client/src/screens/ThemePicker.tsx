// Light / Dark / Auto, as a control rather than a settings row.
//
// It was a row reading "Theme — Auto", stating a fact nobody could change,
// which is the shape WIREFRAMES.md reserves for things that are not built yet
// - except this one carried no "Later" tag, so it read as a setting that had
// simply lost its control.
//
// Three radios in a segmented group, for the reasons chrome/BackgroundPicker.tsx
// gives at length and which apply unchanged: arrow keys move within a radio
// group for free, the browser owns the roving tabstop, and a form control that
// IS a form control needs no aria re-implementation. Not that component with a
// third option bolted on - it is about the map, this is about every screen,
// and one component serving both would take a `kind` prop that decides its
// legend, its options, its descriptions and its name attribute, which is two
// components sharing a stylesheet spelled as one.
//
// WHY AUTO IS LAST AND NOT FIRST
//
// It is the default (lib/userPreferences.ts), and a default usually goes
// first. But the segment is read as a spectrum - light, dark, and then "let
// the phone decide" - and putting the deferral between the two concrete
// choices breaks that reading. Apple and Google both order it this way.

import type { Theme } from '../lib/userPreferences'

const OPTIONS: ReadonlyArray<{ value: Theme; label: string; hint: string }> = [
  { value: 'light', label: 'Light', hint: 'Paper' },
  { value: 'dark', label: 'Dark', hint: 'Ink' },
  { value: 'auto', label: 'Auto', hint: 'Follow phone' },
]

/**
 * What each choice means, said in terms of what a hiker gets.
 *
 * The dark line names night vision and says plainly what it is NOT for.
 * Dark mode and sunlight glare sound adjacent and are opposite problems -
 * glare wants more contrast and more light, not less (features/UX_CUSTOMIZATION.md
 * makes this an explicit non-goal) - and someone squinting at a screen in full
 * sun will reach for the darker option first unless told.
 */
const DESCRIPTIONS: Record<Theme, string> = {
  light:
    'The paper map. What the app was designed in, and the easier one to read in daylight.',
  dark: 'Ink instead of paper, for reading in the dark without losing your night vision. It doesn’t help with glare in bright sun — light does that better.',
  auto: 'Follows your phone, so the app turns dark when the rest of it does.',
}

export interface ThemePickerProps {
  value: Theme
  onChange: (next: Theme) => void
}

export function ThemePicker({ value, onChange }: ThemePickerProps) {
  return (
    <fieldset className="theme-picker">
      <legend className="theme-picker__legend">Theme</legend>

      <div className="theme-picker__options">
        {OPTIONS.map((option) => (
          <label
            key={option.value}
            className="theme-picker__option"
            data-selected={value === option.value}
          >
            <input
              type="radio"
              className="theme-picker__input"
              name="theme"
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <span className="theme-picker__label">{option.label}</span>
            <span className="theme-picker__hint">{option.hint}</span>
          </label>
        ))}
      </div>

      <p className="theme-picker__description">{DESCRIPTIONS[value]}</p>
    </fieldset>
  )
}
