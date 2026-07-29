// The legend bottom sheet (WIREFRAMES.md §2).
//
// It answers "what am I looking at right now," so its contents are derived
// from the current viewport on every render rather than held in state - pan
// the map and the counts change. It is deliberately NOT the settings list of
// every possible category; WIREFRAMES.md puts that in Settings.
//
// Closure and serious-warning rows render with no hide control whatsoever.
// Not defaulted-on, not disabled - absent. A safety layer having no off switch
// is a rule that holds across the whole app (features/MAP_OPTIONS.md,
// features/HIKER_SAFETY.md), and the surest way to keep it is to never build
// the affordance.

import {
  computeLegendContents,
  type BoundingBox,
  type MapPoint,
} from '../lib/legendContents'
import { blazePaintColor } from '../lib/blaze'
import { typeLabel } from './legendLabels'

export interface BlazeCount {
  blaze: string
  count: number
}

export interface LegendProps {
  open: boolean
  bbox: BoundingBox
  points: MapPoint[]
  blazeCounts: BlazeCount[]
  hiddenTypes: Set<string>
  onToggleType: (type: string) => void
  onClose: () => void
}

export function Legend({
  open,
  bbox,
  points,
  blazeCounts,
  hiddenTypes,
  onToggleType,
  onClose,
}: LegendProps) {
  if (!open) return null

  const rows = computeLegendContents(bbox, points)
  const isEmpty = rows.length === 0 && blazeCounts.length === 0

  return (
    <div className="legend" role="dialog" aria-label="Legend" aria-modal="true">
      <div className="legend__head">
        <h2 className="legend__title">Legend</h2>
        <button type="button" className="legend__close" onClick={onClose}>
          <span className="visually-hidden">Close legend</span>
          <span aria-hidden="true">×</span>
        </button>
      </div>

      {isEmpty && (
        <p className="legend__empty">
          Nothing on this part of the map yet — pan or zoom out to see more.
        </p>
      )}

      {blazeCounts.length > 0 && (
        <ul className="legend__blazes">
          {blazeCounts.map(({ blaze, count }) => (
            <li key={blaze} className="legend__row" aria-label={`${blaze} blaze`}>
              <span
                className="legend__swatch"
                style={{ backgroundColor: blazePaintColor(blaze) }}
                aria-hidden="true"
              />
              <span className="legend__label">{blaze}</span>
              <span className="legend__count">{count}</span>
            </li>
          ))}
        </ul>
      )}

      {rows.length > 0 && (
        <ul className="legend__pins">
          {rows.map((row) => {
            const name = typeLabel(row.type)
            const unverified = row.confidence === 'low'
            const label = unverified ? `${name} · Unverified` : name

            return (
              <li
                key={`${row.type}::${row.confidence}`}
                className="legend__row"
                aria-label={label}
              >
                <span className="legend__label">{label}</span>
                <span className="legend__count">{row.count}</span>

                {row.hideable ? (
                  <button
                    type="button"
                    className="legend__toggle"
                    aria-pressed={hiddenTypes.has(row.type)}
                    onClick={() => onToggleType(row.type)}
                  >
                    <span className="visually-hidden">
                      {hiddenTypes.has(row.type) ? `Show ${name}` : `Hide ${name}`}
                    </span>
                    <span aria-hidden="true">
                      {hiddenTypes.has(row.type) ? '◌' : '●'}
                    </span>
                  </button>
                ) : (
                  <span className="legend__always">Always shown</span>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </div>
  )
}
