// Which background the map draws, as a control rather than a settings row.
//
// It lived only in Settings, three taps from the map, behind a select. That is
// the wrong place for it: the background is the most visible thing on the
// screen, and the state someone most wants to change it from - "why is there
// nothing here" - is the state where hunting through Settings is least
// appealing. It is now the first thing in the legend, which is one tap from
// the map and already the panel that answers "what am I looking at."
//
// Two radio inputs rather than a select, and real inputs rather than buttons
// with aria-checked: arrow keys move between radios in a group for free, the
// browser handles the roving tabstop, and a form control that IS a form
// control needs no re-implementation. They are styled as a segmented pair,
// which is what makes two mutually exclusive choices read as a choice.
//
// Rendered in Settings too, from this one component. The alternative was a
// select in one place and buttons in the other, both writing the same
// preference and disagreeing about what it looks like.

import type { BackgroundSource } from '../lib/userPreferences'
import type { BackgroundOverride } from '../lib/dataSaver'

/**
 * What each choice actually changes, said in terms of what a hiker would see.
 *
 * Not "OpenFreeMap" or "PMTiles" - the live sheet is not a trade against
 * working offline (it is drawn OVER the download, so the download is still
 * what shows with no signal) and that is the one thing worth knowing here.
 */
const OPTIONS: ReadonlyArray<{
  value: BackgroundSource
  label: string
  hint: string
}> = [
  { value: 'hiking_topo_live', label: 'Live topo', hint: 'Contours & relief' },
  { value: 'usgs_topo_offline', label: 'Downloaded', hint: 'No data fetched' },
]

/** The longer description under the group, per choice. */
const DESCRIPTIONS: Record<BackgroundSource, string> = {
  hiking_topo_live:
    'Contours, shaded relief and streams beyond your downloaded area. Falls back to your download with no signal.',
  usgs_topo_offline: 'Your downloaded corridor only — no background data is fetched.',
}

/**
 * What to say when the drawn background is not the chosen one.
 *
 * Opposite in kind, so opposite in wording: one is the app withholding the
 * live sheet, the other is the app supplying it against a choice that has no
 * download to honour yet. See lib/dataSaver.ts.
 */
const OVERRIDE_NOTES: Record<BackgroundOverride, string> = {
  'data-saver':
    "Data Saver is on, so the map is using your download only and fetching no background tiles. Turn Data Saver off in your phone's settings to see contours and shaded relief.",
  'nothing-downloaded':
    'Nothing is downloaded yet, so "downloaded only" has no map to draw and the live topo sheet is being used instead. Download the map and this setting takes effect.',
}

export interface BackgroundPickerProps {
  value: BackgroundSource
  onChange: (next: BackgroundSource) => void
  /** Why the drawn background differs from `value`, if it does. */
  override?: BackgroundOverride | null
  /**
   * Distinguishes this group's radios from another instance's.
   *
   * Radio inputs are grouped by `name` across the whole document, so two
   * pickers sharing one would behave as a single four-way choice if they were
   * ever mounted together.
   */
  idPrefix?: string
}

export function BackgroundPicker({
  value,
  onChange,
  override = null,
  idPrefix = 'background',
}: BackgroundPickerProps) {
  return (
    <fieldset className="bg-picker">
      <legend className="bg-picker__legend">Background</legend>

      <div className="bg-picker__options">
        {OPTIONS.map((option) => (
          <label
            key={option.value}
            className="bg-picker__option"
            data-selected={value === option.value}
          >
            <input
              type="radio"
              className="bg-picker__input"
              name={`${idPrefix}-background_source`}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
            />
            <span className="bg-picker__label">{option.label}</span>
            <span className="bg-picker__hint">{option.hint}</span>
          </label>
        ))}
      </div>

      <p className="bg-picker__description">{DESCRIPTIONS[value]}</p>

      {override !== null && (
        <p className="bg-picker__note" role="note">
          {OVERRIDE_NOTES[override]}
        </p>
      )}
    </fieldset>
  )
}
