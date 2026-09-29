// The launch-budget verdict (scripts/check-launch-speed.mjs), and the third
// answer #1488 added to it.
//
// "never reached" used to be the only thing a missing mark could mean, so a
// deployed build that predates a mark read exactly like a launch that never
// got there - five days of it on #1376. These hold that the two are now told
// apart, and only on evidence: the stopwatch has to have read the bundle and
// found the name missing, or the row stays on the loud side.

import { describe, expect, it } from 'vitest'

import { judge } from '../../scripts/check-launch-speed.mjs'

const NOW = new Date('2026-09-25T09:45:00Z')

/** A returning launch with every row inside its budget, before overrides. */
const run = (overrides: Record<string, unknown> = {}) => ({
  url: 'https://ourhike.org/app/',
  mode: 'returning',
  marks: { 'tab bar rendered': 480 },
  taps: [{ accepted_ms: 223 }],
  longest_task_ms: 300,
  total_blocking_ms: 540,
  ...overrides,
})

const shellRow = (verdict: ReturnType<typeof judge>) =>
  verdict.rows.find((row: { check: string }) => row.check === 'shell_frame')

describe('judge', () => {
  it('passes a launch whose every row is inside its budget', () => {
    const verdict = judge(run(), NOW)
    expect(verdict.failed).toEqual([])
    expect(verdict.not_in_build).toEqual([])
    expect(verdict.checked_at).toBe('2026-09-25 09:45 UTC')
  })

  it('still calls a declared mark that never fired "never reached", and over', () => {
    const verdict = judge(
      run({
        marks: { 'tab bar rendered': null },
        declared_marks: { 'tab bar rendered': true },
      }),
      NOW,
    )
    expect(shellRow(verdict)).toMatchObject({ over: true, reason: 'never reached' })
    expect(verdict.failed.map((row: { check: string }) => row.check)).toEqual([
      'shell_frame',
    ])
  })

  it('calls a mark the deployed bundle does not declare "not in this build", and not over (#1488)', () => {
    // v1.2.2 on 2026-09-10: no `ourhike:shell` anywhere in the bundle, and a
    // first tap on the tab bar at 223 ms.
    const verdict = judge(
      run({
        marks: { 'tab bar rendered': null },
        declared_marks: { 'tab bar rendered': false },
      }),
      NOW,
    )
    expect(shellRow(verdict)).toMatchObject({ over: false, reason: 'not in this build' })
    expect(verdict.failed).toEqual([])
    expect(verdict.not_in_build.map((row: { check: string }) => row.check)).toEqual([
      'shell_frame',
    ])
  })

  it('falls to "never reached" when the stopwatch could not read the bundle, or is older than the field', () => {
    for (const declared of [null, undefined]) {
      const verdict = judge(
        run({ marks: { 'tab bar rendered': null }, declared_marks: declared }),
        NOW,
      )
      expect(shellRow(verdict)).toMatchObject({ over: true, reason: 'never reached' })
    }
  })

  it('never lets "not in this build" excuse a row that has a number', () => {
    const verdict = judge(
      run({
        marks: { 'tab bar rendered': 2400 },
        declared_marks: { 'tab bar rendered': false },
      }),
      NOW,
    )
    expect(shellRow(verdict)).toMatchObject({ over: true, reason: null })
  })
})
