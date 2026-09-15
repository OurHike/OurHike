/**
 * What would BAKED contour tiles weigh? Measured with the library that ships.
 *
 * The other half of spike_baked_terrain.py. Baking the hillshade alone frees
 * nothing, because maplibre-contour reads the same `dem.pmtiles` to draw
 * isolines in the browser; dropping the DEM means baking the contours too.
 * This prices that, using maplibre-contour's own isoline generator and its own
 * vector-tile encoder - so the bytes are the bytes the app would ship, not an
 * estimate of them.
 *
 * Run spike_baked_terrain.py first: it writes the elevation dumps and
 * elev_index.json this reads. Elevation comes in already decoded, through a
 * substituted `decodeImage`, which is the library's own extension point - so
 * no PNG decoder is needed in Node and the geometry path is untouched.
 *
 * TWO UNITS, NOT ONE. terrain.ts's CONTOUR_THRESHOLDS carries an imperial and
 * a metric ladder, and the interval changes with zoom in both. A live map
 * picks per request; a baked archive has to carry every combination it wants
 * to offer, which is the cost this prints and the reason terrain.ts rejected
 * baked contours for the live map in the first place.
 *
 * `overzoom: 0` where the app uses 1. The app reads one zoom out and uses a
 * quadrant, which is a runtime economy (fewer, larger fetches) and yields
 * smoother lines off half-resolution data. A baker has no fetch to economise
 * and would want full resolution, so 0 is the honest setting for this question
 * - and it is the pessimistic one for bytes, which is worth saying plainly.
 */
import { readFileSync, writeFileSync } from 'node:fs'
import { gzipSync } from 'node:zlib'
import { createRequire } from 'node:module'

// Resolved against the client's install rather than a symlink into pipeline/:
// maplibre-contour is the CLIENT's dependency, and this spike measures what
// the client would ship. Nothing here belongs in pipeline's dependency set.
const require = createRequire(new URL('../client/package.json', import.meta.url))
const mlcontour = require('maplibre-contour')

const DIR = new URL('./data/spike_baked_terrain/', import.meta.url)
const index = JSON.parse(readFileSync(new URL('elev_index.json', DIR), 'utf8'))

// terrain.ts CONTOUR_THRESHOLDS, verbatim. A zoom with no entry inherits the
// next lower one, which is the lookup the library does from the same table.
const THRESHOLDS = {
  imperial: { 9: [500, 2000], 11: [200, 1000], 12: [100, 500], 13: [40, 200], 14: [20, 100] },
  metric: { 9: [200, 1000], 11: [100, 500], 12: [50, 250], 13: [10, 50] },
}
const METRES_TO_FEET = 3.28084 // terrain.ts
const TILE = 256

function levelsFor(units, z) {
  const table = THRESHOLDS[units]
  const keys = Object.keys(table).map(Number).filter((k) => k <= z).sort((a, b) => a - b)
  return table[keys[keys.length - 1]]
}

/** The 9 neighbour dumps spike_baked_terrain.py wrote, keyed by tile coords. */
function loadTiles(entry) {
  const tiles = new Map()
  // A request above maxzoom clamps to the z13 parent, so key on the z13 tile
  // whatever zoom was asked for - `z13x`/`z13y` carry it for the children.
  const pz = Math.min(entry.z, 13)
  const scale = 2 ** (entry.z - pz)
  const px = entry.z13x ?? Math.floor(entry.x / scale)
  const py = entry.z13y ?? Math.floor(entry.y / scale)
  let i = 0
  for (const dy of [-1, 0, 1]) {
    for (const dx of [-1, 0, 1]) {
      const buf = readFileSync(new URL(`${entry.stem}_n${i}.f32`, DIR))
      const data = new Float32Array(buf.buffer, buf.byteOffset, buf.length / 4)
      tiles.set(`${pz}/${px + dx}/${py + dy}`, { width: TILE, height: TILE, data })
      i += 1
    }
  }
  return tiles
}

async function contourBytes(entry, units) {
  const tiles = loadTiles(entry)
  const manager = new mlcontour.LocalDemManager({
    demUrlPattern: 'dem://{z}/{x}/{y}',
    cacheSize: 100,
    encoding: 'terrarium',
    maxzoom: 13,
    timeoutMs: 10_000,
    // The library's own extension points: hand it decoded elevation directly.
    getTile: async (url) => ({ data: { key: url.replace('dem://', '') } }),
    decodeImage: async (blob) => {
      const tile = tiles.get(blob.key)
      if (!tile) throw new Error(`no dump for ${blob.key}`)
      return tile
    },
  })

  const { arrayBuffer } = await manager.fetchContourTile(
    entry.z,
    entry.x,
    entry.y,
    {
      levels: levelsFor(units, entry.z),
      multiplier: units === 'imperial' ? METRES_TO_FEET : 1,
      elevationKey: 'ele',
      levelKey: 'level',
      contourLayer: 'contours',
      overzoom: 0,
    },
    new AbortController(),
  )
  const raw = Buffer.from(arrayBuffer)
  // PMTiles stores vector tiles gzipped, as export_basemap's archives do.
  return { raw: raw.length, gz: gzipSync(raw, { level: 6 }).length }
}

const out = []
const say = (s = '') => { console.log(s); out.push(s) }

const byZoomUnit = new Map()
for (const entry of index) {
  for (const units of ['imperial', 'metric']) {
    const { raw, gz } = await contourBytes(entry, units)
    const key = `${entry.z}|${units}`
    if (!byZoomUnit.has(key)) byZoomUnit.set(key, [])
    byZoomUnit.get(key).push({ name: entry.name, raw, gz })
  }
}

