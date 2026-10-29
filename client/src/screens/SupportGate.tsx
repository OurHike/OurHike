// Everything the day-5 ask needs, behind one deferred import (#1876).
//
// WHY IT IS ONE COMPONENT AND NOT HOOKS IN THE SHELL. The shell is the
// launch closure, and main sat 290 bytes under LAUNCH_BUDGET.md §3's line
// when this landed (245,470 of 245,760, `check:build` on origin/main,
// 2026-10-24). The day counter, the account fetch and the ask decision
// were hooks in App.tsx first and cost 1,763 eager bytes with the screens
// already deferred. Here they load after the first frame, from
// screens/deferred.ts, and the shell keeps two pieces of state: a request
// counter for "Choose an amount", and the More row's line.
//
// WHAT IT DECIDES is lib/support.ts's `shouldAsk`; what it renders is the
// window from screens/SupportAsk.tsx, or nothing.
//
// IT DECIDES ONCE PER LAUNCH, AND ONLY NEAR THE START OF ONE (the third
// #1885 review). The ask used to re-decide whenever the day count, the
// signal or the account answer changed - so on day five it opened at the
// hiker's first tap, under their finger, and a signal returning mid-hike
// opened it over the map they were reading. Now: the count is the one this
// launch reaches (`daysIncludingToday`, read at mount), the decision is
// taken the first time the account answer has settled and nothing holds
// the screen, and not at all after `ASK_WINDOW_MS`. A launch that does not
// ask leaves it to the next launch.
//
// AND ONLY ON AN ANSWER IT CAN STAND BEHIND (the fourth #1885 review):
//   - "Signed out" is not decided from App.tsx's account alone, which is
//     null until supabase-js hands a stored session back - after a network
//     token refresh on any launch more than an hour after the last. That
//     asked a hiker paying $60 a year. The gate reads the stored session
//     itself and decides once it knows.
//   - A hiker who has tapped or typed since this mounted is using the app,
//     and the ask does not open under them. Taps before this chunk loads are
//     not seen; the window between first frame and here is the gap.
//   - The server has to be taking paid choices: `can_choose` for an
//     account, `supportAccepting()` for nobody. A required question every
//     paid answer to which fails is worse than no question.

import { useEffect, useRef, useState } from 'react'
import { API_CONFIGURED } from '../lib/api'
import { daysIncludingToday, localDate, recordActiveDay } from '../lib/activeDays'
import { currentAccount } from '../lib/auth'
import { usePaidChoiceAllowed } from '../lib/storefront'
import { shouldAsk, supportSummaryLine } from '../lib/support'
import { supportAccepting } from '../lib/supportApi'
import { holdPendingSupportTier, takePendingSupportTier } from '../lib/supportPending'
import { useSupport } from '../lib/useSupport'
import { SupportAsk, type AskView } from './SupportAsk'

// Re-exported so screens/deferred.ts loads the page from this same chunk.
export { YourSupportPage } from './YourSupport'

// @unvalidated: fifteen seconds is a guess at "still the moment the app
// came up, not yet the middle of something". What would settle it is how
// long a launch takes to reach the map on a slow phone with one bar.
export const ASK_WINDOW_MS = 15_000

export interface SupportGateProps {
  /** The signed-in account's email, or null when signed out. */
  accountEmail: string | null
  online: boolean
  /**
   * True while something the ask must not cover is up: first run, a flow a
   * hiker is typing into, the sign-in window. The ask waits for it to close.
   */
  held: boolean
  /** Bumped by the shell each time a hiker presses "Choose an amount". */
  openRequest: number
  /** Open the shell's sign-in window. */
  onSignIn: () => void
  /** The More row's second line, whenever it changes. */
  onSummary: (line: string) => void
  /** "Share usage statistics" on this phone - App.tsx's preference. */
  usageCounts: boolean
  /** Whether a paid choice may be offered here; null while the store is
   *  asked. Injected for tests; lib/storefront.ts's answer otherwise. */
  paidAllowed?: boolean | null
  /** Injected for tests: whether a stored session exists, however slowly
   *  it is read. lib/auth.ts's `currentAccount` otherwise. */
  storedAccount?: () => Promise<unknown>
  /** Injected for tests: whether the server takes a paid choice, asked
   *  for a signed-out hiker. lib/supportApi.ts's `supportAccepting` otherwise. */
  accepting?: () => Promise<boolean>
}

