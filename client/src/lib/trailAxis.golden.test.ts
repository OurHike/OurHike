import { readFileSync, writeFileSync } from 'node:fs'
import { resolve as resolvePath } from 'node:path'

import type { FeatureCollection } from 'geojson'
import { describe, expect, it } from 'vitest'

import { buildTrailIndex, locateOnTrail, type TrailFix } from './trailPosition'

// The trail-axis golden (#1987 — The server computes an observation's mile and
// distance to the line from the club's own section geometry, and stores both
// beside the raw point). The structure inventory's mile is the server's,
// computed by backend/app/core/trail_axis.py from a club's own section line;
// this phone computes its own mile with locateOnTrail. Both are supposed to
// name the same place, and nothing else compares them.
//
// So trailAxis.golden.json holds one synthetic centerline with a published
// mile per vertex, and four points, and THIS file records what locateOnTrail
// answers for each. backend/tests/test_trail_axis.py reads the same file,
// draws a section along that line from its first published mile to its last,
// and requires the server's mile within 0.05 mi of the one recorded here.
// Here goes red when the phone's answer changes; there goes red when the
// server's stops agreeing with it.
//
// The line is synthetic, not a real section: about two miles near Harriman,
// vertices about 100 ft apart, miles that run 3% long on the first mile and
// 2% short on the second, so the two calculations really differ. The script
// that drew it is not kept; the coordinates are the fixture.
//
// When locateOnTrail is MEANT to change, rewrite the recorded answers and let
// the backend test judge them:
//
//   UPDATE_TRAIL_AXIS_GOLDEN=1 npx vitest run src/lib/trailAxis.golden.test.ts
//   npx prettier --write src/lib/trailAxis.golden.json

// `process.cwd()` rather than `import.meta.url`, the convention
// src/design-system/tokens/contrast.test.ts records: jsdom's is not a file URL.
const GOLDEN = resolvePath(process.cwd(), 'src/lib/trailAxis.golden.json')

interface GoldenPoint {
  name: string
  lon: number
  lat: number
  locateOnTrail?: TrailFix | null
}

interface Golden {
  about: string
  trails: FeatureCollection
  miles: Record<string, number[]>
  points: GoldenPoint[]
}

function readGolden(): Golden {
  return JSON.parse(readFileSync(GOLDEN, 'utf-8')) as Golden
}

function answers(golden: Golden): Array<TrailFix | null> {
  const index = buildTrailIndex(golden.trails, new Map(Object.entries(golden.miles)))
  return golden.points.map(({ lon, lat }) => locateOnTrail(index, { lon, lat }))
}

describe('trailAxis.golden.json', () => {
  it('builds its index on the published miles, the axis the server interpolates', () => {
    const golden = readGolden()

    const index = buildTrailIndex(golden.trails, new Map(Object.entries(golden.miles)))

    expect(index.onPipelineAxis).toBe(true)
  })

  it('records exactly what locateOnTrail answers for each point', () => {
    const golden = readGolden()
    const computed = answers(golden)

    if (process.env.UPDATE_TRAIL_AXIS_GOLDEN) {
      golden.points.forEach((point, i) => {
        point.locateOnTrail = computed[i]
      })
      writeFileSync(GOLDEN, `${JSON.stringify(golden, null, 2)}\n`)
    }

    expect(golden.points.map((point) => point.locateOnTrail)).toEqual(computed)
  })

  it('places three points on the line and refuses the one past the three-mile gate', () => {
    const recorded = readGolden().points.map((point) => point.locateOnTrail)

    expect(recorded.slice(0, 3).every((fix) => fix != null)).toBe(true)
    expect(recorded[3]).toBeNull()
  })
})
