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
  CORRIDOR_BOUNDARY_LAYER_ID,
  CORRIDOR_UNATTRIBUTED_CASING_LAYER_ID,
  CORRIDOR_UNATTRIBUTED_LAYER_ID,
} from './corridorLayers'
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
  SHEET_COLOURS,
  SHEET_VARIANTS,
  SHEET_VARIANT_RED,
  TOPO_PALETTE,
  TOPO_PALETTE_DARK,
  TOPO_PALETTE_FIELD_NIGHT,
  TOPO_PALETTE_RED,
  attachSheetAppearance,
  liveTopoLayers,
  sheetPalette,
  sheetVariant,
} from './liveTopo'
import { MAP_STYLE_VALUES } from '../lib/userPreferences'
import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'
import {
  CONTOUR_LEVEL_KEY,
  CONTOUR_SOURCE_ID,
  DEM_SOURCE_ID,
  ELEVATION_ATTRIBUTION,
} from './terrain'
import { POI_DOT_LAYER_ID, POI_LAYER_ID, POI_STALENESS_LAYER_ID } from './poiLayers'
import { WARNING_LAYER_ID } from './warningLayers'
import {
  ATC_UPDATE_CASING_LAYER_ID,
  ATC_UPDATE_HALO_LAYER_ID,
  ATC_UPDATE_LAYER_ID,
  ATC_UPDATE_POINT_LAYER_ID,
} from '../lib/atcUpdateStyle'
import { CLOSURE_CASING_LAYER_ID, CLOSURE_LAYER_ID } from '../lib/closureStyle'
import {
  ROUTE_CASING_LAYER_ID,
  ROUTE_LINE_LAYER_ID,
  ROUTE_POINT_LAYER_ID,
} from './routeLayers'
import { DROUGHT_LAYER_ID } from '../lib/droughtStyle'

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

/** A `#rrggbb` split into its three channels, for the couple of assertions
 *  below that are about lightness rather than about an exact value. */
function hexChannels(hex: string): [number, number, number] {
  return [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16)) as [
    number,
    number,
    number,
  ]
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
    //
    // SYMBOL layers, not all of them, and the distinction is the whole
    // mechanism rather than a narrowing of the test. Placement only ever ranks
    // symbols against symbols - a `circle` or a `line` takes no part in it, so
    // the ATC's dots and bands sit above these two in the style (that is
    // src/test/atcAlertProminence.test.ts's subject) and cannot suppress a
    // water pin no matter where they are drawn. Asserting on the raw tail
    // would say the opposite: that appending any non-symbol layer costs the
    // pins their priority, which is not true and would send the next person
    // to fix a bug that is not there.
    const symbols = live()
      .layers.filter((layer) => layer.type === 'symbol')
      .map((layer) => layer.id)

    expect(symbols.slice(-2)).toEqual([POI_LAYER_ID, WARNING_LAYER_ID])
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

