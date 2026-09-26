import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { SETTLE_MS, useDrawnPoiCounts } from './useDrawnPoiCounts'
import {
  POI_ID_PROPERTY,
  POI_LAYER_ID,
  POI_PIN_MIN_ZOOM,
  POI_SOURCE_ID,
} from '../map/poiLayers'
import { poiIconId } from '../map/poiIcons'
import { TRAIL_SOURCE_PROPERTY } from '../map/drawnBlazes'
import { BLAZE_LAYER_ID } from '../map/style'
import { MockMap } from '../test/mocks/maplibre-gl'

// The part a plain read in the render would get wrong: `queryRenderedFeatures`
// reflects the LAST RENDERED FRAME, so the count has to be taken when the map
// has settled - on `idle` or after SETTLE_MS without a frame, never on `move`
// (#528, #1538).

afterEach(() => {
  vi.useRealTimers()
})

/**
 * A map whose waypoints can be counted: the pin layer in the style, the
 * waypoint source loaded and the pin artwork registered. `ready: false` is a
 * cold start - the layer is there, nothing else is yet.
 */
function mapWith(features: unknown[], zoom = 14, { ready = true } = {}) {
  const map = new MockMap({
    style: {
      layers: [{ id: POI_LAYER_ID }, { id: BLAZE_LAYER_ID }],
      sources: { pois: {} },
    },
    zoom,
  })
  map.renderedFeatures.set(POI_LAYER_ID, features)
  const makeReady = () => {
    map.loadedSources.add(POI_SOURCE_ID)
    map.addImage(poiIconId('water', 'high'), {})
  }
  if (ready) makeReady()
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
    fireRender: () => (handlers.render ?? []).forEach((handler) => handler()),
    idleHandlers: () => (handlers.idle ?? []).length,
    renderHandlers: () => (handlers.render ?? []).length,
    queries: () => map.featureQueries.length,
    makeReady,
    setFeatures: (next: unknown[]) => map.renderedFeatures.set(POI_LAYER_ID, next),
    setLines: (next: unknown[]) => map.renderedFeatures.set(BLAZE_LAYER_ID, next),
  }
}

