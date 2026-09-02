// The map screen shell (WIREFRAMES.md §1), stacking the pieces top to bottom.
//
// Still to slot in: the elevation ribbon and the three waypoint lanes (D8), and
// the legend bottom sheet (D7). They are left out rather than stubbed, so the
// gap stays visible instead of hiding behind an empty placeholder.
//
// Attribution is rendered here rather than by MapLibre's own control, because
// WIREFRAMES.md positions it bottom-left beneath the scale bar. USGS topo is
// public domain; OpenStreetMap is ODbL and its credit is a licence condition,
// so this element is not optional and is not behind a prop.
//
// What it names is map/credits.ts's decision and how it is laid out is
// MapAttribution's; this screen only supplies the two facts neither of them
// can see - which background is drawn, and whether the raster archive it may
// be drawn over is actually on the phone.

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentProps,
  type ReactNode,
} from 'react'
import { StatusStrip } from './StatusStrip'
import { Header } from './Header'
import { TabBar } from './TabBar'
import type { TabId } from './tabs'
import { Legend } from './Legend'
import { useDesktop } from '../lib/useDesktop'
import { Search } from './Search'
import { ElevationRibbon, type RibbonControl } from './ElevationRibbon'
import type { RibbonView } from '../lib/ribbonView'
import { ElevationChart, type ChartStretch } from './ElevationChart'
import type { ChartDomain } from '../lib/chartProfile'
import type { PaceProfile } from '../lib/pace'
import type { ElevationProfile } from '../lib/elevationProfile'
import {
  attachChartFocus,
  type ChartFocusHandle,
  type StretchRuns,
} from '../map/chartFocusLayers'
import { NextUpRail } from './NextUpRail'
import type { Waypoint } from '../lib/ribbonView'
import type { StalenessTreatment } from '../lib/stalenessDisplay'
import type { HikeDirection } from './Header'
import { PoiCard, type PoiDetail } from './PoiCard'
import type { FieldNoteContext } from './FieldNoteSection'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MapView } from '../map/MapView'
import type { DroughtBand } from '../map/droughtLayers'
import type { ClosureBand } from '../map/closureLayers'
import type { CorridorFeatureCollection } from '../map/corridorLayers'
import type { WorkdayPoint } from '../map/workdayLayers'
import type { DisputePoint } from '../map/disputeLayers'
import type { AtcUpdatePoint } from '../map/atcUpdateLayers'
import type { TappedLine } from '../map/lineTaps'
import type { RouteDrawing } from '../map/routeLayers'
import type { DayHikeDrawing } from '../map/dayHikeLayers'
import type { WarningPoint } from '../map/warningLayers'
import type { SourceReport } from '../map/liveSourceHealth'
import type { BackgroundProblem } from '../lib/backgroundHealth'
import type { BackgroundOverride } from '../lib/dataSaver'
import { downloadFillPercent, type DownloadActivity } from '../lib/downloadActivity'
import { formatBytes, formatBytesLive } from '../lib/formatBytes'
import type { ArchiveZooms } from '../lib/archiveCoverage'
import { mapCredits } from '../map/credits'
import { MapAttribution } from './MapAttribution'

/** Room the camera leaves around a stretch the chart asked it to frame.
 *  Wider than MapView's opening FIT_PADDING (24): the chart has already
 *  padded the MILES by 8% each side, and these are the pixels that keep the
 *  band's ends off the very frame edge. */
const CHART_FIT_PADDING = 48
import type { ResolvedTheme } from '../lib/theme'
import type {
  BackgroundSource,
  LayerDetailLevel,
  MapStyle,
  Theme,
  UnitSystem,
} from '../lib/userPreferences'
import {
  computeLegendContents,
  legendDropSummary,
  type BoundingBox,
  type MapPoint,
} from '../lib/legendContents'
import type { SearchablePoi } from '../lib/searchPoi'
import { TrailDataUpdate, type TrailDataUpdateProps } from './TrailDataUpdate'
import './chrome.css'

export interface MapScreenProps {
  /**
   * The Today journal, docked beside the map as the desktop's planning
   * station (#1054). A slot rather than this screen knowing Today's props:
   * the shell owns both screens and passes the very element the phone's
   * Today tab renders, so the two layouts cannot drift apart. Passed ONLY
   * above the breakpoint and only while the Today tab is active - on a phone
   * this is always undefined and nothing here changes, which is WEBSITE.md
   * §8's constraint made structural.
   */
  journal?: ReactNode
  /** The sidebar's "today I'm…" control, handed through to the TabBar this
   *  screen renders - see TabBarProps.modeSwitch for the contract. */
  modeSwitch?: ReactNode
  topoArchiveUrl: string
  trailsUrl: string
  /** The corridor-view centerline, while there is no real one to draw (#869).
   *  Passed straight through - which line the map is drawing is decided in
   *  lib/useTrailData.ts, and a screen that second-guessed it could put both
   *  on at once. */
  overviewTrailsUrl?: string | null
  /** The trails other organizations maintain (#950), forwarded to MapView -
   *  see its own prop for what null means and why it is the usual answer. */
  nearbyTrailsUrl?: string | null
  /** The network's corridor-view sketch, forwarded to the canvas (#1135). */
  networkOverviewUrl?: string | null
  /** Which background the map draws; also decides what the corner has to
   *  credit, since the live sheet brings two more licences with it. */
  background?: BackgroundSource

  trailName: string
  trailLogo?: string
  // All three are omitted until they are actually known - see HeaderProps.
  state?: string
  /** The position line, already decided by the shell (lib/positionLine.ts) -
   *  see HeaderProps for why this is a sentence rather than a number. */
  position: string
  /** Whether location is switched on, which decides whether the map offers
   *  its locate control at all (map/mapChrome.ts, #312). */
  locationEnabled?: boolean

  time: Date
  online: boolean
  hasGpsFix: boolean
  lastSyncedAt: Date | null
  /** Passed straight to StatusStrip; see its prop for what it means. */
  conditionsAge?: string | null

  /**
   * The closure a hiker is about to walk into, already rendered to one line
   * (lib/closureBanner.ts), or null when the way ahead is clear.
   *
   * Null also covers "we could not check" — the shell cannot tell those apart
   * from here and must not pretend to. What separates them is the status
   * strip's sync age directly above, which is why this sits under it rather
   * than anywhere else on the screen.
   */
  closureAhead?: string | null
  /**
   * The broad advisory the hiker is inside or heading toward, already rendered
   * to one line, or null.
   *
   * Its own prop rather than folded into `closureAhead` because the two are
   * different kinds of statement and #485 is what happens when they share a line:
   * a region-sized advisory scores "inside" and buries the specific closure three
   * miles ahead for as long as the hiker is in it. This one is a standing
   * condition — it does not change for hundreds of miles — so it is drawn under
   * the actionable line and quieter than it.
   */
  advisoryAhead?: string | null
  /** "N serious warnings on your route", or null (lib/seriousWarnings.ts). */
  warningsAhead?: string | null

