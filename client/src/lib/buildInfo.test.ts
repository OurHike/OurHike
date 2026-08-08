import { describe, it, expect } from 'vitest'
import { existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { cwd } from 'node:process'
import {
  BUILD_INFO,
  UNKNOWN,
  buildSummary,
  builtAtLabel,
  readBuildInfo,
} from './buildInfo'

// #378. The behaviour under test is what the app is willing to CLAIM about
// itself, which is most of the point: a version display that guesses is worse
// than none, because the guess is what somebody then quotes back.
//
// Almost everything here goes through `readBuildInfo` with fixed input rather
// than through `BUILD_INFO`. The real constants are a live commit and the
// clock at build time, so a test asserting on them would be asserting on when
// it happened to run - and none of the states worth checking (no commit, a
// released version, a malformed timestamp) can be produced by the build the
// test is running in.

const RELEASED = {
  version: '1.0.0',
  commit: '6e23f122d35c327abf6eec8ca48158e336362cc9',
  builtAt: '2026-08-07T23:51:31.603Z',
}

// Resolved from the working directory rather than import.meta.url, which
// vitest does not hand back as a file:// URL - the same gotcha, and the same
// answer, as lib/push.test.ts. Both candidates are checked so this works
// whether the suite is run from the repo root or from client/.
const PACKAGE_JSON = [
  join(cwd(), 'package.json'),
  join(cwd(), 'client', 'package.json'),
].find((candidate) => existsSync(candidate)) as string

describe('readBuildInfo', () => {
  it('reports the version and commit the build stamped in', () => {
    const info = readBuildInfo(RELEASED)

    expect(info.version).toBe('1.0.0')
    expect(info.commit).toBe('6e23f122d35c327abf6eec8ca48158e336362cc9')
    expect(info.shortCommit).toBe('6e23f12')
  })

  it('abbreviates the commit to a prefix of the full one, never something else', () => {
    const info = readBuildInfo(RELEASED)

    expect(info.commit.startsWith(info.shortCommit)).toBe(true)
  })

  it('says so plainly when the build could not identify itself', () => {
    const info = readBuildInfo({ version: '', commit: '', builtAt: '' })

    expect(info.version).toBe(UNKNOWN)
    expect(info.commit).toBe(UNKNOWN)
    expect(info.shortCommit).toBe(UNKNOWN)
    expect(info.builtAt).toBeNull()
  })

  // A value that is not a hash must not be dressed up as one. Abbreviating it
  // to seven characters would produce something that looks exactly like a
  // commit and cannot be looked up, which is the one outcome worse than
  // admitting the build does not know.
  it('refuses to abbreviate a commit that is not a hash', () => {
    for (const commit of ['HEAD', 'not-a-sha', 'zzzzzzz', '123']) {
      const info = readBuildInfo({ ...RELEASED, commit })

      expect(info.commit).toBe(UNKNOWN)
      expect(info.shortCommit).toBe(UNKNOWN)
    }
  })

  // `new Date('nonsense')` is an Invalid Date rather than a throw, and it
  // renders as the literal words "Invalid Date" if it is allowed through.
  it('treats an unreadable build time as no build time', () => {
    expect(readBuildInfo({ ...RELEASED, builtAt: 'sometime' }).builtAt).toBeNull()
  })

  it('does not claim to be a release before there has been one', () => {
    expect(readBuildInfo({ ...RELEASED, version: '0.0.0' }).isRelease).toBe(false)
    expect(readBuildInfo({ ...RELEASED, version: '' }).isRelease).toBe(false)
    expect(readBuildInfo(RELEASED).isRelease).toBe(true)
  })
})

describe('builtAtLabel', () => {
  // Fixed and UTC rather than locale-formatted: this is a string one person
  // reads out to another, so both of them have to see the same one.
  it('gives the same string whatever the reader’s locale', () => {
    expect(builtAtLabel(new Date('2026-08-07T23:51:31.603Z'))).toBe(
      '2026-08-07 23:51 UTC',
    )
  })

  it('says unknown rather than nothing when there is no build time', () => {
    expect(builtAtLabel(null)).toBe(UNKNOWN)
  })
})

describe('buildSummary', () => {
  it('carries the full commit, not the seven characters on screen', () => {
    const summary = buildSummary(readBuildInfo(RELEASED))

    expect(summary).toContain('6e23f122d35c327abf6eec8ca48158e336362cc9')
    expect(summary).toContain('1.0.0')
    expect(summary).toContain('2026-08-07 23:51 UTC')
  })

  it('stays one line, because it is pasted into somebody else’s message', () => {
    expect(buildSummary(readBuildInfo(RELEASED))).not.toContain('\n')
  })
})

describe('BUILD_INFO', () => {
  // The one thing worth asserting about the real constants, and it is the
  // thing that would actually break: if the `define` substitution in
  // vite.config.ts stopped happening, every field would fall back to "unknown"
  // and the About section would ship saying nothing at all.
  it('is populated by the build rather than falling back to unknown', () => {
    expect(BUILD_INFO.version).not.toBe(UNKNOWN)
    expect(BUILD_INFO.commit).not.toBe(UNKNOWN)
    expect(BUILD_INFO.builtAt).not.toBeNull()
  })

  // RELEASING.md §4 makes package.json the single source for the version.
  // This is what keeps that true from the app's side; pages.yml refuses to
  // deploy a `v*` tag that disagrees with the same file, which keeps it true
  // from the release's.
  it('reads its version from package.json rather than inventing one', () => {
    const packaged = JSON.parse(readFileSync(PACKAGE_JSON, 'utf8')) as {
      version: string
    }

    expect(packaged.version).not.toBe('')
    expect(BUILD_INFO.version).toBe(packaged.version)
  })
})
