// The foot of Settings: which build of the app this phone is running (#378).
//
// Its own file rather than more rows inside Settings.tsx, for the reason
// BRANCHING.md gives about App.tsx - a screen everything gets appended to
// becomes the file every branch collides in - and because the copy button
// gives this section state, which nothing else in Settings has.
//
// WHY A COPY BUTTON AND NOT JUST THREE ROWS.
//
// The whole value of a version is somebody else reading it. The path this has
// to survive is a hiker on a phone, in a browser, typing a commit hash into an
// email with cold hands - and seven characters of hex is exactly the kind of
// thing that arrives with a digit changed. The button is not a convenience; it
// is what makes the answer arrive intact. The rows stay visible either way,
// so a browser that refuses the clipboard costs accuracy, not the feature.
//
// WHERE IT SITS: below every group a hiker can change, and above the download
// link rather than below it. Convention would put About dead last, but the
// download link already holds the foot of this screen deliberately - it is the
// only way to the download, and Settings.tsx's own comment gives it that spot
// so it is what anyone scrolling to the bottom lands on. Six rows of reference
// material after it would take that away, and this is the one section here
// nobody arrives looking for.

import { useState } from 'react'
import { BUILD_INFO, buildSummary, builtAtLabel, type BuildInfo } from '../lib/buildInfo'

export interface AboutBuildProps {
  /**
   * Which build this is. Defaults to the real one, and is injectable so the
   * rows can be tested against fixed values - the actual constants are a live
   * commit and the clock at build time, so a test asserting on them would be
   * asserting on when it happened to run.
   */
  build?: BuildInfo
}

type CopyState = 'idle' | 'copied' | 'failed'

export function AboutBuild({ build = BUILD_INFO }: AboutBuildProps) {
  const [copyState, setCopyState] = useState<CopyState>('idle')

  const copy = async () => {
    try {
      // Not `navigator.clipboard?.writeText(...)`. Optional chaining would
      // yield undefined, `await undefined` resolves happily, and the button
      // would report a copy that never happened - on precisely the browsers
      // where it did not.
      await navigator.clipboard.writeText(buildSummary(build))
      setCopyState('copied')
    } catch {
      setCopyState('failed')
    }
  }

  return (
    <section className="settings__group">
      <h2 className="settings__heading">About this build</h2>

      <p className="settings__row">
        <span className="settings__label">Version</span>
        <span className="settings__value">{build.version}</span>
      </p>

      <p className="settings__row">
        <span className="settings__label">Commit</span>
        <span className="settings__value settings__value--code">{build.shortCommit}</span>
      </p>

      <p className="settings__row">
        <span className="settings__label">Built</span>
        <span className="settings__value">{builtAtLabel(build.builtAt)}</span>
      </p>

      <button type="button" className="settings__action" onClick={copy}>
        Copy build details
      </button>

      {/* Announced, because the button's own label cannot change to report
          what happened - it has to keep saying what it does. A failure says
          what to do instead rather than only that it failed: the three rows
          are right there, which is the whole reason they are not hidden
          behind the button. */}
      {copyState !== 'idle' && (
        <p className="settings__note" role="status">
          {copyState === 'copied'
            ? 'Copied.'
            : 'This browser would not let the app use the clipboard. The three lines above are the same thing.'}
        </p>
      )}

      {!build.isRelease && (
        // Said plainly, because "0.0.0" looks like a version number somebody
        // could look up and is not one. A build off `main`, a pull request
        // preview and a laptop all carry it (RELEASING.md §13), and for every
        // one of them the commit is the only thing that identifies the build.
        <p className="settings__note">
          This build was never tagged as a release, so the commit is what identifies it.
        </p>
      )}

      {/* The copy button is still the path for an email or a message to a
          club. Report a bug, directly below, needs no copying at all - it
          carries these three lines into the form itself (lib/bugReport.ts,
          #626) - and saying so is what stops this note reading as the only
          way to do it. */}
      <p className="settings__note">
        Worth quoting if you report a problem with the app itself — it says exactly which
        build you were looking at. Report a bug, below, carries these three lines for you.
      </p>
    </section>
  )
}
