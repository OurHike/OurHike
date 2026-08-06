// Whole-corridor download detail levels. See WIREFRAMES.md's Known
// Deviations #1: the wireframe's per-section download list is superseded by
// ROADMAP.md Phase 2's decision - one package for the whole corridor, with
// this Light/Standard/Fine choice as the *only* download's detail, not a
// per-section override. Sizes are the real measured whole-corridor figures
// from pipeline/README.md, not derived per-section ratios.

export type DetailLevel = 'light' | 'standard' | 'fine'

export interface DownloadDetail {
  level: DetailLevel
  zoom: 11 | 12 | 13
  sizeBytes: number
  recommended: boolean
}

export const DOWNLOAD_DETAIL_LEVELS: DownloadDetail[] = [
  { level: 'light', zoom: 11, sizeBytes: 68_900_000, recommended: false },
  { level: 'standard', zoom: 12, sizeBytes: 300_300_000, recommended: true },
  { level: 'fine', zoom: 13, sizeBytes: 1_179_200_000, recommended: false },
]

export function getDownloadDetail(level: DetailLevel): DownloadDetail {
  const found = DOWNLOAD_DETAIL_LEVELS.find((d) => d.level === level)
  if (!found) throw new Error(`Unknown download detail level: ${level}`)
  return found
}

/** The reverse lookup, for reading the choice back out of
 *  UserPreferences.max_background_zoom - which is where it is stored, since
 *  the zoom ceiling IS what the choice means. */
export function detailLevelForZoom(zoom: number): DetailLevel {
  const found = DOWNLOAD_DETAIL_LEVELS.find((d) => d.zoom === zoom)
  if (!found) throw new Error(`No download detail level for zoom ${zoom}`)
  return found.level
}
