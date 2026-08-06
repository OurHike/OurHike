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
import { HEALTHY, type LiveSourceHealth } from '../map/liveSourceHealth'
import type { BackgroundOverride } from '../lib/dataSaver'
import type { ArchiveZooms } from '../lib/archiveCoverage'
import { attributionFor } from '../map/style'
import type { ScaleUnits } from '../map/mapChrome'
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

  // Held here rather than lifted to the shell: nothing above this screen acts
  // on it, and the strip that reports it is three lines up. `setState` is
  // stable across renders, so handing it straight to MapView satisfies that
  // prop's stability contract without a useCallback.
  const [liveSources, setLiveSources] = useState<LiveSourceHealth>(HEALTHY)

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
          // The basemap alone. A DEM outage costs relief and contour lines on
          // a sheet that still draws, which is the degradation terrain.ts
          // promises rather than something to interrupt a hiker over.
          liveBackgroundUnavailable={liveSources.basemap}
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
              onSelectPoi={onSelectPoi}
              showZoomButtons={showZoomButtons}
              units={units}
              center={center}
              zoom={zoom}
              bounds={bounds}
              archiveZooms={archiveZooms}
              onViewportChange={onViewportChange}
              onMapReady={handleMapReady}
              onLiveSourceHealth={setLiveSources}
            />
            <p className="map-screen__attribution">{attributionFor(background)}</p>

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
