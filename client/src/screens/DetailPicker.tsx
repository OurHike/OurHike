// The Light / Standard / Fine choice, shared by onboarding's "map size" step
// and the Downloads screen so the two can never drift apart.
//
// This is the detail for ONE whole-corridor package (WIREFRAMES.md Known
// Deviations #1 - the wireframe's per-section override sheet is retired). The
// sizes come from lib/downloadDetail.ts's real measured figures and are
// rendered through lib/formatBytes.ts rather than typed as copy.

import { DOWNLOAD_DETAIL_LEVELS, type DetailLevel } from '../lib/downloadDetail'
import { formatBytes } from '../lib/formatBytes'

const LEVEL_LABELS: Record<DetailLevel, string> = {
  light: 'Light',
  standard: 'Standard',
  fine: 'Fine',
}

export interface DetailPickerProps {
  value: DetailLevel
  onChange: (level: DetailLevel) => void
  /** Distinguishes the radio group when two pickers share a page. */
  name?: string
}

export function DetailPicker({
  value,
  onChange,
  name = 'map-detail',
}: DetailPickerProps) {
  return (
    <fieldset className="detail-picker">
      <legend className="detail-picker__legend">Map detail</legend>

      {DOWNLOAD_DETAIL_LEVELS.map((detail) => (
        <label key={detail.level} className="detail-picker__option">
          <input
            type="radio"
            name={name}
            value={detail.level}
            checked={value === detail.level}
            onChange={() => onChange(detail.level)}
          />
          <span className="detail-picker__name">{LEVEL_LABELS[detail.level]}</span>
          <span className="detail-picker__size">{formatBytes(detail.sizeBytes)}</span>
          {detail.recommended && (
            <span className="detail-picker__recommended">Recommended</span>
          )}
        </label>
      ))}
    </fieldset>
  )
}
