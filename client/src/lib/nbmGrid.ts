// Which NOAA forecast square a point is in, on the phone (#1056, features/WEATHER.md §7).
//
// `conditions/weather/<cell>.json` carries NBM's forecast for every 2.5 km
// square under a trail or a waypoint, listed as `[row, col]`. The phone finds a
// waypoint's forecast by working out which square the waypoint is in and
// looking that square up in the list - so this file and
// `pipeline/lib/nbm_grid.py` must agree to the square, or a hiker reads the
// forecast for the square next door. `nbmGrid.test.ts` pins this arithmetic to
// the Python module's answers at eight points from Springer to Harts Pass,
// to a millionth of a square.
//
// THE GRID IS PINNED HERE TOO, not read from `weather_index.json`. The pipeline
// refuses any NBM file whose grid differs from its pinned one (`matches` in
// nbm_grid.py), so the files a phone can receive are on exactly this grid, and
// a phone that took its projection from a document would have one more thing
// to be wrong about offline.
//
// THE PROJECTION IS LAMBERT CONFORMAL CONIC ON A SPHERE, tangent at 25°N
// (`+lat_1=25 +lat_2=25`), which is Snyder's "Map Projections - A Working
// Manual" (USGS Professional Paper 1395, 1987), equations 15-1 to 15-4 with
// one standard parallel. The sphere is NBM's own 6,371,200 m, not WGS84 -
// nbm_grid.py's comment says what treating it as WGS84 would cost.

const DEG = Math.PI / 180

/** Read with rasterio off a live NBM v5.0 GeoTIFF, 2026-09-24 - see
 *  `pipeline/lib/nbm_grid.py`, which is the one place these were measured. */
export const NBM_GRID = {
  lat0: 25,
  lon0: -95,
  standardParallel: 25,
  radiusM: 6371200,
  /** West edge of column 0, metres. */
  originX: -3272421.4573371694,
  /** North edge of row 0, metres. */
  originY: 3790842.106035436,
  squareM: 2539.703,
  width: 2345,
  height: 1597,
} as const

const n = Math.sin(NBM_GRID.standardParallel * DEG)
const F =
  (Math.cos(NBM_GRID.standardParallel * DEG) *
    Math.tan(Math.PI / 4 + (NBM_GRID.standardParallel * DEG) / 2) ** n) /
  n
const rho0 =
  (NBM_GRID.radiusM * F) / Math.tan(Math.PI / 4 + (NBM_GRID.lat0 * DEG) / 2) ** n

/** Fractional (col, row) on the grid: a point in square (r, c) comes back with
 *  c <= col < c + 1 and r <= row < r + 1. The same numbers as
 *  nbm_grid.grid_coords, and unbounded in the same way. */
export function gridCoords(lon: number, lat: number): { col: number; row: number } {
  const rho = (NBM_GRID.radiusM * F) / Math.tan(Math.PI / 4 + (lat * DEG) / 2) ** n
  const theta = n * (lon - NBM_GRID.lon0) * DEG
  const x = rho * Math.sin(theta)
  const y = rho0 - rho * Math.cos(theta)
  return {
    col: (x - NBM_GRID.originX) / NBM_GRID.squareM,
    row: (NBM_GRID.originY - y) / NBM_GRID.squareM,
  }
}

/** `[row, col]` of the square containing the point, or null off the CONUS
 *  grid - Alaska, Puerto Rico and Hawaii are separate NBM grids the weather
 *  job does not read yet (WEATHER.md §7). */
export function nbmSquare(lon: number, lat: number): [number, number] | null {
  const { col, row } = gridCoords(lon, lat)
  if (!Number.isFinite(col) || !Number.isFinite(row)) return null
  const r = Math.floor(row)
  const c = Math.floor(col)
  if (r < 0 || r >= NBM_GRID.height || c < 0 || c >= NBM_GRID.width) return null
  return [r, c]
}

/** The 1° cell a point is in, named the way `pipeline/cut_cells.cell_name`
 *  names it - the south-west corner, latitude first: `n44w072` for a point at
 *  44.26°N 71.32°W. The weather files are keyed by it. */
export function weatherCellName(lon: number, lat: number): string {
  const south = Math.floor(lat)
  const west = Math.floor(lon)
  const ns = south >= 0 ? 'n' : 's'
  const ew = west >= 0 ? 'e' : 'w'
  return `${ns}${String(Math.abs(south)).padStart(2, '0')}${ew}${String(Math.abs(west)).padStart(3, '0')}`
}
