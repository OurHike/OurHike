// conditions/trail_closures.json in an hour whose areas were not cut
// (decision 213, Q11, the maintainer's poll of 2026-10-15, "Now, in this
// PR"): pipeline/dbt's pub_conditions_trail_closures writes `areas_cut`
// false and names every standing area closure in `uncut_areas`, and the
// phone keeps the area or shade it last drew for each one, in what it shows
// and in the copy it keeps for offline, rather than drawing none of them
// until it next connects.

import 'fake-indexeddb/auto'
import { clear } from 'idb-keyval'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
}))

import { recallPublished } from './conditionsCache'
import {
  fetchPublishedTrailClosures,
  keepUncutAreas,
  PUBLISHED_TRAIL_CLOSURES_KEY,
} from './publishedNotices'
import { trailClosureRows } from '../../preview-shots/fixtures/clubClosures.mjs'

const AREA_ID = 'example_state_parks_status:lake-park-storm'
const SHADE_ID = 'example_open_space_access:closed-lands'
const LINE_ID = 'example_forest_closures:ridge-trail-fire'

/** A file of `rows` baked at `bakedAt`, with the cut's two keys. */
function file(
  bakedAt: string,
  rows: Record<string, unknown>[],
  cut: { areas_cut: boolean; uncut_areas: string[] },
): Record<string, unknown> {
  return { generated_at: bakedAt, closures: rows, ...cut }
}

/** The bucket answers each read with the next of `files`. */
function serve(...files: Record<string, unknown>[]) {
  const queue = [...files]
  vi.spyOn(globalThis, 'fetch').mockImplementation(
    async () => new Response(JSON.stringify(queue.shift()), { status: 200 }),
  )
}

/** The ids a read draws, by shape, once the copy it keeps is stored: the
 *  reader keeps a copy without waiting for the store, and the next read
 *  starts from that copy. */
async function drawn(online: boolean): Promise<Record<string, string[]>> {
  const published = await fetchPublishedTrailClosures({ online })
  if (online && published !== null) {
    const bakedAt = published.generatedAt.toISOString()
    await vi.waitFor(async () => {
      const kept = await recallPublished(PUBLISHED_TRAIL_CLOSURES_KEY)
      expect(new Date(String(kept?.document.generated_at)).toISOString()).toBe(bakedAt)
    })
  }
  const byShape: Record<string, string[]> = {}
  for (const closure of published?.items ?? []) {
    ;(byShape[closure.shape] ??= []).push(closure.notice_id)
  }
  return byShape
}

beforeEach(async () => {
  await clear()
})

afterEach(() => vi.restoreAllMocks())

describe('an area closure the file could not cut this hour (keepUncutAreas)', () => {
  const { line, area, point, shade } = trailClosureRows()

  it('carries the kept area and shade of each id listed, after the file’s own rows', () => {
    const kept = file('2026-10-15T20:00:00Z', [line, area, point, shade], {
      areas_cut: true,
      uncut_areas: [],
    })
    const arrived = file('2026-10-15T21:00:00Z', [line, point], {
      areas_cut: false,
      uncut_areas: [AREA_ID, SHADE_ID],
    })

    expect(keepUncutAreas(arrived, kept)).toEqual({
      ...arrived,
      closures: [line, point, area, shade],
    })
  })

  it('carries nothing for an id not listed, a line or point row, or an id the file already draws', () => {
    const kept = file('2026-10-15T20:00:00Z', [line, area, point, shade], {
      areas_cut: true,
      uncut_areas: [],
    })
    // The shade is lifted (not listed), the line is not an area, and the
    // area arrived drawn afresh.
    const fresh = { ...area, title: 'Redrawn this hour' }
    const arrived = file('2026-10-15T21:00:00Z', [fresh], {
      areas_cut: true,
      uncut_areas: [AREA_ID, LINE_ID],
    })

    expect(keepUncutAreas(arrived, kept)).toBe(arrived)
  })

  it('keeps a file exactly as it arrived when nothing is kept or nothing is listed, or the file predates the list', () => {
    const arrived = file('2026-10-15T21:00:00Z', [line], {
      areas_cut: false,
      uncut_areas: [AREA_ID],
    })
    const kept = file('2026-10-15T20:00:00Z', [line, area], {
      areas_cut: true,
      uncut_areas: [],
    })
    const { areas_cut: _cut, uncut_areas: _uncut, ...older } = arrived

    expect(keepUncutAreas(arrived, null)).toBe(arrived)
    expect(keepUncutAreas({ ...arrived, uncut_areas: [] }, kept).closures).toEqual([line])
    expect(keepUncutAreas(older, kept)).toBe(older)
  })
})

describe('reading conditions/trail_closures.json across an hour with no lines', () => {
  const { line, area, point, shade } = trailClosureRows()

  it('draws the last cut’s areas through an uncut hour, keeps them for offline, and drops one lifted later', async () => {
    serve(
      // A cut hour: every closure drawn.
      file('2026-10-15T20:00:00Z', [line, area, point, shade], {
        areas_cut: true,
        uncut_areas: [],
      }),
      // An hour with no lines: both areas standing, neither drawn by the file.
      file('2026-10-15T21:00:00Z', [line, point], {
        areas_cut: false,
        uncut_areas: [AREA_ID, SHADE_ID],
      }),
      // A second such hour, carried from the copy the first one kept.
      file('2026-10-15T22:00:00Z', [line, point], {
        areas_cut: false,
        uncut_areas: [AREA_ID, SHADE_ID],
      }),
      // A cut hour again, in which the shaded closure has been lifted.
      file('2026-10-15T23:00:00Z', [line, area, point], {
        areas_cut: true,
        uncut_areas: [],
      }),
    )

    expect(await drawn(true)).toEqual({
      line: [LINE_ID],
      area: [AREA_ID],
      point: [point.notice_id],
      shade: [SHADE_ID],
    })
    const uncut = {
      line: [LINE_ID],
      point: [point.notice_id],
      area: [AREA_ID],
      shade: [SHADE_ID],
    }
    expect(await drawn(true)).toEqual(uncut)
    // Relaunched with no signal: the copy kept in that hour still has them.
    expect(await drawn(false)).toEqual(uncut)
    expect(await drawn(true)).toEqual(uncut)
    expect(await drawn(true)).toEqual({
      line: [LINE_ID],
      area: [AREA_ID],
      point: [point.notice_id],
    })
  })

  it('draws no area in an uncut hour on a phone that never kept one, rather than guessing', async () => {
    serve(
      file('2026-10-15T21:00:00Z', [line, point], {
        areas_cut: false,
        uncut_areas: [AREA_ID],
      }),
    )

    expect(await drawn(true)).toEqual({ line: [LINE_ID], point: [point.notice_id] })
  })
})
