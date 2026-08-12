import { describe, it, expect } from 'vitest'
import {
  ATC_BAND_ID_PREFIX,
  atcBandCandidates,
  atcBandId,
  atcUpdateAsClosure,
  atcUpdateBanner,
  atcUpdateDistanceAhead,
  atcUpdateForBandId,
  nearestAtcUpdate,
  obstructsTheTrail,
  type AtcUpdate,
} from './atcUpdates'
import { closureBanner } from './closureBanner'

// features/ATC_TRAIL_UPDATES.md, #461.
//
// The rule under most of this file is that an ATC notice and an OurHike
// closure must not render identically: OurHike did not verify the ATC's, and
// presenting the second as the first misrepresents the ATC as much as it
// misleads the hiker. So the adapter into `Closure` exists for geometry alone,
// and every string a hiker reads comes off the update itself.
//
// The fixtures are real updates from ATC's page, measured 2026-08-09.

function update(overrides: Partial<AtcUpdate> = {}): AtcUpdate {
  return {
    atc_id: 'va-creeper-trail-closure-detour',
    title: 'SW Virginia: VA Creeper Trail Closure/Detour',
    category: 'Closure',
    states: ['VA'],
    start_mile_marker: 476.6,
    end_mile_marker: 485.8,
    updated_at: '2026-07-17T00:00:00Z',
    source_url: 'https://appalachiantrail.org/trail-updates/va-creeper/',
    ...overrides,
  }
}

describe('which updates become bands', () => {
  it('draws a band for a closure and for a detour', () => {
    expect(obstructsTheTrail(update({ category: 'Closure' }))).toBe(true)
    expect(obstructsTheTrail(update({ category: 'Detour' }))).toBe(true)
  })

  it('draws no band for a notice that does not obstruct the trail', () => {
    // A barred band's sentence is "do not walk down there, go around". A
    // closed car park does not say that, and a barrier that turns out not to
    // be a barrier teaches a hiker that the barriers can be walked past.
    expect(obstructsTheTrail(update({ category: 'Parking' }))).toBe(false)
    expect(obstructsTheTrail(update({ category: 'Alert' }))).toBe(false)
    expect(obstructsTheTrail(update({ category: 'Hiking Safety' }))).toBe(false)
  })

  it('still warns about a notice it will not draw', () => {
    // The suppressed ones keep the banner, exactly as an over-long advisory
    // does. Losing the band must not mean losing the warning.
    const alert = update({ category: 'Alert' })

    expect(atcBandCandidates([alert])).toHaveLength(0)
    expect(atcUpdateBanner(alert, 480, 'NOBO')).not.toBeNull()
  })
})

describe('the adapter into the shared closure shape', () => {
  it('carries the mile range across unchanged', () => {
    const closure = atcUpdateAsClosure(update())

    expect(closure.start_mile_marker).toBe(476.6)
    expect(closure.end_mile_marker).toBe(485.8)
  })

  it('never lets its placeholder reason reach a hiker', () => {
    // `reason_type: 'other'` labels as "Closed". Applied to an ATC Detour
    // that would put a word in their mouth, so nothing may render the
    // adapter's output as text - this test is what would fail if something
    // started to.
    const detour = update({ category: 'Detour' })

    const asClosure = closureBanner(atcUpdateAsClosure(detour), 480, 'NOBO')
    const asAtc = atcUpdateBanner(detour, 480, 'NOBO')

    expect(asClosure).toContain('Trail closed')
    expect(asAtc).not.toContain('Trail closed')
    expect(asAtc).toContain('Detour')
  })

  it('gives a band an id that cannot collide with a closure UUID', () => {
    expect(atcBandId(update())).toBe(
      `${ATC_BAND_ID_PREFIX}va-creeper-trail-closure-detour`,
    )
  })

  it('finds the update a tapped band belongs to', () => {
    const updates = [update(), update({ atc_id: 'other' })]

    expect(atcUpdateForBandId(updates, atcBandId(updates[1]))?.atc_id).toBe('other')
  })

  it('answers null for a band id it does not know', () => {
    // A band from a previous read, tapped after the list refreshed. Null
    // closes the sheet rather than opening someone else's notice.
    expect(atcUpdateForBandId([update()], 'atc:vanished')).toBeNull()
  })
})

