import { describe, expect, it } from 'vitest'
import { parseChallengeMap, stateAtMile } from './challengeMap'
import { MAP_DOCUMENT, fixtureMap } from './challengeMap.fixtures'

const copy = () => JSON.parse(JSON.stringify(MAP_DOCUMENT)) as Record<string, unknown>

describe('reading challenge_map.json (#1965)', () => {
  it('reads the published shape into what the map draws', () => {
    const map = fixtureMap()
    expect(map.trail).toHaveLength(2)
    expect(map.trail[0].miles).toEqual([0, 450, 715, 1026.5])
    expect(map.states.map((state) => [state.code, state.trail])).toEqual([
      ['GA', true],
      ['VA', true],
      [null, false],
    ])
    expect(map.stateRuns[0]).toEqual({ code: 'GA', fromMile: 0, toMile: 78.2 })
    expect(map.credits.map((entry) => entry.credit)).toEqual([
      'Appalachian Trail Conservancy',
      'U.S. Census Bureau',
      'Natural Earth',
    ])
  })

  it('is no map at all without a trail, a frame or the format it knows', () => {
    expect(parseChallengeMap({ ...copy(), trail: [] })).toBeNull()
    expect(parseChallengeMap({ ...copy(), frame: [1, 2] })).toBeNull()
    expect(parseChallengeMap({ ...copy(), format: 2 })).toBeNull()
    expect(parseChallengeMap(null)).toBeNull()
  })

  it('drops a malformed part and keeps the rest of the map', () => {
    const document = copy()
    const trail = document.trail as { coordinates: unknown[]; miles: unknown[] }[]
    trail[1].miles = [1027, 1300]
    ;(document.states as { polygons: unknown }[])[2].polygons = 'not polygons'
    ;(document.state_runs as unknown[]).push(['XX', 0, 1], ['GA', 5, 1])
    const map = parseChallengeMap(document)!
    expect(map.trail).toHaveLength(1)
    expect(map.states).toHaveLength(2)
    expect(map.stateRuns).toHaveLength(5)
  })

  it('names the state a mile is in from the published runs, and nothing off their ends', () => {
    const { stateRuns } = fixtureMap()
    expect(stateAtMile(stateRuns, 0)).toBe('GA')
    expect(stateAtMile(stateRuns, 714.9)).toBe('VA')
    expect(stateAtMile(stateRuns, 1025)).toBe('WV')
    expect(stateAtMile(stateRuns, 2197.9)).toBe('ME')
    expect(stateAtMile(stateRuns, 1500)).toBeNull()
    expect(stateAtMile([], 10)).toBeNull()
  })
})
