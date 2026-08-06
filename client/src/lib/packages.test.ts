import { describe, it, expect } from 'vitest'
import {
  BACKGROUND_DATA,
  backgroundSizeBytes,
  BASEMAP_PACKAGE,
  CORRIDOR_BACKGROUND_PACKAGE,
  DEM_PACKAGE,
  MAP_PACKAGES,
  offeredPackages,
  packageDownloadUrl,
  packageSizeBytes,
  type OfferedPackage,
} from './packages'
import { archiveUrl, dataUrl } from './config'
import { getDownloadDetail } from './downloadDetail'
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'

// The catalog is where a package's identity lives, so what these cover is
// mostly identity: keys that must not change under a phone that already holds
// an archive, keys that must not collide, keys that are never trail-scoped,
// and the one rule that keeps the Downloads screen honest - a package with
// nothing published behind it is never offered.

const PUBLISHED_ELSEWHERE: OfferedPackage = {
  id: 'example',
  idbKey: 'ourhike:example',
  title: 'Example',
  summary: 'A package with one artifact and one size.',
  source: { kind: 'artifact', artifact: 'example.pmtiles', sizeBytes: 12_345 },
}

describe('the package catalog', () => {
  it('keeps the corridor archive under the key phones already hold', () => {
    // An archive sitting in a tester's IndexedDB has to stay readable across
    // this change. A new key would silently re-download several hundred MB.
    expect(CORRIDOR_BACKGROUND_PACKAGE.idbKey).toBe(CORRIDOR_ARCHIVE_KEY)
    expect(CORRIDOR_ARCHIVE_KEY).toBe('ourhike:corridor-archive')
  })

  it('gives every package a distinct id and a distinct store key', () => {
    // Two packages sharing a key would share partial, progress and source
    // records too (archiveDownload.ts derives all three from the key), so one
    // download would resume onto another's bytes.
    const ids = MAP_PACKAGES.map((pkg) => pkg.id)
    const keys = MAP_PACKAGES.map((pkg) => pkg.idbKey)

    expect(new Set(ids).size).toBe(ids.length)
    expect(new Set(keys).size).toBe(keys.length)
  })

  it('names no trail in any key, so two trails share one copy', () => {
    // The background is shared: a hiker who has the AT's and then adds
    // NYNJTC's must not re-download the ground both stand on. A trail-scoped
    // key would put two identical copies on one phone (#193).
    for (const pkg of MAP_PACKAGES) {
      expect(pkg.idbKey).not.toMatch(/\b(at|nynjtc|trail)[-:]/i)
    }
  })
})

describe('the background, as one thing', () => {
  it('is made of every background archive this build knows', () => {
    expect(BACKGROUND_DATA.packages).toEqual(MAP_PACKAGES)
  })

  it('carries the trail’s own data nowhere in it', () => {
    // The centerline, spurs, POIs and elevation profile are per-trail and
    // downloaded by default (lib/trailData.ts). Putting them in here would
    // make the shared half trail-shaped and the always-on half a choice.
    const ids = BACKGROUND_DATA.packages.map((pkg) => pkg.id)

    expect(ids).not.toContain('trails')
    expect(ids).not.toContain('poi')
  })

  it('carries no version of its own', () => {
    // Which bytes are current is latest.json's per-artifact hashes
    // (pipeline/DATA_RELEASES.md). A second scheme here would be a second
    // answer to the same question.
    expect(BACKGROUND_DATA).not.toHaveProperty('version')
  })
})

describe('offering only what is actually published', () => {
  it('leaves out a package nothing publishes yet', () => {
    // The vector basemap and the DEM are catalogued - their keys resolve, and
    // an archive stored under one renders - but neither is published, and
    // offering a download that 404s is a hiker's data allowance spent to
    // learn nothing on a mountain.
    expect(BASEMAP_PACKAGE.source).toBeNull()
    expect(DEM_PACKAGE.source).toBeNull()
    expect(offeredPackages()).toEqual([CORRIDOR_BACKGROUND_PACKAGE])
  })

  it('offers a package the moment it has a source', () => {
    const offered = offeredPackages({
      id: 'example',
      title: 'Example',
      summary: 'Example background.',
      packages: [BASEMAP_PACKAGE, PUBLISHED_ELSEWHERE],
    })

    expect(offered).toEqual([PUBLISHED_ELSEWHERE])
  })

  it('keeps offering a package whatever state it is in on the phone', () => {
    // Filtering on "already downloaded" would take away the only way to
    // delete it, and the only place an eviction can be reported (#190).
    expect(offeredPackages()).toContain(CORRIDOR_BACKGROUND_PACKAGE)
  })

  it('gives every offered package a size, with no null to branch on', () => {
    // The point of OfferedPackage: a package that can be downloaded always
    // has a measured size, so nothing downstream needs a "size unknown" path
    // it could get wrong.
    for (const pkg of offeredPackages()) {
      expect(packageSizeBytes(pkg, 'standard')).toBeGreaterThan(0)
    }
  })
})

describe('where a package’s bytes come from', () => {
  it('follows the detail level for a package published in tiers', () => {
    expect(packageDownloadUrl(CORRIDOR_BACKGROUND_PACKAGE, 'light')).toBe(
      archiveUrl('light'),
    )
    expect(packageDownloadUrl(CORRIDOR_BACKGROUND_PACKAGE, 'fine')).toBe(
      archiveUrl('fine'),
    )
    expect(packageDownloadUrl(CORRIDOR_BACKGROUND_PACKAGE, 'light')).not.toBe(
      packageDownloadUrl(CORRIDOR_BACKGROUND_PACKAGE, 'fine'),
    )
  })

  it('is one artifact, at any detail level, for a package with one size', () => {
    expect(packageDownloadUrl(PUBLISHED_ELSEWHERE, 'light')).toBe(
      dataUrl('example.pmtiles'),
    )
    expect(packageDownloadUrl(PUBLISHED_ELSEWHERE, 'fine')).toBe(
      dataUrl('example.pmtiles'),
    )
  })
})

describe('what the background will cost', () => {
  it('is the chosen tier’s measured size while the raster sheet is all of it', () => {
    for (const level of ['light', 'standard', 'fine'] as const) {
      expect(backgroundSizeBytes(level)).toBe(getDownloadDetail(level).sizeBytes)
      expect(packageSizeBytes(CORRIDOR_BACKGROUND_PACKAGE, level)).toBe(
        getDownloadDetail(level).sizeBytes,
      )
    }
  })

  it('is the package’s own size where it has one', () => {
    expect(packageSizeBytes(PUBLISHED_ELSEWHERE, 'standard')).toBe(12_345)
  })

  it('sums every archive the background is made of', () => {
    // One tap brings all of them, so the figure shown beside "may not fit"
    // has to be all of them too.
    const background = {
      id: 'example',
      title: 'Example',
      summary: 'Example background.',
      packages: [CORRIDOR_BACKGROUND_PACKAGE, PUBLISHED_ELSEWHERE],
    }

    expect(backgroundSizeBytes('standard', background)).toBe(
      getDownloadDetail('standard').sizeBytes + 12_345,
    )
  })

  it('counts only what is offered, never an archive nobody can download', () => {
    const background = {
      id: 'example',
      title: 'Example',
      summary: 'Example background.',
      packages: [PUBLISHED_ELSEWHERE, BASEMAP_PACKAGE, DEM_PACKAGE],
    }

    expect(backgroundSizeBytes('standard', background)).toBe(12_345)
  })
})