const trail = (id: number, source: string) => ({
  id,
  properties: { [TRAIL_SOURCE_PROPERTY]: source },
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

  it('subscribes to idle and to frames, and never to move', () => {
    const { map } = mapWith([])
    const on = vi.spyOn(map, 'on')

    renderHook(() => useDrawnPoiCounts(map))

    // Nothing recomputes mid-fling: that is a query per frame for a number
    // nobody can read yet, and it would lag anyway. `render` is listened to
    // only to notice when frames STOP - see the settle tests below.
    expect(on.mock.calls.map(([event]) => event).sort()).toEqual(['idle', 'render'])
  })

  it('stops listening when it goes away', () => {
    const { map, idleHandlers, renderHandlers } = mapWith([])
    const { unmount } = renderHook(() => useDrawnPoiCounts(map))
    expect(idleHandlers()).toBe(1)
    expect(renderHandlers()).toBe(1)

    unmount()

    expect(idleHandlers()).toBe(0)
    expect(renderHandlers()).toBe(0)
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

describe('a count that cannot stick at a false zero (#1538)', () => {
  it('measures once the map stops drawing, even when idle never comes', () => {
    // THE BUG. MapLibre fires `idle` only once every source has every tile,
    // and one basemap tile that fails holds it off for good. Traced against
    // the UA bucket over Manhattan on 2026-09-26: forty pins drawn, `osm`
    // still failing at 30 s, no `idle`, and the chip reading "0 of 1568
    // waypoints fit" - the count taken up front, before any pin could draw.
    vi.useFakeTimers()
    const { map, fireRender, setFeatures, makeReady } = mapWith([], 14, {
      ready: false,
    })
    const { result } = renderHook(() => useDrawnPoiCounts(map))

    // The waypoints load, the pins are drawn, frames stop. No idle.
    makeReady()
    setFeatures([pin('w1', 'water'), pin('w2', 'water')])
    act(() => fireRender())
    act(() => {
      vi.advanceTimersByTime(SETTLE_MS)
    })

    expect(result.current.counts).toEqual(new Map([['water', 2]]))
  })

  it('publishes no count before a pin could be drawn, rather than zero', () => {
    // The measurement up front runs before the style has loaded. With nothing
    // placed it reads zero, and a zero here is the chip saying the map hides
    // everything. Unmeasured shows no chip, which is the honest cold start.
    const { map } = mapWith([], 14, { ready: false })

    const { result } = renderHook(() => useDrawnPoiCounts(map))

    expect(result.current.counts).toBeUndefined()
  })

  it.each([
    ['the waypoint source has not loaded', 'source'],
    ['the pin artwork has not arrived', 'artwork'],
  ])('holds the count back while %s', (_, missing) => {
    const { map } = mapWith([], 14, { ready: false })
    const mock = map as unknown as MockMap
    if (missing === 'artwork') mock.loadedSources.add(POI_SOURCE_ID)
    else mock.addImage(poiIconId('water', 'high'), {})

    const { result } = renderHook(() => useDrawnPoiCounts(map))

    expect(result.current.counts).toBeUndefined()
  })

  it('waits for the frames to stop, rather than measuring each one', () => {
    // A pan is dozens of frames. Each only pushes the settle back, so the map
    // is queried once after it ends, not once per frame.
    vi.useFakeTimers()
    const { map, fireRender, queries } = mapWith([pin('w1', 'water')])
    renderHook(() => useDrawnPoiCounts(map))
    const afterMount = queries()

    for (let frame = 0; frame < 30; frame += 1) {
      act(() => fireRender())
      act(() => {
        vi.advanceTimersByTime(16)
      })
    }
    expect(queries()).toBe(afterMount)

    act(() => {
      vi.advanceTimersByTime(SETTLE_MS)
    })
    // One settled frame: the waypoint query and the trail-line query.
    expect(queries()).toBe(afterMount + 2)
  })

  it('drops a pending settle when it goes away', () => {
    vi.useFakeTimers()
    const { map, fireRender, queries } = mapWith([pin('w1', 'water')])
    const { unmount } = renderHook(() => useDrawnPoiCounts(map))
    act(() => fireRender())
    const beforeUnmount = queries()

    unmount()
    vi.advanceTimersByTime(SETTLE_MS * 2)

    expect(queries()).toBe(beforeUnmount)
  })

  it('still answers the zoom and the ghosting sentence while the waypoints cannot be counted', () => {
    // Only the counts wait. Below the seam, or with no waypoint on the map,
    // the pin artwork may never be registered, and the legend's other two
    // answers must not wait for it.
    const { map, setLines, fireIdle } = mapWith([], POI_PIN_MIN_ZOOM - 1, {
      ready: false,
    })
    setLines([trail(1, 'centerline'), trail(2, 'oprhp_trails')])

    const { result } = renderHook(() => useDrawnPoiCounts(map))
    act(() => fireIdle())

    expect(result.current.counts).toBeUndefined()
    expect(result.current.belowPoiZoom).toBe(true)
    expect(result.current.ghostedTrailsDrawn).toBe(true)
  })
})

describe('the ghosting sentence (#783)', () => {
  it('is false before there is a map, which is the legend saying nothing', () => {
    // Not "no other trails are here" - a map that has not drawn yet has not
    // answered. False is what makes the legend omit the sentence entirely,
    // which is the honest rendering of an unmeasured cold start.
    const { result } = renderHook(() => useDrawnPoiCounts(null))

    expect(result.current.ghostedTrailsDrawn).toBe(false)
  })

  it('is true as soon as one line from another network is on screen', () => {
    const { map, setLines, fireIdle } = mapWith([])
    setLines([trail(1, 'centerline'), trail(2, 'oprhp_trails')])

    const { result } = renderHook(() => useDrawnPoiCounts(map))
    act(() => fireIdle())

    expect(result.current.ghostedTrailsDrawn).toBe(true)
  })

  it('is false on a map drawing only the chosen system', () => {
    const { map, setLines, fireIdle } = mapWith([])
    setLines([trail(1, 'centerline'), trail(2, 'side_trails')])

    const { result } = renderHook(() => useDrawnPoiCounts(map))
    act(() => fireIdle())

    expect(result.current.ghostedTrailsDrawn).toBe(false)
  })

  it('is decided on the same settled frame as the waypoints', () => {
    // ONE LISTENER, NOT TWO, and this is the assertion that says so. It used
    // to be made of the blaze counts, which were the hook's other `idle`
    // reader until they were removed on 2026-08-25; the guarantee outlived
    // them, so the test moved rather than going with them. Two listeners
    // would let the legend show waypoint counts from this camera beside a
    // ghosting sentence decided at the last one.
    const { map, setFeatures, setLines, fireIdle, idleHandlers } = mapWith([])

    const { result } = renderHook(() => useDrawnPoiCounts(map))
    setFeatures([pin('w1', 'water')])
    setLines([trail(1, 'oprhp_trails')])
    act(() => fireIdle())

    expect(idleHandlers()).toBe(1)
    expect(result.current.counts?.get('water')).toBe(1)
    expect(result.current.ghostedTrailsDrawn).toBe(true)
  })
})