  /**
   * The same two facts on the canvas: closed stretches as bands along the
   * trail, serious warnings as pins. Passed straight through to MapView.
   *
   * Deliberately NOT derived from the two banners above, which is why they are
   * four props rather than two. A banner says what is AHEAD of a hiker walking
   * a known direction; the canvas draws what is THERE, in both directions and
   * before the app knows which way anyone is going. Tying them together would
   * mean a map that draws no closure until the direction tracker has made up
   * its mind.
   */
  closures?: readonly ClosureBand[]
  /** Which staleness ring each waypoint wears (#759's nudge surface, #256's
   *  consumer). Passed straight through to MapView; the policy lives in
   *  lib/stalenessDisplay.ts's `pinConditionFor`. */
  pinCondition?: (poiId: string, poiType: string) => { ring: string; faded: boolean }
  /** The card's conditions section, passed straight through to PoiCard -
   *  the shell is what holds the notes and the write path. */
  noteContext?: FieldNoteContext
  /** The corridor view's attribution, already in map coordinates (#598).
   *  Coordinates rather than mile ranges for the reason `closures` gives. */
  corridor?: CorridorFeatureCollection
  /** Who maintains the trail in front of the hiker, as a sentence, for the
   *  legend (#598). Null above nothing in particular - see Legend's own prop. */
  maintainerLine?: string | null
  /** Told which highlight mark a tap landed on, or null for a miss (#858). */
  onSelectHighlight?: (id: string | null) => void
  /** The ATC's own notices, drawn at the same weight as a closure and read
   *  from the same geometry path (features/ATC_TRAIL_UPDATES.md, #461). */
  atcUpdates?: readonly ClosureBand[]
  /** The single-mile notices, drawn as dots rather than bands. */
  atcUpdatePoints?: readonly AtcUpdatePoint[]
  /** Volunteer workdays as map points (#760), already windowed and already
   *  checked against the feed's staleness ceiling by the shell. */
  workdays?: readonly WorkdayPoint[]
  /** Which workday a tap landed on. */
  onSelectWorkday?: (projectId: string) => void
  /** Places the field says are not there (#876), joined to coordinates. */
  disputes?: readonly DisputePoint[]
  /** The tapped workday's sheet, or null - the atcUpdateSheet pattern: the
   *  map answers which pin, the shell decides what to show. */
  workdaySheet?: ReactNode
  /** An ATC band was tapped, by band id. */
  onSelectAtcUpdate?: (bandId: string) => void
  /** The tapped update's sheet, or null. Rendered by the shell for the same
   *  reason `selectedPoi` is: the map draws bands, and the app is what knows
   *  whose notice a band belongs to. */
  atcUpdateSheet?: ReactNode
  /** A trail line was tapped, as its published facts - null for a tap that
   *  landed elsewhere, which is how the sheet dismisses (#134). Stable
   *  across renders, like `onSelectPoi`. */
  onSelectLine?: (line: TappedLine | null) => void
  /** The tapped line's sheet, or null - the atcUpdateSheet pattern: the map
   *  draws lines, and the shell is what knows a line's spur record and the
   *  name of the shelter it leads to. */
  lineSheet?: ReactNode
  /**
   * The route being built, in map coordinates, and the builder's own card -
   * both on the atcUpdateSheet pattern: the map draws a line, the shell is
   * what knows it is a route (#755). While `onRouteTap` is set the canvas is
   * in route-building mode and a tap drops a point instead of selecting a
   * POI - see MapViewProps.onRouteTap for the exclusivity.
   */
  routeDrawing?: RouteDrawing | null
  dayHikeDrawing?: DayHikeDrawing | null
  /** Passed straight through to the map - see MapViewProps for both. */
  dayHikeTicks?: ComponentProps<typeof MapView>['dayHikeTicks']
  mapLabels?: ComponentProps<typeof MapView>['mapLabels']
  onRouteTap?: (at: { lon: number; lat: number }, point: { x: number; y: number }) => void
  /** A drawn line, in the day-hike builder's draw mode (#983). Replaces the
   *  tap handler while set - see MapViewProps.onRouteStroke. */
  onRouteStroke?: (stroke: Array<{ lon: number; lat: number }>) => void
  /** Press and hold on bare map (#1137) - see MapViewProps.onLongPress. */
  onLongPress?: (
    at: { lon: number; lat: number },
    point: { x: number; y: number },
  ) => void
  /** True while the press plate is up - see MapViewProps.pressPlateOpen
   *  for what it suppresses and why. */
  pressPlateOpen?: boolean
  routeSheet?: ReactNode
  /**
   * The day-hike builder's panel (#1194) - the left rail on a desktop, the
   * collapsible top panel on a phone.
   *
   * IN THE FLOW, NOT OVER THE MAP, which is the whole of the fix it carries.
   * Every other slot on this screen is an overlay, and that is what made the
   * builder's map too small: `.day-hike-bar` covers up to 60% of the canvas.
   * This one is a SIBLING of `.map-screen__canvas`, so it takes its room
   * rather than borrowing the map's - a row on a desktop (desktop.css already
   * turns `.map-screen__body` into one) and a band above the map on a phone.
   *
   * A slot for the same reason `routeSheet` is: what a day hike knows is the
   * shell's, and a map screen that learned about them would be the fourth
   * feature to move into it (#937).
   */
  builderPanel?: ReactNode
  /** The press-and-hold plate (#1137). A slot for the same reason as the
   *  sheets above - but unlike them it DOES anchor to a point on the
   *  canvas, so it positions itself and this screen only gives it the
   *  layer to sit in. */
  pressPlate?: ReactNode
  /**
   * The band a followed day hike puts directly UNDER the header (#1041,
   * frame `D11`) - today only "you are not on your route".
   *
   * A slot rather than a prop this screen understands, like `routeSheet` and
   * the sheets below it: what a followed hike knows is the shell's, and a map
   * screen that learned about day hikes would be the fourth feature to move
   * into it (#937).
   *
   * Under the header, not in `.map-screen__alerts` above it, and
   * chrome/OffRouteCard.tsx holds the reasoning: that strip is the trail's
   * condition ahead, true for everyone on that ground, and this is one
   * hiker's own route.
   */
  followBand?: ReactNode
  /**
   * One sentence about the followed walk, for the polite line below - not for
   * the eye, which reads {@link followBand}.
   *
   * A STRING RATHER THAN A NODE, and that is the whole point (#1055). The
   * band is a node this screen renders without reading; an announcement has
   * to be something this screen can put INSIDE its one live region, because
   * the alternative is the band carrying its own live role and re-announcing
   * a distance on every fix. Keep it free of numbers: the value here should
   * change when the hiker crosses a threshold, never when a fix wobbles.
   */
  followAnnouncement?: string | null
  /**
   * How many trail notices the app is holding, from every organization, for
   * the Legend row that opens all of them (#687 - it used to be a permanent
   * button on this screen; see `newNoticeCount` below for what replaced it
   * here). Zero, or the shell not passing it, renders no row.
   *
   * A COUNT RATHER THAN THE NOTICES. This component does not need to read one,
   * and handing it the array would make it the second place that knows how a
   * notice is rendered - which is how the banner and the sheet would come to
   * disagree. The list itself arrives as `noticeList` below, already built,
   * exactly as `atcUpdateSheet` does.
   */
  noticeCount?: number
  /** Opens that list - from the Legend row and from the bottom banner below,
   *  both of which are simply "a hiker asked to see it". */
  onOpenNotices?: () => void
  /** The full list of notices, or null when it is closed. */
  noticeList?: ReactNode
  /**
   * How many notices this screen is holding that their publisher touched in
   * the last 72 hours and the hiker has not already silenced (lib/notices.ts,
   * #687). Zero, or the shell not passing it, renders no banner.
   *
   * Deliberately not derived from `noticeCount` above - that is every notice
   * the app holds, drawn or not, and this is the much narrower "something
   * changed recently" question the bottom banner exists to answer. The two can
   * and usually do disagree: most visits hold several notices and none of them
   * new.
   *
   * ONE BANNER ACROSS ORGANIZATIONS (#1083). features/ORG_NOTICES.md §5 calls
   * the banner "a scarce surface rather than a record"; a second one is a
   * third of the chrome the wrong-way alert competes with. So the count merges
   * and every row survives in the list.
   */
  newNoticeCount?: number
  /**
   * What that banner says, built by the shell.
   *
   * A STRING RATHER THAN A COUNT AND A LIST OF ORGANIZATIONS, because naming
   * an organization means resolving its `source_key` through the published
   * registry, and features/ORG_NOTICES.md §6 puts that everywhere except a
   * component: "a string in a component is how the app ends up telling a hiker
   * that NYNJTC's closure is ATC's word." This screen renders the sentence and
   * does not compose it.
   */
  newNoticeLabel?: string
  /** Silences the bottom banner without opening the list - the quick "not
   *  now" beside `onOpenNotices`'s "show me". Omitted, no silence control
   *  is drawn. */
  onSilenceNewNotices?: () => void
  /**
   * The published trail data this phone does not have, and the two answers to
   * it (#919). Undefined renders nothing, which is the state on every launch
   * where the map is current - see chrome/TrailDataUpdate.tsx.
   */
  trailDataUpdate?: TrailDataUpdateProps
  warnings?: readonly WarningPoint[]

