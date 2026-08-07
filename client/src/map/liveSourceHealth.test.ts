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
  type SourceReport,
} from './liveSourceHealth'
import { OSM_SOURCE_ID } from './liveTopo'
import { DEM_SOURCE_ID } from './terrain'
import { TOPO_SOURCE_ID } from './style'

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
    /** Every report, for the cases where `drew` or `withdrawn` IS the subject. */
    const all: SourceReport[] = []
    /** The unreachable half of each, which is what most cases here are about. */
    const reports: LiveSourceHealth[] = []
    const detach = attachLiveSourceHealth(map as never, (report) => {
      all.push(report)
      reports.push(report.unreachable)
    })
    return { map, all, reports, detach }
  }

  /** What a source that has drawn nothing and failed nothing looks like. */
  const NOTHING_YET = HEALTHY

  it('reports the basemap unreachable when it errors having drawn nothing', () => {
    const { map, reports } = attach()

    map.emit('error', sourceFailed(OSM_SOURCE_ID))

    expect(reports).toEqual([{ basemap: true, elevation: false, archive: false }])
  })

  it('claims nothing when a source that has already drawn loses one tile', () => {
    // The distinction the whole module exists to draw. A working sheet that
    // drops a tile at the edge of the view is not an unreachable one, and
    // flagging it would put a false claim on a map that is drawing fine.
    const { map, reports, all } = attach()

    map.emit('sourcedata', tileArrived(OSM_SOURCE_ID))
    map.emit('error', sourceFailed(OSM_SOURCE_ID))

    // The tile arriving IS reported since #352 - a source that has drawn is
    // the only thing that can retract a failure an earlier map observed - but
    // it claims nothing is unreachable, before or after the lost tile.
    expect(reports).toEqual([NOTHING_YET])
    expect(all.at(-1)?.drew.basemap).toBe(true)
  })

  it('clears itself when a tile finally lands, which is walking back into signal', () => {
    const { map, reports } = attach()

    map.emit('error', sourceFailed(OSM_SOURCE_ID))
    map.emit('sourcedata', tileArrived(OSM_SOURCE_ID))

    expect(reports).toEqual([
      { basemap: true, elevation: false, archive: false },
      { basemap: false, elevation: false, archive: false },
    ])
  })

  it('coalesces a whole screen of failing tiles into one report', () => {
    // Twelve DEM tiles fail together on a single pan. Twelve renders of the
    // same flag is the difference between a status line and a flicker.
    const { map, reports } = attach()

    for (let i = 0; i < 12; i += 1) map.emit('error', sourceFailed(DEM_SOURCE_ID))

    expect(reports).toEqual([{ basemap: false, elevation: true, archive: false }])
  })

  it('tracks the basemap and the elevation model separately', () => {
    const { map, reports } = attach()

    map.emit('error', sourceFailed(DEM_SOURCE_ID))
    map.emit('error', sourceFailed(OSM_SOURCE_ID))

    expect(reports.at(-1)).toEqual({ basemap: true, elevation: true, archive: false })
  })

  it('ignores sources it does not speak for', () => {
    // The trail lines and the pins are drawn from data the app already holds,
    // so a failure there is a different report on a different screen. The
    // downloaded archive used to be in this list and is not any more (#314) -
    // see the archive cases below.
    const { map, reports } = attach()

    map.emit('error', sourceFailed('trails'))
    map.emit('error', sourceFailed('poi'))

    expect(reports).toEqual([])
  })

  it('reports the downloaded archive when it errors having drawn nothing', () => {
    // The signal #314 needed and did not have. What it MEANS depends on
    // whether an archive is on the phone at all, which this module cannot see
    // and deliberately does not guess - lib/backgroundHealth.ts joins the two.
    const { map, reports } = attach()

    map.emit('error', sourceFailed(TOPO_SOURCE_ID))

    expect(reports).toEqual([{ basemap: false, elevation: false, archive: true }])
  })

  it('holds the archive to the same errored-and-never-drew rule', () => {
    // A raster archive that draws the corridor and fails at its edge is a
    // working download. Flagging it would tell a hiker to re-fetch 314 MB
    // because they panned off the strip.
    const { map, reports, all } = attach()

    map.emit('sourcedata', tileArrived(TOPO_SOURCE_ID))
    map.emit('error', sourceFailed(TOPO_SOURCE_ID))

    expect(reports).toEqual([NOTHING_YET])
    expect(all.at(-1)?.drew.archive).toBe(true)
  })

  it('tracks the archive and the live sheet separately', () => {
    // Offline with a damaged download, both fail, and they are not one fact:
    // the download is fixable where the hiker stands and the live sheet is
    // not, so the strip has to be able to tell them apart.
    const { map, reports } = attach()

    map.emit('error', sourceFailed(TOPO_SOURCE_ID))
    map.emit('error', sourceFailed(OSM_SOURCE_ID))

    expect(reports.at(-1)).toEqual({ basemap: true, elevation: false, archive: true })
  })

  it('ignores metadata events, which prove nothing about ink on the screen', () => {
    const { map, reports } = attach()

    map.emit('sourcedata', { sourceId: OSM_SOURCE_ID, sourceDataType: 'metadata' })
    map.emit('error', sourceFailed(OSM_SOURCE_ID))

    expect(reports).toEqual([{ basemap: true, elevation: false, archive: false }])
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

  it('does not let one source’s tile clear another source’s flag', () => {
    // The archive draws tiles constantly, and on the offline background it is
    // the only thing drawing. Counting one as proof the live sheet arrived
    // would clear a flag the live sheet never earned.
    const { map, reports, all } = attach()

    map.emit('error', sourceFailed(OSM_SOURCE_ID))
    map.emit('sourcedata', tileArrived(TOPO_SOURCE_ID))

    // Two reports - the failure, then the archive's tile - and the basemap's
    // claim stands through both. The second is what a shell needs to retract
    // a remembered ARCHIVE failure, and it must not retract this one.
    expect(reports).toEqual([
      { basemap: true, elevation: false, archive: false },
      { basemap: true, elevation: false, archive: false },
    ])
    expect(all.at(-1)?.drew).toEqual({ basemap: false, elevation: false, archive: true })
  })

  it('treats a null tile as no arrival at all', () => {
    const { map, reports } = attach()

    map.emit('sourcedata', { sourceId: OSM_SOURCE_ID, tile: null })
    map.emit('error', sourceFailed(OSM_SOURCE_ID))

    expect(reports).toEqual([{ basemap: true, elevation: false, archive: false }])
  })

  it('does not re-report once a source is already known to draw', () => {
    // One report for the first tile, and silence after it: the fact does not
    // change, and a report per tile would be a render per tile.
    const { map, all } = attach()

    map.emit('sourcedata', tileArrived(OSM_SOURCE_ID))
    map.emit('sourcedata', tileArrived(OSM_SOURCE_ID))

    expect(all).toHaveLength(1)
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

describe('what has actually drawn (#352)', () => {
  // The half that was missing, and the reason a shell could not tell a healthy
  // map from a silent one. Every case here is about a report EXISTING at all -
  // a map that says nothing cannot retract anything.

  function attach() {
    const map = new MockMap({})
    const all: SourceReport[] = []
    const detach = attachLiveSourceHealth(map as never, (report) => all.push(report))
    return { map, all, detach }
  }

  beforeEach(() => {
    resetMapLibreMock()
    vi.spyOn(console, 'warn').mockImplementation(() => {})
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('reports a source that draws without ever having failed', () => {
    // The bug in one line. This map has nothing to complain about, so under
    // the old contract it said nothing at all - and a shell remembering an
    // earlier map's failure went on calling a good archive damaged for the
    // rest of the session.
    const { map, all } = attach()

    map.emit('sourcedata', tileArrived(TOPO_SOURCE_ID))

    expect(all).toHaveLength(1)
    expect(all[0]).toEqual({
      unreachable: HEALTHY,
      drew: { basemap: false, elevation: false, archive: true },
      withdrawn: false,
    })
  })

  it('marks only the teardown report as withdrawn', () => {
    const { map, all, detach } = attach()

    map.emit('error', sourceFailed(OSM_SOURCE_ID))
    expect(all.at(-1)?.withdrawn).toBe(false)

    detach()

    expect(all.at(-1)).toEqual({
      unreachable: HEALTHY,
      drew: HEALTHY,
      withdrawn: true,
    })
  })

  it('says nothing on detach when it claimed nothing, drawn or not', () => {
    // `drew` describes a map that no longer exists and nothing downstream
    // keeps it, so there is no claim to withdraw and no reason to speak.
    const { map, all, detach } = attach()

    map.emit('sourcedata', tileArrived(OSM_SOURCE_ID))
    const before = all.length

    detach()

    expect(all).toHaveLength(before)
  })
})
