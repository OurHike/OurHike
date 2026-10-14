// conditions/trail_closures.json, read and checked (the maintainer's S6, poll
// of 2026-10-11): every club closure, each a conditions/notices.json row plus
// the shape the map crosses it out as.
//
// These hold the reader to the file's contract, row by row, with the
// hand-made file in preview-shots/fixtures/clubClosures.mjs as the good case:
// every row the map can draw is kept, and every row it cannot is refused one
// at a time, never the file.

import { afterEach, describe, expect, it, vi } from 'vitest'

vi.mock('./config', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./config')>()),
  DATA_BASE_URL: 'https://data.example',
  DATA_CONFIGURED: true,
  dataUrl: (key: string) => `https://data.example/${key}`,
}))

import {
  fetchPublishedTrailClosures,
  PUBLISHED_TRAIL_CLOSURES_KEY,
  validTrailClosure,
} from './publishedNotices'
import { ATC_SOURCE_KEY } from './notices'
import {
  trailClosureRows,
  trailClosuresDocument,
} from '../../preview-shots/fixtures/clubClosures.mjs'

const CLOSURES_URL = 'https://data.example/conditions/trail_closures.json'

/** One of the fixture's rows, with `fields` written over it. */
function rowWith(fields: Record<string, unknown>): Record<string, unknown> {
  return { ...trailClosureRows().line, ...fields }
}

afterEach(() => vi.restoreAllMocks())

describe('a conditions/trail_closures.json row (validTrailClosure)', () => {
  it('reads every row of the hand-made file as the closure its shape says', () => {
    const rows = trailClosureRows()
    const read = Object.values(rows).map((row) => validTrailClosure(row))

    expect(read.map((closure) => closure?.shape)).toEqual([
      'line',
      'area',
      'point',
      'line',
      'shade',
    ])
    expect(read.map((closure) => closure?.notice_id)).toEqual(
      Object.values(rows).map((row) => row.notice_id),
    )
    // The rest of the row is notices.json's, read by notices.json's reader:
    // the dates and the edit stamp the list prints come through as written.
    expect(read[0]).toMatchObject({
      title: 'Example Ridge Trail fire closure (example)',
      obstructs_trail: true,
      hazard: null,
      starts_on: rows.line.starts_on,
      current_until: rows.line.current_until,
      place: { kind: 'geometry', geometry: { type: 'LineString' } },
    })
    expect(read[1]?.place.geometry.type).toBe('MultiLineString')
    expect(read[2]?.place.geometry).toEqual(rows.point.place.geometry)
    expect(read[2]?.place.geometry.type).toBe('Point')
    // The greyed row's missing dates stay missing: no date, never a default.
    expect(read[3]).toMatchObject({ current_until: null, updated_at: null })
    // The shade is the area itself (decision 191), kept as it came.
    expect(read[4]?.place.geometry).toEqual(rows.shade.place.geometry)
  })

  it('reads a shade as the area it hatches: a Polygon, holes and all, or a MultiPolygon (decision 191)', () => {
    const outline = [
      [-100.2, 38.75],
      [-100.19, 38.75],
      [-100.19, 38.76],
      [-100.2, 38.75],
    ]
    const hole = [
      [-100.195, 38.752],
      [-100.193, 38.752],
      [-100.193, 38.754],
      [-100.195, 38.752],
    ]
    const shade = (geometry: unknown) =>
      validTrailClosure({
        ...trailClosureRows().shade,
        place: { kind: 'geometry', geometry },
      })

    expect(shade({ type: 'Polygon', coordinates: [outline, hole] })?.shape).toBe('shade')
    expect(
      shade({ type: 'MultiPolygon', coordinates: [[outline], [hole]] })?.place.geometry
        .type,
    ).toBe('MultiPolygon')
  })

  it('refuses a shade placed by a line, or by rings the map cannot fill', () => {
    // A shade is the area itself; a line in its place would hatch nothing,
    // and a ring of three positions, an empty polygon, a ring with a
    // position off the globe or a MultiPolygon with one empty member could
    // cost the source every other closure's mark.
    const { shade, line } = trailClosureRows()
    const placed = (geometry: unknown) =>
      validTrailClosure({ ...shade, place: { kind: 'geometry', geometry } })
    expect(validTrailClosure({ ...shade, place: line.place })).toBeNull()
    expect(
      placed({
        type: 'Polygon',
        coordinates: [
          [
            [-100.2, 38.75],
            [-100.19, 38.75],
            [-100.2, 38.75],
          ],
        ],
      }),
    ).toBeNull()
    expect(placed({ type: 'Polygon', coordinates: [] })).toBeNull()
    expect(
      placed({
        type: 'Polygon',
        coordinates: [
          [
            [-100.2, 38.75],
            [-100.19, 98.75],
            [-100.19, 38.76],
            [-100.2, 38.75],
          ],
        ],
      }),
    ).toBeNull()
    expect(
      placed({
        type: 'MultiPolygon',
        coordinates: [shade.place.geometry.coordinates, []],
      }),
    ).toBeNull()
    // And a line row placed by the shade's polygon is still refused.
    expect(validTrailClosure({ ...line, place: shade.place })).toBeNull()
  })

  it('refuses a row with no shape, or a shape the map does not draw', () => {
    const { shape: _, ...noShape } = rowWith({})
    expect(validTrailClosure(noShape)).toBeNull()
    expect(validTrailClosure(rowWith({ shape: 'polygon' }))).toBeNull()
    expect(validTrailClosure(rowWith({ shape: 'LINE' }))).toBeNull()
  })

  it('refuses an area row that carries its polygon instead of the trail stretches cut inside it', () => {
    // Crossing out a park's EDGE would draw a closed trail where there is
    // none and leave the trails inside it open-looking: the pipeline cuts
    // the trails, and a row that did not is refused, never drawn wrongly.
    const polygon = {
      kind: 'geometry',
      geometry: {
        type: 'Polygon',
        coordinates: [
          [
            [-100.2, 38.75],
            [-100.19, 38.75],
            [-100.19, 38.76],
            [-100.2, 38.75],
          ],
        ],
      },
    }
    expect(validTrailClosure(rowWith({ shape: 'area', place: polygon }))).toBeNull()
  })

  it('refuses a point row placed by a line, and a line row placed by a point', () => {
    const rows = trailClosureRows()
    expect(validTrailClosure({ ...rows.point, place: rows.line.place })).toBeNull()
    expect(validTrailClosure({ ...rows.line, place: rows.point.place })).toBeNull()
    expect(validTrailClosure({ ...rows.line, place: { kind: 'unplaced' } })).toBeNull()
  })

  it('refuses a row whose coordinates the map cannot draw, so one bad row cannot cost the others their marks', () => {
    const line = (coordinates: unknown) =>
      rowWith({
        place: { kind: 'geometry', geometry: { type: 'LineString', coordinates } },
      })
    // A one-point line, a position that is text, one off the globe, and a
    // MultiLineString with one good part and one empty part.
    expect(validTrailClosure(line([[-100.2, 38.75]]))).toBeNull()
    expect(
      validTrailClosure(
        line([
          ['-100.2', '38.75'],
          [-100.19, 38.76],
        ]),
      ),
    ).toBeNull()
    expect(
      validTrailClosure(
        line([
          [-100.2, 38.75],
          [-100.19, 98.76],
        ]),
      ),
    ).toBeNull()
    expect(
      validTrailClosure(
        rowWith({
          shape: 'area',
          place: {
            kind: 'geometry',
            geometry: {
              type: 'MultiLineString',
              coordinates: [
                [
                  [-100.2, 38.75],
                  [-100.19, 38.76],
                ],
                [],
              ],
            },
          },
        }),
      ),
    ).toBeNull()
    expect(
      validTrailClosure(
        rowWith({
          shape: 'point',
          place: {
            kind: 'geometry',
            geometry: { type: 'Point', coordinates: [NaN, 38] },
          },
        }),
      ),
    ).toBeNull()
  })

  it('refuses a row that does not close the trail, and one carrying a hazard', () => {
    // A crossed-out trail that is open is the false alarm CLAUDE.md's "miss
    // rather than cry wolf" rules out; a hunting area is never a closure.
    expect(validTrailClosure(rowWith({ obstructs_trail: false }))).toBeNull()
    expect(validTrailClosure(rowWith({ obstructs_trail: 'true' }))).toBeNull()
    expect(validTrailClosure(rowWith({ hazard: 'hunting' }))).toBeNull()
  })

  it('refuses ATC’s own rows, which ATC’s band already draws from ATC’s own file', () => {
    expect(validTrailClosure(rowWith({ source_key: ATC_SOURCE_KEY }))).toBeNull()
  })

  it('refuses a row with no id or no source, as notices.json’s reader does', () => {
    expect(validTrailClosure(rowWith({ notice_id: '' }))).toBeNull()
    expect(validTrailClosure(rowWith({ source_key: undefined }))).toBeNull()
    expect(validTrailClosure(null)).toBeNull()
    expect(validTrailClosure('a closure')).toBeNull()
  })
})

