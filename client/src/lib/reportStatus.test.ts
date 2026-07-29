import { describe, it, expect } from 'vitest'
import { REPORT_STATE_WORDS, reportStateFor, isPenalised } from './reportStatus'

// WIREFRAMES.md line 184 lists "the four report states' exact words" among the
// load-bearing values: Waiting, Confirmed, Fixed, Not confirmed. They are the
// only feedback a reporter ever gets, so the wording is the feature.
//
// The backend's enum uses different words (submitted / verified / resolved /
// dismissed) because it is describing a moderation queue. This module is the
// one place that translation happens.
//
// "Not confirmed" carrying NO penalty is an explicit product decision
// (WIREFRAMES.md §6: "carries no penalty, deliberately"). Someone who reports
// a blowdown that a maintainer cannot find has done nothing wrong, and an app
// that makes them feel otherwise gets fewer reports next time.

describe('reportStateFor', () => {
  it.each([
    ['submitted', 'Waiting'],
    ['verified', 'Confirmed'],
    ['resolved', 'Fixed'],
    ['dismissed', 'Not confirmed'],
  ] as const)('shows a %s report to its reporter as "%s"', (status, word) => {
    expect(reportStateFor(status)).toBe(word)
  })

  it('covers every backend status - an unmapped one would render blank', () => {
    expect(Object.keys(REPORT_STATE_WORDS).sort()).toEqual([
      'dismissed',
      'resolved',
      'submitted',
      'verified',
    ])
  })

  it('uses exactly the four words WIREFRAMES.md pins, and no others', () => {
    expect(Object.values(REPORT_STATE_WORDS).sort()).toEqual([
      'Confirmed',
      'Fixed',
      'Not confirmed',
      'Waiting',
    ])
  })

  it('never says "rejected", "denied" or "invalid" about a dismissed report', () => {
    // The reporter did not fail at anything; a moderator simply could not
    // confirm it. Blame-shaped wording here costs future reports.
    const words = Object.values(REPORT_STATE_WORDS).join(' ').toLowerCase()

    expect(words).not.toMatch(/reject|denied|invalid|failed|wrong/)
  })
})

describe('isPenalised', () => {
  it.each(['submitted', 'verified', 'resolved', 'dismissed'] as const)(
    'never penalises the reporter, including for %s',
    (status) => {
      expect(isPenalised(status)).toBe(false)
    },
  )
})
