import { describe, it, expect } from 'vitest'
import {
  EMPTY_CLUB_SECTIONS,
  clubAtMile,
  clubBoundaryMiles,
  clubRunAtMile,
  clubTimeline,
  parseClubSections,
  unattributedTotal,
  type ClubSections,
} from './clubSections'

/** A cut-down club_sections.json in the shape export_club_sections.py writes:
 *  three clubs tiling 0-300, with 20 miles in the middle the centerline cannot
 *  attribute, and MATC holding two separate pieces the way four real clubs do. */
const ARTIFACT = {
  sources: {
    attribution: 'centerline',
    names: 'trail_club_sections',
    miles: 'half_mile_points_from_springer',
  },
  clubs: [
    {
      acronym: 'GATC',
      name: 'Georgia Appalachian Trail Club',
      region: 'SORO',
      stretches: [{ start_mile: 0, end_mile: 77 }],
      miles: 77,
    },
    {
      acronym: 'NHC',
      name: 'Nantahala Hiking Club',
      region: 'SORO',
      stretches: [{ start_mile: 77, end_mile: 100 }],
      miles: 23,
    },
    {
      acronym: 'MATC',
      name: 'Maine Appalachian Trail Club',
      region: 'NERO',
      stretches: [
        { start_mile: 120, end_mile: 300 },
        { start_mile: 100, end_mile: 110 },
      ],
      miles: 190,
    },
  ],
  unattributed: [{ start_mile: 110, end_mile: 120 }],
}

function parsed(): ClubSections {
  return parseClubSections(ARTIFACT)
}

describe('parseClubSections', () => {
  it('reads the artifact’s `stretches` into `runs`, because stretch is spoken for', () => {
    // #552 gave `stretch` to the 50-mile download unit and the maintainer asked
    // that nothing else reuse it. The published key keeps its name; the word
    // stops at this boundary.
    const gatc = parsed().clubs.find((c) => c.acronym === 'GATC')
    expect(gatc?.runs).toEqual([{ startMile: 0, endMile: 77 }])
  })

  it('keeps the two source layers apart, since they are two years apart', () => {
    expect(parsed().sources).toEqual({
      attribution: 'centerline',
      names: 'trail_club_sections',
      miles: 'half_mile_points_from_springer',
    })
  })

  it('publishes the unattributed runs rather than leaving gaps', () => {
    // A gap would read as "no trail here". The whole point of the exporter
    // publishing these is that "not recorded" is visibly a different fact.
    expect(parsed().unattributed).toEqual([{ startMile: 110, endMile: 120 }])
  })

  it.each([
    ['not an object', 42],
    ['null', null],
    ['an array', []],
    ['an empty object', {}],
  ])('yields no sections rather than throwing, given %s', (_label, raw) => {
    expect(parseClubSections(raw)).toEqual(EMPTY_CLUB_SECTIONS)
  })

  it('drops a single unreadable club without losing the ones beside it', () => {
    // A release must not lose every club because one row is malformed - the
    // same restraint fetchSpurs applies to a whole missing artifact.
    const result = parseClubSections({
      clubs: [
        {
          acronym: 'GATC',
          name: 'Georgia',
          stretches: [{ start_mile: 0, end_mile: 77 }],
        },
        { name: 'no acronym at all', stretches: [{ start_mile: 77, end_mile: 90 }] },
        { acronym: 'NHC', name: 'Nantahala', stretches: 'not a list' },
      ],
    })
    expect(result.clubs.map((c) => c.acronym)).toEqual(['GATC'])
  })

  it('drops a zero-width run, which would tick a boundary standing on nothing', () => {
    const result = parseClubSections({
      clubs: [
        {
          acronym: 'GATC',
          name: 'Georgia',
          stretches: [
            { start_mile: 10, end_mile: 10 },
            { start_mile: 10, end_mile: 20 },
          ],
        },
      ],
    })
    expect(result.clubs[0].runs).toEqual([{ startMile: 10, endMile: 20 }])
  })

  it('falls back to the acronym when the stale polygon layer names no club', () => {
    // The centerline is fresh and the names are two years old, so the fresh
    // source can name a club the stale one has never heard of. "GATC" is a
    // worse heading than the full name and a far better one than blank.
    const result = parseClubSections({
      clubs: [{ acronym: 'GATC', stretches: [{ start_mile: 0, end_mile: 77 }] }],
    })
    expect(result.clubs[0]).toMatchObject({ name: 'GATC', region: null })
  })
})

