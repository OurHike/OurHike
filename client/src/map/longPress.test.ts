import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MockMap } from '../test/mocks/maplibre-gl'
import {
  attachLongPress,
  LONG_PRESS_MS,
  LONG_PRESS_SLOP_PX,
  type PressAt,
  type PressPoint,
} from './longPress'

// Press and hold (#1137), and almost all of it is about what must NOT fire.
//
// A press, a pan and a pinch begin with the same event; only time and movement
// separate them. Every test below that ends in `not.toHaveBeenCalled()` is one
// of those separations, and they are the point of the module - a plate that
// opens when somebody meant to drag the map is worse than no plate, because it
// takes the map away at the moment they were using it.

const AT = { lngLat: { lat: 37.3, lng: -80.4 }, point: { x: 120, y: 240 } }

function press(map: MockMap, event: Record<string, unknown> = AT) {
  map.emit('touchstart', event)
}

describe('press and hold', () => {
  let map: MockMap
  let onLongPress: ReturnType<typeof vi.fn<(at: PressAt, point: PressPoint) => void>>
  let detach: () => void

  beforeEach(() => {
    vi.useFakeTimers()
    map = new MockMap({})
    onLongPress = vi.fn()
    detach = attachLongPress(map as unknown as MapLibreMap, onLongPress)
  })

  afterEach(() => {
    detach()
    vi.useRealTimers()
    MockMap.instances = []
  })

  it('fires while the finger is still down, not on release', () => {
    // The behaviour a phone has already taught this hiker: the thing appears
    // under your thumb. A press that only resolved on release would leave
    // somebody holding a finger on the map with no idea anything was happening.
    press(map)
    expect(onLongPress).not.toHaveBeenCalled()

    vi.advanceTimersByTime(LONG_PRESS_MS)

    expect(onLongPress).toHaveBeenCalledTimes(1)
    expect(onLongPress).toHaveBeenCalledWith(
      { lat: 37.3, lon: -80.4 },
      { x: 120, y: 240 },
    )
  })

  it('does not fire a moment early', () => {
    press(map)
    vi.advanceTimersByTime(LONG_PRESS_MS - 1)
    expect(onLongPress).not.toHaveBeenCalled()
  })

  it('gives the touch up the moment MapLibre starts moving the map', () => {
    // THE WHOLE OF THIS MODULE'S DEFERENCE, in one test. `movestart` is the
    // library saying "this touch was a drag or a zoom, I am acting on it".
    // Nothing here suspends the built-in handlers or calls preventDefault, so
    // a hiker dragging the map never has to fight a plate for it.
    press(map)
    map.emit('movestart')
    vi.advanceTimersByTime(LONG_PRESS_MS * 4)

    expect(onLongPress).not.toHaveBeenCalled()
  })

  it('cancels when the finger drifts further than the slop', () => {
    press(map)
    map.emit('touchmove', { ...AT, point: { x: 120 + LONG_PRESS_SLOP_PX + 1, y: 240 } })
    vi.advanceTimersByTime(LONG_PRESS_MS)

    expect(onLongPress).not.toHaveBeenCalled()
  })

  it('survives a wobble inside the slop, which is what a held hand does', () => {
    // The reason the slop is larger than poiTaps.ts's 3 px: that number is
    // about which pin you meant. This one is about whether you moved at all
    // over half a second, and a hand at arm's length does not sit inside three
    // pixels for that long.
    press(map)
    map.emit('touchmove', { ...AT, point: { x: 123, y: 244 } })
    vi.advanceTimersByTime(LONG_PRESS_MS)

    expect(onLongPress).toHaveBeenCalledTimes(1)
  })

  it('measures drift from the press, not from the last move', () => {
    // Three moves of 5 px each is 15 px from where the finger landed, which is
    // past the slop - and would pass a guard that only compared consecutive
    // points. A slow drag is still a drag.
    press(map)
    map.emit('touchmove', { ...AT, point: { x: 125, y: 240 } })
    map.emit('touchmove', { ...AT, point: { x: 130, y: 240 } })
    map.emit('touchmove', { ...AT, point: { x: 135, y: 240 } })
    vi.advanceTimersByTime(LONG_PRESS_MS)

    expect(onLongPress).not.toHaveBeenCalled()
  })

  it('cancels on a second finger, because that is a pinch', () => {
    press(map)
    map.emit('touchstart', {
      ...AT,
      points: [
        { x: 120, y: 240 },
        { x: 300, y: 300 },
      ],
    })
    vi.advanceTimersByTime(LONG_PRESS_MS)

    expect(onLongPress).not.toHaveBeenCalled()
  })

  it('cancels when the finger lifts early', () => {
    press(map)
    vi.advanceTimersByTime(LONG_PRESS_MS - 50)
    map.emit('touchend', AT)
    vi.advanceTimersByTime(LONG_PRESS_MS)

    expect(onLongPress).not.toHaveBeenCalled()
  })

  it('cancels on touchcancel, which is what an incoming call looks like', () => {
    press(map)
    map.emit('touchcancel', AT)
    vi.advanceTimersByTime(LONG_PRESS_MS)

    expect(onLongPress).not.toHaveBeenCalled()
  })

  it('works with a mouse, so the gesture is reachable on a laptop', () => {
    map.emit('mousedown', AT)
    vi.advanceTimersByTime(LONG_PRESS_MS)

    expect(onLongPress).toHaveBeenCalledTimes(1)
  })

  it('reports the press position it STARTED at, not where the finger ended', () => {
    // The plate names a point on the trail. A press that drifted 9 px and
    // reported the drifted position would anchor the report a few metres from
    // where somebody put their thumb - inside the slop, so it still fires,
    // which is exactly why this is worth pinning.
    press(map)
    map.emit('touchmove', { lngLat: { lat: 99, lng: 99 }, point: { x: 128, y: 246 } })
    vi.advanceTimersByTime(LONG_PRESS_MS)

    expect(onLongPress).toHaveBeenCalledWith(
      { lat: 37.3, lon: -80.4 },
      { x: 120, y: 240 },
    )
  })

  it('starts a fresh press rather than stacking two', () => {
    press(map)
    vi.advanceTimersByTime(LONG_PRESS_MS - 100)
    press(map, { lngLat: { lat: 40, lng: -75 }, point: { x: 10, y: 20 } })
    vi.advanceTimersByTime(100)

    // The first press's own deadline passed during that 100 ms and must not
    // have fired: it was replaced, not queued behind the second.
    expect(onLongPress).not.toHaveBeenCalled()

    vi.advanceTimersByTime(LONG_PRESS_MS)
    expect(onLongPress).toHaveBeenCalledTimes(1)
    expect(onLongPress).toHaveBeenCalledWith({ lat: 40, lon: -75 }, { x: 10, y: 20 })
  })

  it('leaves no timer running after detach', () => {
    // A press in flight when the map unmounts would otherwise call back into a
    // shell that has gone.
    press(map)
    detach()
    vi.advanceTimersByTime(LONG_PRESS_MS * 2)

    expect(onLongPress).not.toHaveBeenCalled()
    // Re-detaching in afterEach must stay harmless.
    detach = () => {}
  })

  it('unbinds every listener it bound', () => {
    const events = [
      'mousedown',
      'touchstart',
      'mousemove',
      'touchmove',
      'mouseup',
      'touchend',
      'touchcancel',
      'movestart',
    ]
    for (const event of events) expect(map.listenerCount(event)).toBe(1)

    detach()
    detach = () => {}

    for (const event of events) expect(map.listenerCount(event)).toBe(0)
  })
})
