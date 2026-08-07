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
import { registerBasemapProtocol } from './basemap'
import { registerMapWorker } from './mapWorker'
import { attachMapAppearance, buildMapStyle } from './style'
import { attachMapDetail } from './mapDetail'
import { attachContourUnits, registerTerrain } from './contours'
import { attachLiveSourceHealth, type LiveSourceHealth } from './liveSourceHealth'
import { attachElevationLabelUnits } from './liveTopo'
import type { TerrainUrls } from './terrain'
import { attachMapChrome, type ScaleUnits } from './mapChrome'
import type { ResolvedTheme } from '../lib/theme'
import { attachHiddenPoiTypes, attachPoiData, attachPoiIcons } from './poiLayers'
import { attachClosureData, type ClosureBand } from './closureLayers'
import { attachWarningData, attachWarningIcon, type WarningPoint } from './warningLayers'
import { attachPoiTaps } from './poiTaps'
import type { BoundingBox, MapPoint } from '../lib/legendContents'
import type { BackgroundSource, LayerDetailLevel, MapStyle } from '../lib/userPreferences'
import { openingZoomFloor, type ArchiveZooms } from '../lib/archiveCoverage'

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
  /**
   * Closed stretches of trail, already in map coordinates.
   *
   * Coordinates rather than mile markers, deliberately. Turning "mile 1,408.2
   * to 1,408.6" into a line needs the centerline index, which the shell holds
   * and this component has no business asking for - the same division that
   * keeps `pois` a list of points rather than a POI database. See
   * closureLayers.ts's `closureBands`.
   */
  closures?: readonly ClosureBand[]
  /**
   * Moderator-escalated warnings, as points. NEVER a notification - see the
   * header of warningLayers.ts.
   */
  warnings?: readonly WarningPoint[]
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
   * What the downloaded archive's own header says it covers, when it is known.
   *
   * Used for exactly one thing: keeping the opening camera out of the zooms
   * the archive has no tiles for, which on the offline background is the
   * difference between a map and blank paper (#216). It never constrains what
   * the hiker can do afterwards - zooming out past the download is allowed,
   * and the chrome says so rather than the map refusing.
   */
  archiveZooms?: ArchiveZooms | null
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
   * Which theme the canvas is drawn in - see map/style.ts's mapBackdrop.
   *
   * Resolved by the shell (lib/useTheme.ts) rather than read here, for the
   * reason `units` is: this component draws the map, and a hiker's preference
   * is the shell's to know. It also has to be the same answer the chrome
   * around the canvas is using, and two independent reads of one media query
   * is how a dark app ends up around a light map.
   */
  theme?: ResolvedTheme
  /**
   * Which of the sheet's palettes to draw, and whether night_hike's red-light
   * sub-mode is armed (MAP_STYLE_SPEC.md). Handed down like `theme` and
   * applied the same two ways: seeded into the built style for a correct
   * first frame, repainted in place on change.
   */
  mapStyle?: MapStyle
  redLight?: boolean
  /**
   * How much of the sheet to draw - see map/mapDetail.ts. Pure layer
   * visibility on the live sheet; the downloaded raster has no layers to
   * thin and ignores it.
   */
  detail?: LayerDetailLevel
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
  /**
   * Which of the live background's network sources reported an error and never
   * drew anything - see map/liveSourceHealth.ts.
   *
   * Reported rather than rendered: this component draws the map, and what the
   * hiker is told about it belongs to the chrome. Must be stable across
   * renders (a `useState` setter already is), like `onViewportChange` - an
   * inline function would re-attach the listeners on every parent render.
   */
  onLiveSourceHealth?: (health: LiveSourceHealth) => void
}

const DEFAULT_CENTER: [number, number] = [-77.1, 39.3]
const DEFAULT_ZOOM = 12

/** Breathing room around a fitted box, and the figure the opening-floor
 *  calculation has to use too or the two disagree about what fits. */
const FIT_PADDING = 24

// Module-level, so the default is the SAME value on every render. A `= []`
// default parameter would hand over a fresh identity each time and re-run the
// effect that depends on it, which for the POI source means re-serialising
// every pin on the trail on every render of the map screen.
const NO_POIS: readonly MapPoint[] = []
const NOTHING_HIDDEN: ReadonlySet<string> = new Set()
const NO_CLOSURES: readonly ClosureBand[] = []
const NO_WARNINGS: readonly WarningPoint[] = []