// Published dem.pmtiles bands (LIGHT_DOWNLOAD.md, run 33065213666) and the
// per-zoom mean DEM tile bytes this sample measured, for the ratio.
const PUBLISHED = { 11: [1139, 49.3], 12: [2315, 78.8], 13: [4054, 106.2] }
const DEM_SAMPLE_KB = { 11: 48.9, 12: 36.9, 13: 27.1 } // spike_baked_terrain.py

const mean = (a) => a.reduce((s, x) => s + x, 0) / a.length

say('BAKED CONTOURS - maplibre-contour isolines + its own vector-tile encoder')
say('gzipped, 6 areas per cell, intervals from terrain.ts CONTOUR_THRESHOLDS')
say('')
say(['zoom', 'interval', 'imperial KB', 'metric KB', 'both KB', 'DEM KB'].join('\t'))
for (const z of [11, 12, 13]) {
  const imp = mean(byZoomUnit.get(`${z}|imperial`).map((r) => r.gz)) / 1024
  const met = mean(byZoomUnit.get(`${z}|metric`).map((r) => r.gz)) / 1024
  say([`z${z}`, `${levelsFor('imperial', z)[0]}ft/${levelsFor('metric', z)[0]}m`,
    imp.toFixed(1), met.toFixed(1), (imp + met).toFixed(1), DEM_SAMPLE_KB[z].toFixed(1)].join('\t'))
}
say('')

say('PROJECTION onto the published bands (reasoned: sample ratio x band MB)')
let impTotal = 0, metTotal = 0
for (const z of [11, 12, 13]) {
  const [, bandMb] = PUBLISHED[z]
  const imp = mean(byZoomUnit.get(`${z}|imperial`).map((r) => r.gz)) / 1024
  const met = mean(byZoomUnit.get(`${z}|metric`).map((r) => r.gz)) / 1024
  impTotal += (bandMb * imp) / DEM_SAMPLE_KB[z]
  metTotal += (bandMb * met) / DEM_SAMPLE_KB[z]
  say(`  z${z}: imperial ${((bandMb * imp) / DEM_SAMPLE_KB[z]).toFixed(1)} MB, metric ${((bandMb * met) / DEM_SAMPLE_KB[z]).toFixed(1)} MB`)
}
say(`  imperial only : ${impTotal.toFixed(1)} MB`)
say(`  metric only   : ${metTotal.toFixed(1)} MB`)
say(`  both units    : ${(impTotal + metTotal).toFixed(1)} MB`)
say('')
say('PER-AREA, z13 imperial (40 ft), gzipped KB')
for (const r of byZoomUnit.get('13|imperial')) say(`  ${r.name.padEnd(22)} ${(r.gz / 1024).toFixed(1)}`)

writeFileSync(new URL('contour_report.txt', DIR), out.join('\n') + '\n')
writeFileSync(
  new URL('contour_bytes.json', DIR),
  JSON.stringify(Object.fromEntries([...byZoomUnit].map(([k, v]) => [k, Object.fromEntries(v.map((r) => [r.name, r.gz]))])), null, 2),
)
console.log('\nwrote contour_report.txt')

/**
 * THE ZOOM A BAKED SET WOULD ACTUALLY HAVE TO REACH.
 *
 * terrain.ts caps the DEM at z13 (DEM_MAX_ZOOM) but draws contours to z15
 * (CONTOUR_MAX_ZOOM), overzooming the same tiles - and CONTOUR_THRESHOLDS has
 * an imperial entry at z14 (20 ft) finer than z13's 40 ft. Live, that costs
 * nothing: the lines are generated from tiles already on the phone. Baked,
 * every one of those tiles has to exist.
 *
 * Measured by asking for the 4 z14 and 16 z15 children of each z13 tile
 * already dumped - the same ground, so the sum is directly comparable to the
 * z13 tile it replaces.
 */
say('')
say('DEEPER ZOOMS - cost of covering ONE z13 tile of ground, gzipped KB')
say('the live map draws these from tiles it already has; a baked set ships them')
say(['area', 'z13', 'z14 (4 tiles)', 'z15 (16 tiles)'].join('\t'))
const deepTotals = { 13: 0, 14: 0, 15: 0 }
for (const entry of index.filter((e) => e.z === 13)) {
  const row = { 13: 0, 14: 0, 15: 0 }
  row[13] = (await contourBytes(entry, 'imperial')).gz
  for (const [z, n] of [[14, 2], [15, 4]]) {
    for (let dx = 0; dx < n; dx += 1) {
      for (let dy = 0; dy < n; dy += 1) {
        const child = { ...entry, z, x: entry.x * n + dx, y: entry.y * n + dy }
        // Children read the SAME z13 dumps, keyed by the z13 coords the
        // manager asks for once it clamps to maxzoom.
        row[z] += (await contourBytes({ ...child, stem: entry.stem, z13x: entry.x, z13y: entry.y }, 'imperial')).gz
      }
    }
  }
  for (const z of [13, 14, 15]) deepTotals[z] += row[z]
  say([entry.name.padEnd(22), (row[13] / 1024).toFixed(1), (row[14] / 1024).toFixed(1), (row[15] / 1024).toFixed(1)].join('\t'))
}
say(`multiplier vs z13: z14 ${(deepTotals[14] / deepTotals[13]).toFixed(2)}x, z15 ${(deepTotals[15] / deepTotals[13]).toFixed(2)}x`)
writeFileSync(new URL('contour_report.txt', DIR), out.join('\n') + '\n')
