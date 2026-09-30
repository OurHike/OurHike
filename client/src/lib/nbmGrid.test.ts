import { describe, expect, it } from 'vitest'
import { NBM_GRID, gridCoords, nbmSquare, weatherCellName } from './nbmGrid'

// [name, lon, lat, row, col, fractional col, fractional row], every number
// printed by pipeline/lib/nbm_grid.py (pyproj) on 2026-09-30. The squares are
// what the weather job files each point's forecast under; the fractions are
// there so a drift too small to change a square still fails.
const PYTHON: [string, number, number, number, number, number, number][] = [
  [
    'Lakes of the Clouds Hut',
    -71.319,
    44.2587,
    563,
    2073,
    2073.9285452254294,
    563.5472335218215,
  ],
  [
    'Mount Washington summit',
    -71.3033,
    44.2706,
    562,
    2074,
    2074.3476254140605,
    562.9107685836167,
  ],
  [
    'Springer Mountain',
    -84.1936,
    34.6272,
    1053,
    1683,
    1683.1435647831322,
    1053.3389174866406,
  ],
  [
    'Katahdin, Baxter Peak',
    -68.9213,
    45.9044,
    473,
    2137,
    2137.7871530635307,
    473.3422305554818,
  ],
  [
    'Clingmans Dome',
    -83.4985,
    35.5628,
    1009,
    1704,
    1704.9414443773487,
    1009.7721181067636,
  ],
  ['Mount Whitney', -118.2923, 36.5785, 910, 456, 456.0463422524114, 910.4167321212415],
  ['Harts Pass, WA', -120.668, 48.721, 344, 477, 477.67639487520165, 344.18411677327936],
  ['Denver', -104.99, 39.74, 826, 940, 940.5066066474029, 826.9475554164937],
]

describe('nbmSquare', () => {
  it.each(PYTHON)(
    'puts %s in the square nbm_grid.py files it under',
    (_, lon, lat, row, col) => {
      expect(nbmSquare(lon, lat)).toEqual([row, col])
    },
  )

  it.each(PYTHON)(
    'agrees with pyproj about where %s sits inside its square, to a millionth of a square',
    (_, lon, lat, _row, _col, fcol, frow) => {
      const { col, row } = gridCoords(lon, lat)
      expect(Math.abs(col - fcol)).toBeLessThan(1e-6)
      expect(Math.abs(row - frow)).toBeLessThan(1e-6)
    },
  )

  it('returns null for Anchorage and San Juan, which are on NBM grids the job does not read', () => {
    expect(nbmSquare(-149.9, 61.2)).toBeNull()
    expect(nbmSquare(-66.1, 18.2)).toBeNull()
  })

  it('pins the same grid constants as pipeline/lib/nbm_grid.py', () => {
    expect(NBM_GRID).toMatchObject({
      originX: -3272421.4573371694,
      originY: 3790842.106035436,
      squareM: 2539.703,
      width: 2345,
      height: 1597,
      radiusM: 6371200,
    })
  })
})

describe('weatherCellName', () => {
  it('names the cell by its south-west corner, as cut_cells.cell_name does: n44w072 for Lakes of the Clouds', () => {
    expect(weatherCellName(-71.319, 44.2587)).toBe('n44w072')
    expect(weatherCellName(-84.1936, 34.6272)).toBe('n34w085')
    expect(weatherCellName(-120.668, 48.721)).toBe('n48w121')
  })

  it('floors rather than truncates on a whole degree of longitude, so -72.0 is w072 and -71.9999 is w072', () => {
    expect(weatherCellName(-72, 44.5)).toBe('n44w072')
    expect(weatherCellName(-71.9999, 44.5)).toBe('n44w072')
    expect(weatherCellName(-72.0001, 44.5)).toBe('n44w073')
  })
})
