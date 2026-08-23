import { describe, it, expect } from 'vitest'
import { OBSERVATION_OPTIONS, NOTE_SCOPED_TYPES, peekObservations } from './fieldNotes'

// The peek's answer set (#941), which is a rule rather than a fourth table -
// and the reason to test it here rather than only through the card is that
// the card only ever renders water. The generalisation to the other three
// types has no other reader.

describe('peekObservations', () => {
  it('carries the pair the design pass drew for water', () => {
    // Flowing and Dry. Everything below is the same rule applied to the types
    // the drawing did not cover, so if this one is wrong the rest are too.
    expect(peekObservations('water').map((option) => option.id)).toEqual([
      'flowing',
      'dry',
    ])
  })

  it('takes the ends of every other scale the same way', () => {
    expect(peekObservations('shelter').map((option) => option.id)).toEqual([
      'fine',
      'full',
    ])
    expect(peekObservations('campsite').map((option) => option.id)).toEqual([
      'fine',
      'full',
    ])
    expect(peekObservations('resupply').map((option) => option.id)).toEqual([
      'open',
      'closed',
    ])
  })

  it('never offers the dispute', () => {
    // `not_found` answers a different question from the three above it, and a
    // dispute filed by a mis-hit on a crowded peek is the claim #876 built
    // corroboration to keep out. It is one tap away in the opened card.
    for (const type of NOTE_SCOPED_TYPES) {
      expect(peekObservations(type).map((option) => option.id)).not.toContain('not_found')
    }
  })

  it('offers two answers for every type the app asks about', () => {
    // A peek that carried one answer would be asking a yes/no question about
    // something that is not one, and a peek that carried three is the row
    // #941's first defect was about.
    for (const type of NOTE_SCOPED_TYPES) {
      expect(peekObservations(type)).toHaveLength(2)
    }
  })

  it('offers only answers the type can actually wear', () => {
    // The pairing lives in OBSERVATION_OPTIONS - the server holds every value
    // in one enum because it has no POI table and cannot police it - so a peek
    // that invented an answer would be filing something the card behind it
    // could not show.
    for (const type of NOTE_SCOPED_TYPES) {
      const allowed = OBSERVATION_OPTIONS[type]
      for (const option of peekObservations(type)) expect(allowed).toContain(option)
    }
  })

  it('has a scale with two ends to read off, for every type', () => {
    // The precondition the two-ends rule rests on, asserted against the table
    // rather than inferred from it. `peekObservations` guards the degenerate
    // case - a scale trimmed to one answer has one end, not two, and would
    // otherwise render the same button twice under one question - and this is
    // what would fail first, and point at that guard, if the table ever
    // shrank far enough to reach it.
    for (const type of NOTE_SCOPED_TYPES) {
      const scale = OBSERVATION_OPTIONS[type].filter(
        (option) => option.id !== 'not_found',
      )
      expect(scale.length).toBeGreaterThanOrEqual(2)
    }
  })
})
