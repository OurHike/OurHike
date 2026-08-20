import { describe, it, expect } from 'vitest'
import { rollUpNotes, rollupByPoi, CONTESTED_WINDOW_DAYS } from './noteRollup'
import type { NoteSummary } from './fieldNotes'

// FIELD_NOTES.md §3: three things derived from the notes at render time -
// last confirmed (staleness.ts's long-missing producer, #256), a one-line
// headline, and "contested" when recent notes disagree, which shows BOTH
// rather than averaging or picking a winner (value #4 doing real work).

const NOW = new Date('2026-08-20T12:00:00Z')
const DAY_MS = 24 * 60 * 60 * 1000

function note(overrides: Partial<NoteSummary>): NoteSummary {
  return {
    id: crypto.randomUUID(),
    poi_id: 'osm_water:123',
    lat: 41.2,
    lon: -74.1,
    mile: 1382.4,
    observation: 'flowing',
    note: null,
    observed_at: new Date(NOW.getTime() - 3 * DAY_MS).toISOString(),
    reporter_type: 'thru',
    ...overrides,
  }
}

describe('rollUpNotes', () => {
  it('answers null-everything for a place with no notes - which staleness reads as never', () => {
    expect(rollUpNotes([], NOW)).toEqual({
      lastConfirmedAt: null,
      headline: null,
      contested: null,
    })
  })

  it('takes last-confirmed from the newest observation, whatever order the wire sent', () => {
    const older = note({
      observed_at: new Date(NOW.getTime() - 9 * DAY_MS).toISOString(),
    })
    const newer = note({
      observed_at: new Date(NOW.getTime() - 2 * DAY_MS).toISOString(),
    })

    const rollup = rollUpNotes([older, newer], NOW)

    expect(rollup.lastConfirmedAt?.toISOString()).toBe(newer.observed_at)
  })

  it('writes the headline as the design words it: observation, age, reporter type', () => {
    const dry = note({
      observation: 'dry',
      reporter_type: 'thru',
      observed_at: new Date(NOW.getTime() - 3 * DAY_MS).toISOString(),
    })

    expect(rollUpNotes([dry], NOW).headline?.text).toBe('Dry — 3 days ago, thru-hiker')
  })

  it('says today and yesterday rather than 0 and 1 days ago', () => {
    const today = note({ observed_at: NOW.toISOString(), reporter_type: 'maintainer' })
    const yesterday = note({
      observed_at: new Date(NOW.getTime() - 1 * DAY_MS).toISOString(),
      reporter_type: 'day',
    })

    expect(rollUpNotes([today], NOW).headline?.text).toBe('Flowing — today, maintainer')
    expect(rollUpNotes([yesterday], NOW).headline?.text).toBe(
      'Flowing — yesterday, day hiker',
    )
  })

  it('headlines a text-only note as Noted rather than inventing a tag', () => {
    const prose = note({ observation: null, note: 'Piped spring north is better.' })

    expect(rollUpNotes([prose], NOW).headline?.text).toContain('Noted —')
  })

  it('marks a place contested when two recent tagged notes disagree, and shows both', () => {
    const saysDry = note({
      observation: 'dry',
      observed_at: new Date(NOW.getTime() - 1 * DAY_MS).toISOString(),
    })
    const saysFlowing = note({
      observation: 'flowing',
      observed_at: new Date(NOW.getTime() - 4 * DAY_MS).toISOString(),
      reporter_type: 'section',
    })

    const rollup = rollUpNotes([saysFlowing, saysDry], NOW)

    expect(rollup.contested).not.toBeNull()
    expect(rollup.contested?.[0].observation).toBe('dry')
    expect(rollup.contested?.[1].observation).toBe('flowing')
  })

  it('does not call it contested when the disagreeing note has aged out of the window', () => {
    // "Dry in June, flowing in August" is a spring that recovered, not a
    // live disagreement.
    const current = note({ observation: 'flowing', observed_at: NOW.toISOString() })
    const longAgo = note({
      observation: 'dry',
      observed_at: new Date(
        NOW.getTime() - (CONTESTED_WINDOW_DAYS + 5) * DAY_MS,
      ).toISOString(),
    })

    expect(rollUpNotes([current, longAgo], NOW).contested).toBeNull()
  })

  it('never reads prose as disagreement - text-only notes cannot contest', () => {
    const tagged = note({ observation: 'flowing', observed_at: NOW.toISOString() })
    const prose = note({
      observation: null,
      note: 'actually looked pretty dry to me',
      observed_at: NOW.toISOString(),
    })

    expect(rollUpNotes([tagged, prose], NOW).contested).toBeNull()
  })
})

describe('rollupByPoi', () => {
  it('groups by place and drops notes that anchor to no pin', () => {
    const here = note({ poi_id: 'osm_water:123' })
    const there = note({ poi_id: 'atc_shelters:9', observation: 'fine' })
    const nowhere = note({ poi_id: null })

    const rollups = rollupByPoi([here, there, nowhere], NOW)

    expect([...rollups.keys()].sort()).toEqual(['atc_shelters:9', 'osm_water:123'])
    expect(rollups.get('atc_shelters:9')?.headline?.text).toContain('Fine')
  })
})
