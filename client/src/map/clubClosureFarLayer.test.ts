// The small ✕ every club closure gets at z5 and z6 (Q22 of #1805 — dlt → dbt
// re-platform as one go/no-go change: the maintainer's variant A, "small ✕,
// thinned", 2026-10-15): the layer as the built style holds it, where its one
// point per closure sits, the source it is filled into, its repaint on a sheet
// change, and a touch on it opening the closure's sheet.

import { describe, expect, it, vi } from 'vitest'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MockMap } from '../test/mocks/maplibre-gl'
import {
  CLOSURE_CROSS_ARM,
  CLOSURE_CROSS_ICON_ID,
  CLOSURE_CROSS_STROKE,
  CLOSURE_INK,
  CLOSURE_MARK_MIN_ZOOM,
  closurePointId,
} from '../lib/closureStyle'
import type { TrailClosure } from '../lib/publishedConditions'
import { validTrailClosure } from '../lib/publishedNotices'
import { trailClosureRows } from '../../preview-shots/fixtures/clubClosures.mjs'
import {
  buildClubClosureFarLayer,
  CLOSURE_CROSS_HALO_WIDTH_FAR,
  CLUB_CLOSURE_FAR_CROSS_PADDING,
  CLUB_CLOSURE_FAR_CROSS_SIZE,
  CLUB_CLOSURE_FAR_LAYER_ID,
  CLUB_CLOSURE_FAR_MIN_ZOOM,
  CLUB_CLOSURE_FAR_SOURCE_ID,
  CLUB_CLOSURE_SOURCE_ID,
  clubClosureFarPoint,
} from './clubClosureLayers'
import {
  attachClubClosureData,
  attachClubClosureTaps,
  clubClosureFarCollection,
} from './clubClosureTaps'
import { CLUB_CLOSURE_ID_PROPERTY } from './closureLayers'
import {
  attachMapAppearance,
  BACKDROP_LAYER_ID,
  buildMapStyle,
  closureInk,
  closureTapeGround,
  CLUB_CLOSURE_LAYER_ID,
} from './style'
import { WARNING_ID_PROPERTY, WARNING_LAYER_ID } from './warningLayers'

/** The hand-made file's closures, read by the app's own reader. */
function closures() {
  const rows = trailClosureRows()
  const read = (row: unknown): TrailClosure => {
    const closure = validTrailClosure(row)
    if (closure === null) throw new Error('the fixture row did not read')
    return closure
  }
  return {
    line: read(rows.line),
    area: read(rows.area),
    point: read(rows.point),
    shade: read(rows.shade),
  }
}

function builtStyle() {
  return buildMapStyle({
    topoArchiveUrl: 'pmtiles://ourhike-corridor',
    trailsUrl: '/data/trails.geojson',
  })
}

describe('the small ✕ at z5 and z6, as the built style holds it', () => {
  it('draws one closure-ink ✕ of about 7.2 px on a 1.5 px paper ring, thinned by collision with 2 px padding, from its own source', () => {
    const layers = builtStyle().layers as Array<{ id: string }>
    const far = layers.find((layer) => layer.id === CLUB_CLOSURE_FAR_LAYER_ID)
    expect(far).toEqual({
      id: CLUB_CLOSURE_FAR_LAYER_ID,
      type: 'symbol',
      source: CLUB_CLOSURE_FAR_SOURCE_ID,
      minzoom: 5,
      maxzoom: 7,
      layout: {
        'icon-image': CLOSURE_CROSS_ICON_ID,
        'icon-size': CLUB_CLOSURE_FAR_CROSS_SIZE,
        // Thinned: a ✕ that would overlap one already placed is dropped.
        'icon-allow-overlap': false,
        'icon-ignore-placement': false,
        'icon-padding': 2,
      },
      paint: {
        // The closure ink on the day sheet's paper, never the closure red
        // (#1677): a red ✕ would vanish on a red trail.
        'icon-color': CLOSURE_INK,
        'icon-halo-color': '#ffffff',
        'icon-halo-width': 1.5,
      },
    })
    expect(CLUB_CLOSURE_FAR_CROSS_PADDING).toBe(2)
    expect(CLOSURE_CROSS_HALO_WIDTH_FAR).toBe(1.5)
    // The chain's own cross at full size: 7.2 px of ink across.
    expect(2 * (CLOSURE_CROSS_ARM + CLOSURE_CROSS_STROKE / 2)).toBeCloseTo(7.2)
    expect(builtStyle().sources[CLUB_CLOSURE_FAR_SOURCE_ID]).toEqual({
      type: 'geojson',
      data: { type: 'FeatureCollection', features: [] },
    })
  })

  it('stops at z7, where the full drawing starts, so no zoom draws both', () => {
    const club = (
      builtStyle().layers as Array<{ id: string; source?: string; minzoom?: number }>
    )
      .filter((layer) => layer.source === CLUB_CLOSURE_SOURCE_ID)
      .map((layer) => layer.minzoom ?? 0)
    expect(CLUB_CLOSURE_FAR_MIN_ZOOM).toBe(5)
    expect(CLOSURE_MARK_MIN_ZOOM).toBe(7)
    expect(Math.min(...club)).toBe(CLOSURE_MARK_MIN_ZOOM)
    expect(buildClubClosureFarLayer('#fff', '#000').maxzoom).toBe(Math.min(...club))
  })

  it('sits above the clubs’ own layers, just after their point cross', () => {
    const ids = (builtStyle().layers as Array<{ id: string }>).map((layer) => layer.id)
    expect(ids.indexOf(CLUB_CLOSURE_FAR_LAYER_ID)).toBe(
      ids.indexOf(closurePointId(CLUB_CLOSURE_LAYER_ID)) + 1,
    )
  })

  it('repaints the ✕ in the sheet’s ink and paper on a sheet change', () => {
    const map = new MockMap({})
    map.layerIds = [BACKDROP_LAYER_ID, CLUB_CLOSURE_FAR_LAYER_ID]
    const appearance = { mapStyle: 'night_hike', redLight: true } as const

    attachMapAppearance(map as never, appearance)

    expect(map.paintProperties.get(`${CLUB_CLOSURE_FAR_LAYER_ID}/icon-color`)).toBe(
      closureInk(appearance),
    )
    expect(map.paintProperties.get(`${CLUB_CLOSURE_FAR_LAYER_ID}/icon-halo-color`)).toBe(
      closureTapeGround(appearance),
    )
  })
})

