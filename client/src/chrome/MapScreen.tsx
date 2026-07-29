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
import { MapView } from '../map/MapView'
import { ATTRIBUTION } from '../map/style'
import type { ScaleUnits } from '../map/mapChrome'
import './chrome.css'

export interface MapScreenProps {
  topoArchiveUrl: string
  trailsUrl: string

  trailName: string
  state: string
  mile: number
  direction: HikeDirection

  time: Date
  online: boolean
  hasGpsFix: boolean
  lastSyncedAt: Date | null

  activeTab: TabId
  onSelectTab: (id: TabId) => void
  onOpenLegend: () => void
  onOpenSearch: () => void

  showZoomButtons?: boolean
  units?: ScaleUnits
}

export function MapScreen({
  topoArchiveUrl,
  trailsUrl,
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
  showZoomButtons = false,
  units = 'imperial',
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

      <div className="map-screen__canvas">
        <MapView
          topoArchiveUrl={topoArchiveUrl}
          trailsUrl={trailsUrl}
          showZoomButtons={showZoomButtons}
          units={units}
        />
        <p className="map-screen__attribution">{ATTRIBUTION}</p>
      </div>

      <TabBar active={activeTab} onSelect={onSelectTab} />
    </div>
  )
}
