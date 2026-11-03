import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MockMap } from '../test/mocks/maplibre-gl'
import { SETTLE_MS, onSettled } from './settle'

// When a reader of rendered features may measure (#1538, #1696): on `idle`,
// or once the map has drawn no frame for SETTLE_MS. The second half is the
// one that matters - `idle` never fires while one basemap tile hangs.

beforeEach(() => {
  vi.useFakeTimers()
})

afterEach(() => {
  vi.useRealTimers()
})

function attached() {
  const map = new MockMap({})
  const settled = vi.fn()
  const detach = onSettled(map as unknown as MapLibreMap, settled)
  /** One frame, then `ms` of nothing. */
  const frame = (ms = 16) => {
    map.emit('render')
    vi.advanceTimersByTime(ms)
  }
  return { map, settled, detach, frame }
}

describe('onSettled', () => {
  it('calls once the map has drawn no frame for SETTLE_MS, with no idle at all', () => {
    // #1696's trace: the lines drew, one tile hung, `idle` never came.
    const { settled, frame } = attached()

    frame(SETTLE_MS - 1)
    expect(settled).not.toHaveBeenCalled()

    vi.advanceTimersByTime(1)
    expect(settled).toHaveBeenCalledTimes(1)
  })

  it('calls once per pan, after its last frame, not once per frame', () => {
    const { settled, frame } = attached()

    for (let n = 0; n < 60; n += 1) frame(16)
    expect(settled).not.toHaveBeenCalled()

    vi.advanceTimersByTime(SETTLE_MS)
    expect(settled).toHaveBeenCalledTimes(1)
  })

  it('calls on idle, and does not measure the same frames again after it', () => {
    // An `idle` answers for the frames before it, so the quiet-spell call
    // they scheduled would only take the same reading twice.
    const { map, settled, frame } = attached()

    frame(16)
    map.emit('idle')
    expect(settled).toHaveBeenCalledTimes(1)

    vi.advanceTimersByTime(SETTLE_MS * 2)
    expect(settled).toHaveBeenCalledTimes(1)
  })

  it('calls nothing up front - a reader that wants a first answer takes it itself', () => {
    const { settled } = attached()

    vi.advanceTimersByTime(SETTLE_MS * 10)

    expect(settled).not.toHaveBeenCalled()
  })

  it('detaches both listeners and drops a pending call', () => {
    const { map, settled, detach, frame } = attached()
    expect(map.listenerCount('render')).toBe(1)
    expect(map.listenerCount('idle')).toBe(1)
    frame(16)

    detach()
    vi.advanceTimersByTime(SETTLE_MS * 2)

    expect(settled).not.toHaveBeenCalled()
    expect(map.listenerCount('render')).toBe(0)
    expect(map.listenerCount('idle')).toBe(0)
  })
})
