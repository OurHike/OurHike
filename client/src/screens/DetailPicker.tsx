// A download-level choice, shared by the Downloads screen's cards and
// onboarding so the two can never drift apart.
//
// Options-driven since #276, because there are two sheets with two different
// level sets now: the USGS raster's Light/Standard/Fine tiers and the hiking
// sheet's Standard/Fine cuts. The options carry their real measured sizes -
// rendered through lib/formatBytes.ts rather than typed as copy - and the
// builders below are the only places each sheet's options are assembled, so
// a size shown anywhere is the same size shown everywhere.

import { DOWNLOAD_DETAIL_LEVELS, type DetailLevel } from '../lib/downloadDetail'
import { HIKING_DETAIL_LEVELS } from '../lib/hikingDetail'
import { hikingSheetSizeBytes } from '../lib/packages'
import type { HikingDetailLevel } from '../lib/userPreferences'
import { formatBytes } from '../lib/formatBytes'

export interface DetailOption {
  id: string
  label: string
  sizeBytes: number
  recommended: boolean
}

const RASTER_LEVEL_LABELS: Record<DetailLevel, string> = {
  light: 'Light',
  standard: 'Standard',
  fine: 'Fine',
}

/** The USGS raster's tiers, sizes from downloadDetail.ts. */
export function rasterDetailOptions(): DetailOption[] {
  return DOWNLOAD_DETAIL_LEVELS.map((detail) => ({
    id: detail.level,
    label: RASTER_LEVEL_LABELS[detail.level],
    sizeBytes: detail.sizeBytes,
    recommended: detail.recommended,
  }))
}

const HIKING_LEVEL_LABELS: Record<HikingDetailLevel, string> = {
  standard: 'Standard',
  fine: 'Fine',
}

/** The hiking sheet's levels (#276). Each option's size is the WHOLE sheet
 *  at that level - the basemap cut plus the DEM - because that is the number
 *  a hiker weighs against their storage, not one archive's share of it. */
export function hikingDetailOptions(): DetailOption[] {
  return HIKING_DETAIL_LEVELS.map((detail) => ({
    id: detail.level,
    label: HIKING_LEVEL_LABELS[detail.level],
    sizeBytes: hikingSheetSizeBytes(detail.level),
    recommended: detail.recommended,
  }))
}

export interface DetailPickerProps {
  options: readonly DetailOption[]
  value: string
  onChange: (id: string) => void
  /** Distinguishes the radio group when two pickers share a page - and two
   *  do, now that both sheets' cards carry one. */
  name?: string
}

export function DetailPicker({
  options,
  value,
  onChange,
  name = 'map-detail',
}: DetailPickerProps) {
  return (
    <fieldset className="detail-picker">
      <legend className="detail-picker__legend">Map detail</legend>

      {options.map((option) => (
        <label key={option.id} className="detail-picker__option">
          <input
            type="radio"
            name={name}
            value={option.id}
            checked={value === option.id}
            onChange={() => onChange(option.id)}
          />
          <span className="detail-picker__name">{option.label}</span>
          <span className="detail-picker__size">{formatBytes(option.sizeBytes)}</span>
          {option.recommended && (
            <span className="detail-picker__recommended">Recommended</span>
          )}
        </label>
      ))}
    </fieldset>
  )
}
