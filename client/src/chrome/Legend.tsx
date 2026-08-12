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
// the affordance. That rule is why the row is not uniformly a button: a
// hideable row IS one, edge to edge, and a safety row is plain text with an
// "Always shown" tag beside it.
//
// Every row carries the icon the map draws for it, from map/MapIcon.tsx and
// therefore from the map's own geometry rather than from a second drawing of
// it - a legend that approximates the map teaches a symbol the map does not
// use, which is worse than a legend with no pictures in it.
//
// One row per category, never one per category per confidence: the reasoning
// is on lib/legendContents.ts's LegendRow, and the consequence here is that
// the pin drawn is the solid-rimmed one.

import {
  computeLegendContents,
  type BoundingBox,
  type MapPoint,
} from '../lib/legendContents'
import { MapIcon } from '../map/MapIcon'
import { blazePaintColor } from '../lib/blaze'
import { typeLabel } from './legendLabels'
import { BackgroundPicker } from './BackgroundPicker'
import { DownloadsLink } from './DownloadsLink'
import type { BackgroundSource } from '../lib/userPreferences'
import type { BackgroundOverride } from '../lib/dataSaver'
import type { DownloadActivity } from '../lib/downloadActivity'

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
  /**
   * Draw only waypoints somebody has confirmed exist.
   *
   * This is what became of the "Unverified" rows. They doubled the length of
   * the grid to carry a distinction a viewport count cannot act on; one
   * checkbox carries the same fact as a decision instead, and the counts above
   * it move with it so the panel never claims more than the map is drawing.
   *
   * Never applies to closures or serious warnings - see legendContents.ts.
   */
  verifiedOnly?: boolean
  onToggleVerifiedOnly?: () => void
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
  /** Whether the view is zoomed out past what the download covers (#216). */
  belowArchiveZoom?: boolean
  /** Opens the download window, from the link at the foot of the panel.
   *  Passed straight through: this panel has no opinion about downloads, it is
   *  just the piece of chrome the link ended up in. Omitted, no link is drawn
   *  - a control that does nothing is worse than one that is not there. */
  onOpenDownloads?: () => void
  /** Whether a finished archive is on the phone, which words that link. */
  hasDownload?: boolean
  /** What is downloading right now, if anything - passed through to the link,
   *  which is where it is drawn (lib/downloadActivity.ts). This panel is one
   *  tap from the map, so it is where a hiker who started a download and shut
   *  its window will actually look to find out whether it is still going. */
  downloadActivity?: DownloadActivity | null
}

