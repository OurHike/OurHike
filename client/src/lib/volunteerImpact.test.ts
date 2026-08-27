import { describe, it, expect } from 'vitest'
import { impactTiles, IMPACT_NOT_COUNTED, IMPACT_SUBTITLE } from './volunteerImpact'
import type { VolunteerHoursSummary } from './volunteerHours'

// #969 / features/VOLUNTEERING.md §5. Most of what is asserted here is what
// this module DECLINES to produce, because the guardrail it has to get past is
// written down in four separate places and every one of them is about a
// scoreboard. What survives is memory: one person's own records, read back.

function record(overrides: Partial<VolunteerHoursSummary>): VolunteerHoursSummary {
  return {
    id: crypto.randomUUID(),
    club_id: null,
    worked_on: '2026-08-18',
    hours: 4,
    work_project_id: null,
    activity: 'maintenance',
    note: null,
    mile: null,
    lat: null,
    lon: null,
    state: 'claimed',
    confirmed_at: null,
    recorded_at: '2026-08-18T22:00:00Z',
    ...overrides,
  }
}

describe('impactTiles', () => {
  it('counts the days out and the hours written down', () => {
    const tiles = impactTiles([
      record({ hours: 4, worked_on: '2026-08-18' }),
      record({ hours: 3.5, worked_on: '2026-08-17' }),
    ])

    expect(tiles).toEqual([
      { label: 'Days out', value: '2' },
      {
        label: 'Hours you wrote down',
        value: '7.5',
        caveat: '7.5 not yet confirmed' + ' by a club',
      },
    ])
  })

  it('treats two records on one Saturday as one day of showing up', () => {
    // hoursTotals' own rule, reused rather than recounted, so the panel and the
    // totals line above it cannot come to disagree about what a day is.
    const tiles = impactTiles([
      record({ hours: 3, worked_on: '2026-08-18' }),
      record({ hours: 2, worked_on: '2026-08-18' }),
    ])

    expect(tiles[0]).toEqual({ label: 'Day out', value: '1' })
  })

  it('carries the unconfirmed slice inside the tile, not beside it', () => {
    // #761's rule: the state always travels where the number does. A tile that
    // shed its caveat on the way up from the record would be the panel making a
    // firmer claim than the logbook under it.
    const tiles = impactTiles([
      record({ hours: 4, state: 'confirmed', worked_on: '2026-08-18' }),
      record({ hours: 2, state: 'claimed', worked_on: '2026-08-17' }),
    ])
    const hours = tiles.find((tile) => tile.label === 'Hours you wrote down')

    expect(hours?.value).toBe('6')
    expect(hours?.caveat).toBe('2 not yet confirmed by a club')
  })

  it('says nothing about confirmation once a club has stood behind all of it', () => {
    const tiles = impactTiles([record({ hours: 4, state: 'confirmed' })])

    expect(tiles.find((tile) => tile.label === 'Hours you wrote down')?.caveat).toBe(
      undefined,
    )
  })

  it('drops a disputed record from both counts', () => {
    // The same states hoursTotals counts. A day that exists only as a disputed
    // record is not a day this panel may claim.
    const tiles = impactTiles([
      record({ hours: 4, state: 'claimed', worked_on: '2026-08-18' }),
      record({ hours: 8, state: 'disputed', worked_on: '2026-08-16' }),
    ])

    expect(tiles).toEqual([
      { label: 'Day out', value: '1' },
      {
        label: 'Hours you wrote down',
        value: '4',
        caveat: '4 not yet confirmed by a club',
      },
    ])
  })

  describe('the guardrail, as things it will not produce', () => {
    it('produces nothing at all for a hiker with no records', () => {
      // Rule 2 taken literally. An empty panel headed "what you've put back" is
      // the most pointed lack-state this screen could draw, and the component
      // renders nothing when this is empty.
      expect(impactTiles(null)).toEqual([])
      expect(impactTiles([])).toEqual([])
    })

    it('produces nothing for records that all count for nothing', () => {
      expect(impactTiles([record({ hours: 8, state: 'disputed' })])).toEqual([])
    })

    it('never returns a total across the tiles', () => {
      // Rule 4: "no single composite score - the moment there is one number
      // there is a thing to maximise". Asserted as the shape rather than as a
      // value, because the failure would be a new tile rather than a wrong one.
      const tiles = impactTiles([
        record({ hours: 4 }),
        record({ worked_on: '2026-08-17' }),
      ])

      expect(tiles.map((tile) => tile.label)).toEqual([
        'Days out',
        'Hours you wrote down',
      ])
    })

    it('has no wording anywhere that puts a second person or a target in the frame', () => {
      // Rule 1 and rule 2 as a text assertion over everything this module can
      // print. Crude on purpose: it catches the copy edit that reintroduces the
      // thing four docs have forbidden, which is how this feature would fail.
      const everything = [
        IMPACT_SUBTITLE,
        IMPACT_NOT_COUNTED,
        ...impactTiles([record({})]).flatMap((tile) => [
          tile.label,
          tile.value,
          tile.caveat ?? '',
        ]),
      ].join(' ')

      for (const forbidden of [
        /streak/i,
        /rank/i,
        /average/i,
        /other hikers/i,
        /percentile/i,
        /goal/i,
        /target/i,
        /badge/i,
        /leaderboard/i,
        /since (June|last)/i,
      ]) {
        expect(everything).not.toMatch(forbidden)
      }
    })

    it('says whose fault the two missing tiles are', () => {
      // Frame 2 draws four tiles and two have no source (#967). The sentence
      // has to be about the APP rather than the hiker - "you have filed no
      // notes" is a lack-state, "this app does not keep a record" is a
      // confession - so it is asserted as containing the app's admission.
      expect(IMPACT_NOT_COUNTED).toMatch(/forgets what it filed/i)
      expect(IMPACT_NOT_COUNTED).toMatch(/this app’s gap, not a gap in what you did/i)
    })
  })
})