export function MapView({
  topoArchiveUrl,
  trailsUrl,
  background = 'hiking_topo_live',
  pois = NO_POIS,
  hiddenTypes = NOTHING_HIDDEN,
  closures = NO_CLOSURES,
  warnings = NO_WARNINGS,
  onSelectPoi,
  center,
  zoom,
  bounds,
  archiveZooms = null,
  showZoomButtons = false,
  units = 'imperial',
  theme = 'light',
  mapStyle = 'field',
  redLight = false,
  detail = 'standard',
  onViewportChange,
  onMapReady,
  onLiveSourceHealth,
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

    // And basemap:// URLs - the hiking sheet's local-first tile resolution
    // (basemap.ts). Registered unconditionally like the pmtiles scheme, and
    // unlike the terrain protocols below: it reaches the network only as the
    // per-tile fallthrough of a source the chosen style actually declares,
    // so there is no behind-the-back request to guard against.
    registerBasemapProtocol()

    // Same contract for the DEM and contour protocols, with one difference
    // worth being deliberate about: this one reaches the network, so it is
    // only set up when a background that uses it was actually asked for.
    // Someone who chose the downloaded archive to stay off the network should
    // not have a DEM protocol registered behind their back.
    //
    // Best-effort, and narrower than it used to claim. This comment said the
    // branch fires when "a Web Worker and a blob URL" are unavailable; neither
    // is true. contours.ts feature-detects Worker and falls back to the main
    // thread rather than throwing, and the worker it constructs is the app's
    // own emitted asset (demWorker.ts, since #187) rather than the library's
    // blob. What actually lands here is a Content-Security-Policy whose
    // worker-src refuses that construction - no such policy is served today,
    // so this is a guard against a future hardening rather than a path
    // anyone is on.
    //
    // Either way the outcome is a map without contours, not no map: a failure
    // here costs terrain and nothing else. That is now true of what gets
    // built, too - style.ts used to drop the entire live sheet along with it.
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
      style: buildMapStyle({
        topoArchiveUrl,
        trailsUrl,
        background,
        terrain,
        units,
        theme,
        mapStyle,
        redLight,
      }),
      // `bounds` wins where it is given: MapLibre works out the zoom that fits
      // the box on this particular screen, which is the whole point of asking
      // for a box rather than a zoom number.
      ...(bounds === undefined
        ? { center: center ?? DEFAULT_CENTER, zoom: zoom ?? DEFAULT_ZOOM }
        : { bounds, fitBoundsOptions: { padding: FIT_PADDING } }),
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
    //
    // `theme`, `mapStyle` and `redLight` are omitted on exactly that pattern
    // (MAP_STYLE_SPEC.md spells it as a requirement: appearance never rebuilds
    // the map). They seed the backdrop, the archive's dimming, the trail ink
    // and the sheet's palette so a cold start under a dark appearance is dark
    // in its first frame, and the appearance effect below repaints all of it
    // in place for every change after that. A hiker tapping "Dark" while
    // walking must not lose the map they were reading.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topoArchiveUrl, trailsUrl, background])

  // Keeps the OPENING camera out of the zooms the download cannot draw (#216).
  //
  // Its own effect rather than part of the construction above, for three
  // reasons that all point the same way. It reads the zoom MapLibre actually
  // settled on, so nothing here has to reimplement how a box is fitted to a
  // screen. It re-runs when the archive's header lands, which is a tick AFTER
  // the map is built and would otherwise be missed entirely. And it does that
  // without the archive's coverage becoming a dependency of the construction
  // effect, where a late-arriving header would tear down a live WebGL context
  // and rebuild it.
  //
  // Only the zoom is touched. The centre stays exactly where fitBounds put it,
  // which is what makes this defensible at all: App.tsx's opening view is
  // built around not making a confident-looking claim about where the hiker is
  // (Harpers Ferry was removed for precisely that), and moving the scale in
  // without moving the centre claims nothing new.
  //
  // Gated on `bounds`, which the shell supplies only for the very first view -
  // once there is a remembered camera it passes centre and zoom instead. So
  // this cannot fight a hiker who has deliberately zoomed out to look at the
  // whole trail; it only decides where they start.
  useEffect(() => {
    if (map === null || bounds === undefined || background !== 'usgs_topo_offline') return

    const floor = openingZoomFloor(archiveZooms, map.getZoom())
    if (floor !== null) map.setZoom(floor)
  }, [map, bounds, background, archiveZooms])

  // Chrome lives in its own effect so that a preference which only affects the
  // controls - the scale bar's units, the zoom buttons - re-attaches three
  // controls instead of tearing down and rebuilding the entire map underneath
  // the hiker.
  useEffect(() => {
    if (map === null) return
    return attachMapChrome(map, { showZoomButtons, units })
  }, [map, showZoomButtons, units])

  // The appearance's half of the same promise, and the widest one: it
  // repaints the backdrop, the archive's dimming, the trail's ink and every
  // colour on the live sheet - see map/style.ts's attachMapAppearance.
  useEffect(() => {
    if (map === null) return
    return attachMapAppearance(map, { theme, mapStyle, redLight })
  }, [map, theme, mapStyle, redLight])

  // And the detail level's: which of the sheet's layers are drawn at all.
  // Pure visibility (map/mapDetail.ts), so a hiker thinning the sheet keeps
  // the camera, the tiles in flight and the WebGL context, like every other
  // preference on this screen.
  useEffect(() => {
    if (map === null) return
    return attachMapDetail(map, detail)
  }, [map, detail])

  // The contours' half of that same promise. The scale bar can just be
  // re-created with new units; the contour source has to be re-pointed at a
  // different tile URL, which is what this does - see contours.ts.
  useEffect(() => {
    if (map === null) return
    return attachContourUnits(map, units)
  }, [map, units])

  // And the labels' half: the contour suffix and the peak elevation field
  // are baked into the style as layout, so re-pointing the tiles alone
  // leaves metric values under imperial punctuation - see liveTopo.ts.
  useEffect(() => {
    if (map === null) return
    return attachElevationLabelUnits(map, units)
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

  // The safety overlays, on the same three-clocks reasoning as the POIs above:
  // the warning pin image is built once, and the two datasets arrive from the
  // network on their own schedules and refuse independently (App.tsx). Folding
  // them together would mean a closures read that came back re-rasterising a
  // 88px pin, and either read failing would hold the other off the map.
  useEffect(() => {
    if (map === null) return
    return attachWarningIcon(map)
  }, [map])

  useEffect(() => {
    if (map === null) return
    return attachClosureData(map, closures)
  }, [map, closures])

  useEffect(() => {
    if (map === null) return
    return attachWarningData(map, warnings)
  }, [map, warnings])

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

  // Its own effect, like every other attach here, so that a shell which starts
  // caring about source health does not cost a WebGL context to wire up.
  useEffect(() => {
    if (map === null || onLiveSourceHealth === undefined) return
    return attachLiveSourceHealth(map, onLiveSourceHealth)
  }, [map, onLiveSourceHealth])

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
