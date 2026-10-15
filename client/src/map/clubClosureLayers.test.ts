// Every club closure on the map (the maintainer's S6, poll of 2026-10-11),
// as the map draws it and as a touch reaches it: the layers, the filters as
// MapLibre's own tiler hands them features, the source the closures land in,
// and the one-touch-one-sheet order every handler keeps around them.

import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { featureFilter } from '@maplibre/maplibre-gl-style-spec'
import type { LayerSpecification } from '@maplibre/maplibre-gl-style-spec'
import { GeoJSONVT } from '@maplibre/geojson-vt'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import {
  buildClosureLayers,
  CLOSURE_CROSS_ICON_ID,
  closureCrossImageSize,
  closureCrossesId,
  CLOSURE_LAYER_ID,
  CLOSURE_MARK_HALO_WIDTH,
  CLOSURE_MARK_MIN_ZOOM,
  CLOSURE_MARK_SIZE,
  CLOSURE_MARK_UNTIL_CROSSES,
  closureMarkUntilFilter,
  CLOSURE_NEAR_MIN_ZOOM,
  CLOSURE_TRACE_OPACITY,
  closureLayerIds,
  closureMarkId,
  closurePointId,
} from '../lib/closureStyle'
import { ATC_UPDATE_LAYER_ID } from '../lib/atcUpdateStyle'
import type { TrailClosure } from '../lib/publishedConditions'
import { validTrailClosure } from '../lib/publishedNotices'
import {
  shortClosureRow,
  trailClosureRows,
} from '../../preview-shots/fixtures/clubClosures.mjs'
import {
  buildClubClosureLayers,
  buildClubClosureShadeLayer,
  buildClubClosureSource,
  CLUB_CLOSURE_CHAIN_FROM_PROPERTY,
  CLUB_CLOSURE_LINE_FILTER,
  CLUB_CLOSURE_NEVER_CHAINED,
  CLUB_CLOSURE_POINT_FILTER,
  CLUB_CLOSURE_SHADE_FILTER,
  CLUB_CLOSURE_SHADE_LAYER_ID,
  CLUB_CLOSURE_SOURCE_ID,
  clubClosureChainFrom,
  clubClosureShadeIdAt,
  clubClosureShadeImageId,
  longestRunAtZ0,
  SHADE_INKS,
} from './clubClosureLayers'
import {
  attachClubClosureData,
  attachClubClosureTaps,
  clubClosureFeatureCollection,
} from './clubClosureTaps'
import { CLOSURE_ID_PROPERTY, CLUB_CLOSURE_ID_PROPERTY } from './closureLayers'
import { ATC_UPDATE_ID_PROPERTY, attachAtcUpdateTaps } from './atcUpdateLayers'
import { HAZARD_FILL_LAYER_ID } from './hazardAreaLayers'
import { attachHazardTaps } from './hazardAreaTaps'
import { tappedLineAt } from './lineTaps'
import { POI_DOT_LAYER_ID, POI_ID_PROPERTY, POI_LAYER_ID } from './poiLayers'
import { poiIdAt } from './poiTaps'
import {
  attachMapAppearance,
  BACKDROP_LAYER_ID,
  BLAZE_LAYER_ID,
  closureInk,
  closureTapeGround,
  CLUB_CLOSURE_LAYER_ID,
} from './style'
import { WARNING_ID_PROPERTY, WARNING_LAYER_ID } from './warningLayers'

const GROUND = '#ffffff'
const INK = '#14130f'
const POINT_LAYER_ID = closurePointId(CLUB_CLOSURE_LAYER_ID)

/** The hand-made file's five closures, read by the app's own reader. */
function closures(): Record<
  'line' | 'area' | 'point' | 'greyed' | 'shade',
  TrailClosure
> {
  const rows = trailClosureRows()
  const read = (row: unknown) => {
    const closure = validTrailClosure(row)
    if (closure === null) throw new Error('the fixture row did not read')
    return closure
  }
  return {
    line: read(rows.line),
    area: read(rows.area),
    point: read(rows.point),
    greyed: read(rows.greyed),
    shade: read(rows.shade),
  }
}

/** The z10 tile holding `[lon, lat]`, as MapLibre's GeoJSON source tiles
 *  `closures` (@maplibre/geojson-vt): at z0 the tiler drops a line shorter
 *  than its tolerance, about 29 km there, and every closure here is
 *  shorter. */
function tileAt([lon, lat]: [number, number], closures: readonly TrailClosure[]) {
  const z = 10
  const x = Math.floor(((lon + 180) / 360) * 2 ** z)
  const rad = (lat * Math.PI) / 180
  const y = Math.floor(
    ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * 2 ** z,
  )
  return new GeoJSONVT(clubClosureFeatureCollection(closures) as never).getTile(z, x, y)
}

