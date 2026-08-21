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
import { readTrailsMerged } from '../lib/trailShape'
import {
  attachMapAppearance,
  attachTrailData,
  attachTrailOverview,
  buildMapStyle,
} from './style'
import { attachMapDetail } from './mapDetail'
import { attachContourUnits, registerTerrain } from './contours'
import { attachLiveSourceHealth, type SourceReport } from './liveSourceHealth'
import { attachElevationLabelUnits } from './liveTopo'
import type { TerrainUrls } from './terrain'
import { attachMapChrome, type ScaleUnits } from './mapChrome'
import type { ResolvedTheme } from '../lib/theme'
import { attachPoiData, attachPoiFilter, attachPoiIcons } from './poiLayers'
import {
  attachAtcUpdateData,
  attachAtcUpdateTaps,
  type AtcUpdatePoint,
} from './atcUpdateLayers'
import { attachClosureData, type ClosureBand } from './closureLayers'
import {
  attachCorridorData,
  attachHighlightTaps,
  EMPTY_CORRIDOR,
  type CorridorFeatureCollection,
} from './corridorLayers'
import { attachDroughtData, setDroughtVisible, type DroughtBand } from './droughtLayers'
import { attachWarningData, attachWarningIcon, type WarningPoint } from './warningLayers'
import {
  attachWorkdayData,
  attachWorkdayIcon,
  attachWorkdayTaps,
  type WorkdayPoint,
} from './workdayLayers'
import { attachLineTaps, type TappedLine } from './lineTaps'
import { attachPoiTaps } from './poiTaps'
import { attachRouteData, attachRouteTaps, type RouteDrawing } from './routeLayers'
import type { BoundingBox, MapPoint } from '../lib/legendContents'
import type {
  BackgroundSource,
  LayerDetailLevel,
  MapStyle,
  Theme,
} from '../lib/userPreferences'
import { openingZoomFloor, type ArchiveZooms } from '../lib/archiveCoverage'

