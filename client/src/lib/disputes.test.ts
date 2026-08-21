import { describe, it, expect } from 'vitest'
import { disputeFor, disputeSentence, type DisputeSummary } from './disputes'

// What a hiker reads about a place the field says is not there (#876).
//
// WIREFRAMES.md §11: the visual channel never carries the meaning alone. A
// dashed pin says something is unusual about a place; only these sentences
// say which of two very different things it is - never verified to exist, or
// verified and now gone. Getting that distinction wrong in either direction
// is the failure this file exists to prevent.

const NOW = new Date('2026-08-21T12:00:00Z')
const DAY_MS = 24 * 60 * 60 * 1000

function dispute(over: Partial<DisputeSummary> = {}): DisputeSummary {
  return {
    poi_id: 'atc_shelters:spring-1',
    accounts: 2,
    latest_at: new Date(NOW.getTime() - 4 * DAY_MS).toISOString(),
    maintainer_said: false,
    ...over,
  }
}

describe('what the card says', () => {
  it('prints the sentence FIELD_NOTES.md §4 asks for, in its words', () => {
    expect(disputeSentence(dispute(), NOW)).toBe(
      '2 hikers reported this missing, most recently 4 days ago.',
    )
  })

  it('says nothing at all about a place nobody disputes', () => {
    expect(disputeSentence(null, NOW)).toBeNull()
  })

  it('names a maintainer as a maintainer rather than as a count', () => {
    // The strongest evidence this feature can receive, and flattening it
    // into "1 hiker" would throw it away.
    expect(disputeSentence(dispute({ maintainer_said: true, accounts: 1 }), NOW)).toBe(
      'The maintainer for this stretch reported this missing, 4 days ago.',
    )
  })

  it('hedges a place upstream never confirmed either', () => {
    // §4's carried-over open question, answered in words rather than by
    // withholding the button: a hiker disputing a low-confidence POI may be
    // reporting the data's known weakness rather than a change on the
    // ground, and the card is where that is said.
    const sentence = disputeSentence(dispute(), NOW, { unverified: true })

    expect(sentence).toMatch(/2 hikers reported this missing/)
    expect(sentence).toMatch(/never confirmed to exist/)
  })

  it('counts one account as one hiker, not "1 hikers"', () => {
    expect(disputeSentence(dispute({ accounts: 1 }), NOW)).toMatch(/^1 hiker reported/)
  })

  it('ages today and yesterday in words, like the roll-up does', () => {
    // noteRollup.ts's phrasing, shared deliberately: two surfaces ageing one
    // observation differently is a hiker reading two claims where there is
    // one.
    expect(disputeSentence(dispute({ latest_at: NOW.toISOString() }), NOW)).toMatch(
      /today\.$/,
    )
    expect(
      disputeSentence(
        dispute({ latest_at: new Date(NOW.getTime() - DAY_MS).toISOString() }),
        NOW,
      ),
    ).toMatch(/yesterday\.$/)
  })
})

describe('finding the dispute for a place', () => {
  it('answers null when the working set holds none for it', () => {
    expect(disputeFor([dispute()], 'osm_water:99')).toBeNull()
  })

  it('answers null rather than throwing when nothing was read at all', () => {
    // Null is "we could not ask" - the same distinction every conditions
    // surface keeps (#249). It must not become "nobody disputes this".
    expect(disputeFor(null, 'atc_shelters:spring-1')).toBeNull()
  })

  it('finds the place it was asked about', () => {
    expect(disputeFor([dispute()], 'atc_shelters:spring-1')?.accounts).toBe(2)
  })
})
