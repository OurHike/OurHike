// Elevation: the hillshade and the contour lines, both from one DEM.
//
// This is the half of the live background that makes it a TOPOGRAPHIC map
// rather than a road map with trees on it. Contours and relief shading are the
// two things a hiker actually reads terrain from, and neither exists in OSM
// vector data - they have to come from a digital elevation model.
//
// WHY GENERATE CONTOURS IN THE CLIENT RATHER THAN SHIP THEM
//
// The obvious alternative is to bake contour lines into the pipeline the way
// the topo raster already is. That was rejected for the same reason
// export_pmtiles.py's raster is being demoted in the first place: a baked
// contour is a picture of one interval at one scale. Generating them here from
// raw elevation means the interval can follow the zoom, follow the hiker's
// unit preference (a US topo map is read in feet; the same DEM in metric wants
// 10m/50m), and be restyled without a pipeline run - and it costs no storage
// and no extra download, because the DEM tiles are fetched for the hillshade
// anyway.
//
// That last point is the reason both layers share ONE DemSource. maplibre-
// contour exposes `sharedDemProtocolUrl` precisely so the hillshade and the
// contour generator read the same decoded tiles out of one cache instead of
// each pulling its own copy - halving the network for the most bandwidth-
// expensive part of the background.
//
// THE DATA
//
// AWS Terrain Tiles (`elevation-tiles-prod`), an AWS Open Data registry
// dataset: no key, no registration, plain S3, and over the Appalachian Trail
// specifically it is derived from USGS 3DEP - the same survey the app already
// credits for the elevation profile. Attribution is a condition of use
// (tilezen/joerd's attribution doc), which is why ELEVATION_ATTRIBUTION below
// is not optional and is carried into the style's own attribution string.
//
// It is Open Data, not a product with an SLA - so every failure path here is a
// missing layer, never a broken map. A DEM that will not load costs contours
// and shading; the paper backdrop, the trail lines and the downloaded corridor
// raster are all unaffected.
//
// This module is the CONFIGURATION half only, and deliberately imports
// nothing: style.ts and liveTopo.ts read these constants to build a style, and
// making them pay for maplibre-contour (and through it a Web Worker and a blob
// URL) to know what a contour interval is would put a runtime dependency
// behind every style test. contours.ts is the other half - the protocol
// registration that turns these numbers into live tiles - and the split is the
// same one pmtilesSource.ts and protocol.ts already draw.

/** AWS Open Data, us-east-1. Terrarium encoding, 256px tiles. */
export const DEM_TILE_URL =
  'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'

/**
 * The deepest zoom fetched from the DEM, deliberately below the dataset's own
 * z15.
 *
 * Contour generation reads a tile plus its eight neighbours, so the request
 * count grows fast with zoom for detail the source cannot really back: over
 * the AT the terrarium tiles come from 3DEP at roughly 10m, which z13 already
 * resolves. Past this the contour source overzooms and subsamples instead,
 * which keeps the lines smooth without pulling four times the tiles for the
 * same underlying measurements.
 */
export const DEM_MAX_ZOOM = 13

/** Contours may be drawn past {@link DEM_MAX_ZOOM} by overzooming the DEM. */
export const CONTOUR_MAX_ZOOM = 15

export const DEM_SOURCE_ID = 'dem'
export const CONTOUR_SOURCE_ID = 'contours'

/** The vector-tile layer name contour lines arrive in, and the feature keys on
 *  them. Style layers filter on `level`, so these have to agree exactly. */
export const CONTOUR_LAYER = 'contours'
export const CONTOUR_ELEVATION_KEY = 'ele'
export const CONTOUR_LEVEL_KEY = 'level'

/** Required by the dataset's terms - see the note at the top of this file. */
export const ELEVATION_ATTRIBUTION = 'Elevation: USGS 3DEP via AWS Terrain Tiles'

export type ContourUnits = 'imperial' | 'metric'

/** Exported for contours.ts, which applies it - see CONTOUR_THRESHOLDS. */
export const METRES_TO_FEET = 3.28084

/**
 * Contour intervals as `[minor, index]` per zoom, in the displayed unit.
 *
 * Read against a USGS 7.5-minute quad rather than picked for looks: the
 * Appalachians are mapped at a 20ft interval with every fifth line indexed at
 * 100ft, which is what the deepest zooms here reproduce. Zooming out, an
 * interval that fine turns a mountainside into a solid block of ink, so the
 * interval coarsens with the zoom - the standard cartographic answer, and the
 * reason a single baked interval could never be right at both ends.
 *
 * A zoom with no entry inherits the next lower one, so only the changes are
 * listed.
 */
export const CONTOUR_THRESHOLDS: Record<
  ContourUnits,
  Record<number, [number, number]>
> = {
  imperial: {
    9: [500, 2000],
    11: [200, 1000],
    12: [100, 500],
    13: [40, 200],
    14: [20, 100],
  },
  metric: {
    9: [200, 1000],
    11: [100, 500],
    12: [50, 250],
    13: [10, 50],
    14: [10, 50],
  },
}

export interface TerrainUrls {
  /** `raster-dem` source URL, served from the shared decoded-tile cache. */
  demUrl: string
  /** Vector-tile URL template producing contour lines on the fly. */
  contourTilesUrl: string
}
