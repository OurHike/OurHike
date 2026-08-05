// Tests for viewerStyle.ts - the style must be the live sheet's real
// cartography over whichever local archives exist, and must never reference
// a source that does not.

import { describe, it, expect } from 'vitest'
import { buildViewerStyle, VIEWER_RASTER_LAYER_ID } from './viewerStyle'
import { LIVE_TOPO_LAYER_IDS, OSM_SOURCE_ID } from '../map/liveTopo'
import { CONTOUR_SOURCE_ID, DEM_SOURCE_ID } from '../map/terrain'

const BASEMAP_URL = 'pmtiles://viewer:basemap'
const DEM_URL = 'pmtiles://viewer:dem'
const RASTER_URL = 'pmtiles://viewer:raster'

function sourcesReferenced(style: ReturnType<typeof buildViewerStyle>): Set<string> {
  return new Set(
    style.layers
      .map((layer) => ('source' in layer ? layer.source : undefined))
      .filter((source): source is string => typeof source === 'string'),
  )
}

describe('buildViewerStyle', () => {
  it('with nothing dropped, paints only the paper backdrop', () => {
    const style = buildViewerStyle({})
    expect(Object.keys(style.sources)).toEqual([])
    expect(style.layers.map((l) => l.type)).toEqual(['background'])
  })

  it('every layer references a source the style actually declares', () => {
    for (const slots of [
      {},
      { basemap: BASEMAP_URL },
      { dem: DEM_URL },
      { raster: RASTER_URL },
      { basemap: BASEMAP_URL, dem: DEM_URL, raster: RASTER_URL },
    ]) {
      const style = buildViewerStyle(slots)
      for (const source of sourcesReferenced(style)) {
        expect(style.sources).toHaveProperty(source)
      }
    }
  })

  it('renders the live sheet layers over a dropped basemap', () => {
    const style = buildViewerStyle({ basemap: BASEMAP_URL })
    const ids = style.layers.map((l) => l.id)
    expect(ids).toContain(LIVE_TOPO_LAYER_IDS.wood)
    expect(ids).toContain(LIVE_TOPO_LAYER_IDS.place)
    expect(style.sources[OSM_SOURCE_ID]).toMatchObject({
      type: 'vector',
      url: BASEMAP_URL,
    })
    expect(style.glyphs).toBeDefined()
  })

  it('never emits contour layers - that plumbing is #187, and a dangling source is a style error', () => {
    const style = buildViewerStyle({ basemap: BASEMAP_URL, dem: DEM_URL })
    expect(sourcesReferenced(style)).not.toContain(CONTOUR_SOURCE_ID)
  })

  it('hillshade appears exactly when a DEM was dropped, declared terrarium', () => {
    const without = buildViewerStyle({ basemap: BASEMAP_URL })
    expect(without.layers.map((l) => l.id)).not.toContain(LIVE_TOPO_LAYER_IDS.hillshade)

    const withDem = buildViewerStyle({ basemap: BASEMAP_URL, dem: DEM_URL })
    expect(withDem.layers.map((l) => l.id)).toContain(LIVE_TOPO_LAYER_IDS.hillshade)
    expect(withDem.sources[DEM_SOURCE_ID]).toMatchObject({
      type: 'raster-dem',
      encoding: 'terrarium',
      tileSize: 256,
    })
  })

  it('a raster sheet draws under the vector layers, as the app stacks them', () => {
    const style = buildViewerStyle({ basemap: BASEMAP_URL, raster: RASTER_URL })
    const ids = style.layers.map((l) => l.id)
    expect(ids.indexOf(VIEWER_RASTER_LAYER_ID)).toBeLessThan(
      ids.indexOf(LIVE_TOPO_LAYER_IDS.wood),
    )
    // 512px declared, matching style.ts today - the viewer must show the
    // current rendering, blur included, or #191 cannot be judged against it.
    expect(style.sources['viewer-raster']).toMatchObject({ tileSize: 512 })
  })
})