export interface MapViewProps {
  /** `pmtiles://` URL for the downloaded topo archive. */
  topoArchiveUrl: string
  /**
   * Local URL of the exported trail lines.
   *
   * Seeds the style so the opening frame already has the trail on it, and is
   * then re-pointed in place whenever it changes - the same two-step `theme`
   * and `pois` get, and for the same reason. The shell mints this URL when the
   * lines come back from IndexedDB, a beat after the map is built.
   */
  trailsUrl: string
  /**
   * The corridor-view centerline, while there is no real one (#869).
   *
   * Null once the shell has the real line - or has decided there is no sketch
   * to draw - and clearing it is the point rather than an edge case: this is
   * a line that is only true at the zooms it is drawn at, and it stops being
   * drawn the moment something better arrives. lib/config.ts's
   * TRAILS_OVERVIEW_KEY has what "only true at those zooms" means in metres.
   */
  overviewTrailsUrl?: string | null
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
   * Which staleness ring each waypoint wears and whether its pin fades -
   * lib/stalenessDisplay.ts's `pinConditionFor`, precomputed by the shell
   * from the field-note roll-up. Absent means no notes have arrived, which
   * renders exactly as the day-one map: no rings, no fades (#256, #759).
   */
  pinCondition?: (poiId: string, poiType: string) => { ring: string; faded: boolean }
  /**
   * POI categories the hiker has hidden from the legend. Applied as a filter
   * on the pin layer, so hiding a category costs a filter, not a rebuild.
   */
  hiddenTypes?: ReadonlySet<string>
  /**
   * The legend's "Verified?" toggle: draw only waypoints somebody has
   * confirmed exist. Rides the same filter as {@link hiddenTypes} rather than
   * a second one, so the two cannot fight over the layer.
   */
  verifiedOnly?: boolean
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
   * The corridor view's attribution - the miles with no recorded club, and the
   * marks where responsibility changes hands - already in map coordinates
   * (#598).
   *
   * Coordinates rather than mile ranges, for the reason `closures` gives: the
   * centerline index belongs to the shell. See map/corridorLayers.ts.
   */
  corridor?: CorridorFeatureCollection
  /** Told which highlight mark a tap landed on, or null for a miss - which is
   *  how the sheet closes on a tap elsewhere (#858). */
  onSelectHighlight?: (id: string | null) => void
  /**
   * This week's drought bands, already as published polygons (#720).
   *
   * Unlike `closures`, these need no coordinate work in the shell: the
   * pipeline ships real geometry rather than mile markers, so there is no
   * centerline index in the way and the features go straight onto the source.
   */
  drought?: readonly DroughtBand[]
  /** Whether the hiker has the drought wash switched on. Separate from the
   *  data for the reason droughtLayers.ts gives: the bands arrive once and
   *  the switch moves whenever somebody taps it. */
  showDrought?: boolean
  /**
   * The ATC's own trail updates, in the same coordinates and drawn at the
   * same weight - a second band source rather than more features in
   * `closures`, because the two carry different rhythms and a tap has to be
   * able to say which kind it landed on (map/atcUpdateLayers.ts, #461).
   */
  atcUpdates?: readonly ClosureBand[]
  /** The same notices that name a single mile rather than a stretch, drawn as
   *  dots. Most of what the ATC publishes is one of these. */
  atcUpdatePoints?: readonly AtcUpdatePoint[]
  /** A tap landed on an ATC band, by band id. The shell decides what to show
   *  - this component deliberately does not know what a sheet is. */
  onSelectAtcUpdate?: (bandId: string) => void
  /**
   * Moderator-escalated warnings, as points. NEVER a notification - see the
   * header of warningLayers.ts.
   */
  warnings?: readonly WarningPoint[]
  /**
   * Volunteer workdays, as points (#760).
   *
   * The shell does the windowing AND the staleness check: past
   * `OPPORTUNITIES_STALE_MS` it passes nothing, because a pin has no hedged
   * form and a hedged invitation still reads as an invitation
   * (workdayLayers.ts's header).
   */
  workdays?: readonly WorkdayPoint[]
  /** Which workday a tap landed on. Must be stable across renders, like
   *  `onSelectPoi`. */
  onSelectWorkday?: (projectId: string) => void
  /**
   * The route being built, already in map coordinates - same division as
   * `closures`: turning miles into geometry needs the centerline index,
   * which the shell holds. Null (or absent) clears the drawing.
   */
  routeDrawing?: RouteDrawing | null
  /**
   * When set, the map is in route-building mode: a tap anywhere reports its
   * raw coordinate here, and the POI tap handler is NOT attached - one
   * interpreter per touch (see routeLayers.ts's attachRouteTaps). Must be
   * stable across renders (useCallback), like `onSelectPoi`.
   */
  onRouteTap?: (at: { lon: number; lat: number }) => void
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
  /**
   * Room to leave around {@link bounds} when fitting it, per side.
   *
   * A number is the same inset all round and is what almost every caller wants.
   * An object is for the case this exists for: something is drawn OVER the map,
   * so the box has to be framed against the part of the canvas that is actually
   * visible rather than against the whole of it. First run is that case - the
   * onboarding card covers most of the screen, and without a bottom inset the
   * trail is fitted to the full canvas and then three quarters of it is hidden,
   * leaving a fragment of Maine in the corner above the card (#719 review).
   */
  boundsPadding?: number | { top: number; bottom: number; left: number; right: number }
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
  /**
   * A trail line was tapped, reported as its published facts - or the bare
   * map was, reported as null so the shell can dismiss the line sheet
   * (#134). Yields to pins, dots and ATC notices under the same thumb (see
   * map/lineTaps.ts for the two rules). Must be stable across renders
   * (useCallback), like `onSelectPoi`.
   */
  onSelectLine?: (line: TappedLine | null) => void
  /** Web only; touch platforms rely on pinch (see mapChrome.ts). */
  showZoomButtons?: boolean
  units?: ScaleUnits
  /** Whether the hiker has location switched on - which decides whether the
   *  locate control is offered at all (#312, and see mapChrome.ts for the
   *  three things attaching it unconditionally cost). Defaults to false, so a
   *  caller that has not thought about it does not open a GPS watch. */
  locationEnabled?: boolean
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
   * The stored theme preference behind `theme`'s resolution, so the sheet
   * can tell a CHOSEN dark from a sunset one: field's auto-dark is
   * night_hike, its chosen dark is its own maximum-contrast night sheet -
   * see liveTopo.ts's sheetVariant.
   */
  themeChoice?: Theme
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
   * Which of the background's sources reported an error and never drew
   * anything - see map/liveSourceHealth.ts.
   *
   * Reported rather than rendered: this component draws the map, and what the
   * hiker is told about it belongs to the chrome. Must be stable across
   * renders (a `useState` setter already is), like `onViewportChange` - an
   * inline function would re-attach the listeners on every parent render.
   *
   * The report carries both what never arrived and what has actually drawn,
   * plus `withdrawn` for the one report this map sends as it is torn down. A
   * caller drawing only this map's chrome needs the first; one that remembers
   * a failure across screens needs all three (#352).
   */
  onLiveSourceHealth?: (report: SourceReport) => void
}

const DEFAULT_CENTER: [number, number] = [-77.1, 39.3]
const DEFAULT_ZOOM = 12

/** Breathing room around a fitted box, on every side, when the caller asks for
 *  nothing more specific. */
const FIT_PADDING = 24

// Module-level, so the default is the SAME value on every render. A `= []`
// default parameter would hand over a fresh identity each time and re-run the
// effect that depends on it, which for the POI source means re-serialising
// every pin on the trail on every render of the map screen.
const NO_POIS: readonly MapPoint[] = []
const NOTHING_HIDDEN: ReadonlySet<string> = new Set()
const NO_CLOSURES: readonly ClosureBand[] = []
const NO_DROUGHT: readonly DroughtBand[] = []
const NO_ATC_UPDATES: readonly ClosureBand[] = []
const NO_ATC_POINTS: readonly AtcUpdatePoint[] = []
const NO_WARNINGS: readonly WarningPoint[] = []
const NO_WORKDAYS: readonly WorkdayPoint[] = []

export function MapView({
  topoArchiveUrl,
  trailsUrl,
  background = 'hiking_topo_live',
  overviewTrailsUrl = null,
  pois = NO_POIS,
  pinCondition,
  hiddenTypes = NOTHING_HIDDEN,
  verifiedOnly = false,
  closures = NO_CLOSURES,
  // A stable empty collection, for the reason NO_CLOSURES is one: a fresh
  // object literal in a default would be a new identity every render, and the
  // effect below would re-push it to MapLibre on each one.
  corridor = EMPTY_CORRIDOR,
  onSelectHighlight,
  drought = NO_DROUGHT,
  showDrought = false,
  atcUpdates = NO_ATC_UPDATES,
  atcUpdatePoints = NO_ATC_POINTS,
  onSelectAtcUpdate,
  warnings = NO_WARNINGS,
  workdays = NO_WORKDAYS,
  onSelectWorkday,
  routeDrawing = null,
  onRouteTap,
  onSelectPoi,
  onSelectLine,
  center,
  zoom,
  bounds,
  archiveZooms = null,
  boundsPadding = FIT_PADDING,
  showZoomButtons = false,
  units = 'imperial',
  locationEnabled = false,
  theme = 'light',
  themeChoice = 'auto',
  mapStyle = 'field',
  redLight = false,
  detail = 'standard',
  onViewportChange,
  onMapReady,
  onLiveSourceHealth,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [map, setMap] = useState<MapLibreMap | null>(null)

  /**
   * Which trail lines the live map's source is already pointing at, or null
   * when there is no map.
   *
   * Seeding the style AND pushing the same URL in afterwards would fetch and
   * re-tile the lines twice for every map built - twelve megabytes of
   * coordinates, and measurably more worker time than the whole low-zoom
   * tiling costs once (see the `tolerance` note in map/style.ts). So the
   * construction below records what it seeded, and the attach further down
   * writes only when the answer has actually changed.
   */
  const drawnTrailsUrl = useRef<string | null>(null)

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
        themeChoice,
        mapStyle,
        redLight,
        // Read here, at creation, rather than passed as a prop: the trails
        // source's tolerance is fixed when the style is built, and the fact
        // deciding it is a property of the bytes in storage (recorded
        // synchronously readable for exactly this moment - lib/trailShape.ts,
        // #161), not of anything the shell renders from.
        trailsMerged: readTrailsMerged(),
      }),
      // `bounds` wins where it is given: MapLibre works out the zoom that fits
      // the box on this particular screen, which is the whole point of asking
      // for a box rather than a zoom number.
      ...(bounds === undefined
        ? { center: center ?? DEFAULT_CENTER, zoom: zoom ?? DEFAULT_ZOOM }
        : { bounds, fitBoundsOptions: { padding: boundsPadding } }),
      // Attribution is rendered by the app's own chrome, positioned per
      // WIREFRAMES.md, rather than by MapLibre's default control.
      attributionControl: false,
    })
    // Recorded, not assumed: the style above was seeded with whatever this
    // render's lines are, so the attach below has nothing to do until they
    // change. Cleared on teardown so the next map is seeded and recorded
    // together, and a rebuild can never inherit the previous map's answer.
    drawnTrailsUrl.current = trailsUrl
    setMap(created)

