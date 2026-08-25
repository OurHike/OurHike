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
// goes: a component can take `units` and ignore it. What this catches is the
// one failure that has no natural test - a new screen quietly deciding for
// itself.
//
// "A formatter could be handed the wrong quantity" used to be on that list
// too, left to ordinary tests. It happened (#986): a route point's map label
// ran `stop.mile` through `formatDistance`, so a metric hiker's map named a
// place "757.7 km" while the row beside it called the same place "mi 470.8" -
// and "5.1" or "757.7" is itself a valid marker naming somewhere else on the
// trail, so the number was not merely odd, it was a position claim that
// resolved wrong. lib/units.ts's header had spelled the rule out, with that
// exact example, in the file the call imported from.
//
// So MARKER_INTO_FORMATTER below catches the one shape of it a scanner can
// see honestly: a bare `.mile` handed straight to a units formatter. It works
// because the two quantities are written differently everywhere in this
// codebase - a MARKER is `stop.mile`, and a DISTANCE is a difference of two
// (`Math.abs(a.mile - b.mile)`) or a field that says so (`distanceMi`). It
// cannot see a marker that arrived through a variable, and does not pretend
// to.
//
// AND WHAT THE SCANNER ITSELF CANNOT SEE (#657's audit found this, and the
// gap matters more than the individual lines it names, because a ledger
// believed to be complete is worse than one known to be partial):
//
//   - **A unit with no number in front of it.** `WRITTEN_UNIT` matches a
//     figure THEN a unit, which is what makes it precise about mile markers -
//     and it means a bare `'m'` is invisible. `map/liveTopo.ts:1036,1058`
//     write exactly that: the contour and peak label expressions end
//     `units === 'imperial' ? "'" : 'm'`. **Those two are correct** - the
//     values are already per-unit, so the suffix only says which system the
//     number is in - but they are correct by inspection rather than because
//     this guard checked them, and `MAY_WRITE_UNITS` below has never named
//     them. Deliberately NOT added to that list: excusing the whole file
//     would stop this scanner reading the rest of it, and the rest of it is
//     ordinary code.
//   - **Concatenation and variables.** `'ft'` assigned to a constant, or
//     built with `+`, passes. Only the inline template form is matched.
//   - **Anything outside `src/`**, and anything a dependency renders for
//     itself. MapLibre's `ScaleControl` writes its own "mi"/"km" inside the
//     library (`map/mapChrome.ts` passes it `unit: units`, so the hiker's
//     choice IS honoured - but no string in this repository says so).
//
// Widening the regex to cover the first two was considered and not done: a
// pattern loose enough to catch a bare `'m'` matches every `m` in the
// codebase, and a guard that cries wolf is a guard people delete. The honest
// answer is this paragraph rather than a rule nobody can keep.

const ROOT = resolve(process.cwd(), 'src')

/**
 * The one module allowed to write a unit, and the file you are reading.
 *
 * Everything else goes through lib/units.ts. Kept as a list rather than a
 * regex so that adding an exemption is a visible act with a name on it.
 */
const MAY_WRITE_UNITS = ['lib/units.ts']

/**
 * The escape hatch, and the toll it charges: `units-exempt #N`, on the line.
 *
 * There is exactly one thing this is for - a number the app displays that it
 * does not own, so that converting the app's copy would make one card
 * disagree with itself. #625 was the standing case and is now closed: the
 * pipeline composed a shelter's "Nearby: a privy 40 m away" into published
 * prose, and #526's chips under it printed the same distances from the same
 * equirectangular maths, so converting the chips alone would have read
 * `Privy · 130 ft` above a sentence saying 40 m. The fix was to stop
 * publishing the sentence: `pipeline/lib/poi_description.py` publishes the
 * parts and `lib/nearbyClause.ts` writes the words, so both halves now answer
 * the hiker.
 *
 * Nothing is exempt today, which is the state this hatch exists to make
 * conspicuous rather than comfortable. The issue number is REQUIRED, and that
 * is the whole design. An exemption with a number is a debt somebody can find,
 * count and close; an exemption without one is the standard quietly ending. A
 * bare `units-exempt` fails this file as loudly as the unit it was trying to
 * excuse.
 */
const EXEMPTION = /units-exempt #(\d+)/

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
  return source
    .replace(/\/\*[\s\S]*?\*\//g, (block) => '\n'.repeat(countNewlines(block)))
    .replace(/^\s*\/\/.*$/gm, '')
}

/** Block comments collapse to their own newlines rather than to nothing, so a
 *  reported line number still points at the line. A guard that names the wrong
 *  line sends somebody hunting, which is most of the cost of a rule like this
 *  firing at all. */