  /**
   * Whether the alert marks are drawn at all (#1047).
   *
   * One flag over `closures`, `atcUpdates`, `atcUpdatePoints` and `warnings` -
   * chrome/alertLayerPanel.ts has why those four are one control and why the
   * flag it comes from is never stored.
   *
   * IT WITHHOLDS AT ONE PLACE, the `<MapView>` call site, and that is the
   * property worth keeping rather than a detail of where the ternaries went.
   * Two other things read it and neither takes anything away: the status strip
   * SAYS the marks are off, and the legend DISPLAYS the switch's own state.
   * `closureAhead`, `advisoryAhead` and `warningsAhead` arrive here as
   * finished sentences on their own props, so this flag has no route to them
   * at all: a hiker who takes the bands off the canvas is still told what is
   * in front of them, and that stays true by construction rather than by
   * anyone remembering it.
   *
   * Defaults to drawn. A MapScreen rendered without a shell to hold the flag
   * shows every alert it was given, which is the only default a safety layer
   * may have.
   */
  alertsShown?: boolean
  /** Flips it. Omitted, the legend draws no alert control - a switch that
   *  goes nowhere is worse than no switch. */
  onToggleAlerts?: () => void

  activeTab: TabId
  onSelectTab: (id: TabId) => void
  onOpenLegend: () => void
  onOpenSearch: () => void

  legendOpen: boolean
  onCloseLegend: () => void

  // Search takes over the header rather than sitting beside it
  // (WIREFRAMES.md Interactions), so the shell owns whether it is showing.
  searchOpen: boolean
  onCloseSearch: () => void
  searchablePois: SearchablePoi[]
  onSelectSearchResult: (poi: SearchablePoi) => void
  bbox: BoundingBox
  /**
   * Every POI the app holds. Named for the legend, which is what first needed
   * it, but it is the map's pin data too - both are handed this one array so a
   * legend row can never name something the map is not drawing, which is
   * exactly what it used to do.
   */
  viewportPoints: MapPoint[]
  /** Passed straight through to the Legend (#783) - MapScreen decides nothing
   *  about it. */
  ghostedTrailsDrawn?: boolean
  hiddenTypes: Set<string>
  onToggleType: (type: string) => void
  /** One tap to show a single category, and the way back from it (#530). Passed
   *  to the legend, where the rows are. */
  onOnlyType?: (type: string) => void
  onShowAllTypes?: () => void
  /** The stored preference itself, so the panel can say what is filtered - the
   *  price of the filter persisting across a pan. */
  typesShown?: readonly string[]
  /** The legend's "Verified?" filter. Handed to the legend and to the map from
   *  here, so the counts in the panel and the pins on the canvas are one
   *  decision rather than two that can drift. */
  verifiedOnly: boolean
  onToggleVerifiedOnly: () => void
  /** The drought wash and its switch (#720), passed straight through to
   *  the legend and the map - this screen makes no decision about it. */
  drought?: readonly DroughtBand[]
  droughtShown?: boolean
  onToggleDrought?: () => void
  droughtWeek?: { start: Date; end: Date } | null

  /**
   * The tapped pin's detail, or null when nothing is selected.
   *
   * The shell resolves the id the map reports into this, because the map draws
   * pins and the app is what knows a POI's name, its mile and where it came
   * from.
   */
  selectedPoi: PoiDetail | null
  /**
   * The card for a waypoint that no longer exists (#831), when the selected id
   * is one this project has retired.
   *
   * A rendered element rather than a tombstone, deliberately, and it is the
   * same call `atcUpdateSheet` and `lineSheet` above already make: what the
   * card has to say includes where the pointer LEADS — the successor's name,
   * and a way to open it — and only the shell holds the live waypoints to
   * resolve that against. Passing the raw tombstone here would put a second
   * lookup in the map screen, against data it does not have.
   *
   * Mutually exclusive with `selectedPoi` by construction: an id is a live
   * waypoint or a retired one, never both — verify_release's check 21 fails a
   * release where any id is published as each.
   */
  removedPoiCard?: ReactNode
  /**
   * Every part of that waypoint's site, anchor first, for the card's chip strip
   * (#526) - resolved by the shell for the same reason `selectedPoi` is.
   *
   * Optional, because a screen with no site data behaves exactly as it did
   * before sites existed; this screen adds nothing to it and only hands it on.
   */
  selectedSite?: readonly PoiDetail[]
  /** A pin was tapped, by POI id - null for a tap on bare map, which is how
   *  the card is dismissed. Stable across renders - see MapViewProps. */
  onSelectPoi: (id: string | null) => void
  onClosePoi: () => void

  // Both are optional and both are omitted rather than stubbed when their data
  // isn't there. An empty ribbon or a bare set of lanes would read as "nothing
  // ahead of you," which is a different and much worse claim than "we don't
  // have the profile for this stretch."
  //
  // The shell decides WHICH ribbon this is (#910) - the route being planned,
  // the map's own viewport, the ten miles around the GPS fix, or the whole
  // trail - and lib/ribbonView.ts holds that precedence. What arrives here is
  // the winner, already drawn-out, carrying its `source` and its `domain` so
  // this screen can offer the right framing buttons and no others. The one
  // thing that must hold is that `waypoints` came from the SAME domain (#913),
  // because a hiker reads a pin as sitting under the part of the profile it
  // belongs to; lib/ribbonView.ts builds both halves off one decision for
  // exactly that reason, and refuses the lanes outright where they would
  // stand for more trail than a place.
  elevation?: RibbonView
  /** Put the map back on the hiker, clearing the shell's "they took the map"
   *  latch. Undefined without a fix to go back to, which is what hides the
   *  button rather than offering one that would do nothing. */
  onRibbonBackToMe?: () => void
  /**
   * The desktop's full elevation chart (#135), swapped in for the ribbon
   * above the breakpoint. Separate from `elevation` because the two answer
   * different questions with different requirements: the ribbon needs a GPS
   * fix and shows the ten miles around it; the chart needs only the
   * published profile - a desk has no fix - and rests on the whole trail.
   *
   * The two converters cross the chart's profile-axis miles onto the map.
   * They live in the shell, which holds the centerline index and the POI
   * anchors, and arrive here as functions for the same reason `selectedPoi`
   * arrives resolved: this screen draws, the shell knows.
   */
  chart?: {
    profile: ElevationProfile
    currentMile: number | null
    mileToCoordinate: (mile: number) => [number, number] | null
    stretchToRuns: (startMile: number, endMile: number) => StretchRuns
    /**
     * The settled selection, owned by the shell (PR #885 review): while the
     * route builder is open it IS the route's stretch, so a stop entered
     * there selects here and a drag here re-stretches the route. The band
     * on the map follows this value - not the chart's callbacks - so a
     * selection the PLAN changed lands on the canvas too.
     */
    selection?: ChartStretch | null
    southbound?: boolean
    selectionFromPlan?: boolean
    onSelectStretch?: (stretch: ChartStretch | null) => void
    onToggleSouthbound?: () => void
    onPlanStretch?: () => void
    /** Where "Whole trail" sends the camera - the shell's own opening frame,
     *  so the button and a fresh open agree about what the whole trail is. */
    wholeTrailBounds?: [[number, number], [number, number]]
    /** The hiker's own pace, so the chart's ≈time and the route builder's
     *  legs price the same selection the same way (#886). */
    pace?: PaceProfile
  }
  /**
   * `onSelectPoi` omitted deliberately, the way `units` is left off the ribbon
   * above: this screen already holds the handler a pin tap goes through, so it
   * supplies that one rather than letting the shell pass a second. A rail card
   * and a map pin opening different cards is the disagreement one prop
   * prevents. The shape is lib/ribbonView.ts's RibbonLanes plus the staleness
   * lookup - the same window the ribbon settled on (#913), walked as cards
   * instead of plotted as lanes since #1054.
   */
  waypoints?: {
    points: Waypoint[]
    startMile: number
    endMile: number
    stalenessFor?: (
      poiId: string,
      poiType: string,
    ) => { treatment: StalenessTreatment; words: string } | null
  }
  /**
   * The settled walking direction, or undefined while the tracker has not
   * committed - which is exactly when the rail's heading must not say
   * "NEXT UP" (chrome/NextUpRail.tsx). The position line already embeds it
   * as text; the rail needs it as data.
   */
  direction?: HikeDirection
  /**
   * The hiker's own mile on the centerline, or undefined where there is not
   * one (#953).
   *
   * The waypoint card is the only thing that reads it, and it is a number here
   * rather than a string for the reason #953 names: what crossed this boundary
   * before was `positionLine`'s finished sentence, so by the time a card
   * existed the figure had already been spent. Undefined covers every state
   * that module has its own wording for - and the card's answer to all of them
   * is the same silence, so they arrive here as one absence rather than six.
   */
  hikerMile?: number

