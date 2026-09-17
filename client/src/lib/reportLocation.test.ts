import { describe, it, expect } from 'vitest'
import {
  AT_THE_FIX,
  NEARBY_LIMIT,
  NEARBY_WITHIN_MILES,
  STALE_FIX_SECONDS,
  chosenMile,
  fixAgeSeconds,
  fixAgeWords,
  fixWords,
  hasPlace,
  locationWords,
  nearbyPlaces,
  placesByName,
  reportLocationFields,
  type FixSnapshot,
  type PlaceCandidate,
} from './reportLocation'

// The one module every report surface now places a report through (#1563).
// The load-bearing properties, in the order they would hurt somebody:
//
//   - a report with no fix and no place carries no coordinates at all,
//     never 0,0 and never a pin made of the hiker's words
//   - a report at the fix carries the radius and the age the phone knew
//   - a named place carries its id AND its coordinates
//   - the mile is omitted, never zeroed, wherever it is unknown

const NOW = new Date('2026-09-17T14:00:00Z')

const FIX: FixSnapshot = {
  lat: 35.6,
  lon: -83.5,
  mile: 1043.2,
  accuracyM: 4.87,
  fixedAt: new Date('2026-09-17T13:59:30Z'),
}

const SHELTER: PlaceCandidate = {
  id: 'atc_shelters:12',
  name: 'Bailey Gap Shelter',
  type: 'shelter',
  mile: 628.4,
  lat: 37.4,
  lon: -80.4,
}

describe('what the wire carries', () => {
  it('sends a waypoint as its id, its coordinates, its mile and location_source poi', () => {
    expect(
      reportLocationFields(
        {
          kind: 'poi',
          poiId: SHELTER.id,
          name: SHELTER.name,
          lat: 37.4,
          lon: -80.4,
          mile: 628.4,
        },
        FIX,
        NOW,
      ),
    ).toEqual({
      poi_id: 'atc_shelters:12',
      lat: 37.4,
      lon: -80.4,
      mile: 628.4,
      location_source: 'poi',
    })
  })

  it('sends the fix with location_source gps, the radius to a tenth, and the age in seconds', () => {
    expect(reportLocationFields(AT_THE_FIX, FIX, NOW)).toEqual({
      lat: 35.6,
      lon: -83.5,
      mile: 1043.2,
      location_source: 'gps',
      location_accuracy_m: 4.9,
      location_fix_age_s: 30,
    })
  })

  it('sends a marked spot with location_source map and no radius', () => {
    const fields = reportLocationFields(
      { kind: 'point', lat: 36.1, lon: -81.7 },
      FIX,
      NOW,
    )

    expect(fields).toEqual({ lat: 36.1, lon: -81.7, location_source: 'map' })
    expect('location_accuracy_m' in fields).toBe(false)
    expect('mile' in fields).toBe(false)
  })

  it('sends NOTHING - not 0,0, not mile 0 - for the fix when there is no fix', () => {
    // 0,0 is the Atlantic off West Africa and mi 0.0 is Springer Mountain;
    // both are confident, checkable-looking answers, which is what makes them
    // worse than an absent one.
    expect(reportLocationFields(AT_THE_FIX, null, NOW)).toEqual({})
  })

  it("sends the hiker's words, and only the words, when there is no fix", () => {
    // Prose, never turned into a pin: a typed name geocoded into coordinates
    // is a confident wrong dot on every phone that downloads the report.
    const fields = reportLocationFields(AT_THE_FIX, null, NOW, '  north of the gap  ')

    expect(fields).toEqual({ place_words: 'north of the gap' })
  })

  it('drops the words once a place is known - they described a report that now has one', () => {
    expect(
      'place_words' in reportLocationFields(AT_THE_FIX, FIX, NOW, 'north of the gap'),
    ).toBe(false)
  })

  it('omits the mile rather than zeroing it when the fix is off the corridor', () => {
    const { mile: _unplaced, ...offCorridor } = FIX
    const fields = reportLocationFields(AT_THE_FIX, offCorridor, NOW)

    expect('mile' in fields).toBe(false)
    expect(fields.lat).toBe(35.6)
  })

  it('floors the age at zero when the fix is stamped after the report', () => {
    const early = new Date(FIX.fixedAt.getTime() - 5_000)
    expect(reportLocationFields(AT_THE_FIX, FIX, early).location_fix_age_s).toBe(0)
    expect(fixAgeSeconds(FIX.fixedAt, early)).toBe(0)
  })
})

