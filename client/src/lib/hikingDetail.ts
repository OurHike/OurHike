// The hiking sheet's download levels (#276) - downloadDetail.ts's sibling,
// for the other sheet.
//
// The USGS raster's levels are whole alternative archives; the hiking
// sheet's levels switch only its BASEMAP cut - the z13 Standard package or
// the full z14 Fine one - while the DEM is the same archive at either level.
// That asymmetry is why this table carries the basemap artifact per level
// rather than a whole-sheet size: the sheet's total is composed where sheets
// are composed (lib/packages.ts), from these bytes plus the DEM's.
//
// Sizes are the published artifacts' exact bytes, per the same honesty bar
// as everything in packages.ts. Standard is recommended for the same reason
// it is the preference default (userPreferences.ts): it is the level that
// fits the storage envelope, and z14 is individual-building detail MapLibre
// renders acceptably by overzooming z13 anyway.

import type { HikingDetailLevel } from './userPreferences'

export interface HikingDetail {
  level: HikingDetailLevel
  /** The flat R2 key of this level's basemap cut, as latest.json names it -
   *  publish.py's OFFLINE_SHEET_ARCHIVES spelling. */
  artifact: string
  /** That artifact's exact published size. */
  basemapSizeBytes: number
  recommended: boolean
}

export const HIKING_DETAIL_LEVELS: HikingDetail[] = [
  {
    level: 'standard',
    artifact: 'at_basemap_package_z13.pmtiles',
    basemapSizeBytes: 182_286_799,
    recommended: true,
  },
  {
    level: 'fine',
    artifact: 'at_basemap_package.pmtiles',
    basemapSizeBytes: 532_459_439,
    recommended: false,
  },
]

export function getHikingDetail(level: HikingDetailLevel): HikingDetail {
  const found = HIKING_DETAIL_LEVELS.find((d) => d.level === level)
  if (!found) throw new Error(`Unknown hiking detail level: ${level}`)
  return found
}