describe('clubTimeline', () => {
  it('reads the corridor in mile order, not in the file’s order', () => {
    // The artifact groups by club, so runs interleave the moment one club
    // holds two pieces - MATC's 120-300 is written before its own 100-110.
    expect(clubTimeline(parsed()).map((run) => run.startMile)).toEqual([
      0, 77, 100, 110, 120,
    ])
  })

  it('tiles the trail with no seam and no overlap', () => {
    // The exporter's central guarantee, and the thing that makes "not
    // recorded" distinguishable from "no trail here".
    const timeline = clubTimeline(parsed())
    for (let i = 1; i < timeline.length; i += 1) {
      expect(timeline[i].startMile).toBe(timeline[i - 1].endMile)
    }
  })

  it('carries the unattributed run in the line rather than off to one side', () => {
    const unattributed = clubTimeline(parsed()).filter((run) => run.club === null)
    expect(unattributed).toEqual([{ startMile: 110, endMile: 120, club: null }])
  })
})

describe('clubRunAtMile', () => {
  const timeline = clubTimeline(parsed())

  it('resolves a shared boundary mile northbound, never to both clubs', () => {
    // Runs abut exactly - GATC ends at 77 and NHC starts at 77 - so without a
    // half-open rule mile 77 has two answers.
    expect(clubAtMile(timeline, 76.9)?.acronym).toBe('GATC')
    expect(clubAtMile(timeline, 77)?.acronym).toBe('NHC')
  })

  it('includes the far end, because Katahdin is a place a hiker can stand', () => {
    // Half-open everywhere else would make the corridor's last mile answer
    // "not recorded" when the artifact plainly attributes it.
    expect(clubAtMile(timeline, 300)?.acronym).toBe('MATC')
  })

  it.each([-1, 300.1, Number.NaN])(
    'answers nothing off the published corridor (%s)',
    (mile) => {
      expect(clubRunAtMile(timeline, mile)).toBeNull()
    },
  )

  it('tells an unattributed mile apart from a mile off the trail', () => {
    // Both give no club, and they are different facts with different
    // sentences: one says "not recorded", the other draws nothing at all.
    expect(clubRunAtMile(timeline, 115)).toEqual({
      startMile: 110,
      endMile: 120,
      club: null,
    })
    expect(clubAtMile(timeline, 115)).toBeNull()
    expect(clubRunAtMile(timeline, 400)).toBeNull()
  })
})

describe('clubBoundaryMiles', () => {
  it('ticks where responsibility changes hands, and not at the trail’s ends', () => {
    // Springer and Katahdin are where the trail stops. A tick there would say
    // something false about both.
    expect(clubBoundaryMiles(clubTimeline(parsed()))).toEqual([77, 100, 110, 120])
  })

  it('has nothing to tick when nothing is published', () => {
    expect(clubBoundaryMiles(clubTimeline(EMPTY_CLUB_SECTIONS))).toEqual([])
  })
})

describe('unattributedTotal', () => {
  it('counts the miles and the runs the legend and the sheet both quote', () => {
    expect(unattributedTotal(parsed())).toEqual({ miles: 10, runs: 1 })
  })

  it('is zero rather than absent when every mile is attributed', () => {
    expect(unattributedTotal(EMPTY_CLUB_SECTIONS)).toEqual({ miles: 0, runs: 0 })
  })
})
