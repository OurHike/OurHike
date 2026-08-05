// What the map is allowed to say about its own background, and when.
//
// The rule under every case here is that "unreachable" means errored AND
// nothing ever drew. Either half alone is a false statement: a source that has
// not answered yet is loading, and a source that failed one tile while serving
// the rest is working. Saying otherwise over a map a hiker is reading is the
// same category of error as a stale position drawn like a live one.

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { MockMap, resetMapLibreMock } from '../test/mocks/maplibre-gl'
import {
  attachLiveSourceHealth,
  HEALTHY,
  type LiveSourceHealth,
} from './liveSourceHealth'
import { OSM_SOURCE_ID } from './liveTopo'
import { DEM_SOURCE_ID } from './terrain'

/** A tile that loaded, as MapLibre reports one: the `tile` is the proof. */
function tileArrived(sourceId: string) {
  return { sourceId, tile: { state: 'loaded' } }
}

function sourceFailed(sourceId: string, message = 'Failed to fetch') {
  return { sourceId, error: new Error(message) }
}

describe('attachLiveSourceHealth', () => {
  let warn: ReturnType<typeof vi.spyOn>

  beforeEach(() => {
    resetMapLibreMock()
    warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

  afterEach(() => {
    warn.mockRestore()
  })

  function attach() {
    const map = new MockMap({})
    const reports: LiveSourceHealth[] = []
    const detach = attachLiveSourceHealth(map as never, (h) => reports.push(h))
    return { map, reports, detach }
  }

  it('reports the basemap unreachable when it errors having drawn nothing', () => {
    const { map, reports } = attach()

    map.emit('error', sourceFailed(OSM_SOURCE_ID))

    expect(reports).toEqual([{ basemap: true, elevation: false }])
  })

  it('says nothing when a source that has already drawn loses one tile', () => {
    // The distinction the whole module exists to draw. A working sheet that
    // drops a tile at the edge of the view is not an unreachable one, and
    // flagging it would put a false claim on a map that is drawing fine.
    const { map, reports } = attach()

    map.emit('sourcedata', tileArrived(OSM_SOURCE_ID))
    map.emit('error', sourceFailed(OSM_SOURCE_ID))

    expect(reports).toEqual([])
  })

  it('clears itself when a tile finally lands, which is walking back into signal', () => {
    const { map, reports } = attach()

    map.emit('error', sourceFailed(OSM_SOURCE_ID))
    map.emit('sourcedata', tileArrived(OSM_SOURCE_ID))

    expect(reports).toEqual([
      { basemap: true, elevation: false },
      { basemap: false, elevation: false },
    ])
  })

  it('coalesces a whole screen of failing tiles into one report', () => {
    // Twelve DEM tiles fail together on a single pan. Twelve renders of the
    // same flag is the difference between a status line and a flicker.
    const { map, reports } = attach()

    for (let i = 0; i < 12; i += 1) map.emit('error', sourceFailed(DEM_SOURCE_ID))

    expect(reports).toEqual([{ basemap: false, elevation: true }])
  })

  it('tracks the basemap and the elevation model separately', () => {
    const { map, reports } = attach()

    map.emit('error', sourceFailed(DEM_SOURCE_ID))
    map.emit('error', sourceFailed(OSM_SOURCE_ID))

    expect(reports.at(-1)).toEqual({ basemap: true, elevation: true })
  })

  it('ignores sources it does not speak for', () => {
    // The downloaded archive reports through the Downloads screen and the
    // trail lines are local. A second opinion here would be a second place to
    // keep right.
    const { map, reports } = attach()

    map.emit('error', sourceFailed('usgs-topo'))
    map.emit('error', sourceFailed('trails'))

    expect(reports).toEqual([])
  })

  it('ignores metadata events, which prove nothing about ink on the screen', () => {
    const { map, reports } = attach()

    map.emit('sourcedata', { sourceId: OSM_SOURCE_ID, sourceDataType: 'metadata' })
    map.emit('error', sourceFailed(OSM_SOURCE_ID))

    expect(reports).toEqual([{ basemap: true, elevation: false }])
  })

  it('still logs every error, because attaching this listener silenced MapLibre', () => {
    // Not decoration. util/evented.ts only console.errors an ErrorEvent when
    // NOBODY in the parent chain listens, and ui/map.ts adds no internal
    // listener - so attaching a handler here turns MapLibre's own reporting
    // off. Without this the app would be quieter than before in exactly the
    // failure the module was added to explain.
    const { map } = attach()

    map.emit('error', sourceFailed('some-other-source', 'boom'))

    expect(warn).toHaveBeenCalledTimes(1)
  })

  it('survives an error event carrying nothing it can read', () => {
    // MapLibre fires plenty of errors that never passed a source - a style
    // parse failure, a worker that died. They still deserve the console line,
    // and they say nothing about whether the background arrived.
    const { map, reports } = attach()

    map.emit('error')
    map.emit('error', { error: new Error('no source on this one') })

    expect(reports).toEqual([])
    expect(warn).toHaveBeenCalledTimes(2)
  })

  it('ignores a tile that belongs to a source it does not watch', () => {
    // The archive draws tiles constantly. Counting one as proof the live sheet
    // arrived would clear a flag the live sheet never earned.
    const { map, reports } = attach()

    map.emit('error', sourceFailed(OSM_SOURCE_ID))
    map.emit('sourcedata', tileArrived('usgs-topo'))

    expect(reports).toEqual([{ basemap: true, elevation: false }])
  })

  it('treats a null tile as no arrival at all', () => {
    const { map, reports } = attach()

    map.emit('sourcedata', { sourceId: OSM_SOURCE_ID, tile: null })
    map.emit('error', sourceFailed(OSM_SOURCE_ID))

    expect(reports).toEqual([{ basemap: true, elevation: false }])
  })

  it('does not re-report once a source is already known to draw', () => {
    const { map, reports } = attach()

    map.emit('sourcedata', tileArrived(OSM_SOURCE_ID))
    map.emit('sourcedata', tileArrived(OSM_SOURCE_ID))

    expect(reports).toEqual([])
  })

  it('detaches both listeners and withdraws what it claimed', () => {
    // These flags describe one map. A map that has been torn down has no
    // background to be unreachable, and leaving the claim standing would
    // outlive the thing it was about.
    const { map, reports, detach } = attach()
    map.emit('error', sourceFailed(OSM_SOURCE_ID))

    detach()

    expect(reports.at(-1)).toEqual(HEALTHY)
    expect(map.listenerCount('error')).toBe(0)
    expect(map.listenerCount('sourcedata')).toBe(0)
  })

  it('stays quiet on detach when it never claimed anything', () => {
    const { reports, detach } = attach()

    detach()

    expect(reports).toEqual([])
  })
})
