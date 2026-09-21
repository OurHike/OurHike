// What the account button opens when a hiker is ALREADY signed in (#1596).
//
// THE HOLE THIS FILLS. The button was one control in two states - a hollow
// glyph signed out, a filled one signed in - and both states opened
// `SignInPrompt`. Signed in that is a dead end: the window offers "Continue
// with GitHub / Google / email" for an account you already have, and the one
// thing you came for is not there. Signing out lived, and still lives, on
// More -> You. chrome/AccountButton.tsx asserted the opposite in a comment
// ("Signed in, it opens the same window, which is where signing out lives")
// and AccountButton.test.tsx wrote that sentence into a test NAME while
// asserting only that `onOpen` fired, so the claim was never checked. The
// review of #1596 found it.
//
// SMALL, AND NOT A SECOND SETTINGS SCREEN. Everything else about an account
// - sync, export, deletion, the trail name - is on More -> You and stays
// there: one home per item. This answers the two questions a hiker taps a
// filled glyph to ask, "who am I signed in as" and "let me out", and hands
// the rest over with a line that says where it is.
//
// THE ADDRESS IS SHOWN, which is the same call AccountButton's `aria-label`
// makes: on a shared or borrowed handset the answer to "whose account is
// this" is the account's name, and a glyph cannot carry it. Nothing else
// here is personal, and the preview's browser never signs in, so no recipe
// can photograph one (features/HIKER_SAFETY.md's rule for shots).

export interface AccountPanelProps {
  /** The signed-in account. This view is not rendered signed out. */
  account: { email: string }
  /** Sign out, and forget this device's claim to have synced with the
   *  account - App.tsx's `handleSignOut` is what does the second half, at
   *  length and for the reason #891, #892 and #1035 each give. */
  onSignOut: () => void
  /** Leave the window with nothing changed. */
  onClose: () => void
}

export function AccountPanel({ account, onSignOut, onClose }: AccountPanelProps) {
  return (
    <div className="reporting">
      <h2 className="reporting__title">Your account</h2>

      {/* `aria-label` rather than a visible label: the heading above already
          says what this is, and "Signed in as" in front of the address would
          be a third line saying it a third time. */}
      <p className="reporting__meta" aria-label={`Signed in as ${account.email}`}>
        {account.email}
      </p>

      <div className="reporting__actions">
        <button type="button" className="reporting__secondary" onClick={onSignOut}>
          Sign out
        </button>
        <button type="button" className="reporting__secondary" onClick={onClose}>
          Not now
        </button>
      </div>

      {/* Where the rest is, rather than a copy of it here. Worded as a fact
          about the app and not as a link, because it is not one: this window
          closes over whatever screen raised it, and sending a hiker to More
          from here would take away the map the ask was made over - which is
          the thing #1596 exists to stop. */}
      <p className="reporting__unavailable">
        Syncing, your trail name and deleting your account are in More → You.
      </p>
    </div>
  )
}
