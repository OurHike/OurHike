import { describe, it, expect } from 'vitest'

import {
  NO_CLOSURES,
  closureAgeLabel,
  closuresOf,
  withBaseline,
  withLive,
} from './closureState'
import type { ClosureSummary } from './api'

const CLOSURE = { id: 'c1' } as ClosureSummary
const OTHER = { id: 'c2' } as ClosureSummary

const NOW = new Date('2026-08-08T12:00:00Z')
const hoursBefore = (n: number) => new Date(NOW.getTime() - n * 60 * 60 * 1000)

describe('which source wins', () => {
  it('takes a live read over nothing', () => {
    expect(withLive([CLOSURE]).kind).toBe('live')
  })

  it('takes the baseline when there is no live read', () => {
    const state = withBaseline(NO_CLOSURES, {
      generatedAt: hoursBefore(3),
      closures: [CLOSURE],
    })

    expect(state.kind).toBe('baseline')
    expect(closuresOf(state)).toEqual([CLOSURE])
  })

  it('does not let a late baseline displace a live read', () => {
    // The race this module exists for. Both reads fire independently, so a
    // slow baseline landing after a fast live one is ordinary - and letting it
    // win would swap fresh closures for day-old ones AND label them stale.
    const live = withLive([CLOSURE])

    const state = withBaseline(live, { generatedAt: hoursBefore(20), closures: [OTHER] })

    expect(state).toBe(live)
    expect(closuresOf(state)).toEqual([CLOSURE])
  })

  it('lets a live read replace a baseline that arrived first', () => {
    // The ordinary sequence: baseline lands from the CDN, the backend answers
    // a moment later, and the caveat goes away.
    const baseline = withBaseline(NO_CLOSURES, {
      generatedAt: hoursBefore(5),
      closures: [OTHER],
    })

    const state = withLive([CLOSURE])

    expect(baseline.kind).toBe('baseline')
    expect(state.kind).toBe('live')
    expect(closuresOf(state)).toEqual([CLOSURE])
  })
})

describe('what a hiker is told', () => {
  it('says nothing about age when the data is live', () => {
    // A caveat on data that has none is noise, and noise teaches people to
    // ignore caveats.
    expect(closureAgeLabel(withLive([CLOSURE]), NOW)).toBeNull()
  })

  it('says conditions are unavailable when neither source could be reached', () => {
    // The #249 fix in one assertion: this used to render as nothing at all,
    // indistinguishable from a trail with no closures on it.
    expect(closureAgeLabel(NO_CLOSURES, NOW)).toBe('Trail conditions unavailable')
  })

  it('reports a baseline in hours', () => {
    const state = withBaseline(NO_CLOSURES, { generatedAt: hoursBefore(6), closures: [] })

    expect(closureAgeLabel(state, NOW)).toBe('Conditions as of 6h ago')
  })

  it('reports a baseline in days once it is older than one', () => {
    const state = withBaseline(NO_CLOSURES, {
      generatedAt: hoursBefore(30),
      closures: [],
    })

    expect(closureAgeLabel(state, NOW)).toBe('Conditions as of 1d ago')
  })

  it('rounds a very fresh baseline to less than an hour rather than 0h', () => {
    const state = withBaseline(NO_CLOSURES, {
      generatedAt: hoursBefore(0.25),
      closures: [],
    })

    expect(closureAgeLabel(state, NOW)).toBe('Conditions as of less than an hour ago')
  })

  it('does not report a future timestamp as a negative age', () => {
    // Clock skew between the bake host and the phone. "in 3 hours" on a safety
    // banner reads as a bug and undermines the banner it sits in.
    const state = withBaseline(NO_CLOSURES, {
      generatedAt: hoursBefore(-3),
      closures: [],
    })

    expect(closureAgeLabel(state, NOW)).toBe('Conditions as of less than an hour ago')
  })
})

describe('closuresOf', () => {
  it('is null only when nothing could be read', () => {
    // Every existing consumer - the banner, the map bands - already treats
    // null as "draw no closure warnings". That contract is unchanged; what
    // moved is that null no longer has to carry the reason too.
    expect(closuresOf(NO_CLOSURES)).toBeNull()
    expect(closuresOf(withLive([]))).toEqual([])
  })
})
