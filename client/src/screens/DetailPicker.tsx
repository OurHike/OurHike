// The Light / Standard / Fine choice, shared by first run's "map size" step
// and the download window so the two can never drift apart.
//
// This is the detail for ONE whole-corridor package (WIREFRAMES.md Known
// Deviations #1 - the wireframe's per-section override sheet is retired). The
// sizes come from lib/downloadDetail.ts's real measured figures and are
// rendered through lib/formatBytes.ts rather than typed as copy.
//
// ALL THREE LEVELS, ALWAYS - GREYED WHERE THEY ARE NOT ON OFFER.
//
// A sheet the pipeline publishes at one size used to render no picker at all
// (#298). Under a tab that says "Hiking sheet", an absent control answers
// nothing: a hiker comparing it against the USGS sheet's three sizes cannot
// tell whether this map has no smaller version or whether the app forgot to
// ask. The levels are drawn either way, disabled where there is nothing
// behind them, and the note says what the one size is.
//
// Disabled radios are deliberately still radios. A greyed row that is a
// `<span>` looks the same and reads as nothing at all; an input with
// `disabled` is announced as an unavailable option, which is the fact.

import {
  TIERED_DETAIL_OPTIONS,
  type DetailLevel,
  type DetailOption,
} from '../lib/downloadDetail'
import { formatBytes } from '../lib/formatBytes'

const LEVEL_LABELS: Record<DetailLevel, string> = {
  light: 'Light',
  standard: 'Standard',
  fine: 'Fine',
}

export interface DetailPickerProps {
  value: DetailLevel
  onChange: (level: DetailLevel) => void
  /** Each level with what it costs here, or null where it is not published. */
  options?: readonly DetailOption[]
  /**
   * What the whole download costs when there is no level to choose - stated
   * in place of the choice, so a sheet without tiers still says its size.
   * Ignored where any level is on offer, since the levels state their own.
   */
  singleSizeBytes?: number | null
  /** Every level greyed because no choice can be taken right now (a download
   *  is under way, or the map is already here), with `lockedNote` saying so. */
  locked?: boolean
  lockedNote?: string
  /** Distinguishes the radio group when two pickers share a page. */
  name?: string
}

export function DetailPicker({
  value,
  onChange,
  options = TIERED_DETAIL_OPTIONS,
  singleSizeBytes = null,
  locked = false,
  lockedNote,
  name = 'map-detail',
}: DetailPickerProps) {
  const anyOffered = options.some((option) => option.sizeBytes !== null)

  const note = !anyOffered
    ? singleSizeBytes === null
      ? 'This map is published at one size, so there is no detail to choose.'
      : `This map is published at one size — ${formatBytes(singleSizeBytes)} — so there is no detail to choose.`
    : locked
      ? lockedNote
      : undefined

  return (
    <fieldset className="detail-picker">
      <legend className="detail-picker__legend">Map detail</legend>

      {options.map((option) => {
        const offered = option.sizeBytes !== null
        const disabled = locked || !offered

        return (
          <label
            key={option.level}
            className="detail-picker__option"
            data-disabled={disabled}
          >
            <input
              type="radio"
              name={name}
              value={option.level}
              // Never pre-selected where the level does not exist: a checked
              // "Standard" on a sheet that has no tiers would state a size
              // this download is not.
              checked={offered && value === option.level}
              disabled={disabled}
              onChange={() => onChange(option.level)}
            />
            <span className="detail-picker__name">{LEVEL_LABELS[option.level]}</span>
            <span className="detail-picker__size">
              {option.sizeBytes === null ? 'Not offered' : formatBytes(option.sizeBytes)}
            </span>
            {option.recommended && offered && (
              <span className="detail-picker__recommended">Recommended</span>
            )}
          </label>
        )
      })}

      {note !== undefined && <p className="detail-picker__note">{note}</p>}
    </fieldset>
  )
}
