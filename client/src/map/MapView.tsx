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
// MapLibre's own stylesheet, and not optional. Everything the map puts on
// itself - compass, locate, the scale bar, the zoom buttons - is positioned by
// this file and by nothing else. Without it `.maplibregl-canvas` is not
// absolute, so the control container follows the canvas in normal flow instead
// of sitting over it and lands past the bottom edge of the map: in a 1280x800
// window the whole stack sat at y=804, four pixels below the fold, with the
// document growing a scrollbar to reach it. The map drew correctly and had
// nothing on it, which is exactly what it looked like.
//
// chrome.css's `.map-view .maplibregl-ctrl button` rule is an OVERRIDE of a
// size set here (WIREFRAMES.md's 42px against MapLibre's 29px), which is the
// tell that this import was forgotten rather than declined.
import 'maplibre-gl/dist/maplibre-gl.css'
import { registerPMTilesProtocol } from './protocol'
import { registerMapWorker } from './mapWorker'
import { buildMapStyle } from './style'
import { attachContourUnits, registerTerrain } from './contours'
import type { TerrainUrls } from './terrain'
import { attachMapChrome, type ScaleUnits } from './mapChrome'
import { attachHiddenPoiTypes, attachPoiData, attachPoiIcons } from './poiLayers'
import { attachPoiTaps } from './poiTaps'
import type { BoundingBox, MapPoint } from '../lib/legendContents'
import type { BackgroundSource } from '../lib/userPreferences'

export interface MapViewProps {
  /** `pmtiles://` URL for the downloaded topo archive. */
  topoArchiveUrl: string
  /** Local URL of the exported trail lines. */
  trailsUrl: string
  /** Which background to draw - see lib/userPreferences.ts. */
  background?: BackgroundSource
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
  /**
   * A pin was tapped, by POI id - or the bare map was, reported as null so
   * the shell can dismiss whatever the last pin opened. Must be stable across
   * renders (useCallback), like `onViewportChange` - an inline function would
   * re-bind the map's listeners on every render of the parent.
   *
   * Only the id: this component knows what is drawn on the map, not what the
   * app knows about it, and looking a POI up is the shell's job.
   */
  onSelectPoi?: (id: string | null) => void
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
  background = 'hiking_topo_live',
  pois = NO_POIS,
  hiddenTypes = NOTHING_HIDDEN,
  onSelectPoi,
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

    // Before anything else: MapLibre 6 looks for its own worker next to the
    // bundle, where no bundler ever puts it, and a map with no worker parses no
    // tiles at all - see mapWorker.ts. Every layer below depends on this line.
    registerMapWorker()

    // The style resolves pmtiles:// URLs, so the protocol has to exist first.
    registerPMTilesProtocol()

    // Same contract for the DEM and contour protocols, with one difference
    // worth being deliberate about: this one reaches the network, so it is
    // only set up when a background that uses it was actually asked for.
    // Someone who chose the downloaded archive to stay off the network should
    // not have a DEM protocol registered behind their back.
    //
    // Best-effort: contour generation needs a Web Worker and a blob URL, and
    // if either is unavailable the honest outcome is a map without contours,
    // not no map. A failure here costs terrain and nothing else - the
    // archive, the trail lines and the paper are all in the style already.
    let terrain: TerrainUrls | undefined
    if (background === 'hiking_topo_live') {
      try {
        terrain = registerTerrain(units)
      } catch (error) {
        console.warn('Terrain unavailable; drawing the background without it.', error)
      }
    }

    const created = new MapLibreMap({
      container,
      style: buildMapStyle({ topoArchiveUrl, trailsUrl, background, terrain, units }),
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
    //
    // `units` is omitted for the same reason, even though it seeds the contour
    // interval: switching to metric must not cost a WebGL context. The units
    // effect below re-points the contour source in place instead.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topoArchiveUrl, trailsUrl, background])

  // Chrome lives in its own effect so that a preference which only affects the
  // controls - the scale bar's units, the zoom buttons - re-attaches three
  // controls instead of tearing down and rebuilding the entire map underneath
  // the hiker.
  useEffect(() => {
    if (map === null) return
    return attachMapChrome(map, { showZoomButtons, units })
  }, [map, showZoomButtons, units])

  // The contours' half of that same promise. The scale bar can just be
  // re-created with new units; the contour source has to be re-pointed at a
  // different tile URL, which is what this does - see contours.ts.
  useEffect(() => {
    if (map === null) return
    return attachContourUnits(map, units)
  }, [map, units])

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

  // Taps are their own effect for the same reason: this one re-binds when the
  // shell hands over a different handler, which has nothing to do with the
  // pins themselves and must not re-push the POI source to do it.
  useEffect(() => {
    if (map === null || onSelectPoi === undefined) return
    return attachPoiTaps(map, onSelectPoi)
  }, [map, onSelectPoi])

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
