// The native shells' version numbers follow client/package.json (#1397).
//
// scripts/shell-version.mjs is the one place the scheme lives; these hold the
// scheme's arithmetic, its refusals, and - the test a release pull request
// meets - that the committed Android and iOS projects say what package.json
// says, so a bump that forgot `npm run shell:version` goes red here rather
// than at a store's upload form.

import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import {
  GRADLE,
  PACKAGE_JSON,
  PBXPROJ,
  drift,
  rewriteGradle,
  rewritePbxproj,
  shellVersion,
  statedVersions,
} from '../../scripts/shell-version.mjs'

describe('shellVersion', () => {
  it('reads 1.3.2 as version code 1030200, and a rebuild adds one', () => {
    expect(shellVersion('1.3.2')).toEqual({ name: '1.3.2', code: 1030200 })
    expect(shellVersion('1.3.2', 1).code).toBe(1030201)
  })

  it('only ever goes up while the semver does', () => {
    const order = ['1.3.2', '1.3.3', '1.4.0', '1.10.0', '2.0.0']
    const codes = order.map((version) => shellVersion(version, 99).code)
    const firsts = order.map((version) => shellVersion(version).code)
    for (let i = 1; i < order.length; i++) expect(firsts[i]).toBeGreaterThan(codes[i - 1])
  })

  it('refuses a minor or patch above 99 rather than overflowing into the next field', () => {
    expect(() => shellVersion('1.100.0')).toThrow(/0-99/)
    expect(() => shellVersion('1.3.100')).toThrow(/0-99/)
  })

  it('refuses a version that is not MAJOR.MINOR.PATCH, and a rebuild outside 0-99', () => {
    expect(() => shellVersion('1.3')).toThrow(/MAJOR\.MINOR\.PATCH/)
    expect(() => shellVersion('1.3.2-beta')).toThrow(/MAJOR\.MINOR\.PATCH/)
    expect(() => shellVersion('1.3.2', 100)).toThrow(/rebuild/)
  })
})

describe('rewriting the shells', () => {
  const gradle =
    '    defaultConfig {\n        versionCode 1\n        versionName "1.0"\n    }\n'
  const pbx =
    '\t\t\t\tCURRENT_PROJECT_VERSION = 1;\n\t\t\t\tMARKETING_VERSION = 1.0;\n' +
    '\t\t\t\tCURRENT_PROJECT_VERSION = 1;\n\t\t\t\tMARKETING_VERSION = 1.0;\n'
  const want = shellVersion('1.3.2')

  it('rewrites build.gradle and both of the pbxproj build configurations', () => {
    const stated = statedVersions(rewriteGradle(gradle, want), rewritePbxproj(pbx, want))

    expect(stated).toEqual({
      gradleCode: '1030200',
      gradleName: '1.3.2',
      pbxCodes: ['1030200', '1030200'],
      pbxNames: ['1.3.2', '1.3.2'],
    })
    expect(drift(want, stated)).toEqual([])
  })

  it('names each field that drifted, including one configuration of two', () => {
    const halfDone = rewritePbxproj(pbx, want).replace(
      'MARKETING_VERSION = 1.3.2;',
      'MARKETING_VERSION = 1.0;',
    )
    const problems = drift(want, statedVersions(gradle, halfDone))

    expect(problems).toHaveLength(3)
    expect(problems.join('\n')).toContain('versionCode is 1, want 1030200')
    expect(problems.join('\n')).toContain('MARKETING_VERSION is 1.0, 1.3.2, want 1.3.2')
  })

  it('throws rather than writing nothing when a field has moved out from under it', () => {
    expect(() => rewriteGradle('android {}\n', want)).toThrow(/versionCode/)
    expect(() => rewritePbxproj('nothing here', want)).toThrow(/CURRENT_PROJECT_VERSION/)
  })
})

describe('the committed shells', () => {
  it('say the version package.json says - run `npm run shell:version` if this fails', () => {
    const version = JSON.parse(readFileSync(PACKAGE_JSON, 'utf8')).version
    const stated = statedVersions(
      readFileSync(GRADLE, 'utf8'),
      readFileSync(PBXPROJ, 'utf8'),
    )

    expect(drift(shellVersion(version), stated)).toEqual([])
  })
})