    return () => {
      drawnTrailsUrl.current = null
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
    //
    // `trailsUrl` is omitted on that same pattern, and it is the one that used
    // to cost a cold start a whole extra map. The lines are read out of
    // IndexedDB a beat after the map is built, so depending on this URL meant
    // every launch tore down the map a second after it appeared - a blink and
    // a re-frame, for data a GeoJSON source can take in place. It still seeds
    // the style, so the first frame already has the trail on it; the effect
    // below re-points the source for every change after that.
    //
    // Only `background` remains, and it earns the rebuild: the two backgrounds
    // are different sources and a different layer stack, not a different value
    // in the same one. App.tsx holds its first render until it knows which one
    // to ask for, so switching is the hiker's doing rather than a fact about
    // the phone arriving late.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topoArchiveUrl, background])

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
    return attachMapChrome(map, { showZoomButtons, units, locationEnabled })
  }, [map, showZoomButtons, units, locationEnabled])

  // The appearance's half of the same promise, and the widest one: it
  // repaints the backdrop, the archive's dimming, the trail's ink and every
  // colour on the live sheet - see map/style.ts's attachMapAppearance.
  useEffect(() => {
    if (map === null) return
    return attachMapAppearance(map, { theme, themeChoice, mapStyle, redLight })
  }, [map, theme, themeChoice, mapStyle, redLight])

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

  // The trail lines, pushed onto the live map for the same reason the POIs
  // below are: they come out of IndexedDB after the map exists, and they are
  // one GeoJSON source, which can simply be handed a new URL. Its own effect
  // rather than folded in with the pins, because the two arrive from separate
  // reads and a re-tiling of twelve megabytes of coordinates must not ride
  // along with a legend tap.
  useEffect(() => {
    if (map === null || drawnTrailsUrl.current === trailsUrl) return
    drawnTrailsUrl.current = trailsUrl
    return attachTrailData(map, trailsUrl)
  }, [map, trailsUrl])

  // The sketch that stands in for the trail line until it arrives, on the
  // same seam as the lines above: a GeoJSON source takes a URL in place, and
  // takes an empty collection to say it is done. Its own effect because it
  // moves on a different clock from the real line - it is set once early and
  // cleared once, where the real one is set once and stays.
  useEffect(() => {
    if (map === null) return
    return attachTrailOverview(map, overviewTrailsUrl)
  }, [map, overviewTrailsUrl])

  // Three separate effects rather than one, because they change on different
  // clocks: the pin images are built once and never again, while the source and
  // the filter both move when the hiker taps a legend row. Folding them together
  // would re-register sixty rasterised badges on every one of those taps.
  //
  // The images are the one that must NOT re-run - that is the whole of this
  // split. The other two now share a clock (see below) and are still two
  // effects, because a POI download landing should not re-run a `setFilter` and
  // the pair reads as what it is: two different questions about the same tap.
  //
  // AND NOT UNTIL THERE IS A PIN TO DRAW (#857). A map with no POIs on it
  // cannot ask for a single one of the 46 images - the style's `match` arms
  // are reached by a feature or not at all - so on the launch where that bill
  // was largest it bought nothing. That is every first run: the entry steps
  // hold the waypoints back (lib/useTrailData.ts), and this is what stops the
  // map paying for them anyway.
  //
  // The bill is 2,521 ms of rasterising, measured 2026-08-20 on a 4x CPU
  // throttle; map/poiIconImages.ts has the measurement and the other half of
  // the fix, which is where that work runs when it does run.
  //
  // `havePois` rather than `pois`, so this still runs once and not per
  // download: the images are the same 46 whatever is in the array.
  const havePois = pois.length > 0
  useEffect(() => {
    if (map === null || !havePois) return
    return attachPoiIcons(map)
  }, [map, havePois])

  // The hidden set is in BOTH of the next two effects, and deliberately. The
  // filter decides which pins are drawn; the source decides which POIs get a
  // pin to be drawn at all, and a site folds its members away only behind a pin
  // the filter is going to keep (#607). So a legend tap rebuilds the features as
  // well as re-filtering the layer - features/POI_SITES.md §6 asked for exactly
  // that, and 2,800 points is the cost it weighed.
  useEffect(() => {
    if (map === null) return
    return attachPoiData(map, pois, { hiddenTypes, verifiedOnly }, pinCondition)
  }, [map, pois, hiddenTypes, verifiedOnly, pinCondition])

  useEffect(() => {
    if (map === null) return
    return attachPoiFilter(map, hiddenTypes, verifiedOnly)
  }, [map, hiddenTypes, verifiedOnly])

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

  // Its own effect rather than folded into the closures above: the two arrive
  // on completely different schedules - closures from the network whenever
  // conditions sync, the attribution once from IndexedDB at launch - and
  // sharing one would re-push thirty clubs' geometry on every conditions poll.
  useEffect(() => {
    if (map === null) return
    return attachCorridorData(map, corridor)
  }, [map, corridor])

  useEffect(() => {
    if (map === null || onSelectHighlight === undefined) return
    return attachHighlightTaps(map, onSelectHighlight)
  }, [map, onSelectHighlight])

  // Two effects rather than one, and deliberately: the bands arrive from the
  // network once and the switch moves whenever a hiker taps it. Folding them
  // together would re-push the polygons on every tap of the toggle.
  //
  // Neither is passed to `buildMapStyle` at creation, though the option
  // exists there for tests and for reading the stack in one place. Threading
  // the switch through the style would put it in the style's rebuild
  // dependencies, and a hiker flipping a background tint would get the whole
  // map torn down and rebuilt - the exact cost `setDroughtVisible` avoids.
  // The layer is built hidden and this effect shows it on the next frame.
  useEffect(() => {
    if (map === null) return
    return attachDroughtData(map, drought)
  }, [map, drought])

  useEffect(() => {
    if (map === null) return
    return setDroughtVisible(map, showDrought)
  }, [map, showDrought])

  useEffect(() => {
    if (map === null) return
    return attachAtcUpdateData(map, atcUpdates, atcUpdatePoints)
  }, [map, atcUpdates, atcUpdatePoints])

  useEffect(() => {
    if (map === null) return
    return attachWarningData(map, warnings)
  }, [map, warnings])

  // The workday pins (#760): the image once, the data whenever the shell's
  // window or staleness verdict changes, and the tap. Same three-effect shape
  // as the warnings above.
  useEffect(() => {
    if (map === null) return
    return attachWorkdayIcon(map)
  }, [map])

  useEffect(() => {
    if (map === null) return
    return attachWorkdayData(map, workdays)
  }, [map, workdays])

  useEffect(() => {
    // Not attached during route building, for attachRouteTaps' rule: one
    // interpreter per touch, and while a route is being drawn every tap on
    // this map means "a point on my route".
    if (map === null || onSelectWorkday === undefined || onRouteTap !== undefined) return
    return attachWorkdayTaps(map, onSelectWorkday)
  }, [map, onSelectWorkday, onRouteTap])

  // The route drawing, on the closure pattern: pushed onto the live map, its
  // own effect so a point dropped mid-build re-serialises a few features and
  // nothing else.
  useEffect(() => {
    if (map === null) return
    return attachRouteData(map, routeDrawing)
  }, [map, routeDrawing])

  // Taps are their own effect for the same reason: this one re-binds when the
  // shell hands over a different handler, which has nothing to do with the
  // pins themselves and must not re-push the POI source to do it.
  //
  // Suppressed entirely while the route builder owns the tap. Two live
  // handlers would race to interpret one touch - a tap meant to drop a point
  // would also select whatever POI sat under it - and the ATC handler's
  // hits-only contract (atcUpdateLayers.ts) only works because bare-ground
  // taps have exactly one interpreter.
  useEffect(() => {
    if (map === null || onSelectPoi === undefined || onRouteTap !== undefined) return
    return attachPoiTaps(map, onSelectPoi)
  }, [map, onSelectPoi, onRouteTap])

  useEffect(() => {
    if (map === null || onRouteTap === undefined) return
    return attachRouteTaps(map, onRouteTap)
  }, [map, onRouteTap])

  // The line taps (#134), suppressed in route mode like every other tap
  // handler. Attached separately from the POI taps because their yields
  // differ - lineTaps.ts asks the POI and ATC layers itself and reports
  // null where they win, so the one-interpreter rule holds without these
  // two effects knowing about each other.
  useEffect(() => {
    if (map === null || onSelectLine === undefined || onRouteTap !== undefined) return
    return attachLineTaps(map, onSelectLine)
  }, [map, onSelectLine, onRouteTap])

  // Suppressed in route mode for the same one-interpreter rule as the POI
  // taps above: a point dropped near an ATC notice must not also open its
  // sheet over the builder.
  useEffect(() => {
    if (map === null || onSelectAtcUpdate === undefined || onRouteTap !== undefined)
      return
    return attachAtcUpdateTaps(map, onSelectAtcUpdate)
  }, [map, onSelectAtcUpdate, onRouteTap])

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
