import { describe, it, expect } from 'vitest'
import {
  NOTE_SCOPED_TYPES,
  NOTED_OPENERS,
  OBSERVATION_OPTIONS,
  QUICK_ANSWERS,
  escalationFor,
  goodWords,
  observationLabel,
  peekObservations,
  pickGoodWord,
  pickNotedOpener,
} from './fieldNotes'
import { REPORTER_TYPE_VALUES } from './userPreferences'
import { signReportAs } from './reporterIdentity'

// The card's vocabulary (features/FIELD_NOTES.md, features/DATA_NUDGES.md).
//
// Tested here rather than only through the card because the card renders one
// place at a time and most of what is below is a claim about ALL of them - the
// peek pair, the four-answer shape, and the rule every rotating word clears.
// The component's own suite covers what a tap DOES; this covers what a hiker
// is offered.

describe('peekObservations', () => {
  it('carries the pair the design pass drew for water', () => {
    // Flowing and Dry, which is the drawing #941 made and the one pair here
    // that was never in question.
    expect(peekObservations('water').map((option) => option.id)).toEqual([
      'flowing',
      'dry',
    ])
  })

  it('puts the problem a place is usually standing in front of on the peek', () => {
    // #1122's correction. These used to be read off the ENDS of each list, and
    // the ends rule survives only while every list happens to run best to
    // worst. It does not survive `trash`: the ends of a shelter's list are now
    // `fine` and `trash`, so the derived version would hide Problem - the
    // answer this whole change exists to promote - and would hide Full on
    // parking, which is the reason parking is here at all.
    expect(peekObservations('shelter').map((option) => option.id)).toEqual([
      'fine',
      'problem',
    ])
    expect(peekObservations('campsite').map((option) => option.id)).toEqual([
      'fine',
      'problem',
    ])
    expect(peekObservations('resupply').map((option) => option.id)).toEqual([
      'open',
      'closed',
    ])
    expect(peekObservations('parking').map((option) => option.id)).toEqual([
      'open',
      'full',
    ])
  })

  it('never offers the dispute', () => {
    // `not_found` answers a different question from the answers above it, and a
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

  it('hands back the SAME option object the opened card renders', () => {
    // Identity, not equality, and the distinction is the point: the peek's
    // Problem and the opened card's Problem have to be one control with one
    // label and one id. `peekObservations` looks its answers up in
    // OBSERVATION_OPTIONS rather than constructing them, and this is what
    // would fail if somebody "simplified" that into a literal.
    for (const type of NOTE_SCOPED_TYPES) {
      for (const option of peekObservations(type)) {
        expect(OBSERVATION_OPTIONS[type]).toContain(option)
      }
    }
  })

  it('names a good and a problem that the type can actually wear', () => {
    // The guard inside peekObservations is a filter, so a QUICK_ANSWERS entry
    // naming a value its type does not offer would silently produce a ONE
    // button peek rather than an error. This asserts against the table
    // directly, so the failure names the mistyped row instead of the symptom.
    for (const type of NOTE_SCOPED_TYPES) {
      const ids = OBSERVATION_OPTIONS[type].map((option) => option.id)
      expect(ids).toContain(QUICK_ANSWERS[type].good)
      expect(ids).toContain(QUICK_ANSWERS[type].problem)
      expect(QUICK_ANSWERS[type].good).not.toBe(QUICK_ANSWERS[type].problem)
    }
  })
})

describe('the answers each place is offered', () => {
  it('gives every type exactly four, which is what the card has room for', () => {
    // chrome.css lays the answers out two per row inside a 264px card; four is
    // two tidy rows, and five is a ragged one. #941's first defect was four
    // answers squeezed onto ONE row at ~50px each, which is the same
    // constraint pushing from the other side.
    for (const type of NOTE_SCOPED_TYPES) {
      expect(OBSERVATION_OPTIONS[type]).toHaveLength(4)
    }
  })

  it('stops asking a shelter or a campsite whether it is full (#1122)', () => {
    // Capacity is the number this project has already decided it will not
    // claim - a shelter whose capacity nobody stands behind exports none - and
    // a one-tap `full` is that unbacked number wearing a button, arriving
    // dated and attributed.
    for (const type of ['shelter', 'campsite'] as const) {
      expect(OBSERVATION_OPTIONS[type].map((option) => option.id)).not.toContain('full')
    }
  })

  it('keeps `full` where capacity is a fact somebody can see', () => {
    expect(OBSERVATION_OPTIONS.parking.map((option) => option.id)).toContain('full')
  })

  it('ends every list with the dispute', () => {
    // `not_found` describes the absence of a place where the others describe
    // the place, so it sorts last everywhere rather than per-type.
    for (const type of NOTE_SCOPED_TYPES) {
      const options = OBSERVATION_OPTIONS[type]
      expect(options[options.length - 1]?.id).toBe('not_found')
    }
  })

  it('reads a note back in one canonical word, whatever the button said', () => {
    // The counterweight to the rotation below. A button may say "All good" or
    // "Serviceable"; the history list, the roll-up headline and the card's
    // freshness line all print this. A record that read differently on two
    // screens would be one note telling two stories.
    expect(observationLabel('fine')).toBe('Good shape')
    expect(observationLabel('trash')).toBe('Trash')

    // And `full` still reads, because notes filed on shelters before this
    // change still hold it. A word this build no longer OFFERS is not a word
    // it may fail to render.
    expect(observationLabel('full')).toBe('Full')

    // Anything it has genuinely never heard of renders as itself rather than
    // crashing a card.
    expect(observationLabel('somethingelse')).toBe('somethingelse')
  })
})

describe('the good answer’s rotating word', () => {
  // THE RULE, ASSERTED RATHER THAN ONLY COMMENTED: a rotating word is a
  // SYNONYM for the value it files and carries nothing that value does not.
  // Most of it is a judgement no test can make - whether "Snug" claims more
  // than `fine` is a question about English. What IS mechanical is everything
  // below, and it is the part that would rot silently.

  const SIGNED = REPORTER_TYPE_VALUES

  it('offers at least two ways of saying it, for every type and every role', () => {
    // One word is not a rotation, and an empty list is a blank button.
    for (const type of NOTE_SCOPED_TYPES) {
      for (const role of SIGNED) {
        expect(goodWords(type, role).length).toBeGreaterThanOrEqual(2)
      }
    }
  })

  it('never repeats a word inside one list', () => {
    for (const type of NOTE_SCOPED_TYPES) {
      for (const role of SIGNED) {
        const words = goodWords(type, role)
        expect(new Set(words).size).toBe(words.length)
      }
    }
  })

  it('keeps every word inside the peek button’s width', () => {
    // 13 characters is what a 13px semibold label fits in half of a 264px
    // card before it wraps to a second line and the row goes ragged - #941's
    // defect, which this change must not reintroduce by wording. It is a
    // BUDGET rather than a font metric: a word at 14 is a design question and
    // this is what asks it, which it already did once - "Nothing to report"
    // was in the maintainer's list until this test measured it at 17.
    for (const type of NOTE_SCOPED_TYPES) {
      for (const role of SIGNED) {
        for (const word of goodWords(type, role)) {
          expect(word.length).toBeLessThanOrEqual(13)
        }
      }
    }
  })

  it('says the same thing to everybody where the value is already specific', () => {
    // Water, resupply and parking file `flowing` and `open` - values that say
    // one thing - so there is one honest list and only its wording varies.
    // Three lists there would be three chances to let one drift into a
    // stronger claim than the others, which is the failure the rule exists to
    // prevent. Identity rather than equality: they are one array.
    for (const type of ['water', 'resupply', 'parking'] as const) {
      const dealt = SIGNED.map((role) => goodWords(type, role))
      for (const list of dealt) expect(list).toBe(dealt[0])
    }
  })

  it('lets the voice differ only where the value is generic', () => {
    // `fine` is the one value on the board that means "nothing wrong here" and
    // nothing more, so it is the only place a role has room to say it
    // differently - and what differs is HOW SOMEBODY KNOWS, not what they
    // claim. A maintainer inspected it; a day hiker walked past.
    expect(goodWords('shelter', 'maintainer')).not.toBe(goodWords('shelter', 'day'))
    expect(goodWords('shelter', 'maintainer')).toContain('No work due')
    expect(goodWords('shelter', 'day')).toContain('Looks fine')

    // thru and section are one voice: the distinction the app draws between
    // them is about standing in a moderation queue, not about words.
    expect(goodWords('shelter', 'thru')).toBe(goodWords('shelter', 'section'))

    // A shelter and a campsite are asked the same generic question, so they
    // are offered the same generic answers.
    expect(goodWords('campsite', 'thru')).toBe(goodWords('shelter', 'thru'))
  })

  it('deals the day hiker’s words to somebody who never said who they are', () => {
    // Not a fourth list, and not an accident: `signReportAs` already floors an
    // unstated identity to `day` on the argument that under-claiming is the
    // safer error (#233). Reading the vocabulary off the same call is what
    // keeps one answer to "who is this" in the codebase instead of two.
    expect(goodWords('shelter', signReportAs(null))).toBe(goodWords('shelter', 'day'))
  })

  it('reaches every word in the list and never falls off the end', () => {
    // The seam exists for this: a rotation whose only assertion is "it
    // eventually says all four" is a flaky test.
    const words = goodWords('shelter', 'thru')
    for (const [index, word] of words.entries()) {
      expect(pickGoodWord('shelter', 'thru', () => index / words.length)).toBe(word)
    }

    // A generator that returns exactly 1 would index past the end. Math.random
    // cannot, but the seam means something else could, and a blank button is a
    // worse failure than a repeated word.
    expect(words).toContain(pickGoodWord('shelter', 'thru', () => 1))
  })
})

describe('the acknowledgement’s opener', () => {
  it('claims nothing about the place', () => {
    // These rotate freely and carry none of the synonymy rule above, because
    // they are the app talking about ITSELF. That is exactly why they can be
    // playful where the buttons may not be - so the guard worth having is that
    // none of them ever becomes a word about a shelter.
    for (const opener of NOTED_OPENERS) {
      expect(opener.length).toBeLessThanOrEqual(20)
    }
    expect(new Set(NOTED_OPENERS).size).toBe(NOTED_OPENERS.length)
  })

  it('reaches every opener and never falls off the end', () => {
    for (const [index, opener] of NOTED_OPENERS.entries()) {
      expect(pickNotedOpener(() => index / NOTED_OPENERS.length)).toBe(opener)
    }
    expect(NOTED_OPENERS).toContain(pickNotedOpener(() => 1))
  })
})

describe('escalationFor', () => {
  it('sends a named problem straight to the form that names it', () => {
    // `trash` is the same complaint at two weights - one tap that dates the
    // observation, and a form that puts it in front of a maintainer - so it
    // hands off to the report type of the same name rather than the picker.
    expect(escalationFor('trash')).toEqual({ kind: 'form', type: 'trash' })
  })

  it('opens the picker for a problem no report type names', () => {
    // No report type is "a dry spring", and pre-picking a wrong one would file
    // a flooding report about the absence of water.
    expect(escalationFor('dry')).toEqual({ kind: 'pick' })
  })

  it('opens the picker for `problem` too, because the word stopped being narrow', () => {
    // THE HALF OF #1140 THAT IS NOT A LABEL. `damaged` went straight to the
    // `shelter_repair` form, and that was honest: the word promised structural
    // damage, so the form matched what had been tapped. "Problem" covers mice
    // in the food box, a fouled privy, a missing bear hang, a spring that
    // stopped - and a repair form for any of those is the same pre-pick the
    // test above refuses for `dry`.
    //
    // Asserted as `{ kind: 'pick' }` rather than "not shelter_repair", because
    // the failure worth catching is somebody restoring the shortcut for the
    // common case, and `null` would pass a looser assertion while silently
    // dropping the escalation altogether.
    expect(escalationFor('problem')).toEqual({ kind: 'pick' })
  })

  it('stops escalating `full`, which now points at nowhere (#1122)', () => {
    // DATA_NUDGES.md's own sentence was "tapping 'dry' or 'full' prompts 'want
    // to report this?'", and it was written when `full` meant a crowded
    // shelter. `full` is parking-only now, and nothing in the report picker
    // describes a busy lot - so the prompt would be a control teaching a hiker
    // not to trust its labels. What they reach for instead is the report entry
    // the opened card now keeps visible at all times.
    expect(escalationFor('full')).toBeNull()
  })

  it('leaves a good answer alone', () => {
    // The common tap is the whole design: one tap, standing there, and nothing
    // afterwards. An escalation offered on "All good" would turn the cheap
    // interaction into a two-step one.
    expect(escalationFor('fine')).toBeNull()
    expect(escalationFor('flowing')).toBeNull()
    expect(escalationFor('open')).toBeNull()
  })
})
