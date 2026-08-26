// Whether this phone is holding a superseded map, and what it is told about it
// (#919).
//
// The decisions under test are the ones that decide what a hiker sees, so each
// is asserted in the direction that would hurt if it went the other way: an
// unknown never reads as reassuring, an undescribable hop never borrows
// somebody else's counts, and an unknown size never reads as free.

import { describe, expect, it } from 'vitest'

import {
  availableRefresh,
  connectionKind,
  LARGE_UPDATE_BYTES,
  warnsAboutData,
  type StoredRelease,
} from './dataRefresh'
import { CONSEQUENTIAL, ROUTINE, type PublishedSnapshot } from './dataManifest'

const stored = (
  version: string | null,
  hashes: Record<string, string>,
): StoredRelease => ({
  version,
  hashes,
  at: 1_700_000_000_000,
})

function snapshot(overrides: Partial<PublishedSnapshot> = {}): PublishedSnapshot {
  return {
    version: 'v2',
    previousVersion: 'v1',
    lookup: () => null,
    hashes: {},
    sizes: {},
    changes: {},
    ...overrides,
  }
}

const routine = {
  severity: ROUTINE as typeof ROUTINE,
  added: 3,
  removed: 0,
  moved: 0,
  edited: 1,
}
const consequential = {
  severity: CONSEQUENTIAL as typeof CONSEQUENTIAL,
  added: 0,
  removed: 2,
  moved: 1,
  edited: 0,
}

describe('is there an update', () => {
  it('offers nothing to a phone that has downloaded nothing', () => {
    expect(availableRefresh(null, snapshot())).toBeNull()
  })

  it('offers nothing when the published version is the stored one', () => {
    const current = stored('v2', { 'poi_water.geojson': 'aaa' })
    expect(
      availableRefresh(current, snapshot({ hashes: { 'poi_water.geojson': 'bbb' } })),
    ).toBeNull()
  })

  it('offers nothing when the manifest could not be read', () => {
    const current = stored('v1', { 'poi_water.geojson': 'aaa' })
    expect(availableRefresh(current, snapshot({ version: null }))).toBeNull()
  })

  it('offers nothing when the phone stored no version to compare', () => {
    // A download that finished while latest.json was unreadable. Real, and not
    // something to guess about - the counts would be a fiction.
    const current = stored(null, { 'poi_water.geojson': 'aaa' })
    expect(
      availableRefresh(current, snapshot({ hashes: { 'poi_water.geojson': 'bbb' } })),
    ).toBeNull()
  })

  it('offers nothing when the version moved but nothing this phone holds did', () => {
    // A release that only touched the archives. Offering it would spend
    // 5.78 MB to change nothing.
    const current = stored('v1', { 'poi_water.geojson': 'aaa' })
    expect(
      availableRefresh(current, snapshot({ hashes: { 'poi_water.geojson': 'aaa' } })),
    ).toBeNull()
  })

  it('names only the artifacts whose hash actually differs', () => {
    const current = stored('v1', { 'poi_water.geojson': 'aaa', 'trails.geojson': 'ttt' })
    const found = availableRefresh(
      current,
      snapshot({ hashes: { 'poi_water.geojson': 'bbb', 'trails.geojson': 'ttt' } }),
    )
    expect(found?.keys).toEqual(['poi_water.geojson'])
  })

  it('ignores a published artifact this phone never held', () => {
    // A layer this build has no code to draw is not an update to what it has,
    // and prompting about it would ask a hiker to pay for nothing.
    const current = stored('v1', { 'poi_water.geojson': 'aaa' })
    const found = availableRefresh(
      current,
      snapshot({ hashes: { 'poi_water.geojson': 'aaa', 'poi_newthing.geojson': 'zzz' } }),
    )
    expect(found).toBeNull()
  })
})

