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
import { HIDEABLE_TYPES, shownSelection } from '../lib/waypointVisibility'
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

// The two picker entries that are not a category. Sentinels rather than the
// empty string, so no waypoint type can ever collide with one, and not exported
// because a module that exports both a component and a value breaks React Fast
// Refresh (see chrome/legendLabels.ts).
const ALL_TYPES = '\0all'
const SOME_TYPES = '\0some'

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
   * Show this one category and nothing else (#530).
   *
   * The control that makes this preference worth having rather than tidy: hiding
   * a category hands its collision budget to the ones left, so at a crowded zoom
   * this is the difference between four water pins drawn and forty, and it
   * answers "where is the next water" in two taps instead of by zooming in and
   * panning along the trail.
   *
   * Omitted, no row offers it - a legend rendered without a shell to write the
   * preference back to must not offer a control that goes nowhere.
   */
  onOnlyType?: (type: string) => void
  /** Back to every category - the same control's "All types", not a second one
   *  beside it. Both handlers are halves of one picker, so it renders only when
   *  the shell offers both; a picker that can enter a filter and not leave it is
   *  the trap this issue is most able to build. */
  onShowAllTypes?: () => void
  /** The stored preference, which is what the picker DISPLAYS. Absent, it reads
   *  "All types" - the state a fresh install is in. */
  typesShown?: readonly string[]
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
  onOnlyType,
  onShowAllTypes,
  typesShown,
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

  // What the type picker shows. Not a placeholder: a picker sitting at "Show one
  // only…" over a map drawing water alone is a control disowning its own state.
  const shown = shownSelection(typesShown ?? [])
  const shownValue =
    shown.kind === 'all' ? ALL_TYPES : shown.kind === 'one' ? shown.type : SOME_TYPES

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

      {/* Which categories are drawn. Under the grid rather than in it, because it
          is not a category: it cuts across every row at once. NOT gated on there
          being rows, for exactly the reason the verified control below is not -
          "only privies" in a stretch with no privies empties this panel, and an
          exit that disappears along with the rows is the trap that leaves.

          ONE control, and one that DISPLAYS the state rather than describing it
          in prose beside itself. What stood here was a sentence, an exit button
          and a placeholder menu strung together with middots, and at the 272px
          the desktop panel actually is (desktop.css `flex: 0 0 17rem`) that line
          wrapped and left a dangling separator with the menu orphaned under it.
          The menu also had no border, so `Show one only…` read as more of the
          sentence it sat in rather than as a control - photographed at both
          widths before being changed, not guessed at.

          Collapsing the three into one is not only tidier, it removes a
          contradiction: the sentence and the placeholder both spoke about the
          filter, and the placeholder always said the same thing whatever the
          sentence said. A picker whose selected value IS the state cannot
          disagree with itself, and "All types" is the exit, so nothing is lost
          with the button.

          Rows stay a plain hide/show toggle and this stays global. Cycling a row
          through a third "only" state would have been worse than either: from
          "only water", a tap on the privy row has no defined meaning - privy is
          already undrawn, and what changed was never privy's own state - and it
          would break the row's `aria-pressed`, which #580 made binary.

          A native select because it is one line at rest, opens to the full list,
          and is reachable by keyboard without any of that being written here. It
          lists every hideable category rather than only those in view, which
          answers the second consequence #530 lists: a category with nothing in
          the viewport has no row, and could not otherwise be reached from this
          panel at all. */}
      {onOnlyType !== undefined && onShowAllTypes !== undefined && (
        <label className="legend__shown">
          <span className="legend__shown-name">Showing</span>
          {/* Named in full on the control, and STARTING with the visible word
              beside it, which is what WCAG 2.5.3 asks of anything a hiker might
              address by the label they can see. Spelt out rather than assembled
              from the visible word plus a hidden continuation: the accessible
              name of `Showing<hidden> waypoint types</hidden>` computes as
              "Showingwaypoint types" - the joining space is dropped, and a
              screen reader reads it as one word. */}
          <select
            aria-label="Showing waypoint types"
            className="legend__shown-select"
            value={shownValue}
            onChange={(event) => {
              const next = event.target.value
              if (next === ALL_TYPES) onShowAllTypes()
              // SOME_TYPES is the state the row toggles put the map in, and it
              // is only ever the selected entry - choosing what is already
              // chosen fires nothing. Guarded anyway: it is not a category, and
              // handing it to `onOnlyType` would write it to the preference.
              else if (next !== SOME_TYPES) onOnlyType(next)
            }}
          >
            {/* Present only while it is true, because it is a readout rather
                than a choice: several categories showing is reachable by
                toggling rows, and there is no single tap that means it. */}
            {shown.kind === 'some' && (
              <option value={SOME_TYPES}>
                {shown.shown} of {shown.of} types
              </option>
            )}
            <option value={ALL_TYPES}>All types</option>
            {HIDEABLE_TYPES.map((type) => (
              <option key={type} value={type}>
                {typeLabel(type)}
              </option>
            ))}
          </select>
        </label>
      )}

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