export function SupportGate({
  accountEmail,
  online,
  held,
  openRequest,
  onSignIn,
  onSummary,
  usageCounts,
  paidAllowed: injected,
  storedAccount = currentAccount,
  accepting = supportAccepting,
}: SupportGateProps) {
  const asked = usePaidChoiceAllowed()
  // A store app on a non-US account never asks (the maintainer, 2026-10-27:
  // a required choice with one answer is a sheet over the map for nothing).
  const paidAllowed = injected === undefined ? asked : injected
  const signedIn = accountEmail !== null
  const support = useSupport(signedIn)
  const [days] = useState(() => daysIncludingToday(new Date()))
  const [mountedAt] = useState(() => Date.now())
  const decided = useRef(false)
  const touched = useRef(false)
  const [ask, setAsk] = useState<AskView | null>(null)
  // Null while the stored session is being read; then whether there is one.
  const [stored, setStored] = useState<boolean | null>(null)
  const accountKnown = signedIn || stored === false

  useEffect(() => {
    let live = true
    storedAccount().then(
      (account) => {
        if (live) setStored(account !== null)
      },
      () => {
        if (live) setStored(false)
      },
    )
    return () => {
      live = false
    }
  }, [storedAccount])

  // EVENTING.md §2's "active": a foreground session with at least one hiker
  // interaction. The first pointer or key event of each local date counts
  // that date - not only the first after mount, because a phone keeps a
  // backgrounded app in memory overnight and the next morning's taps are
  // the same launch (the fourth #1885 review).
  useEffect(() => {
    let counted = ''
    const count = () => {
      touched.current = true
      const now = new Date()
      const today = localDate(now)
      if (today === counted) return
      counted = today
      recordActiveDay(now)
    }
    window.addEventListener('pointerdown', count, { capture: true })
    window.addEventListener('keydown', count, { capture: true })
    return () => {
      window.removeEventListener('pointerdown', count, { capture: true })
      window.removeEventListener('keydown', count, { capture: true })
    }
  }, [])

  useEffect(() => {
    onSummary(supportSummaryLine(support.server, support.local, new Date()))
  }, [support.server, support.local, onSummary])

  // "Choose an amount" on More → Your support. Zero is the shell's starting
  // value, so a mount alone opens nothing.
  useEffect(() => {
    if (openRequest > 0 && paidAllowed === true) {
      // Opened at the top, so a tier held for an abandoned sign-in is not
      // the hiker's answer any more.
      takePendingSupportTier()
      setAsk({ kind: 'choose' })
    }
  }, [openRequest, paidAllowed])

  useEffect(() => {
    if (ask !== null || held || paidAllowed !== true) return
    if (!accountKnown || !support.settled) return
    // Back from signing in with a paid tier already picked: pick up at the
    // confirmation rather than at the top - unless the account's answer
    // says no new choice would be taken (it pays already, or support is
    // off). In this effect rather than one of its own, because two effects
    // setting the same state in one commit let the later one win, and that
    // was the ask reopening at the top. Not held to `touched`: the hiker
    // asked for this by pressing "Sign in to continue".
    if (signedIn) {
      const tier = takePendingSupportTier()
      if (tier !== null) {
        if (support.server?.can_choose !== false) setAsk({ kind: 'confirm', tier })
        return
      }
    }
    if (decided.current) return
    decided.current = true
    if (touched.current || Date.now() - mountedAt > ASK_WINDOW_MS) return
    // Signed in and the account could not be read, or it says no choice
    // would be taken: it may already be paying, and asking a supporter to
    // choose again is the one wrong ask.
    if (signedIn && support.server?.can_choose !== true) return
    if (
      !shouldAsk({
        now: new Date(),
        apiConfigured: API_CONFIGURED,
        online,
        server: support.server,
        days,
        local: support.local,
      })
    ) {
      return
    }
    takePendingSupportTier()
    if (signedIn) {
      setAsk({ kind: 'choose' })
      return
    }
    void accepting().then((yes) => {
      if (yes && !touched.current && Date.now() - mountedAt <= ASK_WINDOW_MS) {
        setAsk((open) => open ?? { kind: 'choose' })
      }
    })
  }, [
    ask,
    held,
    paidAllowed,
    accountKnown,
    signedIn,
    online,
    days,
    mountedAt,
    accepting,
    support.settled,
    support.server,
    support.local,
  ])

  if (ask === null || held) return null
  return (
    <SupportAsk
      days={days}
      accountEmail={accountEmail}
      initial={ask}
      onSignIn={(tier) => {
        holdPendingSupportTier(tier)
        setAsk(null)
        onSignIn()
      }}
      onChosen={support.replace}
      onClose={() => {
        // Answered or sent on: a tier still held from an abandoned sign-in
        // must not reopen the window at its confirmation later.
        takePendingSupportTier()
        setAsk(null)
      }}
      usageCounts={usageCounts}
    />
  )
}
