import { describe, it, expect, beforeEach } from 'vitest'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import {
  attachCoverageSeams,
  buildCoverageSeamLayers,
  COVERAGE_SEAM_LABEL,
  COVERAGE_SEAM_LABEL_LAYER_ID,
  COVERAGE_SEAM_LAYER_ID,
  COVERAGE_SEAM_SOURCE_ID,
  seamFeatureCollection,
} from './coverageLayers'
import type { SeamEdge } from '../lib/coverageCells'

// The edge of the download, drawn (#557). What matters: the line is named in
// the words of coverage, the layers sit where the style stack puts them (see
// style.test.ts for the order), and the shell can push an edge list onto a
// live map and take it back to nothing.

const EDGE: SeamEdge = [
  [-84, 34],
  [-84, 35],
]

beforeEach(() => {
  resetMapLibreMock()
})

describe('seamFeatureCollection', () => {
  it('draws each edge as a two-point line carrying the label', () => {
    const collection = seamFeatureCollection([EDGE])

    expect(collection.features).toHaveLength(1)
    expect(collection.features[0]?.geometry).toEqual({
      type: 'LineString',
      coordinates: [
        [-84, 34],
        [-84, 35],
      ],
    })
    expect(collection.features[0]?.properties).toEqual({ label: COVERAGE_SEAM_LABEL })
  })

  it('names the edge as coverage, never as damage', () => {
    expect(COVERAGE_SEAM_LABEL).toMatch(/downloaded/)
    expect(COVERAGE_SEAM_LABEL).not.toMatch(/damaged|corrupt|incomplete/i)
  })
})

describe('buildCoverageSeamLayers', () => {
  it('draws a dashed line and a name along it, off the one source', () => {
    const [line, label] = buildCoverageSeamLayers('#123', '#fff')

    expect(line?.id).toBe(COVERAGE_SEAM_LAYER_ID)
    expect(line?.type).toBe('line')
    expect((line as { source?: string }).source).toBe(COVERAGE_SEAM_SOURCE_ID)
    expect(
      (line as { paint?: Record<string, unknown> }).paint?.['line-dasharray'],
    ).toEqual([3, 3])
    expect((line as { paint?: Record<string, unknown> }).paint?.['line-color']).toBe(
      '#123',
    )

    expect(label?.id).toBe(COVERAGE_SEAM_LABEL_LAYER_ID)
    expect(label?.type).toBe('symbol')
    expect(
      (label as { layout?: Record<string, unknown> }).layout?.['symbol-placement'],
    ).toBe('line')
    expect(
      (label as { paint?: Record<string, unknown> }).paint?.['text-halo-color'],
    ).toBe('#fff')
  })
})

describe('attachCoverageSeams', () => {
  it('pushes the edges onto the live map once the source exists', () => {
    const map = new MockMap({})
    map.sourceIds = [COVERAGE_SEAM_SOURCE_ID]
    map.styleLoaded = true

    attachCoverageSeams(map as never, [EDGE])

    expect(map.sourceData.get(COVERAGE_SEAM_SOURCE_ID)).toEqual(
      seamFeatureCollection([EDGE]),
    )
  })

  it('takes the line back to nothing when nothing is held', () => {
    // A delete, or the whole sheet arriving: both leave no edge, and an
    // empty push is how the last one comes off the map.
    const map = new MockMap({})
    map.sourceIds = [COVERAGE_SEAM_SOURCE_ID]
    map.styleLoaded = true

    attachCoverageSeams(map as never, [EDGE])
    attachCoverageSeams(map as never, [])

    expect(map.sourceData.get(COVERAGE_SEAM_SOURCE_ID)).toEqual({
      type: 'FeatureCollection',
      features: [],
    })
  })
})