function countNewlines(text: string): number {
  return text.split('\n').length - 1
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

/**
 * A mile MARKER handed to a units formatter (#986).
 *
 * Matches `formatDistance(x.mile` / `formatElevation(x.mile` and the range
 * form - a bare member access ending in `.mile`, with no arithmetic around
 * it. Arithmetic is what makes a distance out of two markers, so requiring
 * its absence is what keeps this precise rather than noisy: every legitimate
 * call in the tree today passes a difference or a `…Mi` field.
 */
const MARKER_INTO_FORMATTER =
  /format(?:Distance|DistanceRange|Elevation)\(\s*[A-Za-z_$][\w$]*(?:[.?]\[?[\w$]+\]?)*\.mile\s*[,)]/

describe('the unit display standard', () => {
  it('leaves every unit in the app to lib/units.ts', () => {
    const offenders: string[] = []
    const excused: string[] = []

    for (const file of sourceFiles()) {
      const name = relative(ROOT, file)
      if (MAY_WRITE_UNITS.includes(name)) continue

      const lines = code(readFileSync(file, 'utf8')).split('\n')
      lines.forEach((line, index) => {
        if (!WRITTEN_UNIT.test(line)) return
        const excuse = EXEMPTION.exec(line)
        // An offender needs a location to go and fix. An excused line needs
        // only its name and its issue: pinning its line number too would put
        // this assertion in the way of every edit made above it, which is how
        // a guard earns a reputation for crying wolf.
        if (excuse === null) offenders.push(`${name}:${index + 1} — ${line.trim()}`)
        else excused.push(`${name} #${excuse[1]}`)
      })
    }

    expect(
      offenders,
      'These write a unit into a string. Every height and distance a hiker reads goes through lib/units.ts, so it comes out in the system they chose in Settings. If this one genuinely cannot - the app does not own the number, and converting its copy would make a card disagree with itself - mark the line `units-exempt #N` against an issue that will close it.',
    ).toEqual([])

    // The debt, asserted rather than merely permitted. NOTHING is excused
    // today - #625 closed the one line that was - and pinning the empty list
    // is what stops the hatch becoming the way past the rule: the first
    // exemption is a decision somebody has to make on purpose, in this file,
    // in front of a reviewer.
    expect(excused).toEqual([])
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

  it('never hands a mile MARKER to a units formatter (#986)', () => {
    const offenders: string[] = []

    for (const file of sourceFiles()) {
      const name = relative(ROOT, file)
      const text = code(readFileSync(file, 'utf8'))
      // Whole-file rather than line-by-line: a formatter call wraps across
      // lines as often as not, and this pattern has to survive prettier
      // deciding where to break it.
      const flat = text.replace(/\s+/g, ' ')
      if (MARKER_INTO_FORMATTER.test(flat)) offenders.push(name)
    }

    expect(
      offenders,
      'These pass a mile MARKER to a distance formatter. `mi 470.8` is WHERE somebody is - the reference a guidebook, a shelter register and a shuttle driver all share - and converting it hands a metric hiker "757.7 km", which names nothing and, read as a marker, names somewhere else. lib/units.ts deliberately has no function for one; lib/planDisplay.ts has `mileMarker`. The distance BETWEEN two markers is an ordinary distance and converts like any other.',
    ).toEqual([])
  })

  it('tells a marker from a distance, which is the whole basis of the check', () => {
    // The precision this rests on: markers are bare property reads, distances
    // are differences or fields that say so. If that stops being true of the
    // codebase, this guard stops being trustworthy and should be re-thought
    // rather than exempted around.
    for (const marker of [
      'formatDistance(stop.mile, units)',
      'formatDistance(day.start.mile, units, "tenths")',
      'formatElevation(poi.mile, units)',
      'formatDistance( stop.mile , units)',
    ]) {
      expect(MARKER_INTO_FORMATTER.test(marker), marker).toBe(true)
    }
    for (const distance of [
      'formatDistance(Math.abs(day.end.mile - day.start.mile), units)',
      'formatDistance(leg.distanceMi, units)',
      'formatDistance(dry.miles, units)',
      'formatDistance(figures.distanceMi, units)',
      'mileMarker(stop.mile)',
    ]) {
      expect(MARKER_INTO_FORMATTER.test(distance), distance).toBe(false)
    }
  })

  it('charges an issue number for an exemption, and refuses a bare one', () => {
    // The hatch's toll. An exemption somebody can find, count and close is a
    // debt; one without a number is the standard quietly ending, and this is
    // the assertion that keeps the difference real.
    expect(EXEMPTION.test('`${m} m` // units-exempt #625')).toBe(true)
    expect(EXEMPTION.test('`${m} m` // units-exempt')).toBe(false)
    expect(EXEMPTION.test('`${m} m` // units-exempt: it is fine')).toBe(false)
  })
})
