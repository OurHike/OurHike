import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'

// THE STANDARD, ENFORCED: no screen prints a pace-adjusted time without also
// showing what it was adjusted from (#851, #880).
//
// The decision is the maintainer's, recorded on #851: "We should always
// display how their setting relates to Naismith." The hazard it answers is a
// hiker who set their pace optimistic in week one and forgot - an estimate
// reading low is somebody planning to be somewhere before dark that they reach
// after it.
//
// lib/pace.ts holds the rule at the TYPE level: `paceEstimate()` returns the
// adjusted `text` and its `relativeLine` in one object, so a caller with the
// figure in hand necessarily has the baseline too. That is the guarantee, and
// it has exactly one hole: a surface that calls `paceMinutes()` and formats
// the result itself, bypassing the bundle. Nothing stops that at the type
// level, because both halves are legitimately exported - route.ts needs raw
// minutes to sum a day before formatting once.
//
// So this scans for the bypass. It is the same shape as
// test/unitDisplay.test.ts, and for the same reason: a convention nobody can
// check is a convention that lasts until the next screen.

const ROOT = resolve(process.cwd(), 'src')

/**
 * The files allowed to turn pace minutes into a string, and the file you are
 * reading.
 *
 * `lib/pace.ts` is where the bundle is built. `lib/pace.test.ts` exercises the
 * pieces separately, which is its job. This file names both literals in order
 * to search for them, and flagged ITSELF on the first run - which is the
 * cheapest possible evidence that the scan works.
 *
 * A list rather than a pattern, so adding one is a visible act with a name on
 * it and a reviewer to answer to.
 */
const MAY_FORMAT_PACE_MINUTES = [
  'lib/pace.ts',
  'lib/pace.test.ts',
  'test/paceBaseline.test.ts',
]

/** The escape hatch and its toll: `pace-baseline-exempt #N`, on the line. */
const EXEMPTION = /pace-baseline-exempt #(\d+)/

function sourceFiles(dir = ROOT): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry)
    return statSync(full).isDirectory()
      ? sourceFiles(full)
      : /\.tsx?$/.test(entry)
        ? [full]
        : []
  })
}

describe('the pace baseline standard', () => {
  it('lets nothing but lib/pace.ts format a pace-adjusted time', () => {
    const offenders: string[] = []
    const excused: string[] = []

    for (const file of sourceFiles()) {
      const name = relative(ROOT, file)
      if (MAY_FORMAT_PACE_MINUTES.includes(name)) continue

      const source = readFileSync(file, 'utf8')
      // Only files that touch the personal estimator at all can offend.
      if (!source.includes('paceMinutes')) continue

      source.split('\n').forEach((line, index) => {
        if (!line.includes('formatNaismithMinutes')) return
        const excuse = EXEMPTION.exec(line)
        if (excuse === null) offenders.push(`${name}:${index + 1} — ${line.trim()}`)
        else excused.push(`${name} #${excuse[1]}`)
      })
    }

    expect(
      offenders,
      'These format a pace-adjusted time by hand. Use paceEstimate(), which ' +
        'returns the figure and its baseline together so a screen cannot show ' +
        'one without the other (#851). If a surface genuinely must format its ' +
        'own - a running total across legs, say - mark the line ' +
        '`pace-baseline-exempt #N` against an issue that will close it, and ' +
        'render the baseline yourself.',
    ).toEqual([])

    // The debt, pinned rather than merely permitted. Nothing is excused today,
    // and an empty list is what stops the hatch quietly becoming the way past
    // the rule.
    expect(excused).toEqual([])
  })

  it('is a guard that can actually fire', () => {
    // The failure mode this whole file exists to avoid: a scanner that finds
    // no files, passes, and is believed. If lib/pace.ts is ever renamed, this
    // fails rather than going quiet.
    const files = sourceFiles()
    expect(files.length).toBeGreaterThan(50)
    expect(files.some((f) => relative(ROOT, f) === 'lib/pace.ts')).toBe(true)
    expect(
      files.filter((f) => readFileSync(f, 'utf8').includes('paceMinutes')).length,
    ).toBeGreaterThan(0)
  })
})
