// One tracking issue, opened when a monitor goes red and closed when it goes
// green again. Seven scheduled workflows share this: check-deployment.yml,
// check-deployed-app.yml, check-upstream-freshness.yml, smoke-published.yml,
// check-pending-approvals.yml, check-note-anchors.yml and route-disputes.yml.
//
// The last of those is the only one that calls this more than once per run:
// route-disputes.yml opens ONE ISSUE PER DATA SOURCE, because its recipient
// is a steward rather than this repository, and each steward wants their own
// running list. That works because the lookup is label AND title, which was
// already true for #651's reason - see the `title` parameter below.
//
// WHY THIS IS ONE FILE AND NOT FOUR COPIES (#678). It was four copies of about
// ninety lines each, and the interesting part was never the markdown - it is
// the handful of ways the policy can be wrong:
//
//   * Opening notifies the codeowners and updating a body does not, which is
//     what makes a week-long outage cost one email rather than seven. #431:
//     alert on transitions, not on runs.
//   * "First seen" has to survive across runs, or every update resets the
//     clock and a source stale for three weeks reads as stale since this
//     morning - which is the number that decides how urgent this is.
//   * The all-clear closes the issue, so the issue being open is itself the
//     signal, and nothing has to read a run log to know the state.
//
// Fixing those in one place is the same argument
// .github/actions/changed-paths/action.yml makes for itself, and the same
// evidence: the four copies had already drifted. #655 fixed a `| tee` exit
// status in one while another had carried the right pattern all along, and
// #651 corrected the all-clear condition in two of them, differently, leaving
// nobody able to say whether the other two needed it.
//
// WHAT STAYS WITH THE CALLER, AND WHY THAT LINE IS WHERE IT IS. #651 is the
// reason `healthy` is an input rather than something computed here. The two
// corrections it made were not the same correction:
//
//   check-deployment.yml   failed.length === 0 && verdict.checked_artifacts !== false
//   smoke-published.yml    failed.length === 0 && unreachable.length === 0
//
// One is about whether the run looked at all, the other about telling
// unreachable apart from failed. A shared implementation of "is it green"
// would have had to be wrong for at least one of them. So the caller owns the
// verdict and the body; this owns finding, opening, updating, closing, and the
// first-seen map.

'use strict'

// The marker is the whole reason first-seen stops being fragile. Each copy
// used to parse the dates back out of the table it had just written, with a
// regex hand-fitted to that file's column count - three of the four counted
// three columns, one counted two - so adding a column to any of those tables
// would silently reset that monitor's clock to today, for ever, with the body
// still saying "first seen". Nothing tested the round trip.
//
// Written as an HTML comment so it renders as nothing, and parsed as JSON so
// it does not care what the table above it looks like.
const MARKER = /<!-- tracking-issue first-seen (\{[\s\S]*?\}) -->/

const marker = (firstSeen) => `<!-- tracking-issue first-seen ${JSON.stringify(firstSeen)} -->`

// A table cell holds text this repository did not write - an upstream ETag, a
// bucket's error detail - and a stray pipe or newline in one would break both
// the table and, before the marker, the parse that read it back.
const cell = (value) => String(value).replace(/\r?\n/g, ' ').replace(/\|/g, '\\|')

