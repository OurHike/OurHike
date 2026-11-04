// Map geometry for the blaze-card frames, second pass: the real A.T. line
// (OpenStreetMap relation 156553, ODbL, via hrmerrill/steps-challenge), US
// states from us-atlas (US Census), Canada and the rest of the land from
// world-atlas (Natural Earth), all projected into a W x H box and emitted as
// SVG path strings plus a mile → point lookup along the trail.
import { readFileSync, writeFileSync } from 'node:fs'
import * as topojson from 'topojson-client'
import { presimplify, simplify, quantile } from 'topojson-simplify'
import { geoConicConformal, geoPath, geoDistance } from 'd3-geo'

const W = Number(process.argv[2] ?? 358)
const H = Number(process.argv[3] ?? 400)
const OUT = process.argv[4] ?? 'map2.json'
const TRAIL_POINTS = Number(process.argv[5] ?? 900)

const us = JSON.parse(readFileSync(new URL('./node_modules/us-atlas/states-10m.json', import.meta.url)))
let topo = presimplify(us); topo = simplify(topo, quantile(topo, 0.25))
const states = topojson.feature(topo, topo.objects.states)
const world = JSON.parse(readFileSync(new URL('./node_modules/world-atlas/countries-50m.json', import.meta.url)))
let wtopo = presimplify(world); wtopo = simplify(wtopo, quantile(wtopo, 0.3))
const countries = topojson.feature(wtopo, wtopo.objects.countries)
const canada = countries.features.find((f) => f.properties.name === 'Canada')

const AT_STATES = { '13': 'GA', '37': 'NC', '47': 'TN', '51': 'VA', '54': 'WV', '24': 'MD', '42': 'PA', '34': 'NJ', '36': 'NY', '09': 'CT', '25': 'MA', '50': 'VT', '33': 'NH', '23': 'ME' }

// The trail, NOBO: the OSM line runs south to north already; verify by latitude.
const osm = JSON.parse(readFileSync(new URL('./src/at-osm.geojson', import.meta.url)))
let line = osm.features[0].geometry.coordinates
if (line[0][1] > line[line.length - 1][1]) line = line.slice().reverse()
// Thin to TRAIL_POINTS by keeping every k-th vertex plus the ends.
const k = Math.max(1, Math.floor(line.length / TRAIL_POINTS))
const AT = line.filter((_, i) => i % k === 0 || i === line.length - 1)

const projection = geoConicConformal().parallels([38, 43]).rotate([76.5, 0])
projection.fitExtent([[14, 30], [W - 14, H - 26]], { type: 'LineString', coordinates: AT })
projection.clipExtent([[-2, -2], [W + 2, H + 2]])
const path = geoPath(projection)

// Cumulative great-circle distance along the FULL line in miles -> mile scale.
const R_MI = 3958.8
const cumFull = [0]
for (let i = 1; i < line.length; i++) cumFull.push(cumFull[i - 1] + geoDistance(line[i - 1], line[i]) * R_MI)
const totalMi = cumFull[cumFull.length - 1]
const SCALE = 2198 / totalMi // OSM's line length vs the ATC's published total
const atMile = (mile) => {
  const t = Math.max(0, Math.min(totalMi, mile / SCALE))
  let i = 1
  while (i < cumFull.length && cumFull[i] < t) i++
  if (i >= cumFull.length) return projection(line[line.length - 1])
  const f = (t - cumFull[i - 1]) / (cumFull[i] - cumFull[i - 1] || 1)
  const a = line[i - 1], b = line[i]
  return projection([a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f])
}
const segment = (from, to) => {
  const pts = [atMile(from)]
  for (let i = 0; i < line.length; i++) {
    const m = cumFull[i] * SCALE
    if (m > from && m < to) pts.push(projection(line[i]))
  }
  pts.push(atMile(to))
  return pts
}
const r1 = (n) => Math.round(n * 10) / 10
const toPath = (pts) => 'M' + pts.map((p) => `${r1(p[0])} ${r1(p[1])}`).join(' L')
const round = (d) => d.replace(/(\d+\.\d{1,})/g, (m) => String(Math.round(Number(m) * 10) / 10))

const atPath = toPath(AT.map((c) => projection(c)))
const atStates = round(path({ type: 'FeatureCollection', features: states.features.filter((f) => AT_STATES[f.id]) }))
const otherStates = round(path({ type: 'FeatureCollection', features: states.features.filter((f) => !AT_STATES[f.id]) }))
const canadaPath = round(path(canada))
const borders = round(path(topojson.mesh(topo, topo.objects.states, (a, b) => a !== b)))
const labels = Object.fromEntries(states.features.filter((f) => AT_STATES[f.id]).map((f) => [AT_STATES[f.id], path.centroid(f).map(r1)]))

// A scale bar: 200 miles at the map's centre latitude, in px.
const c0 = projection.invert([W / 2, H / 2])
const c1 = projection.invert([W / 2 + 50, H / 2])
const miPer50px = geoDistance(c0, c1) * R_MI
const scalePx = r1((200 / miPer50px) * 50)

const miles = [0, 8, 200.1, 380, 471.3, 500, 703.1, 713, 714.9, 719.6, 720.3, 787.9, 830.5, 1000, 1026.5, 1030, 1106, 1500, 2000, 2045.9, 2080, 2197.9]
writeFileSync(OUT, JSON.stringify({
  W, H, atPath, atStates, otherStates, canada: canadaPath, borders, labels, scalePx,
  trailMiles: Math.round(totalMi),
  atMile: Object.fromEntries(miles.map((m) => [m, atMile(m).map(r1)])),
  tick: Object.fromEntries([500, 1000, 1500, 2000].map((m) => {
    // A short perpendicular tick: direction from the trail a few miles either side.
    const a = atMile(m - 4), b = atMile(m + 4)
    const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy) || 1
    return [m, { p: atMile(m).map(r1), nx: r1(-dy / len), ny: r1(dx / len) }]
  })),
  walked: [[0, 12], [700, 725], [785, 790], [826, 834], [1024, 1032], [1100, 1110]].map(([a, b]) => toPath(segment(a, b))),
}))
console.log('wrote', OUT, 'trail pts', AT.length, 'osm miles', Math.round(totalMi), 'sizes', atStates.length, otherStates.length, canadaPath.length, borders.length, atPath.length)
