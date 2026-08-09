import { describe, it, expect } from 'vitest'

import {
  UNAVAILABLE,
  conditionsAgeLabel,
  itemsOf,
  withBaseline,
  withLive,
  worstOf,
} from './conditionState'
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
    const state = withBaseline(UNAVAILABLE, [CLOSURE], hoursBefore(3))

    expect(state.kind).toBe('baseline')
    expect(itemsOf(state)).toEqual([CLOSURE])
  })

  it('does not let a late baseline displace a live read', () => {
    // The race this module exists for. Both reads fire independently, so a
    // slow baseline landing after a fast live one is ordinary - and letting it
    // win would swap fresh closures for day-old ones AND label them stale.
    const live = withLive([CLOSURE])

    const state = withBaseline(live, [OTHER], hoursBefore(20))

    expect(state).toBe(live)
    expect(itemsOf(state)).toEqual([CLOSURE])
  })

  it('lets a live read replace a baseline that arrived first', () => {
    // The ordinary sequence: baseline lands from the CDN, the backend answers
    // a moment later, and the caveat goes away.
    const baseline = withBaseline(UNAVAILABLE, [OTHER], hoursBefore(5))

    const state = withLive([CLOSURE])

    expect(baseline.kind).toBe('baseline')
    expect(state.kind).toBe('live')
    expect(itemsOf(state)).toEqual([CLOSURE])
  })
})

describe('what a hiker is told', () => {
  it('says nothing about age when the data is live', () => {
    // A caveat on data that has none is noise, and noise teaches people to
    // ignore caveats.
    expect(conditionsAgeLabel(withLive([CLOSURE]), NOW)).toBeNull()
  })

  it('says conditions are unavailable when neither source could be reached', () => {
    // The #249 fix in one assertion: this used to render as nothing at all,
    // indistinguishable from a trail with no closures on it.
    expect(conditionsAgeLabel(UNAVAILABLE, NOW)).toBe('Trail conditions unavailable')
  })

  it('reports a baseline in hours', () => {
    const state = withBaseline(UNAVAILABLE, [], hoursBefore(6))

    expect(conditionsAgeLabel(state, NOW)).toBe('Conditions as of 6h ago')
  })

  it('reports a baseline in days once it is older than one', () => {
    const state = withBaseline(UNAVAILABLE, [], hoursBefore(30))

    expect(conditionsAgeLabel(state, NOW)).toBe('Conditions as of 1d ago')
  })

  it('rounds a very fresh baseline to less than an hour rather than 0h', () => {
    const state = withBaseline(UNAVAILABLE, [], hoursBefore(0.25))

    expect(conditionsAgeLabel(state, NOW)).toBe('Conditions as of less than an hour ago')
  })

  it('does not report a future timestamp as a negative age', () => {
    // Clock skew between the bake host and the phone. "in 3 hours" on a safety
    // banner reads as a bug and undermines the banner it sits in.
    const state = withBaseline(UNAVAILABLE, [], hoursBefore(-3))

    expect(conditionsAgeLabel(state, NOW)).toBe('Conditions as of less than an hour ago')
  })
})

describe('itemsOf', () => {
  it('is null only when nothing could be read', () => {
    // Every existing consumer - the banner, the map bands, the warning pins -
    // already treats null as "draw nothing". That contract is unchanged; what
    // moved is that null no longer has to carry the reason too.
    expect(itemsOf(UNAVAILABLE)).toBeNull()
    expect(itemsOf(withLive([]))).toEqual([])
  })
})

describe('worstOf', () => {
  // The strip has one line for the whole safety picture, and closures and
  // reports each hold a state of their own (#436). The line is only as good
  // as the weakest source, so the worst state is the one whose caveat shows.

  it('says nothing only when every source is live', () => {
    expect(worstOf(withLive([]), withLive([])).kind).toBe('live')
  })

  it('lets one unavailable source dominate a live one', () => {
    // A live closures read next to unreachable reports is a map silently
    // missing its warning pins - no caveat would claim a completeness the
    // screen does not have.
    expect(worstOf(withLive([]), UNAVAILABLE).kind).toBe('unavailable')
    expect(worstOf(UNAVAILABLE, withLive([])).kind).toBe('unavailable')
  })

  it('prefers a baseline caveat over silence when the other source is live', () => {
    const state = worstOf(withLive([]), withBaseline(UNAVAILABLE, [], hoursBefore(6)))

    expect(conditionsAgeLabel(state, NOW)).toBe('Conditions as of 6h ago')
  })

  it('confesses the older of two baselines', () => {
    const older = withBaseline(UNAVAILABLE, [], hoursBefore(20))
    const newer = withBaseline(UNAVAILABLE, [], hoursBefore(2))

    expect(worstOf(newer, older)).toBe(older)
    expect(worstOf(older, newer)).toBe(older)
  })

  it('ranks unavailable above a baseline', () => {
    const baseline = withBaseline(UNAVAILABLE, [], hoursBefore(2))

    expect(worstOf(baseline, UNAVAILABLE).kind).toBe('unavailable')
  })
})
