// The challenge map as one SVG string (#1965, features/CHALLENGES_BLAZE_CARD.md
// slice 5, "The map: reuse, do not invent"): a paper map of the eastern
// states with the A.T. on it, walked miles in yellow, and the places on a
// challenge card as the live map's own diamond pins - hollow until earned,
// filled once they are. No tiles, no MapLibre, nothing fetched: the geometry
// is lib/challengeMap.ts's, kept on the phone.
//
// A STRING, NOT A COMPONENT, because the same drawing goes two places: inline
// on "Where your trail karma is", and into the share poster, which is
// rasterised on the phone (lib/challengePoster.ts) and cannot hold React.
//
// THE VOCABULARY IS THE APP'S. Ground in the Field palette (map/sheets.ts
// TOPO_PALETTE, the day default) - a paper map on a paper page, never a dark
// map in a dark card, which is unreadable in sun. The trail cased the way
// map/style.ts cases the A.T. on the light sheet. A place is map/challengePin.ts's
// diamond in CHALLENGE_COLOR. A mile is the trail's mile axis, written "mi
// 500" like every other position label (lib/challengeText.ts mileLabel); the
// scale bar is a distance and goes through lib/units.ts, so a hiker on
// kilometres reads kilometres.
//
// THE PROJECTION is the brief's: Lambert conformal conic, standard parallels
// 38°N and 43°N, central meridian 76.5°W - d3-geo's geoConicConformal with
// .parallels([38, 43]).rotate([76.5, 0]), which made the mock maps, written
// out here so no projection library ships to the phone. Spherical, as d3's is.

import { CHALLENGE_COLOR, CHALLENGE_EDGE_COLOR } from '../map/challengePin'
import { sheetVariant, TOPO_PALETTE } from '../map/sheets'
import type { ChallengeMap, LonLat, Polygons, TrailRun } from './challengeMap'
import { formatDistance, type UnitSystem } from './units'
import type { MileRange } from './walkedMiles'
import type { TrailStateCode } from './wherePlace'

const RAD = Math.PI / 180
const PARALLELS: readonly [number, number] = [38 * RAD, 43 * RAD]
const CENTRAL_MERIDIAN = -76.5
/** Earth's radius in miles, d3-geo's spherical one (6,371 km). */
const EARTH_MILES = 3958.8

const tanHalf = (phi: number) => Math.tan(Math.PI / 4 + phi / 2)
const CONE_N =
  Math.log(Math.cos(PARALLELS[0]) / Math.cos(PARALLELS[1])) /
  Math.log(tanHalf(PARALLELS[1]) / tanHalf(PARALLELS[0]))
const CONE_F = (Math.cos(PARALLELS[0]) * Math.pow(tanHalf(PARALLELS[0]), CONE_N)) / CONE_N

/** [lon, lat] in degrees → unit-sphere map coordinates, y growing south. */
export function conicConformal([lon, lat]: LonLat): [number, number] {
  const rho = CONE_F / Math.pow(tanHalf(lat * RAD), CONE_N)
  const theta = CONE_N * (lon - CENTRAL_MERIDIAN) * RAD
  return [rho * Math.sin(theta), rho * Math.cos(theta) - CONE_F]
}

/** The projection's scale factor at a latitude: map units per unit of
 *  ground, the same in every direction because the projection is conformal. */
function scaleFactor(lat: number): number {
  const phi = lat * RAD
  return (CONE_N * CONE_F) / (Math.cos(phi) * Math.pow(tanHalf(phi), CONE_N))
}

/** Paper the map sits on and the soft ink of its labels: --paper-0 and
 *  --stone-600 (design-system/tokens/colors.css), the mock maps' own. */
const PAGE = '#fffdf7'
const SOFT_INK = '#706859'
/** The trail's line inside its casing: --blaze-white. */
const TRAIL_LINE = '#fdfaf2'
/** The orange ring round a chosen place: --blaze-orange. */
const CHOSEN = '#c1611a'
/** The trail states' edge, the Field palette's park edge. */
const PARK_EDGE = '#5f8f57'
const INK = TOPO_PALETTE.label
const CASING = sheetVariant({}).casing
const MONO = "'IBM Plex Mono', ui-monospace, monospace"

