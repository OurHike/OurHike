// Turns one run of the stopwatch into a verdict against the launch budget
// (#1299), so a scheduled job can say whether production still meets it.
//
// WHY THIS IS A SEPARATE SCRIPT AND NOT PART OF THE STOPWATCH.
// `measure-first-run.mjs` measures and prints; a person reads it while working
// on the launch path, and TESTING.md §21 is explicit that it is not a gate. It
// stays that. This file is the second reader of the same run - a comparison
// against the numbers features/LAUNCH_BUDGET.md §3 wrote down - and keeping
// the two apart is what stops the instrument acquiring an opinion.
//
// IT DOES NOT FAIL THE RUN, for the reason check-deployed-app.yml's header
// gives: GitHub emails on every scheduled failure, so a persistent regression
// would send an identical email every morning until somebody filtered it. The
// tracking issue is the signal - opened green->red, closed red->green.
//
// AND IT IS ONE MACHINE'S MILLISECONDS, which is the whole caveat. A GitHub
// runner is not a phone and its speed varies between runs; the budget was
// written on a 4x-throttled desktop core and is compared against one here. So
// the thresholds below are deliberately the LOOSE end of §3 - what they catch
// is a regression of the size #1300 and #1301 fixed (hundreds of milliseconds
// to seconds), never a ten-per-cent drift. features/LAUNCH_BUDGET.md §4.1 is
// where the phone's own number comes from, and it is not this.

import { readFileSync, writeFileSync } from 'node:fs'

const argv = process.argv.slice(2)
const flag = (name, fallback = null) => {
  const found = argv.find((arg) => arg.startsWith(`--${name}=`))
  return found === undefined ? fallback : found.slice(name.length + 3)
}

const measured = flag('measured')
const out = flag('json')
/**
 * Report rather than gate.
 *
 * Without it, a row over budget exits 1 - which is what somebody running this
 * by hand after a change wants, and what makes the flag mean something rather
 * than decorate the workflow. With it, non-zero is RESERVED for this script
 * itself crashing, which is the distinction .github/workflows/*.yml's
 * `| tee` steps are built to read (#514, and see
 * .github/tests/test_pipe_to_tee_does_not_mask_failure.py).
 */
const exitZero = argv.includes('--exit-zero')
if (measured === null) {
  console.error(
    'usage: node scripts/check-launch-speed.mjs --measured=<stopwatch json> ' +
      '[--json=<verdict json>] [--exit-zero]',
  )
  process.exit(2)
}

/**
 * What a launch may cost on a runner, and where each number comes from.
 *
 * Every one is features/LAUNCH_BUDGET.md §3's row, widened for the machine:
 * the doc's figures are a 4x-throttled phone profile and this runs on a
 * shared CI core whose own speed moves between mornings. A threshold that
 * fired on that movement would be a check nobody reads.
 */
const BUDGET = [
  {
    key: 'shell_frame',
    what: 'the tab bar rendered',
    /** §3's shell-frame row is 500 ms. Tripled here: the doc's number is the
     *  target on a phone profile, and what this is watching for is the class
     *  of regression where the shell waited on storage or on a chunk it did
     *  not need - which cost 1,152-1,572 ms when it was measured. */
    limit: 1500,
    read: (run) => run.marks?.['tab bar rendered'] ?? null,
  },
  {
    key: 'first_tap',
    what: 'the first tap on a tab being accepted',
    /** §3 asks for 100 ms. The first tap in a `--returning` run is made at
     *  800 ms, deliberately into the busiest moment of the launch, and it
     *  waited 933-1,441 ms on production when the budget was written. */
    limit: 1200,
    read: (run) => run.taps?.[0]?.accepted_ms ?? null,
  },
  {
    key: 'longest_task',
    what: 'the longest single task',
    /** §3 asks for 100 ms; production measured 275-332 ms. A whole second is
     *  the point at which a tap visibly does nothing. */
    limit: 1000,
    read: (run) => run.longest_task_ms ?? null,
  },
  {
    key: 'total_blocking',
    what: 'total blocking time',
    /** §3 asks for 200 ms; production measured 534-764 ms. Two seconds is the
     *  shape of the regression this exists to notice, not a tight bound. */
    limit: 2000,
    read: (run) => run.total_blocking_ms ?? null,
  },
]

const run = JSON.parse(readFileSync(measured, 'utf8'))

const rows = BUDGET.map((row) => {
  const value = row.read(run)
  return {
    check: row.key,
    what: row.what,
    measured_ms: value,
    limit_ms: row.limit,
    // A moment the run never reached is NOT a pass. It is the one answer a
    // check like this must not round down: a launch whose tab bar never
    // appeared is the worst outcome available, and reporting it as "no
    // number, no problem" is how a monitor goes quiet on a real outage.
    over: value === null ? true : value > row.limit,
    reason: value === null ? 'never reached' : null,
  }
})

const failed = rows.filter((row) => row.over)
const verdict = {
  checked_at: new Date().toISOString().replace('T', ' ').slice(0, 16) + ' UTC',
  url: run.url ?? null,
  mode: run.mode ?? null,
  rows,
  failed,
}

const width = Math.max(...rows.map((row) => row.what.length))
console.log(`launch budget, ${verdict.mode} launch against ${verdict.url}`)
for (const row of rows) {
  const value = row.measured_ms === null ? 'never reached' : `${row.measured_ms} ms`
  console.log(
    `  ${row.over ? 'OVER' : ' ok '}  ${row.what.padEnd(width)}  ${value.padStart(13)}  (budget ${row.limit_ms} ms)`,
  )
}
console.log(
  failed.length === 0
    ? '\nEvery row inside its budget.'
    : `\n${failed.length} row(s) over budget. features/LAUNCH_BUDGET.md §3 is what they are measured against.`,
)

if (out !== null) {
  writeFileSync(out, `${JSON.stringify(verdict, null, 2)}\n`)
  console.log(`wrote ${out}`)
}

if (failed.length > 0 && !exitZero) process.exit(1)
