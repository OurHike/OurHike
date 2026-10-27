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

import { useEffect, useRef, useState } from 'react'
import { API_CONFIGURED } from '../lib/api'
import { daysIncludingToday, recordActiveDay } from '../lib/activeDays'
import { usePaidChoiceAllowed } from '../lib/storefront'
import { shouldAsk, supportSummaryLine } from '../lib/support'
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
  /** Whether a paid choice may be offered here; null while the store is
   *  asked. Injected for tests; lib/storefront.ts's answer otherwise. */
  paidAllowed?: boolean | null
}

export function SupportGate({
  accountEmail,
  online,
  held,
  openRequest,
  onSignIn,
  onSummary,
  paidAllowed: injected,
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
  const [ask, setAsk] = useState<AskView | null>(null)

  // EVENTING.md §2's "active": a foreground session with at least one hiker
  // interaction. The first pointer or key event after this mounts counts
  // today; `recordActiveDay` is idempotent, so a second one adds nothing.
  useEffect(() => {
    const count = () => {
      recordActiveDay(new Date())
    }
    window.addEventListener('pointerdown', count, { once: true, capture: true })
    window.addEventListener('keydown', count, { once: true, capture: true })
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
    if (openRequest > 0 && paidAllowed === true) setAsk({ kind: 'choose' })
  }, [openRequest, paidAllowed])

  useEffect(() => {
    if (ask !== null || held || paidAllowed !== true) return
    // Back from signing in with a paid tier already picked: pick up at the
    // confirmation rather than at the top. In this effect rather than one
    // of its own, because two effects setting the same state in one commit
    // let the later one win, and that was the ask reopening at the top.
    if (signedIn) {
      const tier = takePendingSupportTier()
      if (tier !== null) {
        setAsk({ kind: 'confirm', tier })
        return
      }
    }
    if (decided.current || !support.settled) return
    decided.current = true
    if (Date.now() - mountedAt > ASK_WINDOW_MS) return
    // Signed in and the account could not be read: it may already be paying,
    // and asking a supporter to choose again is the one wrong ask.
    if (signedIn && support.server === null) return
    if (
      shouldAsk({
        now: new Date(),
        apiConfigured: API_CONFIGURED,
        online,
        server: support.server,
        days,
        local: support.local,
      })
    ) {
      setAsk({ kind: 'choose' })
    }
  }, [
    ask,
    held,
    paidAllowed,
    signedIn,
    online,
    days,
    mountedAt,
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
      onClose={() => setAsk(null)}
    />
  )
}