export interface MapPin {
  mile: number
  earned: boolean
}

export interface MapLabel {
  mile: number
  text: string
  /** Offset from the place, in px at scale 1. */
  dx: number
  dy: number
  anchor?: 'start' | 'end' | 'middle'
}

export interface DrawOptions {
  width: number
  height: number
  /** Every place on the card, at its mile. Several earned at one spot
   *  cluster under one pin with a count. */
  pins?: readonly MapPin[]
  /** All-time walked miles, drawn in the taken-trail yellow. */
  walked?: readonly MileRange[]
  /** A mile ringed in orange - the Where sheet's "where it lands". */
  chosen?: number | null
  labels?: readonly MapLabel[]
  units: UnitSystem
  /** What a screen reader hears: one sentence saying what the map shows. */
  title: string
  /** Stroke and type scale - the poster draws a little heavier. */
  scale?: number
  /** "Springer Mtn · mi 0" rather than "Springer Mtn". */
  terminiMiles?: boolean
  /** Trail-state codes not to write (a place label sits there). */
  hideStates?: readonly TrailStateCode[]
}

interface Frame {
  project: (point: LonLat) => [number, number]
  /** px per mile of ground near the middle of the drawing. */
  pxPerMile: number
}

function fit(map: ChallengeMap, width: number, height: number): Frame {
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  for (const run of map.trail) {
    for (const point of run.coordinates) {
      const [x, y] = conicConformal(point)
      minX = Math.min(minX, x)
      maxX = Math.max(maxX, x)
      minY = Math.min(minY, y)
      maxY = Math.max(maxY, y)
    }
  }
  // The mock maps' margins: 14 px either side, 30 above for the scale bar,
  // 26 below for the attribution.
  const box = { left: 14, top: 30, right: width - 14, bottom: height - 26 }
  const k = Math.min(
    (box.right - box.left) / (maxX - minX),
    (box.bottom - box.top) / (maxY - minY),
  )
  const tx = (box.left + box.right) / 2 - (k * (minX + maxX)) / 2
  const ty = (box.top + box.bottom) / 2 - (k * (minY + maxY)) / 2
  const middleLat = (map.frame[1] + map.frame[3]) / 2
  return {
    project: (point) => {
      const [x, y] = conicConformal(point)
      return [k * x + tx, k * y + ty]
    },
    pxPerMile: (k * scaleFactor(middleLat)) / EARTH_MILES,
  }
}

const r1 = (n: number) => Math.round(n * 10) / 10

function pathOf(points: readonly (readonly [number, number])[], close = false): string {
  if (points.length === 0) return ''
  return 'M' + points.map(([x, y]) => `${r1(x)} ${r1(y)}`).join('L') + (close ? 'Z' : '')
}

function polygonsPath(polygons: Polygons, frame: Frame): string {
  return polygons
    .flatMap((rings) => rings.map((ring) => pathOf(ring.map(frame.project), true)))
    .join('')
}

