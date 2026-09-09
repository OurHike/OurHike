import { describe, it, expect, vi } from 'vitest'

// The release pin (#1333, DATA_RELEASES.md §4). Bumping DATA_RELEASE is the
// release, so what this file is really about is the boundary either side of
// it: which keys move into the pinned folder and which must not.
//
// The three that must not are not a style choice. `conditions/` is safety
// data rewritten in place - a closure that has reopened must STOP being
// served, which an immutable folder cannot express. `photos/` is already
// content-addressed, so a copy per release is duplication. `latest.json` is
// the pointer, and versioning the thing that says which version is current
// is a loop.

import {
  DATA_RELEASE,
  RELEASE_MANIFEST_PATH,
  isReleaseScoped,
  releasePath,
} from './dataRelease'

const BASE = 'https://cdn.example.org'

async function loadConfigWithBase(base: string) {
  vi.resetModules()
  vi.stubEnv('VITE_DATA_BASE_URL', base)
  return import('./config')
}

describe('what the pin covers', () => {
  it.each([
    'trails.geojson',
    'poi_shelter.geojson',
    'background.pmtiles',
    'registry.json',
    'spurs.json',
    // Dynamic keys the client builds at runtime from a cells index - they
    // carry no declaration of their own, which is exactly why the rule is an
    // exclusion rather than an allowlist: a key nobody listed is still
    // versioned.
    'at_basemap_cell_n35w084.pmtiles',
    'dem_stretch_ga_nc.pmtiles',
  ])('%s is served from the pinned release', (key) => {
    expect(isReleaseScoped(key)).toBe(true)
    expect(releasePath(key)).toBe(`releases/${DATA_RELEASE}/${key}`)
  })

  it.each([
    ['conditions/closures.json', 'safety data is rewritten in place'],
    ['conditions/reports.json', 'safety data is rewritten in place'],
    ['photos/abc123.jpg', 'already content-addressed'],
    ['latest.json', 'the pointer cannot version itself'],
  ])('%s stays at the bucket root - %s', (key) => {
    expect(isReleaseScoped(key)).toBe(false)
    expect(releasePath(key)).toBe(key)
  })

  it('does not mistake a key that merely contains a root prefix', () => {
    // `poi_conditions.geojson` is not under `conditions/`, and a `contains`
    // check rather than a prefix check would quietly un-version it.
    expect(isReleaseScoped('poi_conditions.geojson')).toBe(true)
    expect(isReleaseScoped('trail_photos.json')).toBe(true)
  })
})

describe('the pin itself', () => {
  it('is a release id publish.py could have written', () => {
    // lib/r2_keys.RELEASE_ID_PATTERN: YYYY-MM-DD with an optional -N for a
    // second release the same day. A pin that does not match this names a
    // folder no publish can ever create.
    expect(DATA_RELEASE).toMatch(/^\d{4}-\d{2}-\d{2}(-\d+)?$/)
  })

  it('names the release folder its own manifest lives in', () => {
    expect(RELEASE_MANIFEST_PATH).toBe(`releases/${DATA_RELEASE}/manifest.json`)
  })
})

describe('the URLs config.ts builds from it', () => {
  it('puts a release artifact under the pinned folder', async () => {
    const { dataUrl } = await loadConfigWithBase(BASE)
    expect(dataUrl('trails.geojson')).toBe(
      `${BASE}/releases/${DATA_RELEASE}/trails.geojson`,
    )
  })

  it('leaves conditions at the root, where the hourly bake rewrites them', async () => {
    const { dataUrl } = await loadConfigWithBase(BASE)
    expect(dataUrl('conditions/closures.json')).toBe(`${BASE}/conditions/closures.json`)
  })

  it('reads the pinned release manifest, never the root pointer', async () => {
    // The correctness of the pin, not a preference. `latest.json` describes
    // the FLAT keys, which move on every publish; this build's bytes do not.
    // Reading the root manifest from a pinned client agrees only until the
    // next publish, after which every changed artifact fails the hash
    // trailData.ts holds it to and the app rejects data it fetched correctly.
    const { releaseManifestUrl } = await loadConfigWithBase(BASE)
    expect(releaseManifestUrl()).toBe(`${BASE}/releases/${DATA_RELEASE}/manifest.json`)
    expect(releaseManifestUrl()).not.toContain('latest.json')
  })
})
