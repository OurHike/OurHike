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

import { useCallback, useState, type ReactNode } from 'react'
import { StatusStrip } from './StatusStrip'
import { Header } from './Header'
import { TabBar } from './TabBar'
import type { TabId } from './tabs'
import { Legend, type BlazeCount } from './Legend'
import { useDesktop } from '../lib/useDesktop'
import { Search } from './Search'
import { ElevationRibbon, type ElevationRibbonProps } from './ElevationRibbon'
import { WaypointLanes, type WaypointLanesProps } from './WaypointLanes'
import { PoiCard, type PoiDetail } from './PoiCard'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MapView } from '../map/MapView'
import type { ClosureBand } from '../map/closureLayers'
import type { AtcUpdatePoint } from '../map/atcUpdateLayers'
import type { WarningPoint } from '../map/warningLayers'
import type { SourceReport } from '../map/liveSourceHealth'
import type { BackgroundProblem } from '../lib/backgroundHealth'
import type { BackgroundOverride } from '../lib/dataSaver'
import type { DownloadActivity } from '../lib/downloadActivity'
import type { ArchiveZooms } from '../lib/archiveCoverage'
import { mapCredits } from '../map/credits'
import { MapAttribution } from './MapAttribution'
import type { ScaleUnits } from '../map/mapChrome'
import type { ResolvedTheme } from '../lib/theme'
import type {
  BackgroundSource,
  LayerDetailLevel,
  MapStyle,
  Theme,
} from '../lib/userPreferences'
import type { BoundingBox, MapPoint } from '../lib/legendContents'
import type { SearchablePoi } from '../lib/searchPoi'
import './chrome.css'

export interface MapScreenProps {
  topoArchiveUrl: string
  trailsUrl: string
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
  /** The ATC's own notices, drawn at the same weight as a closure and read
   *  from the same geometry path (features/ATC_TRAIL_UPDATES.md, #461). */
  atcUpdates?: readonly ClosureBand[]
  /** The single-mile notices, drawn as dots rather than bands. */
  atcUpdatePoints?: readonly AtcUpdatePoint[]
  /** An ATC band was tapped, by band id. */
  onSelectAtcUpdate?: (bandId: string) => void
  /** The tapped update's sheet, or null. Rendered by the shell for the same
   *  reason `selectedPoi` is: the map draws bands, and the app is what knows
   *  whose notice a band belongs to. */
  atcUpdateSheet?: ReactNode
  /**
   * How many ATC notices the app is holding, for the button that opens all of
   * them. Zero, or the shell not passing it, renders no button.
   *
   * A COUNT RATHER THAN THE NOTICES. This component does not need to read one,
   * and handing it the array would make it the second place that knows how an
   * ATC update is rendered - which is how the banner and the sheet would come
   * to disagree. The list itself arrives as `atcNoticeList` below, already
   * built, exactly as `atcUpdateSheet` does.
   */
  atcNoticeCount?: number
  /** Opens that list. */
  onOpenAtcNotices?: () => void
  /** The full list of ATC notices, or null when it is closed. */
  atcNoticeList?: ReactNode
  warnings?: readonly WarningPoint[]

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
  blazeCounts: BlazeCount[]
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

  /**
   * The tapped pin's detail, or null when nothing is selected.
   *
   * The shell resolves the id the map reports into this, because the map draws
   * pins and the app is what knows a POI's name, its mile and where it came
   * from.
   */
  selectedPoi: PoiDetail | null
  /** A pin was tapped, by POI id - null for a tap on bare map, which is how
   *  the card is dismissed. Stable across renders - see MapViewProps. */
  onSelectPoi: (id: string | null) => void
  onClosePoi: () => void

  // Both are optional and both are omitted rather than stubbed when their data
  // isn't there. An empty ribbon or a bare set of lanes would read as "nothing
  // ahead of you," which is a different and much worse claim than "we don't
  // have the profile for this stretch."
  elevation?: ElevationRibbonProps
  waypoints?: WaypointLanesProps

  showZoomButtons?: boolean
  units?: ScaleUnits
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
  onViewportChange?: (bbox: BoundingBox) => void
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
}

