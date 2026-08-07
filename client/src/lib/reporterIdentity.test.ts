// What a report says about who filed it (#233).
//
// The bug: `reporterType="thru"` was a literal at both call sites, so a day
// hiker, a section hiker and a club maintainer all reached the moderation
// queue as thru-hikers. `reporter_type` is the one attribution that survives
// HIKER_SAFETY.md §2's anonymity window, so it is the one a maintainer weighs
// a report by - and a field that says the same thing about everybody weighs
// nothing.

import { describe, it, expect } from 'vitest'
import {
  hasStatedReporterType,
  signReportAs,
  UNSTATED_REPORTER_TYPE,
} from './reporterIdentity'
import { REPORTER_TYPE_VALUES } from './userPreferences'

describe('signReportAs', () => {
  it('signs with what the hiker actually chose', () => {
    for (const stated of REPORTER_TYPE_VALUES) {
      expect(signReportAs(stated)).toBe(stated)
    }
  })

  it('never invents a thru-hiker for someone who has not said', () => {
    // The regression this exists to prevent, named as itself: the fallback
    // must not be the strongest claim, whatever else it is.
    expect(signReportAs(null)).not.toBe('thru')
  })

  it('falls back to the weakest claim, which is a day hiker', () => {
    // `Report.reporter_type` is non-nullable with no "unstated" member, so
    // something has to be sent. Under-claiming is the safer error: a real
    // thru-hiker weighed as a day hiker loses one report's standing and fixes
    // it by answering the screen; a fabricated thru-hiker is trusted.
    expect(signReportAs(null)).toBe('day')
    expect(UNSTATED_REPORTER_TYPE).toBe('day')
  })

  it('only ever returns a type the contract accepts', () => {
    for (const stored of [...REPORTER_TYPE_VALUES, null]) {
      expect(REPORTER_TYPE_VALUES).toContain(signReportAs(stored))
    }
  })
})

describe('hasStatedReporterType', () => {
  it('is false only before the hiker has answered', () => {
    expect(hasStatedReporterType(null)).toBe(false)
    for (const stated of REPORTER_TYPE_VALUES) {
      expect(hasStatedReporterType(stated)).toBe(true)
    }
  })

  it('does not confuse a real day hiker with an unanswered one', () => {
    // The reason this is a separate function rather than `=== 'day'` at the
    // call sites: the fallback VALUE and the fact that nobody chose it are
    // different facts, and reading one for the other would ask a genuine day
    // hiker the same question on every report they file.
    expect(hasStatedReporterType('day')).toBe(true)
    expect(signReportAs('day')).toBe(signReportAs(null))
  })
})
