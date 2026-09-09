import { describe, it, expect } from 'vitest'
import {
  ATC_BAND_ID_PREFIX,
  atcBandCandidates,
  atcBandId,
  atcUpdateAsClosure,
  atcUpdateBanner,
  atcUpdateDistanceAhead,
  atcUpdateForBandId,
  atcUpdateLanes,
  isBroadAtcAdvisory,
  isReviewedByAPerson,
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
    obstructs_trail: true,
    updated_at: '2026-07-17T00:00:00Z',
    source_url: 'https://appalachiantrail.org/trail-updates/va-creeper/',
    ...overrides,
  }
}

describe('which updates become bands', () => {
  it('draws a band only where a hiker is actually stopped', () => {
    // A barred band's sentence is "do not walk down there, go around", and a
    // barrier that turns out not to be a barrier teaches a hiker that the
    // barriers can be walked past.
    expect(obstructsTheTrail(update({ obstructs_trail: true }))).toBe(true)
    expect(obstructsTheTrail(update({ obstructs_trail: false }))).toBe(false)
  })

  it('does not read the answer off ATC’s category', () => {
    // The live case that removed the category-based rule, as ATC actually
    // filed it on 2026-08-12: the only notice they call a `Closure` is a
    // closed SHELTER with the trail past it open, while the one thing that
    // genuinely stops a hiker - the way across the Potomac - is a `Detour`.
    // The old rule ("draw `Closure` and `Detour`") was therefore wrong in
    // both directions at once.
    //
    // Written from the live page rather than from memory of it. The first
    // version of this test said both were `Closure`, which is the tidier
    // story and not the one ATC published.
    const shelter = update({
      atc_id: 'connecticut-limestone-spring-shelter-closed',
      category: 'Closure',
      obstructs_trail: false,
    })
    const footbridge = update({
      atc_id: 'harpers-ferry-footbridge-closure',
      category: 'Detour',
      obstructs_trail: true,
    })

    // The `Closure` is the one that does NOT obstruct, which is the whole
    // point: sorting on the category gets both of these backwards.
    expect(obstructsTheTrail(shelter)).toBe(false)
    expect(obstructsTheTrail(footbridge)).toBe(true)
  })

  it('still warns about a notice it will not draw', () => {
    // The undrawn ones keep the banner, exactly as an over-long advisory
    // does. Losing the band must not mean losing the warning.
    const bears = update({ category: 'Alert', obstructs_trail: false })

    expect(atcBandCandidates([bears])).toHaveLength(0)
    expect(atcUpdateBanner(bears, 480, 'NOBO', 'ATC')).not.toBeNull()
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
    const asAtc = atcUpdateBanner(detour, 480, 'NOBO', 'ATC')

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
    const line = atcUpdateBanner(update(), 470, 'NOBO', 'ATC')

    expect(line?.startsWith('ATC · ')).toBe(true)
  })

  it('quotes ATC’s own category and headline', () => {
    const line = atcUpdateBanner(update({ category: 'Detour' }), 470, 'NOBO', 'ATC')

    expect(line).toContain('Detour')
    expect(line).toContain('SW Virginia: VA Creeper Trail Closure/Detour')
  })

  it('says how far ahead it is, to a tenth', () => {
    expect(atcUpdateBanner(update(), 470, 'NOBO', 'ATC')).toContain('6.6 mi ahead')
  })

  it('says it in kilometres for a hiker who chose them, leaving ATC’s range alone', () => {
    // #619. The distance ahead is OurHike's arithmetic on this hiker's
    // position and follows their preference; the mile range is ATC's own
    // published figure, in the units they publish it in, and rewriting their
    // numbers would misquote them as well as move a mile marker.
    const line = atcUpdateBanner(update(), 470, 'NOBO', 'ATC', 'metric')

    expect(line).toContain('10.6 km ahead')
    expect(line).toContain('mi 476.6 – 485.8')
  })

  it('says "here" rather than a distance when the hiker is inside it', () => {
    // "0.0 mi ahead" is a distance pretending to be a place - the same call
    // lib/closureBanner.ts makes.
    const line = atcUpdateBanner(update(), 480, 'NOBO', 'ATC')

    expect(line).toContain('here')
    expect(line).not.toContain('mi ahead')
  })

  it('needs no direction to warn a hiker standing inside it', () => {
    expect(atcUpdateBanner(update(), 480, undefined, 'ATC')).not.toBeNull()
  })

  it('stays silent outside it while the direction is unknown', () => {
    // Guessing would warn half of all hikers about something behind them.
    expect(atcUpdateBanner(update(), 470, undefined, 'ATC')).toBeNull()
  })

  it('stays silent about a notice a hiker has already walked past', () => {
    expect(atcUpdateBanner(update(), 490, 'NOBO', 'ATC')).toBeNull()
    expect(atcUpdateBanner(update(), 470, 'SOBO', 'ATC')).toBeNull()
  })

  it('warns a southbound hiker approaching the far end', () => {
    // The end a SOBO hiker reaches first is `end_mile_marker`. Getting this
    // backwards means silence about the notice they are walking into.
    expect(atcUpdateBanner(update(), 490, 'SOBO', 'ATC')).toContain('4.2 mi ahead')
  })

  it('writes a point notice as one mile rather than a zero-length range', () => {
    const shelter = update({ start_mile_marker: 1503.6, end_mile_marker: 1503.6 })

    expect(atcUpdateBanner(shelter, 1500, 'NOBO', 'ATC')).toContain('mi 1,503.6')
    expect(atcUpdateBanner(shelter, 1500, 'NOBO', 'ATC')).not.toContain('–')
  })
})