describe('protected land, drawn as an area rather than an outline', () => {
  // The outline was the bug (#347): along the corridor the protected land is
  // a narrow sliver whose edges parallel the trail for miles, and a broken
  // line wandering through woodland gets read as a walkable one whatever its
  // rhythm - restyling the edge still left two long lines beside the trail.
  // So there is no edge at all, and the tint carries the fact alone. These
  // hold the two halves of that: no outline can come back, and no palette
  // tweak can fade the tint out of legibility over the woodland that most
  // protected land here is - which is the failure the outline originally
  // existed to paper over.

  const layers = () => liveTopoLayers({ terrain: TERRAIN, units: 'imperial' })

  it('draws no park outline at all', () => {
    expect(layers().map((l) => l.id)).not.toContain('topo-park-edge')
  })

  it('leaves every broken line accounted for: walkable beats, or the state line', () => {
    // Paths and tracks own the even two-beat rhythms; the admin boundary owns
    // the dash-dot. A new dashed layer joining the sheet has to face this
    // list, which is the point - a broken green line through woodland is
    // exactly how #347 happened.
    const dashed = layers().filter(
      (l) => (l.paint as Record<string, unknown> | undefined)?.['line-dasharray'],
    )

    expect(dashed.map((l) => l.id).sort()).toEqual(
      [
        LIVE_TOPO_LAYER_IDS.boundary,
        LIVE_TOPO_LAYER_IDS.path,
        LIVE_TOPO_LAYER_IDS.track,
      ].sort(),
    )
  })

  it('keeps the tint legible over woodland, in every palette of every style', () => {
    // What "the tint carries it alone" means in numbers: composited over the
    // wood fill at the layer's own opacity, the park wash has to move at
    // least one channel by a margin a phone panel still shows. The exact
    // colours are the palette's business - under red light the wash is a
    // dim rust, not a green - and only the margin is pinned. A palette
    // added without meeting it is the old invisible tint coming back.
    //
    // Swept over the whole variant table rather than the three palettes this
    // was written against, and that is the case it caught: every mockup card
    // drew its park wash with a dashed outline beside it, so all eleven
    // arrived a few RGB steps from their own wood fill. A style added later
    // faces the same bar without anyone remembering to add it here.
    const park = layers().find((l) => l.id === LIVE_TOPO_LAYER_IDS.parkFill)
    if (park === undefined) throw new Error('no park fill layer in the live sheet')
    const opacity = (park.paint as Record<string, unknown>)['fill-opacity'] as number

    expect(opacity).toBeGreaterThan(0)
    expect(opacity).toBeLessThan(1)

    const palettes = [
      ...MAP_STYLE_VALUES.flatMap((style) => [
        SHEET_VARIANTS[style].day.palette,
        SHEET_VARIANTS[style].night.palette,
      ]),
      SHEET_VARIANT_RED.palette,
    ]

    for (const palette of palettes) {
      const wood = hexChannels(palette.wood)
      const wash = hexChannels(palette.park)
      const delta = Math.max(
        ...wood.map((w, at) => Math.abs(w * (1 - opacity) + wash[at] * opacity - w)),
      )

      expect(delta, `${palette.wood} -> ${palette.park}`).toBeGreaterThanOrEqual(8)
    }
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
      // The drought wash sits between the background and the trail, and its
      // presence here is the assertion (#720): it is a BACKGROUND layer, so
      // it must survive the subtraction the way the archive does - and it
      // must stay below everything a hiker acts on. Built hidden; the switch
      // is a visibility flip, not an add and remove, so it is in the stack
      // whether or not it is drawn.
      DROUGHT_LAYER_ID,
      'trail-casing',
      'trail-blaze',
      // The corridor view's attribution, over the blaze it covers and under
      // everything a hiker acts on (#598). It survives the subtraction for
      // the plainest reason of all: club_sections.json is ON THE PHONE, so
      // there is nothing about drawing it that needs signal, and the person
      // most likely to be reading the whole trail at once is the person
      // planning rather than walking.
      CORRIDOR_UNATTRIBUTED_CASING_LAYER_ID,
      CORRIDOR_UNATTRIBUTED_LAYER_ID,
      CORRIDOR_BOUNDARY_LAYER_ID,
      // The route being built survives the subtraction too (#755): planning
      // an evening's next stretch at a shelter with no signal is a normal
      // use of it, not an edge case.
      ROUTE_CASING_LAYER_ID,
      ROUTE_LINE_LAYER_ID,
      ROUTE_POINT_LAYER_ID,
      CLOSURE_CASING_LAYER_ID,
      CLOSURE_LAYER_ID,
      // All three waypoint ranks (#597, and the staleness rings with #759),
      // dots under rings under pins - a waypoint that wins its collision
      // hides its own dot, and one that loses still leaves it.
      POI_DOT_LAYER_ID,
      POI_STALENESS_LAYER_ID,
      POI_LAYER_ID,
      WARNING_LAYER_ID,
      // The ATC's own notices survive the subtraction for the same reason the
      // closures do, and arguably more so: their band is baked into a
      // published artifact rather than fetched live, so it is exactly the
      // warning a hiker with no signal still has (#461).
      //
      // LAST, over both pin layers, which is where they moved once the dots
      // were drawn large enough to matter: a closed shelter reported by the
      // organisation that maintains it, underneath OurHike's own pin for that
      // shelter, is not a picture anybody wants. src/test/atcAlertProminence.test.ts
      // holds that ordering as a property; this case only has to agree with it.
      ATC_UPDATE_HALO_LAYER_ID,
      ATC_UPDATE_CASING_LAYER_ID,
      ATC_UPDATE_LAYER_ID,
      // And the dots, which is what most ATC notices actually are - five of
      // the six reviewed on 2026-08-12 name a single mile marker.
      ATC_UPDATE_POINT_LAYER_ID,
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

describe('the sheet under light and dark', () => {
  // The palette is the whole cartography here (see the file header), so a
  // second one is a second sheet rather than a filter over the first. What
  // these guard is the wiring: that no colour is left behind, and that the
  // table which drives both the build and the live repaint stays complete.
  const layersFor = (theme: 'light' | 'dark') =>
    liveTopoLayers({ terrain: TERRAIN, units: 'imperial', theme })

  const colourProperties = (layer: LayerSpecification) =>
    Object.entries((layer.paint ?? {}) as Record<string, unknown>).filter(
      ([, value]) => typeof value === 'string' && value.startsWith('#'),
    )

  it('lists every colour the sheet paints, so none can miss the theme', () => {
    // The failure this prevents is not a crash. It is one layer still drawn in
    // paper-brown over an ink sheet, which reads as a rendering bug rather
    // than as a line somebody forgot to add to a list - so the list is checked
    // against what the style actually paints rather than trusted.
    const declared = new Set(
      SHEET_COLOURS.map(([layer, property]) => `${layer}/${property}`),
    )

    for (const layer of layersFor('light')) {
      for (const [property] of colourProperties(layer)) {
        expect(declared).toContain(`${layer.id}/${property}`)
      }
    }
  })

  it('repoints every one of them under the dark theme', () => {
    const light = layersFor('light')
    const dark = layersFor('dark')

    for (const [index, layer] of light.entries()) {
      for (const [property, value] of colourProperties(layer)) {
        const darkValue = (dark[index].paint as Record<string, unknown>)[property]
        expect(darkValue, `${layer.id}/${property}`).not.toBe(value)
      }
    }
  })

  it('keys every palette the same, so a new colour cannot stay light', () => {
    expect(Object.keys(TOPO_PALETTE_DARK).sort()).toEqual(
      Object.keys(TOPO_PALETTE).sort(),
    )
    expect(Object.keys(TOPO_PALETTE_RED).sort()).toEqual(Object.keys(TOPO_PALETTE).sort())
  })

  it('holds only real six-digit hex in every variant of every style - the tables are data', () => {
    // MAP_STYLE_SPEC.md's own test brief, swept across the full variant
    // table. A malformed value here is not a type error - TopoPalette is
    // Record<..., string> - and MapLibre would swallow it per layer, so it is
    // asserted where the data lives. Backdrop and casing ride along: they
    // are the same class of data one table over.
    const variants = [
      ...MAP_STYLE_VALUES.flatMap((style) => [
        SHEET_VARIANTS[style].day,
        SHEET_VARIANTS[style].night,
      ]),
      SHEET_VARIANT_RED,
    ]

    for (const variant of variants) {
      for (const [key, value] of Object.entries(variant.palette)) {
        expect(value, key).toMatch(/^#[0-9a-f]{6}$/)
      }
      expect(variant.backdrop).toMatch(/^#[0-9a-f]{6}$/)
      expect(variant.casing).toMatch(/^#[0-9a-f]{6}$/)
      expect(variant.hillshadeBase).toBeGreaterThan(0)
      expect(variant.hillshadeBase).toBeLessThanOrEqual(1)
    }
  })

  it('gives every style a day and a night sheet, keyed to the same value list', () => {
    // MAP_STYLE_VALUES is what the picker offers and the backend accepts; a
    // style in that list without variants here is a control writing a value
    // nothing can render.
    for (const style of MAP_STYLE_VALUES) {
      expect(SHEET_VARIANTS[style]?.day, style).toBeDefined()
      expect(SHEET_VARIANTS[style]?.night, style).toBeDefined()
    }
  })

  it('aims every row of the colour table at a layer the sheet actually builds', () => {
    // The complement of "lists every colour": a typo'd id in SHEET_COLOURS
    // would build fine and repaint nothing, leaving one layer stuck in the
    // palette it was born with.
    const built = new Set(layersFor('light').map((layer) => layer.id))

    for (const [layer] of SHEET_COLOURS) {
      expect(built, layer).toContain(layer)
    }
  })

  it('keeps the dark sheet genuinely dark rather than mid-grey', () => {
    // The reason this is in MVP at all is a phone on a trail after sunset
    // (features/UX_CUSTOMIZATION.md). A "dark" ground that settles at #333
    // still lights a face up, and still costs the night vision the theme was
    // meant to protect. Checked on the ground layers only - labels are
    // supposed to be bright, which is the point of them.
    for (const key of ['wood', 'scrub', 'wetland', 'rock', 'park'] as const) {
      const [r, g, b] = hexChannels(TOPO_PALETTE_DARK[key])
      expect((r + g + b) / 3, key).toBeLessThan(60)
    }
  })

  it('keeps the labels the brightest thing on the dark sheet', () => {
    // A place name you cannot read is a place name that is not there.
    const [lr, lg, lb] = hexChannels(TOPO_PALETTE_DARK.label)
    const [gr, gg, gb] = hexChannels(TOPO_PALETTE_DARK.wood)

    expect((lr + lg + lb) / 3).toBeGreaterThan((gr + gg + gb) / 3 + 100)
  })

  it('defaults to the light sheet for a caller with no opinion', () => {
    const wood = liveTopoLayers({ terrain: TERRAIN, units: 'imperial' }).find(
      (l) => l.id === LIVE_TOPO_LAYER_IDS.wood,
    )
    if (wood === undefined) throw new Error('no wood layer in the light sheet')

    expect((wood.paint as Record<string, unknown>)['fill-color']).toBe(TOPO_PALETTE.wood)
  })
})

describe('sheetPalette', () => {
  // How the three preferences compose (MAP_STYLE_SPEC.md), spelled per case
  // so a regression names the hiker it fails: which style, which mode, and
  // whether red light was armed.
  it.each([
    [
      'field by day is the field sheet',
      { mapStyle: 'field', theme: 'light' },
      TOPO_PALETTE,
    ],
    [
      "field after dark is night_hike - the spec's auto-dark",
      { mapStyle: 'field', theme: 'dark' },
      TOPO_PALETTE_DARK,
    ],
    [
      'night_hike chosen outright is dark even under the light theme',
      { mapStyle: 'night_hike', theme: 'light' },
      TOPO_PALETTE_DARK,
    ],
    [
      'night_hike stays itself after dark',
      { mapStyle: 'night_hike', theme: 'dark' },
      TOPO_PALETTE_DARK,
    ],
    [
      'red light re-inks night_hike',
      { mapStyle: 'night_hike', theme: 'dark', redLight: true },
      TOPO_PALETTE_RED,
    ],
    [
      'red light never touches a day sheet - it refines night_hike only',
      { mapStyle: 'field', theme: 'light', redLight: true },
      TOPO_PALETTE,
    ],
    [
      'a CHOSEN dark theme reaches field/night - the bright-screen-in-the-dark sheet',
      { mapStyle: 'field', theme: 'dark', themeChoice: 'dark' },
      TOPO_PALETTE_FIELD_NIGHT,
    ],
    [
      "an auto theme that resolved dark does not - sunset on a trail wants night_hike's dim",
      { mapStyle: 'field', theme: 'dark', themeChoice: 'auto' },
      TOPO_PALETTE_DARK,
    ],
  ] as const)('%s', (_name, appearance, expected) => {
    expect(sheetPalette(appearance)).toBe(expected)
  })

  it('follows every other style to its own night sheet, chosen or auto alike', () => {
    // Field's auto-dark exception is field's alone: quiet_pine, parchment and
    // ridgeline drew their nights as dim companions, so both roads to dark
    // land on the same sheet.
    for (const style of ['quiet_pine', 'parchment', 'ridgeline'] as const) {
      for (const themeChoice of ['auto', 'dark'] as const) {
        expect(
          sheetVariant({ mapStyle: style, theme: 'dark', themeChoice }),
          `${style}/${themeChoice}`,
        ).toBe(SHEET_VARIANTS[style].night)
      }
      expect(sheetVariant({ mapStyle: style, theme: 'light' })).toBe(
        SHEET_VARIANTS[style].day,
      )
    }
  })

  it('carries each card’s tuning on the variant, ridgeline strongest', () => {
    // The card notes are data too: ridgeline is 0.55 relief with contours a
    // zoom early - terrain first means terrain sooner - while field sits at
    // 0.30 with the bold sunlight type, and quiet_pine keeps the launch
    // weights untouched.
    expect(SHEET_VARIANTS.ridgeline.day.hillshadeBase).toBe(0.55)
    expect(SHEET_VARIANTS.ridgeline.day.contoursEarly).toBe(true)
    expect(SHEET_VARIANTS.field.day.hillshadeBase).toBe(0.3)
    expect(SHEET_VARIANTS.field.day.boldType).toBe(true)
    expect(SHEET_VARIANTS.quiet_pine.day.hillshadeBase).toBe(0.35)
    expect(SHEET_VARIANTS.quiet_pine.day.boldType).toBe(false)
    expect(SHEET_VARIANTS.quiet_pine.day.contoursEarly).toBe(false)
  })

  it('keeps the red sheet as dark as the night one, ground layer by ground layer', () => {
    // Red light exists to spare dark adaptation; a red sheet lighter than the
    // dark sheet would cost the very thing it advertises.
    for (const key of ['wood', 'scrub', 'wetland', 'rock', 'park', 'water'] as const) {
      const [r, g, b] = hexChannels(TOPO_PALETTE_RED[key])
      expect((r + g + b) / 3, key).toBeLessThan(60)
    }
  })

  it('spends its brightness on red wavelengths, not blue ones', () => {
    // The whole physiological point: rods are near-blind to deep red, so red
    // may be bright where blue may not. Every colour on the red sheet keeps
    // its red channel dominant and its blue channel smallest.
    for (const [key, value] of Object.entries(TOPO_PALETTE_RED)) {
      const [r, g, b] = hexChannels(value)
      expect(r, key).toBeGreaterThanOrEqual(g)
      expect(g, key).toBeGreaterThanOrEqual(b)
    }
  })

  it('keeps the labels the brightest thing on the red sheet too', () => {
    // A smaller margin than the dark sheet's 100, on purpose: the reviewed
    // red values are dimmer throughout - "astronomy-grade darkness" is the
    // card's own bar - and a label bright enough to clear the dark sheet's
    // margin would be spending the adaptation the mode exists to keep.
    const [lr, lg, lb] = hexChannels(TOPO_PALETTE_RED.label)
    const [gr, gg, gb] = hexChannels(TOPO_PALETTE_RED.wood)

    expect((lr + lg + lb) / 3).toBeGreaterThan((gr + gg + gb) / 3 + 80)
  })
})

describe('attachSheetAppearance', () => {
  it('repaints every colour on a live map, without rebuilding the style', async () => {
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})
    m.layerIds = [...new Set(SHEET_COLOURS.map(([layer]) => layer))]

    attachSheetAppearance(m as never, { theme: 'dark' })

    for (const [layer, property, colour] of SHEET_COLOURS) {
      expect(m.paintProperties.get(`${layer}/${property}`)).toBe(
        TOPO_PALETTE_DARK[colour],
      )
    }
    expect(m.styles).toEqual([])
  })

  it('leaves an offline-background style alone', async () => {
    // None of the sheet's layers is in it, which is a normal state rather than
    // a failure - the wait simply never resolves and detach ends it.
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})
    m.layerIds = [TOPO_LAYER_ID, BACKDROP_LAYER_ID]

    const detach = attachSheetAppearance(m as never, { theme: 'dark' })
    m.emit('styledata')
    detach()

    expect(m.paintProperties.size).toBe(0)
  })

  it('skips the terrain layers a style built without a DEM does not have', async () => {
    // The probe is the wood layer, which is always there when the sheet is.
    // Proving it exists proves nothing about the four DEM/contour layers that
    // liveTopoLayers filters out when terrain could not be built, and the mock
    // rejects a write to an absent layer exactly as MapLibre does.
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})
    m.layerIds = [LIVE_TOPO_LAYER_IDS.wood, LIVE_TOPO_LAYER_IDS.place]

    attachSheetAppearance(m as never, { theme: 'dark' })

    expect(m.paintProperties.get(`${LIVE_TOPO_LAYER_IDS.wood}/fill-color`)).toBe(
      TOPO_PALETTE_DARK.wood,
    )
    expect(
      m.paintProperties.get(`${LIVE_TOPO_LAYER_IDS.hillshade}/hillshade-shadow-color`),
    ).toBeUndefined()
  })

  it('replays the variant tuning too, and a style change is a true restore', async () => {
    // Ridgeline turns the relief up and pulls the contours a zoom early;
    // leaving it must turn both back. Sticky properties make a loop that only
    // writes what differs a one-way ratchet - so the attach writes the full
    // managed set for the TARGET variant every time.
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})
    m.layerIds = [...new Set(SHEET_COLOURS.map(([layer]) => layer))]

    attachSheetAppearance(m as never, { mapStyle: 'ridgeline' })()

    const exaggeration = m.paintProperties.get(
      `${LIVE_TOPO_LAYER_IDS.hillshade}/hillshade-exaggeration`,
    ) as unknown[]
    expect(exaggeration[exaggeration.length - 1]).toBe(0.55)
    const minorOpacity = m.paintProperties.get(
      `${LIVE_TOPO_LAYER_IDS.contour}/line-opacity`,
    ) as unknown[]
    expect(minorOpacity).toContain(9)

    attachSheetAppearance(m as never, { mapStyle: 'quiet_pine' })

    const restored = m.paintProperties.get(
      `${LIVE_TOPO_LAYER_IDS.hillshade}/hillshade-exaggeration`,
    ) as unknown[]
    expect(restored[restored.length - 1]).toBe(0.35)
    expect(m.layoutProperties.get(`${LIVE_TOPO_LAYER_IDS.contourLabel}/text-size`)).toBe(
      10,
    )
    expect(m.paintProperties.get(`${LIVE_TOPO_LAYER_IDS.peak}/text-halo-width`)).toBe(1.6)
  })

  it('writes the field type treatment when field is the target', async () => {
    const { MockMap } = await import('../test/mocks/maplibre-gl')
    const m = new MockMap({})
    m.layerIds = [...new Set(SHEET_COLOURS.map(([layer]) => layer))]

    attachSheetAppearance(m as never, { mapStyle: 'field', theme: 'light' })

    expect(m.layoutProperties.get(`${LIVE_TOPO_LAYER_IDS.contourLabel}/text-size`)).toBe(
      11,
    )
    expect(
      m.paintProperties.get(`${LIVE_TOPO_LAYER_IDS.contourLabel}/text-halo-width`),
    ).toBe(1.8)
  })
})
