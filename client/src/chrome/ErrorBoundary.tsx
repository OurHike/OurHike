// The thing that stops one broken screen becoming a broken app.
//
// React's default for an error thrown in render, in an effect, or in an
// effect's CLEANUP is to unmount the entire root - not the component that
// threw, the whole tree, tab bar included. #131 did exactly that: a stale
// `removeControl` threw during cleanup on every tab switch away from the map,
// and what the hiker saw was a white page with no navigation on it. The
// reported symptom was "the download tab shows nothing"; the cause was three
// lines away in mapChrome.ts, and the distance between those two facts is what
// this file exists to close.
//
// Three decisions are baked in here, and all three are choices rather than
// defaults:
//
// **The tab bar stays under the fallback.** A fallback you cannot navigate out
// of is a white screen with words on it. Whatever else has gone wrong, the map
// has to be one tap away.
//
// **No reload button.** A reload is the obvious thing to offer and the wrong
// thing here: it happens with no signal, against a service worker, on the
// battery that gets someone home. Switching tabs and coming back remounts the
// screen anyway, costs nothing, and is what the tab bar below already does.
//
// **Nothing is recorded.** There is no telemetry in this client, and adding
// some carries its own privacy weight (features/IDENTITY_AND_PRIVACY.md), so
// this is a deliberate no rather than an oversight. The error still reaches
// console.error, which is where a developer looks and a hiker never does.

import { Component, type ErrorInfo, type ReactNode } from 'react'

export interface ErrorBoundaryProps {
  children: ReactNode
  /**
   * What replaces the subtree when it throws. A render prop rather than an
   * element so the shell can keep its own chrome - the tab bar in particular -
   * around whatever this says.
   */
  fallback: (error: Error) => ReactNode
  /**
   * Changing this resets the boundary, so a hiker who navigates away and back
   * gets a real attempt rather than the fallback again. Without it a screen
   * that threw once stays broken for the life of the app.
   */
  resetKey?: unknown
}

interface ErrorBoundaryState {
  error: Error | null
  /** The key the current error belongs to, so a change to it can be seen. */
  resetKey: unknown
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  state: ErrorBoundaryState = { error: null, resetKey: this.props.resetKey }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { error }
  }

  /**
   * Clears the error when the reset key changes, during render rather than
   * after it - the same update that navigates away drops the error, so the
   * fallback never renders a frame for a screen the hiker has already left.
   *
   * The comparison is against the key held in state, not a previous prop:
   * clearing on every update would re-render the subtree that just threw,
   * which throws again, forever.
   */
  static getDerivedStateFromProps(
    props: ErrorBoundaryProps,
    state: ErrorBoundaryState,
  ): Partial<ErrorBoundaryState> | null {
    if (props.resetKey === state.resetKey) return null
    return { error: null, resetKey: props.resetKey }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Logged, not sent. See the note at the top of this file.
    console.error('A screen failed and was replaced with a fallback.', error, info)
  }

  render(): ReactNode {
    const { error } = this.state
    return error === null ? this.props.children : this.props.fallback(error)
  }
}

/**
 * What a broken screen says.
 *
 * Written to be true rather than reassuring: something is wrong, the app knows
 * it, and the rest of it still works. No apology, no "unexpected error", and
 * no detail a hiker cannot act on - HIKER_SAFETY.md's rule is that the app does
 * not mislead, and "Something went wrong" with a shrug is misleading about how
 * much is still available.
 */
export function ScreenFailed({ what }: { what: string }) {
  return (
    <div className="screen-failed" role="alert">
      <h1 className="screen-failed__title">{what} stopped working</h1>
      <p className="screen-failed__body">
        The rest of the app is fine. Switching tabs and coming back will start this screen
        again.
      </p>
      <p className="screen-failed__body screen-failed__body--quiet">
        Your downloaded map and anything waiting in your outbox are untouched.
      </p>
    </div>
  )
}
