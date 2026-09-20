// The way in to an account, and the way back to it, on every screen (#1596).
//
// WHY THIS EXISTS AT ALL, since the app deliberately does not ask. Until now
// the only deliberate way in was More → You → Sign in: three taps, in the
// settings tab, under a row nobody opens unless they already suspect an
// account is there. Every other door was incidental - five contribution
// flows that open the same ask with `afterReport: true`, which is a
// different sentence ("your report is saved; signing in is what lets it
// reach someone").
//
// WHAT IT IS NOT. Not a wall, and the distinction is the whole design.
// Nothing here gates anything: every screen reachable signed out before is
// reachable signed out after, the callout naming what stays free without an
// account is untouched, and FEATURES.md's no-signup-wall commitment holds.
// #393 warns that gating BROWSING behind sign-in would be the most expensive
// product decision available to this project, because it moves every reader
// onto the metered line. A door nobody is forced through does not.
//
// It lives in chrome/Header.tsx's action cluster beside Legend and Search,
// which is already this app's top-right home for tools, and in Today's own
// chrome - so it is one tap from the two screens a launch can land on.
//
// NOT FROM EVERY SCREEN, which an earlier version of this line claimed. On a
// phone the Plan and More tabs draw over the map, so the header's copy is
// inert and Today's is not mounted; the way in from there is the one that
// always existed, More -> You. The three places below are the map, Today and
// the sidebar, and those are the three.
//
// ONE OF THESE IS DRAWN, NEVER TWO, and where depends on the layout because
// the layouts differ in how many screens they draw at once:
//
//   below 900px  the map header's cluster, and Today's own chrome. One
//                screen is up at a time, so a hiker sees one button.
//   at or above  the sidebar's top-left corner (chrome/TabBar.tsx), and
//                neither of the other two. Today and the map are side by
//                side up here, so both of those were on the page together -
//                the maintainer's report, 2026-09-20, #1596.
//
// Each of the three reads `useDesktop()` and decides for itself. Doing it in
// the stylesheet instead left all three in the DOM with two of them
// `display: none` - gone from a browser's accessibility tree, still there in
// jsdom, which loads no stylesheet and duly found three buttons named
// "Sign in" in App.flows.test.tsx. useDesktop.ts's own docstring is the
// general form of that: "a few things cannot be done in CSS".

export interface AccountButtonProps {
  /** Null when signed out, which is the state this whole app works in. */
  account: { email: string } | null
  /** Opens the account window. ONE CONTROL, TWO STATES, ONE WINDOW: signed
   *  out it opens the ask (screens/SignInPrompt.tsx), signed in it opens
   *  chrome/AccountPanel.tsx, which says who you are signed in as and signs
   *  you out. That second half is why this docstring is worth reading: the
   *  sentence was here before the panel was, so the filled glyph opened the
   *  SIGN-IN ask - providers for an account the hiker already had, and no
   *  way out - and AccountButton.test.tsx wrote this claim into a test name
   *  while asserting only that `onOpen` fired. The review of #1596 found it.
   *  App.tsx picks the view; this button does not change what it does. */
  onOpen: () => void
  /** The header passes its own button class so this matches Legend and
   *  Search exactly; Today passes its own. Neither should have to restate
   *  the glyph. */
  className?: string
}

export function AccountButton({ account, onOpen, className }: AccountButtonProps) {
  const signedIn = account !== null
  return (
    <button
      type="button"
      className={className}
      onClick={onOpen}
      // THE ADDRESS IS IN THE LABEL, and deliberately: a screen reader user
      // gets the same answer a sighted one reads off the filled glyph, which
      // is "you are signed in, and as whom". The glyph alone cannot say the
      // second half.
      aria-label={signedIn ? `Account, signed in as ${account.email}` : 'Sign in'}
    >
      <svg aria-hidden="true" viewBox="0 0 24 24" width="20" height="20">
        {/* One person glyph in two weights rather than two glyphs: the shape
            a hiker learns stays put, and only its fill changes with the
            state. Stroke-only reads as an empty seat; filled reads as taken. */}
        <circle
          cx="12"
          cy="8"
          r="3.5"
          fill={signedIn ? 'currentColor' : 'none'}
          stroke="currentColor"
          strokeWidth="2"
        />
        <path
          d="M4.5 20c0-4 3.4-6.5 7.5-6.5s7.5 2.5 7.5 6.5"
          fill={signedIn ? 'currentColor' : 'none'}
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
        />
      </svg>
    </button>
  )
}
