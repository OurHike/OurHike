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
//   contours   client-side contour generation from a local DEM is #187's
//              plumbing (maplibre-contour's worker-import route). Until it
//              lands, contour layers would reference a source that does not
//              exist, which MapLibre treats as a style error - so they are
//              filtered out, not hidden.
//   hillshade  only when a DEM has actually been dropped, for the same
//              reason.
//
// Glyphs stay on the network. The viewer is a reviewer tool that runs where
// there is connectivity (a PR preview, a dev server); bundling glyphs for
// offline labels is the app's own #188, not this page's problem.

import type {
  LayerSpecification,
  StyleSpecification,
} from '@maplibre/maplibre-gl-style-spec'
import { MAP_BACKGROUND_COLOR } from '../map/style'
import {
  LIVE_TOPO_ATTRIBUTION,
  OPENFREEMAP_GLYPHS,
  liveTopoLayers,
} from '../map/liveTopo'
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
      // The shipped archives are 512px tiles and the app declares them the
      // same way (style.ts) - the viewer must show today's rendering, blur
      // included, or it cannot be used to judge #191's fixes against it.
      tileSize: 512,
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
    ...(slots.basemap !== undefined ? { glyphs: OPENFREEMAP_GLYPHS } : {}),
    sources,
    layers,
  }
}