  showZoomButtons?: boolean
  /**
   * Feet or metres, for everything on this screen (lib/units.ts).
   *
   * Typed as the PREFERENCE rather than as map/mapChrome.ts's `ScaleUnits`,
   * which is the same two strings under a name that stopped being true: this
   * prop drives the scale bar, the contour interval, the summit labels' source
   * field AND the elevation ribbon's three labels. One value down one road, so
   * the canvas and the chrome over it cannot disagree.
   */
  units?: UnitSystem
  /** Which theme the canvas is drawn in. Passed down rather than read here so
   *  the chrome and the map answer from one value - see MapViewProps. */
  theme?: ResolvedTheme
  /** The stored theme preference behind `theme`, the sheet's palette family,
   *  night_hike's red-light sub-mode, and the detail level - passed straight
   *  through to MapView like `theme`, and for the same reason. */
  themeChoice?: Theme
  mapStyle?: MapStyle
  redLight?: boolean
  detail?: LayerDetailLevel

  /** Opening camera only; later moves are the hiker's. */
  center?: [number, number]
  /** Opening zoom, paired with `center`. */
  zoom?: number
  /** Opening view as `[[west, south], [east, north]]`; wins over `center`. */
  bounds?: [[number, number], [number, number]]
  onViewportChange?: (bbox: BoundingBox, fromGesture: boolean) => void
  onMapReady?: (map: MapLibreMap | null) => void
  /** Why the drawn background is not the one in settings, if it isn't - see
   *  lib/dataSaver.ts. Passed down rather than computed here, so the decision
   *  keeps the single home that module's docstring insists on. */
  backgroundOverride?: BackgroundOverride | null
  /**
   * The stored background preference and how to change it, for the picker in
   * the legend.
   *
   * Distinct from `background` above, which is what is actually DRAWN after
   * Data Saver and the download state have had their say. The control has to
   * show and write the choice, not the outcome - a picker that snapped back
   * to "downloaded" because Data Saver was on would be unusable.
   */
  backgroundChoice?: BackgroundSource
  onChangeBackground?: (next: BackgroundSource) => void
  /**
   * Whether "downloaded only" is a background this phone can get at all.
   *
   * The USGS sheet was withdrawn for v2 (#855) and that option draws its
   * archive and nothing else, so on a phone that did not already take it
   * there is one background and no choice to offer. Carried from the shell
   * for the same reason `backgroundOverride` is: what is on the phone is the
   * shell's knowledge, and the legend's picker must not go and re-derive it.
   */
  offlineBackgroundAvailable?: boolean
  /**
   * Opens the download window, which the legend's picker links to.
   *
   * The window itself is the shell's, not this screen's: it opens over the
   * More tab as readily as over the map, and a copy owned here would be a
   * second one with its own idea of whether it is showing.
   */
  onOpenDownloads?: () => void
  /** Whether a finished archive is on the phone, which words that link. */
  hasDownload?: boolean
  /** What is downloading right now, if anything - drawn on that same link, so
   *  a transfer started from the window and left running is visible from the
   *  map without opening the window again (lib/downloadActivity.ts). */
  downloadActivity?: DownloadActivity | null
  /**
   * Whether the corridor RASTER archive specifically is finished and on this
   * phone, which decides whether the corner credits USGS at all.
   *
   * Narrower than `hasDownload` above, and it has to be: that one is true when
   * any sheet has landed, and the hiking sheet downloading without the USGS
   * raster has been a normal phone since #237. Credit follows the tiles that
   * are actually drawing, not the fact that some download happened.
   */
  hasRasterArchive?: boolean
  /** Whether the other organizations' trail lines are drawn (#950) - it is
   *  what puts OPRHP's required attribution in the corner. */
  hasNearbyTrails?: boolean
  /**
   * Why the background is not on screen, or null when it is
   * (lib/backgroundHealth.ts).
   *
   * Decided by the shell rather than here, and it moved there rather than
   * staying local for a concrete reason (#334): the same failing source has
   * to reach the Downloads window, which opens over the More tab where this
   * screen is not rendered at all. A screen that owned the fact could not
   * hand it to a window that outlives it. `onLiveSourceHealth` below is the
   * other half of that move - the observations go up, the conclusion comes
   * back down.
   */
  backgroundProblem?: BackgroundProblem | null
  /** Where the map's source observations go. Passed straight to MapView, and
   *  stable across renders like every other handler here. */
  onLiveSourceHealth?: (report: SourceReport) => void
  /**
   * Whether the view is zoomed out past what the download covers (#216).
   *
   * Reported by the shell rather than worked out here, for the same reason
   * `backgroundOverride` is: the strip and the legend's picker both say it,
   * and two independent readings of one condition is how they come to
   * disagree.
   */
  belowArchiveZoom?: boolean
  /** How many waypoints of each `type::confidence` the map actually drew, and
   *  whether the camera is below the zoom pins are drawn at (#528). Passed
   *  straight to the legend, which is where both are said. */
  drawnCounts?: ReadonlyMap<string, number>
  belowPoiZoom?: boolean
  /**
   * Whether the map is drawing no trail line at all - see StatusStrip, which
   * is the only thing that reads it.
   *
   * Decided by the shell, like `backgroundProblem` and for the same reason:
   * whether the phone holds trail lines is a fact about IndexedDB and a fetch
   * that may have failed, neither of which this screen can see. It arrives as
   * a settled boolean rather than as the data, so the strip cannot come to a
   * different conclusion than the download window's own notice.
   */
  trailLinesMissing?: boolean
  /** What the archive's own header says it covers, for the opening camera. */
  archiveZooms?: ArchiveZooms | null
  /** Room to leave around the opening box, per side - see MapViewProps. The
   *  shell sets a bottom inset during first run so the trail is framed against
   *  the strip above the entry card rather than against the whole canvas. */
  boundsPadding?: number | { top: number; bottom: number; left: number; right: number }
  /**
   * First run: this screen is the backdrop to the onboarding steps, and is
   * showing its canvas and nothing else (#721).
   *
   * ONE BOOLEAN RATHER THAN A SECOND MAP. `App.tsx` used to render its own
   * `<MapView>` behind the steps and then hand over to this screen's, which
   * meant the first run built two maps and threw the first away at the exact
   * moment onboarding ended - measured at two WebGL contexts and 1,230 ms of
   * blocking work across 7 long tasks, on a phone that had just finished the
   * launch fetch. React reconciles by position, so the only way to keep one
   * map across that transition is for the map to stay where it is and the
   * chrome to change around it. This is that.
   *
   * What it does NOT do is put the map screen behind the steps. The chrome is
   * hidden AND the whole subtree is `inert`, because `App.tsx`'s original
   * reasoning holds: chrome behind a modal "is either a trap or a way to skip
   * the flow sideways". Hiding is structural rather than a list of names - see
   * chrome.css's `.map-screen--entering` block - so a control added to this
   * screen later is hidden here by default rather than appearing behind the
   * steps because nobody remembered this flag.
   *
   * The attribution is the deliberate exception and stays drawn: the live
   * sheet's OSM data is ODbL and its credit is a licence condition, so a map
   * that is drawn has to be credited whether or not anyone may touch it.
   */
  entering?: boolean
}