describe('the mile a choice resolves to', () => {
  it('is the place’s own mile, the fix’s snapped mile, and null off the corridor', () => {
    expect(
      chosenMile(
        { kind: 'poi', poiId: 'x', name: 'X', lat: 1, lon: 1, mile: 12.5 },
        null,
      ),
    ).toBe(12.5)
    expect(chosenMile({ kind: 'point', lat: 1, lon: 1 }, FIX)).toBeNull()
    expect(chosenMile(AT_THE_FIX, FIX)).toBe(1043.2)
    expect(chosenMile(AT_THE_FIX, null)).toBeNull()
  })
})

describe('whether a choice gives the report a place', () => {
  it('always does for a waypoint or a marked spot, and for the fix only while there is one', () => {
    expect(hasPlace({ kind: 'point', lat: 1, lon: 1 }, null)).toBe(true)
    expect(hasPlace({ kind: 'poi', poiId: 'x', name: 'X', lat: 1, lon: 1 }, null)).toBe(
      true,
    )
    expect(hasPlace(AT_THE_FIX, FIX)).toBe(true)
    expect(hasPlace(AT_THE_FIX, null)).toBe(false)
  })
})

describe('how a place reads', () => {
  it('names a waypoint, and says it is a named place at its mile', () => {
    const words = locationWords(
      {
        kind: 'poi',
        poiId: SHELTER.id,
        name: SHELTER.name,
        lat: 37.4,
        lon: -80.4,
        mile: 628.4,
      },
      FIX,
      'imperial',
      true,
      NOW,
    )

    expect(words).toEqual({
      label: 'Bailey Gap Shelter',
      phrase: 'at Bailey Gap Shelter',
      detail: 'A named place · mi 628.4',
    })
  })

  it('prints the fix as its mile, with the radius in the units the hiker chose and the age', () => {
    expect(locationWords(AT_THE_FIX, FIX, 'imperial', true, NOW)).toEqual({
      label: 'mi 1,043.2',
      phrase: 'at mi 1,043.2',
      detail: 'Your position · ±16 ft · just now',
    })
    expect(locationWords(AT_THE_FIX, FIX, 'metric', true, NOW).detail).toBe(
      'Your position · ±5 m · just now',
    )
  })

  it('says "here" for a fix with no mile, never "at here"', () => {
    const { mile: _unplaced, ...offCorridor } = FIX
    const words = locationWords(AT_THE_FIX, offCorridor, 'imperial', true, NOW)

    expect(words.label).toBe('Where you are')
    expect(words.phrase).toBe('here')
  })

  it('warns when the fix is older than STALE_FIX_SECONDS', () => {
    const stale: FixSnapshot = {
      ...FIX,
      fixedAt: new Date(NOW.getTime() - (STALE_FIX_SECONDS + 60) * 1000),
    }

    expect(fixWords(stale, 'imperial', NOW)).toBe(
      '±16 ft · 6 min ago — you may have moved since',
    )
    expect(fixWords(FIX, 'imperial', NOW)).not.toContain('moved')
  })

  it('writes the age coarsely: just now, minutes, then hours', () => {
    const at = (secondsAgo: number) => new Date(NOW.getTime() - secondsAgo * 1000)
    expect(fixAgeWords(at(59), NOW)).toBe('just now')
    expect(fixAgeWords(at(60), NOW)).toBe('1 min ago')
    expect(fixAgeWords(at(59 * 60), NOW)).toBe('59 min ago')
    expect(fixAgeWords(at(3 * 3600 + 5), NOW)).toBe('3 hr ago')
  })

  it('gives a marked spot the three placement answers and never a borrowed mile', () => {
    // lib/placement.ts's three: a mile, "This spot" with no trail index, and
    // more than 3 mi off the trail when the index refused the point. The
    // hiker's own mile (FIX.mile) must not leak into any of them - a press
    // two miles up the trail is not at mi 1,043.2.
    expect(
      locationWords(
        { kind: 'point', lat: 1, lon: 1, mile: 630 },
        FIX,
        'imperial',
        true,
        NOW,
      ),
    ).toEqual({ label: 'mi 630.0', phrase: 'at mi 630.0', detail: 'Marked on the map' })
    expect(
      locationWords({ kind: 'point', lat: 1, lon: 1 }, FIX, 'imperial', false, NOW),
    ).toEqual({
      label: 'This spot',
      phrase: 'at the spot you marked',
      detail: 'Marked on the map',
    })
    expect(
      locationWords({ kind: 'point', lat: 1, lon: 1 }, FIX, 'imperial', true, NOW).label,
    ).toBe('More than 3 mi off the trail')
  })

  it('says "No location yet" with no fix and no words, and "In your words" with words', () => {
    expect(locationWords(AT_THE_FIX, null, 'imperial', true, NOW)).toEqual({
      label: 'No location yet',
      phrase: 'here',
      detail: null,
    })
    expect(
      locationWords(AT_THE_FIX, null, 'imperial', true, NOW, 'by the brook'),
    ).toEqual({
      label: 'In your words',
      phrase: 'where you described',
      detail: null,
    })
  })
})