describe('what it says changed', () => {
  it('carries the publisher grade and counts for a described hop', () => {
    const current = stored('v1', { 'poi_water.geojson': 'aaa' })
    const found = availableRefresh(
      current,
      snapshot({
        hashes: { 'poi_water.geojson': 'bbb' },
        changes: { 'poi_water.geojson': routine },
      }),
    )
    expect(found).toMatchObject({
      described: true,
      severity: ROUTINE,
      added: 3,
      edited: 1,
    })
  })

  it('is consequential when any changed artifact is', () => {
    const current = stored('v1', { a: '1', b: '1' })
    const found = availableRefresh(
      current,
      snapshot({ hashes: { a: '2', b: '2' }, changes: { a: routine, b: consequential } }),
    )
    expect(found?.severity).toBe(CONSEQUENTIAL)
    expect(found?.removed).toBe(2)
  })

  it('refuses to describe a hop the manifest does not cover', () => {
    // Two releases behind: previous_version names somebody else's transition,
    // and repeating its counts would be a confident wrong answer.
    const current = stored('v0', { 'poi_water.geojson': 'aaa' })
    const found = availableRefresh(
      current,
      snapshot({
        previousVersion: 'v1',
        hashes: { 'poi_water.geojson': 'bbb' },
        changes: { 'poi_water.geojson': routine },
      }),
    )
    expect(found?.described).toBe(false)
    expect(found?.severity).toBe(CONSEQUENTIAL)
    expect(found?.added).toBe(0)
  })

  it('refuses to describe when a changed artifact was not graded', () => {
    const current = stored('v1', { a: '1', b: '1' })
    const found = availableRefresh(
      current,
      snapshot({ hashes: { a: '2', b: '2' }, changes: { a: routine } }),
    )
    expect(found?.described).toBe(false)
    expect(found?.severity).toBe(CONSEQUENTIAL)
  })

  it('carries the version being offered, so a decline can be remembered', () => {
    const current = stored('v1', { a: '1' })
    expect(availableRefresh(current, snapshot({ hashes: { a: '2' } }))?.version).toBe(
      'v2',
    )
  })
})

describe('what it costs', () => {
  it('reads the wire cost and never the decoded size', () => {
    // The bug this guards, found while pointing a preview recipe at the row:
    // the publisher measures both and the client was reading `size_bytes`,
    // which is ~3x what a phone spends. A cautious overstatement of a figure
    // shown to somebody deciding whether to pay it is just a wrong figure.
    const current = stored('v1', { a: '1' })
    const found = availableRefresh(current, {
      ...snapshot({ hashes: { a: '2' } }),
      sizes: {},
    })
    expect(found?.bytes).toBeNull()
  })

  it('adds up the published sizes of the changed artifacts only', () => {
    const current = stored('v1', { a: '1', b: '1' })
    const found = availableRefresh(
      current,
      snapshot({ hashes: { a: '2', b: '1' }, sizes: { a: 500, b: 9_000_000 } }),
    )
    expect(found?.bytes).toBe(500)
  })

  it('says it cannot tell rather than guessing when a size is missing', () => {
    const current = stored('v1', { a: '1', b: '1' })
    const found = availableRefresh(
      current,
      snapshot({ hashes: { a: '2', b: '2' }, sizes: { a: 500 } }),
    )
    expect(found?.bytes).toBeNull()
  })
})

describe('whether to caution about the data', () => {
  const large = { bytes: LARGE_UPDATE_BYTES } as never
  const small = { bytes: LARGE_UPDATE_BYTES - 1 } as never
  const unknown = { bytes: null } as never

  it('never cautions on wifi', () => {
    expect(warnsAboutData(large, 'wifi')).toBe(false)
  })

  it('cautions on a large update over cellular', () => {
    expect(warnsAboutData(large, 'cellular')).toBe(true)
  })

  it('stays quiet about a small update', () => {
    expect(warnsAboutData(small, 'cellular')).toBe(false)
  })

  it('treats an unknown size as large', () => {
    // The only direction that cannot quietly spend somebody's allowance.
    expect(warnsAboutData(unknown, 'unknown')).toBe(true)
  })

  it('cautions when the connection is unknown, because most browsers are', () => {
    expect(warnsAboutData(large, 'unknown')).toBe(true)
  })
})

describe('reading the connection', () => {
  it('is unknown where the browser offers nothing', () => {
    // Safari has no Network Information API at all. Claiming either answer
    // would be inventing a fact about somebody's plan.
    expect(connectionKind(undefined)).toBe('unknown')
  })

  it('takes saveData as the hiker having already said what they want', () => {
    expect(connectionKind({ type: 'wifi', saveData: true })).toBe('cellular')
  })

  it('reads wifi and ethernet as unmetered', () => {
    expect(connectionKind({ type: 'wifi' })).toBe('wifi')
    expect(connectionKind({ type: 'ethernet' })).toBe('wifi')
  })

  it('reads cellular as metered', () => {
    expect(connectionKind({ type: 'cellular' })).toBe('cellular')
  })

  it('is unknown for a type it does not recognise', () => {
    expect(connectionKind({ type: 'bluetooth' })).toBe('unknown')
  })
})