export function Legend({
  open,
  persistent = false,
  bbox,
  points,
  blazeCounts,
  hiddenTypes,
  onToggleType,
  verifiedOnly = false,
  onToggleVerifiedOnly,
  onClose,
  backgroundChoice,
  onChangeBackground,
  backgroundOverride = null,
  belowArchiveZoom = false,
  onOpenDownloads,
  hasDownload = false,
  downloadActivity = null,
}: LegendProps) {
  if (!open && !persistent) return null

  const rows = computeLegendContents(bbox, points, verifiedOnly)
  const isEmpty = rows.length === 0 && blazeCounts.length === 0

  // An empty grid has two quite different causes and one of them is this
  // panel's own doing. "Nothing here yet, pan or zoom out" is a false claim
  // about a stretch with six unconfirmed springs on it, and it sends a hiker
  // walking away from the water. Costs a second pass over the same points,
  // only while the filter is on.
  const emptiedByFilter =
    verifiedOnly && rows.length === 0 && computeLegendContents(bbox, points).length > 0

  // Gates the wrapper only. The picker's own two props are re-checked where it
  // is drawn, because that is what narrows them from optional to present - and
  // an empty block would still take the desktop panel's `margin-top: auto`.
  const hasPicker = backgroundChoice !== undefined && onChangeBackground !== undefined

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

      {isEmpty && !emptiedByFilter && (
        <p className="legend__empty">
          Nothing on this part of the map yet — pan or zoom out to see more.
        </p>
      )}

      {emptiedByFilter && (
        <p className="legend__empty">
          Nothing here has been confirmed yet — turn Verified? off to see what is
          reported.
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
            const label = typeLabel(row.type)
            const hidden = row.hideable && hiddenTypes.has(row.type)

            // The pin, the name and the count, in that order. On a hideable
            // row all three go inside the button, which is the whole point:
            // WIREFRAMES.md §2 has said "rows are tappable to hide" since
            // before this panel was built, and what shipped was a 20px dot at
            // the end of a 44px row that looked tappable across its width.
            // A tap on the word "Water" did nothing and said nothing.
            const face = (
              <>
                {/* No confidence passed, so this is the solid-rimmed pin. A key
                    says what a category's symbol IS, and a symbol that changed
                    its rim as you panned - broken here because the two springs
                    in view happen to be unconfirmed, solid a mile later - would
                    not be a key. The rim still means what it means on the map,
                    one pin at a time, which is where it is a fact about
                    something rather than about a rectangle. */}
                <MapIcon className="legend__icon" type={row.type} />
                <span className="legend__label">{label}</span>
                <span className="legend__count">{row.count}</span>
              </>
            )

            return (
              <li
                key={row.type}
                className={[
                  'legend__row',
                  // A safety row is wider than a column, because it carries an
                  // "Always shown" tag on top of what every other row carries.
                  row.hideable ? null : 'legend__row--always',
                  hidden ? 'legend__row--hidden' : null,
                ]
                  .filter(Boolean)
                  .join(' ')}
                aria-label={label}
              >
                {row.hideable ? (
                  <button
                    type="button"
                    className="legend__toggle"
                    /* Pressed means SHOWN, which is the opposite of what this
                       said while the control was a separate dot. That button
                       was a "hide" action and pressed meant the action was
                       engaged; the row is now the category itself, and it
                       greys out when the category is off. Leaving the old
                       polarity would have a row that plainly reads as off
                       announcing itself as pressed - the screen and the
                       screen reader disagreeing about one control. */
                    aria-pressed={!hidden}
                    onClick={() => onToggleType(row.type)}
                  >
                    {face}
                  </button>
                ) : (
                  <>
                    {face}
                    <span className="legend__always">Always shown</span>
                  </>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {/* Under the grid rather than in it, because it is not a category: it
          cuts across every row at once. Rendered whenever the shell offers the
          handler and never gated on there being rows - a filter that empties
          the panel and then disappears with it is a trap, and this one can
          empty the panel. */}
      {onToggleVerifiedOnly !== undefined && (
        <label className="legend__verified">
          <span className="legend__verified-name">Verified?</span>
          <input
            type="checkbox"
            name="verified_only"
            checked={verifiedOnly}
            onChange={onToggleVerifiedOnly}
          />
        </label>
      )}

      {/* THE DOWNLOADED MAP, ALL OF IT, IN ONE BLOCK AT THE FOOT.
          The background choice used to open the panel and the way to the
          download has always closed it, which put the two ends of one question
          at the two ends of the panel: "Downloaded" draws the corridor archive
          and nothing else, and the link below is where a corridor archive comes
          from. Choosing a background this phone has no map to honour meant
          reading the note that says so, then scrolling past every legend row to
          reach the only control that fixes it. They are one errand and they sit
          together now, with the picker's own notes - "nothing is downloaded
          yet", "your download starts closer in than this" - landing directly
          above the link that answers them.

          Last, and the legend rows start the panel because of it. A hiker opens
          this all day to ask what is around them and a handful of times ever to
          change what is on the phone, so the daily question keeps the top. On a
          desktop the panel is full height and this whole block is pushed to the
          bottom of it - see desktop.css, which pushes the block rather than the
          link precisely so the two do not come apart again. */}
      {(hasPicker || onOpenDownloads !== undefined) && (
        <div className="legend__downloads">
          {backgroundChoice !== undefined && onChangeBackground !== undefined && (
            <BackgroundPicker
              value={backgroundChoice}
              onChange={onChangeBackground}
              override={backgroundOverride}
              belowArchiveZoom={belowArchiveZoom}
              idPrefix="legend"
            />
          )}

          {onOpenDownloads !== undefined && (
            <DownloadsLink
              onOpen={onOpenDownloads}
              hasDownload={hasDownload}
              downloadActivity={downloadActivity}
            />
          )}
        </div>
      )}
    </div>
  )
}