function layer(id: string): LayerSpecification {
  const found = buildClubClosureLayers(GROUND, INK).find((built) => built.id === id)
  if (found === undefined) throw new Error(`no layer ${id}`)
  return found
}

/** Whether a layer's filter lets a tile feature of `type` through (MapLibre's
 *  1 Point, 2 LineString, 3 Polygon). */
function passes(filter: unknown, type: 1 | 2 | 3): boolean {
  return featureFilter(filter as never, 'filter').filter(
    { zoom: 13 } as never,
    { type, properties: {}, geometry: [] } as never,
    null as never,
  )
}

beforeEach(() => {
  resetMapLibreMock()
})

describe('how a club closure is drawn', () => {
  it('crosses a line closure out with exactly the mark every closure feed wears, but for how long its far mark stays (decision 198)', () => {
    // "Only the id, the source, the filter and the spacing may differ, and,
    // on the clubs' feed alone, how long the far mark stays"
    // (lib/closureStyle.ts): held as equality with the temporary-closure
    // feed's own four layers, paint, layout and zooms, rather than as
    // constants.
    const club = closureLayerIds(CLUB_CLOSURE_LAYER_ID).map(layer)
    const temporary = buildClosureLayers('closures', { ground: GROUND, ink: INK })
    expect(temporary.map((built) => built.id)).toEqual(closureLayerIds(CLOSURE_LAYER_ID))
    club.forEach((built, index) => {
      expect((built as { source?: unknown }).source).toBe(CLUB_CLOSURE_SOURCE_ID)
      expect(built.paint, built.id).toEqual(temporary[index].paint)
      expect((built as { layout?: unknown }).layout, built.id).toEqual(
        (temporary[index] as { layout?: unknown }).layout,
      )
      expect((built as { minzoom?: unknown }).minzoom, built.id).toBe(
        (temporary[index] as { minzoom?: unknown }).minzoom,
      )
    })
    const [paper, trace, chain, mark] = club as Array<{
      filter?: unknown
      maxzoom?: unknown
    }>
    for (const each of [paper, trace, chain]) {
      expect(each.filter).toEqual(CLUB_CLOSURE_LINE_FILTER)
      expect(each.maxzoom).toBeUndefined()
    }
    // The far mark alone differs: no maxzoom, and the line filter joined by
    // the handover each closure carries.
    expect(mark.filter).toEqual([
      'all',
      CLUB_CLOSURE_LINE_FILTER,
      closureMarkUntilFilter(CLUB_CLOSURE_CHAIN_FROM_PROPERTY),
    ])
    expect(mark.maxzoom).toBeUndefined()
    expect((temporary[3] as { maxzoom?: unknown }).maxzoom).toBe(CLOSURE_NEAR_MIN_ZOOM)
  })

  it('draws a line and an area’s cut stretches on the line layers, and a point on the cross alone, as MapLibre’s tiler hands them over', () => {
    // The area's MultiLineString has to reach the LineString filter: if it
    // did not, every closed park would draw nothing. Run through the tiler
    // MapLibre's GeoJSON source uses (@maplibre/geojson-vt), not a guess at
    // what it emits.
    const { line, area, point } = closures()
    const tile = tileAt(point.place.geometry.coordinates as [number, number], [
      line,
      area,
      point,
    ])
    expect(tile?.features).toHaveLength(3)
    const drawnBy = (filter: unknown) =>
      (tile?.features ?? [])
        .filter((feature) => passes(filter, feature.type as 1 | 2 | 3))
        .map((feature) => feature.tags?.[CLUB_CLOSURE_ID_PROPERTY])
    expect(drawnBy(CLUB_CLOSURE_LINE_FILTER)).toEqual([line.notice_id, area.notice_id])
    expect(drawnBy(CLUB_CLOSURE_POINT_FILTER)).toEqual([point.notice_id])
    // And the source the style declares is there before any closure lands,
    // keeping every line however short (decision 198).
    expect(buildClubClosureSource()).toEqual({
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
      tolerance: 0,
    })
  })

  it('shades an area no trail runs inside on the hatch layer alone, never along the crossed-out mark (decision 191)', () => {
    // "Shade them, no edge": the polygon must reach the fill and nothing
    // that draws a line, or its edge would read as a closed trail.
    const { line, shade } = closures()
    const [outline] = shade.place.geometry.coordinates as Array<Array<[number, number]>>
    const tile = tileAt(outline[0], [line, shade])
    const drawnBy = (filter: unknown) =>
      (tile?.features ?? [])
        .filter((feature) => passes(filter, feature.type as 1 | 2 | 3))
        .map((feature) => feature.tags?.[CLUB_CLOSURE_ID_PROPERTY])
    expect(drawnBy(CLUB_CLOSURE_SHADE_FILTER)).toEqual([shade.notice_id])
    expect(drawnBy(CLUB_CLOSURE_LINE_FILTER)).toEqual([line.notice_id])
    expect(drawnBy(CLUB_CLOSURE_POINT_FILTER)).toEqual([])
    // And no crossed-out layer takes a polygon at all.
    for (const built of buildClubClosureLayers(GROUND, INK)) {
      expect(passes((built as { filter?: unknown }).filter, 3), built.id).toBe(false)
    }
  })

  it('draws the shade as frame A drew it: the sheet’s hatch, filled, with no outline and no antialiasing pass along the edge', () => {
    const day = buildClubClosureShadeLayer({ theme: 'light' })
    expect(day).toEqual({
      id: CLUB_CLOSURE_SHADE_LAYER_ID,
      type: 'fill',
      source: CLUB_CLOSURE_SOURCE_ID,
      filter: CLUB_CLOSURE_SHADE_FILTER,
      paint: {
        'fill-pattern': clubClosureShadeImageId('day'),
        'fill-antialias': false,
      },
    })
    expect(JSON.stringify(day)).not.toContain('outline')
    expect(
      (buildClubClosureShadeLayer({ theme: 'dark' }).paint as Record<string, unknown>)[
        'fill-pattern'
      ],
    ).toBe(clubClosureShadeImageId('night'))
    expect(
      (
        buildClubClosureShadeLayer({ mapStyle: 'night_hike', redLight: true })
          .paint as Record<string, unknown>
      )['fill-pattern'],
    ).toBe(clubClosureShadeImageId('red'))
  })

  it('names the sheet’s hatch again on a sheet change', () => {
    const map = new MockMap({})
    map.layerIds = [BACKDROP_LAYER_ID, CLUB_CLOSURE_SHADE_LAYER_ID]

    attachMapAppearance(map as never, { mapStyle: 'night_hike', redLight: true })
    expect(map.paintProperties.get(`${CLUB_CLOSURE_SHADE_LAYER_ID}/fill-pattern`)).toBe(
      clubClosureShadeImageId('red'),
    )
    attachMapAppearance(map as never, { theme: 'light' })
    expect(map.paintProperties.get(`${CLUB_CLOSURE_SHADE_LAYER_ID}/fill-pattern`)).toBe(
      clubClosureShadeImageId('day'),
    )
  })

  it('draws a point closure as one cross: the far mark, at the point, from the pin seam in and at every zoom after', () => {
    const point = layer(POINT_LAYER_ID)
    expect(point).toMatchObject({
      type: 'symbol',
      source: CLUB_CLOSURE_SOURCE_ID,
      filter: CLUB_CLOSURE_POINT_FILTER,
      minzoom: CLOSURE_MARK_MIN_ZOOM,
      layout: {
        'icon-image': CLOSURE_CROSS_ICON_ID,
        'icon-size': CLOSURE_MARK_SIZE,
        'icon-allow-overlap': true,
      },
      paint: {
        'icon-color': INK,
        'icon-halo-color': GROUND,
        'icon-halo-width': CLOSURE_MARK_HALO_WIDTH,
      },
    })
    expect(point.maxzoom).toBeUndefined()
    // The far mark's own image and size, so a hiker reads one mark.
    const mark = layer(closureMarkId(CLUB_CLOSURE_LAYER_ID))
    expect((mark.layout as Record<string, unknown>)['icon-image']).toBe(
      (point.layout as Record<string, unknown>)['icon-image'],
    )
    expect((mark.layout as Record<string, unknown>)['icon-size']).toBe(CLOSURE_MARK_SIZE)
  })

  it('draws a closure the list greys at the same full strength: no layer reads the notice, and a feature carries only its id and its geometry’s handover zoom', () => {
    // The maintainer's "B: same mark" over fading it. A fade would need a
    // paint expression reading something off the feature; there is none, and
    // the only opacity anywhere is the trace's constant, the same on every
    // closure feed. The one property a layer reads is the far mark's handover
    // zoom (decision 198), and it is worked out from the line alone, so the
    // greyed closure and the same line with every date given carry the same.
    const built = JSON.stringify(buildClubClosureLayers(GROUND, INK))
    expect(new Set(built.match(/\["get","[^"]*"\]/g))).toEqual(
      new Set([`["get","${CLUB_CLOSURE_CHAIN_FROM_PROPERTY}"]`]),
    )
    expect(built).not.toContain('feature-state')
    const opacities = buildClubClosureLayers(GROUND, INK).flatMap((each) =>
      Object.entries(each.paint ?? {}).filter(([property]) =>
        property.includes('opacity'),
      ),
    )
    expect(opacities).toEqual([['line-opacity', CLOSURE_TRACE_OPACITY]])
    const { greyed, line } = closures()
    const dated: TrailClosure = {
      ...line,
      notice_id: 'example:canyon-trail-dated',
      place: greyed.place,
    }
    const [greyedFeature, datedFeature] = clubClosureFeatureCollection([
      greyed,
      dated,
    ]).features
    expect(greyedFeature.properties).toEqual({
      [CLUB_CLOSURE_ID_PROPERTY]: greyed.notice_id,
      [CLUB_CLOSURE_CHAIN_FROM_PROPERTY]: clubClosureChainFrom(greyed.place.geometry),
    })
    expect(datedFeature.properties[CLUB_CLOSURE_CHAIN_FROM_PROPERTY]).toBe(
      greyedFeature.properties[CLUB_CLOSURE_CHAIN_FROM_PROPERTY],
    )
  })

  it('repaints the point cross with every other closure layer on a sheet change', () => {
    const map = new MockMap({})
    map.layerIds = [
      BACKDROP_LAYER_ID,
      ...closureLayerIds(CLUB_CLOSURE_LAYER_ID),
      POINT_LAYER_ID,
    ]
    const appearance = { mapStyle: 'night_hike', redLight: true } as const

    attachMapAppearance(map as never, appearance)

    expect(map.paintProperties.get(`${POINT_LAYER_ID}/icon-color`)).toBe(
      closureInk(appearance),
    )
    expect(map.paintProperties.get(`${POINT_LAYER_ID}/icon-halo-color`)).toBe(
      closureTapeGround(appearance),
    )
  })
})

describe('a closure too short for the chain keeps the bold ✕ (decision 198)', () => {
  // Finding F1 of the client review of #1805 — dlt → dbt re-platform as one
  // go/no-go change: from z11 the only ✕ on a club closure was the chain,
  // which puts none on a short run, and below z11 a line under 0.375 px was
  // not tiled at all. These are the reviewer's own closures: straight
  // east-west lines at latitude 41.

  /** A line closure `metres` long, east-west at latitude 41. */
  function lineClosure(metres: number): TrailClosure {
    const halfDegrees = metres / 2 / (111_319.49 * Math.cos((41 * Math.PI) / 180))
    return {
      ...closures().line,
      notice_id: `example:${metres}-m`,
      place: {
        kind: 'geometry',
        geometry: {
          type: 'LineString',
          coordinates: [
            [-74 - halfDegrees, 41],
            [-74 + halfDegrees, 41],
          ],
        },
      },
    }
  }

  /** Metres on the ground for `pixels` on screen at a whole `zoom`, at
   *  latitude 41 on MapLibre's 512 px tiles. */
  function metresFor(pixels: number, zoom: number): number {
    return (pixels * 40_075_016.686 * Math.cos((41 * Math.PI) / 180)) / (512 * 2 ** zoom)
  }

  /** Whether the far mark draws `closure` at a whole `zoom`: inside its
   *  layer's zooms, and through its filter as MapLibre evaluates one, at the
   *  tile's whole zoom, on the feature as the source holds it. */
  function farMarkDraws(closure: TrailClosure, zoom: number): boolean {
    const mark = layer(closureMarkId(CLUB_CLOSURE_LAYER_ID)) as {
      minzoom?: number
      maxzoom?: number
      filter?: unknown
    }
    if (zoom < (mark.minzoom ?? 0) || zoom >= (mark.maxzoom ?? 24)) return false
    const [feature] = clubClosureFeatureCollection([closure]).features
    return featureFilter(mark.filter as never, 'filter').filter(
      { zoom } as never,
      { type: 2, properties: feature.properties, geometry: [] } as never,
      null as never,
    )
  }

  /** Whether the chain has room for a cross on `closure`'s longest run at a
   *  whole `zoom`, on a run no tile edge cuts: its layer draws there, and the
   *  run is at least the 14 x 16/24 px maplibre-gl 6.7.0 needs to place a
   *  symbol on a line (lib/closureStyle.ts's CLOSURE_NEAR_MIN_ZOOM). */
  function chainCarries(closure: TrailClosure, zoom: number): boolean {
    const chain = layer(closureCrossesId(CLUB_CLOSURE_LAYER_ID))
    const run = longestRunAtZ0(closure.place.geometry) ?? 0
    return (
      zoom >= (chain.minzoom ?? 0) &&
      run * 2 ** zoom >= (closureCrossImageSize() * 16) / 24
    )
  }

  /** The source's tile holding `[lon, lat]` at `zoom`, tiled as maplibre-gl
   *  6.7.0's GeoJSON source tiles it (source/geojson_source.ts): geojson-vt
   *  with the tolerance and the 128 px buffer in tile units, CSS px x 8192 /
   *  512, and the source's default maxzoom of 18. */
  function sourceTile(
    [lon, lat]: [number, number],
    zoom: number,
    rows: readonly TrailClosure[],
    tolerance = buildClubClosureSource().tolerance ?? 0.375,
  ) {
    const units = 8192 / 512
    const index = new GeoJSONVT(clubClosureFeatureCollection(rows) as never, {
      tolerance: tolerance * units,
      extent: 8192,
      buffer: 128 * units,
      maxZoom: 18,
    })
    const x = Math.floor(((lon + 180) / 360) * 2 ** zoom)
    const sin = Math.sin((lat * Math.PI) / 180)
    const y = Math.floor(
      (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * 2 ** zoom,
    )
    return index.getTile(zoom, x, y)
  }

  it('keeps one bold ✕ on a 20 m closure at z9 and at z12, where the chain has no room for one', () => {
    const short = lineClosure(20)
    expect(farMarkDraws(short, 9)).toBe(true)
    expect(farMarkDraws(short, 12)).toBe(true)
    expect(chainCarries(short, 12)).toBe(false)
    // One: the far mark goes at the middle of each line it is handed
    // (`line-center`), and this closure is one line.
    const mark = layer(closureMarkId(CLUB_CLOSURE_LAYER_ID))
    expect((mark.layout as Record<string, unknown>)['symbol-placement']).toBe(
      'line-center',
    )
    expect(short.place.geometry.type).toBe('LineString')
  })

  it('crosses a 1000 m closure out with the chain at z12 and no bold ✕, as before', () => {
    const long = lineClosure(1000)
    expect(chainCarries(long, 12)).toBe(true)
    expect(farMarkDraws(long, 12)).toBe(false)
    expect(farMarkDraws(long, CLOSURE_NEAR_MIN_ZOOM)).toBe(false)
    // And far out it has its bold ✕, as every closure does.
    expect(farMarkDraws(long, 10)).toBe(true)
    expect(farMarkDraws(long, CLOSURE_MARK_MIN_ZOOM)).toBe(true)
    expect(farMarkDraws(long, CLOSURE_MARK_MIN_ZOOM - 1)).toBe(false)
  })

  it('lets go of the bold ✕ only once the longest run is 2.5 chain crosses long, so a run a tile edge cuts still has a mark', () => {
    // At z13 a chain cross is 14 px. A run of two crosses has room for the
    // chain on its own, and keeps the far mark anyway; one of three does not.
    expect(CLOSURE_MARK_UNTIL_CROSSES).toBe(2.5)
    const twoCrosses = lineClosure(metresFor(2 * closureCrossImageSize(), 13))
    const threeCrosses = lineClosure(metresFor(3 * closureCrossImageSize(), 13))
    expect(chainCarries(twoCrosses, 13)).toBe(true)
    expect(farMarkDraws(twoCrosses, 13)).toBe(true)
    expect(farMarkDraws(threeCrosses, 13)).toBe(false)
    expect(clubClosureChainFrom(threeCrosses.place.geometry)).toBe(13)
    // A run the chain can never carry keeps the far mark at every zoom.
    expect(
      clubClosureChainFrom({
        type: 'LineString',
        coordinates: [
          [-74, 41],
          [-74, 41],
        ],
      }),
    ).toBe(CLUB_CLOSURE_NEVER_CHAINED)
  })

  it('reads the handover off the longest of an area’s cut stretches, and gives a point or a shade none', () => {
    const long = lineClosure(1000).place.geometry.coordinates as number[][]
    const short = lineClosure(20).place.geometry.coordinates as number[][]
    expect(
      clubClosureChainFrom({
        type: 'MultiLineString',
        coordinates: [short, long.map(([lon, lat]) => [lon, lat + 0.01])],
      }),
    ).toBe(clubClosureChainFrom(lineClosure(1000).place.geometry))
    const { point, shade } = closures()
    expect(clubClosureChainFrom(point.place.geometry)).toBeNull()
    expect(clubClosureChainFrom(shade.place.geometry)).toBeNull()
  })

  it('never drops a short closure from a tile below z11, where only the far mark can show it', () => {
    // geojson-vt leaves out a line shorter than the source's tolerance, and
    // the far mark is placed on the line: at MapLibre's default 0.375 px this
    // 5 m closure is gone at z7, and at the source's own it is in every tile.
    const tiny = lineClosure(5)
    const at: [number, number] = [-74, 41]
    const ids = (tile: ReturnType<typeof sourceTile>) =>
      (tile?.features ?? []).map((feature) => feature.tags?.[CLUB_CLOSURE_ID_PROPERTY])
    expect(ids(sourceTile(at, CLOSURE_MARK_MIN_ZOOM, [tiny], 0.375))).toEqual([])
    for (let zoom = CLOSURE_MARK_MIN_ZOOM; zoom < CLOSURE_NEAR_MIN_ZOOM; zoom += 1) {
      expect(ids(sourceTile(at, zoom, [tiny])), `z${zoom}`).toEqual([tiny.notice_id])
      expect(farMarkDraws(tiny, zoom), `z${zoom}`).toBe(true)
    }
  })

  it('draws the preview recipe’s short closure, which the reader takes, with the bold ✕ at its z13 camera', () => {
    const short = validTrailClosure(shortClosureRow())
    expect(short).not.toBeNull()
    expect(farMarkDraws(short as TrailClosure, 13)).toBe(true)
    expect(chainCarries(short as TrailClosure, 13)).toBe(false)
  })
})

describe('putting the closures on a live map', () => {
  it('puts a line, an area’s cut stretches and a point in the source, each on its own geometry and keyed by its notice id', () => {
    const { line, area, point } = closures()
    const map = new MockMap({})
    map.sourceIds = [CLUB_CLOSURE_SOURCE_ID]
    map.styleLoaded = true

    attachClubClosureData(map as never, [line, area, point])

    // A line closure and an area's stretches also carry the zoom their chain
    // takes over (decision 198): both at CLOSURE_NEAR_MIN_ZOOM, the line 61
    // px long there and the park's longer stretch 31, each past 2.5 chain
    // crosses of 11.2 px. A point carries none.
    expect(map.sourceData.get(CLUB_CLOSURE_SOURCE_ID)).toEqual({
      type: 'FeatureCollection',
      features: [
        [line, { [CLUB_CLOSURE_CHAIN_FROM_PROPERTY]: CLOSURE_NEAR_MIN_ZOOM }],
        [area, { [CLUB_CLOSURE_CHAIN_FROM_PROPERTY]: CLOSURE_NEAR_MIN_ZOOM }],
        [point, {}],
      ].map(([closure, handover]) => ({
        type: 'Feature',
        geometry: (closure as TrailClosure).place.geometry,
        properties: {
          [CLUB_CLOSURE_ID_PROPERTY]: (closure as TrailClosure).notice_id,
          ...handover,
        },
      })),
    })
  })

  it('registers every sheet’s hatch before a shaded area reaches the source, and never twice', () => {
    const { shade } = closures()
    const map = new MockMap({})
    map.sourceIds = [CLUB_CLOSURE_SOURCE_ID]
    map.styleLoaded = true
    const order: string[] = []
    const addImage = map.addImage.bind(map)
    vi.spyOn(map, 'addImage').mockImplementation((id, image, options) => {
      order.push(`image ${id}`)
      return addImage(id, image, options)
    })
    const getSource = map.getSource.bind(map)
    vi.spyOn(map, 'getSource').mockImplementation((id: string) => {
      const source = getSource(id) as { setData: (data: unknown) => void } | undefined
      return source === undefined
        ? undefined
        : {
            setData: (data: unknown) => {
              order.push('data')
              source.setData(data)
            },
          }
    })

    attachClubClosureData(map as never, [shade])
    attachClubClosureData(map as never, [shade])

    expect(order).toEqual([
      ...SHADE_INKS.map((ink) => `image ${clubClosureShadeImageId(ink)}`),
      'data',
      'data',
    ])
    const data = map.sourceData.get(CLUB_CLOSURE_SOURCE_ID) as {
      features: Array<{ geometry: unknown }>
    }
    expect(data.features[0].geometry).toEqual(shade.place.geometry)
  })
})

describe('touching a club closure', () => {
  /** A map holding the clubs' paper and point cross, a trail line, the
   *  hiker-reported tape, an ATC band, a waypoint pin and dot, a warning pin
   *  and a hazard area - every mark a touch can land on - with nothing
   *  drawn under the thumb until a test puts it there. */
  function tappableMap(): MockMap {
    const map = new MockMap({})
    map.layerIds = [
      HAZARD_FILL_LAYER_ID,
      CLUB_CLOSURE_SHADE_LAYER_ID,
      BLAZE_LAYER_ID,
      POI_LAYER_ID,
      POI_DOT_LAYER_ID,
      CLOSURE_LAYER_ID,
      CLUB_CLOSURE_LAYER_ID,
      POINT_LAYER_ID,
      ATC_UPDATE_LAYER_ID,
      WARNING_LAYER_ID,
    ]
    return map
  }

  const club = (id: string) => [{ properties: { [CLUB_CLOSURE_ID_PROPERTY]: id } }]
  const touch = { point: { x: 120, y: 240 } }

  it('opens the closure’s sheet from a touch on its crossed-out line or on its point’s cross', () => {
    const map = tappableMap()
    const onSelect = vi.fn()
    attachClubClosureTaps(map as unknown as MapLibreMap, onSelect)

    map.renderedFeatures.set(CLUB_CLOSURE_LAYER_ID, club('example:line'))
    map.emit('click', touch)
    map.renderedFeatures.delete(CLUB_CLOSURE_LAYER_ID)
    map.renderedFeatures.set(POINT_LAYER_ID, club('example:bridge'))
    map.emit('click', touch)
    map.renderedFeatures.delete(POINT_LAYER_ID)
    map.emit('click', touch)

    expect(onSelect.mock.calls).toEqual([['example:line'], ['example:bridge']])
  })

  it('yields to a warning pin, a waypoint pin and a hiker-reported closure’s tape, which rank above it', () => {
    const above: Array<[string, unknown[]]> = [
      [WARNING_LAYER_ID, [{ properties: { [WARNING_ID_PROPERTY]: 'r1' } }]],
      [POI_LAYER_ID, [{ properties: { [POI_ID_PROPERTY]: 'atc_shelters:1' } }]],
      [CLOSURE_LAYER_ID, [{ properties: { [CLOSURE_ID_PROPERTY]: 'c1' } }]],
    ]
    for (const [layerId, features] of above) {
      const map = tappableMap()
      map.renderedFeatures.set(CLUB_CLOSURE_LAYER_ID, club('example:line'))
      map.renderedFeatures.set(layerId, features)
      const onSelect = vi.fn()

      attachClubClosureTaps(map as unknown as MapLibreMap, onSelect)
      map.emit('click', touch)

      expect(onSelect, layerId).not.toHaveBeenCalled()
    }
  })

  /** What each mark ranked below a club closure answers for one touch, with
   *  that mark alone under the thumb, or with a club closure there too. */
  function answers(underneath: 'line' | 'atc' | 'dot' | 'hazard', withClub: boolean) {
    const map = tappableMap()
    if (withClub) map.renderedFeatures.set(CLUB_CLOSURE_LAYER_ID, club('example:line'))
    if (underneath === 'line') {
      map.renderedFeatures.set(BLAZE_LAYER_ID, [
        {
          properties: { id: 'centerline:1', source: 'centerline', blaze_color: 'White' },
          geometry: { type: 'LineString', coordinates: [] },
        },
      ])
      return tappedLineAt(map as unknown as MapLibreMap, touch.point)?.id ?? null
    }
    if (underneath === 'dot') {
      map.renderedFeatures.set(POI_DOT_LAYER_ID, [
        {
          properties: { [POI_ID_PROPERTY]: 'atc_springs:1' },
          geometry: { type: 'Point', coordinates: [0, 0] },
        },
      ])
      return poiIdAt(map as unknown as MapLibreMap, touch.point)
    }
    const onSelect = vi.fn()
    if (underneath === 'atc') {
      map.renderedFeatures.set(ATC_UPDATE_LAYER_ID, [
        { properties: { [ATC_UPDATE_ID_PROPERTY]: 'atc:1' } },
      ])
      attachAtcUpdateTaps(map as unknown as MapLibreMap, onSelect)
    } else {
      map.renderedFeatures.set(HAZARD_FILL_LAYER_ID, [
        { properties: { notice_id: 'h1' } },
      ])
      attachHazardTaps(map as unknown as MapLibreMap, onSelect)
    }
    map.emit('click', touch)
    return (onSelect.mock.calls[0]?.[0] as string | undefined) ?? null
  }

  it.each([
    ['the trail line', 'line'],
    ['an ATC band', 'atc'],
    ['a waypoint dot', 'dot'],
    ['a hazard area', 'hazard'],
  ] as const)(
    'takes the touch from %s under it, so one touch opens one sheet',
    (_, underneath) => {
      // Alone, the mark answers the touch; with a club closure over it, it
      // yields, and the closure's handler answers instead.
      expect(answers(underneath, false)).not.toBeNull()
      expect(answers(underneath, true)).toBeNull()
    },
  )

  const shaded = (id: string) => [{ properties: { [CLUB_CLOSURE_ID_PROPERTY]: id } }]

  it('opens a shaded area’s sheet from a touch inside it, the same sheet its list row opens (decision 191)', () => {
    const map = tappableMap()
    const onSelect = vi.fn()
    attachClubClosureTaps(map as unknown as MapLibreMap, onSelect)

    map.renderedFeatures.set(CLUB_CLOSURE_SHADE_LAYER_ID, shaded('example:closed-lands'))
    map.emit('click', touch)
    expect(clubClosureShadeIdAt(map as unknown as MapLibreMap, touch.point)).toBe(
      'example:closed-lands',
    )

    expect(onSelect.mock.calls).toEqual([['example:closed-lands']])
  })

  it.each([
    [
      'a warning pin',
      WARNING_LAYER_ID,
      [{ properties: { [WARNING_ID_PROPERTY]: 'r1' } }],
    ],
    [
      'a waypoint pin',
      POI_LAYER_ID,
      [{ properties: { [POI_ID_PROPERTY]: 'atc_shelters:1' } }],
    ],
    [
      'a waypoint dot',
      POI_DOT_LAYER_ID,
      [
        {
          properties: { [POI_ID_PROPERTY]: 'atc_springs:1' },
          geometry: { type: 'Point', coordinates: [0, 0] },
        },
      ],
    ],
    [
      'a hiker-reported closure’s tape',
      CLOSURE_LAYER_ID,
      [{ properties: { [CLOSURE_ID_PROPERTY]: 'c1' } }],
    ],
    [
      'an ATC band',
      ATC_UPDATE_LAYER_ID,
      [{ properties: { [ATC_UPDATE_ID_PROPERTY]: 'atc:1' } }],
    ],
    [
      'a trail line',
      BLAZE_LAYER_ID,
      [
        {
          properties: { id: 'centerline:1', source: 'centerline', blaze_color: 'White' },
          geometry: { type: 'LineString', coordinates: [] },
        },
      ],
    ],
  ] as const)(
    'leaves a touch inside a shaded area to %s drawn on it: the area is last in line',
    (_, layerId, features) => {
      const map = tappableMap()
      map.renderedFeatures.set(
        CLUB_CLOSURE_SHADE_LAYER_ID,
        shaded('example:closed-lands'),
      )
      map.renderedFeatures.set(layerId, [...features])
      const onSelect = vi.fn()

      attachClubClosureTaps(map as unknown as MapLibreMap, onSelect)
      map.emit('click', touch)

      expect(onSelect).not.toHaveBeenCalled()
    },
  )

  it('answers a crossed-out stretch inside a shaded area with the stretch’s closure, never both', () => {
    const map = tappableMap()
    map.renderedFeatures.set(CLUB_CLOSURE_SHADE_LAYER_ID, shaded('example:closed-lands'))
    map.renderedFeatures.set(CLUB_CLOSURE_LAYER_ID, club('example:line'))
    const onSelect = vi.fn()

    attachClubClosureTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', touch)

    expect(onSelect.mock.calls).toEqual([['example:line']])
  })

  it('takes a touch inside both a shaded area and a hazard area from the hazard area: a closure outranks an advisory', () => {
    const map = tappableMap()
    map.renderedFeatures.set(HAZARD_FILL_LAYER_ID, [{ properties: { notice_id: 'h1' } }])
    map.renderedFeatures.set(CLUB_CLOSURE_SHADE_LAYER_ID, shaded('example:closed-lands'))
    const onHazard = vi.fn()
    const onClub = vi.fn()

    attachHazardTaps(map as unknown as MapLibreMap, onHazard)
    attachClubClosureTaps(map as unknown as MapLibreMap, onClub)
    map.emit('click', touch)

    expect(onHazard).not.toHaveBeenCalled()
    expect(onClub.mock.calls).toEqual([['example:closed-lands']])
    // Alone, the hazard area still answers.
    map.renderedFeatures.delete(CLUB_CLOSURE_SHADE_LAYER_ID)
    map.emit('click', touch)
    expect(onHazard.mock.calls).toEqual([['h1']])
  })
})

describe('routing, which this change leaves alone', () => {
  it('reads no club closure in any router module: a route still goes through a drawn closure (the maintainer’s Q2, 2026-10-11)', () => {
    // "Build the map file now", whose option said routes still go through
    // these closures until a later change. Held here as the router's
    // modules never naming the file, its reader or its layers, so the day
    // routes do avoid them is a change somebody makes on purpose, here too.
    const router = [
      'lib/trailGraph.ts',
      'lib/trailGraphData.ts',
      'lib/trailGraphStore.ts',
      'lib/useTrailGraph.ts',
      'lib/route.ts',
      'lib/orgRoute.ts',
      'lib/orgRoutePath.ts',
      'lib/useOrgRoute.ts',
      'lib/dayHikeDraft.ts',
    ]
    for (const path of router) {
      const source = readFileSync(join(process.cwd(), 'src', path), 'utf8')
      for (const name of ['trail_closures', 'TrailClosure', 'clubClosure', 'obstructs']) {
        expect(source.includes(name), `${path} mentions ${name}`).toBe(false)
      }
    }
  })
})
