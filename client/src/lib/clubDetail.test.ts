import { describe, it, expect } from 'vitest'
import { clubTimeline, parseClubSections, type ClubSections } from './clubSections'
import { buildClubDetail } from './clubDetail'
import type { MileRange } from './walkedMiles'

const ARTIFACT = {
  sources: {
    attribution: 'centerline',
    names: 'trail_club_sections',
    miles: 'half_mile_points_from_springer',
  },
  clubs: [
    {
      acronym: 'PATC',
      name: 'Potomac Appalachian Trail Club',
      region: 'MARO',
      stretches: [
        { start_mile: 940.2, end_mile: 1013.4 },
        { start_mile: 1015.2, end_mile: 1180.9 },
      ],
      miles: 238.9,
    },
    {
      acronym: 'RMC',
      // No region: the polygon layer is two years old and does not carry
      // every club the fresh centerline names.
      name: 'Randolph Mountain Club',
      stretches: [{ start_mile: 1800, end_mile: 1802.5 }],
      miles: 2.5,
    },
  ],
  unattributed: [{ start_mile: 1013.4, end_mile: 1015.2 }],
}

function detail(mile: number, sections: ClubSections = parseClubSections(ARTIFACT)) {
  return buildClubDetail(sections, clubTimeline(sections), mile, 'imperial')
}

describe('buildClubDetail', () => {
  it('names the club, its acronym and its region', () => {
    expect(detail(1000)).toMatchObject({
      heading: 'Potomac Appalachian Trail Club',
      subtitle: 'PATC · MARO',
    })
  })

  it('gives the run under the finger, not the club’s whole span', () => {
    // PATC holds two pieces here. Tapping the second must not report the
    // first's mileposts, which is the bug a club-keyed lookup would have.
    expect(detail(1100)?.rangeLine).toBe('mi 1,015.2 – 1,180.9')
    expect(detail(1000)?.rangeLine).toBe('mi 940.2 – 1,013.4')
  })

  it('reports the club’s whole share beside the piece tapped', () => {
    expect(detail(1000)?.extentLine).toBe('238.9 mi maintained, in 2 sections')
  })

  it('says section, singular, for a club that holds one piece', () => {
    expect(detail(1801)?.extentLine).toBe('2.5 mi maintained, in 1 section')
  })

  it('drops the region rather than printing half a subtitle', () => {
    // The polygon layer carries no region for this club. An empty half - "RMC
    // · " - would read as a rendering bug rather than as missing data.
    expect(detail(1801)?.subtitle).toBe('RMC')
  })

  it('mile markers do not convert with the unit preference', () => {
    // A mile marker is a shared coordinate, not a distance - lib/units.ts's
    // opening rule, and the same call lineDetail.ts makes.
    const sections = parseClubSections(ARTIFACT)
    const metric = buildClubDetail(sections, clubTimeline(sections), 1000, 'metric')
    expect(metric?.rangeLine).toBe('mi 940.2 – 1,013.4')
    // The maintained LENGTH is a distance, and does convert.
    expect(metric?.extentLine).toBe('384.5 km maintained, in 2 sections')
  })
})

describe('a stretch with no recorded club', () => {
  it('says the source cannot name one, never that nobody maintains it', () => {
    // Somebody almost certainly does. The sheet's job is to report what ATC's
    // centerline does and does not say.
    const absent = detail(1014)
    expect(absent?.heading).toBe('Club not recorded')
    expect(absent?.absenceLine).toBe('ATC’s centerline does not name a club along here.')
    expect(absent?.absenceLine).not.toMatch(/nobody|no club maintains|unmaintained/i)
  })

  it('puts the stretch in proportion, so it reads as a gap and not as a fault', () => {
    expect(detail(1014)?.scaleLine).toBe('1.8 mi of the trail are like this, in 1 run.')
  })

  it('claims no scale when a release names every mile', () => {
    const named = parseClubSections({ ...ARTIFACT, unattributed: [] })
    // Mile 1,014 is now outside the published corridor entirely - the gap it
    // sat in is gone - so the honest answer is no sheet at all.
    expect(detail(1014, named)).toBeNull()
  })

  it('offers no club name source, having taken no name from anywhere', () => {
    expect(detail(1014)?.nameSourceLine).toBeNull()
    expect(detail(1014)?.extentLine).toBeNull()
  })
})

describe('provenance', () => {
  it('names the two layers separately, because they are two different claims', () => {
    // WHICH club is decided by the centerline; how it is SPELLED comes from
    // the club-section polygons. Collapsing them into one "source" line would
    // lose the distinction the exporter publishes them separately to keep.
    expect(detail(1000)).toMatchObject({
      attributionSourceLine: 'Who maintains it: the ATC’s trail centerline',
      nameSourceLine: 'Club name: the ATC’s club-section map',
    })
  })

  it('prints no date where the release carries none', () => {
    // Not hypothetical, and it is why the date is APPENDED rather than
    // substituted: ARTIFACT has no `source_edited`, which is every release
    // published before #852 and every phone still holding one. Inventing a
    // date to fill the slot would be the claim-nobody-checked failure the
    // dates existed in a docstring to avoid.
    const lines = Object.values(detail(1000) ?? {}).filter(
      (value): value is string => typeof value === 'string',
    )
    for (const line of lines) {
      expect(line).not.toMatch(/\b20\d\d\b/)
    }
  })

  it('says nothing about a source the artifact does not name', () => {
    const bare = parseClubSections({ ...ARTIFACT, sources: {} })
    expect(detail(1000, bare)).toMatchObject({
      attributionSourceLine: null,
      nameSourceLine: null,
    })
  })

  it('does not name one layer twice as if two sources agreed', () => {
    const same = parseClubSections({
      ...ARTIFACT,
      sources: { attribution: 'centerline', names: 'centerline' },
    })
    expect(detail(1000, same)?.nameSourceLine).toBeNull()
  })
})

