// The live topographic background: OpenStreetMap vector tiles, drawn as a
// hiking sheet rather than a road map.
//
// WHY VECTOR, WHEN THE DOWNLOADED BACKGROUND IS RASTER
//
// The corridor archive is a picture of a map. US Topo quads are pre-rendered
// at 1:24,000, in per-quad UTM zones, with their labels baked into the pixels -
// so mosaicking them means reprojecting and resampling ink that was drawn for
// one scale, and reading them at any other zoom means looking at that ink
// stretched or crushed. Seams between quads of different vintages, type that
// cannot reflow, contours that cannot be recoloured, and nothing at all
// outside the 30-mile strip are not bugs in that pipeline; they are what a
// raster mosaic IS. features/MAP_OPTIONS.md's own framing - a live background
// is additive, most useful where there is signal - still holds, which is why
// this stacks over the archive rather than deleting it.
//
// Vector tiles carry the features instead of a picture of them, so the same
// bytes render sharp at every zoom, and every colour, weight and threshold
// below is ours to set. That is what makes "stylized for hiking" a real thing
// rather than a filter: what a hiker needs foregrounded (water, woodland,
// terrain shape, tracks and paths, named summits) is foregrounded, and what a
// road map would foreground is turned down or left out.
//
// THE SOURCE
//
// OpenFreeMap's public instance: OpenStreetMap data on the unmodified
// OpenMapTiles schema, no API key, no registration, no request cap, explicitly
// free for commercial use with attribution. That last part is why it is here
// and raw tile.openstreetmap.org is not - the OSMF tile policy warns that
// access to that server may be withdrawn from exactly this kind of app, and
// MAP_OPTIONS.md already ruled it out on those grounds.
//
// Attribution is a licence condition on both counts - ODbL for the data,
// OpenFreeMap's own terms for the hosting - so LIVE_TOPO_ATTRIBUTION is
// carried into the style and is not behind a prop.
//
// If the public instance ever becomes a problem (it is donation-funded and
// carries no SLA), OPENFREEMAP_TILEJSON is the single line to repoint: the
// schema is standard OpenMapTiles, so a self-hosted extract on the R2 bucket
// the pipeline already publishes to serves the same layer names, and nothing
// below this constant changes.

