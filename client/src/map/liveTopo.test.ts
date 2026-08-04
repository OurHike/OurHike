import { describe, it, expect } from 'vitest'
import {
  createExpression,
  featureFilter,
  latest,
  validateStyleMin,
} from '@maplibre/maplibre-gl-style-spec'
import { buildMapStyle, ATTRIBUTION, TOPO_LAYER_ID, BACKDROP_LAYER_ID } from './style'
import {
  LIVE_TOPO_ATTRIBUTION,
  LIVE_TOPO_LAYER_IDS,
  OPENFREEMAP_GLYPHS,
  OPENFREEMAP_TILEJSON,
  OSM_SOURCE_ID,
  PLACE_TOWN_MIN_ZOOM,
  PLACE_VILLAGE_MIN_ZOOM,
  liveTopoLayers,
} from './liveTopo'
import {
  CONTOUR_LEVEL_KEY,
  CONTOUR_SOURCE_ID,
  DEM_SOURCE_ID,
  ELEVATION_ATTRIBUTION,
} from './terrain'
import { POI_LAYER_ID } from './poiLayers'

// The live background exists because a raster mosaic of pre-rendered US Topo
// quads cannot be restyled, cannot be read at a zoom it was not drawn for, and
// stops at the edge of the downloaded corridor. What is asserted here is the
// part of that fix which is checkable without a GPU: that the style is really
// a valid MapLibre style, that it is really OUR cartography rather than a
// vendor's, that the licences it pulls in are credited, and - the one that
// matters on a ridge - that turning it on cannot cost the offline map.

const TERRAIN = {
  demUrl: 'dem://shared/{z}/{x}/{y}',
  contourTilesUrl: 'contour://40ft/{z}/{x}/{y}',
}

function live(units: 'imperial' | 'metric' = 'imperial') {
  return buildMapStyle({
    topoArchiveUrl: 'pmtiles://ourhike-corridor',
    trailsUrl: '/data/trails.geojson',
    background: 'hiking_topo_live',
    terrain: TERRAIN,
    units,
  })
}

function offline() {
  return buildMapStyle({
    topoArchiveUrl: 'pmtiles://ourhike-corridor',
    trailsUrl: '/data/trails.geojson',
    background: 'usgs_topo_offline',
    terrain: TERRAIN,
  })
}

function ids(style: ReturnType<typeof live>) {
  return style.layers.map((layer) => layer.id)
}

