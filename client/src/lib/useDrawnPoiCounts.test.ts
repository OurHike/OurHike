import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { useDrawnPoiCounts } from './useDrawnPoiCounts'
import { POI_ID_PROPERTY, POI_LAYER_ID, POI_PIN_MIN_ZOOM } from '../map/poiLayers'
import { BLAZE_COLOR_PROPERTY } from '../map/drawnBlazes'
import { BLAZE_LAYER_ID } from '../map/style'
import { MockMap } from '../test/mocks/maplibre-gl'

// The part a plain read in the render would get wrong: `queryRenderedFeatures`
// reflects the LAST RENDERED FRAME, so the count has to be taken when the map
// has settled - on `idle`, never on `move` (#528).

function mapWith(features: unknown[], zoom = 14) {
  const map = new MockMap({
    style: {
      layers: [{ id: POI_LAYER_ID }, { id: BLAZE_LAYER_ID }],
      sources: { pois: {} },
    },
    zoom,
  })
  map.renderedFeatures.set(POI_LAYER_ID, features)
  const handlers: Record<string, (() => void)[]> = {}
  // The mock has no event plumbing for `idle`, so this adds just enough to let
  // a test fire one - which is the whole behaviour under test.
  const withEvents = Object.assign(map, {
    getZoom: () => zoom,
    on: (event: string, handler: () => void) => {
      ;(handlers[event] ??= []).push(handler)
      return withEvents
    },
    off: (event: string, handler: () => void) => {
      handlers[event] = (handlers[event] ?? []).filter((each) => each !== handler)
      return withEvents
    },
  })
  return {
    map: withEvents as unknown as MapLibreMap,
    fireIdle: () => (handlers.idle ?? []).forEach((handler) => handler()),
    idleHandlers: () => (handlers.idle ?? []).length,
    setFeatures: (next: unknown[]) => map.renderedFeatures.set(POI_LAYER_ID, next),
    setLines: (next: unknown[]) => map.renderedFeatures.set(BLAZE_LAYER_ID, next),
  }
}

const trail = (id: number, blaze: string) => ({
  id,
  properties: { [BLAZE_COLOR_PROPERTY]: blaze },
})

const pin = (id: string, poi_type: string) => ({
  properties: { [POI_ID_PROPERTY]: id, poi_type, confidence: 'high' },
})

describe('useDrawnPoiCounts', () => {
  it('is unmeasured before there is a map', () => {
    // Undefined rather than empty: an empty map renders as "0 shown", which
    // would claim a drop nothing has measured.
    const { result } = renderHook(() => useDrawnPoiCounts(null))

    expect(result.current.counts).toBeUndefined()
  })

  it('measures once up front rather than waiting for a move', () => {
    // The map may already be idle by the time the effect runs, and waiting for
    // the next `idle` would leave the panel unmeasured until the hiker happened
    // to pan.
    const { map } = mapWith([pin('w1', 'water')])

    const { result } = renderHook(() => useDrawnPoiCounts(map))

    expect(result.current.counts).toEqual(new Map([['water', 1]]))
  })

  it('re-measures when the map settles', () => {
    const { map, fireIdle, setFeatures } = mapWith([pin('w1', 'water')])
    const { result } = renderHook(() => useDrawnPoiCounts(map))

    setFeatures([pin('w1', 'water'), pin('w2', 'water')])
    act(() => fireIdle())

    expect(result.current.counts).toEqual(new Map([['water', 2]]))
  })

  it('subscribes to idle and not to move', () => {
    const { map } = mapWith([])
    const on = vi.spyOn(map, 'on')

    renderHook(() => useDrawnPoiCounts(map))

    // Nothing recomputes mid-fling: that is a query per frame for a number
    // nobody can read yet, and it would lag anyway.
    for (const [event] of on.mock.calls) expect(event).toBe('idle')
  })

  it('stops listening when it goes away', () => {
    const { map, idleHandlers } = mapWith([])
    const { unmount } = renderHook(() => useDrawnPoiCounts(map))
    expect(idleHandlers()).toBe(1)

    unmount()

    expect(idleHandlers()).toBe(0)
  })

  it('reports being below the zoom pins are drawn at', () => {
    const { map } = mapWith([], POI_PIN_MIN_ZOOM - 1)

    const { result } = renderHook(() => useDrawnPoiCounts(map))

    expect(result.current.belowPoiZoom).toBe(true)
  })

  it('does not report that at the zoom pins start at', () => {
    const { map } = mapWith([pin('w1', 'water')], POI_PIN_MIN_ZOOM)

    const { result } = renderHook(() => useDrawnPoiCounts(map))

    expect(result.current.belowPoiZoom).toBe(false)
  })

  it('goes back to unmeasured when the map is torn down', () => {
    // A map being replaced is not a map drawing nothing.
    const { map } = mapWith([pin('w1', 'water')])
    const { result, rerender } = renderHook(
      ({ current }: { current: MapLibreMap | null }) => useDrawnPoiCounts(current),
      { initialProps: { current: map as MapLibreMap | null } },
    )
    expect(result.current.counts?.size).toBe(1)

    rerender({ current: null })

    expect(result.current.counts).toBeUndefined()
  })
})

describe('the blazes in view (#782)', () => {
  it('is empty before there is a map, which is what the legend renders as nothing', () => {
    // Unlike the waypoint counts, empty is the right answer here rather than
    // undefined: the legend guards its blaze list on `length > 0`, so there
    // is no "measured and none" state for empty to be confused with.
    const { result } = renderHook(() => useDrawnPoiCounts(null))

    expect(result.current.blazes).toEqual([])
  })

  it('reports what the map is drawing, most-drawn first', () => {
    const { map, setLines, fireIdle } = mapWith([])
    setLines([trail(1, 'Blue'), trail(2, 'Blue'), trail(3, 'White')])

    const { result } = renderHook(() => useDrawnPoiCounts(map))
    act(() => fireIdle())

    expect(result.current.blazes).toEqual([
      { blaze: 'Blue', count: 2 },
      { blaze: 'White', count: 1 },
    ])
  })

  it('orders ties by name, so rows do not reshuffle between frames', () => {
    // A legend whose rows swap places while a hiker reads them is worse than
    // one that is merely unsorted.
    const { map, setLines, fireIdle } = mapWith([])
    setLines([trail(1, 'White'), trail(2, 'Aqua'), trail(3, 'Blue')])

    const { result } = renderHook(() => useDrawnPoiCounts(map))
    act(() => fireIdle())

    expect(result.current.blazes.map((row) => row.blaze)).toEqual([
      'Aqua',
      'Blue',
      'White',
    ])
  })

  it('measures blazes on the same settled frame as the waypoints', () => {
    // One listener, not two. Two would let the legend show waypoint counts
    // from this camera beside blaze counts from the last one.
    const { map, setFeatures, setLines, fireIdle, idleHandlers } = mapWith([])

    const { result } = renderHook(() => useDrawnPoiCounts(map))
    setFeatures([pin('w1', 'water')])
    setLines([trail(1, 'Aqua')])
    act(() => fireIdle())

    expect(idleHandlers()).toBe(1)
    expect(result.current.counts?.get('water')).toBe(1)
    expect(result.current.blazes).toEqual([{ blaze: 'Aqua', count: 1 }])
  })
})
