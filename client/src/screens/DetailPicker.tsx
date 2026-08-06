// A download-level choice, shared by the Downloads screen's cards and
// onboarding so the two can never drift apart.
//
// Options-driven since #276, because there are two sheets with two different
// level sets now: the USGS raster's Light/Standard/Fine tiers and the hiking
// sheet's Standard/Fine cuts. The options carry their real measured sizes -
// rendered through lib/formatBytes.ts rather than typed as copy - and the
// builders below are the only places each sheet's options are assembled, so
// a size shown anywhere is the same size shown everywhere.
//
// EVERY LEVEL, ALWAYS - GREYED WHERE IT IS NOT ON OFFER (#298).
//
// Two different level sets meant two differently-shaped pickers, and once
// the sheets sit under tabs (screens/Tabs.tsx) that difference is what a
// hiker actually sees when they switch: three rows become two, and the row
// that vanished is the cheapest one. A missing row cannot say whether this
// map has no Light version or whether the app forgot to ask. So the ladder
// is the same under every tab and a level a sheet does not have renders
// disabled, saying so.
//
// Disabled radios are deliberately still radios. A greyed row that is a
// `<span>` looks the same and reads as nothing at all; an input with
// `disabled` is announced as an unavailable option, which is the fact.
//
// The same greying carries a second, unrelated case: levels that exist but
// cannot be chosen right now, because bytes are already on the phone or on
// their way. `locked` is that one, and it comes with a note saying what
// would have to happen instead - see DownloadCard.

import { DOWNLOAD_DETAIL_LEVELS, type DetailLevel } from '../lib/downloadDetail'
import { HIKING_DETAIL_LEVELS } from '../lib/hikingDetail'
import { hikingSheetSizeBytes } from '../lib/packages'
import { formatBytes } from '../lib/formatBytes'

export interface DetailOption {
  id: string
  label: string
  /** What this download costs at this level, or null where it is not
   *  published at it - a row that renders greyed rather than not at all. */
  sizeBytes: number | null
  recommended: boolean
}

/**
 * The rungs every picker shows, cheapest first.
 *
 * One ladder for both sheets, so switching tabs never reshuffles the rows.
 * It is the raster's own three because that is the widest set anything
 * offers; a sheet with fewer fills the gaps with nulls.
 */
const LEVEL_LADDER: ReadonlyArray<{ id: DetailLevel; label: string }> = [
  { id: 'light', label: 'Light' },
  { id: 'standard', label: 'Standard' },
  { id: 'fine', label: 'Fine' },
]

/** The USGS raster's tiers, sizes from downloadDetail.ts. Published at all
 *  three, so nothing here is greyed. */
export function rasterDetailOptions(): DetailOption[] {
  return LEVEL_LADDER.map(({ id, label }) => {
    const detail = DOWNLOAD_DETAIL_LEVELS.find((level) => level.level === id)
    return {
      id,
      label,
      sizeBytes: detail?.sizeBytes ?? null,
      recommended: detail?.recommended ?? false,
    }
  })
}

/**
 * The hiking sheet's levels (#276). Each option's size is the WHOLE sheet at
 * that level - the basemap cut plus the DEM - because that is the number a
 * hiker weighs against their storage, not one archive's share of it.
 *
 * Light comes back with a null size: the pipeline cuts the basemap at z13
 * and z14 and nothing below (lib/hikingDetail.ts), so there is no lighter
 * hiking sheet to offer. It is still drawn, greyed, rather than left out -
 * see the header.
 */
export function hikingDetailOptions(): DetailOption[] {
  return LEVEL_LADDER.map(({ id, label }) => {
    const detail = HIKING_DETAIL_LEVELS.find((level) => level.level === id)
    return {
      id,
      label,
      sizeBytes: detail === undefined ? null : hikingSheetSizeBytes(detail.level),
      recommended: detail?.recommended ?? false,
    }
  })
}

/**
 * The ladder with nothing behind any rung - what a sheet gets before anyone
 * has wired it a level set.
 *
 * A sheet with no dial used to render no picker, which under tabs is the
 * ambiguity this change exists to remove. Three greyed rows say "no levels
 * published for this map" out loud, and a new sheet that reaches a screen
 * before its options do says something true rather than nothing.
 */
export function noDetailOptions(): DetailOption[] {
  return LEVEL_LADDER.map(({ id, label }) => ({
    id,
    label,
    sizeBytes: null,
    recommended: false,
  }))
}

export interface DetailPickerProps {
  options: readonly DetailOption[]
  value: string
  onChange: (id: string) => void
  /** Every level greyed because no choice can be taken here at all - bytes
   *  already on the phone or on their way, or a screen that is showing this
   *  sheet rather than configuring it. `lockedNote` says which. */
  locked?: boolean
  lockedNote?: string
  /** Distinguishes the radio group when two pickers share a page - and two
   *  do, now that both sheets' cards carry one. */
  name?: string
}

export function DetailPicker({
  options,
  value,
  onChange,
  locked = false,
  lockedNote,
  name = 'map-detail',
}: DetailPickerProps) {
  return (
    <fieldset className="detail-picker">
      <legend className="detail-picker__legend">Map detail</legend>

      {options.map((option) => {
        const offered = option.sizeBytes !== null
        const disabled = locked || !offered

        return (
          <label
            key={option.id}
            className="detail-picker__option"
            data-disabled={disabled}
          >
            <input
              type="radio"
              name={name}
              value={option.id}
              // Never pre-selected where the level does not exist: a checked
              // "Light" on a sheet that has no Light cut would state a size
              // this download is not.
              checked={offered && value === option.id}
              disabled={disabled}
              onChange={() => onChange(option.id)}
            />
            <span className="detail-picker__name">{option.label}</span>
            <span className="detail-picker__size">
              {option.sizeBytes === null ? 'Not offered' : formatBytes(option.sizeBytes)}
            </span>
            {option.recommended && offered && (
              <span className="detail-picker__recommended">Recommended</span>
            )}
          </label>
        )
      })}

      {locked && lockedNote !== undefined && (
        <p className="detail-picker__note">{lockedNote}</p>
      )}
    </fieldset>
  )
}
