// The viewer page's bootstrap (issue #202): DOM glue only, excluded from
// coverage the way src/main.tsx is - every decision lives in
// viewerController.ts and viewerStyle.ts, which are tested.

import { Map as MapLibreMap } from 'maplibre-gl'
import { registerPMTilesProtocol } from '../map/protocol'
import { registerMapWorker } from '../map/mapWorker'
import { buildViewerStyle } from './viewerStyle'
import { createViewerController } from './viewerController'

registerMapWorker()
const protocol = registerPMTilesProtocol()

const status = document.getElementById('viewer-status')
const input = document.getElementById('viewer-files') as HTMLInputElement | null
const container = document.getElementById('viewer-map')

if (container !== null) {
  const map = new MapLibreMap({
    container,
    style: buildViewerStyle({}),
    center: [-77.5, 39.5],
    zoom: 5,
    attributionControl: { compact: false },
  })

  const controller = createViewerController({
    map,
    protocol,
    onStatus: (text) => {
      if (status !== null) status.textContent = text
    },
  })

  input?.addEventListener('change', () => {
    if (input.files !== null) void controller.handleFiles(input.files)
  })

  // Drag-and-drop anywhere on the page - the browser's default for a dropped
  // file is to navigate to it, which would replace the viewer with a download.
  document.addEventListener('dragover', (event) => event.preventDefault())
  document.addEventListener('drop', (event) => {
    event.preventDefault()
    const files = event.dataTransfer?.files
    if (files !== undefined && files.length > 0) void controller.handleFiles(files)
  })
}
