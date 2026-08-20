import { describe, it, expect } from 'vitest'
import {
  buildHighlightDetail,
  highlightAscentFt,
  PROFILED_TRAIL,
} from './highlightDetail'
import { NAMED, PUBLISHED, VISITED, parseHighlights, type Highlight } from './highlights'
import type { ElevationProfile } from './elevationProfile'
import type { MileRange } from './walkedMiles'
import { STANDARD_PACE, type PaceProfile } from './pace'

function highlight(overrides: Record<string, unknown> = {}): Highlight {
  return parseHighlights({
    highlights: [
      {
        id: 'mcafee-knob',
        name: 'McAfee Knob',
        bases: [NAMED],
        citations: {
          [NAMED]: { by: 'OurHike', note: 'A ledge.', reviewed: '2026-08-20' },
        },
        legs: [{ trail: PROFILED_TRAIL, start_mile: 10, end_mile: 13.5 }],
        club: 'RATC',
        ...overrides,
      },
    ],
  })[0]
}

/**
 * A profile climbing 500 ft per mile from mile 0 to 20, sampled every tenth.
 *
 * A steady climb rather than a jagged one on purpose: the dead band in
 * elevationGain.ts is what makes a real profile's answer hard to predict, and
 * this file is about what the SHEET does with a gain, not about the gain
 * algorithm - which has its own tests and its own pinned vectors.
 */
function steadyClimb(): ElevationProfile {
  const distanceMi: number[] = []
  const elevationFt: number[] = []
  for (let i = 0; i <= 200; i += 1) {
    distanceMi.push(i / 10)
    elevationFt.push((i / 10) * 500)
  }
  return {
    distanceMi: Float64Array.from(distanceMi),
    elevationFt: Float64Array.from(elevationFt),
  } as unknown as ElevationProfile
}

describe('highlightAscentFt', () => {
  it('measures the climbing over the leg', () => {
    // 3.5 miles at 500 ft/mi.
    expect(highlightAscentFt(highlight(), steadyClimb())).toBeCloseTo(1750, 0)
  })

  it('sums every leg of a highlight that stays on the A.T.', () => {
    const twoLegs = highlight({
      legs: [
        { trail: PROFILED_TRAIL, start_mile: 1, end_mile: 2 },
        { trail: PROFILED_TRAIL, start_mile: 5, end_mile: 7 },
      ],
    })
    expect(highlightAscentFt(twoLegs, steadyClimb())).toBeCloseTo(1500, 0)
  })

  it('refuses a total for a highlight that leaves the A.T.', () => {
    // The published profile samples the A.T. centerline. Summing only the legs
    // it happens to cover would report a smaller number AS A TOTAL - wrong in
    // the optimistic direction, which FEATURES.md names as the dangerous one.
    const loop = highlight({
      legs: [
        { trail: PROFILED_TRAIL, start_mile: 1, end_mile: 2 },
        { trail: 'Falling Waters Trail', start_mile: 0, end_mile: 3.2 },
      ],
    })
    expect(highlightAscentFt(loop, steadyClimb())).toBeNull()
  })

  it('refuses a total for a leg the profile does not reach', () => {
    // Zero gain over real ground is a claim, not an absence.
    const beyond = highlight({
      legs: [{ trail: PROFILED_TRAIL, start_mile: 500, end_mile: 503 }],
    })
    expect(highlightAscentFt(beyond, steadyClimb())).toBeNull()
  })

  it('refuses a total with no profile on the phone at all', () => {
    expect(highlightAscentFt(highlight(), null)).toBeNull()
  })
})

describe('the derived line', () => {
  it('gives distance, ascent and a Naismith time', () => {
    const detail = buildHighlightDetail(highlight(), steadyClimb(), 'imperial')
    expect(detail.derivedLine).toMatch(/^3\.5 mi · 1,7\d\d ft ascent · ≈/)
  })

  it('always prefixes the time and never shows an arrival clock', () => {
    // WIREFRAMES.md's load-bearing rule for every Naismith estimate.
    const detail = buildHighlightDetail(highlight(), steadyClimb(), 'imperial')
    expect(detail.derivedLine).toContain('≈')
    expect(detail.derivedLine).not.toMatch(/\d{1,2}:\d{2}\s*(am|pm)/i)
  })

  it('shows distance alone where the climbing cannot be measured', () => {
    // The distance comes from the mileposts and is always honest; what is
    // dropped is the climbing and the time, not the whole line.
    const loop = highlight({
      legs: [
        { trail: PROFILED_TRAIL, start_mile: 1, end_mile: 2 },
        { trail: 'Falling Waters Trail', start_mile: 0, end_mile: 3.2 },
      ],
    })
    const detail = buildHighlightDetail(loop, steadyClimb(), 'imperial')
    expect(detail.derivedLine).toBe('4.2 mi')
    expect(detail.derivedLine).not.toContain('ascent')
    expect(detail.derivedLine).not.toContain('≈')
  })

  it('converts with the unit preference, because these are distances', () => {
    const detail = buildHighlightDetail(highlight(), steadyClimb(), 'metric')
    expect(detail.derivedLine).toMatch(/^5\.6 km/)
  })

  it('says the numbers were worked out here, not published', () => {
    const detail = buildHighlightDetail(highlight(), steadyClimb(), 'imperial')
    expect(detail.derivedSourceLine).toBe(
      'Worked out on your phone from the elevation profile.',
    )
  })

  it('claims no profile behind a line the profile did not produce', () => {
    // With the ascent dropped, what is left is a distance summed from the
    // legs' own mileposts. Crediting the elevation profile for it would be
    // provenance for a number it had no part in.
    const loop = highlight({
      legs: [
        { trail: PROFILED_TRAIL, start_mile: 1, end_mile: 2 },
        { trail: 'Falling Waters Trail', start_mile: 0, end_mile: 3.2 },
      ],
    })
    const detail = buildHighlightDetail(loop, steadyClimb(), 'imperial')
    expect(detail.derivedLine).toBe('4.2 mi')
    expect(detail.derivedSourceLine).toBeNull()
  })
})

