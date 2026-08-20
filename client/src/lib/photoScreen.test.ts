import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screenPhoto, looksLikeNudity, NUDITY_MIN_PROBABILITY } from './photoScreen'
import { screenBlob } from './photoScreenEngine'

// The seam's whole contract (#837, #570): a finding passes through, and
// every way the engine can fail - including failing to load at all -
// resolves to null, indistinguishable from "nothing found". The engine
// itself (TensorFlow + two models) cannot run under jsdom and is mocked
// away; what it feeds the decision rule is tested against the rule's pure
// half below.

vi.mock('./photoScreenEngine', () => ({ screenBlob: vi.fn() }))

const mockedScreenBlob = vi.mocked(screenBlob)

const blob = new Blob(['not really a jpeg'], { type: 'image/jpeg' })

beforeEach(() => {
  vi.clearAllMocks()
})

describe('screenPhoto', () => {
  it('passes the engine finding through', async () => {
    mockedScreenBlob.mockResolvedValue({ flag: 'faces', faces: 2 })

    expect(await screenPhoto(blob)).toEqual({ flag: 'faces', faces: 2 })
  })

  it('resolves null when the engine throws, never rejecting', async () => {
    mockedScreenBlob.mockRejectedValue(new Error('no WebGL on this phone'))

    expect(await screenPhoto(blob)).toBeNull()
  })

  it('resolves null when the engine cannot even be loaded', async () => {
    // A dynamic-import failure (offline before the chunk ever arrived) is a
    // rejection from the import itself, upstream of screenBlob.
    mockedScreenBlob.mockImplementation(() => {
      throw new Error('Failed to fetch dynamically imported module')
    })

    expect(await screenPhoto(blob)).toBeNull()
  })
})

describe('looksLikeNudity', () => {
  const spread = (porn: number, hentai: number, sexy: number) => [
    { className: 'Porn', probability: porn },
    { className: 'Hentai', probability: hentai },
    { className: 'Sexy', probability: sexy },
    { className: 'Neutral', probability: Math.max(0, 1 - porn - hentai - sexy) },
  ]

  it('flags when Porn and Hentai together clear the threshold', () => {
    expect(looksLikeNudity(spread(0.2, 0.15, 0))).toBe(true)
    expect(looksLikeNudity(spread(NUDITY_MIN_PROBABILITY, 0, 0))).toBe(true)
  })

  it('does not flag below it', () => {
    expect(looksLikeNudity(spread(0.1, 0.1, 0))).toBe(false)
    expect(looksLikeNudity([])).toBe(false)
  })

  it('never counts Sexy - shorts at a swimming hole are not a finding', () => {
    expect(looksLikeNudity(spread(0, 0, 0.99))).toBe(false)
  })
})
