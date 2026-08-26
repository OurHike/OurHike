// The legend bottom sheet (WIREFRAMES.md §2).
//
// It answers "what am I looking at right now," so its COUNTS are derived from
// the current viewport on every render rather than held in state - pan the map
// and they change.
//
// The rows it puts those counts on are every hideable category, in view or not
// (#723). That is not the panel giving up on the viewport - it is the rows
// having a second job. They are the hide toggles, and a toggle that exists only
// while something of its category is on screen is a switch a hiker cannot find
// when they want it: features/POI_VISIBILITY.md's density table puts 2-4
// waypoints in a phone map at z14, so the panel carrying eight toggles was
// routinely showing two. `withEveryType` in lib/legendContents.ts pads the grid
// and nothing else, so every sentence on this panel still speaks only about what
// is in front of the hiker. WIREFRAMES.md §2 is amended to match; Settings keeps
// its own copy of the list, which is where somebody setting the app up rather
// than reading a map will look.
//
// NO BLAZE ROWS, AND WHAT THAT COSTS (maintainer's call, 2026-08-25).
//
// The panel used to open with one row per blaze in view - a painted line
// swatch, the blaze name, the count - shipped by #782 and removed on the
// request "the legend doesn't need the color of the blaze included... it's too
// cluttered". Recorded here rather than deleted quietly, because the rows were
// not free to lose and the next person to reach for them should find the
// argument rather than re-run it.
//
// What went with them is the only KEY this app had for its line colours. The
// map paints a trail by its blaze (map/style.ts's `blazeLineColor`, over
// lib/blaze.ts's closed palette - both untouched here, so the lines look
// exactly as they did), and nothing on this panel now says which paint means
// which blaze.
//
// Two things carry that instead, and they are why the cost is affordable
// rather than why it is zero:
//
//   - a blaze name IS a colour word, so a line is closer to self-describing
//     than a pin ever is: the thing a hiker reads off the map is the same
//     word the legend would have printed;
//   - a tapped line still names its blaze in full - `lib/lineDetail.ts`'s
//     heading is "White blaze · Appalachian Trail", drawn by
//     chrome/LineSheet.tsx - which is where somebody asking about one
//     particular line in front of them is already looking.
//
// Neither covers the case the rows did cover: "what is on this screen",
// answered without tapping anything. @unvalidated - nobody has watched a hiker
// try, and what would settle it is somebody using this panel on a stretch
// where two trail systems overlap and reporting whether the lines are
// legible without a key.
//
// Closure and serious-warning rows still render with no hide control of their
// own - plain text with a tag beside them, where a hideable row is a button
// edge to edge. That much is unchanged and is why the row is not uniformly a
// button.
//
// WHAT CHANGED IS THE RULE BEHIND IT (#1047, maintainer's call). "A safety
// layer has no off switch anywhere in the app" was the whole answer until this
// panel gained an Alerts switch below the grid, and features/MAP_OPTIONS.md
// had always flagged that rule as "a recommendation, not force-decided". The
// half that survives is the half that could have lasted for days: the stored
// `waypoint_types_shown` filter still cannot reach a closure, which is why
// these rows are not buttons and why lib/legendContents.ts's NEVER_HIDEABLE is
// untouched. The half that went is permanence - a hiker can clear the bands
// off the canvas for as long as they are looking at it, and the app gives them
// back at the next open (chrome/alertLayerPanel.ts).
//
// So these rows now say which of the two states they are in, and grey out with
// the switch. A row promising "Always shown" over a map a hiker has just
// cleared would be this panel disagreeing with the screen beside it, which is
// the one thing a legend may never do.
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
  GHOSTED_TRAILS_NOTE,
  legendDropSummary,
  withEveryType,
  type BoundingBox,
  type MapPoint,
} from '../lib/legendContents'
import { MapIcon } from '../map/MapIcon'
import { HIDEABLE_TYPES, shownSelection } from '../lib/waypointVisibility'
import { typeLabel } from './legendLabels'
import { BackgroundPicker } from './BackgroundPicker'
import { DownloadsLink } from './DownloadsLink'
import type { BackgroundSource, UnitSystem } from '../lib/userPreferences'
import { formatDistance } from '../lib/units'
import type { BackgroundOverride } from '../lib/dataSaver'
import type { DownloadActivity } from '../lib/downloadActivity'

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
  /** Whether a trail from outside the chosen system is on screen (#783), which
   *  is the only condition under which the ghosting sentence means anything. */
  ghostedTrailsDrawn?: boolean
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
  /**
   * Whether the alert marks are on the canvas (#1047).
   *
   * Read twice on this panel and for two different jobs: it is what the Alerts
   * switch displays, and it is what the closure and serious-warning rows in
   * the grid say about themselves. A row tagged "Alerts" over a map with no
   * band on it would be this panel making the exact claim it exists to
   * prevent - see the header comment.
   *
   * Defaults to drawn, like MapScreen's own prop and for the same reason.
   */
  alertsShown?: boolean
  /**
   * Takes them off, and puts them back.
   *
   * Omitted, no switch is drawn, and a panel drawing alerts says "Always
   * shown" on its safety rows - which is exactly what they are where nothing
   * here can hide them. The two branches are one fact, not two designs.
   *
   * What this does NOT decide is a panel handed `alertsShown={false}` with no
   * handler: the screen wins, the rows grey, and the tag reads "Alerts off".
   * A tag is a statement about the map, never about what this panel can offer.
   */
  onToggleAlerts?: () => void
  /**
   * The drought wash, and how to turn it off (#720).
   *
   * Here for the same reason the background picker is: this panel is one tap
   * from the map and already answers "what am I looking at", and a tint over
   * the whole map is exactly the thing somebody wants to switch off at the
   * moment they notice it - not after finding a settings screen.
   *
   * Its row states the week and the trail miles rather than only naming the
   * layer, because the numbers are the whole content: "1,388 mi affected,
   * week of 11 Aug" is the claim, and a switch labelled "Drought" would leave
   * a hiker to guess how current it is.
   */
  droughtShown?: boolean
  onToggleDrought?: () => void
  /** What the bands say, for that row's summary line. Empty when none
   *  arrived, which draws no numbers rather than a confident zero. */
  droughtSummary?: { miles: number; weekStart: Date | null }
  /** The hiker's unit system, for that row's distance. Required with
   *  `droughtSummary`: CONTRIBUTING.md's units standard says every
   *  distance a hiker reads comes out of lib/units.ts in the system they
   *  chose, and a legend printing miles under a metric map is exactly the
   *  disagreement that rule exists to stop. */
  units?: UnitSystem
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
  /** Whether "downloaded only" is a background this phone can get at all -
   *  false since the USGS sheet was withdrawn (#855), except on a phone that
   *  already holds it. Carried rather than derived here: it is the shell that
   *  knows what is on the phone. See chrome/BackgroundPicker.tsx. */
  offlineBackgroundAvailable?: boolean
  /**
   * How many waypoints of each category the map actually drew
   * (map/drawnPois.ts). Omitted where nobody measured, and then the rows read
   * exactly as they did before #528.
   */
  drawnCounts?: ReadonlyMap<string, number>
  /**
   * Whether the camera is below POI_PIN_MIN_ZOOM, where neither waypoint rank
   * is drawn at all.
   *
   * Its own flag rather than inferred from an empty row list, because the two are
   * different facts with opposite remedies: nothing here, or everything here and
   * none of it drawable yet. The panel said the wrong one at the opening view.
   *
   * "The pin layer" until #597 landed a second rank under it. Below the seam
   * both are absent, so the sentence this gates is still the true one - but the
   * reason is now the seam rather than one layer's floor.
   */
  belowPoiZoom?: boolean
  /** Opens the download window, from the link at the foot of the panel.
   *  Passed straight through: this panel has no opinion about downloads, it is
   *  just the piece of chrome the link ended up in. Omitted, no link is drawn
   *  - a control that does nothing is worse than one that is not there. */
  /**
   * Who maintains the trail in front of the hiker - "Maintained by the
   * Potomac Appalachian Trail Club" (#598).
   *
   * A SENTENCE rather than a club, because the shell is what holds the
   * published attribution and the centerline index that turns the camera into
   * a mile; this panel has no business asking for either. The same division
   * `drawnCounts` keeps.
   *
   * Absent above nothing in particular: it is omitted below the seam, where
   * the map itself is drawing the answer and a second copy in the legend would
   * be the panel repeating the screen.
   */
  maintainerLine?: string | null
  onOpenDownloads?: () => void
  /** Whether a finished archive is on the phone, which words that link. */
  hasDownload?: boolean
  /** What is downloading right now, if anything - passed through to the link,
   *  which is where it is drawn (lib/downloadActivity.ts). This panel is one
   *  tap from the map, so it is where a hiker who started a download and shut
   *  its window will actually look to find out whether it is still going. */
  downloadActivity?: DownloadActivity | null
  /**
   * How many ATC trail updates the app is holding, for the row that opens
   * all of them (#687). Zero, or the shell not passing it, renders no row -
   * the same "count rather than the notices" reasoning MapScreen's own prop
   * of this name documents.
   *
   * This is the row that used to be a permanent button across the top of the
   * map screen. It moved here because browsing every notice on the trail,
   * whether or not any of it changed lately, is exactly the kind of rare
   * errand this panel's own download link already exists for - "a hiker
   * opens this all day to ask what is nearby, a handful of times ever to do
   * this." What is actually NEW gets its own bottom banner on the map screen
   * instead, which this row has no opinion about.
   */
  atcNoticeCount?: number
  /** Opens the full list (chrome/AtcNoticeList.tsx), rendered by the shell
   *  the same way `onOpenDownloads` is. */
  onOpenAtcNotices?: () => void
}

