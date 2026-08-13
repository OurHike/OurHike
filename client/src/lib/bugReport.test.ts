import { describe, it, expect } from 'vitest'
import { BUG_REPORT_OPTIONS, bugReportUrl, REPOSITORY_URL } from './bugReport'
import { readBuildInfo } from './buildInfo'

// #626. What is tested here is that each option lands on the right form with
// the right things already answered - the whole value of prefilling is that a
// hiker does not have to reproduce a commit hash from memory, and a parameter
// that names no field is silently dropped by GitHub rather than reported.

const RELEASE = readBuildInfo({
  version: '1.0.0',
  commit: '6e23f122d35c327abf6eec8ca48158e336362cc9',
  builtAt: '2026-08-07T23:51:31.603Z',
})

/** The query GitHub will actually parse, rather than the string around it. */
function paramsOf(url: string): URLSearchParams {
  return new URL(url).searchParams
}

describe('bugReportUrl', () => {
  it('opens an issue form on the repository', () => {
    const url = bugReportUrl(BUG_REPORT_OPTIONS[0], RELEASE)

    expect(url.startsWith(`${REPOSITORY_URL}/issues/new?`)).toBe(true)
    expect(paramsOf(url).get('template')).toBe('bug_report.yml')
  })

  it('carries the whole build, full commit included, into the software form', () => {
    const app = BUG_REPORT_OPTIONS.find((o) => o.id === 'app')!

    const conditions = paramsOf(bugReportUrl(app, RELEASE)).get('conditions')

    expect(conditions).toContain('1.0.0')
    // The FULL hash, not the seven characters the screen shows: this is the
    // copy of it nobody has to retype, so it may as well be unambiguous.
    expect(conditions).toContain('6e23f122d35c327abf6eec8ca48158e336362cc9')
    expect(conditions).toContain('2026-08-07 23:51 UTC')
  })

  it('preselects the area, so a hiker is not asked to place their own bug', () => {
    const account = BUG_REPORT_OPTIONS.find((o) => o.id === 'account')!

    expect(paramsOf(bugReportUrl(account, RELEASE)).get('area')).toBe(
      'Backend — reports, closures, moderation, accounts',
    )
  })

  // The data form has neither field. Sending them anyway would work - GitHub
  // drops a parameter naming no field - and would still be a claim about what
  // that form asks for.
  it('sends the data form only what it has fields for', () => {
    const data = BUG_REPORT_OPTIONS.find((o) => o.id === 'data')!
    const params = paramsOf(bugReportUrl(data, RELEASE))

    expect(params.get('template')).toBe('trail_data.yml')
    expect(params.get('area')).toBeNull()
    expect(params.get('conditions')).toBeNull()
  })

  // An em dash and a middle dot both have to survive being put in a URL. A
  // link that arrives with a mangled area preselects nothing, which is the
  // failure this whole mechanism exists to avoid.
  it('encodes the punctuation the labels and the build line carry', () => {
    const url = bugReportUrl(BUG_REPORT_OPTIONS[0], RELEASE)

    expect(url).not.toContain('—')
    expect(url).not.toContain('·')
    expect(url).not.toContain(' ')
    // Decoded by the same parser GitHub uses, it is the label again.
    expect(paramsOf(url).get('area')).toBe('Client — the map app')
  })

  it('says something useful even when the build could not identify itself', () => {
    const unknown = readBuildInfo({ version: '', commit: '', builtAt: '' })

    const conditions = paramsOf(bugReportUrl(BUG_REPORT_OPTIONS[0], unknown)).get(
      'conditions',
    )

    expect(conditions).toContain('unknown')
  })
})

describe('BUG_REPORT_OPTIONS', () => {
  it('offers a handful of options rather than one link into the tracker', () => {
    expect(BUG_REPORT_OPTIONS.length).toBeGreaterThanOrEqual(3)
    expect(BUG_REPORT_OPTIONS.length).toBeLessThanOrEqual(5)
  })

  it('gives every option a distinct id and its own hint', () => {
    const ids = BUG_REPORT_OPTIONS.map((o) => o.id)
    expect(new Set(ids).size).toBe(ids.length)

    for (const option of BUG_REPORT_OPTIONS) {
      expect(option.label.length).toBeGreaterThan(0)
      expect(option.hint.length).toBeGreaterThan(0)
    }
  })

  // Somebody who does not know which of the three it is still has to be able
  // to file. Without this row, the option that fits worst is the one they pick.
  it('keeps a way through for someone who cannot place their own bug', () => {
    expect(BUG_REPORT_OPTIONS.some((o) => o.area === 'Not sure')).toBe(true)
  })
})
