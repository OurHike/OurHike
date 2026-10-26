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

import { useEffect, useState } from 'react'
import { API_CONFIGURED } from '../lib/api'
import { activeDaysThisYear, recordActiveDay } from '../lib/activeDays'
import { shouldAsk, supportSummaryLine } from '../lib/support'
import { holdPendingSupportTier, takePendingSupportTier } from '../lib/supportPending'
import { useSupport } from '../lib/useSupport'
import { SupportAsk, type AskView } from './SupportAsk'

// Re-exported so screens/deferred.ts loads the page from this same chunk.
export { YourSupportPage } from './YourSupport'

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
}

export function SupportGate({
  accountEmail,
  online,
  held,
  openRequest,
  onSignIn,
  onSummary,
}: SupportGateProps) {
  const signedIn = accountEmail !== null
  const support = useSupport(signedIn)
  const [days, setDays] = useState(() => activeDaysThisYear(new Date()))
  const [ask, setAsk] = useState<AskView | null>(null)

  // EVENTING.md §2's "active": a foreground session with at least one hiker
  // interaction. The first pointer or key event after this mounts counts
  // today; `recordActiveDay` is idempotent, so a second one adds nothing.
  useEffect(() => {
    const count = () => setDays(recordActiveDay(new Date()))
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
    if (openRequest > 0) setAsk({ kind: 'choose' })
  }, [openRequest])

  useEffect(() => {
    if (ask !== null || held) return
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
    if (!support.settled) return
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
  }, [ask, held, signedIn, online, days, support.settled, support.server, support.local])

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