describe('picking the nearest', () => {
  it('prefers the one the hiker reaches first', () => {
    const near = update({ atc_id: 'near', start_mile_marker: 480, end_mile_marker: 481 })
    const far = update({ atc_id: 'far', start_mile_marker: 600, end_mile_marker: 601 })

    expect(atcUpdateLanes([far, near], 470, 'NOBO').specific?.update.atc_id).toBe('near')
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
    expect(atcUpdateLanes([ahead, inside], 475, 'NOBO').specific?.update.atc_id).toBe(
      'inside',
    )
  })

  it('answers null when everything is behind', () => {
    expect(atcUpdateLanes([update()], 490, 'NOBO').specific).toBeNull()
  })

  it('reports a distance the header can compare against a closure', () => {
    // The whole reason this returns a distance rather than a string: App.tsx
    // has two sources competing for each line.
    expect(atcUpdateDistanceAhead(update(), 470, 'NOBO')).toBeCloseTo(6.6, 5)
    expect(atcUpdateDistanceAhead(update(), 480, 'NOBO')).toBe(0)
  })
})

// The ATC path is the one #485's case actually travels. Since #461 the Helene
// advisory arrives as an `AtcUpdate` and never as a `Closure`, so a fix confined
// to lib/closureBanner.ts would have left the reported bug in place.
describe('a region-wide ATC advisory', () => {
  const HELENE = update({
    atc_id: 'helene',
    category: 'Alert',
    title: 'Hurricane Helene damage',
    start_mile_marker: 239.4,
    end_mile_marker: 637.8,
  })
  const CREEPER = update({
    atc_id: 'creeper',
    category: 'Closure',
    title: 'Virginia Creeper Trail',
    start_mile_marker: 245,
    end_mile_marker: 254,
  })

  it('is broad by the same ceiling the band uses', () => {
    // Read through the shared `Closure` shape rather than a second number, so
    // the map and the header cannot disagree about which notices are regions.
    expect(isBroadAtcAdvisory(HELENE)).toBe(true)
    expect(isBroadAtcAdvisory(CREEPER)).toBe(false)
  })

  it('leaves the actionable line to the nine-mile closure', () => {
    const lanes = atcUpdateLanes([HELENE, CREEPER], 242, 'NOBO')

    expect(lanes.specific?.update.atc_id).toBe('creeper')
    expect(lanes.broad?.update.atc_id).toBe('helene')
  })

  it('stops saying the notice is "here" when here is 398 miles long', () => {
    const banner = atcUpdateBanner(HELENE, 242, 'NOBO', 'ATC')

    expect(banner).not.toContain('Alert here')
    expect(banner).toContain('ATC · Alert along 398 mi of trail')
    expect(atcUpdateBanner(HELENE, 242, 'NOBO', 'ATC', 'metric')).toContain(
      'ATC · Alert along 641 km of trail',
    )
    // ATC's category and headline stay verbatim - only OurHike's word for WHERE
    // the hiker is has changed.
    expect(banner).toContain('Hurricane Helene damage')
    expect(banner).toContain('mi 239.4 – 637.8')
  })

  it('still says "here" for a notice that is actually here', () => {
    // Five of the seven placeable notices live on 2026-08-12 were a single mile
    // marker, so this is the common case and it must not change.
    const shelter = update({
      category: 'Closure',
      title: 'Shelter closed',
      start_mile_marker: 1503.6,
      end_mile_marker: 1503.6,
    })

    expect(atcUpdateBanner(shelter, 1503.6, 'NOBO', 'ATC')).toContain('Closure here')
  })
})

describe('rows nobody here has read (#963)', () => {
  // The hourly job publishes ATC notices posted since the last human review,
  // through a deliberately narrow gate. What follows is about the half of
  // that which is a UI problem: an unread row must not be rendered in the
  // same voice as one somebody checked.

  it('treats a row with no review_state as reviewed, because older artifacts had none', () => {
    // A deployed client meeting an artifact baked before #963. Every row in
    // one of those was reviewed by definition, so absent has to read as
    // reviewed rather than as unknown - the other way round would relabel
    // every existing notice as unchecked overnight.
    expect(isReviewedByAPerson(update())).toBe(true)
  })

  it('knows an automatic row from a reviewed one', () => {
    expect(isReviewedByAPerson(update({ review_state: 'unreviewed' }))).toBe(false)
    expect(isReviewedByAPerson(update({ review_state: 'reviewed' }))).toBe(true)
  })

  it('says so on the banner, because the position claim is ours and not ATC’s', () => {
    // ATC's category, headline and mile are theirs and need no hedge. "here"
    // is OurHike's, derived from a mile a regex read off their prose.
    const banner = atcUpdateBanner(
      update({ review_state: 'unreviewed' }),
      480,
      'NOBO',
      'ATC',
    )

    expect(banner).toContain('not checked by OurHike')
  })

  it('leaves a reviewed banner alone', () => {
    expect(atcUpdateBanner(update(), 480, 'NOBO', 'ATC')).not.toContain('not checked')
  })

  it('marks an automatic notice a hiker has not reached yet', () => {
    const ahead = update({
      review_state: 'unreviewed',
      start_mile_marker: 500,
      end_mile_marker: 500,
    })

    expect(atcUpdateBanner(ahead, 480, 'NOBO', 'ATC')).toContain('not checked by OurHike')
  })
})
