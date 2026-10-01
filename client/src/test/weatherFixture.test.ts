import { describe, expect, it } from 'vitest'
import { nbmSquare as appSquare, weatherCellName } from '../lib/nbmGrid'
import { parseWeatherAlerts, parseWeatherCell } from '../lib/weatherForecast'
import {
  nbmSquare as fixtureSquare,
  squaresCovering,
  weatherAlertsDocument,
  weatherCellDocument,
} from '../../preview-shots/fixtures/weather.mjs'

// preview-shots/fixtures/weather.mjs copies lib/nbmGrid.ts's projection,
// because a recipe runs in Node and cannot import TypeScript. A copy that
// drifted would serve the preview's card a forecast for the square next door
// and the photograph would show no weather, so the two are held together here.

const POINTS: [string, number, number][] = [
  ['Lakes of the Clouds Hut', -71.319, 44.2587],
  ['Springer Mountain', -84.1936, 34.6272],
  ['Katahdin, Baxter Peak', -68.9213, 45.9044],
  ['Mount Whitney', -118.2923, 36.5785],
  ['Harts Pass, WA', -120.668, 48.721],
]

describe('preview-shots/fixtures/weather.mjs', () => {
  it.each(POINTS)('puts %s in the same square lib/nbmGrid.ts does', (_, lon, lat) => {
    expect(fixtureSquare(lon, lat)).toEqual(appSquare(lon, lat))
  })

  it('writes a cell file and an alerts file the card can read', () => {
    const cycle = new Date('2026-09-30T08:00Z')
    expect(
      parseWeatherCell(weatherCellDocument({ cycle, squares: [[563, 2073]] })),
    ).not.toBeNull()
    expect(parseWeatherAlerts(weatherAlertsDocument({ fetchedAt: cycle }))).not.toBeNull()
  })

  it.each(POINTS)(
    "covers %s's square when a recipe serves the whole of its cell",
    (_, lon, lat) => {
      const covered = new Set(
        squaresCovering(weatherCellName(lon, lat)).map((sq) => sq.join(',')),
      )
      expect(covered.has(appSquare(lon, lat)!.join(','))).toBe(true)
    },
  )

  it("covers the squares of the cell's own corners, where the curved parallels are furthest out", () => {
    const covered = new Set(squaresCovering('n44w072').map((sq) => sq.join(',')))
    for (const [lon, lat] of [
      [-72, 44],
      [-71.0001, 44],
      [-72, 44.9999],
      [-71.0001, 44.9999],
      [-71.5, 44],
    ]) {
      expect(covered.has(appSquare(lon, lat)!.join(','))).toBe(true)
    }
  })
})