describe('the live topographic background', () => {
  it('is a valid MapLibre style according to MapLibre’s own spec validator', () => {
    // Twenty-odd hand-written layers of filters and interpolate expressions -
    // exactly the kind of thing that type-checks and then silently renders
    // nothing. This is the only check that reads them the way MapLibre will.
    expect(validateStyleMin(live())).toEqual([])
  })

  it('is still valid in metric, where every threshold and label changes', () => {
    expect(validateStyleMin(live('metric'))).toEqual([])
  })

  it('draws OpenStreetMap through our own layers, not a vendor’s ready-made style', () => {
    // The whole point of taking vector tiles rather than someone's rendered
    // basemap: if this ever became a hosted style URL, "stylized for hiking"
    // would stop being true and nothing else in this file would notice.
    const source = live().sources[OSM_SOURCE_ID]

    expect(source).toMatchObject({ type: 'vector', url: OPENFREEMAP_TILEJSON })
    expect(ids(live()).filter((id) => id.startsWith('topo-')).length).toBeGreaterThan(10)
  })

  it('keeps the downloaded archive in the style, underneath the live sheet', () => {
    // The offline guarantee, asserted as an ordering rather than a promise.
    // With no signal the live layers draw nothing and the archive shows
    // through, which is why turning this on costs a hiker nothing.
    const order = ids(live())

    expect(order).toContain(TOPO_LAYER_ID)
    expect(order.indexOf(TOPO_LAYER_ID)).toBeLessThan(
      order.indexOf(LIVE_TOPO_LAYER_IDS.wood),
    )
  })

  it('keeps the paper backdrop at the very bottom, under the live sheet too', () => {
    expect(ids(live())[0]).toBe(BACKDROP_LAYER_ID)
  })

  it('adds no source-free fill of its own, so the off-archive hatch survives', () => {
    // A land-coloured `background` layer here would paint over backdrop.ts's
    // hatch even when no tile had loaded - turning "nothing arrived" back into
    // a confident picture of empty ground, which is the exact lie that hatch
    // exists to prevent.
    const backgrounds = live().layers.filter((layer) => layer.type === 'background')

    expect(backgrounds.map((layer) => layer.id)).toEqual([BACKDROP_LAYER_ID])
  })

  it('shades relief and draws contours from one shared DEM, not two downloads', () => {
    const style = live()

    expect(style.sources[DEM_SOURCE_ID]).toMatchObject({
      type: 'raster-dem',
      tiles: [TERRAIN.demUrl],
      encoding: 'terrarium',
    })
    expect(style.sources[CONTOUR_SOURCE_ID]).toMatchObject({
      type: 'vector',
      tiles: [TERRAIN.contourTilesUrl],
    })
  })

  it('separates index contours from minor ones, and labels only the index lines', () => {
    // Labelling every contour is what makes a digital topo map unreadable -
    // the number belongs on the line you count from, not the ones you count.
    const byId = (id: string) =>
      liveTopoLayers({ terrain: TERRAIN, units: 'imperial' }).find(
        (layer) => layer.id === id,
      ) as { filter?: unknown }

    expect(byId(LIVE_TOPO_LAYER_IDS.contourLabel).filter).toEqual([
      '>',
      ['get', CONTOUR_LEVEL_KEY],
      0,
    ])
    expect(byId(LIVE_TOPO_LAYER_IDS.contour).filter).toEqual([
      '==',
      ['get', CONTOUR_LEVEL_KEY],
      0,
    ])
  })

  it('labels summits and contours in feet, and in metres when asked', () => {
    const feet = JSON.stringify(live().layers)
    const metres = JSON.stringify(live('metric').layers)

    expect(feet).toContain('ele_ft')
    expect(metres).not.toContain('ele_ft')
  })

  it('draws the trail and the pins over every background layer, never under one', () => {
    // The blazes are the reason the map exists and a pin buried under the
    // hillshade is a POI the hiker cannot see; a background layer on top of
    // either would be a regression no amount of cartography makes up for.
    // Worth asserting against the whole live stack rather than one layer,
    // since the stack is where a new layer would get appended by mistake.
    const order = ids(live())
    const lastBackground = Math.max(
      ...Object.values(LIVE_TOPO_LAYER_IDS).map((id) => order.indexOf(id)),
    )

    expect(lastBackground).toBeLessThan(order.indexOf('trail-casing'))
    expect(lastBackground).toBeLessThan(order.indexOf(POI_LAYER_ID))
  })

  it('keeps the POI pins last of all, so they win collisions against our labels', () => {
    // Not only about what draws on top. The live sheet added four SYMBOL
    // layers (peak, place, water and contour labels) to a style that had none,
    // and MapLibre declutters symbols across the whole style, not per layer -
    // so those labels and the pins now compete for the same space.
    //
    // Which one loses is decided by layer order, and in a direction worth
    // checking rather than assuming: PauseablePlacement starts at
    // `order.length - 1` and decrements, so placement runs TOP-DOWN and the
    // last layer has priority. Pins last therefore means a contour label can
    // never suppress a water source - which is the way round it has to be,
    // since water is the most safety-relevant thing on this map.
    //
    // Move this layer and that guarantee is silently gone, which is why it is
    // asserted rather than left to the ordering in buildMapStyle.
    const order = ids(live())

    expect(order[order.length - 1]).toBe(POI_LAYER_ID)
  })

  it('credits every licence the live sheet pulls in', () => {
    // ODbL for the data, OpenFreeMap's terms for the hosting, and the AWS
    // Terrain Tiles attribution requirement for the elevation. All three are
    // conditions of use, not courtesies.
    const style = live()

    expect(style.sources[OSM_SOURCE_ID]).toHaveProperty(
      'attribution',
      LIVE_TOPO_ATTRIBUTION,
    )
    expect(style.sources[DEM_SOURCE_ID]).toHaveProperty(
      'attribution',
      ELEVATION_ATTRIBUTION,
    )
    expect(LIVE_TOPO_ATTRIBUTION).toContain('OpenStreetMap')
  })

  it('declares a glyph endpoint, without which every label silently vanishes', () => {
    expect(live().glyphs).toBe(OPENFREEMAP_GLYPHS)
  })
})

