// The share poster (#1965, frame features/design/blaze-card/Poster.dc.html):
// 1080 by 1350, a hiker's season on one image - the card's tiles, how much
// trail karma, the states, and the map unless the hiker chooses the states
// poster instead.
//
// TWO LAYOUTS. With the map, the frame's: the card left, the map and a short
// strip right. Without it, the card across the top and the fourteen states as
// one wide strip under it. Which one the share sheet opens on is
// chrome/PosterShareSheet.tsx's to say (the map, by the maintainer's poll of
// 2026-11-04), and the map card there says "This shows where you've been."
// before anything is shared.
//
// MADE ON THE PHONE, FROM WHAT IS ON THE PHONE. The poster is an SVG drawn
// here and rasterised to a PNG by the browser (`rasterise`), with the app's
// own fonts embedded so the image renders the same in any viewer. Nothing is
// uploaded to make it; nothing waits on the network but the font files,
// which the app shell already holds. Whether WebKit draws fonts embedded in
// an SVG image is @unvalidated here - this sandbox has no WebKit; CI's
// phone-webkit project is where it would show.
//
// WHAT IS LEFT OFF THE FRAME, and why:
//   - "#ATBucketList27": no club has published a hashtag in its challenge
//     file, and the app does not invent one in a club's name.
//   - The white bar beside the footer's credit: it was drawn as a blaze, and
//     the maintainer retired blazes from what a hiker earns (2026-11-04).
//   - Any count of what is not earned (features/VOLUNTEERING.md §5 rule 2).

import { blazeIconPath } from '../chrome/blazeIcons'
import { CHALLENGE_COLOR } from '../map/challengePin'
import type { ChallengeMap } from './challengeMap'
import { drawChallengeMap, type MapPin } from './challengeMapSvg'
import { draftLabel, isPlaceItem, isSealed, type Challenge } from './challenges'
import { isItemDone, type ChallengeTag } from './challengeProgress'
import { CHALLENGE_WORDS } from './challengeWords'
import { trailLabel } from './challengeText'
import { earnedPlaces, seasonWord, type StateOfMile } from './seasonStrip'
import { drawStateStrip, walkedStates, type StripMark } from './stateStripSvg'
import type { UnitSystem } from './units'
import type { MileRange } from './walkedMiles'
import { TRAIL_STATES } from './wherePlace'

export const POSTER_WIDTH = 1080
export const POSTER_HEIGHT = 1350

export interface PosterInput {
  challenge: Challenge
  tags: readonly ChallengeTag[]
  today: string
  stateOf: StateOfMile
  walked: readonly MileRange[]
  units: UnitSystem
  /** The map, when the hiker turned it on and the phone holds one. */
  map: ChallengeMap | null
  /** `@font-face` rules to embed; empty in tests. */
  fontCss?: string
}

const GROUND = '#122016'
const PANEL = '#0e1a12'
const CREAM = '#fdfaf2'
const SAGE = '#96b98c'
const SAGE_LIGHT = '#c7dabd'
const TILE = '#2c4a30'
const DISPLAY = "'Bitter', Georgia, serif"
const MONO = "'IBM Plex Mono', ui-monospace, monospace"

const r1 = (n: number) => Math.round(n * 10) / 10