export function MapScreen({
  topoArchiveUrl,
  trailsUrl,
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
  atcUpdates,
  atcUpdatePoints,
  onSelectAtcUpdate,
  atcUpdateSheet,
  atcNoticeCount = 0,
  onOpenAtcNotices,
  atcNoticeList,
  warnings,
  activeTab,
  onSelectTab,
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
  blazeCounts,
  hiddenTypes,
  onToggleType,
  onOnlyType,
  onShowAllTypes,
  typesShown,
  verifiedOnly,
  onToggleVerifiedOnly,
  selectedPoi,
  onSelectPoi,
  onClosePoi,
  elevation,
  waypoints,
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
  onOpenDownloads,
  hasDownload = false,
  downloadActivity = null,
  hasRasterArchive = false,
  backgroundProblem = null,
  onLiveSourceHealth,
  belowArchiveZoom = false,
  trailLinesMissing = false,
  archiveZooms = null,
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
  const handleMapReady = useCallback(
    (map: MapLibreMap | null) => {
      setLiveMap(map)
      onMapReady?.(map)
    },
    [onMapReady],
  )

  return (
    <div className="map-screen">
      {/* Everything that is not the navigation. On a phone this is a plain
          column and changes nothing; on a desktop the tab bar becomes a
          sidebar beside it (src/desktop.css). */}
      <div className="map-screen__main">
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
        />

        {/* Between the status strip and the header, and that placement is the
            decision rather than a layout accident (#232).

            Above the map because a hiker who is walking has not opened
            anything - a closure that only appears on tapping a red band is a
            closure they walk into. Below the sync age because these two are
            read together: the age is what says whether this line is current,
            and an empty space here means "clear" only as far as that age.

            role="alert" for the same reason More.tsx's stuck reports use it -
            this is not ambient status, it is a thing that changes what
            someone does next. */}
        {(closureAhead !== null || advisoryAhead !== null || warningsAhead !== null) && (
          <div className="map-screen__alerts" role="alert">
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
            {/* Last, and quieter than both, because it is the only one of the
                three that is not about the next few miles (#485). A hiker inside
                ATC's Helene advisory is inside it for 398 miles; whatever is
                three miles ahead has to be read first. Still inside the same
                alert region rather than demoted to the status strip - that strip
                is narrow flags about connectivity, GPS and data age, and a
                warning about the trail is not app status. */}
            {advisoryAhead !== null && (
              <p className="map-screen__alert map-screen__alert--advisory">
                {advisoryAhead}
              </p>
            )}
          </div>
        )}

        {/* The way to everything the ATC said, and deliberately OUTSIDE the
            alert region above rather than a fourth row inside it.

            Two reasons, and both are about what `role="alert"` means. It is a
            live region: a screen reader announces its contents when they
            change, which is right for three lines that appear because
            something is ahead and wrong for a control that is simply always
            there - every change to a sibling row would re-announce it. And it
            is reserved for what changes what a hiker does NEXT; this button
            changes nothing, it only opens something.

            Rendered whenever the app holds any notices, including when no
            banner line is showing at all. That is the case it exists for: an
            update behind the hiker, or one that obstructs nothing, produces no
            banner and no map mark, and before this had no surface whatsoever
            (chrome/AtcNoticeList.tsx opens with the full accounting). */}
        {atcNoticeCount > 0 && onOpenAtcNotices !== undefined && (
          <div className="map-screen__notices">
            <button
              type="button"
              className="map-screen__notices-button"
              onClick={onOpenAtcNotices}
            >
              {atcNoticeCount === 1
                ? 'Read the 1 ATC trail update'
                : `Read all ${atcNoticeCount} ATC trail updates`}
            </button>
          </div>
        )}

        <Header
          trailName={trailName}
          trailLogo={trailLogo}
          state={state}
          position={position}
          onOpenLegend={onOpenLegend}
          onOpenSearch={onOpenSearch}
        />

        {elevation && <ElevationRibbon {...elevation} />}
        {waypoints && <WaypointLanes {...waypoints} />}

        {/* The map and the legend. Separated from the chrome above so the two
            can sit side by side on a desktop, where the legend is a panel
            rather than a sheet over the map. Deliberately NOT the positioned
            .map-screen__canvas: the phone legend is absolute against the
            viewport, and reparenting it under a positioned ancestor would move
            it - the one thing WEBSITE.md §8 rules out. */}
        <div className="map-screen__body">
          <div className="map-screen__canvas">
            <MapView
              topoArchiveUrl={topoArchiveUrl}
              trailsUrl={trailsUrl}
              background={background}
              pois={viewportPoints}
              hiddenTypes={hiddenTypes}
              verifiedOnly={verifiedOnly}
              closures={closures}
              atcUpdates={atcUpdates}
              atcUpdatePoints={atcUpdatePoints}
              onSelectAtcUpdate={onSelectAtcUpdate}
              warnings={warnings}
              onSelectPoi={onSelectPoi}
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
              onViewportChange={onViewportChange}
              onMapReady={handleMapReady}
              onLiveSourceHealth={onLiveSourceHealth}
            />
            {/* Inline above the desktop breakpoint, where the whole list fits
                on one line - the same `isDesktop` the legend uses, so the two
                cannot disagree about how much room this layout has. */}
            <MapAttribution
              credits={mapCredits({ background, hasRasterArchive })}
              inline={isDesktop}
            />

            {/* Inside the canvas, and not one wrapper further out: the card
                positions itself in canvas pixels (poiCardPlacement.ts), so it
                must be absolute against exactly the box the canvas fills or
                every placement would be off by the chrome above the map. */}
            {selectedPoi !== null && (
              <PoiCard poi={selectedPoi} map={liveMap} onClose={onClosePoi} />
            )}

            {/* Beside the card rather than placed like one. The waypoint card
                positions itself in canvas pixels because it points at a pin;
                this is about a stretch of trail, so it sits where the search
                sheet does and needs none of that. */}
            {atcUpdateSheet}

            {/* Beside the single-notice sheet, in the same slot and for the
                same reason - a list about the whole trail anchors to nothing
                on the canvas. Both can be open at once and the list is
                rendered second, so it lands on top; that is the right way
                round, since the list is what a hiker just asked for. */}
            {atcNoticeList}

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
            blazeCounts={blazeCounts}
            hiddenTypes={hiddenTypes}
            onToggleType={onToggleType}
            onOnlyType={onOnlyType}
            onShowAllTypes={onShowAllTypes}
            typesShown={typesShown}
            verifiedOnly={verifiedOnly}
            onToggleVerifiedOnly={onToggleVerifiedOnly}
            onClose={onCloseLegend}
            backgroundChoice={backgroundChoice}
            onChangeBackground={onChangeBackground}
            backgroundOverride={backgroundOverride}
            belowArchiveZoom={belowArchiveZoom}
            onOpenDownloads={onOpenDownloads}
            hasDownload={hasDownload}
            downloadActivity={downloadActivity}
          />
        </div>
      </div>

      <TabBar active={activeTab} onSelect={onSelectTab} />
    </div>
  )
}
