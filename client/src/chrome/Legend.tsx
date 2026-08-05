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
import { BackgroundPicker } from './BackgroundPicker'
import { DownloadsLink } from './DownloadsLink'
import type { BackgroundSource } from '../lib/userPreferences'
import type { BackgroundOverride } from '../lib/dataSaver'

export interface BlazeCount {
  blaze: string
  count: number
}

export interface LegendProps {
  open: boolean
  /** A permanent side panel rather than a sheet over the map (WEBSITE.md §6).
   *
   *  Not styling. A persistent legend is always rendered, is not a dialog, is
   *  not modal, and has nothing to close - four things a stylesheet cannot
   *  express, which is why this is a prop and not a media query. Announcing a
   *  panel that is always on screen as an `aria-modal` dialog would tell a
   *  screen-reader user the rest of the app is inert when it is not. */
  persistent?: boolean
  bbox: BoundingBox
  points: MapPoint[]
  blazeCounts: BlazeCount[]
  hiddenTypes: Set<string>
  onToggleType: (type: string) => void
  onClose: () => void
  /**
   * The stored background preference, and how to change it.
   *
   * Here rather than only in Settings because this panel is one tap from the
   * map and already answers "what am I looking at" - and the moment someone
   * wants to change the background is the moment the map is not showing what
   * they expected, which is the worst moment to send them hunting through a
   * settings screen. Omitted together when the legend is rendered without a
   * shell to write the preference back to, and then no picker is drawn.
   */
  backgroundChoice?: BackgroundSource
  onChangeBackground?: (next: BackgroundSource) => void
  /** Why the drawn background differs from the choice - see lib/dataSaver.ts. */
  backgroundOverride?: BackgroundOverride | null
  /** Opens the download window, from the link at the foot of the panel.
   *  Passed straight through: this panel has no opinion about downloads, it is
   *  just the piece of chrome the link ended up in. Omitted, no link is drawn
   *  - a control that does nothing is worse than one that is not there. */
  onOpenDownloads?: () => void
  /** Whether a finished archive is on the phone, which words that link. */
  hasDownload?: boolean
}

export function Legend({
  open,
  persistent = false,
  bbox,
  points,
  blazeCounts,
  hiddenTypes,
  onToggleType,
  onClose,
  backgroundChoice,
  onChangeBackground,
  backgroundOverride = null,
  onOpenDownloads,
  hasDownload = false,
}: LegendProps) {
  if (!open && !persistent) return null

  const rows = computeLegendContents(bbox, points)
  const isEmpty = rows.length === 0 && blazeCounts.length === 0

  return (
    <div
      className={persistent ? 'legend legend--persistent' : 'legend'}
      // A region, not a dialog, when it is simply part of the page.
      role={persistent ? 'region' : 'dialog'}
      aria-label="Legend"
      aria-modal={persistent ? undefined : true}
    >
      <div className="legend__head">
        <h2 className="legend__title">Legend</h2>
        {/* A close button on a panel that cannot be reopened is a trap: the
            control that opens it is hidden at this width precisely because
            the legend is always there. */}
        {!persistent && (
          <button type="button" className="legend__close" onClick={onClose}>
            <span className="visually-hidden">Close legend</span>
            <span aria-hidden="true">×</span>
          </button>
        )}
      </div>

      {/* First, above the counts. The background is the largest thing on the
          screen and the counts describe what is drawn on top of it, so the
          question "what am I looking at" is answered in that order. */}
      {backgroundChoice !== undefined && onChangeBackground !== undefined && (
        <BackgroundPicker
          value={backgroundChoice}
          onChange={onChangeBackground}
          override={backgroundOverride}
          idPrefix="legend"
        />
      )}

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

      {/* Last in the panel, and last on purpose. It is the only way to the
          download (chrome/DownloadsLink.tsx), which makes it worth having
          here and does not make it worth the top of a panel someone opens all
          day to answer a different question. On a desktop the panel is full
          height and this is pushed to the foot of it - see desktop.css. */}
      {onOpenDownloads !== undefined && (
        <DownloadsLink onOpen={onOpenDownloads} hasDownload={hasDownload} />
      )}
    </div>
  )
}
