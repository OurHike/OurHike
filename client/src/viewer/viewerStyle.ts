// Composes the viewer's MapLibre style from whichever archives have been
// dropped (issue #202).
//
// The whole point of this page over pmtiles.io is that it renders with the
// REAL cartography: the live topo sheet's own palette and layer stack
// (liveTopo.ts), fed from local archives instead of the network - so what a
// reviewer judges is what would ship. The layers are liveTopoLayers'
// verbatim output with two subtractions, each an absence of input rather
// than a restyle:
//
//   contours   the app generates these from the DEM the offline store
//              holds (contours.ts + demWorker.ts, #187) - a pipeline this
//              page deliberately does not run, because its DEM is whatever
//              file was just dropped, not the store's package. Contour
//              layers would therefore reference a source nothing fills,
//              which MapLibre treats as a style error - so they are
//              filtered out, not hidden.
//   hillshade  only when a DEM has actually been dropped, for the same
//              reason.
//
// Glyphs come from the app's own bundle (#188): the viewer rides the same
// origin as the app, so the ranges shipped under public/glyphs/ serve this
// page too, and its labels render from the same bytes a hiker's would.

import type {
  LayerSpecification,
  StyleSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import { MAP_BACKGROUND_COLOR } from '../map/style'
import { BUNDLED_GLYPHS, LIVE_TOPO_ATTRIBUTION, liveTopoLayers } from '../map/liveTopo'
import {
  CONTOUR_SOURCE_ID,
  DEM_SOURCE_ID,
  ELEVATION_ATTRIBUTION,
  type ContourUnits,
} from '../map/terrain'
import { OSM_SOURCE_ID } from '../map/liveTopo'

export interface ViewerSlots {
  /** pmtiles:// URLs per dropped archive kind - see viewerArchives.ts. */
  basemap?: string
  dem?: string
  raster?: string
}

export const VIEWER_RASTER_LAYER_ID = 'viewer-raster-sheet'

/**
 * The raster sheet draws under the vector layers, exactly where style.ts
 * puts the downloaded archive under the live sheet - so dropping the USGS
 * background plus the vector basemap previews the real stacking, not an
 * arrangement invented here.
 */
export function buildViewerStyle(
  slots: ViewerSlots,
  units: ContourUnits = 'imperial',
): StyleSpecification {
  const sources: StyleSpecification['sources'] = {}
  const layers: LayerSpecification[] = [
    {
      id: 'viewer-backdrop',
      type: 'background',
      paint: { 'background-color': MAP_BACKGROUND_COLOR },
    },
  ]

  if (slots.raster !== undefined) {
    sources['viewer-raster'] = {
      type: 'raster',
      url: slots.raster,
      // Mirrors the app's declaration (style.ts, the @2x convention since
      // #191): the viewer's whole point is showing what would ship, so its
      // presentation must move with the app's - a dropped archive judged
      // here at 512 would look blurrier than the same bytes in the app.
      tileSize: 256,
      attribution: 'USGS US Topo',
    }
    layers.push({ id: VIEWER_RASTER_LAYER_ID, type: 'raster', source: 'viewer-raster' })
  }

  if (slots.basemap !== undefined) {
    sources[OSM_SOURCE_ID] = {
      type: 'vector',
      url: slots.basemap,
      attribution: LIVE_TOPO_ATTRIBUTION,
    }
  }

  if (slots.dem !== undefined) {
    sources[DEM_SOURCE_ID] = {
      type: 'raster-dem',
      url: slots.dem,
      // Wrong or missing encoding is silently wrong elevations - the same
      // gotcha #187 documents for the app's own wiring.
      encoding: 'terrarium',
      tileSize: 256,
      attribution: ELEVATION_ATTRIBUTION,
    }
  }

  const wanted = liveTopoLayers({
    // liveTopoLayers only reads `units`; the terrain URLs live in sources it
    // does not build. Spelled as a full TerrainUrls anyway so a future read
    // of these fields fails loudly in tests rather than rendering nothing.
    terrain: { demUrl: '', contourTilesUrl: '' },
    units,
  }).filter((layer) => {
    const source = 'source' in layer ? layer.source : undefined
    if (source === CONTOUR_SOURCE_ID) return false
    if (source === DEM_SOURCE_ID) return slots.dem !== undefined
    if (source === OSM_SOURCE_ID) return slots.basemap !== undefined
    return true
  })
  layers.push(...wanted)

  return {
    version: 8,
    ...(slots.basemap !== undefined ? { glyphs: BUNDLED_GLYPHS } : {}),
    sources,
    layers,
  }
}
