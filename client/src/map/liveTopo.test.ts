import { describe, it, expect } from 'vitest'
import {
  createExpression,
  featureFilter,
  latest,
  validateStyleMin,
} from '@maplibre/maplibre-gl-style-spec'
import { buildMapStyle, TOPO_LAYER_ID, BACKDROP_LAYER_ID } from './style'
import { OSM_CREDIT } from './credits'
import {
  HILLSHADE_EXAGGERATION,
  HILLSHADE_HANDOVER_END_ZOOM,
  HILLSHADE_HANDOVER_START_ZOOM,
  HILLSHADE_RELIEF_ONLY_EXAGGERATION,
  BASEMAP_MAX_ZOOM,
  BASEMAP_SCHEME,
  BASEMAP_TILES_URL,
  BUNDLED_GLYPHS,
  LIVE_TOPO_ATTRIBUTION,
  LIVE_TOPO_LAYER_IDS,
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
import { WARNING_LAYER_ID } from './warningLayers'
import { CLOSURE_CASING_LAYER_ID, CLOSURE_LAYER_ID } from '../lib/closureStyle'

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

    expect(source).toMatchObject({ type: 'vector', tiles: [BASEMAP_TILES_URL] })
    expect(ids(live()).filter((id) => id.startsWith('topo-')).length).toBeGreaterThan(10)
  })

  it('asks for its tiles through the local-first basemap scheme (#189)', () => {
    // The template is the offline story: basemap.ts answers each request
    // from the downloaded package and falls through to the network per
    // tile, so the style never has to know which one a hiker holds. A
    // network URL here - TileJSON or tile template alike - would put a
    // round trip back in front of the first tile and make the archive
    // unreachable, which is exactly the coupling #189 removes.
    const source = live().sources[OSM_SOURCE_ID] as { tiles?: string[]; url?: string }

    expect(source.url).toBeUndefined()
    expect(source.tiles).toEqual([BASEMAP_TILES_URL])
    expect(BASEMAP_TILES_URL.startsWith(`${BASEMAP_SCHEME}://`)).toBe(true)
    expect(BASEMAP_TILES_URL).not.toMatch(/^https?:/)
    // Without a TileJSON nothing else says where overzooming starts, and a
    // source with no maxzoom would fetch z15+ tiles that neither the
    // package nor OpenFreeMap has.
    expect(source).toMatchObject({ maxzoom: BASEMAP_MAX_ZOOM })
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

  it('adds no source-free fill of its own, so the off-archive paper survives', () => {
    // A land-coloured `background` layer here would paint over the paper
    // backdrop even when no tile had loaded - turning "nothing arrived" back
    // into a confident picture of empty ground, which is the exact lie that
    // backdrop exists to prevent.
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

  it('keeps our own pins last of all, so they win collisions against our labels', () => {
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
    // The serious-warning pins sit above the waypoints, which is the same rule
    // applied one level further in: the only symbol on this map a moderator had
    // to escalate by hand outranks the ones the pipeline published. It does not
    // NEED the ordering - map/warningLayers.ts sets `icon-allow-overlap`, so it
    // is never dropped whatever it competes with - but a warning drawn
    // underneath a shelter pin is as unread as one that was decluttered away.
    //
    // Move either layer and both guarantees are silently gone, which is why
    // this is asserted rather than left to the ordering in buildMapStyle.
    const order = ids(live())

    expect(order.slice(-2)).toEqual([POI_LAYER_ID, WARNING_LAYER_ID])
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
    expect(live().glyphs).toBe(BUNDLED_GLYPHS)
  })

  it('serves glyphs from its own origin, so labels survive airplane mode (#188)', () => {
    // Glyph PBFs are fetched per 256-glyph range at runtime, and nothing
    // offline intercepts font requests - the pmtiles protocol only covers
    // tile sources. A host in this URL is therefore every label on the sheet
    // going blank without signal. Same-origin means the bundled ranges under
    // public/glyphs/ answer instead, from the service worker's precache.
    expect(BUNDLED_GLYPHS).not.toMatch(/^https?:/)
    expect(BUNDLED_GLYPHS.startsWith('/')).toBe(true)
    // MapLibre substitutes these two tokens itself; without them the template
    // is a single URL every range request hits in vain.
    expect(BUNDLED_GLYPHS).toContain('{fontstack}')
    expect(BUNDLED_GLYPHS).toContain('{range}')
  })
})

describe('relief shading, by zoom', () => {
  // The opening view is the whole trail - App.tsx frames CORRIDOR_BOUNDS,
  // which lands near z4 - and at that zoom every other terrain layer in this
  // sheet is switched off: both contour layers are at zero opacity, their
  // labels start at 12, the peaks at 10, and OpenMapTiles carries no woodland
  // to fill below roughly z7. The hillshade is the entire background there, so
  // what is asserted is that it is actually turned up enough to be one - read
  // through MapLibre's own expression engine, since what matters is the number
  // that reaches the shader rather than the shape of an array.

  /** A paint value as MapLibre will really compute it at a given zoom. */
  function paintAt(layerId: string, property: string, spec: unknown, zoom: number) {
    const layer = liveTopoLayers({ terrain: TERRAIN, units: 'imperial' }).find(
      (candidate) => candidate.id === layerId,
    ) as { paint?: Record<string, unknown> } | undefined
    const compiled = createExpression(layer?.paint?.[property] as never, spec as never)
    if (compiled.result === 'error') {
      throw new Error(`${layerId}'s ${property} is not a valid expression`)
    }
    return compiled.value.evaluate({ zoom } as never) as number
  }

  const exaggerationAt = (zoom: number) =>
    paintAt(
      LIVE_TOPO_LAYER_IDS.hillshade,
      'hillshade-exaggeration',
      latest.paint_hillshade['hillshade-exaggeration'],
      zoom,
    )

  const contourInkAt = (zoom: number) =>
    Math.max(
      paintAt(
        LIVE_TOPO_LAYER_IDS.contour,
        'line-opacity',
        latest.paint_line['line-opacity'],
        zoom,
      ),
      paintAt(
        LIVE_TOPO_LAYER_IDS.contourIndex,
        'line-opacity',
        latest.paint_line['line-opacity'],
        zoom,
      ),
    )

  it('carries the corridor-wide opening view on its own', () => {
    // The bug this fixes: at the old flat 0.35, stretched over a thousand
    // kilometres of DEM, the first thing anyone saw on opening the app was
    // blank paper with a scale bar on it.
    expect(exaggerationAt(4)).toBe(HILLSHADE_RELIEF_ONLY_EXAGGERATION)
    expect(exaggerationAt(HILLSHADE_HANDOVER_START_ZOOM)).toBe(
      HILLSHADE_RELIEF_ONLY_EXAGGERATION,
    )
  })

  it('hands back to its old weight once the contours are drawing', () => {
    // Hiking zooms are deliberately untouched: anything stronger there starts
    // competing with the contours for the same job and makes the trail line
    // harder to follow across a slope.
    expect(exaggerationAt(HILLSHADE_HANDOVER_END_ZOOM)).toBe(HILLSHADE_EXAGGERATION)
    expect(exaggerationAt(14)).toBe(HILLSHADE_EXAGGERATION)
  })

  it('eases between the two rather than switching at a threshold', () => {
    const midway = exaggerationAt(
      (HILLSHADE_HANDOVER_START_ZOOM + HILLSHADE_HANDOVER_END_ZOOM) / 2,
    )

    expect(midway).toBeLessThan(HILLSHADE_RELIEF_ONLY_EXAGGERATION)
    expect(midway).toBeGreaterThan(HILLSHADE_EXAGGERATION)
  })

  it('hands over across exactly the window the contours fade in over', () => {
    // The handover zooms are not free numbers - they are the contour ramps'
    // own, and the whole argument for turning the shading up is that nothing
    // else is drawing terrain yet. Asserted against those ramps so the two
    // cannot drift apart into a window with no terrain in it at all, or one
    // where full-strength shading sits under full-strength contours.
    expect(contourInkAt(HILLSHADE_HANDOVER_START_ZOOM)).toBe(0)
    expect(contourInkAt(HILLSHADE_HANDOVER_END_ZOOM)).toBeGreaterThan(0.5)
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

  it('declares no glyph endpoint either, having no symbol layer to feed', () => {
    // The endpoint is app-origin now (#188), so this is no longer about a
    // needless host - just that a style declares what its layers actually use.
    expect(offline().glyphs).toBeUndefined()
  })

  it('credits only what it actually draws', () => {
    expect(offline().sources.trails).toHaveProperty('attribution', OSM_CREDIT)
  })

  it('still draws the archive, the trail, the closures and the pins', () => {
    // Exhaustive on purpose: the point of this one is that choosing the
    // offline background subtracts the live layers and NOTHING else. An
    // `toContain` here would pass just as happily if the trail or the pins
    // went missing with them - and the safety layers below are exactly the
    // ones that must survive it, since a hiker on the offline background is a
    // hiker with no signal, which is where a closure matters most.
    expect(ids(offline())).toEqual([
      BACKDROP_LAYER_ID,
      TOPO_LAYER_ID,
      'trail-casing',
      'trail-blaze',
      CLOSURE_CASING_LAYER_ID,
      CLOSURE_LAYER_ID,
      POI_LAYER_ID,
      WARNING_LAYER_ID,
    ])
  })
})

describe('a live background with no terrain registered', () => {
  // registerTerrain() is best-effort in MapView - today only a CSP refusing a
  // blob-backed Worker actually gets here - and it leaves `terrain` undefined.
  //
  // What that used to cost is the bug this block now pins. The style dropped
  // the ENTIRE live sheet, so a hiker with nothing downloaded had an empty
  // archive under a paper backdrop and nothing else: a blank cream screen.
  // Elevation is one input to this sheet, not the sheet itself - it is read by
  // one layer of twenty-one (the hillshade) plus the three contour layers, and
  // the OSM half needs a URL and a schema, nothing more. So the DEM and the
  // contours go, and everything else stays.
  const degraded = buildMapStyle({
    topoArchiveUrl: 'pmtiles://ourhike-corridor',
    trailsUrl: '/data/trails.geojson',
    background: 'hiking_topo_live',
  })

  it('is a valid style rather than one pointing at sources it never added', () => {
    // The guard against a half-done split: a layer left bound to a source that
    // was dropped is precisely what validateStyleMin reports, and it is the
    // one assertion here that cannot be satisfied by accident.
    expect(validateStyleMin(degraded)).toEqual([])
  })

  it('still draws the OSM sheet, which needs no elevation model', () => {
    expect(degraded.sources).toHaveProperty(OSM_SOURCE_ID)
    expect((degraded.sources[OSM_SOURCE_ID] as { tiles?: string[] }).tiles).toEqual([
      BASEMAP_TILES_URL,
    ])
    for (const id of [
      LIVE_TOPO_LAYER_IDS.wood,
      LIVE_TOPO_LAYER_IDS.water,
      LIVE_TOPO_LAYER_IDS.path,
      LIVE_TOPO_LAYER_IDS.peak,
      LIVE_TOPO_LAYER_IDS.place,
    ]) {
      expect(ids(degraded)).toContain(id)
    }
  })

  it('keeps the glyphs URL its surviving labels need', () => {
    // Summits, water names and place names are OSM-sourced symbol layers and
    // outlive a missing DEM, so the font endpoint has to outlive it too.
    // validateStyleMin does NOT catch a text-field with no glyphs URL, so this
    // is asserted here or nowhere.
    expect(degraded.glyphs).toBe(BUNDLED_GLYPHS)
  })

  it('drops exactly the elevation sources and the layers reading them', () => {
    expect(degraded.sources).not.toHaveProperty(DEM_SOURCE_ID)
    expect(degraded.sources).not.toHaveProperty(CONTOUR_SOURCE_ID)
    for (const id of [
      LIVE_TOPO_LAYER_IDS.hillshade,
      LIVE_TOPO_LAYER_IDS.contour,
      LIVE_TOPO_LAYER_IDS.contourIndex,
      LIVE_TOPO_LAYER_IDS.contourLabel,
    ]) {
      expect(ids(degraded)).not.toContain(id)
    }
  })

  it('keeps the downloaded archive under the live sheet, as ever', () => {
    const order = ids(degraded)
    expect(order).toContain(TOPO_LAYER_ID)
    expect(order.indexOf(TOPO_LAYER_ID)).toBeLessThan(
      order.indexOf(LIVE_TOPO_LAYER_IDS.wood),
    )
  })
})

describe('attachElevationLabelUnits', () => {
  // The other half of the live unit switch. attachContourUnits re-points the
  // contour SOURCE at the other unit's tiles; without this, the label suffix
  // and the peak elevation field stayed baked at style-build time, and a
  // metric retune drew 500 m index contours labelled 500'.
  it('re-points both elevation text-fields in place', async () => {
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const { attachElevationLabelUnits, contourLabelTextField, peakLabelTextField } =
      await import('./liveTopo')
    const m = new MockMap({})
    m.layerIds = [LIVE_TOPO_LAYER_IDS.contourLabel, LIVE_TOPO_LAYER_IDS.peak]

    attachElevationLabelUnits(m as never, 'metric')

    expect(
      m.layoutProperties.get(`${LIVE_TOPO_LAYER_IDS.contourLabel}/text-field`),
    ).toEqual(contourLabelTextField('metric'))
    expect(m.layoutProperties.get(`${LIVE_TOPO_LAYER_IDS.peak}/text-field`)).toEqual(
      peakLabelTextField('metric'),
    )
  })

  it('waits for the label layer when the style has not brought it yet', async () => {
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const { attachElevationLabelUnits } = await import('./liveTopo')
    const m = new MockMap({})

    attachElevationLabelUnits(m as never, 'metric')
    expect(m.layoutProperties.size).toBe(0)

    m.layerIds = [LIVE_TOPO_LAYER_IDS.contourLabel, LIVE_TOPO_LAYER_IDS.peak]
    m.emit('styledata')
    expect(m.layoutProperties.size).toBe(2)
  })

  it('leaves an offline-background style alone', async () => {
    // Neither layer exists there, and that is a normal state rather than a
    // failure - the wait simply never resolves and detach ends it.
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const { attachElevationLabelUnits } = await import('./liveTopo')
    const m = new MockMap({})
    m.layerIds = [TOPO_LAYER_ID]

    const detach = attachElevationLabelUnits(m as never, 'metric')
    m.emit('styledata')
    detach()

    expect(m.layoutProperties.size).toBe(0)
  })

  it('survives a live style that has contour labels but no peak layer', async () => {
    // ready() probes the contour label only; the peak write is guarded
    // separately because proving one layer is there proves nothing about
    // the rest, and the mock (like real MapLibre) rejects writes to absent
    // layers.
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const { attachElevationLabelUnits, contourLabelTextField } =
      await import('./liveTopo')
    const m = new MockMap({})
    m.layerIds = [LIVE_TOPO_LAYER_IDS.contourLabel]

    attachElevationLabelUnits(m as never, 'imperial')

    expect(
      m.layoutProperties.get(`${LIVE_TOPO_LAYER_IDS.contourLabel}/text-field`),
    ).toEqual(contourLabelTextField('imperial'))
    expect(m.layoutProperties.size).toBe(1)
  })

  it('retunes the summits on a live style that has no contours', async () => {
    // The mirror image of the case above, and newly reachable: a live sheet
    // built without terrain keeps its OSM peak labels and has no contour
    // layers at all. A probe that waited on the contour label alone would
    // never fire here, so every summit would keep reading `ele_ft` after a
    // switch to metric - a wrong number on the map, which is the exact
    // failure this function exists to prevent.
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const { attachElevationLabelUnits, peakLabelTextField } = await import('./liveTopo')
    const m = new MockMap({})
    m.layerIds = [LIVE_TOPO_LAYER_IDS.peak]

    attachElevationLabelUnits(m as never, 'metric')

    expect(m.layoutProperties.get(`${LIVE_TOPO_LAYER_IDS.peak}/text-field`)).toEqual(
      peakLabelTextField('metric'),
    )
    expect(m.layoutProperties.size).toBe(1)
  })
})
