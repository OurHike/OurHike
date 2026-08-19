// The merged-chain flag (#161): detected from the artifact's own bytes at
// download time, recorded synchronously readable for style-build time, and
// biased so every failure lands on the conservative side - `tolerance: 0`
// costs worker minutes, a wrongly-optimistic flag would cost the trail line.

import { afterEach, describe, expect, it } from 'vitest'
import {
  CHAIN_ID_MARKER,
  clearTrailsMerged,
  readTrailsMerged,
  sniffMergedChains,
  TRAILS_MERGED_STORAGE_KEY,
  writeTrailsMerged,
} from './trailShape'

afterEach(() => localStorage.removeItem(TRAILS_MERGED_STORAGE_KEY))

describe('sniffMergedChains', () => {
  it('recognises the chain ids the merged export mints', () => {
    const merged = JSON.stringify({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {
            id: 'centerline:chain:0',
            source: 'centerline',
            blaze_color: 'White',
          },
          geometry: { type: 'LineString', coordinates: [] },
        },
      ],
    })

    expect(sniffMergedChains(merged)).toBe(true)
  })

  it('reads a pre-merge export as unmerged', () => {
    const segmented = JSON.stringify({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          properties: {
            id: 'centerline:abc-123',
            source: 'centerline',
            blaze_color: 'White',
          },
          geometry: { type: 'LineString', coordinates: [] },
        },
      ],
    })

    expect(sniffMergedChains(segmented)).toBe(false)
  })

  it('pins the marker to the id spelling pipeline/export_trails.py publishes', () => {
    // The pipeline side of this contract is pinned by
    // test_export_trails.py's chain-merge tests (`centerline:chain:<n>`).
    // If either side respells it, the sniff answers false forever and every
    // phone silently keeps paying `tolerance: 0` - a drift with no error
    // anywhere, which is why the exact string is asserted.
    expect(CHAIN_ID_MARKER).toBe('"centerline:chain:')
  })
})

describe('the recorded answer', () => {
  it('round-trips through storage', () => {
    writeTrailsMerged(true)
    expect(readTrailsMerged()).toBe(true)

    // Written on every download commit, including back DOWN - a re-download
    // from an older release has to take the flag with it.
    writeTrailsMerged(false)
    expect(readTrailsMerged()).toBe(false)
  })

  it('answers false when nothing was ever recorded', () => {
    // No record means the stored data predates the merge or the flag, and
    // both need the conservative tolerance.
    expect(readTrailsMerged()).toBe(false)
  })

  it('is cleared when the trail data is deleted', () => {
    writeTrailsMerged(true)

    clearTrailsMerged()

    expect(readTrailsMerged()).toBe(false)
  })
})
