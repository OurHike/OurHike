import { describe, it, expect } from 'vitest'
import {
  BACKGROUND_SHEETS,
  hikingSheetSizeBytes,
  BASEMAP_PACKAGE,
  CORRIDOR_BACKGROUND_PACKAGE,
  DEM_PACKAGE,
  HIKING_SHEET,
  MAP_PACKAGES,
  offeredPackages,
  offeredSheets,
  offlineBackgroundAvailable,
  packageArtifactKey,
  packageDownloadUrl,
  packageSizeBytes,
  sheetSizeBytes,
  USGS_SHEET,
  withdrawnSheets,
  type BackgroundSheet,
  type OfferedPackage,
} from './packages'
import { archiveUrl, dataUrl } from './config'
import { getDownloadDetail } from './downloadDetail'
import { getHikingDetail } from './hikingDetail'
import { CORRIDOR_ARCHIVE_KEY } from '../map/pmtilesSource'

// The catalog is where a package's identity lives, so what these cover is
// mostly identity: keys that must not change under a phone that already holds
// an archive, keys that must not collide, keys that are never trail-scoped,
// and the three rules that keep the Downloads screen honest - a package with
// nothing published behind it is never offered, the USGS raster is a sheet a
// hiker opts into rather than part of everyone's download (#237), and a
// withdrawn sheet stops being offered without becoming undeletable (#855).

const PUBLISHED_ELSEWHERE: OfferedPackage = {
  id: 'example',
  idbKey: 'ourhike:example',
  title: 'Example',
  summary: 'A package with one artifact and one size.',
  source: { kind: 'artifact', artifact: 'example.pmtiles', sizeBytes: 12_345 },
}

const UNPUBLISHED = {
  id: 'unpublished',
  idbKey: 'ourhike:unpublished',
  title: 'Unpublished',
  summary: 'Catalogued, nothing behind it.',
  source: null,
}

