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

import { StatusStrip } from './StatusStrip'
import { Header, type HikeDirection } from './Header'
import { TabBar } from './TabBar'
import type { TabId } from './tabs'
import { Legend, type BlazeCount } from './Legend'
import { useDesktop } from '../lib/useDesktop'
import { Search } from './Search'
import { ElevationRibbon, type ElevationRibbonProps } from './ElevationRibbon'
import { WaypointLanes, type WaypointLanesProps } from './WaypointLanes'
import { PoiSheet, type PoiDetail } from './PoiSheet'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MapView } from '../map/MapView'
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
  // All three are omitted until they are actually known - see HeaderProps.
  state?: string
  mile?: number
  direction?: HikeDirection

  time: Date
  online: boolean
  hasGpsFix: boolean
  lastSyncedAt: Date | null

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
  /** A pin was tapped, by POI id. Stable across renders - see MapViewProps. */
  onSelectPoi: (id: string) => void
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
}

export function MapScreen({
  topoArchiveUrl,
  trailsUrl,
  background = 'hiking_topo_live',
  trailName,
  state,
  mile,
  direction,
  time,
  online,
  hasGpsFix,
  lastSyncedAt,
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
}: MapScreenProps) {
  // The one thing the stylesheet cannot do. The legend announces itself as
  // `role="dialog" aria-modal="true"` and renders nothing when closed; as a
  // permanent panel it is neither. No media query can change what a component
  // tells a screen reader it is.
  const isDesktop = useDesktop()

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
        />

        <Header
          trailName={trailName}
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
              onViewportChange={onViewportChange}
              onMapReady={onMapReady}
            />
            <p className="map-screen__attribution">{attributionFor(background)}</p>

            {/* Inside the canvas, so on a desktop it stays over the map
                rather than over the legend panel beside it - and on a phone it
                lands in the lower third, which WIREFRAMES.md §1 reserves for
                everything touched mid-walk. */}
            {selectedPoi !== null && <PoiSheet poi={selectedPoi} onClose={onClosePoi} />}

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
          />
        </div>
      </div>

      <TabBar active={activeTab} onSelect={onSelectTab} />
    </div>
  )
}
