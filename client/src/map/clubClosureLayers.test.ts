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
  CLOSURE_LAYER_ID,
  CLOSURE_MARK_HALO_WIDTH,
  CLOSURE_MARK_MIN_ZOOM,
  CLOSURE_MARK_SIZE,
  CLOSURE_TRACE_OPACITY,
  closureLayerIds,
  closureMarkId,
  closurePointId,
} from '../lib/closureStyle'
import { ATC_UPDATE_LAYER_ID } from '../lib/atcUpdateStyle'
import type { TrailClosure } from '../lib/publishedConditions'
import { validTrailClosure } from '../lib/publishedNotices'
import { trailClosureRows } from '../../preview-shots/fixtures/clubClosures.mjs'
import {
  buildClubClosureLayers,
  buildClubClosureSource,
  CLUB_CLOSURE_LINE_FILTER,
  CLUB_CLOSURE_POINT_FILTER,
  CLUB_CLOSURE_SOURCE_ID,
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

/** The hand-made file's four closures, read by the app's own reader. */
function closures(): Record<'line' | 'area' | 'point' | 'greyed', TrailClosure> {
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
  }
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
  it('crosses a line closure out with exactly the mark every closure feed wears', () => {
    // "Only the id, the source, the filter and the spacing may differ"
    // (lib/closureStyle.ts): held as equality with the temporary-closure
    // feed's own four layers, paint and layout, rather than as constants.
    const club = closureLayerIds(CLUB_CLOSURE_LAYER_ID).map(layer)
    const temporary = buildClosureLayers('closures', { ground: GROUND, ink: INK })
    expect(temporary.map((built) => built.id)).toEqual(closureLayerIds(CLOSURE_LAYER_ID))
    club.forEach((built, index) => {
      expect((built as { source?: unknown }).source).toBe(CLUB_CLOSURE_SOURCE_ID)
      expect((built as { filter?: unknown }).filter).toEqual(CLUB_CLOSURE_LINE_FILTER)
      expect(built.paint, built.id).toEqual(temporary[index].paint)
      expect((built as { layout?: unknown }).layout, built.id).toEqual(
        (temporary[index] as { layout?: unknown }).layout,
      )
    })
  })

  it('draws a line and an area’s cut stretches on the line layers, and a point on the cross alone, as MapLibre’s tiler hands them over', () => {
    // The area's MultiLineString has to reach the LineString filter: if it
    // did not, every closed park would draw nothing. Run through the tiler
    // MapLibre's GeoJSON source uses (@maplibre/geojson-vt), not a guess at
    // what it emits.
    const { line, area, point } = closures()
    // The z10 tile holding the fixture: at z0 the tiler drops a line shorter
    // than its tolerance, about 29 km there, and every closure here is
    // shorter.
    const [lon, lat] = point.place.geometry.coordinates as [number, number]
    const z = 10
    const x = Math.floor(((lon + 180) / 360) * 2 ** z)
    const rad = (lat * Math.PI) / 180
    const y = Math.floor(
      ((1 - Math.log(Math.tan(rad) + 1 / Math.cos(rad)) / Math.PI) / 2) * 2 ** z,
    )
    const tile = new GeoJSONVT(
      clubClosureFeatureCollection([line, area, point]) as never,
    ).getTile(z, x, y)
    expect(tile?.features).toHaveLength(3)
    const drawnBy = (filter: unknown) =>
      (tile?.features ?? [])
        .filter((feature) => passes(filter, feature.type as 1 | 2 | 3))
        .map((feature) => feature.tags?.[CLUB_CLOSURE_ID_PROPERTY])
    expect(drawnBy(CLUB_CLOSURE_LINE_FILTER)).toEqual([line.notice_id, area.notice_id])
    expect(drawnBy(CLUB_CLOSURE_POINT_FILTER)).toEqual([point.notice_id])
    // And the source the style declares is there before any closure lands.
    expect(buildClubClosureSource()).toEqual({
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
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

  it('draws a closure the list greys at the same full strength: nothing in a layer reads a feature, and a feature carries only its id', () => {
    // The maintainer's "B: same mark" over fading it. A fade would need a
    // paint expression reading something off the feature; there is none, and
    // the only opacity anywhere is the trace's constant, the same on every
    // closure feed.
    const built = JSON.stringify(buildClubClosureLayers(GROUND, INK))
    expect(built).not.toContain('"get"')
    expect(built).not.toContain('feature-state')
    const opacities = buildClubClosureLayers(GROUND, INK).flatMap((each) =>
      Object.entries(each.paint ?? {}).filter(([property]) =>
        property.includes('opacity'),
      ),
    )
    expect(opacities).toEqual([['line-opacity', CLOSURE_TRACE_OPACITY]])
    const { greyed } = closures()
    expect(clubClosureFeatureCollection([greyed]).features[0].properties).toEqual({
      [CLUB_CLOSURE_ID_PROPERTY]: greyed.notice_id,
    })
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

describe('putting the closures on a live map', () => {
  it('puts a line, an area’s cut stretches and a point in the source, each on its own geometry and keyed by its notice id', () => {
    const { line, area, point } = closures()
    const map = new MockMap({})
    map.sourceIds = [CLUB_CLOSURE_SOURCE_ID]
    map.styleLoaded = true

    attachClubClosureData(map as never, [line, area, point])

    expect(map.sourceData.get(CLUB_CLOSURE_SOURCE_ID)).toEqual({
      type: 'FeatureCollection',
      features: [line, area, point].map((closure) => ({
        type: 'Feature',
        geometry: closure.place.geometry,
        properties: { [CLUB_CLOSURE_ID_PROPERTY]: closure.notice_id },
      })),
    })
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
