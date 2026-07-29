import { describe, it, expect, vi } from 'vitest'
import { searchPois, SEARCH_RESULT_LIMIT } from './searchPoi'

// WIREFRAMES.md Interactions: search is "local GeoJSON only, no network path,
// and says so on empty results" (`7c`). The no-network part is the whole
// point - search that needs signal is useless exactly where it is needed, so
// this module works only against what is already on the phone.

const POIS = [
  { id: '1', name: 'Rocky Run Shelter', type: 'shelter', mile: 1043.2 },
  { id: '2', name: 'Rocky Gap Spring', type: 'water', mile: 1051.8 },
  { id: '3', name: 'Annapolis Rock', type: 'campsite', mile: 1049.1 },
  { id: '4', name: 'Pine Knob Shelter', type: 'shelter', mile: 1055.0 },
  { id: '5', name: 'Ed Garvey Shelter', type: 'shelter', mile: 1035.6 },
]

describe('searchPois', () => {
  it('finds a place by name, regardless of case', () => {
    expect(searchPois('rocky run', POIS).map((p) => p.id)).toEqual(['1'])
  })

  it('matches anywhere in the name, not just the start', () => {
    expect(searchPois('rock', POIS).map((p) => p.id)).toContain('3')
  })

  it('ranks a name that starts with the query above one that merely contains it', () => {
    // Someone typing "rock" almost certainly wants Rocky Run before
    // Annapolis Rock.
    const ids = searchPois('rock', POIS).map((p) => p.id)

    expect(ids.indexOf('1')).toBeLessThan(ids.indexOf('3'))
  })

  it('returns nothing for an empty query rather than the whole trail', () => {
    expect(searchPois('', POIS)).toEqual([])
  })

  it('returns nothing for a whitespace-only query', () => {
    expect(searchPois('   ', POIS)).toEqual([])
  })

  it('ignores surrounding whitespace in a real query', () => {
    expect(searchPois('  pine knob  ', POIS).map((p) => p.id)).toEqual(['4'])
  })

  it('returns an empty list, not an error, when nothing matches', () => {
    expect(searchPois('katahdin', POIS)).toEqual([])
  })

  it('can be filtered to a single waypoint type', () => {
    const shelters = searchPois('rock', POIS, { type: 'shelter' })

    expect(shelters.every((p) => p.type === 'shelter')).toBe(true)
  })

  it('caps how many results come back, so the sheet stays scannable', () => {
    const many = Array.from({ length: 200 }, (_, i) => ({
      id: `x${i}`,
      name: `Spring ${i}`,
      type: 'water',
      mile: 1000 + i,
    }))

    expect(searchPois('spring', many)).toHaveLength(SEARCH_RESULT_LIMIT)
  })

  it('never touches the network - search has to work with no signal', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')

    searchPois('rocky', POIS)

    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })
})