describe('the subtitle and the legs', () => {
  it('names the trail and the mile range for a single-leg highlight', () => {
    expect(buildHighlightDetail(highlight(), null, 'imperial').subtitle).toBe(
      'Appalachian Trail · mi 10.0 – 13.5',
    )
  })

  it('lists no legs for a single-leg highlight, which would repeat itself', () => {
    expect(buildHighlightDetail(highlight(), null, 'imperial').legLines).toEqual([])
  })

  it('names the one trail rather than counting it, over several legs on it', () => {
    // "1 trails" is not a sentence. No mile range either: the legs have a gap
    // between them, and a range would claim that gap as part of the walk.
    const twoSegments = highlight({
      legs: [
        { trail: PROFILED_TRAIL, start_mile: 1, end_mile: 2 },
        { trail: PROFILED_TRAIL, start_mile: 5, end_mile: 7 },
      ],
    })
    const detail = buildHighlightDetail(twoSegments, null, 'imperial')
    expect(detail.subtitle).toBe('Appalachian Trail · 3.0 mi')
    expect(detail.subtitle).not.toMatch(/\btrails\b/)
  })

  it('leads a cross-trail highlight with how many trails and how far', () => {
    // Mile markers are meaningless across trails - they are different scales -
    // so the subtitle does not try to give a range.
    const loop = highlight({
      legs: [
        { trail: PROFILED_TRAIL, start_mile: 1, end_mile: 2.7 },
        { trail: 'Falling Waters Trail', start_mile: 0, end_mile: 3.2 },
        { trail: 'Old Bridle Path', start_mile: 0, end_mile: 4 },
      ],
    })
    const detail = buildHighlightDetail(loop, null, 'imperial')
    expect(detail.subtitle).toBe('3 trails · 8.9 mi')
    expect(detail.legLines).toEqual([
      'Appalachian Trail — 1.7 mi',
      'Falling Waters Trail — 3.2 mi',
      'Old Bridle Path — 4.0 mi',
    ])
  })
})

/**
 * The basis, in the voice it earns.
 *
 * One basis is shown, never two - lib/highlights.ts's strongestBasis is the
 * rule and this is the wording.
 */
describe('the basis', () => {
  it('says our own list is editorial, in as many words', () => {
    const detail = buildHighlightDetail(highlight(), null, 'imperial')
    expect(detail.basisLabel).toBe('On our list')
    expect(detail.basisLine).toBe(
      'We put this on a list of well-known routes. Editorial, not a measurement.',
    )
  })

  it('attributes a published entry to ATC rather than to us', () => {
    const atc = highlight({
      bases: [NAMED, PUBLISHED],
      citations: {
        [NAMED]: { by: 'OurHike', note: '', reviewed: '2026-08-20' },
        [PUBLISHED]: {
          by: 'Appalachian Trail Conservancy',
          note: '',
          reviewed: '2026-08-04',
        },
      },
    })
    const detail = buildHighlightDetail(atc, null, 'imperial')
    expect(detail.basisLabel).toBe('Listed by ATC')
    expect(detail.citationLine).toBe('Appalachian Trail Conservancy, 4 Aug 2026')
  })

  it('never says "popular", on any basis', () => {
    for (const basis of [NAMED, PUBLISHED, VISITED]) {
      const detail = buildHighlightDetail(
        highlight({ bases: [basis], citations: { [basis]: { by: 'x' } } }),
        null,
        'imperial',
      )
      expect(detail.basisLine).not.toMatch(/popular/i)
    }
  })

  it('never claims the visited basis means where people hike', () => {
    // It measures where hikers USING THIS APP sent something. The wording has
    // to survive somebody reading only this line.
    const detail = buildHighlightDetail(
      highlight({ bases: [VISITED], citations: { [VISITED]: { by: 'OurHike' } } }),
      null,
      'imperial',
    )
    expect(detail.basisLine).toContain('OurHike')
    expect(detail.basisLine).not.toMatch(/most|busiest|popular|best/i)
  })

  it('says nothing at all for a basis it cannot word', () => {
    const detail = buildHighlightDetail(
      highlight({ bases: ['sponsored'] }),
      null,
      'imperial',
    )
    expect(detail.basisLabel).toBeNull()
    expect(detail.basisLine).toBeNull()
  })

  it('gives the citation without a date rather than inventing one', () => {
    const undated = highlight({ citations: { [NAMED]: { by: 'OurHike' } } })
    expect(buildHighlightDetail(undated, null, 'imperial').citationLine).toBe('OurHike')
  })

  it('drops an unparseable date rather than rendering it raw', () => {
    const bad = highlight({
      citations: { [NAMED]: { by: 'OurHike', reviewed: 'last week' } },
    })
    expect(buildHighlightDetail(bad, null, 'imperial').citationLine).toBe('OurHike')
  })
})

