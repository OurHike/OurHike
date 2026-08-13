import { describe, it, expect } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join, relative, resolve } from 'node:path'

// THE STANDARD, ENFORCED: every unit this app displays is displayed in the
// system the hiker chose (features/UX_CUSTOMIZATION.md, lib/units.ts).
//
// A convention nobody can check is a convention that lasts until the next
// screen. This app already had the preference - `unit_system` has been in the
// model, in the backend's schema and in the sync payload since preferences
// were consolidated - and every one of the eleven places that printed a height
// or a distance printed it in feet and miles anyway. Nothing was broken; there
// was simply nothing to notice, because each of those literals was correct
// where it stood and wrong only when read beside the others.
//
// So the rule is enforced the way src/test/themeTokens.test.ts enforces the
// theme's: as a property of the source, over every file, failing the build on
// the next one rather than on the next bug report. The parallel is exact. A
// stylesheet naming a base colour instead of a semantic token is invisible
// under the light theme and unreadable under the dark one; a component
// formatting its own feet is invisible to an imperial hiker and wrong for
// everybody else. Neither shows up in a component test, because neither is
// a mistake in the component.
//
// WHAT THIS DOES NOT CATCH, said plainly so nobody trusts it further than it
// goes: a component can take `units` and ignore it, and a formatter could be
// handed the wrong quantity. Those are ordinary bugs with ordinary tests. What
// this catches is the one failure that has no natural test - a new screen
// quietly deciding for itself.

const ROOT = resolve(process.cwd(), 'src')

/**
 * The one module allowed to write a unit, and the file you are reading.
 *
 * Everything else goes through lib/units.ts. Kept as a list rather than a
 * regex so that adding an exemption is a visible act with a name on it.
 */
const MAY_WRITE_UNITS = ['lib/units.ts']

/** Every source file the app ships, tests excluded - a test asserting on
 *  "0.2 mi each way" is asserting the formatter's output, which is exactly
 *  what it should be doing. */
function sourceFiles(dir = ROOT): string[] {
  return readdirSync(dir).flatMap((entry) => {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) return sourceFiles(full)
    if (!/\.tsx?$/.test(full)) return []
    if (/\.test\.tsx?$/.test(full)) return []
    if (full.startsWith(join(ROOT, 'test'))) return []
    return [full]
  })
}

/**
 * Source with its comments removed.
 *
 * This repository's comments talk about miles and feet constantly - "398 miles
 * of walking", "the median spur is 385 ft", "1 hour per 600 m of ascent" - and
 * they should. A rule that fired on prose would be turned off within a week,
 * which is the failure mode worth designing against rather than the false
 * positives themselves.
 */
function code(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '')
}

/**
 * A measurement written out longhand: a number, or the end of a `${…}`, then a
 * space, then a unit.
 *
 * The order is what makes this precise rather than merely strict. A formatted
 * measurement puts the unit AFTER the figure - `${gain} ft`, `2.1 mi ahead` -
 * while a mile marker puts it before: `mi ${mile(start)}`, which is a label on
 * a position rather than a unit on a quantity, and which lib/units.ts explains
 * at length is the one thing that does not convert. Matching on the order
 * distinguishes them with no exemption list to maintain, and keeps the
 * exception legible in the code rather than parked in this file.
 */
const WRITTEN_UNIT =
  /[\d}]\s(?:ft|mi|m|km|feet|miles?|metres?|meters?|kilometres?|kilometers?)\b/

describe('the unit display standard', () => {
  it('leaves every unit in the app to lib/units.ts', () => {
    const offenders: string[] = []

    for (const file of sourceFiles()) {
      const name = relative(ROOT, file)
      if (MAY_WRITE_UNITS.includes(name)) continue

      const lines = code(readFileSync(file, 'utf8')).split('\n')
      lines.forEach((line, index) => {
        if (WRITTEN_UNIT.test(line))
          offenders.push(`${name}:${index + 1} — ${line.trim()}`)
      })
    }

    expect(
      offenders,
      'These write a unit into a string. Every height and distance a hiker reads goes through lib/units.ts, so it comes out in the system they chose in Settings.',
    ).toEqual([])
  })

  it('catches the shape it exists to catch, and lets the mile marker through', () => {
    // Guarding the guard. A rule this quiet is worth proving on both sides:
    // the day it stops matching is the day it silently permits everything.
    for (const written of [
      '`+${climb.ascentFt} ft`',
      '`${distance.toFixed(1)} mi ahead`',
      '`about 240 ft from the blazes`',
      '`along 398 miles of trail`',
      '`${gain} m of climbing`',
    ]) {
      expect(WRITTEN_UNIT.test(written), written).toBe(true)
    }

    for (const allowed of [
      // The mile marker: a place on the A.T., not a measurement of anything.
      '`mi ${mile(start)} – ${mile(end)}`',
      '`mi ${poi.mile}`',
      // Bytes are not lengths, and the download sizes have their own module.
      '`${size} MB`',
      // The formatter's own call sites, which is the whole point.
      'formatDistance(distanceAhead, units)',
      'formatElevation(maxFt, units)',
    ]) {
      expect(WRITTEN_UNIT.test(allowed), allowed).toBe(false)
    }
  })
})
