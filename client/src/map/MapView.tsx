// The map canvas itself. Chrome (header, ribbon, tab bar, controls) composes
// around this rather than living inside it.
//
// Everything delicate here is lifecycle. A map built twice means two WebGL
// contexts, two GPS watchers and doubled range reads against an on-device
// archive that can be 1.18 GB; a map never torn down leaks all of the same.
// React StrictMode mounts, unmounts and remounts on purpose in development to
// surface exactly that, so the effect below is written to survive it: build
// once per effect run, and fully undo the build on cleanup.

import { useEffect, useRef, useState } from 'react'
import { Map as MapLibreMap } from 'maplibre-gl'
import { registerPMTilesProtocol } from './protocol'
import { buildMapStyle } from './style'
import { attachMapChrome, type ScaleUnits } from './mapChrome'
import { attachMapBackdrop } from './backdrop'
import { attachHiddenPoiTypes, attachPoiData, attachPoiIcons } from './poiLayers'
import type { BoundingBox, MapPoint } from '../lib/legendContents'

export interface MapViewProps {
  /** `pmtiles://` URL for the downloaded topo archive. */
  topoArchiveUrl: string
  /** Local URL of the exported trail lines. */
  trailsUrl: string
  /**
   * The POIs to draw - the same array the legend counts. Pushed onto the live
   * map rather than baked into the style, because they are read from IndexedDB
   * well after the map is built and swapping a style out drops the WebGL
   * context with it.
   */
  pois?: readonly MapPoint[]
  /**
   * POI categories the hiker has hidden from the legend. Applied as a filter
   * on the pin layer, so hiding a category costs a filter, not a rebuild.
   */
  hiddenTypes?: ReadonlySet<string>
  /** Initial centre only - later camera moves go through the map imperatively. */
  center?: [number, number]
  /** Initial zoom only. */
  zoom?: number
  /**
   * Opening view as a bounding box, `[[west, south], [east, north]]`. Takes
   * precedence over `center`/`zoom`, and is the better way to say "show all of
   * this" - the zoom that fits a box depends on the size of the screen, so
   * picking one here would frame it differently on every phone.
   */
  bounds?: [[number, number], [number, number]]
  /** Web only; touch platforms rely on pinch (see mapChrome.ts). */
  showZoomButtons?: boolean
  units?: ScaleUnits
  /**
   * What is on screen now, so the legend can describe it. Must be stable
   * across renders (useCallback) - an inline function would re-subscribe on
   * every render of the parent.
   */
  onViewportChange?: (bbox: BoundingBox) => void
  /**
   * The live map, handed over on build and `null` on teardown, so the shell
   * can move the camera imperatively. `center` cannot do that job - it seeds
   * the opening view only, and the first GPS fix usually lands after it.
   */
  onMapReady?: (map: MapLibreMap | null) => void
}

const DEFAULT_CENTER: [number, number] = [-77.1, 39.3]
const DEFAULT_ZOOM = 12

// Module-level, so the default is the SAME value on every render. A `= []`
// default parameter would hand over a fresh identity each time and re-run the
// effect that depends on it, which for the POI source means re-serialising
// every pin on the trail on every render of the map screen.
const NO_POIS: readonly MapPoint[] = []
const NOTHING_HIDDEN: ReadonlySet<string> = new Set()

export function MapView({
  topoArchiveUrl,
  trailsUrl,
  pois = NO_POIS,
  hiddenTypes = NOTHING_HIDDEN,
  center,
  zoom,
  bounds,
  showZoomButtons = false,
  units = 'imperial',
  onViewportChange,
  onMapReady,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [map, setMap] = useState<MapLibreMap | null>(null)

  // `center`/`zoom` are deliberately NOT dependencies. A parent writing
  // center={[x, y]} inline hands over a new array identity on every render; if
  // that drove this effect the map would be destroyed and rebuilt each time the
  // parent re-rendered. They seed the initial camera, and nothing more.
  useEffect(() => {
    const container = containerRef.current
    // Unreachable, and kept for the type checker: the div this ref is attached
    // to is rendered unconditionally, and an effect only runs after that div is
    // in the DOM. Ignored for coverage rather than covered, since there is no
    // way to render this component without its own container.
    /* v8 ignore next */
    if (container === null) return

    // The style resolves pmtiles:// URLs, so the protocol has to exist first.
    registerPMTilesProtocol()

    const created = new MapLibreMap({
      container,
      style: buildMapStyle({ topoArchiveUrl, trailsUrl }),
      // `bounds` wins where it is given: MapLibre works out the zoom that fits
      // the box on this particular screen, which is the whole point of asking
      // for a box rather than a zoom number.
      ...(bounds === undefined
        ? { center: center ?? DEFAULT_CENTER, zoom: zoom ?? DEFAULT_ZOOM }
        : { bounds, fitBoundsOptions: { padding: 24 } }),
      // Attribution is rendered by the app's own chrome, positioned per
      // WIREFRAMES.md, rather than by MapLibre's default control.
      attributionControl: false,
    })
    setMap(created)

    return () => {
      created.remove()
      setMap(null)
    }
    // Intentionally omitting `center`/`zoom` - see the note above. Including
    // them would rebuild the whole map whenever a parent re-rendered with an
    // inline array, which is the bug this omission exists to avoid.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topoArchiveUrl, trailsUrl])

  // Chrome lives in its own effect so that changing a display preference -
  // switching the scale bar to metric, say - re-attaches three controls
  // instead of tearing down and rebuilding the entire map underneath the hiker.
  useEffect(() => {
    if (map === null) return
    return attachMapChrome(map, { showZoomButtons, units })
  }, [map, showZoomButtons, units])

  // The backdrop's paper colour is in the style itself and needs nothing here.
  // This adds only the hatch on top of it, which needs a loaded style and so
  // cannot be expressed in buildMapStyle - see backdrop.ts.
  useEffect(() => {
    if (map === null) return
    return attachMapBackdrop(map)
  }, [map])

  // Three separate effects rather than one, because they change on completely
  // different clocks: the pin images are built once and never again, the POIs
  // land once the download finishes, and the hidden set changes every time the
  // hiker taps a legend row. Folding them together would re-register sixty
  // rasterised badges on every one of those taps.
  useEffect(() => {
    if (map === null) return
    return attachPoiIcons(map)
  }, [map])

  useEffect(() => {
    if (map === null) return
    return attachPoiData(map, pois)
  }, [map, pois])

  useEffect(() => {
    if (map === null) return
    return attachHiddenPoiTypes(map, hiddenTypes)
  }, [map, hiddenTypes])

  useEffect(() => {
    if (map === null || onViewportChange === undefined) return

    const report = () => {
      const bounds = map.getBounds()
      onViewportChange({
        west: bounds.getWest(),
        south: bounds.getSouth(),
        east: bounds.getEast(),
        north: bounds.getNorth(),
      })
    }

    // Reported once up front as well as on every move, so the legend is
    // correct for the opening view rather than only after the first pan.
    report()
    map.on('moveend', report)
    return () => {
      map.off('moveend', report)
    }
  }, [map, onViewportChange])

  useEffect(() => {
    if (onMapReady === undefined) return
    onMapReady(map)
    return () => onMapReady(null)
  }, [map, onMapReady])

  return (
    <div
      ref={containerRef}
      className="map-view"
      role="region"
      aria-label="Trail map"
      data-testid="map-view"
    />
  )
}