export function Legend({
  open,
  persistent = false,
  bbox,
  points,
  ghostedTrailsDrawn = false,
  hiddenTypes,
  onToggleType,
  onOnlyType,
  onShowAllTypes,
  typesShown,
  verifiedOnly = false,
  alertsShown = true,
  onToggleAlerts,
  droughtShown = false,
  onToggleDrought,
  droughtSummary,
  units = 'imperial',
  onToggleVerifiedOnly,
  onClose,
  backgroundChoice,
  onChangeBackground,
  backgroundOverride = null,
  belowArchiveZoom = false,
  offlineBackgroundAvailable = true,
  drawnCounts,
  belowPoiZoom = false,
  maintainerLine = null,
  onOpenDownloads,
  hasDownload = false,
  downloadActivity = null,
  atcNoticeCount = 0,
  onOpenAtcNotices,
}: LegendProps) {
  if (!open && !persistent) return null

  // TWO LISTS, AND KEEPING THEM APART IS THE WHOLE OF #723.
  //
  // `inView` is what this panel has always computed and is what every SENTENCE
  // below is decided by - "nothing on this part of the map yet", "turn Verified?
  // off", the drop summary, the below-the-pin-floor line. Those speak about the
  // viewport, and none of them may start speaking about the category list.
  //
  // `rows` is the grid, which is also the hide toggles, and that job wants every
  // category whether or not one is in front of the hiker right now. A row
  // reading `Privy 0` is an accurate statement about this rectangle and a
  // working switch; no row at all was neither.
  const inView = computeLegendContents(bbox, points, verifiedOnly, drawnCounts)
  const rows = withEveryType(inView, HIDEABLE_TYPES)
  // Minus the categories the hiker hid (#777): their absence is the filter's
  // doing, not the camera's, so they belong in neither half of the fraction -
  // "zoom in to see the rest" must only promise what zooming in delivers.
  const dropped = legendDropSummary(inView, hiddenTypes)
  const isEmpty = inView.length === 0

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
    verifiedOnly && inView.length === 0 && computeLegendContents(bbox, points).length > 0

  // Gates the wrapper only. The picker's own two props are re-checked where it
  // is drawn, because that is what narrows them from optional to present - and
  // an empty block would still take the desktop panel's `margin-top: auto`.
  //
  // The availability test is here as well as inside the picker for exactly
  // that last reason: a picker that renders null (#855) still leaves this
  // wrapper claiming the space, and on the desktop panel that is a visible
  // gap above the downloads link.
  const hasPicker =
    backgroundChoice !== undefined &&
    onChangeBackground !== undefined &&
    offlineBackgroundAvailable

  return (
    <div
      className={persistent ? 'legend legend--persistent' : 'legend'}
      // A region, not a dialog, when it is simply part of the page.
      role={persistent ? 'region' : 'dialog'}
      aria-label="Legend"
      /* No `aria-modal` on the phone panel either (#315). It claimed the
         background was inert, nothing made it so, and Tab walked into the map
         chrome behind - a guarantee to assistive tech that the page does not
         keep, which is worse than not claiming it. screens/DownloadsDialog.tsx
         carries the same correction and the argument for it. */
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

      {/* Below the pin zoom this panel used to render the sentence below, which
          at the opening view is false in both halves: there is plenty here, and
          zooming OUT is the wrong direction (#528). Checked first, so the true
          sentence wins over the general one.

          The background picker used to sit above this and now sits at the foot of
          the panel with the downloads link (#583) - the daily question keeps the
          top. Nothing here moved it back. */}
      {/* Below the pin seam. The sentence changed with #603: the dot rank now
          draws all the way down (map/poiLayers.ts's POI_DOT_MIN_ZOOM), so
          "waypoints are drawn from a closer zoom" became half wrong - they ARE
          drawn here, as dots. What needs a closer zoom is telling one from
          another, which is the pin's job and the thing this panel lists.

          Gated on `inView` rather than `rows`, which is #723's rule and not a
          detail of this sentence: `rows` now carries every hideable category
          whether or not one is in front of the hiker, so it is almost never
          empty and this line would have stopped appearing at all. Every
          sentence in this panel speaks about the viewport. */}
      {belowPoiZoom && inView.length === 0 && (
        <p className="legend__empty">
          Waypoints show as dots at this zoom. Zoom in to see what each one is.
        </p>
      )}

      {/* "No WAYPOINTS", where this said "Nothing", and the word had to change
          when the blaze rows went. `isEmpty` used to consult those rows too, so
          a stretch of drawn trail with no shelter or spring on it suppressed
          this line; it now fires there, and "nothing on this part of the map"
          over a map with the A.T. running down it is the panel claiming an
          emptiness that is not on the screen. Narrowing the noun is what keeps
          the sentence true - the grid below it counts waypoints, and so does
          this. */}
      {isEmpty && !emptiedByFilter && !belowPoiZoom && (
        <p className="legend__empty">
          No waypoints on this part of the map yet — pan or zoom out to see more.
        </p>
      )}

      {emptiedByFilter && (
        <p className="legend__empty">
          Nothing here has been confirmed yet — turn Verified? off to see what is
          reported.
        </p>
      )}

      {/* The summary, above the rows it summarises. Second-order on purpose - the
          per-row figures are where a hiker learns that the category missing is the
          privies, and a single averaged line would hide exactly that. */}
      {dropped !== null && (
        <p className="legend__dropped">
          {dropped.drawn} of {dropped.present} waypoints fit at this zoom. Zoom in to see
          the rest.
        </p>
      )}

      {/* features/NEARBY_TRAILS.md §1's sentence of state - above the pin
          grid, because it is about the LINES on the map and everything below
          it is about the pins. It used to sit above the blaze rows and its
          reason was those rows; with them gone it is the only thing on this
          panel that speaks about the trail lines at all, which is why it
          stayed. No control accompanies it, and that is the decision rather
          than an omission. */}
      {ghostedTrailsDrawn && <p className="legend__note">{GHOSTED_TRAILS_NOTE}</p>}

      {rows.length > 0 && (
        <ul className="legend__pins">
          {rows.map((row) => {
            const label = typeLabel(row.type)
            // A hideable row is off when the hiker hid its category; a safety
            // row is off when the alert marks are off, which is a different
            // switch and the only one that can reach it (#1047). Both end up
            // greyed by the same class, because to a hiker they are the same
            // statement: this is not on the map right now.
            const hidden = row.hideable ? hiddenTypes.has(row.type) : !alertsShown
            // Only where it differs, which keeps the panel quiet at the zooms
            // where nothing is being dropped: `Water 14` and `Water 13/14` are
            // the same row saying as much as is true.
            const short = row.drawnCount !== undefined && row.drawnCount < row.count

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
                {/* ONE SLOT, NOT TWO. This carried the count and then a second
                    `13 shown` badge beside it, and in a two-column grid at
                    390 px that badge does not fit on the line: `3 shown` and
                    `2 shown` wrapped, leaving rows of unequal height and a
                    ragged column edge. Rendered from this repository's own
                    tokens before the change was made, rather than reasoned
                    about - it is the defect, not a preference.

                    The fraction says the same thing in the space the count
                    already had. `0/6` is six here and none drawn; `13/14` is
                    one missing. It also puts the relationship IN the notation,
                    which the two-badge version never did - `9` beside `3 shown`
                    is two numbers with nothing saying one is a subset of the
                    other. Maintainer's call between six renderings, PR #706. */}
                <span className="legend__count">
                  {short ? `${row.drawnCount}/${row.count}` : row.count}
                </span>
              </>
            )

            return (
              <li
                key={row.type}
                className={[
                  'legend__row',
                  // A safety row is wider than a column, because it carries a
                  // tag on top of what every other row carries.
                  row.hideable ? null : 'legend__row--always',
                  hidden ? 'legend__row--hidden' : null,
                ]
                  .filter(Boolean)
                  .join(' ')}
                // The drawn figure goes into the accessible name too, so a
                // screen-reader user hears "Privy, none of 6 shown" rather than
                // a count that is wrong about what is on the map.
                //
                // WORDS HERE, THE FRACTION ON SCREEN, and they are allowed to
                // differ because the two are read by different means. A slash
                // is punctuation a screen reader is free to skip - "13 14" is a
                // plausible rendering of `13/14` and says nothing - so the
                // visual shorthand that fixes the wrapping is exactly the wrong
                // string to hand a reader. `none of 6` rather than `0 of 6` for
                // the same reason PoiCard spells its separators out: zero read
                // in a run of digits is the one that slips past.
                aria-label={
                  short
                    ? `${label} · ${row.drawnCount === 0 ? 'none' : row.drawnCount} of ${row.count} shown`
                    : label
                }
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
                    {/* WHAT THIS TAG SAYS DEPENDS ON WHETHER A SWITCH EXISTS,
                        and that is one fact rather than two designs. "Always
                        shown" was the whole truth for as long as nothing in
                        the app could hide a closure; #1047 built the Alerts
                        switch below, and a row still promising "always" over a
                        map a hiker has just cleared would be the panel
                        disagreeing with the screen.

                        So where the switch is on the panel, the tag names it -
                        the word is the switch's own visible label, which is
                        what makes it findable from here - and the row greys
                        out with it. Where no switch is offered, nothing on
                        that panel can take these marks off the map and the
                        original promise is exactly right.

                        WHAT THE MAP IS DOING IS ASKED FIRST, and deliberately.
                        A panel handed `alertsShown={false}` with no handler -
                        a shell that draws no alerts and offers no way back -
                        must not tag a greyed row "Always shown". The screen
                        wins over the affordance in every branch here. */}
                    <span className="legend__always">
                      {!alertsShown
                        ? 'Alerts off'
                        : onToggleAlerts === undefined
                          ? 'Always shown'
                          : 'Alerts'}
                    </span>
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
          lists every hideable category, which the grid above now does too (#723)
          - so this is no longer the only way to reach a category with nothing in
          the viewport, and is back to being what it says it is: one tap for
          "this one and nothing else", against eight taps of the rows. */}
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

      {/* THE ALERTS SWITCH (#1047), the first control this app has ever put
          over a safety layer.

          Here rather than in the grid above, and that is the decision. The
          rows are one waypoint CATEGORY each and are toggled through the
          stored `waypoint_types_shown` preference; alerts are neither - they
          are three map layers (closure bands, the ATC's bands and dots,
          serious-warning pins) governed by a flag nothing writes down. Putting
          them in the grid would have meant either a fourth thing the stored
          filter can express, which is the one shape #1047 rules out, or a row
          that looks identical to its neighbours and behaves unlike all of
          them. It sits with the drought wash instead, which is the honest
          neighbour: a map overlay, switched here because the moment you want
          it off is the moment you are looking at it.

          The row states what the switch does NOT take away, in both states
          rather than only while it is off - the moment that matters is
          BEFORE the tap, when a hiker is deciding what it will cost them.
          chrome/alertLayerPanel.ts is what makes the sentence true, and
          chrome/StatusStrip.tsx is what says so on the map itself once the
          legend is shut. */}
      {onToggleAlerts !== undefined && (
        <label className="legend__alerts">
          <span className="legend__alerts-name">
            Alerts
            <span className="legend__alerts-detail">
              {alertsShown
                ? 'Closures and warnings, drawn on the map. What is ahead of you is called out at the top either way.'
                : 'Hidden until you open the app again. What is ahead of you is still called out at the top.'}
            </span>
          </span>
          <input
            type="checkbox"
            name="alert_layer"
            checked={alertsShown}
            onChange={onToggleAlerts}
          />
        </label>
      )}

      {/* The drought wash (#720). Rendered whenever the shell can write the
          preference back, INCLUDING in a week with no drought on the trail -
          a hiker who switched it on should see it stay on and say "none this
          week" rather than find the control has vanished, which would read
          as the app losing their setting. */}
      {onToggleDrought !== undefined && (
        <label className="legend__drought">
          <span className="legend__drought-name">
            Drought
            {droughtSummary !== undefined && (
              <span className="legend__drought-detail">
                {/* THE WEEK IS WHAT SAYS SOMEBODY LOOKED, so it decides this
                    sentence rather than decorating it (#286's distinction,
                    which this row got wrong first time round). With no week
                    there is no artifact - the bucket 404ed, or the app has
                    not reached it yet - and "none on the trail" would be a
                    reassurance nobody has earned. The pipeline publishes an
                    EMPTY band set precisely so that a genuinely dry-free week
                    can say so, and that case still has a week. */}
                {droughtSummary.weekStart === null
                  ? 'not available'
                  : `${
                      droughtSummary.miles > 0
                        ? `${formatDistance(droughtSummary.miles, units, 'whole')} affected`
                        : 'none on the trail'
                    } · week of ${droughtSummary.weekStart.toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      timeZone: 'UTC',
                    })}`}
              </span>
            )}
          </span>
          <input
            type="checkbox"
            name="drought_layer"
            checked={droughtShown}
            onChange={onToggleDrought}
          />
        </label>
      )}

      {/* The way to every ATC notice (#687), moved here from a permanent
          button across the top of the map screen - it used to render
          whenever the app held any notice at all, which given ATC almost
          always has something live was almost always, so a hiker paid map
          height for it on every visit rather than the times it actually had
          news. What is genuinely new gets its own bottom banner on the map
          screen instead; this is the quiet, permanent way to browse
          everything ATC has posted, trail-content-adjacent so it sits above
          the downloaded-map block below rather than inside it - those answer
          a different question and #687 is explicit that conflating them is
          what this replaces. */}
      {atcNoticeCount > 0 && onOpenAtcNotices !== undefined && (
        <button type="button" className="legend__atc-link" onClick={onOpenAtcNotices}>
          {atcNoticeCount === 1
            ? 'Read the 1 ATC trail update'
            : `Read all ${atcNoticeCount} ATC trail updates`}
        </button>
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
      {/* Who looks after the ground under the hiker (#598).
          features/CORRIDOR_VIEW.md leaves open whether a club section should
          be tappable above the seam; this is the cheap half of the answer -
          the polygon stops at the seam and the SENTENCE does not, because
          "who maintains where I am standing" is a good question at any zoom
          and a thirty-run recolouring over a map somebody is navigating by is
          clutter competing with pins that matter more.

          Here rather than in the status strip because this panel is already
          where the app puts its provenance, it costs no map ink, and a hiker
          opens it deliberately. If it reads as clutter it is deleted without
          touching a layer; if it earns its place it can graduate. */}
      {maintainerLine !== null && <p className="legend__maintainer">{maintainerLine}</p>}

      {(hasPicker || onOpenDownloads !== undefined) && (
        <div className="legend__downloads">
          {backgroundChoice !== undefined && onChangeBackground !== undefined && (
            <BackgroundPicker
              value={backgroundChoice}
              onChange={onChangeBackground}
              override={backgroundOverride}
              belowArchiveZoom={belowArchiveZoom}
              offlineBackgroundAvailable={offlineBackgroundAvailable}
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