// Rows written before the marker existed, read once so a live issue does not
// lose its clock the day this lands. #478 - "Upstream data freshness" - is
// open right now and carries real dates.
//
// Deliberately NOT the per-file regexes this replaces: it takes the first
// backticked cell as the key and the first bare ISO date in any later cell as
// the value, so it does not depend on how many columns sit between them. That
// is the property the originals lacked. It is read-only and disappears on its
// own, since every body written from here on carries a marker.
function legacyFirstSeen(body) {
  const recovered = {}
  for (const line of body.split('\n')) {
    if (!line.startsWith('|')) continue
    const key = /^\|\s*`([^`]+)`\s*\|/.exec(line)
    if (!key) continue
    const since = /\|\s*(\d{4}-\d{2}-\d{2})\s*\|/.exec(line)
    if (since) recovered[key[1]] = since[1]
  }
  return recovered
}

function recoverFirstSeen(body) {
  const found = MARKER.exec(body || '')
  if (found) {
    try {
      return JSON.parse(found[1])
    } catch {
      // A corrupted marker is not worth failing a monitor over, and the
      // legacy reader below is a better answer than an empty map: the table
      // is still there and still has the dates in it.
    }
  }
  return legacyFirstSeen(body || '')
}

/**
 * @param {object} api                 github, context and core, as github-script provides them.
 * @param {object} options
 * @param {string} options.label       The label that identifies this monitor's issue.
 * @param {string} options.title       Its exact title. Label plus title, because
 *                                     check-deployment.yml and smoke-published.yml
 *                                     deliberately share a label and must not share an issue.
 * @param {boolean} options.healthy    Caller's verdict. See the note above on #651.
 * @param {string} options.allClear    Comment posted when closing. Notifies once, which is the point.
 * @param {string} options.checkedAt   The date new keys are first seen on.
 * @param {string[]} options.keys      The keys currently failing.
 * @param {(firstSeen: object, cell: (v: unknown) => string) => string} options.render
 *                                     Builds the body. Given the recovered dates and the escaper.
 * @param {(newKeys: string[], cell: (v: unknown) => string) => string|null} [options.announce]
 *                                     Optional, and the one exception to "updating is silent" -
 *                                     see the note above the call. Comments when keys appear that
 *                                     the open issue had not already recorded. Return null to stay quiet.
 */
async function trackingIssue({ github, context, core }, options) {
  const { label, title, healthy, allClear, checkedAt, keys = [], render, announce } = options
  const repo = { owner: context.repo.owner, repo: context.repo.repo }

  const existing = (
    await github.paginate(github.rest.issues.listForRepo, {
      ...repo,
      state: 'open',
      labels: label,
      per_page: 100,
    })
  ).find((issue) => issue.title === title)

  if (healthy) {
    if (!existing) {
      core.info(`Healthy, and no "${title}" issue is open. Nothing to do.`)
      return { action: 'none' }
    }
    // Comment then close, in that order: the comment is the notification and
    // closing alone would be silent.
    await github.rest.issues.createComment({
      ...repo,
      issue_number: existing.number,
      body: `${allClear}\n\n---\n_Generated by [Claude Code](https://claude.ai/code)_`,
    })
    await github.rest.issues.update({
      ...repo,
      issue_number: existing.number,
      state: 'closed',
      state_reason: 'completed',
    })
    core.info(`Closed #${existing.number}.`)
    return { action: 'closed', number: existing.number }
  }

  const recovered = recoverFirstSeen(existing ? existing.body : '')
  // Only the keys failing NOW carry forward. A check that passed and later
  // fails again is a new occurrence and starts a new clock, which is what the
  // per-file versions did implicitly by only ever looking up failing keys -
  // and it keeps the marker from growing without bound.
  const firstSeen = {}
  for (const key of keys) {
    firstSeen[key] = recovered[key] ?? checkedAt
  }

  const body = `${render(firstSeen, cell)}\n\n${marker(firstSeen)}`

  if (existing) {
    // Updating a body does not notify, which is the whole reason a week-long
    // outage costs one email.
    await github.rest.issues.update({ ...repo, issue_number: existing.number, body })

    // WHEN SILENCE IS THE WRONG ANSWER, AND WHY THIS IS NOT #431 REOPENED.
    // The four original monitors each track one ongoing condition - an
    // upstream is stale, an origin is down - so a body update carrying the
    // same condition into its second week is genuinely not news. A key set
    // whose members are discrete events is a different shape:
    // check-pending-approvals.yml's keys are workflow runs, each one a
    // separate decision somebody has to make, and `concurrency: publish-data`
    // queues dispatches behind one another, so a second run joining an open
    // episode is the normal case rather than the rare one. Staying silent
    // there means the first run of an episode is announced and every one
    // after it is not.
    //
    // So the transition rule is unchanged and the *transition* is what
    // widened: a new key is a transition, a key that was already there is
    // not. A monitor that passes no `announce` behaves exactly as before,
    // which is why the other four are untouched.
    const appeared = keys.filter((key) => !(key in recovered))
    if (announce && appeared.length) {
      const said = announce(appeared, cell)
      if (said) {
        await github.rest.issues.createComment({
          ...repo,
          issue_number: existing.number,
          body: `${said}\n\n---\n_Generated by [Claude Code](https://claude.ai/code)_`,
        })
      }
    }

    core.info(`Updated #${existing.number}.`)
    return { action: 'updated', number: existing.number, firstSeen, appeared }
  }

  const created = await github.rest.issues.create({ ...repo, title, body, labels: [label] })
  core.info(`Opened #${created.data.number}.`)
  return { action: 'opened', number: created.data.number, firstSeen }
}

module.exports = trackingIssue
module.exports.cell = cell
module.exports.recoverFirstSeen = recoverFirstSeen
module.exports.marker = marker