function escapeXml(text: string): string {
  return text.replace(/[<>&'"]/g, (c) => `&#${c.charCodeAt(0)};`)
}

/** The strip's marks: every earned item with a state, gold, and every place
 *  still on the card, as an outline in its own state. */
export function stripMarks(
  input: Pick<PosterInput, 'challenge' | 'tags' | 'stateOf'>,
): StripMark[] {
  const { challenge, tags, stateOf } = input
  const marks: StripMark[] = []
  for (const place of earnedPlaces(challenge, tags, stateOf)) {
    if (place.state !== null) marks.push({ state: place.state, earned: true })
  }
  for (const item of challenge.items) {
    if (!isPlaceItem(item) || isItemDone(item, challenge.id, tags)) continue
    const state = stateOf(item.match.places[0].mile)
    if (state !== null) marks.push({ state, earned: false })
  }
  return marks
}

/** The map's pins: every place item at its mile, earned or not, and every
 *  earned item the hiker placed on the trail at a mile. */
export function mapPins(
  input: Pick<PosterInput, 'challenge' | 'tags' | 'stateOf'>,
): MapPin[] {
  const { challenge, tags, stateOf } = input
  const pins: MapPin[] = earnedPlaces(challenge, tags, stateOf).flatMap((place) =>
    place.mile === null ? [] : [{ mile: place.mile, earned: true }],
  )
  for (const item of challenge.items) {
    if (isPlaceItem(item) && !isItemDone(item, challenge.id, tags)) {
      pins.push({ mile: item.match.places[0].mile, earned: false })
    }
  }
  return pins
}

function tiles(
  input: PosterInput,
  x: number,
  y: number,
  width: number,
  height: number,
  columns = 10,
): string {
  const { challenge, tags, today } = input
  const sections = challenge.sections
    .map((section) => ({
      section,
      items: challenge.items.filter((item) => item.section === section.id),
    }))
    .filter((entry) => entry.items.length > 0)
  const gap = 6
  const labelHeight = 26
  const rows = sections.reduce(
    (sum, entry) => sum + Math.ceil(entry.items.length / columns),
    0,
  )
  const fromWidth = (width - gap * (columns - 1)) / columns
  const fromHeight =
    (height - sections.length * labelHeight - gap * Math.max(0, rows - 1)) / rows / 1.3
  const tileWidth = Math.floor(Math.min(fromWidth, fromHeight))
  const tileHeight = Math.round(tileWidth * 1.3)
  const glyph = tileWidth * 0.55
  const out: string[] = []
  let top = y
  for (const { section, items } of sections) {
    out.push(
      `<text x="${x}" y="${r1(top + 16)}" font-family="${MONO}" font-size="14" letter-spacing="0.14em" fill="${SAGE}">${escapeXml(section.title.toUpperCase())}</text>`,
    )
    top += labelHeight
    items.forEach((item, index) => {
      const tx = x + (index % columns) * (tileWidth + gap)
      const ty = top + Math.floor(index / columns) * (tileHeight + gap)
      const sealed = isSealed(item, today)
      const done = isItemDone(item, challenge.id, tags)
      if (sealed && !done) {
        out.push(
          `<rect x="${r1(tx + 0.75)}" y="${r1(ty + 0.75)}" width="${tileWidth - 1.5}" height="${tileHeight - 1.5}" rx="4" fill="none" stroke="${SAGE}" stroke-width="1.5" stroke-dasharray="4 3"/>`,
        )
      } else {
        out.push(
          `<rect x="${r1(tx)}" y="${r1(ty)}" width="${tileWidth}" height="${tileHeight}" rx="4" fill="${done ? CHALLENGE_COLOR : TILE}"/>`,
        )
      }
      const k = glyph / 24
      out.push(
        `<path d="${blazeIconPath(sealed && !done ? 'mystery' : item.icon)}" transform="translate(${r1(tx + (tileWidth - glyph) / 2)} ${r1(ty + (tileHeight - glyph) / 2)}) scale(${r1(k * 100) / 100})" fill="none" stroke="${done ? GROUND : SAGE}" stroke-width="${done ? 2 : 1.8}" stroke-linecap="round" stroke-linejoin="round"/>`,
      )
    })
    top += Math.ceil(items.length / columns) * (tileHeight + gap)
  }
  return out.join('')
}

/** The poster as an SVG document string. */
export function posterSvg(input: PosterInput): string {
  const { challenge, tags, stateOf, walked, units, map } = input
  const places = earnedPlaces(challenge, tags, stateOf)
  const earned = places.length
  const order = TRAIL_STATES.map((entry) => entry.code)
  const states = [
    ...new Set(places.flatMap((place) => (place.state === null ? [] : [place.state]))),
  ].sort((a, b) => order.indexOf(a) - order.indexOf(b))
  const year = (challenge.window.closes ?? challenge.window.opens ?? input.today).slice(
    0,
    4,
  )
  const W = POSTER_WIDTH
  const H = POSTER_HEIGHT
  const out: string[] = [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${W} ${H}" width="${W}" height="${H}">`,
  ]
  if (input.fontCss) out.push(`<defs><style>${input.fontCss}</style></defs>`)
  out.push(`<rect width="${W}" height="${H}" fill="${GROUND}"/>`)
  // The header: the list, the season, the count and the states.
  out.push(
    `<text x="72" y="96" font-family="${MONO}" font-size="20" letter-spacing="0.14em" fill="${SAGE}">${escapeXml(`${challenge.name} · ${year}`.toUpperCase())}</text>`,
  )
  // The DRAFT label wherever a draft is named - a shared image included.
  const draft = draftLabel(challenge)
  if (draft !== null) {
    out.push(
      `<text x="72" y="124" font-family="${MONO}" font-size="16" fill="${CHALLENGE_COLOR}">${escapeXml(draft)}</text>`,
    )
  }
  const trail = trailLabel(challenge.trail)
  out.push(
    `<text font-family="${DISPLAY}" font-weight="700" font-size="84" fill="${CREAM}" letter-spacing="-1"><tspan x="72" y="214">My ${escapeXml(seasonWord(challenge.window))}</tspan><tspan x="72" y="296">on the ${escapeXml(trail)}</tspan></text>`,
  )
  out.push(
    `<text x="${W - 72}" y="220" text-anchor="end" font-family="${DISPLAY}" font-weight="700" font-size="150" fill="${CHALLENGE_COLOR}">${earned}</text>`,
  )
  const stateWord = states.length === 1 ? 'state' : 'states'
  out.push(
    `<text x="${W - 72}" y="276" text-anchor="end" font-family="${MONO}" font-size="20" letter-spacing="0.14em" fill="${SAGE}">${escapeXml(`${CHALLENGE_WORDS.noun} ${CHALLENGE_WORDS.past}${states.length > 0 ? ` · ${states.length} ${stateWord}` : ''}`.toUpperCase())}</text>`,
  )
  const marks = stripMarks(input)
  const lit = walkedStates(walked, stateOf)
  const statesLine = (x: number, y: number, size: number) =>
    states.length === 0
      ? ''
      : `<text x="${x}" y="${y}" font-family="${MONO}" font-size="${size}" letter-spacing="0.04em" fill="${CHALLENGE_COLOR}">${escapeXml(states.join(' · '))}</text>`
  const top = 360
  const bottom = H - 150
  if (map === null) {
    // THE DEFAULT, NO MAP: the card across the top, twenty tiles a row, and
    // the fourteen states as one wide strip under it - wide enough that a
    // state's code and marks read on a phone screen once shared.
    const cardBottom = 905
    out.push(
      `<rect x="72" y="${top}" width="${W - 144}" height="${cardBottom - top}" rx="18" fill="${PANEL}"/>`,
    )
    out.push(tiles(input, 92, top + 12, W - 184, cardBottom - top - 24, 20))
    const stripTop = cardBottom + 18
    out.push(
      `<rect x="72" y="${stripTop}" width="${W - 144}" height="${bottom - stripTop}" rx="18" fill="${PANEL}"/>`,
    )
    out.push(
      `<text x="96" y="${stripTop + 38}" font-family="${MONO}" font-size="16" letter-spacing="0.14em" fill="${SAGE}">WHERE IT HAPPENED</text>`,
    )
    const strip = drawStateStrip(marks, {
      width: W - 192,
      columnHeight: bottom - stripTop - 132,
      walkedStates: lit,
      termini: true,
      title: 'The fourteen trail states, south to north',
    })
    out.push(`<g transform="translate(96 ${stripTop + 56})">${strip}</g>`)
    out.push(statesLine(96, bottom - 22, 22))
  } else {
    // THE MAP, CHOSEN: the frame's layout - the card left, the map and a
    // short strip right.
    out.push(
      `<rect x="72" y="${top}" width="500" height="${bottom - top}" rx="18" fill="${PANEL}"/>`,
    )
    out.push(tiles(input, 82, top + 10, 480, bottom - top - 20))
    const rightX = 588
    const rightWidth = W - 72 - rightX
    const mapHeight = 470
    const svg = drawChallengeMap(map, {
      width: rightWidth,
      height: mapHeight,
      units,
      title: 'Where this hiker’s trail karma landed on the A.T.',
      pins: mapPins(input),
      walked,
      scale: 1.15,
    })
    out.push(
      `<g transform="translate(${rightX} ${top})"><clipPath id="poster-map"><rect width="${rightWidth}" height="${mapHeight}" rx="18"/></clipPath><g clip-path="url(#poster-map)">${svg}</g></g>`,
    )
    const stripTop = top + mapHeight + 14
    out.push(
      `<rect x="${rightX}" y="${stripTop}" width="${rightWidth}" height="${bottom - stripTop}" rx="18" fill="${PANEL}"/>`,
    )
    out.push(
      `<text x="${rightX + 20}" y="${stripTop + 38}" font-family="${MONO}" font-size="16" letter-spacing="0.14em" fill="${SAGE}">WHERE IT HAPPENED</text>`,
    )
    const strip = drawStateStrip(marks, {
      width: rightWidth - 40,
      columnHeight: 96,
      walkedStates: lit,
      termini: true,
      title: 'The fourteen trail states, south to north',
    })
    out.push(`<g transform="translate(${rightX + 20} ${stripTop + 56})">${strip}</g>`)
    out.push(statesLine(rightX + 20, bottom - 24, states.length > 8 ? 16 : 20))
  }
  // The footer: whose list it is.
  out.push(
    `<text x="72" y="${H - 84}" font-family="${MONO}" font-size="20" letter-spacing="0.08em" fill="${SAGE_LIGHT}">${escapeXml(challenge.orgName.toUpperCase())}</text>`,
  )
  out.push(
    `<text x="72" y="${H - 54}" font-family="${MONO}" font-size="20" letter-spacing="0.08em" fill="${SAGE}">× OURHIKE</text>`,
  )
  out.push('</svg>')
  return out.join('')
}

/** `@font-face` rules for the poster's three faces, each file inlined as a
 *  data URL so the rasterised SVG carries its own type. */
export async function posterFontCss(): Promise<string> {
  const faces = await Promise.all(
    [
      [
        'Bitter',
        '700',
        import('../design-system/assets/fonts/bitter-normal-400-700-latin.woff2?url'),
      ],
      [
        'IBM Plex Mono',
        '400',
        import('../design-system/assets/fonts/ibm-plex-mono-normal-400-latin.woff2?url'),
      ],
      [
        'IBM Plex Mono',
        '500',
        import('../design-system/assets/fonts/ibm-plex-mono-normal-500-latin.woff2?url'),
      ],
    ].map(async ([family, weight, module]) => {
      const url = ((await module) as { default: string }).default
      const bytes = new Uint8Array(await (await fetch(url)).arrayBuffer())
      let binary = ''
      for (let i = 0; i < bytes.length; i += 0x8000)
        binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000))
      return `@font-face{font-family:'${family}';font-weight:${weight};src:url(data:font/woff2;base64,${btoa(binary)}) format('woff2')}`
    }),
  )
  return faces.join('')
}

/** The SVG drawn onto a canvas and read back as a PNG. */
export async function rasterise(
  svg: string,
  width = POSTER_WIDTH,
  height = POSTER_HEIGHT,
): Promise<Blob> {
  const url = URL.createObjectURL(new Blob([svg], { type: 'image/svg+xml' }))
  try {
    const image = new Image()
    image.src = url
    await image.decode()
    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const context = canvas.getContext('2d')
    if (context === null) throw new Error('This browser cannot draw the poster.')
    context.drawImage(image, 0, 0, width, height)
    return await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob(
        (blob) =>
          blob === null
            ? reject(new Error('The poster could not be made.'))
            : resolve(blob),
        'image/png',
      ),
    )
  } finally {
    URL.revokeObjectURL(url)
  }
}
