// Which background the map draws, as a control rather than a settings row.
//
// It lived only in Settings, three taps from the map, behind a select. That is
// the wrong place for it: the background is the most visible thing on the
// screen, and the state someone most wants to change it from - "why is there
// nothing here" - is the state where hunting through Settings is least
// appealing. It is in the legend now, which is one tap from the map and
// already the panel that answers "what am I looking at."
//
// At the FOOT of that panel, beside the way to the download, rather than at
// the top of it where it first landed. One tap from the map was the whole
// point and the foot of a panel is still one tap; what the top cost was the
// company. Half of what this control says is about the downloaded corridor -
// the "Downloaded" segment, its description, and both notes below - and the
// only control that changes what is downloaded was at the other end of the
// panel. See Legend.tsx.
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
//
// CHOOSING "DOWNLOADED" WITH AN EMPTY PHONE OPENS THE DOWNLOAD
//
// Not here - the shell does it (App.tsx), because a rule about what a choice
// MEANS belongs to the thing that owns the download rather than to the control
// that reports the choice. Worth knowing from here all the same, because it is
// why this component does not need a download button of its own: the one
// moment someone picks a background this phone cannot draw is already handled,
// and the link for every other moment is immediately below this control in the
// legend and at the foot of Settings (chrome/DownloadsLink.tsx).
//
// The choice is saved either way. It takes effect the moment a download lands
// (lib/dataSaver.ts), and the note below says so meanwhile.

import type { BackgroundSource } from '../lib/userPreferences'
import type { BackgroundOverride } from '../lib/dataSaver'

/**
 * What each choice actually changes, said in terms of what a hiker would see.
 *
 * Not "OpenFreeMap" or "PMTiles" - the live sheet is not a trade against
 * working offline (it is drawn OVER the download, so the download is still
 * what shows with no signal) and that is the one thing worth knowing here.
 *
 * BOTH HINTS SAY WHAT YOU GET, AND THAT IS NOT A STYLE RULE.
 *
 * The offline hint read "No data fetched" and was reported as a bug by
 * somebody who had the whole corridor on their phone: under a label saying
 * "Downloaded", three words beginning "No data" are read as a report on the
 * phone rather than as a description of the option. It was answering "what
 * does this cost" while its neighbour answered "what does this draw", and the
 * asymmetry is what let it be mistaken for a status.
 *
 * The saving is still the reason anyone picks this, and it is still said - in
 * DESCRIPTIONS below, as a whole sentence, where there is room for it to be
 * unambiguously about behaviour. A hint this small cannot carry a claim that
 * has to be read twice.
 *
 * "No signal needed" was tried first and is worse for a reason worth keeping:
 * it answers "when does this work" while its neighbour answers "what does this
 * draw", so the pair still did not line up - and it collided with the live
 * option's own description, which already promises falling back to the
 * download with no signal.
 */
const OPTIONS: ReadonlyArray<{
  value: BackgroundSource
  label: string
  hint: string
}> = [
  { value: 'hiking_topo_live', label: 'Live topo', hint: 'Contours & relief' },
  { value: 'usgs_topo_offline', label: 'Downloaded', hint: 'Your download only' },
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

/**
 * What to say when the choice is being honoured and still draws nothing.
 *
 * Separate from OVERRIDE_NOTES, and phrased to be separable: nothing has been
 * overridden here, the download is simply a range of scales and this view is
 * outside it (#216). It ends with the action, because "zoom in" is the whole
 * remedy and a hiker staring at blank paper has no way to guess it.
 */
const BELOW_ARCHIVE_NOTE =
  'Your download starts closer in than this, so there is no background to draw at this zoom. Zoom in and it appears.'

export interface BackgroundPickerProps {
  value: BackgroundSource
  onChange: (next: BackgroundSource) => void
  /** Why the drawn background differs from `value`, if it does. */
  override?: BackgroundOverride | null
  /** Whether the view is zoomed out past what the download covers. Distinct
   *  from `override` - see StatusStripProps for why they are not one field. */
  belowArchiveZoom?: boolean
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
  belowArchiveZoom = false,
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

      {belowArchiveZoom && (
        <p className="bg-picker__note" role="note">
          {BELOW_ARCHIVE_NOTE}
        </p>
      )}
    </fieldset>
  )
}