describe('where a closure’s ✕ sits (clubClosureFarPoint)', () => {
  it('puts a line closure’s ✕ halfway along its longest run', () => {
    expect(
      clubClosureFarPoint({
        type: 'MultiLineString',
        coordinates: [
          [
            [0, 0],
            [0.1, 0],
          ],
          [
            [1, 1],
            [1, 1.2],
            [1.2, 1.2],
          ],
        ],
      }),
    ).toEqual([1, 1.2])
  })

  it('puts a point closure’s ✕ on its point, and a MultiPoint’s on its first', () => {
    expect(clubClosureFarPoint({ type: 'Point', coordinates: [-100, 38] })).toEqual([
      -100, 38,
    ])
    expect(
      clubClosureFarPoint({
        type: 'MultiPoint',
        coordinates: [
          [-100.2, 38.7],
          [-100.1, 38.7],
        ],
      }),
    ).toEqual([-100.2, 38.7])
  })

  it('puts a shaded area’s ✕ in the middle of its outer ring’s box', () => {
    expect(
      clubClosureFarPoint({
        type: 'Polygon',
        coordinates: [
          [
            [0, 0],
            [4, 0],
            [4, 2],
            [0, 2],
            [0, 0],
          ],
        ],
      }),
    ).toEqual([2, 1])
  })
})

describe('the ✕s on a live map', () => {
  it('fills the ✕s’ source with one point per closure, keyed by its notice id', () => {
    const { line, area, point, shade } = closures()
    const map = new MockMap({})
    map.sourceIds = [CLUB_CLOSURE_SOURCE_ID, CLUB_CLOSURE_FAR_SOURCE_ID]
    map.styleLoaded = true

    attachClubClosureData(map as never, [line, area, point, shade])

    const data = map.sourceData.get(CLUB_CLOSURE_FAR_SOURCE_ID) as {
      features: Array<{ geometry: { type: string }; properties: Record<string, unknown> }>
    }
    expect(data).toEqual(clubClosureFarCollection([line, area, point, shade]))
    expect(data.features.map((feature) => feature.properties)).toEqual(
      [line, area, point, shade].map((closure) => ({
        [CLUB_CLOSURE_ID_PROPERTY]: closure.notice_id,
      })),
    )
    expect(new Set(data.features.map((feature) => feature.geometry.type))).toEqual(
      new Set(['Point']),
    )
  })

  it('opens the sheet of the closure whose ✕ won the spot, and nothing for an empty touch', () => {
    const map = new MockMap({})
    map.layerIds = [CLUB_CLOSURE_LAYER_ID, CLUB_CLOSURE_FAR_LAYER_ID, WARNING_LAYER_ID]
    const onSelect = vi.fn()
    attachClubClosureTaps(map as unknown as MapLibreMap, onSelect)
    const touch = { point: { x: 120, y: 240 } }

    map.renderedFeatures.set(CLUB_CLOSURE_FAR_LAYER_ID, [
      { properties: { [CLUB_CLOSURE_ID_PROPERTY]: 'usfs:fire-closure' } },
    ])
    map.emit('click', touch)
    map.renderedFeatures.delete(CLUB_CLOSURE_FAR_LAYER_ID)
    map.emit('click', touch)

    expect(onSelect.mock.calls).toEqual([['usfs:fire-closure']])
  })

  it('yields a touch on the ✕ to a warning pin there, which ranks above it', () => {
    const map = new MockMap({})
    map.layerIds = [CLUB_CLOSURE_LAYER_ID, CLUB_CLOSURE_FAR_LAYER_ID, WARNING_LAYER_ID]
    map.renderedFeatures.set(CLUB_CLOSURE_FAR_LAYER_ID, [
      { properties: { [CLUB_CLOSURE_ID_PROPERTY]: 'usfs:fire-closure' } },
    ])
    map.renderedFeatures.set(WARNING_LAYER_ID, [
      { properties: { [WARNING_ID_PROPERTY]: 'r1' } },
    ])
    const onSelect = vi.fn()

    attachClubClosureTaps(map as unknown as MapLibreMap, onSelect)
    map.emit('click', { point: { x: 120, y: 240 } })

    expect(onSelect).not.toHaveBeenCalled()
  })
})
