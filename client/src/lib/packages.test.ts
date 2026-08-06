import { describe, it, expect } from 'vitest'
import {
  anyPackageRemains,
  AT_PACKAGES,
  BASEMAP_PACKAGE,
  CORRIDOR_BACKGROUND_PACKAGE,
  DEM_PACKAGE,
  MAP_PACKAGES,
  offeredPackages,
  packageDownloadUrl,
  packageSizeBytes,
  type MapPackage,
} from './packages'
import { archiveUrl, dataUrl } from './config'
import { getDownloadDetail } from './downloadDetail'
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'

// The catalog is where a package's identity lives, so what these cover is
// mostly identity: keys that must not change under a phone that already holds
// an archive, keys that must not collide, and the one rule that keeps the
// Downloads screen honest - a package with nothing published behind it is
// never offered.

const PUBLISHED_ELSEWHERE: MapPackage = {
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

  it('says what every package is, in words a hiker chooses by', () => {
    for (const pkg of MAP_PACKAGES) {
      expect(pkg.title.length).toBeGreaterThan(0)
      expect(pkg.summary.length).toBeGreaterThan(0)
    }
  })
})

describe('what the trail is made of', () => {
  it('names the packages the AT needs, so one tap can fan out to all of them', () => {
    expect(AT_PACKAGES.packages).toEqual(MAP_PACKAGES)
    expect(AT_PACKAGES.packages).toContain(CORRIDOR_BACKGROUND_PACKAGE)
    expect(AT_PACKAGES.packages).toContain(BASEMAP_PACKAGE)
    expect(AT_PACKAGES.packages).toContain(DEM_PACKAGE)
  })

  it('carries no version of its own', () => {
    // Which bytes are current is latest.json's per-artifact hashes
    // (pipeline/DATA_RELEASES.md). A second scheme here would be a second
    // answer to the same question.
    expect(AT_PACKAGES).not.toHaveProperty('version')
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
      trailId: 'example',
      title: 'Example',
      packages: [BASEMAP_PACKAGE, PUBLISHED_ELSEWHERE],
    })

    expect(offered).toEqual([PUBLISHED_ELSEWHERE])
  })

  it('keeps offering a package whatever state it is in on the phone', () => {
    // Filtering on "already downloaded" would take away the only way to
    // delete it, and the only place an eviction can be reported (#190).
    expect(offeredPackages()).toContain(CORRIDOR_BACKGROUND_PACKAGE)
  })
})

describe('what a deletion takes with it', () => {
  const downloaded = (...keys: string[]) => {
    const held = new Set(keys)
    return (idbKey: string) => held.has(idbKey)
  }

  it('keeps the trail’s own data while another package is still here', () => {
    // Someone reclaiming the raster sheet's gigabyte and keeping the terrain
    // must not lose the trail line off the map they kept.
    expect(
      anyPackageRemains(
        MAP_PACKAGES,
        CORRIDOR_BACKGROUND_PACKAGE.idbKey,
        downloaded(CORRIDOR_BACKGROUND_PACKAGE.idbKey, DEM_PACKAGE.idbKey),
      ),
    ).toBe(true)
  })

  it('lets it go when the package being removed was the last one', () => {
    expect(
      anyPackageRemains(
        MAP_PACKAGES,
        CORRIDOR_BACKGROUND_PACKAGE.idbKey,
        downloaded(CORRIDOR_BACKGROUND_PACKAGE.idbKey),
      ),
    ).toBe(false)
  })

  it('does not count the package being removed as a reason to keep it', () => {
    // The status map is read before the deletion settles, so the removed
    // package can still read as downloaded. Counting it would keep the trail
    // data on a phone holding no map at all.
    expect(
      anyPackageRemains(
        [CORRIDOR_BACKGROUND_PACKAGE],
        CORRIDOR_BACKGROUND_PACKAGE.idbKey,
        downloaded(CORRIDOR_BACKGROUND_PACKAGE.idbKey),
      ),
    ).toBe(false)
  })

  it('ignores packages that are merely offered, not downloaded', () => {
    expect(
      anyPackageRemains(MAP_PACKAGES, CORRIDOR_BACKGROUND_PACKAGE.idbKey, downloaded()),
    ).toBe(false)
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

  it('has no URL at all where nothing is published', () => {
    expect(packageDownloadUrl(DEM_PACKAGE, 'standard')).toBeNull()
  })
})

describe('what a package will cost', () => {
  it('is the chosen tier’s measured size for the raster sheet', () => {
    for (const level of ['light', 'standard', 'fine'] as const) {
      expect(packageSizeBytes(CORRIDOR_BACKGROUND_PACKAGE, level)).toBe(
        getDownloadDetail(level).sizeBytes,
      )
    }
  })

  it('is the package’s own size where it has one', () => {
    expect(packageSizeBytes(PUBLISHED_ELSEWHERE, 'standard')).toBe(12_345)
  })

  it('is null - never a guess - where nobody has measured it', () => {
    // The sizes shown before a download are held to ±0.6% against measured
    // artifacts (pipeline/README.md). An estimate returned here would be
    // shown at the same weight as a measurement.
    expect(packageSizeBytes(BASEMAP_PACKAGE, 'standard')).toBeNull()
  })
})
