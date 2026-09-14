import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MockMap } from '../test/mocks/maplibre-gl'
import { DAY_HIKE_CASING_LAYER_ID } from '../map/dayHikeLayers'
import { useRouteHover } from './useRouteHover'

// The hover figure over a route being built (the review of #1374): where the
// pointer is when it is over the route's line, on a fine pointer, and null
// everywhere else. The mock answers queryRenderedFeatures from what a test
// says is drawn, the way the badge placer's tests drive it.

function pointer(fine: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: query === '(pointer: fine)' && fine,
    media: query,
    addEventListener: () => undefined,
    removeEventListener: () => undefined,
  }))
}

function routedMap(drawn: boolean): MockMap {
  const map = new MockMap({
    style: { layers: drawn ? [{ id: DAY_HIKE_CASING_LAYER_ID }] : [], sources: {} },
  })
  if (drawn) map.renderedFeatures.set(DAY_HIKE_CASING_LAYER_ID, [{ properties: {} }])
  return map
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('useRouteHover', () => {
  it('follows the pointer while it is over the route, and lets go when it leaves', () => {
    pointer(true)
    const map = routedMap(true)
    const { result } = renderHook(() =>
      useRouteHover(map as unknown as MapLibreMap, true),
    )
    expect(result.current).toBeNull()

    act(() => map.emit('mousemove', { point: { x: 120, y: 300 } }))
    expect(result.current).toEqual({ x: 120, y: 300 })

    act(() => map.emit('mouseout', {}))
    expect(result.current).toBeNull()
  })

  it('is null over the map where the route is not drawn under the pointer', () => {
    pointer(true)
    const map = routedMap(true)
    const { result } = renderHook(() =>
      useRouteHover(map as unknown as MapLibreMap, true),
    )
    map.renderedFeatures.set(DAY_HIKE_CASING_LAYER_ID, [])
    act(() => map.emit('mousemove', { point: { x: 10, y: 10 } }))
    expect(result.current).toBeNull()
  })

  it('does nothing on a coarse pointer - a touch has no hover', () => {
    pointer(false)
    const map = routedMap(true)
    const { result } = renderHook(() =>
      useRouteHover(map as unknown as MapLibreMap, true),
    )
    act(() => map.emit('mousemove', { point: { x: 120, y: 300 } }))
    expect(result.current).toBeNull()
  })

  it('is null the moment the builder closes, and stops listening', () => {
    pointer(true)
    const map = routedMap(true)
    const { result, rerender } = renderHook(
      ({ enabled }: { enabled: boolean }) =>
        useRouteHover(map as unknown as MapLibreMap, enabled),
      { initialProps: { enabled: true } },
    )
    act(() => map.emit('mousemove', { point: { x: 120, y: 300 } }))
    expect(result.current).not.toBeNull()

    rerender({ enabled: false })
    expect(result.current).toBeNull()
    act(() => map.emit('mousemove', { point: { x: 130, y: 310 } }))
    expect(result.current).toBeNull()
  })
})
