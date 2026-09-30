#!/usr/bin/env node
// The native shells' version numbers, derived from client/package.json
// (#1397).
//
// WHY. Both shells carried Capacitor's scaffold defaults - Android
// versionName "1.0" / versionCode 1, iOS MARKETING_VERSION 1.0 /
// CURRENT_PROJECT_VERSION 1 - while the web app inside them went to 1.3.2,
// and nothing anywhere wrote those four fields. So a hiker's About screen
// said 1.3.2 while the phone's own app info said 1.0 (1), and the second
// upload to either store would be refused: both require a build number
// higher than the last one accepted.
//
// THE SCHEME, chosen by the maintainer (poll, 2026-09-25):
//
//   name = package.json's version, as it is             1.3.2
//   code = major*1,000,000 + minor*10,000 + patch*100 + rebuild
//                                                       1030200
//
// Readable in both directions (1030200 is 1.3.2, first build), monotonic for
// as long as package.json's version only goes up - which RELEASING.md §4's
// version gate already enforces - and it leaves 99 re-uploads of one version
// in the `rebuild` slot, for a store build that has to go again without a new
// web release. What would break it: a minor or patch number above 99, which
// this refuses rather than letting it overflow into the next field, because
// a code that only ever goes up cannot be taken back once a store holds it.
//
// TWO CALLERS, ONE ANSWER. build-shells.yml runs `--write` before
// `cap sync`, so a shell CI builds always carries the version it wraps. The
// committed files are kept in step too, and src/test/shellVersion.test.ts
// fails when they drift, so a local Android Studio or Xcode build does not
// quietly say 1.0 - and a release pull request that bumps package.json
// without running `npm run shell:version` is told so by the suite, rather
// than by a store at submission time.
//
//   node scripts/shell-version.mjs            print what the shells should say
//   node scripts/shell-version.mjs --write    rewrite both shells to match
//   node scripts/shell-version.mjs --check    exit 1 if either disagrees
//
// SHELL_REBUILD (0-99, default 0) fills the rebuild slot.

import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const CLIENT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
export const PACKAGE_JSON = resolve(CLIENT, 'package.json')
export const GRADLE = resolve(CLIENT, 'android/app/build.gradle')
export const PBXPROJ = resolve(CLIENT, 'ios/App/App.xcodeproj/project.pbxproj')

const SEMVER = /^(\d+)\.(\d+)\.(\d+)$/

/** `{ name, code }` for a package.json version and a rebuild count. */
export function shellVersion(version, rebuild = 0) {
  const match = SEMVER.exec(version)
  if (!match)
    throw new Error(
      `package.json version ${JSON.stringify(version)} is not MAJOR.MINOR.PATCH`,
    )
  const [major, minor, patch] = match.slice(1).map(Number)
  if (minor > 99 || patch > 99) {
    throw new Error(
      `${version}: minor and patch must be 0-99, or the version code would overflow into the next field`,
    )
  }
  if (!Number.isInteger(rebuild) || rebuild < 0 || rebuild > 99) {
    throw new Error(`rebuild must be an integer 0-99, got ${rebuild}`)
  }
  return {
    name: version,
    code: major * 1_000_000 + minor * 10_000 + patch * 100 + rebuild,
  }
}

const GRADLE_CODE = /^(\s*versionCode\s+)\d+\s*$/m
const GRADLE_NAME = /^(\s*versionName\s+)"[^"]*"\s*$/m
const PBX_CODE = /(\bCURRENT_PROJECT_VERSION = )[^;]+;/g
const PBX_NAME = /(\bMARKETING_VERSION = )[^;]+;/g

function replaceOrThrow(text, pattern, replacement, what) {
  pattern.lastIndex = 0
  if (!pattern.test(text)) throw new Error(`no ${what} to rewrite`)
  pattern.lastIndex = 0
  return text.replace(pattern, replacement)
}

export function rewriteGradle(text, { name, code }) {
  const withCode = replaceOrThrow(
    text,
    GRADLE_CODE,
    `$1${code}`,
    'versionCode in build.gradle',
  )
  return replaceOrThrow(
    withCode,
    GRADLE_NAME,
    `$1"${name}"`,
    'versionName in build.gradle',
  )
}

export function rewritePbxproj(text, { name, code }) {
  const withCode = replaceOrThrow(
    text,
    PBX_CODE,
    `$1${code};`,
    'CURRENT_PROJECT_VERSION in project.pbxproj',
  )
  return replaceOrThrow(
    withCode,
    PBX_NAME,
    `$1${name};`,
    'MARKETING_VERSION in project.pbxproj',
  )
}

/** Every version the two shells state, as strings, so a mismatch in one of
 *  the pbxproj's two build configurations is not hidden by the other. */
export function statedVersions(gradleText, pbxText) {
  return {
    gradleCode: GRADLE_CODE.exec(gradleText)?.[0].trim().split(/\s+/)[1] ?? null,
    gradleName:
      GRADLE_NAME.exec(gradleText)?.[0].trim().split(/\s+/)[1]?.replaceAll('"', '') ??
      null,
    pbxCodes: [...pbxText.matchAll(PBX_CODE)].map((m) =>
      m[0].split('=')[1].replace(';', '').trim(),
    ),
    pbxNames: [...pbxText.matchAll(PBX_NAME)].map((m) =>
      m[0].split('=')[1].replace(';', '').trim(),
    ),
  }
}

/** The disagreements between what the shells state and what they should. */
export function drift(expected, stated) {
  const want = { code: String(expected.code), name: expected.name }
  const problems = []
  if (stated.gradleCode !== want.code)
    problems.push(`build.gradle versionCode is ${stated.gradleCode}, want ${want.code}`)
  if (stated.gradleName !== want.name)
    problems.push(`build.gradle versionName is ${stated.gradleName}, want ${want.name}`)
  if (stated.pbxCodes.length === 0 || stated.pbxCodes.some((c) => c !== want.code)) {
    problems.push(
      `project.pbxproj CURRENT_PROJECT_VERSION is ${stated.pbxCodes.join(', ') || 'absent'}, want ${want.code}`,
    )
  }
  if (stated.pbxNames.length === 0 || stated.pbxNames.some((n) => n !== want.name)) {
    problems.push(
      `project.pbxproj MARKETING_VERSION is ${stated.pbxNames.join(', ') || 'absent'}, want ${want.name}`,
    )
  }
  return problems
}

function main(argv) {
  const version = JSON.parse(readFileSync(PACKAGE_JSON, 'utf8')).version
  const expected = shellVersion(version, Number(process.env.SHELL_REBUILD ?? 0))
  const gradle = readFileSync(GRADLE, 'utf8')
  const pbx = readFileSync(PBXPROJ, 'utf8')

  if (argv.includes('--write')) {
    writeFileSync(GRADLE, rewriteGradle(gradle, expected))
    writeFileSync(PBXPROJ, rewritePbxproj(pbx, expected))
    console.log(`shells now say ${expected.name} (${expected.code})`)
    return 0
  }
  if (argv.includes('--check')) {
    const problems = drift(expected, statedVersions(gradle, pbx))
    for (const problem of problems) console.error(problem)
    if (problems.length)
      console.error(
        'Run `npm run shell:version` in client/ to bring both shells in line with package.json.',
      )
    return problems.length ? 1 : 0
  }
  console.log(`${expected.name} (${expected.code})`)
  return 0
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exit(main(process.argv.slice(2)))
}
