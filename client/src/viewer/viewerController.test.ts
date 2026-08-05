// Tests for viewerController.ts - what dropping files does to the map and
// the status line. openArchive is mocked here (its own tests run it against
// real archive bytes); what is under test is the orchestration.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { Protocol } from 'pmtiles'
import { createViewerController } from './viewerController'
import { openArchive, type OpenedArchive } from './viewerArchives'
import { LIVE_TOPO_LAYER_IDS } from '../map/liveTopo'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'

vi.mock('./viewerArchives', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./viewerArchives')>()),
  openArchive: vi.fn(),
}))

const HEADER = {
  tileType: 1,
  minZoom: 0,
  maxZoom: 14,
  minLon: -80,
  minLat: 34,
  maxLon: -68,
  maxLat: 46,
}

function opened(slot: OpenedArchive['slot'], fileName: string): OpenedArchive {
  return {
    slot,
    url: `pmtiles://viewer:${slot}`,
    header: HEADER,
    fileName,
    sizeBytes: 532_400_000,
  }
}

function file(name: string): File {
  return new File(['bytes'], name)
}

function makeController() {
  const map = new MockMap({})
  const statuses: string[] = []
  const controller = createViewerController({
    map,
    protocol: new Protocol(),
    onStatus: (text) => statuses.push(text),
  })
  return { map, statuses, controller }
}

beforeEach(() => {
  vi.mocked(openArchive).mockReset()
  resetMapLibreMock()
})

describe('createViewerController', () => {
  it('renders a dropped basemap with the live sheet layers and fits its bounds', async () => {
    vi.mocked(openArchive).mockResolvedValue(opened('basemap', 'at.pmtiles'))
    const { map, statuses, controller } = makeController()

    await controller.handleFiles([file('at.pmtiles')])

    const style = map.styles.at(-1) as { layers: Array<{ id: string }> }
    expect(style.layers.map((l) => l.id)).toContain(LIVE_TOPO_LAYER_IDS.wood)
    expect(map.cameraMoves[0]).toMatchObject({
      fitBounds: [
        [-80, 34],
        [-68, 46],
      ],
    })
    expect(statuses.at(-1)).toContain('at.pmtiles')
    expect(statuses.at(-1)).toContain('z0–14')
  })

  it('a second drop composes with the first and leaves the camera alone', async () => {
    vi.mocked(openArchive)
      .mockResolvedValueOnce(opened('basemap', 'at.pmtiles'))
      .mockResolvedValueOnce(opened('dem', 'dem.pmtiles'))
    const { map, statuses, controller } = makeController()

    await controller.handleFiles([file('at.pmtiles')])
    await controller.handleFiles([file('dem.pmtiles')])

    const style = map.styles.at(-1) as { layers: Array<{ id: string }> }
    expect(style.layers.map((l) => l.id)).toContain(LIVE_TOPO_LAYER_IDS.hillshade)
    expect(map.cameraMoves).toHaveLength(1)
    expect(statuses.at(-1)).toContain('at.pmtiles')
    expect(statuses.at(-1)).toContain('dem.pmtiles')
  })

  it('one unreadable file reports itself and does not cost the archives already shown', async () => {
    vi.mocked(openArchive)
      .mockResolvedValueOnce(opened('basemap', 'at.pmtiles'))
      .mockRejectedValueOnce(new Error('not a PMTiles archive'))
    const { map, statuses, controller } = makeController()

    await controller.handleFiles([file('at.pmtiles')])
    const stylesBefore = map.styles.length
    await controller.handleFiles([file('junk.bin')])

    expect(statuses).toContain('not a PMTiles archive')
    // The style is rebuilt from what is open - the basemap survives.
    expect(map.styles.length).toBeGreaterThan(stylesBefore)
    expect(controller.opened.has('basemap')).toBe(true)
  })

  it('nothing openable means no style write at all', async () => {
    vi.mocked(openArchive).mockRejectedValue(new Error('nope'))
    const { map, controller } = makeController()

    await controller.handleFiles([file('junk.bin')])

    expect(map.styles).toHaveLength(0)
  })
})