function escapeXml(text: string): string {
  return text.replace(/[<>&'"]/g, (c) => `&#${c.charCodeAt(0)};`)
}

/** The run holding a mile, else the nearest end of the nearest run. */
function pointAtMile(trail: readonly TrailRun[], mile: number): LonLat {
  let best: LonLat = trail[0].coordinates[0]
  let bestGap = Infinity
  for (const run of trail) {
    const { miles, coordinates } = run
    const first = miles[0]
    const last = miles[miles.length - 1]
    if (mile >= first && mile <= last) {
      let low = 0
      let high = miles.length - 1
      while (high - low > 1) {
        const middle = (low + high) >> 1
        if (miles[middle] <= mile) low = middle
        else high = middle
      }
      const span = miles[high] - miles[low]
      const f = span === 0 ? 0 : (mile - miles[low]) / span
      const a = coordinates[low]
      const b = coordinates[high]
      return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f]
    }
    const gap = mile < first ? first - mile : mile - last
    if (gap < bestGap) {
      bestGap = gap
      best = mile < first ? coordinates[0] : coordinates[coordinates.length - 1]
    }
  }
  return best
}

/** The trail between two miles, as one path per run it crosses. */
function stretch(
  trail: readonly TrailRun[],
  from: number,
  to: number,
  frame: Frame,
): string {
  const parts: string[] = []
  for (const run of trail) {
    const first = run.miles[0]
    const last = run.miles[run.miles.length - 1]
    if (to < first || from > last) continue
    const a = Math.max(from, first)
    const b = Math.min(to, last)
    const points: LonLat[] = [pointAtMile([run], a)]
    run.miles.forEach((mile, i) => {
      if (mile > a && mile < b) points.push(run.coordinates[i])
    })
    points.push(pointAtMile([run], b))
    parts.push(pathOf(points.map(frame.project)))
  }
  return parts.join('')
}

function text(
  x: number,
  y: number,
  value: string,
  size: number,
  {
    fill = INK,
    anchor = 'start',
    weight = 400,
    halo = true,
  }: {
    fill?: string
    anchor?: 'start' | 'end' | 'middle'
    weight?: number
    halo?: boolean
  } = {},
): string {
  const common = `x="${r1(x)}" y="${r1(y)}" font-family="${MONO}" font-size="${r1(size)}" font-weight="${weight}" text-anchor="${anchor}"`
  const safe = escapeXml(value)
  const under = halo
    ? `<text ${common} fill="${PAGE}" stroke="${PAGE}" stroke-width="${r1(size * 0.34)}" stroke-linejoin="round">${safe}</text>`
    : ''
  return `${under}<text ${common} fill="${fill}">${safe}</text>`
}

/** map/challengePin.ts's diamond: hollow until earned, gold with a tick once
 *  it is. `r` is the diamond's apothem. */
function diamond(
  x: number,
  y: number,
  r: number,
  earned: boolean,
  scale: number,
): string {
  const s = r * Math.SQRT2
  const points = `${r1(x)},${r1(y - s)} ${r1(x + s)},${r1(y)} ${r1(x)},${r1(y + s)} ${r1(x - s)},${r1(y)}`
  if (!earned) {
    return `<polygon points="${points}" fill="${PAGE}" stroke="${CHALLENGE_EDGE_COLOR}" stroke-width="${r1(1.8 * scale)}"/>`
  }
  const tick = `M${r1(x - r * 0.55)} ${r1(y + r * 0.05)}L${r1(x - r * 0.12)} ${r1(y + r * 0.5)}L${r1(x + r * 0.62)} ${r1(y - r * 0.5)}`
  return (
    `<polygon points="${points}" fill="${CHALLENGE_COLOR}" stroke="${CHALLENGE_EDGE_COLOR}" stroke-width="${r1(1.2 * scale)}"/>` +
    `<path d="${tick}" fill="none" stroke="${INK}" stroke-width="${r1(Math.max(1.4, r * 0.22))}" stroke-linecap="round" stroke-linejoin="round"/>`
  )
}

function mileText(mile: number): string {
  // A position on the trail's own axis, not a distance (lib/challengeText.ts
  // mileLabel's rule): the unit before the figure, never converted.
  return `mi ${mile.toLocaleString('en-US', { maximumFractionDigits: 0 })}`
}

/** The whole map, as an SVG document string. */
export function drawChallengeMap(map: ChallengeMap, options: DrawOptions): string {
  const { width: W, height: H, units } = options
  const scale = options.scale ?? 1
  const frame = fit(map, W, H)
  const hidden = new Set(options.hideStates ?? [])
  const out: string[] = []
  out.push(
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" role="img" aria-label="${escapeXml(options.title)}">`,
  )
  out.push(`<rect width="${W}" height="${H}" fill="${TOPO_PALETTE.water}"/>`)
  out.push(`<path d="${polygonsPath(map.canada, frame)}" fill="${TOPO_PALETTE.wood}"/>`)
  const others = map.states.filter((state) => !state.trail)
  const trailStates = map.states.filter((state) => state.trail)
  out.push(
    `<path d="${others.map((s) => polygonsPath(s.polygons, frame)).join('')}" fill="${TOPO_PALETTE.wood}"/>`,
  )
  const parks = trailStates.map((s) => polygonsPath(s.polygons, frame)).join('')
  out.push(`<path d="${parks}" fill="${TOPO_PALETTE.park}"/>`)
  out.push(
    `<path d="${map.borders.map((b) => pathOf(b.map(frame.project))).join('')}" fill="none" stroke="${TOPO_PALETTE.boundary}" stroke-width="${r1(0.7 * scale)}" opacity="0.55"/>`,
  )
  out.push(
    `<path d="${parks}" fill="none" stroke="${PARK_EDGE}" stroke-width="${r1(0.6 * scale)}" opacity="0.5"/>`,
  )
  for (const state of trailStates) {
    if (
      state.code === null ||
      state.code === 'GA' ||
      state.code === 'ME' ||
      hidden.has(state.code)
    )
      continue
    const [x, y] = frame.project(state.label)
    if (x < 12 || x > W - 12 || y < 12 || y > H - 12) continue
    out.push(
      text(x, y, state.code, 10 * scale, {
        fill: SOFT_INK,
        anchor: 'middle',
        halo: false,
      }),
    )
  }
  // The trail: casing, then the line inside it, as the app draws the A.T.
  const trail = map.trail
    .map((run) => pathOf(run.coordinates.map(frame.project)))
    .join('')
  out.push(
    `<path d="${trail}" fill="none" stroke="${CASING}" stroke-width="${r1(3.2 * scale)}" stroke-linejoin="round" stroke-linecap="round"/>`,
  )
  out.push(
    `<path d="${trail}" fill="none" stroke="${TRAIL_LINE}" stroke-width="${r1(1.6 * scale)}" stroke-linejoin="round" stroke-linecap="round"/>`,
  )
  for (const range of options.walked ?? []) {
    const d = stretch(map.trail, range.startMile, range.endMile, frame)
    if (d !== '') {
      out.push(
        `<path d="${d}" fill="none" stroke="${CHALLENGE_COLOR}" stroke-width="${r1(4.2 * scale)}" stroke-linecap="round" stroke-linejoin="round"/>`,
      )
    }
  }
  // Mile ticks every 500, a short stroke across the line and its label.
  for (const mile of [500, 1000, 1500, 2000]) {
    const [px, py] = frame.project(pointAtMile(map.trail, mile))
    const [ax, ay] = frame.project(pointAtMile(map.trail, mile - 4))
    const [bx, by] = frame.project(pointAtMile(map.trail, mile + 4))
    const length = Math.hypot(bx - ax, by - ay) || 1
    const nx = (by - ay) / length
    const ny = -(bx - ax) / length
    const L = 4 * scale
    out.push(
      `<line x1="${r1(px - nx * L)}" y1="${r1(py - ny * L)}" x2="${r1(px + nx * L)}" y2="${r1(py + ny * L)}" stroke="${INK}" stroke-width="${r1(1.2 * scale)}"/>`,
    )
    out.push(
      text(
        px + nx * (L + 4 * scale) - 2 * scale,
        py + ny * (L + 4 * scale) + 3.5 * scale,
        mileText(mile),
        9 * scale,
        {
          fill: SOFT_INK,
          anchor: 'end',
        },
      ),
    )
  }
  // Places: hollow first, earned over them, earned ones at one spot clustered.
  const r = 5 * scale
  for (const pin of options.pins ?? []) {
    if (pin.earned) continue
    const [x, y] = frame.project(pointAtMile(map.trail, pin.mile))
    out.push(diamond(x, y, r, false, scale))
  }
  const clusters: { x: number; y: number; n: number }[] = []
  for (const pin of options.pins ?? []) {
    if (!pin.earned) continue
    const [x, y] = frame.project(pointAtMile(map.trail, pin.mile))
    const near = clusters.find(
      (c) => Math.abs(c.x - x) < 9 * scale && Math.abs(c.y - y) < 9 * scale,
    )
    if (near) near.n += 1
    else clusters.push({ x, y, n: 1 })
  }
  for (const cluster of clusters) {
    out.push(diamond(cluster.x, cluster.y, r, true, scale))
    if (cluster.n > 1) {
      out.push(
        text(
          cluster.x + r * 1.6 + 3 * scale,
          cluster.y + 3.5 * scale,
          String(cluster.n),
          11 * scale,
          { weight: 500 },
        ),
      )
    }
  }
  if (options.chosen != null) {
    const [x, y] = frame.project(pointAtMile(map.trail, options.chosen))
    out.push(
      `<circle cx="${r1(x)}" cy="${r1(y)}" r="${r1(15 * scale)}" fill="none" stroke="${CHOSEN}" stroke-width="${r1(2 * scale)}"/>` +
        `<circle cx="${r1(x)}" cy="${r1(y)}" r="${r1(24 * scale)}" fill="none" stroke="${CHOSEN}" stroke-width="${r1(1.2 * scale)}" opacity="0.45"/>`,
    )
  }
  for (const label of options.labels ?? []) {
    const [x, y] = frame.project(pointAtMile(map.trail, label.mile))
    out.push(
      text(x + label.dx * scale, y + label.dy * scale, label.text, 10 * scale, {
        anchor: label.anchor ?? 'start',
        weight: 500,
      }),
    )
  }
  // The termini, from the published line's own ends.
  const firstRun = map.trail[0]
  const lastRun = map.trail[map.trail.length - 1]
  const [sx, sy] = frame.project(firstRun.coordinates[0])
  const [kx, ky] = frame.project(lastRun.coordinates[lastRun.coordinates.length - 1])
  const end = lastRun.miles[lastRun.miles.length - 1]
  out.push(
    text(
      sx + 9 * scale,
      sy + 13 * scale,
      options.terminiMiles ? 'Springer Mtn · mi 0' : 'Springer Mtn',
      10 * scale,
      { weight: 500 },
    ),
  )
  out.push(
    text(
      kx - 8 * scale,
      ky - 9 * scale,
      options.terminiMiles ? `Katahdin · ${mileText(end)}` : 'Katahdin',
      10 * scale,
      {
        anchor: 'end',
        weight: 500,
      },
    ),
  )
  // The scale bar, in the hiker's own units, and whose map this is.
  const barMiles = units === 'metric' ? 300 / 1.609344 : 200
  const bar = barMiles * frame.pxPerMile
  const bx = 14 * scale
  const by = 22 * scale
  out.push(
    `<path d="M${r1(bx)} ${r1(by - 4 * scale)}L${r1(bx)} ${r1(by)}L${r1(bx + bar)} ${r1(by)}L${r1(bx + bar)} ${r1(by - 4 * scale)}" fill="none" stroke="${INK}" stroke-width="${r1(1.4 * scale)}"/>`,
  )
  out.push(
    text(
      bx + bar / 2,
      by + 12 * scale,
      formatDistance(barMiles, units, 'whole'),
      9 * scale,
      { fill: SOFT_INK, anchor: 'middle' },
    ),
  )
  const credit = map.credits.map((entry) => entry.credit).join(' · ')
  out.push(
    text(W - 10 * scale, H - 6 * scale, credit, 7.5 * scale, {
      fill: SOFT_INK,
      anchor: 'end',
    }),
  )
  out.push('</svg>')
  return out.join('')
}

/** Whether a hiker's record puts anything on the trail - the brief's rule for
 *  when the Where view draws the map at all ("map once a blaze is on the
 *  trail", which the build reads as an earned item with a trail mile). */
export function anythingOnTheTrail(pins: readonly MapPin[]): boolean {
  return pins.some((pin) => pin.earned)
}