describe('the club and what the hiker has walked', () => {
  it('names the maintaining club, which is the thread back to volunteering', () => {
    expect(buildHighlightDetail(highlight(), null, 'imperial').clubLine).toBe(
      'Maintained by RATC.',
    )
  })

  it('says nothing where no club is recorded', () => {
    expect(
      buildHighlightDetail(highlight({ club: null }), null, 'imperial').clubLine,
    ).toBeNull()
  })

  it('reports what this hiker has walked across every leg', () => {
    const walked: MileRange[] = [{ startMile: 10, endMile: 12 }]
    expect(buildHighlightDetail(highlight(), null, 'imperial', walked).walkedLine).toBe(
      'You have walked 2.0 mi of this.',
    )
  })

  it('says nothing when they have walked none of it', () => {
    // This app does not tell anybody how much of the A.T. they have not done.
    expect(buildHighlightDetail(highlight(), null, 'imperial', []).walkedLine).toBeNull()
  })
})

/**
 * #851's hook.
 *
 * Naismith cannot see terrain, and Mahoosuc Arm is already published. Until
 * that issue is decided the field is empty on every record; carrying it means
 * whichever way it goes is a line on a sheet rather than a schema change.
 */
describe('the caution line', () => {
  it('is absent while no record carries one', () => {
    expect(buildHighlightDetail(highlight(), null, 'imperial').cautionLine).toBeNull()
  })

  it('is shown verbatim when a record does', () => {
    const notch = highlight({
      caution: 'The usual estimate does not fit this one — allow considerably longer.',
    })
    expect(buildHighlightDetail(notch, null, 'imperial').cautionLine).toBe(
      'The usual estimate does not fit this one — allow considerably longer.',
    )
  })
})

/**
 * Whose estimate the sheet is printing (#880).
 *
 * The decision on #851 is that no surface may show an adjusted time without
 * showing what it was adjusted from. lib/pace.ts holds the wording; this holds
 * that the sheet actually carries it, and that it stays silent when there is
 * nothing to say.
 */
describe('the pace line', () => {
  const SLOWER: PaceProfile = { ...STANDARD_PACE, flatPaceMph: 2.6 }

  it('is absent on a fresh install, where the pace IS the standard', () => {
    const detail = buildHighlightDetail(highlight(), steadyClimb(), 'imperial', [])
    expect(detail.paceRelativeLine).toBeNull()
  })

  it('defaults to the standard when no pace is passed at all', () => {
    // Every caller that predates this keeps its exact behaviour.
    expect(
      buildHighlightDetail(highlight(), steadyClimb(), 'imperial').paceRelativeLine,
    ).toBeNull()
  })

  it('names the baseline once a hiker has adjusted it', () => {
    const detail = buildHighlightDetail(
      highlight(),
      steadyClimb(),
      'imperial',
      [],
      SLOWER,
    )
    expect(detail.paceRelativeLine).toMatch(/^was ≈.*× standard$/)
  })

  it('moves the time it qualifies, not just the caption', () => {
    // The line would be a lie if the figure above it had not changed.
    const standard = buildHighlightDetail(highlight(), steadyClimb(), 'imperial', [])
    const slower = buildHighlightDetail(
      highlight(),
      steadyClimb(),
      'imperial',
      [],
      SLOWER,
    )
    expect(slower.derivedLine).not.toBe(standard.derivedLine)
    expect(slower.paceRelativeLine).toContain(
      (standard.derivedLine.split('·').pop() as string).trim(),
    )
  })

  it('says nothing where no time is shown at all', () => {
    // A highlight that leaves the A.T. shows distance alone. There is no
    // estimate, so there is nothing to have adjusted - and a pace caption
    // under a bare distance would imply the distance was scaled too.
    const loop = highlight({
      legs: [
        { trail: PROFILED_TRAIL, start_mile: 1, end_mile: 2 },
        { trail: 'Falling Waters Trail', start_mile: 0, end_mile: 3.2 },
      ],
    })
    const detail = buildHighlightDetail(loop, steadyClimb(), 'imperial', [], SLOWER)
    expect(detail.derivedLine).toBe('4.2 mi')
    expect(detail.paceRelativeLine).toBeNull()
  })
})
