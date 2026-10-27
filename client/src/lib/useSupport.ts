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

export function useSupport(signedIn: boolean): SupportState {
  const [server, setServer] = useState<SupportSummary | null>(null)
  const [local, setLocal] = useState<LocalChoice | null>(readLocalChoice)
  const [settled, setSettled] = useState(!signedIn || !API_CONFIGURED)
  const [error, setError] = useState(false)
  const [generation, setGeneration] = useState(0)

  const refresh = useCallback(() => setGeneration((n) => n + 1), [])

  useEffect(() => onLocalChoiceChanged(() => setLocal(readLocalChoice())), [])

  useEffect(() => {
    if (!signedIn || !API_CONFIGURED) {
      setServer(null)
      setSettled(true)
      return
    }
    const abort = new AbortController()
    setSettled(false)
    fetchSupport(abort.signal)
      .then((summary) => {
        setServer(summary)
        setError(false)
      })
      .catch(() => {
        if (!abort.signal.aborted) setError(true)
      })
      .finally(() => {
        if (!abort.signal.aborted) setSettled(true)
      })
    return () => abort.abort()
  }, [signedIn, generation])

  useEffect(() => {
    if (!signedIn || !API_CONFIGURED) return
    window.addEventListener('focus', refresh)
    return () => window.removeEventListener('focus', refresh)
  }, [signedIn, refresh])

  return { server, local, settled, error, refresh, replace: setServer }
}
