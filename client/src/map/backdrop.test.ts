import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import type { Map as MapLibreMap } from 'maplibre-gl'
import { MAP_BACKGROUND_COLOR, BACKDROP_LAYER_ID } from './style'
import {
  attachMapBackdrop,
  buildBackdropPattern,
  BACKDROP_PATTERN_ID,
  BACKDROP_TILE_SIZE,
  BACKDROP_HATCH_SPACING,
  BACKDROP_HATCH_COLOR,
} from './backdrop'

vi.mock('maplibre-gl', () => import('../test/mocks/maplibre-gl'))

function pixel(data: Uint8ClampedArray, x: number, y: number) {
  const at = (y * BACKDROP_TILE_SIZE + x) * 4
  return [data[at], data[at + 1], data[at + 2], data[at + 3]]
}

function newMap(): MapLibreMap {
  return new MockMap({}) as unknown as MapLibreMap
}

beforeEach(() => {
  resetMapLibreMock()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('buildBackdropPattern', () => {
  it('is fully opaque in every pixel, so nothing behind the canvas shows through', () => {
    // The whole point of the backdrop is that black cannot get back in. One
    // translucent pixel per tile would let it, everywhere, in a fine mesh.
    const { data } = buildBackdropPattern()

    for (let at = 3; at < data.length; at += 4) {
      expect(data[at]).toBe(255)
    }
  })

  it('paints the same paper the style falls back to, read from the style itself', () => {
    // If these ever drift, the map changes colour at the moment the pattern
    // loads. Deriving one from the other is what makes that impossible.
    const { data } = buildBackdropPattern()
    const [r, g, b] = [0xf7, 0xf3, 0xe9]

    expect(MAP_BACKGROUND_COLOR).toBe('#f7f3e9')
    // (1, 0) is off the hatch: 1 + 0 is not a multiple of the spacing.
    expect(pixel(data, 1, 0)).toEqual([r, g, b, 255])
  })

  it('rules 45° hatch lines at the documented spacing', () => {
    const { data } = buildBackdropPattern()
    const [r, g, b] = BACKDROP_HATCH_COLOR

    expect(pixel(data, 0, 0)).toEqual([r, g, b, 255])
    expect(pixel(data, BACKDROP_HATCH_SPACING, 0)).toEqual([r, g, b, 255])
    // Same diagonal, one step down-left - the line runs at 45°, not vertically.
    expect(pixel(data, BACKDROP_HATCH_SPACING - 1, 1)).toEqual([r, g, b, 255])
  })

  it('tiles seamlessly, which needs the tile size to be a whole number of spacings', () => {
    // A tile whose edge is not a multiple of the spacing puts a visible seam on
    // every tile join across the whole off-archive field.
    expect(BACKDROP_TILE_SIZE % BACKDROP_HATCH_SPACING).toBe(0)
  })

  it('stays a texture rather than a warning stripe - low contrast against the paper', () => {
    const [hr] = BACKDROP_HATCH_COLOR
    const paper = 0xf7

    expect(paper - hr).toBeLessThan(40)
  })
})

describe('attachMapBackdrop', () => {
  it('waits for the style before touching it, then hangs the pattern on the background layer', () => {
    const map = newMap()
    const mock = MockMap.instances[0]

    attachMapBackdrop(map)
    expect(mock.images.has(BACKDROP_PATTERN_ID)).toBe(false)

    mock.emit('load')

    expect(mock.images.has(BACKDROP_PATTERN_ID)).toBe(true)
    expect(mock.paintProperties.get(`${BACKDROP_LAYER_ID}/background-pattern`)).toBe(
      BACKDROP_PATTERN_ID,
    )
  })

  it('applies immediately to an already-loaded style, which will never fire load again', () => {
    const map = newMap()
    const mock = MockMap.instances[0]
    mock.styleLoaded = true

    attachMapBackdrop(map)

    expect(mock.paintProperties.get(`${BACKDROP_LAYER_ID}/background-pattern`)).toBe(
      BACKDROP_PATTERN_ID,
    )
  })

  it('does nothing on a load that arrives after detach', () => {
    const map = newMap()
    const mock = MockMap.instances[0]

    attachMapBackdrop(map)()
    mock.emit('load')

    expect(mock.images.size).toBe(0)
    expect(mock.listenerCount('load')).toBe(0)
  })

  it('leaves the map alive when the pattern cannot be applied - paper is the guarantee', () => {
    // The flat background colour is what must never fail. The hatch is the
    // refinement on top of it, so its failure is a warning, not a thrown error
    // that would take the map render down with it.
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const map = newMap()
    const mock = MockMap.instances[0]
    vi.spyOn(mock, 'addImage').mockImplementation(() => {
      throw new Error('style not ready')
    })

    attachMapBackdrop(map)
    expect(() => mock.emit('load')).not.toThrow()
    expect(warn).toHaveBeenCalled()
  })
})
