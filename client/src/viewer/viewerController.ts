// The viewer's state: which archives are open, what the map shows, what the
// status line says (issue #202). Split from main.ts so every decision here
// is testable against the maplibre mock - main.ts is DOM glue.

import type { Protocol } from 'pmtiles'
import { openArchive, type OpenedArchive, type ViewerSlot } from './viewerArchives'
import { buildViewerStyle, type ViewerSlots } from './viewerStyle'

/** The slice of maplibre's Map the controller drives. */
export interface ViewerMap {
  setStyle(style: unknown): unknown
  fitBounds(bounds: [[number, number], [number, number]], options?: unknown): unknown
}

export interface ViewerController {
  handleFiles(files: Iterable<File>): Promise<void>
  /** The slots currently rendered - read by tests and the status line. */
  readonly opened: ReadonlyMap<ViewerSlot, OpenedArchive>
}

const SLOT_LABELS: Record<ViewerSlot, string> = {
  basemap: 'vector basemap',
  dem: 'elevation (hillshade)',
  raster: 'raster sheet',
}

function describe(archive: OpenedArchive): string {
  const mb = (archive.sizeBytes / 1e6).toFixed(1)
  return `${archive.fileName}: ${SLOT_LABELS[archive.slot]}, z${archive.header.minZoom}–${archive.header.maxZoom}, ${mb} MB`
}

export function createViewerController(deps: {
  map: ViewerMap
  protocol: Protocol
  onStatus: (text: string) => void
}): ViewerController {
  const opened = new Map<ViewerSlot, OpenedArchive>()
  let fitted = false

  async function handleFiles(files: Iterable<File>): Promise<void> {
    for (const file of files) {
      try {
        const archive = await openArchive(deps.protocol, file)
        opened.set(archive.slot, archive)

        // Fit once, to the first archive's own header bounds - after that
        // the reviewer owns the camera, and a second drop must not yank the
        // view away from whatever they were inspecting.
        if (!fitted) {
          const { minLon, minLat, maxLon, maxLat } = archive.header
          deps.map.fitBounds(
            [
              [minLon, minLat],
              [maxLon, maxLat],
            ],
            { padding: 20 },
          )
          fitted = true
        }
      } catch (error) {
        // One bad file must not cost the archives already rendered - report
        // it and carry on. "Nothing happened" is the one answer that leaves
        // a reviewer guessing (the same stance useArchiveDownload takes).
        deps.onStatus(
          error instanceof Error ? error.message : `Could not open ${file.name}.`,
        )
        continue
      }
    }

    if (opened.size === 0) return

    const slots: ViewerSlots = {}
    for (const [slot, archive] of opened) slots[slot] = archive.url
    deps.map.setStyle(buildViewerStyle(slots))
    deps.onStatus([...opened.values()].map(describe).join(' · '))
  }

  return { handleFiles, opened }
}
