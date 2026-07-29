// The map canvas itself. Chrome (header, ribbon, tab bar, controls) composes
// around this rather than living inside it.
//
// Everything delicate here is lifecycle. A map built twice means two WebGL
// contexts, two GPS watchers and doubled range reads against an on-device
// archive that can be 1.18 GB; a map never torn down leaks all of the same.
// React StrictMode mounts, unmounts and remounts on purpose in development to
// surface exactly that, so the effect below is written to survive it: build
// once per effect run, and fully undo the build on cleanup.

import { useEffect, useRef } from 'react'
import { Map as MapLibreMap } from 'maplibre-gl'
import { registerPMTilesProtocol } from './protocol'
import { buildMapStyle } from './style'

export interface MapViewProps {
  /** `pmtiles://` URL for the downloaded topo archive. */
  topoArchiveUrl: string
  /** Local URL of the exported trail lines. */
  trailsUrl: string
  /** Initial centre only - later camera moves go through the map imperatively. */
  center?: [number, number]
  /** Initial zoom only. */
  zoom?: number
}

const DEFAULT_CENTER: [number, number] = [-77.1, 39.3]
const DEFAULT_ZOOM = 12

export function MapView({ topoArchiveUrl, trailsUrl, center, zoom }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<MapLibreMap | null>(null)

  // `center`/`zoom` are deliberately NOT dependencies. A parent writing
  // center={[x, y]} inline hands over a new array identity on every render; if
  // that drove this effect the map would be destroyed and rebuilt each time the
  // parent re-rendered. They seed the initial camera, and nothing more.
  useEffect(() => {
    const container = containerRef.current
    if (container === null) return

    // The style resolves pmtiles:// URLs, so the protocol has to exist first.
    registerPMTilesProtocol()

    const map = new MapLibreMap({
      container,
      style: buildMapStyle({ topoArchiveUrl, trailsUrl }),
      center: center ?? DEFAULT_CENTER,
      zoom: zoom ?? DEFAULT_ZOOM,
      // Attribution is rendered by the app's own chrome, positioned per
      // WIREFRAMES.md, rather than by MapLibre's default control.
      attributionControl: false,
    })
    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
    // Intentionally omitting `center`/`zoom` - see the note above. Including
    // them would rebuild the whole map whenever a parent re-rendered with an
    // inline array, which is the bug this omission exists to avoid.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [topoArchiveUrl, trailsUrl])

  return (
    <div
      ref={containerRef}
      className="map-view"
      role="region"
      aria-label="Trail map"
      data-testid="map-view"
    />
  )
}
