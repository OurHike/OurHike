// Which build of the app this is (#378, RELEASING.md §4).
//
// The point is a question someone else asks: "which version are you on?" Until
// this existed there was no answer available to a hiker at all - not in the
// app, not in a report, not in a support email - so every bug report started
// from a build nobody could identify, and an installed PWA is unusually good
// at hiding that. A service worker can serve a bundle long after a newer one
// deployed (vite.config.ts's registerType note is the history), so "I'm on the
// latest" is a sentence a hiker can say in perfect good faith while running
// something three weeks old.
//
// Three facts, and each answers a different half of that:
//
//   version   which RELEASE this is, if it is one. `0.0.0` until the first tag
//             exists, and honestly so - see `isRelease`.
//   commit    which SOURCE this is, which is the fact that never lies and the
//             only one that identifies an untagged build at all.
//   builtAt   WHEN those bytes were produced, which is what makes a stale
//             service worker visible from the phone.
//
// The values arrive as `define` substitutions from vite.config.ts rather than
// as VITE_-prefixed variables. That comment lives there, with the reasoning.

// Declared here rather than in vite-env.d.ts: this module is their only
// reader, and a global that looks available everywhere invites a second
// reader that bypasses the guards below.
declare const __APP_VERSION__: string
declare const __BUILD_COMMIT__: string
declare const __BUILT_AT__: string

/** What the build stamped in, before any of it is trusted. */
export interface RawBuild {
  version: string
  commit: string
  /** ISO 8601, or '' where the build could not say. */
  builtAt: string
}

// Read through `typeof`, because these identifiers exist only where something
// performed the substitution. Under Vite and Vitest it does, and the guard
// costs nothing there - `typeof "0.0.0"` is what the substituted source says
// and evaluates perfectly well. Anywhere else an unguarded read would be a
// ReferenceError at import time: a blank app in exchange for a label.
const RAW: RawBuild = {
  version: typeof __APP_VERSION__ === 'string' ? __APP_VERSION__ : '',
  commit: typeof __BUILD_COMMIT__ === 'string' ? __BUILD_COMMIT__ : '',
  builtAt: typeof __BUILT_AT__ === 'string' ? __BUILT_AT__ : '',
}

export interface BuildInfo {
  /** Always a displayable string; `UNKNOWN` where the build did not say. */
  version: string
  /** The full 40-character SHA, or `UNKNOWN`. */
  commit: string
  /** The first seven characters of `commit`, or `UNKNOWN`. */
  shortCommit: string
  builtAt: Date | null
  /**
   * Whether this build claims to be a released version.
   *
   * False for `0.0.0`, which is what `client/package.json` carries until the
   * first tag (RELEASING.md §13). It is not a hedge: a build off `main` or a
   * pull request preview genuinely is not a release, and the commit is the
   * only thing that identifies it. Saying so is what stops "0.0.0" reading as
   * a version number someone can look up.
   */
  isRelease: boolean
}

/**
 * The string shown when the build could not identify itself.
 *
 * A word rather than an empty cell, because a blank row reads as a rendering
 * bug and invites someone to go looking for the real value. There isn't one.
 */
export const UNKNOWN = 'unknown'

/** No version has been released yet; `client/package.json`'s initial value. */
const UNRELEASED_VERSION = '0.0.0'

/**
 * Pure, and taking its input rather than reading the globals, so the states
 * that matter can be tested - an unknown commit, a malformed timestamp, a
 * released version - none of which the build this test runs in can produce.
 */
export function readBuildInfo(raw: RawBuild): BuildInfo {
  const commit = raw.commit.trim()
  const version = raw.version.trim()

  // Only a syntactically real SHA is shown as one. Anything else is a value
  // that arrived from somewhere unexpected, and abbreviating it to seven
  // characters would turn it into something that LOOKS like a commit and
  // cannot be looked up.
  const isSha = /^[0-9a-f]{7,40}$/i.test(commit)

  const builtAt = raw.builtAt === '' ? null : new Date(raw.builtAt)

  return {
    version: version === '' ? UNKNOWN : version,
    commit: isSha ? commit : UNKNOWN,
    shortCommit: isSha ? commit.slice(0, 7) : UNKNOWN,
    // An unparseable timestamp is the same answer as none. Date never throws
    // on bad input, it yields an Invalid Date, which formats as the literal
    // words "Invalid Date" if it is allowed through.
    builtAt: builtAt === null || Number.isNaN(builtAt.getTime()) ? null : builtAt,
    isRelease: version !== '' && version !== UNKNOWN && version !== UNRELEASED_VERSION,
  }
}

/**
 * This build in one line, for pasting into a bug report or an email.
 *
 * One string rather than three, because it travels by being copied and then
 * retyped by whoever received it - and a hiker reading three rows down a phone
 * screen onto a keyboard will drop one of them.
 *
 * The FULL commit, where the screen shows seven characters. The short one is a
 * prefix of it, so nothing is contradicted, and a written-down build reference
 * should not depend on seven characters staying unambiguous in a repository
 * that keeps growing.
 */
export function buildSummary(info: BuildInfo): string {
  return [
    `OurHike ${info.version}`,
    `commit ${info.commit}`,
    `built ${builtAtLabel(info.builtAt)}`,
  ].join(' · ')
}

/**
 * When this build was made, to the minute, in UTC.
 *
 * UTC and a fixed layout rather than `toLocaleString`, which would render
 * differently on every phone and in every CI locale. This is a value someone
 * reads out to somebody else, so the two of them have to be looking at the
 * same string - and a date that means one thing in Georgia and another in
 * Maine is the wrong kind of friendly.
 */
export function builtAtLabel(builtAt: Date | null): string {
  if (builtAt === null) return UNKNOWN
  return `${builtAt.toISOString().slice(0, 16).replace('T', ' ')} UTC`
}

/** This build. */
export const BUILD_INFO: BuildInfo = readBuildInfo(RAW)