/**
 * The dated release (#852).
 *
 * The two dates are the whole argument for publishing them separately: WHICH
 * club is decided by a layer edited days ago, how it is SPELLED by one edited
 * two years ago, and a hiker reading a club name is entitled to know which
 * half they are looking at.
 */
describe('provenance, once the release carries the dates', () => {
  const DATED = parseClubSections({
    ...ARTIFACT,
    source_edited: {
      centerline: '2026-08-04',
      trail_club_sections: '2024-08-15',
    },
  })

  it('finishes both sentences, two years apart', () => {
    expect(detail(1000, DATED)).toMatchObject({
      attributionSourceLine: 'Who maintains it: the ATC’s trail centerline, 4 Aug 2026',
      nameSourceLine: 'Club name: the ATC’s club-section map, 15 Aug 2024',
    })
  })

  it('dates the layers it can and still names the one it cannot', () => {
    // An upstream edit-date lookup can fail for one layer and not another -
    // fetch_all.py records the layer anyway. The undated line must not go
    // missing; it falls back to the sentence it had before #852.
    const partial = parseClubSections({
      ...ARTIFACT,
      source_edited: { centerline: '2026-08-04' },
    })
    expect(detail(1000, partial)).toMatchObject({
      attributionSourceLine: 'Who maintains it: the ATC’s trail centerline, 4 Aug 2026',
      nameSourceLine: 'Club name: the ATC’s club-section map',
    })
  })

  it('drops a date it cannot read rather than printing it raw', () => {
    const junk = parseClubSections({
      ...ARTIFACT,
      source_edited: { centerline: 'last Tuesday', trail_club_sections: 20240815 },
    })
    expect(detail(1000, junk)).toMatchObject({
      attributionSourceLine: 'Who maintains it: the ATC’s trail centerline',
      nameSourceLine: 'Club name: the ATC’s club-section map',
    })
  })

  it('dates the unattributed sheet too, which names a source and no club', () => {
    // The 38.5 miles ATC's own centerline cannot attribute. It still says
    // which layer could not say, and now when that layer was last edited.
    expect(detail(1014, DATED)).toMatchObject({
      heading: 'Club not recorded',
      attributionSourceLine: 'Who maintains it: the ATC’s trail centerline, 4 Aug 2026',
      nameSourceLine: null,
    })
  })
})

describe('a tap outside the published corridor', () => {
  it('gets no sheet, which is a different fact from an unattributed mile', () => {
    expect(detail(3000)).toBeNull()
    expect(detail(-1)).toBeNull()
  })
})

/**
 * #598's `visited`, answered on the phone about the phone's own fixes.
 *
 * The count across hikers this basis was originally posed as needs an explicit
 * decision about features/EVENTING.md rule 2 before anybody builds it; what
 * ships here needs none, because it uploads nothing.
 */
describe('what this hiker has walked', () => {
  const sections = parseClubSections(ARTIFACT)

  function withWalked(mile: number, walked: readonly MileRange[]) {
    return buildClubDetail(sections, clubTimeline(sections), mile, 'imperial', walked)
  }

  it('reports the overlap with the run under the finger', () => {
    // PATC's first run is 940.2-1,013.4; only the part inside it counts.
    const walked: MileRange[] = [{ startMile: 1000, endMile: 1020 }]
    expect(withWalked(1000, walked)?.walkedLine).toBe(
      'You have walked 13.4 mi of this section.',
    )
  })

  it('says nothing when they have walked none of it', () => {
    // Most people, on most of the trail. A "0 mi" line is a scold, not a fact.
    expect(withWalked(1000, [])?.walkedLine).toBeNull()
    expect(withWalked(1000, [{ startMile: 1, endMile: 2 }])?.walkedLine).toBeNull()
  })

  it('says nothing for a walk too short to round to a tenth', () => {
    expect(
      withWalked(1000, [{ startMile: 1000, endMile: 1000.02 }])?.walkedLine,
    ).toBeNull()
  })

  it('answers for an unrecorded stretch too, which is still ground underfoot', () => {
    expect(withWalked(1014, [{ startMile: 1013.4, endMile: 1015.2 }])?.walkedLine).toBe(
      'You have walked 1.8 mi of this section.',
    )
  })

  it('defaults to nothing walked, so every existing caller is unchanged', () => {
    const plain = buildClubDetail(sections, clubTimeline(sections), 1000, 'imperial')
    expect(plain?.walkedLine).toBeNull()
  })
})
