// The prefilled links in lib/bugReport.ts name things that live in another
// directory: the issue-form filenames, the field ids they fill, and the exact
// text of bug_report.yml's `area` options.
//
// None of those fail loudly. GitHub matches a prefilled dropdown by its option
// TEXT and drops a parameter naming no field, so a label reworded in the form
// and not here does not error - it silently stops preselecting, and the only
// symptom is reports arriving with no area on them, from a mechanism whose
// whole purpose was that a hiker should not have to place their own bug.
//
// So this reads the forms themselves rather than restating them.
// `.github/ISSUE_TEMPLATE/` is in client-tests.yml's scope list for exactly
// this reason - that workflow's rule is that a suite's scope list includes
// every file its tests read.

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { BUG_REPORT_OPTIONS } from '../lib/bugReport'

const TEMPLATE_DIR = resolve(process.cwd(), '../.github/ISSUE_TEMPLATE')

function form(filename: string): string {
  return readFileSync(resolve(TEMPLATE_DIR, filename), 'utf8')
}

describe('the issue forms the app links to', () => {
  it('all exist, under the names the options give', () => {
    for (const option of BUG_REPORT_OPTIONS) {
      expect(() => form(option.template)).not.toThrow()
    }
  })

  // A YAML list item, which is how a dropdown option is written. Substring
  // alone would pass on a label that is merely mentioned in prose somewhere
  // in the file.
  it('still offers every area the app preselects', () => {
    const bugReport = form('bug_report.yml')

    for (const option of BUG_REPORT_OPTIONS) {
      if (option.area === null) continue
      expect(bugReport).toContain(`- ${option.area}`)
    }
  })

  it('still has the fields the links fill', () => {
    const bugReport = form('bug_report.yml')

    expect(bugReport).toContain('id: area')
    expect(bugReport).toContain('id: conditions')
  })

  // The other half of the steer in ReportBug.tsx. If the form itself stops
  // saying a trail condition belongs in the app, the app is the only place
  // left saying it - and this is a repository where that distinction is
  // written into CONTRIBUTING.md, the README and the templates' own headers.
  it('still tells a trail condition to go through the app instead', () => {
    for (const filename of ['bug_report.yml', 'trail_data.yml']) {
      expect(form(filename)).toContain('Report a problem')
    }
  })
})