describe('the banner, in ATC’s voice', () => {
  it('names the ATC before anything else', () => {
    const line = atcUpdateBanner(update(), 470, 'NOBO')

    expect(line?.startsWith('ATC · ')).toBe(true)
  })

  it('quotes ATC’s own category and headline', () => {
    const line = atcUpdateBanner(update({ category: 'Detour' }), 470, 'NOBO')

    expect(line).toContain('Detour')
    expect(line).toContain('SW Virginia: VA Creeper Trail Closure/Detour')
  })

  it('says how far ahead it is, to a tenth', () => {
    expect(atcUpdateBanner(update(), 470, 'NOBO')).toContain('6.6 mi ahead')
  })

  it('says "here" rather than a distance when the hiker is inside it', () => {
    // "0.0 mi ahead" is a distance pretending to be a place - the same call
    // lib/closureBanner.ts makes.
    const line = atcUpdateBanner(update(), 480, 'NOBO')

    expect(line).toContain('here')
    expect(line).not.toContain('mi ahead')
  })

  it('needs no direction to warn a hiker standing inside it', () => {
    expect(atcUpdateBanner(update(), 480, undefined)).not.toBeNull()
  })

  it('stays silent outside it while the direction is unknown', () => {
    // Guessing would warn half of all hikers about something behind them.
    expect(atcUpdateBanner(update(), 470, undefined)).toBeNull()
  })

  it('stays silent about a notice a hiker has already walked past', () => {
    expect(atcUpdateBanner(update(), 490, 'NOBO')).toBeNull()
    expect(atcUpdateBanner(update(), 470, 'SOBO')).toBeNull()
  })

  it('warns a southbound hiker approaching the far end', () => {
    // The end a SOBO hiker reaches first is `end_mile_marker`. Getting this
    // backwards means silence about the notice they are walking into.
    expect(atcUpdateBanner(update(), 490, 'SOBO')).toContain('4.2 mi ahead')
  })

  it('writes a point notice as one mile rather than a zero-length range', () => {
    const shelter = update({ start_mile_marker: 1503.6, end_mile_marker: 1503.6 })

    expect(atcUpdateBanner(shelter, 1500, 'NOBO')).toContain('mi 1,503.6')
    expect(atcUpdateBanner(shelter, 1500, 'NOBO')).not.toContain('–')
  })
})

describe('picking the nearest', () => {
  it('prefers the one the hiker reaches first', () => {
    const near = update({ atc_id: 'near', start_mile_marker: 480, end_mile_marker: 481 })
    const far = update({ atc_id: 'far', start_mile_marker: 600, end_mile_marker: 601 })

    expect(nearestAtcUpdate([far, near], 470, 'NOBO')?.update.atc_id).toBe('near')
  })

  it('lets one the hiker is standing in win outright', () => {
    const inside = update({
      atc_id: 'inside',
      start_mile_marker: 470,
      end_mile_marker: 480,
    })
    const ahead = update({
      atc_id: 'ahead',
      start_mile_marker: 476,
      end_mile_marker: 477,
    })

    // Both are "ahead" by the raw arithmetic; only one is underfoot.
    expect(nearestAtcUpdate([ahead, inside], 475, 'NOBO')?.update.atc_id).toBe('inside')
  })

  it('answers null when everything is behind', () => {
    expect(nearestAtcUpdate([update()], 490, 'NOBO')).toBeNull()
  })

  it('reports a distance the header can compare against a closure', () => {
    // The whole reason this returns a distance rather than a string: App.tsx
    // has one banner line and two sources competing for it.
    expect(atcUpdateDistanceAhead(update(), 470, 'NOBO')).toBeCloseTo(6.6, 5)
    expect(atcUpdateDistanceAhead(update(), 480, 'NOBO')).toBe(0)
  })
})
