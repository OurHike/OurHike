// The hiking sheet's download levels (#276) - downloadDetail.ts's sibling,
// for the other sheet.
//
// The USGS raster's levels are whole alternative archives. The hiking sheet's
// switch its BASEMAP cut - the z13 Standard package or the full z14 Fine one -
// and, since #1088, its DEM as well: the terrain corridor narrows with depth
// (pipeline/export_dem.py's CORRIDOR_TAPER_MILES), and a Light level is a
// harder taper rather than a shallower pyramid. Both artifacts are therefore
// per-level, which is why this table carries an artifact and a size for each
// rather than a whole-sheet total; the sheet's total is composed where sheets
// are composed (lib/packages.ts).
//
// Sizes are the published artifacts' exact bytes, per the same honesty bar as
// everything in packages.ts. Standard is recommended for the same reason it is
// the preference default (userPreferences.ts): it is the level that fits the
// storage envelope, and z14 is individual-building detail MapLibre renders
// acceptably by overzooming z13 anyway.
//
// A LEVEL WHOSE ARTIFACT IS NOT IN THE BUCKET CARRIES `published: false` AND A
// NULL SIZE, and that is this file's version of packages.ts's `source: null`
// rule. The comment there records what it is defending against - "the app was
// offering a Light tier that did not exist" - and calls the failure by its
// right name: a 404 on a mountain. A level can be catalogued here, typed, and
// referenced by the picker long before `publish.py` has actually put its bytes
// behind a key; what it may not do is become choosable. `published` is the one
// gate, and it flips only when a maintainer has run the build and measured the
// object in the bucket.

import type { HikingDetailLevel } from './userPreferences'

export interface HikingDetail {
  level: HikingDetailLevel
  /** The flat R2 key of this level's basemap cut, as latest.json names it -
   *  publish.py's OFFLINE_SHEET_ARCHIVES spelling. */
  artifact: string
  /** That artifact's exact published size, or null while it is unpublished. */
  basemapSizeBytes: number | null
  /** The flat R2 key of this level's DEM, same mapping. Leveled since #1088. */
  demArtifact: string
  /** That artifact's exact published size, or null while it is unpublished. */
  demSizeBytes: number | null
  recommended: boolean
  /** Whether both of this level's artifacts are actually in the bucket. See
   *  the header - this is the gate that keeps an unbuilt level off the screen. */
  published: boolean
}

export const HIKING_DETAIL_LEVELS: HikingDetail[] = [
  {
    // NOT OFFERED YET, and the null DEM size is the honest reason rather than
    // an oversight. `dem_light.pmtiles` is a real artifact name publish.py
    // knows (#1088), but no build has produced it, so nobody can state its
    // bytes. The projection from the measured per-zoom tile counts is ~249 MB
    // of terrain against Standard's 607 - reasoned, not measured, which is
    // exactly the grade that may not be shown to a hiker deciding whether they
    // have room. Flip `published` when build-dem.yml has run with the harder
    // taper and the object has been weighed in the bucket, and put its exact
    // bytes here in the same change.
    level: 'light',
    artifact: 'at_basemap_package_z13.pmtiles',
    basemapSizeBytes: 182_286_799,
    demArtifact: 'dem_light.pmtiles',
    demSizeBytes: null,
    recommended: false,
    published: false,
  },
  {
    // THE DEM SIZE HERE IS THE UNTAPERED ARCHIVE, and it is correct until the
    // rebuild lands. #1088 narrows Standard's terrain too, which will move
    // this number - so the tapered build and this constant have to change in
    // one go. verify_release.py check 18 fails a release where an advertised
    // size drifts more than 2% from the bucket, which is what stops the two
    // separating quietly.
    level: 'standard',
    artifact: 'at_basemap_package_z13.pmtiles',
    basemapSizeBytes: 182_286_799,
    demArtifact: 'dem.pmtiles',
    demSizeBytes: 607_265_661,
    recommended: true,
    published: true,
  },
  {
    level: 'fine',
    artifact: 'at_basemap_package.pmtiles',
    basemapSizeBytes: 532_459_439,
    demArtifact: 'dem.pmtiles',
    demSizeBytes: 607_265_661,
    recommended: false,
    published: true,
  },
]

export function getHikingDetail(level: HikingDetailLevel): HikingDetail {
  const found = HIKING_DETAIL_LEVELS.find((d) => d.level === level)
  if (!found) throw new Error(`Unknown hiking detail level: ${level}`)
  return found
}

/**
 * The levels a hiker may actually be asked to take - catalogued, and with both
 * artifacts published.
 *
 * The same filter `offeredPackages()` applies to packages, one level up. Every
 * screen that OFFERS a hiking-sheet level reads this; the picker still draws
 * the unoffered rungs greyed, because a missing row cannot say whether this
 * sheet has no Light version or whether the app forgot to ask (WIREFRAMES.md
 * §4).
 */
export function offeredHikingDetails(): HikingDetail[] {
  return HIKING_DETAIL_LEVELS.filter((d) => d.published)
}