describe('the named places worth offering', () => {
  /** Places along a north-south line, `milesNorth` of the reference. */
  const reference = { lat: 37.0, lon: -80.0 }
  const place = (id: string, milesNorth: number, name = id): PlaceCandidate => ({
    id,
    name,
    type: 'water',
    lat: 37.0 + milesNorth / 69.05,
    lon: -80.0,
  })

  it('offers what is within NEARBY_WITHIN_MILES, nearest first, and drops the rest', () => {
    const rows = nearbyPlaces(
      [place('far', NEARBY_WITHIN_MILES + 0.5), place('near', 0.2), place('mid', 1.1)],
      reference,
    )

    expect(rows.map((row) => row.id)).toEqual(['near', 'mid'])
    expect(rows[0]?.awayMiles).toBeCloseTo(0.2, 1)
  })

  it('keeps a place walked past today at any distance', () => {
    const rows = nearbyPlaces(
      [place('far', 9), place('near', 0.2)],
      reference,
      new Set(['far']),
    )

    expect(rows.map((row) => row.id)).toEqual(['near', 'far'])
    expect(rows[1]?.awayMiles).toBeCloseTo(9, 0)
  })

  it('with no reference point offers only the passed places, in name order, with no distance', () => {
    const rows = nearbyPlaces(
      [
        place('b', 0.1, 'Wide Spring'),
        place('a', 0.1, 'Bailey Gap Shelter'),
        place('c', 0.1),
      ],
      null,
      new Set(['a', 'b']),
    )

    expect(rows.map((row) => row.name)).toEqual(['Bailey Gap Shelter', 'Wide Spring'])
    expect(rows.every((row) => row.awayMiles === null)).toBe(true)
  })

  it('stops at NEARBY_LIMIT rows', () => {
    const many = Array.from({ length: NEARBY_LIMIT + 4 }, (_, i) =>
      place(`p${i}`, i * 0.05),
    )

    expect(nearbyPlaces(many, reference)).toHaveLength(NEARBY_LIMIT)
  })

  it('finds a place by name the way search does, nearest match first', () => {
    const rows = placesByName(
      'spring',
      [
        place('far', 5, 'Far Spring'),
        place('near', 0.3, 'Near Spring'),
        place('x', 0.1, 'Shelter'),
      ],
      reference,
    )

    expect(rows.map((row) => row.id)).toEqual(['near', 'far'])
  })

  it('answers an empty query with nothing rather than every waypoint on the trail', () => {
    expect(placesByName('   ', [place('a', 0.1)], reference)).toEqual([])
  })
})
