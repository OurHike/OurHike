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

import { useCallback, useState } from 'react'
import { StatusStrip } from './StatusStrip'
import { Header, type HikeDirection } from './Header'
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
import type { WarningPoint } from '../map/warningLayers'
import type { LiveSourceHealth } from '../map/liveSourceHealth'
import type { BackgroundProblem } from '../lib/backgroundHealth'
import type { BackgroundOverride } from '../lib/dataSaver'
import type { ArchiveZooms } from '../lib/archiveCoverage'
import { mapCredits } from '../map/credits'
import { MapAttribution } from './MapAttribution'
import type { ScaleUnits } from '../map/mapChrome'
import type { ResolvedTheme } from '../lib/theme'
import type { BackgroundSource } from '../lib/userPreferences'
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
  mile?: number
  direction?: HikeDirection

  time: Date
  online: boolean
  hasGpsFix: boolean
  lastSyncedAt: Date | null

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
  onLiveSourceHealth?: (health: LiveSourceHealth, withdrawn: boolean) => void
  /**
   * Whether the view is zoomed out past what the download covers (#216).
   *
   * Reported by the shell rather than worked out here, for the same reason
   * `backgroundOverride` is: the strip and the legend's picker both say it,
   * and two independent readings of one condition is how they come to
   * disagree.
   */
  belowArchiveZoom?: boolean
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
  mile,
  direction,
  time,
  online,
  hasGpsFix,
  lastSyncedAt,
  closureAhead = null,
  warningsAhead = null,
  closures,
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
  selectedPoi,
  onSelectPoi,
  onClosePoi,
  elevation,
  waypoints,
  showZoomButtons = false,
  units = 'imperial',
  theme = 'light',
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
  hasRasterArchive = false,
  backgroundProblem = null,
  onLiveSourceHealth,
  belowArchiveZoom = false,
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
          backgroundProblem={backgroundProblem}
          backgroundOverride={backgroundOverride}
          belowArchiveZoom={belowArchiveZoom}
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
        {(closureAhead !== null || warningsAhead !== null) && (
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
          </div>
        )}

        <Header
          trailName={trailName}
          trailLogo={trailLogo}
          state={state}
          mile={mile}
          direction={direction}
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
              closures={closures}
              warnings={warnings}
              onSelectPoi={onSelectPoi}
              showZoomButtons={showZoomButtons}
              units={units}
              theme={theme}
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
            onClose={onCloseLegend}
            backgroundChoice={backgroundChoice}
            onChangeBackground={onChangeBackground}
            backgroundOverride={backgroundOverride}
            belowArchiveZoom={belowArchiveZoom}
            onOpenDownloads={onOpenDownloads}
            hasDownload={hasDownload}
          />
        </div>
      </div>

      <TabBar active={activeTab} onSelect={onSelectTab} />
    </div>
  )
}
