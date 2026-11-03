// The support state the shell and More → Your support read (#1876): the
// account's paid choice from the backend, and this phone's $0 answer.
//
// Fetched when signed in and a backend is configured, and again whenever
// the window regains focus - which is the moment a hiker comes back from
// the provider's checkout in another tab, or from the email the store
// apps send. A failed fetch leaves the last answer standing and `error`
// set; it never invents a status, because `shouldAsk` reads null as "no
// account answer" and a guessed `none` would ask somebody who already pays.

import { useCallback, useEffect, useState } from 'react'
import { API_CONFIGURED } from './api'
import { fetchSupport } from './supportApi'
import {
  onLocalChoiceChanged,
  readLocalChoice,
  type LocalChoice,
  type SupportSummary,
} from './support'

export interface SupportState {
  /** Null when signed out, unconfigured, or not fetched yet. */
  server: SupportSummary | null
  /** This phone's $0 answer, if any. */
  local: LocalChoice | null
  /** True once the first fetch for this account has settled either way, so
   *  the ask does not open on a signed-in hiker before their answer is in. */
  settled: boolean
  error: boolean
  /** Fetch again now, e.g. after a choice or a Stop. */
  refresh: () => void
  /** Replace the server answer with one an action just returned. */
  replace: (next: SupportSummary) => void
}

/**
 * Fired on this window when an action answers a new summary. The ask's gate
 * and the Your support page each hold a `useSupport`; a Stop on the page
 * used to leave the More row reading "$60 a year" until the window next
 * gained focus (the fourth #1885 review). Every instance takes the answer.
 */
const SUMMARY_CHANGED = 'ourhike:support-summary'

export function useSupport(signedIn: boolean): SupportState {
  const [server, setServer] = useState<SupportSummary | null>(null)
  const [local, setLocal] = useState<LocalChoice | null>(readLocalChoice)
  const wanted = signedIn && API_CONFIGURED
  // Which answer `settled` is about: false for "nobody to fetch", true for
  // the signed-in account's fetch. A plain boolean stayed true for one
  // render after a sign-in landed - the signed-out answer - and the ask
  // decided on it with no account answer yet (the fourth #1885 review).
  const [settledFor, setSettledFor] = useState<boolean | null>(wanted ? null : false)
  const [error, setError] = useState(false)
  const [generation, setGeneration] = useState(0)

  const refresh = useCallback(() => setGeneration((n) => n + 1), [])

  useEffect(() => onLocalChoiceChanged(() => setLocal(readLocalChoice())), [])

  useEffect(() => {
    const take = (event: Event) => {
      const next = (event as CustomEvent<SupportSummary>).detail
      if (next !== undefined && next !== null) setServer(next)
    }
    window.addEventListener(SUMMARY_CHANGED, take)
    return () => window.removeEventListener(SUMMARY_CHANGED, take)
  }, [])

  const replace = useCallback((next: SupportSummary) => {
    window.dispatchEvent(new CustomEvent(SUMMARY_CHANGED, { detail: next }))
  }, [])

  useEffect(() => {
    if (!signedIn || !API_CONFIGURED) {
      setServer(null)
      setSettledFor(false)
      return
    }
    const abort = new AbortController()
    fetchSupport(abort.signal)
      .then((summary) => {
        setServer(summary)
        setError(false)
      })
      .catch(() => {
        if (!abort.signal.aborted) setError(true)
      })
      .finally(() => {
        if (!abort.signal.aborted) setSettledFor(true)
      })
    return () => abort.abort()
  }, [signedIn, generation])

  useEffect(() => {
    if (!signedIn || !API_CONFIGURED) return
    window.addEventListener('focus', refresh)
    return () => window.removeEventListener('focus', refresh)
  }, [signedIn, refresh])

  return { server, local, settled: settledFor === wanted, error, refresh, replace }
}