export function MapScreen({
  topoArchiveUrl,
  trailsUrl,
  overviewTrailsUrl = null,
  nearbyTrailsUrl = null,
  networkOverviewUrl = null,
  background = 'hiking_topo_live',
  trailName,
  trailLogo,
  state,
  time,
  online,
  hasGpsFix,
  lastSyncedAt,
  conditionsAge = null,
  closureAhead = null,
  advisoryAhead = null,
  warningsAhead = null,
  closures,
  pinCondition,
  noteContext,
  corridor,
  maintainerLine,
  onSelectHighlight,
  atcUpdates,
  atcUpdatePoints,
  onSelectAtcUpdate,
  workdays,
  onSelectWorkday,
  workdaySheet,
  disputes,
  atcUpdateSheet,
  onSelectLine,
  lineSheet,
  routeDrawing = null,
  dayHikeDrawing = null,
  dayHikeTicks,
  mapLabels,
  onRouteTap,
  onRouteStroke,
  onLongPress,
  pressPlateOpen,
  routeSheet,
  builderPanel,
  pressPlate,
  followBand,
  followAnnouncement = null,
  noticeCount = 0,
  onOpenNotices,
  noticeList,
  newNoticeCount = 0,
  newNoticeLabel,
  onSilenceNewNotices,
  trailDataUpdate,
  warnings,
  alertsShown = true,
  onToggleAlerts,
  activeTab,
  onSelectTab,
  journal,
  modeSwitch,
  onOpenLegend,
  onOpenSearch,
  legendOpen,
  onCloseLegend,
  searchOpen,
  onCloseSearch,
  searchablePois,
  onSelectSearchResult,
  bbox,
  viewportPoints,
  ghostedTrailsDrawn,
  hiddenTypes,
  onToggleType,
  onOnlyType,
  onShowAllTypes,
  typesShown,
  verifiedOnly,
  onToggleVerifiedOnly,
  drought,
  droughtShown = false,
  onToggleDrought,
  droughtWeek = null,
  selectedPoi,
  removedPoiCard,
  selectedSite,
  onSelectPoi,
  onClosePoi,
  elevation,
  onRibbonBackToMe,
  chart,
  waypoints,
  direction,
  hikerMile,
  position,
  locationEnabled = false,
  showZoomButtons = false,
  units = 'imperial',
  theme = 'light',
  themeChoice = 'auto',
  mapStyle = 'field',
  redLight = false,
  detail = 'standard',
  center,
  zoom,
  bounds,
  onViewportChange,
  onMapReady,
  backgroundOverride = null,
  backgroundChoice,
  onChangeBackground,
  offlineBackgroundAvailable = true,
  onOpenDownloads,
  hasDownload = false,
  downloadActivity = null,
  hasRasterArchive = false,
  hasNearbyTrails = false,
  backgroundProblem = null,
  onLiveSourceHealth,
  belowArchiveZoom = false,
  drawnCounts,
  belowPoiZoom = false,
  trailLinesMissing = false,
  archiveZooms = null,
  boundsPadding,
  entering = false,
}: MapScreenProps) {
  // The one thing the stylesheet cannot do. The legend announces itself as
  // `role="dialog" aria-modal="true"` and renders nothing when closed; as a
  // permanent panel it is neither. No media query can change what a component
  // tells a screen reader it is.
  const isDesktop = useDesktop()

  // The live map, kept here as well as reported upward, because the waypoint
  // card anchors to a pin by projecting its coordinates through the map - and
  // the shell above owns the POI data, not the canvas. Tee'd rather than
  // intercepted: the owner's `onMapReady` still sees every hand-over.
  const [liveMap, setLiveMap] = useState<MapLibreMap | null>(null)

  // This screen's own root element, for the share sheet's portal: the sheet
  // must land inside the subtree App.tsx hides and inerts when another
  // screen covers the held map (#1081), and the root is the highest box
  // that is - see PoiShareSheet.tsx's header. State rather than a plain
  // ref so the card re-renders with the element once it exists.
  const [screenRoot, setScreenRoot] = useState<HTMLDivElement | null>(null)
  const handleMapReady = useCallback(
    (map: MapLibreMap | null) => {
      setLiveMap(map)
      onMapReady?.(map)
    },
    [onMapReady],
  )

  // The chart's focus overlay on the live map - the hovered mile as a dot,
  // the selected stretch as a band. A REF rather than state, deliberately:
  // hover updates arrive per pointer move, and a setState here would re-render
  // this whole screen (map included) at pointer rate. The handle writes
  // straight into the map's own source instead, and React never hears about
  // it. Attached only while the desktop chart is actually rendered, and
  // keyed on the chart's PRESENCE rather than its identity - the prop is
  // rebuilt when a fix moves, and tearing the overlay down per GPS tick
  // would flicker it for nothing.
  const chartFocusRef = useRef<ChartFocusHandle | null>(null)
  const hasChart = chart !== undefined
  useEffect(() => {
    if (liveMap === null || !isDesktop || !hasChart) return
    const handle = attachChartFocus(liveMap)
    chartFocusRef.current = handle
    return () => {
      chartFocusRef.current = null
      handle.detach()
    }
  }, [liveMap, isDesktop, hasChart])

  // The latest chart config, for the effect and callbacks below - a ref
  // rather than a dependency, because the shell rebuilds the object on every
  // GPS tick and neither the band nor the camera should be re-written for a
  // fix that moved. Assigned in its own effect so it is fresh before the
  // selection effect (declared after) reads it.
  const chartRef = useRef(chart)
  useEffect(() => {
    chartRef.current = chart
  })

  // The band follows the CONTROLLED selection value, not the chart's
  // callbacks (PR #885 review): while the route builder owns the selection,
  // a stop entered there changes it with no chart gesture at all, and the
  // canvas has to follow that change too. `hasChart`/`liveMap`/`isDesktop`
  // re-run this after the overlay re-attaches, so a fresh handle starts
  // with the current stretch rather than empty.
  const chartSelection = chart?.selection ?? null
  useEffect(() => {
    const handle = chartFocusRef.current
    const c = chartRef.current
    if (handle === null || c === undefined) return
    // An uncontrolled chart's band is written by handleChartStretch below.
    if (c.selection === undefined) return
    handle.setStretch(
      chartSelection === null
        ? null
        : c.stretchToRuns(chartSelection.startMile, chartSelection.endMile),
    )
  }, [liveMap, isDesktop, hasChart, chartSelection])

  const handleChartHover = useCallback(
    (mile: number | null) => {
      const handle = chartFocusRef.current
      if (handle === null || chart === undefined) return
      handle.setPoint(mile === null ? null : chart.mileToCoordinate(mile))
    },
    [chart],
  )

  const handleChartStretch = useCallback((stretch: ChartStretch | null) => {
    const c = chartRef.current
    if (c === undefined) return
    if (c.selection === undefined) {
      // Uncontrolled: the chart's own claim is the band.
      const handle = chartFocusRef.current
      handle?.setStretch(
        stretch === null ? null : c.stretchToRuns(stretch.startMile, stretch.endMile),
      )
      return
    }
    // Controlled: the shell decides what the gesture means - a measurement
    // moved, or a route re-stretched - and the band follows its answer
    // through the effect above.
    c.onSelectStretch?.(stretch)
  }, [])

  // "Zoom to stretch" and "Whole trail" move the camera with the chart (PR
  // #885 review). The stretch is framed from its own centerline runs - the
  // geometry the band draws - so the camera frames the ground, not a
  // straight line between two mileposts.
  const handleChartZoom = useCallback(
    (domain: ChartDomain | null) => {
      const c = chartRef.current
      if (liveMap === null || c === undefined) return
      if (domain === null) {
        if (c.wholeTrailBounds !== undefined) {
          liveMap.fitBounds(c.wholeTrailBounds, { padding: CHART_FIT_PADDING })
        }
        return
      }
      const runs = c.stretchToRuns(domain.startMile, domain.endMile)
      let west = Infinity
      let south = Infinity
      let east = -Infinity
      let north = -Infinity
      for (const run of runs) {
        for (const [lon, lat] of run) {
          if (lon < west) west = lon
          if (lon > east) east = lon
          if (lat < south) south = lat
          if (lat > north) north = lat
        }
      }
      // No geometry to frame (a pre-#753 download has no anchors): the
      // chart still zooms, the camera stays.
      if (west > east) return
      liveMap.fitBounds(
        [
          [west, south],
          [east, north],
        ],
        { padding: CHART_FIT_PADDING },
      )
    },
    [liveMap],
  )

  /**
   * The ribbon's framing buttons (#910 review) - the desktop chart's own, on
   * the phone, driving the same `handleChartZoom` so the two surfaces frame
   * ground identically.
   *
   * Which ones exist depends on what the ribbon is showing, and a button that
   * would do nothing is not offered rather than offered and inert:
   *
   *   Zoom to stretch  Frames what the ribbon draws. Pointless when the ribbon
   *                    IS the viewport ('map-view') or the whole trail, which
   *                    is what "Whole trail" already does.
   *   Whole trail      Frames the corridor. Pointless when that is already the
   *                    domain.
   *   Back to me       Only after the hiker has taken the map, and only when
   *                    there is a fix to go back to - the shell decides the
   *                    second half by withholding the callback.
   *
   * Framing the map is a programmatic move, so it carries no `originalEvent`
   * and does not re-arm the shell's "they took the map" latch: tapping "Zoom
   * to stretch" on the fix window moves the map to the hiker's ten miles and
   * leaves the ribbon exactly where it was, which is the sync the review
   * asked for rather than a fight between the two.
   */
  const ribbonControls = useMemo<RibbonControl[]>(() => {
    if (elevation === undefined) return []
    const source = elevation.source
    const controls: RibbonControl[] = []
    if (source === 'planned-stretch' || source === 'ahead') {
      controls.push({
        label: 'Zoom to stretch',
        onClick: () => handleChartZoom(elevation.domain),
      })
    }
    if (source !== 'whole-trail') {
      controls.push({ label: 'Whole trail', onClick: () => handleChartZoom(null) })
    }
    if (source === 'map-view' && onRibbonBackToMe !== undefined) {
      controls.push({ label: 'Back to me', onClick: onRibbonBackToMe })
    }
    return controls
  }, [elevation, handleChartZoom, onRibbonBackToMe])

  // The same rows the legend builds, from the same arguments, so the canvas count
  // and the panel can never disagree - one arithmetic, two places it is said
  // (#528). `verifiedOnly` and `hiddenTypes` are passed for exactly that reason:
  // with either filter on, the legend counts fewer points, and a canvas figure
  // computed without them would contradict the panel it is standing next to.
  //
  // And `drawnCounts` is withheld below the seam for the same reason the
  // legend withholds it (#1135): with both waypoint ranks floored there,
  // "drawn" measures the floor rather than the collision engine, and this
  // chip read "0 of 387 waypoints fit" over the opening view - the floor
  // described as crowding, on the canvas itself. Withheld, the summary is
  // null and the chip does not render; the legend's below-seam sentence is
  // where the absence is explained.
  const droppedSummary = legendDropSummary(
    computeLegendContents(
      bbox,
      viewportPoints,
      verifiedOnly,
      belowPoiZoom ? undefined : drawnCounts,
    ),
    hiddenTypes,
  )

  // THE FOUR ALERT COLLECTIONS, AND THE ONLY PLACE #1047'S FLAG TAKES ANYTHING
  // AWAY. (Two places below read it to describe what is happening - the status
  // strip's "Alerts hidden" and the legend's own switch - and neither of those
  // can withhold a mark.)
  //
  // Kept together here rather than as four ternaries down in the JSX, so that
  // "what the Alerts switch withholds" is a list somebody can check against
  // the map's own layer modules in one glance - and so that a fifth alert
  // layer added later is a line in this block rather than a prop somewhere in
  // a hundred-line element that nobody notices is ungated.
  //
  // `undefined` rather than a `[]` written here: MapView keeps a stable empty
  // for each of these (NO_CLOSURES and friends) precisely so a fresh array per
  // render cannot re-push a source every frame, and handing the prop away uses
  // those rather than making a second set that behaves the same until it does
  // not.
  //
  // WITHHOLDING THE DATA RATHER THAN HIDING THE LAYERS is the decision. An
  // emptied source cannot be hit by `queryRenderedFeatures`, so a tap where a
  // band used to be opens nothing at all - where a layer set to `visibility:
  // none` would still answer taps and put a closure sheet over a map drawing
  // no closure.
  //
  // Nothing in this block can reach `closureAhead`, `advisoryAhead` or
  // `warningsAhead`: those arrive as finished sentences on their own props and
  // are rendered above the map untouched. That is the guarantee the whole
  // control rests on, and it is structural here rather than a rule anybody has
  // to keep.
  const drawnClosures = alertsShown ? closures : undefined
  const drawnAtcUpdates = alertsShown ? atcUpdates : undefined
  const drawnAtcUpdatePoints = alertsShown ? atcUpdatePoints : undefined
  const drawnWarnings = alertsShown ? warnings : undefined

  return (
    // `inert` is what makes hiding the chrome safe rather than cosmetic: it
    // takes the whole subtree out of the tab order and the accessibility tree,
    // so a keyboard or screen-reader user during first run is in the steps and
    // only the steps. It also covers the map's own locate control, a tap on
    // which would put the OS location prompt on screen ahead of the step whose
    // entire job is to explain why we are asking.
    <div
      ref={setScreenRoot}
      className={entering ? 'map-screen map-screen--entering' : 'map-screen'}
      inert={entering || undefined}
      // Paired with `inert` rather than standing in for it. `inert` is what
      // makes the subtree unreachable; this is what stops a screen reader
      // announcing a map region that a hiker cannot get to and is not being
      // asked about. Safe together precisely because of `inert` - aria-hidden
      // over focusable content would otherwise be the classic trap.
      aria-hidden={entering || undefined}
    >
      {/* The desktop's journal column (#1054): the Today screen the shell
          hands over, reading beside the map instead of over it. Before
          __main in the row, so it sits between the sidebar and the map -
          src/desktop.css sizes and re-inks it. Never rendered on a phone,
          because the shell never passes it there. */}
      {journal !== undefined && <div className="map-screen__journal">{journal}</div>}

      {/* Everything that is not the navigation. On a phone this is a plain
          column and changes nothing; on a desktop the tab bar becomes a
          sidebar beside it (src/desktop.css). */}
      <div className="map-screen__main">
        {/* One line, polite, and stable across jitter.

            `aria-live="polite"` rather than `role="status"`, which is the
            convention this screen already keeps and the notices banner's own
            test spells out: StatusStrip.tsx owns `role="status"` here, and a
            second region claiming it makes "the status region" ambiguous to a
            screen reader and to a role query alike. Polite rather than
            assertive because this is announced once when something appears,
            and queueing behind whatever is being read is the right trade for
            somebody who is walking rather than reading. (#315 is why the
            visible cards below carry no live role: their text ends in a
            distance App.tsx recomputes per fix, and a live region there
            re-announced on every tick of the tenths.) */}
        <p className="visually-hidden" aria-live="polite">
          {[
            closureAhead !== null ? 'Trail closure ahead.' : '',
            warningsAhead !== null ? 'Serious warning ahead.' : '',
            advisoryAhead !== null ? 'An advisory covers where you are.' : '',
            // The hiker's OWN route, last, because the three above are the
            // ground itself and true for everyone on it (#1055). One region
            // rather than a second one beside it, for the reason the comment
            // above gives about `role="status"`: two live regions on one
            // screen is two things that can interrupt each other.
            followAnnouncement ?? '',
          ]
            .filter((sentence) => sentence !== '')
            .join(' ')}
        </p>

        {followBand}

        {/* The map and the legend. Separated from the chrome above so the two
            can sit side by side on a desktop, where the legend is a panel
            rather than a sheet over the map. Deliberately NOT the positioned
            .map-screen__canvas: the phone legend is absolute against the
            viewport, and reparenting it under a positioned ancestor would move
            it - the one thing WEBSITE.md §8 rules out. */}
        <div className="map-screen__body">
          {/* Before the canvas so it is the rail on the left of a desktop and
              the band above the map on a phone, and so a keyboard reaches the
              route being built before the map it is being built on. */}
          {builderPanel}
          <div className="map-screen__canvas">
            {/* The floating chrome (#1054): the identity plate and whatever
                stacks under it, in one column so a taller plate pushes the
                alerts down rather than overlapping them. Inside the canvas
                so the .map-screen--entering rules hide all of it during
                first run without a list of names (chrome.css). */}
            <div className="map-screen__float">
              <Header
                trailName={trailName}
                trailLogo={trailLogo}
                state={state}
                position={position}
                onOpenLegend={onOpenLegend}
                onOpenSearch={onOpenSearch}
                strip={
                  <StatusStrip
                    time={time}
                    online={online}
                    hasGpsFix={hasGpsFix}
                    lastSyncedAt={lastSyncedAt}
                    conditionsAge={conditionsAge}
                    backgroundProblem={backgroundProblem}
                    backgroundOverride={backgroundOverride}
                    belowArchiveZoom={belowArchiveZoom}
                    trailLinesMissing={trailLinesMissing}
                    alertsHidden={!alertsShown}
                  />
                }
              />

              {/* Under the plate, and that placement is still #232's
                  decision in the new shape: above the map because a hiker
                  who is walking has not opened anything - a closure that
                  only appears on tapping a red band is a closure they walk
                  into - and directly under the strip's sync age, because the
                  two are read together: the age is what says whether this
                  line is current. No live role on the visible cards (#315);
                  the visually-hidden line above announces once per event. */}
              {(closureAhead !== null ||
                advisoryAhead !== null ||
                warningsAhead !== null) && (
                <div className="map-screen__alerts">
                  {closureAhead !== null && (
                    <p className="map-screen__alert map-screen__alert--closure">
                      {closureAhead}
                    </p>
                  )}
                  {warningsAhead !== null && (
                    <p className="map-screen__alert map-screen__alert--warning">
                      {warningsAhead}
                    </p>
                  )}
                  {/* Last, and quieter than both, because it is the only one
                      of the three that is not about the next few miles
                      (#485). */}
                  {advisoryAhead !== null && (
                    <p className="map-screen__alert map-screen__alert--advisory">
                      {advisoryAhead}
                    </p>
                  )}
                </div>
              )}

              {/* The hour a download spends arriving, admitted where its
                  thinner map is felt (#1103). Below the alerts on purpose:
                  those are the ground itself, this is housekeeping. A
                  button because the window is where the detail lives - the
                  per-asset list this card deliberately does not carry. No
                  live role, like the visible alert cards above (#315): the
                  figures change too often to announce. Absent the moment
                  nothing is arriving, which is the DownloadsLink's rule and
                  most of the year. */}
              {downloadActivity !== null && (
                <button
                  type="button"
                  className="map-screen__download-note"
                  onClick={onOpenDownloads}
                >
                  <span className="map-screen__download-title">Map still arriving</span>
                  {downloadActivity.kind === 'preparing' ? (
                    // The canary step: four fetches of unannounced size, so
                    // the honest figure is no figure (lib/downloadActivity.ts).
                    <span className="map-screen__download-figures">
                      Getting trail data first
                    </span>
                  ) : (
                    <>
                      <span className="map-screen__download-bar">
                        <span
                          className="map-screen__download-fill"
                          style={{
                            width: `${downloadFillPercent(
                              downloadActivity.doneBytes,
                              downloadActivity.totalBytes,
                            )}%`,
                          }}
                        ></span>
                      </span>
                      {/* The same words and figures the window's card prints
                          (DownloadCard.tsx), so the two surfaces can never
                          disagree about one transfer. */}
                      <span className="map-screen__download-figures">
                        {`${downloadActivity.kind === 'downloading' ? 'Downloading' : 'Checking'} · ${formatBytesLive(
                          downloadActivity.doneBytes,
                        )} of ${formatBytes(downloadActivity.totalBytes)}`}
                      </span>
                      <span className="map-screen__download-line">
                        Drawing live tiles meanwhile — some detail is missing until this
                        lands.
                      </span>
                    </>
                  )}
                </button>
              )}
            </div>

            <MapView
              topoArchiveUrl={topoArchiveUrl}
              trailsUrl={trailsUrl}
              overviewTrailsUrl={overviewTrailsUrl}
              nearbyTrailsUrl={nearbyTrailsUrl}
              networkOverviewUrl={networkOverviewUrl}
              background={background}
              pois={viewportPoints}
              pinCondition={pinCondition}
              hiddenTypes={hiddenTypes}
              verifiedOnly={verifiedOnly}
              drought={drought}
              showDrought={droughtShown}
              closures={drawnClosures}
              corridor={corridor}
              onSelectHighlight={onSelectHighlight}
              atcUpdates={drawnAtcUpdates}
              atcUpdatePoints={drawnAtcUpdatePoints}
              onSelectAtcUpdate={onSelectAtcUpdate}
              workdays={workdays}
              onSelectWorkday={onSelectWorkday}
              disputes={disputes}
              warnings={drawnWarnings}
              routeDrawing={routeDrawing}
              dayHikeDrawing={dayHikeDrawing}
              dayHikeTicks={dayHikeTicks}
              mapLabels={mapLabels}
              onRouteTap={onRouteTap}
              onRouteStroke={onRouteStroke}
              onLongPress={onLongPress}
              pressPlateOpen={pressPlateOpen}
              onSelectPoi={onSelectPoi}
              onSelectLine={onSelectLine}
              showZoomButtons={showZoomButtons}
              units={units}
              locationEnabled={locationEnabled}
              theme={theme}
              themeChoice={themeChoice}
              mapStyle={mapStyle}
              redLight={redLight}
              detail={detail}
              center={center}
              zoom={zoom}
              bounds={bounds}
              archiveZooms={archiveZooms}
              boundsPadding={boundsPadding}
              onViewportChange={onViewportChange}
              onMapReady={handleMapReady}
              onLiveSourceHealth={onLiveSourceHealth}
            />
            {/* On the canvas, so "is there anything here I am not being shown"
                is answerable without opening the legend (#528).

                Deliberately NOT in the status strip. That is a row of narrow
                flags about connectivity, GPS and data age - things that are
                either true or not - and a number that changes on every pinch
                does not belong beside them. It sits over the map instead,
                where the thing it is about is. */}
            {droppedSummary !== null && (
              <p className="map-screen__dropped" aria-live="polite">
                {droppedSummary.drawn} of {droppedSummary.present} waypoints fit
              </p>
            )}

            {/* Inline above the desktop breakpoint, where the whole list fits
                on one line - the same `isDesktop` the legend uses, so the two
                cannot disagree about how much room this layout has.

                ON A PHONE THE CREDIT LIVES IN THE RAIL below since #1054 -
                except during first run, when the rail is hidden with the rest
                of the chrome and this canvas copy is what keeps a drawn map
                credited (the .map-screen--entering rules exempt
                .map-attribution by name for exactly this - chrome.css). One
                instance renders at a time. */}
            {(isDesktop || entering) && (
              <MapAttribution
                credits={mapCredits({ background, hasRasterArchive, hasNearbyTrails })}
                inline={isDesktop}
              />
            )}

            {/* Inside the canvas, and not one wrapper further out: the card
                positions itself in canvas pixels (poiCardPlacement.ts), so it
                must be absolute against exactly the box the canvas fills or
                every placement would be off by the chrome above the map. */}
            {selectedPoi !== null && (
              <PoiCard
                poi={selectedPoi}
                site={selectedSite}
                map={liveMap}
                units={units}
                noteContext={noteContext}
                {...(hikerMile === undefined ? {} : { hikerMile })}
                {...(direction === undefined ? {} : { direction })}
                onClose={onClosePoi}
                sheetContainer={screenRoot}
              />
            )}

            {/* In the same slot as the card it stands in for, because it
                stands in for it: a tap that used to render nothing now
                renders this. It positions itself in the canvas rather than
                against a pin - a retired waypoint has none - so it does not
                need the canvas-pixel reasoning above, only the same box. */}
            {removedPoiCard}

            {/* Beside the card rather than placed like one. The waypoint card
                positions itself in canvas pixels because it points at a pin;
                this is about a stretch of trail, so it sits where the search
                sheet does and needs none of that. */}
            {atcUpdateSheet}
            {workdaySheet}

            {/* The line-detail sheet (#134), in the same slot family for the
                same reason: a trail line anchors to no single point on the
                canvas. It cannot be open at the same time as the ATC sheet -
                a tap that hits an ATC notice reports null to the line
                handler (map/lineTaps.ts), which closes this one. */}
            {lineSheet}

            {/* Beside the single-notice sheet, in the same slot and for the
                same reason - a list about the whole trail anchors to nothing
                on the canvas. Both can be open at once and the list is
                rendered second, so it lands on top; that is the right way
                round, since the list is what a hiker just asked for. */}
            {noticeList}

            {/* The route builder's card, in the same slot family: it is about
                a route, which anchors to nothing on the canvas either. */}
            {routeSheet}

            {/* Last of the overlays, so a plate opened over an open sheet
                lands on top - the hiker pressed the map after the sheet
                was already there, and the newer intent wins. */}
            {pressPlate}

            <Search
              open={searchOpen}
              pois={searchablePois}
              onSelect={onSelectSearchResult}
              onClose={onCloseSearch}
            />
          </div>

          <Legend
            open={legendOpen}
            persistent={isDesktop}
            bbox={bbox}
            points={viewportPoints}
            ghostedTrailsDrawn={ghostedTrailsDrawn}
            hiddenTypes={hiddenTypes}
            onToggleType={onToggleType}
            onOnlyType={onOnlyType}
            onShowAllTypes={onShowAllTypes}
            typesShown={typesShown}
            verifiedOnly={verifiedOnly}
            onToggleVerifiedOnly={onToggleVerifiedOnly}
            alertsShown={alertsShown}
            onToggleAlerts={onToggleAlerts}
            droughtShown={droughtShown}
            onToggleDrought={onToggleDrought}
            units={units}
            maintainerLine={maintainerLine}
            droughtSummary={
              drought === undefined
                ? undefined
                : {
                    miles: drought.reduce((total, band) => total + band.trailMiles, 0),
                    weekStart: droughtWeek?.start ?? null,
                  }
            }
            onClose={onCloseLegend}
            backgroundChoice={backgroundChoice}
            onChangeBackground={onChangeBackground}
            backgroundOverride={backgroundOverride}
            belowArchiveZoom={belowArchiveZoom}
            offlineBackgroundAvailable={offlineBackgroundAvailable}
            drawnCounts={drawnCounts}
            belowPoiZoom={belowPoiZoom}
            onOpenDownloads={onOpenDownloads}
            hasDownload={hasDownload}
            downloadActivity={downloadActivity}
            noticeCount={noticeCount}
            onOpenNotices={onOpenNotices}
          />
        </div>

        {/* The next-up rail (#1054): the phone's band between the map and
            the tab bar, replacing the ribbon-and-lanes strip that used to
            sit ABOVE the canvas. Cards first, then the ribbon as a bordered
            card, then the attribution line - which stays on screen because
            ODbL is a licence condition, not chrome. `units` last on the
            ribbon, so the screen's answer wins, exactly as before.

            Phone only: above the breakpoint the full chart below replaces
            the ribbon, and the rail's cards would double the chart's own
            annotations. Hidden during first run by the entering rules like
            the rest of the chrome; the canvas then renders the credit
            itself (see MapAttribution above). */}
        {!isDesktop && (
          // Unconditional on a phone - with no ribbon and no cards to draw,
          // the band is the attribution line alone, because the credit may
          // not depend on whether a profile happened to download.
          <div className="next-up-band">
            {waypoints !== undefined && elevation !== undefined && (
              <NextUpRail
                points={waypoints.points}
                subject={elevation.source}
                currentMile={elevation.currentMile}
                direction={direction}
                onSelectPoi={(id) => onSelectPoi(id)}
                units={units}
                stalenessFor={waypoints.stalenessFor}
              />
            )}
            {elevation !== undefined && (
              <div className="next-up__ribbon-card">
                <ElevationRibbon
                  {...elevation}
                  subject={elevation.source}
                  units={units}
                  controls={ribbonControls}
                />
              </div>
            )}
            <MapAttribution
              credits={mapCredits({ background, hasRasterArchive, hasNearbyTrails })}
              inline={false}
            />
          </div>
        )}

        {/* The full chart, across the bottom of the frame (#135): the desk's
            answer to the ribbon, needing no fix. Rendered below the body so
            the map and the legend keep their whole height until the profile
            exists to draw. `units` last, exactly as on the ribbon above. */}
        {isDesktop && chart !== undefined && (
          <ElevationChart
            profile={chart.profile}
            currentMile={chart.currentMile}
            units={units}
            selection={chart.selection}
            southbound={chart.southbound}
            selectionFromPlan={chart.selectionFromPlan}
            onHoverMile={handleChartHover}
            onSelectStretch={handleChartStretch}
            onToggleSouthbound={chart.onToggleSouthbound}
            onPlanStretch={chart.onPlanStretch}
            onZoomDomain={handleChartZoom}
            pace={chart.pace}
          />
        )}

        {/* "Something changed" rather than "here is everything" - the row
            that used to sit under the alert strip and answer the second
            question moved into the legend above, permanently reachable and
            no longer costing every visit map height for it (#687). This one
            answers only the first, and answers it far less often: it renders
            solely while ATC has touched a live notice in the last 72 hours
            and the hiker has not already silenced it
            (lib/notices.ts).

            At the FOOT of the main column instead - `aria-live="polite"`
            rather than `role="alert"` (assertive) or `role="status"`: the
            status strip above already owns that role for connectivity and
            sync age (StatusStrip.tsx), and a second region claiming it would
            make "the status region" ambiguous to a screen reader and to
            `getByRole('status')` alike. Polite announcement is the part this
            banner actually wants - "something is new" is not "something
            changes what you do next", so it does not need `role="alert"`'s
            interrupt either. Bottom rather than a float over the canvas: a
            floating card would have to dodge the locate/compass stack and
            the credit strip sharing that corner, by hand-tuned offsets that
            drift the moment either changes size. A row in flow needs none of
            that, on a phone or the desktop sidebar layout alike. */}
        {/* Beneath the alert row rather than above it, on the one occasion
            both are up: an organization's closure changes what a hiker does
            next, and newer waypoint data does not. The order is the ranking. */}
        {trailDataUpdate !== undefined && <TrailDataUpdate {...trailDataUpdate} />}
        {newNoticeCount > 0 && onOpenNotices !== undefined && (
          <div className="map-screen__new-alerts" aria-live="polite">
            <button
              type="button"
              className="map-screen__new-alerts-button"
              onClick={onOpenNotices}
            >
              {newNoticeLabel ??
                (newNoticeCount === 1
                  ? 'New trail notice issued'
                  : `${newNoticeCount} new trail notices issued`)}
            </button>
            {onSilenceNewNotices !== undefined && (
              <button
                type="button"
                className="map-screen__new-alerts-silence"
                onClick={onSilenceNewNotices}
              >
                <span className="visually-hidden">Silence new trail notices</span>
                <span aria-hidden="true">×</span>
              </button>
            )}
          </div>
        )}
      </div>

      <TabBar active={activeTab} onSelect={onSelectTab} modeSwitch={modeSwitch} />
    </div>
  )
}
