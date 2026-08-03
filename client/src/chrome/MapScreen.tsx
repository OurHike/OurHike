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
import { Search } from './Search'
import { ElevationRibbon, type ElevationRibbonProps } from './ElevationRibbon'
import { WaypointLanes, type WaypointLanesProps } from './WaypointLanes'
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
  return (
    <div className="map-screen">
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

      <div className="map-screen__canvas">
        <MapView
          topoArchiveUrl={topoArchiveUrl}
          trailsUrl={trailsUrl}
          background={background}
          pois={viewportPoints}
          hiddenTypes={hiddenTypes}
          showZoomButtons={showZoomButtons}
          units={units}
          center={center}
          zoom={zoom}
          bounds={bounds}
          onViewportChange={onViewportChange}
          onMapReady={onMapReady}
        />
        <p className="map-screen__attribution">{attributionFor(background)}</p>

        <Search
          open={searchOpen}
          pois={searchablePois}
          onSelect={onSelectSearchResult}
          onClose={onCloseSearch}
        />
      </div>

      <Legend
        open={legendOpen}
        bbox={bbox}
        points={viewportPoints}
        blazeCounts={blazeCounts}
        hiddenTypes={hiddenTypes}
        onToggleType={onToggleType}
        onClose={onCloseLegend}
      />

      <TabBar active={activeTab} onSelect={onSelectTab} />
    </div>
  )
}
