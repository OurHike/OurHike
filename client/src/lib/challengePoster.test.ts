// The share poster and the strip of states (#1965). The rasteriser needs a
// real browser and is not exercised here; what is held is what the image
// says - the words, the counts, what is and is not on it.

import { describe, expect, it } from 'vitest'
import { ATC_CHALLENGE } from './challenges.fixtures'
import { EMPTY_CHALLENGE_STATE, join, tag, tagsFor } from './challengeProgress'
import { mapPins, posterSvg, stripMarks, type PosterInput } from './challengePoster'
import { fixtureMap } from './challengeMap.fixtures'
import { stateAtMile } from './seasonStrip'
import { drawStateStrip, walkedStates } from './stateStripSvg'
import type { TagPlace } from './tagPlace'

const item = (id: string) => ATC_CHALLENGE.items.find((entry) => entry.id === id)!

function earned(entries: { id: string; place?: TagPlace; how?: 'gps' | 'hand' }[]) {
  let state = join(
    EMPTY_CHALLENGE_STATE,
    ATC_CHALLENGE.id,
    new Date('2027-06-01T12:00:00Z'),
  )
  for (const entry of entries)
    state = tag(state, ATC_CHALLENGE, item(entry.id), {
      at: new Date('2027-07-02T15:00:00Z'),
      how: entry.how ?? 'hand',
      place: entry.place,
    }).state
  return tagsFor(state, ATC_CHALLENGE.id)
}

function input(overrides: Partial<PosterInput> = {}): PosterInput {
  return {
    challenge: ATC_CHALLENGE,
    tags: earned([
      { id: 'springer-mountain' },
      { id: 'mcafee-knob' },
      { id: 'trivia-quiz' },
    ]),
    today: '2027-07-14',
    stateOf: stateAtMile,
    walked: [],
    units: 'imperial',
    map: null,
    ...overrides,
  }
}

describe('the share poster (#1965)', () => {
  it('says the list, the season, how much trail karma and how many states', () => {
    const svg = posterSvg(input())
    expect(svg).toContain('A.T. SUMMER BUCKET LIST · 2027')
    expect(svg).toContain('>My summer</tspan>')
    expect(svg).toContain('>3</text>')
    expect(svg).toContain('TRAIL KARMA EARNED · 2 STATES')
    expect(svg).toContain('>GA · VA</text>')
    expect(svg).toContain('APPALACHIAN TRAIL CONSERVANCY')
  })

  it('carries the draft line wherever a draft list is named, and no hashtag nobody published', () => {
    const svg = posterSvg(input())
    expect(svg).toContain('Draft · not yet confirmed by the ATC')
    expect(svg).not.toMatch(/#ATBucketList/)
    expect(
      posterSvg(input({ challenge: { ...ATC_CHALLENGE, status: 'published' } })),
    ).not.toContain('Draft')
  })

  it('draws the map only when it is handed one, and never counts what is not earned', () => {
    const states = posterSvg(input())
    const withMap = posterSvg(input({ map: fixtureMap() }))
    expect(states).not.toContain('clip-path="url(#poster-map)"')
    expect(withMap).toContain('clip-path="url(#poster-map)"')
    for (const svg of [states, withMap]) {
      expect(svg).not.toMatch(/remaining|left to go|to go|still to|behind|rank|streak/i)
      expect(svg).not.toMatch(/of 100|\/100|of 25/)
    }
  })

  it('embeds the fonts it is given, so the shared image renders the same anywhere', () => {
    const css = "@font-face{font-family:'Bitter';src:url(data:font/woff2;base64,AAAA)}"
    expect(posterSvg(input({ fontCss: css }))).toContain(
      `<defs><style>${css}</style></defs>`,
    )
    expect(posterSvg(input())).not.toContain('<style>')
  })

  it('puts a pin at each place on the card and at each earned item placed at a mile', () => {
    const pins = mapPins({
      challenge: ATC_CHALLENGE,
      tags: earned([
        { id: 'mcafee-knob' },
        { id: 'white-blaze-photo', place: { kind: 'here', mile: 719.6 } },
      ]),
      stateOf: stateAtMile,
    })
    expect(pins.filter((pin) => pin.earned).map((pin) => pin.mile)).toEqual([
      714.92, 719.6,
    ])
    expect(pins.some((pin) => !pin.earned)).toBe(true)
  })
})

describe('the strip of states (#1965)', () => {
  it('marks earned items gold in their state and the rest of the card as outlines', () => {
    const marks = stripMarks({
      challenge: ATC_CHALLENGE,
      tags: earned([
        { id: 'springer-mountain' },
        { id: 'white-blaze-photo', place: { kind: 'state', state: 'WV' } },
      ]),
      stateOf: stateAtMile,
    })
    expect(marks.filter((mark) => mark.earned)).toEqual([
      { state: 'GA', earned: true },
      { state: 'WV', earned: true },
    ])
    expect(marks.some((mark) => !mark.earned)).toBe(true)
  })

  it('counts only earned items past a full column, never the outlines', () => {
    const marks = [
      ...Array.from({ length: 6 }, () => ({ state: 'VA' as const, earned: true })),
      ...Array.from({ length: 9 }, () => ({ state: 'VA' as const, earned: false })),
    ]
    const svg = drawStateStrip(marks, { width: 358, columnHeight: 64, title: 'states' })
    const more = [...svg.matchAll(/>\+(\d+)</g)].map((match) => Number(match[1]))
    expect(more).toHaveLength(1)
    expect(more[0]).toBeLessThanOrEqual(6)
    expect(svg).toContain('>VA</text>')
    expect(svg.match(/<text[^>]*>[A-Z]{2}<\/text>/g)).toHaveLength(14)
  })

  it('lights the states a walked stretch touches', () => {
    expect(
      [...walkedStates([{ startMile: 70, endMile: 90 }], stateAtMile)].sort(),
    ).toEqual(['GA', 'NC'])
    expect(walkedStates([], stateAtMile).size).toBe(0)
  })
})