function sheetOf(packages: BackgroundSheet['packages']): BackgroundSheet {
  return { id: 'example-sheet', title: 'Example', summary: 'Example sheet.', packages }
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

describe('the background, as sheets a hiker chooses between (#237)', () => {
  it('makes the hiking sheet the default and the USGS raster the opt-in', () => {
    // Order is meaning here: the first sheet is the one everyone gets, and
    // the government scan - over a gigabyte at full tier - is a decision of
    // its own, never bundled into a download nobody asked to grow.
    expect(BACKGROUND_SHEETS[0]).toBe(HIKING_SHEET)
    expect(BACKGROUND_SHEETS).toContain(USGS_SHEET)
    expect(HIKING_SHEET.packages).toEqual([BASEMAP_PACKAGE, DEM_PACKAGE])
    expect(USGS_SHEET.packages).toEqual([CORRIDOR_BACKGROUND_PACKAGE])
  })

  it('puts every package in exactly one sheet, and every sheet package in the catalog', () => {
    // protocol.ts registers pmtiles:// for MAP_PACKAGES; a sheet package
    // missing from it would download bytes the map could never read back.
    const sheetPackages = BACKGROUND_SHEETS.flatMap((sheet) => sheet.packages)

    expect(new Set(sheetPackages).size).toBe(sheetPackages.length)
    expect(new Set(sheetPackages)).toEqual(new Set(MAP_PACKAGES))
  })

  it('carries the trail’s own data in no sheet', () => {
    // The centerline, spurs, POIs and elevation profile are per-trail and
    // downloaded by default (lib/trailData.ts). Putting them in a sheet would
    // make the shared half trail-shaped and the always-on half a choice.
    const ids = BACKGROUND_SHEETS.flatMap((sheet) => sheet.packages.map((p) => p.id))

    expect(ids).not.toContain('trails')
    expect(ids).not.toContain('poi')
  })

  it('carries no version of its own', () => {
    // Which bytes are current is latest.json's per-artifact hashes
    // (pipeline/DATA_RELEASES.md). A second scheme here would be a second
    // answer to the same question.
    for (const sheet of BACKGROUND_SHEETS) {
      expect(sheet).not.toHaveProperty('version')
    }
  })
})

describe('offering only what is actually published', () => {
  it('leaves out a package nothing publishes yet', () => {
    // A catalogued-but-unpublished package's key resolves, and an archive
    // stored under it renders - but offering its download would 404, which
    // is a hiker's data allowance spent to learn nothing on a mountain.
    expect(offeredPackages(sheetOf([UNPUBLISHED, PUBLISHED_ELSEWHERE]))).toEqual([
      PUBLISHED_ELSEWHERE,
    ])
  })

  it('offers no card at all for a sheet with nothing published behind it', () => {
    // The same honesty one level up: a sheet whose every archive is
    // unpublished is not a decision anyone can act on, so it gets no card
    // rather than a button that fails.
    for (const sheet of offeredSheets()) {
      expect(offeredPackages(sheet).length).toBeGreaterThan(0)
    }
  })

  it('does not offer the withdrawn USGS sheet, though its raster is published', () => {
    // The two filters are different questions and this sheet answers them
    // differently: its archive IS published, and it is still not on offer
    // (#855). A test that only checked `offeredPackages` would pass whether
    // or not the withdrawal worked.
    expect(offeredPackages(USGS_SHEET)).toEqual([CORRIDOR_BACKGROUND_PACKAGE])
    expect(offeredSheets()).not.toContain(USGS_SHEET)
  })

  it('keeps offering a package whatever state it is in on the phone', () => {
    // Filtering on "already downloaded" would take away the only way to
    // delete it, and the only place an eviction can be reported (#190).
    expect(offeredPackages(USGS_SHEET)).toContain(CORRIDOR_BACKGROUND_PACKAGE)
  })

  it('gives every offered package a size, with no null to branch on', () => {
    // The point of OfferedPackage: a package that can be downloaded always
    // has a measured size, so nothing downstream needs a "size unknown" path
    // it could get wrong.
    for (const sheet of offeredSheets()) {
      for (const pkg of offeredPackages(sheet)) {
        expect(packageSizeBytes(pkg, 'standard', 'fine')).toBeGreaterThan(0)
      }
    }
  })
})

describe('a sheet that is published but withdrawn (#855)', () => {
  // The USGS raster is the one this is written against, but every assertion
  // below is about the MECHANISM rather than about that sheet: withdrawing
  // an offer must not strand the bytes somebody already took, and putting
  // the raster back must not need any of this to change.

  it('keeps a withdrawn sheet out of what a hiker is asked to download', () => {
    expect(offeredSheets().every((sheet) => sheet.withdrawn !== true)).toBe(true)
  })

  it('still lists it separately, so its archive stays deletable', () => {
    // The whole reason this is not `source: null`. A phone that took the
    // Fine tier is holding 1.18 GB (downloadDetail.ts, measured against the
    // published bucket 2026-08-09), and the card is the only way to free it.
    expect(withdrawnSheets()).toContain(USGS_SHEET)
    expect(offeredPackages(USGS_SHEET)).toEqual([CORRIDOR_BACKGROUND_PACKAGE])
  })

  it('accounts for every catalogued sheet in exactly one of the two lists', () => {
    // Nothing may fall between them: a sheet in neither is bytes the app can
    // store and no screen can show.
    const listed = [...offeredSheets(), ...withdrawnSheets()]

    expect(new Set(listed).size).toBe(listed.length)
    expect(listed).toHaveLength(
      BACKGROUND_SHEETS.filter((sheet) => offeredPackages(sheet).length > 0).length,
    )
  })

  it('withdraws the offline background with the sheet it draws, unless it is here', () => {
    // `usgs_topo_offline` draws that archive and nothing else, so the option
    // and the card come and go together - offered, or already downloaded.
    expect(offlineBackgroundAvailable(false)).toBe(false)
    expect(offlineBackgroundAvailable(true)).toBe(true)
  })
})

describe('where a package’s bytes come from', () => {
  it('follows the detail level for a package published in tiers', () => {
    expect(packageDownloadUrl(CORRIDOR_BACKGROUND_PACKAGE, 'light', 'standard')).toBe(
      archiveUrl('light'),
    )
    expect(packageDownloadUrl(CORRIDOR_BACKGROUND_PACKAGE, 'fine', 'standard')).toBe(
      archiveUrl('fine'),
    )
    expect(packageDownloadUrl(CORRIDOR_BACKGROUND_PACKAGE, 'light', 'standard')).not.toBe(
      packageDownloadUrl(CORRIDOR_BACKGROUND_PACKAGE, 'fine', 'standard'),
    )
  })

  it('follows the hiking level for the leveled basemap package (#276)', () => {
    // The raster detail must not move this package, and the hiking level
    // must - the two sheets' dials are separate.
    const standardUrl = packageDownloadUrl(
      BASEMAP_PACKAGE as OfferedPackage,
      'light',
      'standard',
    )
    const fineUrl = packageDownloadUrl(BASEMAP_PACKAGE as OfferedPackage, 'fine', 'fine')

    expect(standardUrl).toBe(dataUrl(getHikingDetail('standard').artifact))
    expect(fineUrl).toBe(dataUrl(getHikingDetail('fine').artifact))
    expect(standardUrl).not.toBe(fineUrl)
    expect(packageDownloadUrl(BASEMAP_PACKAGE as OfferedPackage, 'light', 'fine')).toBe(
      fineUrl,
    )
  })

  it('names the artifact latest.json publishes for each hiking level', () => {
    expect(
      packageArtifactKey(BASEMAP_PACKAGE as OfferedPackage, 'standard', 'standard'),
    ).toBe('at_basemap_package_z13.pmtiles')
    expect(
      packageArtifactKey(BASEMAP_PACKAGE as OfferedPackage, 'standard', 'fine'),
    ).toBe('at_basemap_package.pmtiles')
  })

  it('is one artifact, at any detail level, for a package with one size', () => {
    expect(packageDownloadUrl(PUBLISHED_ELSEWHERE, 'light', 'standard')).toBe(
      dataUrl('example.pmtiles'),
    )
    expect(packageDownloadUrl(PUBLISHED_ELSEWHERE, 'fine', 'standard')).toBe(
      dataUrl('example.pmtiles'),
    )
  })
})

describe('what a sheet will cost', () => {
  it('is the chosen tier’s measured size for the USGS sheet', () => {
    for (const level of ['light', 'standard', 'fine'] as const) {
      expect(sheetSizeBytes(USGS_SHEET, level, 'standard')).toBe(
        getDownloadDetail(level).sizeBytes,
      )
      expect(packageSizeBytes(CORRIDOR_BACKGROUND_PACKAGE, level, 'standard')).toBe(
        getDownloadDetail(level).sizeBytes,
      )
    }
  })

  it('is the package’s own size where it has one', () => {
    expect(packageSizeBytes(PUBLISHED_ELSEWHERE, 'standard', 'standard')).toBe(12_345)
  })

  it('follows the hiking level for the leveled basemap, exactly as published', () => {
    for (const level of ['light', 'standard', 'fine'] as const) {
      expect(packageSizeBytes(BASEMAP_PACKAGE as OfferedPackage, 'light', level)).toBe(
        getHikingDetail(level).basemapSizeBytes,
      )
    }
  })

  it('composes the hiking sheet’s total per level (#276)', () => {
    // What the sheet's picker shows: the level's basemap cut plus its DEM.
    // The DEM became per-level with #1088 - the corridor tapers harder at
    // Light - so this sums the level's own two artifacts rather than adding a
    // constant, which is the thing that would silently stop being true.
    //
    // Light is in this loop since #1107 and is the level that would catch the
    // regression: it is the only one whose basemap AND DEM both differ from
    // every other rung's, so a resolver that fell back to Standard's pair
    // would still look right on Fine.
    for (const level of ['light', 'standard', 'fine'] as const) {
      const detail = getHikingDetail(level)
      expect(hikingSheetSizeBytes(level)).toBe(
        (detail.basemapSizeBytes ?? 0) + (detail.demSizeBytes ?? 0),
      )
    }
  })

  it('resolves each leveled package to its own artifact, not the other one', () => {
    // The 'of' discriminant earns its place here: both packages are leveled
    // now, so a resolver that keyed off the kind alone would hand the DEM's
    // download the basemap's key - the right hash against the wrong bytes.
    for (const level of ['light', 'standard', 'fine'] as const) {
      const detail = getHikingDetail(level)
      expect(
        packageArtifactKey(BASEMAP_PACKAGE as OfferedPackage, 'standard', level),
      ).toBe(detail.artifact)
      expect(packageArtifactKey(DEM_PACKAGE as OfferedPackage, 'standard', level)).toBe(
        detail.demArtifact,
      )
    }
  })

  it('refuses to price a level whose artifact nobody has published', () => {
    // packages.ts's own memory: "the app was offering a Light tier that did
    // not exist". A level with no published size has no honest cost, and a NaN
    // in the remaining-storage sum is exactly the silent wrong number that
    // rule exists to prevent.
    //
    // Driven through a level blanked for the duration rather than through
    // whichever rung happens to be unbuilt this week. Light was that rung
    // between #1088 and #1107 and this test read `'light'` literally; the day
    // its DEM was published the test went green for a reason that had nothing
    // to do with the throw still working. Blanking the table restores what was
    // actually being asserted, and keeps asserting it once every level ships.
    const light = getHikingDetail('light')
    const size = light.demSizeBytes
    light.demSizeBytes = null
    try {
      expect(() =>
        packageSizeBytes(DEM_PACKAGE as OfferedPackage, 'standard', 'light'),
      ).toThrow(/no published dem size/i)
    } finally {
      light.demSizeBytes = size
    }
  })

  it('sums every archive the sheet is made of', () => {
    // One tap brings the whole sheet, so the figure shown beside "may not
    // fit" has to be the whole sheet too.
    const sheet = sheetOf([CORRIDOR_BACKGROUND_PACKAGE, PUBLISHED_ELSEWHERE])

    expect(sheetSizeBytes(sheet, 'standard', 'standard')).toBe(
      getDownloadDetail('standard').sizeBytes + 12_345,
    )
  })

  it('counts only what is offered, never an archive nobody can download', () => {
    const sheet = sheetOf([PUBLISHED_ELSEWHERE, UNPUBLISHED])

    expect(sheetSizeBytes(sheet, 'standard', 'standard')).toBe(12_345)
  })
})