describe('reading conditions/trail_closures.json (fetchPublishedTrailClosures)', () => {
  it('reads the file under its own key, keeping the rows it can draw and refusing only the bad one', async () => {
    const document = trailClosuresDocument()
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) =>
      String(input) === CLOSURES_URL
        ? new Response(
            JSON.stringify({
              ...document,
              closures: [...document.closures, { notice_id: 'no-source' }],
            }),
            { status: 200 },
          )
        : new Response('', { status: 404 }),
    )

    const published = await fetchPublishedTrailClosures({ online: true })

    expect(PUBLISHED_TRAIL_CLOSURES_KEY).toBe('conditions/trail_closures.json')
    expect(fetchSpy.mock.calls.map(([input]) => String(input))).toEqual([CLOSURES_URL])
    expect(published?.items.map((closure) => closure.shape)).toEqual([
      'line',
      'area',
      'point',
      'line',
      'shade',
    ])
    // Dated by the file's own generated_at, which the sheet prints.
    expect(published?.generatedAt.toISOString()).toBe(
      new Date(document.generated_at).toISOString(),
    )
  })

  it('reads a bucket that serves no such file as no answer, never as no closure', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('', { status: 404 }))
    expect(await fetchPublishedTrailClosures({ online: true })).toBeNull()
  })

  it('refuses a file with no generated_at, which could not say how old its closures are', async () => {
    const { generated_at: _, ...undated } = trailClosuresDocument()
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(undated), { status: 200 }),
    )
    expect(await fetchPublishedTrailClosures({ online: true })).toBeNull()
  })
})
