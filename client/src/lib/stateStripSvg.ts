// The A.T. as fourteen stops (#1965, frame features/design/blaze-card/
// StateStrip.dc.html): one column per trail state, south to north, each with
// a mark per item that landed there - gold once earned, an outline while not -
// and lit where this hiker walked. An SVG string, for the same reason the map
// is one: the Where view draws it inline and the share poster rasterises it.
//
// NEVER A NUMERAL FOR WHAT IS MISSING (features/VOLUNTEERING.md §5 rule 2).
// The frame printed "+6" over a crowded column, counting outlines with the
// gold. Here a column shows its earned marks first, up to the cap, and a
// "+N" only ever counts earned items the cap left out; outlines fill what
// room is left and are never counted.

import { CHALLENGE_COLOR } from '../map/challengePin'
import type { MileRange } from './walkedMiles'
import { TRAIL_STATES, type TrailStateCode } from './wherePlace'

export interface StripMark {
  state: TrailStateCode
  earned: boolean
}

export interface StripOptions {
  width: number
  /** A column's height; the labels under the strip add to it. */
  columnHeight: number
  /** Which states this hiker walked in, for the lit columns. */
  walkedStates?: ReadonlySet<TrailStateCode>
  /** "Springer Mtn" and "Katahdin" under the ends. */
  termini?: boolean
  title: string
}

const COLUMN = '#1c2f1f'
const COLUMN_WALKED = '#355c3a'
const OUTLINE = '#96b98c'
const ABBR = '#c7dabd'
const ABBR_WALKED = '#fdfaf2'
const TERMINI = '#6b9463'
const MONO = "'IBM Plex Mono', ui-monospace, monospace"

const r1 = (n: number) => Math.round(n * 10) / 10

/** Which trail states a set of walked miles touches, by a mile lookup. */
export function walkedStates(
  walked: readonly MileRange[],
  stateOf: (mile: number) => TrailStateCode | null,
): Set<TrailStateCode> {
  const out = new Set<TrailStateCode>()
  for (const range of walked) {
    // Every tenth of a mile is plenty: a state's shortest run that is not a
    // border wiggle is miles long (West Virginia's, 2.1 mi, is the shortest).
    for (let mile = range.startMile; mile <= range.endMile; mile += 0.1) {
      const state = stateOf(mile)
      if (state !== null) out.add(state)
    }
  }
  return out
}

export function drawStateStrip(
  marks: readonly StripMark[],
  options: StripOptions,
): string {
  const { width, columnHeight } = options
  const count = TRAIL_STATES.length
  const gap = Math.max(2, Math.round(width * 0.006))
  const columnWidth = (width - gap * (count - 1)) / count
  const markWidth = Math.max(4, Math.round(columnWidth * 0.3))
  const markHeight = Math.round(markWidth * 2.2)
  const abbrSize = Math.max(9, Math.round(columnWidth * 0.3))
  const cap = Math.max(1, Math.floor((columnHeight - abbrSize - 12) / (markHeight + 3)))
  const height = columnHeight + (options.termini ? abbrSize + 8 : 0)
  const out: string[] = [
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${options.title.replace(/[<>&"]/g, '')}">`,
  ]
  TRAIL_STATES.forEach(({ code }, index) => {
    const x = index * (columnWidth + gap)
    const walked = options.walkedStates?.has(code) ?? false
    out.push(
      `<rect x="${r1(x)}" y="0" width="${r1(columnWidth)}" height="${columnHeight}" rx="4" fill="${walked ? COLUMN_WALKED : COLUMN}"/>`,
    )
    const here = marks.filter((mark) => mark.state === code)
    const earned = here.filter((mark) => mark.earned).length
    const shownEarned = Math.min(earned, cap)
    const shownOutlines = Math.min(here.length - earned, cap - shownEarned)
    const markX = x + (columnWidth - markWidth) / 2
    let y = columnHeight - abbrSize - 8 - markHeight
    for (let i = 0; i < shownEarned; i += 1) {
      out.push(
        `<rect x="${r1(markX)}" y="${r1(y)}" width="${markWidth}" height="${markHeight}" rx="1" fill="${CHALLENGE_COLOR}"/>`,
      )
      y -= markHeight + 3
    }
    for (let i = 0; i < shownOutlines; i += 1) {
      out.push(
        `<rect x="${r1(markX + 0.5)}" y="${r1(y + 0.5)}" width="${markWidth - 1}" height="${markHeight - 1}" rx="1" fill="none" stroke="${OUTLINE}" stroke-width="1"/>`,
      )
      y -= markHeight + 3
    }
    if (earned > shownEarned) {
      out.push(
        `<text x="${r1(x + columnWidth / 2)}" y="${r1(Math.max(abbrSize, y + markHeight))}" font-family="${MONO}" font-size="${r1(abbrSize * 0.9)}" text-anchor="middle" fill="${CHALLENGE_COLOR}">+${earned - shownEarned}</text>`,
      )
    }
    out.push(
      `<text x="${r1(x + columnWidth / 2)}" y="${r1(columnHeight - 5)}" font-family="${MONO}" font-size="${abbrSize}" text-anchor="middle" letter-spacing="0.04em" fill="${walked ? ABBR_WALKED : ABBR}">${code}</text>`,
    )
  })
  if (options.termini) {
    const y = columnHeight + abbrSize + 4
    const style = `font-family="${MONO}" font-size="${r1(abbrSize * 0.85)}" letter-spacing="0.1em" fill="${TERMINI}"`
    out.push(`<text x="0" y="${y}" ${style}>SPRINGER MTN</text>`)
    out.push(`<text x="${width}" y="${y}" ${style} text-anchor="end">KATAHDIN</text>`)
  }
  out.push('</svg>')
  return out.join('')
}