describe('place labels, by distance', () => {
  // The corridor-wide view crosses the Boston-Washington seaboard. With
  // cities, towns and villages all labelling at every zoom, that view was a
  // wall of type the centerline had to be picked out from under (#159) - so
  // each class waits for the zoom where its name starts meaning something,
  // and both rules below are evaluated through MapLibre's own engines
  // rather than read back off the arrays, since what is under test is what
  // renders, not the shape of an expression.

  function placeLayer() {
    const found = liveTopoLayers({ terrain: TERRAIN, units: 'imperial' }).find(
      (layer) => layer.id === LIVE_TOPO_LAYER_IDS.place,
    )
    if (found === undefined || found.type !== 'symbol') {
      throw new Error('no symbol place layer in the live sheet')
    }
    return found
  }

  /** Whether one place class labels at one zoom, per the layer's filter. */
  function labelled(zoom: number, placeClass: string): boolean {
    const compiled = featureFilter(placeLayer().filter as never, 'layers[0].filter')
    return compiled.filter(
      { zoom } as never,
      { type: 1, properties: { class: placeClass }, geometry: [] } as never,
    )
  }

  /** Which of two colliding labels is placed first (lower wins the space). */
  function sortKey(placeClass: string): number {
    const layout = placeLayer().layout as Record<string, unknown>
    const compiled = createExpression(
      layout['symbol-sort-key'] as never,
      latest.layout_symbol['symbol-sort-key'] as never,
    )
    if (compiled.result === 'error') {
      throw new Error('symbol-sort-key on the place layer is not a valid expression')
    }
    return compiled.value.evaluate(
      { zoom: 9 } as never,
      { properties: { class: placeClass } } as never,
    )
  }

  it('labels only cities on the corridor-wide view, as anchors', () => {
    for (const zoom of [4, PLACE_TOWN_MIN_ZOOM - 1]) {
      expect(labelled(zoom, 'city')).toBe(true)
      expect(labelled(zoom, 'town')).toBe(false)
      expect(labelled(zoom, 'village')).toBe(false)
    }
  })

  it('lets towns in at section-planning zooms, and villages only close up', () => {
    expect(labelled(PLACE_TOWN_MIN_ZOOM, 'town')).toBe(true)
    expect(labelled(PLACE_VILLAGE_MIN_ZOOM - 1, 'village')).toBe(false)
    expect(labelled(PLACE_VILLAGE_MIN_ZOOM, 'village')).toBe(true)
  })

  it('never labels a hamlet, at any rung of the ladder', () => {
    // The ladder admits classes by zoom; it must not widen the class list on
    // the way. A hamlet label every half mile is noise on a trail map.
    for (const zoom of [4, PLACE_TOWN_MIN_ZOOM, PLACE_VILLAGE_MIN_ZOOM, 14]) {
      expect(labelled(zoom, 'hamlet')).toBe(false)
    }
  })

  it('hands a colliding pair to the bigger place, not to tile feature order', () => {
    // Lower sorts place first, and earlier placement wins the space -
    // whether Boston or a suburb survives their collision is a decision,
    // not an accident of feature order inside the tile.
    expect(sortKey('city')).toBeLessThan(sortKey('town'))
    expect(sortKey('town')).toBeLessThan(sortKey('village'))
  })
})

describe('the offline-only background', () => {
  it('adds no live source, so choosing it really does stay off the network', () => {
    const style = offline()

    expect(Object.keys(style.sources)).not.toContain(OSM_SOURCE_ID)
    expect(Object.keys(style.sources)).not.toContain(DEM_SOURCE_ID)
    expect(Object.keys(style.sources)).not.toContain(CONTOUR_SOURCE_ID)
  })

  it('declares no glyph endpoint either - an unused font host is still a host', () => {
    expect(offline().glyphs).toBeUndefined()
  })

  it('credits only what it actually draws', () => {
    expect(offline().sources.trails).toHaveProperty('attribution', ATTRIBUTION)
  })

  it('still draws the archive, the trail and the pins, which is the whole map', () => {
    // Exhaustive on purpose: the point of this one is that choosing the
    // offline background subtracts the live layers and NOTHING else. An
    // `toContain` here would pass just as happily if the trail or the pins
    // went missing with them.
    expect(ids(offline())).toEqual([
      BACKDROP_LAYER_ID,
      TOPO_LAYER_ID,
      'trail-casing',
      'trail-blaze',
      POI_LAYER_ID,
    ])
  })
})

describe('a live background with no terrain registered', () => {
  // registerTerrain() is best-effort in MapView - a browser with no Worker, or
  // a blob URL a CSP refuses, leaves it undefined. The style has to survive
  // that rather than reference sources that resolve to nothing.
  const degraded = buildMapStyle({
    topoArchiveUrl: 'pmtiles://ourhike-corridor',
    trailsUrl: '/data/trails.geojson',
    background: 'hiking_topo_live',
  })

  it('falls all the way back to the offline map rather than a broken style', () => {
    expect(validateStyleMin(degraded)).toEqual([])
    expect(ids(degraded)).not.toContain(LIVE_TOPO_LAYER_IDS.hillshade)
    expect(ids(degraded)).toContain(TOPO_LAYER_ID)
  })
})