import type {
  LayerSpecification,
  SourceSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import {
  CONTOUR_ELEVATION_KEY,
  CONTOUR_LAYER,
  CONTOUR_LEVEL_KEY,
  CONTOUR_MAX_ZOOM,
  CONTOUR_SOURCE_ID,
  DEM_MAX_ZOOM,
  DEM_SOURCE_ID,
  ELEVATION_ATTRIBUTION,
  type ContourUnits,
  type TerrainUrls,
} from './terrain'

export const OPENFREEMAP_TILEJSON = 'https://tiles.openfreemap.org/planet'
export const OPENFREEMAP_GLYPHS =
  'https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf'

export const OSM_SOURCE_ID = 'osm'

export const LIVE_TOPO_ATTRIBUTION =
  'OpenFreeMap © OpenMapTiles · © OpenStreetMap contributors'

/**
 * One font, varied by size, colour and halo rather than by weight.
 *
 * A fontstack the glyph server does not have is a label layer that silently
 * renders nothing, and "Noto Sans Regular" is the one stack every OpenMapTiles
 * glyph endpoint ships. Reaching for a second weight would double the ways
 * that can go wrong to buy a distinction that halo and size already make.
 */
const FONT = ['Noto Sans Regular']

/**
 * A topographic sheet's palette, not a screen palette.
 *
 * Anchored on the design system's own tokens (tokens/colors.css) so the map
 * belongs to the same app as the chrome around it, but pulled toward what a
 * paper quad does: the sheet itself stays the paper the backdrop already
 * paints, ink is brown rather than black, woodland is a flat overprint rather
 * than a photograph of trees, and nothing competes with the blaze colours the
 * trail lines are drawn in. That last constraint is the real one - the trail
 * has to stay the most legible thing on the screen, so every colour here is
 * chosen to sit behind it.
 */
export const TOPO_PALETTE = {
  /** Woodland overprint - `--sage-100`, the same green family as the app. */
  wood: '#e3ecda',
  scrub: '#e9eedf',
  wetland: '#d9e4dd',
  rock: '#ece7dc',
  /** Protected land, drawn as a tint plus an edge rather than a solid block. */
  park: '#dfead6',
  parkEdge: '#96b98c',
  water: '#bcd8e6',
  waterEdge: '#7fb0c9',
  waterway: '#6ea3bf',
  /** Contours in USGS brown. Index lines are the same hue, darker and wider. */
  contour: '#b09168',
  contourIndex: '#8f6f47',
  contourLabel: '#7d6039',
  /** Roads: present, and deliberately quiet. */
  roadMajor: '#d8c9a8',
  roadMajorEdge: '#b7a382',
  roadMinor: '#e0d5bb',
  track: '#a89372',
  path: '#9a8a6e',
  boundary: '#9c8f78',
  label: '#4a4234',
  labelHalo: '#f7f3e9',
} as const

export const LIVE_TOPO_LAYER_IDS = {
  wood: 'topo-wood',
  scrub: 'topo-scrub',
  wetland: 'topo-wetland',
  rock: 'topo-rock',
  parkFill: 'topo-park-fill',
  parkEdge: 'topo-park-edge',
  hillshade: 'topo-hillshade',
  water: 'topo-water',
  waterway: 'topo-waterway',
  contour: 'topo-contour',
  contourIndex: 'topo-contour-index',
  contourLabel: 'topo-contour-label',
  roadMinor: 'topo-road-minor',
  roadMajorCasing: 'topo-road-major-casing',
  roadMajor: 'topo-road-major',
  track: 'topo-track',
  path: 'topo-path',
  boundary: 'topo-boundary',
  peak: 'topo-peak',
  waterLabel: 'topo-water-label',
  place: 'topo-place',
} as const

/** Shorthand for the OpenMapTiles `class` attribute test, used a dozen times. */
function isClass(...values: string[]): unknown[] {
  return values.length === 1
    ? ['==', ['get', 'class'], values[0]]
    : ['in', ['get', 'class'], ['literal', values]]
}

/**
 * The zoom each place class starts labelling at (#159).
 *
 * Distance decides what deserves ink, the way it does on a paper sheet. The
 * corridor-wide view crosses the whole Boston-Washington seaboard, and with
 * every class labelling at every zoom, that view was a wall of type the
 * centerline had to be picked out from under. So each class waits for the
 * zoom where its name starts meaning something to a hiker: a city anchors
 * the map from any distance, a town matters once a section is being planned,
 * a village once it is about to be walked past.
 *
 * Cities carry no threshold - orientation is their whole job, and the
 * corridor view without them is a line through unnamed country.
 */
export const PLACE_TOWN_MIN_ZOOM = 8
export const PLACE_VILLAGE_MIN_ZOOM = 11

export const PLACE_FILTER = [
  'step',
  ['zoom'],
  isClass('city'),
  PLACE_TOWN_MIN_ZOOM,
  isClass('city', 'town'),
  PLACE_VILLAGE_MIN_ZOOM,
  isClass('city', 'town', 'village'),
]

/**
 * Which label survives when two places collide: the bigger one.
 *
 * Lower sorts place first, and earlier placement wins the space - so without
 * this, whether Boston or a suburb's town label survives their collision is
 * decided by feature order inside the tile, which is nobody's decision. Same
 * reasoning as poiLayers.ts's POI_PRIORITY, one layer over.
 */
export const PLACE_SORT_KEY_EXPRESSION = [
  'match',
  ['get', 'class'],
  'city',
  0,
  'town',
  1,
  2,
]

export interface LiveTopoOptions {
  terrain: TerrainUrls
  units: ContourUnits
}

export function liveTopoSources({
  terrain,
}: LiveTopoOptions): Record<string, SourceSpecification> {
  return {
    [OSM_SOURCE_ID]: {
      type: 'vector',
      url: OPENFREEMAP_TILEJSON,
      attribution: LIVE_TOPO_ATTRIBUTION,
    },
    [DEM_SOURCE_ID]: {
      type: 'raster-dem',
      tiles: [terrain.demUrl],
      encoding: 'terrarium',
      tileSize: 256,
      maxzoom: DEM_MAX_ZOOM,
      attribution: ELEVATION_ATTRIBUTION,
    },
    [CONTOUR_SOURCE_ID]: {
      type: 'vector',
      tiles: [terrain.contourTilesUrl],
      maxzoom: CONTOUR_MAX_ZOOM,
      attribution: ELEVATION_ATTRIBUTION,
    },
  }
}

/**
 * The layer stack, bottom to top.
 *
 * The order is the cartography. Ground cover goes down first, then relief
 * shading over it so hillsides darken the green rather than sitting beside it,
 * then water flat on top so lakes read as level surfaces rather than shaded
 * ones, then contours over everything areal, then the linear network, then
 * type last so nothing is drawn through a label.
 *
 * There is deliberately no land-coloured fill at the bottom. The style's paper
 * backdrop already is the sheet, exactly as on a printed quad where open
 * ground is simply unprinted paper - and adding a source-free fill here would
 * paint over the off-archive hatch (backdrop.ts) even when no tile had loaded,
 * turning "nothing arrived" back into a confident picture of empty ground.
 */
export function liveTopoLayers({ units }: LiveTopoOptions): LayerSpecification[] {
  const elevationSuffix = units === 'imperial' ? "'" : 'm'

  return [
    {
      id: LIVE_TOPO_LAYER_IDS.wood,
      type: 'fill',
      source: OSM_SOURCE_ID,
      'source-layer': 'landcover',
      filter: isClass('wood') as never,
      paint: { 'fill-color': TOPO_PALETTE.wood },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.scrub,
      type: 'fill',
      source: OSM_SOURCE_ID,
      'source-layer': 'landcover',
      filter: isClass('grass') as never,
      paint: { 'fill-color': TOPO_PALETTE.scrub },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.wetland,
      type: 'fill',
      source: OSM_SOURCE_ID,
      'source-layer': 'landcover',
      filter: isClass('wetland') as never,
      paint: { 'fill-color': TOPO_PALETTE.wetland },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.rock,
      type: 'fill',
      source: OSM_SOURCE_ID,
      'source-layer': 'landcover',
      filter: isClass('rock', 'sand') as never,
      paint: { 'fill-color': TOPO_PALETTE.rock },
    },
    // Protected land is context a hiker plans with (where camping is allowed,
    // whose rules apply), so it gets an edge as well as a tint - a tint alone
    // disappears against woodland, which is what most of it is.
    {
      id: LIVE_TOPO_LAYER_IDS.parkFill,
      type: 'fill',
      source: OSM_SOURCE_ID,
      'source-layer': 'park',
      paint: { 'fill-color': TOPO_PALETTE.park, 'fill-opacity': 0.45 },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.parkEdge,
      type: 'line',
      source: OSM_SOURCE_ID,
      'source-layer': 'park',
      paint: {
        'line-color': TOPO_PALETTE.parkEdge,
        'line-width': 1,
        'line-dasharray': [4, 2],
      },
    },
    // Relief shading. Low opacity on purpose: this is here to give the terrain
    // shape, and anything stronger starts competing with the contours for the
    // same job while making the trail line harder to follow across a slope.
    {
      id: LIVE_TOPO_LAYER_IDS.hillshade,
      type: 'hillshade',
      source: DEM_SOURCE_ID,
      paint: {
        'hillshade-exaggeration': 0.35,
        'hillshade-shadow-color': '#6b5f4a',
        'hillshade-highlight-color': '#fffdf7',
        'hillshade-accent-color': '#8a8271',
      },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.water,
      type: 'fill',
      source: OSM_SOURCE_ID,
      'source-layer': 'water',
      // Swimming pools are in this layer too and are not a water source.
      filter: ['!=', ['get', 'class'], 'swimming_pool'] as never,
      paint: {
        'fill-color': TOPO_PALETTE.water,
        'fill-outline-color': TOPO_PALETTE.waterEdge,
      },
    },
    // Streams matter more to a hiker than lakes do - they are the refill
    // points - so they are drawn wide enough to follow, and intermittent ones
    // are dashed rather than hidden, because "sometimes dry" is information,
    // not an absence.
    {
      id: LIVE_TOPO_LAYER_IDS.waterway,
      type: 'line',
      source: OSM_SOURCE_ID,
      'source-layer': 'waterway',
      paint: {
        'line-color': TOPO_PALETTE.waterway,
        'line-width': [
          'interpolate',
          ['linear'],
          ['zoom'],
          9,
          ['case', isClass('river') as never, 1, 0.4],
          14,
          ['case', isClass('river') as never, 2.6, 1.2],
        ] as never,
        'line-opacity': ['case', ['==', ['get', 'intermittent'], 1], 0.6, 1] as never,
      },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.contour,
      type: 'line',
      source: CONTOUR_SOURCE_ID,
      'source-layer': CONTOUR_LAYER,
      filter: ['==', ['get', CONTOUR_LEVEL_KEY], 0] as never,
      paint: {
        'line-color': TOPO_PALETTE.contour,
        'line-width': 0.6,
        // Faded out where they would otherwise mat together into a solid
        // hillside, rather than switched off at a hard zoom threshold.
        'line-opacity': ['interpolate', ['linear'], ['zoom'], 10, 0, 12, 0.7] as never,
      },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.contourIndex,
      type: 'line',
      source: CONTOUR_SOURCE_ID,
      'source-layer': CONTOUR_LAYER,
      filter: ['>', ['get', CONTOUR_LEVEL_KEY], 0] as never,
      paint: {
        'line-color': TOPO_PALETTE.contourIndex,
        'line-width': 1.2,
        'line-opacity': ['interpolate', ['linear'], ['zoom'], 9, 0, 11, 0.9] as never,
      },
    },
    // Only index lines are labelled. Labelling every contour is what makes a
    // digital topo map unreadable - the number belongs on the line you count
    // from, not on the ones you count.
    {
      id: LIVE_TOPO_LAYER_IDS.contourLabel,
      type: 'symbol',
      source: CONTOUR_SOURCE_ID,
      'source-layer': CONTOUR_LAYER,
      filter: ['>', ['get', CONTOUR_LEVEL_KEY], 0] as never,
      minzoom: 12,
      layout: {
        'symbol-placement': 'line',
        'text-field': [
          'concat',
          ['to-string', ['get', CONTOUR_ELEVATION_KEY]],
          elevationSuffix,
        ] as never,
        'text-font': FONT,
        'text-size': 10,
        'text-max-angle': 25,
        'text-padding': 6,
        // Set into the line the way a printed contour label is, rather than
        // floating beside it.
        'symbol-spacing': 320,
      },
      paint: {
        'text-color': TOPO_PALETTE.contourLabel,
        'text-halo-color': TOPO_PALETTE.labelHalo,
        'text-halo-width': 1.4,
      },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.roadMinor,
      type: 'line',
      source: OSM_SOURCE_ID,
      'source-layer': 'transportation',
      filter: isClass('minor', 'service') as never,
      minzoom: 12,
      paint: {
        'line-color': TOPO_PALETTE.roadMinor,
        'line-width': ['interpolate', ['linear'], ['zoom'], 12, 0.8, 16, 3] as never,
      },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.roadMajorCasing,
      type: 'line',
      source: OSM_SOURCE_ID,
      'source-layer': 'transportation',
      filter: isClass('motorway', 'trunk', 'primary', 'secondary', 'tertiary') as never,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': TOPO_PALETTE.roadMajorEdge,
        'line-width': ['interpolate', ['linear'], ['zoom'], 8, 1.6, 16, 7] as never,
      },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.roadMajor,
      type: 'line',
      source: OSM_SOURCE_ID,
      'source-layer': 'transportation',
      filter: isClass('motorway', 'trunk', 'primary', 'secondary', 'tertiary') as never,
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': TOPO_PALETTE.roadMajor,
        'line-width': ['interpolate', ['linear'], ['zoom'], 8, 0.8, 16, 5] as never,
      },
    },
    // Tracks are how you reach most trailheads, and forest roads are a real
    // bail-out option, so they are drawn at their own weight rather than
    // lumped in with service roads.
    {
      id: LIVE_TOPO_LAYER_IDS.track,
      type: 'line',
      source: OSM_SOURCE_ID,
      'source-layer': 'transportation',
      filter: isClass('track') as never,
      minzoom: 11,
      paint: {
        'line-color': TOPO_PALETTE.track,
        'line-width': ['interpolate', ['linear'], ['zoom'], 11, 0.6, 16, 1.8] as never,
        'line-dasharray': [6, 3],
      },
    },
    // OSM paths, NOT the A.T. The trail comes from ATC data and is drawn by
    // style.ts in its blaze colours on top of this; these are the other
    // footpaths around it, which are exactly what the downloaded raster cannot
    // show and what a hiker looking for a side trail or a shortcut wants.
    // Dotted and quiet so they never read as a blazed route.
    {
      id: LIVE_TOPO_LAYER_IDS.path,
      type: 'line',
      source: OSM_SOURCE_ID,
      'source-layer': 'transportation',
      filter: isClass('path') as never,
      minzoom: 12,
      paint: {
        'line-color': TOPO_PALETTE.path,
        'line-width': 1,
        'line-dasharray': [2, 2],
        'line-opacity': 0.8,
      },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.boundary,
      type: 'line',
      source: OSM_SOURCE_ID,
      'source-layer': 'boundary',
      filter: ['<=', ['get', 'admin_level'], 4] as never,
      paint: {
        'line-color': TOPO_PALETTE.boundary,
        'line-width': 1,
        'line-dasharray': [3, 2, 1, 2],
        'line-opacity': 0.7,
      },
    },
    // Named summits with their height. This is the single most hiking-specific
    // thing OSM carries that a road basemap throws away, and on a ridge it is
    // how you confirm which bump you are standing on.
    {
      id: LIVE_TOPO_LAYER_IDS.peak,
      type: 'symbol',
      source: OSM_SOURCE_ID,
      'source-layer': 'mountain_peak',
      filter: isClass('peak', 'volcano') as never,
      minzoom: 10,
      layout: {
        // `concat` errors on a null argument and drops the feature, so the
        // name is coalesced rather than read straight: an unnamed summit with
        // a surveyed height is still worth putting on the map, and losing it
        // to an expression error would be a silent hole in exactly the layer
        // this style added terrain for.
        'text-field': [
          'case',
          ['has', units === 'imperial' ? 'ele_ft' : 'ele'],
          [
            'concat',
            ['coalesce', ['get', 'name'], ''],
            '\n',
            ['to-string', ['get', units === 'imperial' ? 'ele_ft' : 'ele']],
            elevationSuffix,
          ],
          ['coalesce', ['get', 'name'], ''],
        ] as never,
        'text-font': FONT,
        'text-size': ['interpolate', ['linear'], ['zoom'], 10, 10, 14, 13] as never,
        'text-anchor': 'top',
        'text-offset': [0, 0.4],
        'text-max-width': 8,
      },
      paint: {
        'text-color': TOPO_PALETTE.label,
        'text-halo-color': TOPO_PALETTE.labelHalo,
        'text-halo-width': 1.6,
      },
    },
    {
      id: LIVE_TOPO_LAYER_IDS.waterLabel,
      type: 'symbol',
      source: OSM_SOURCE_ID,
      'source-layer': 'water_name',
      minzoom: 11,
      layout: {
        'text-field': ['get', 'name'] as never,
        'text-font': FONT,
        'text-size': 11,
        'text-max-width': 8,
      },
      paint: {
        'text-color': '#3d6b81',
        'text-halo-color': TOPO_PALETTE.labelHalo,
        'text-halo-width': 1.4,
      },
    },
    // Towns only, and only the ones big enough to matter for resupply - a
    // hamlet label every half mile is noise on a trail map. The same rule
    // continues up the ladder by zoom (PLACE_FILTER): zoomed out far enough,
    // even a town is a hamlet.
    {
      id: LIVE_TOPO_LAYER_IDS.place,
      type: 'symbol',
      source: OSM_SOURCE_ID,
      'source-layer': 'place',
      filter: PLACE_FILTER as never,
      layout: {
        'text-field': ['get', 'name'] as never,
        'text-font': FONT,
        // The low stop matters most: at the corridor-wide view a city is an
        // orientation anchor, not a destination, and it is set smaller there
        // so the type never outweighs the line the view is about.
        'text-size': [
          'interpolate',
          ['linear'],
          ['zoom'],
          5,
          ['case', isClass('city') as never, 11, 9],
          8,
          ['case', isClass('city') as never, 13, 10],
          14,
          ['case', isClass('city') as never, 18, 13],
        ] as never,
        'text-max-width': 8,
        'symbol-sort-key': PLACE_SORT_KEY_EXPRESSION as unknown as number,
      },
      paint: {
        'text-color': TOPO_PALETTE.label,
        'text-halo-color': TOPO_PALETTE.labelHalo,
        'text-halo-width': 1.6,
      },
    },
  ]
}
