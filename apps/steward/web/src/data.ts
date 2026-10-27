import { useEffect, useState } from 'react'
import type { Site, Summary } from './types'

/** Serve the invented sites in src/fixtures.ts instead of the job's files: tests and screenshots. */
export const USE_FIXTURES = import.meta.env.VITE_STEWARD_FIXTURES === '1'

export interface StewardData {
  summary: Summary
  sites: Site[]
}

export type Loaded =
  | { state: 'loading' }
  | { state: 'ready'; data: StewardData }
  | { state: 'failed'; message: string }

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) throw new Error(`${path} answered ${response.status}`)
  return (await response.json()) as T
}

/** The job's two files, served beside the app under data/ (PLAN.md §2g). */
export async function loadData(): Promise<StewardData> {
  if (USE_FIXTURES) {
    const { fixtureSites, fixtureSummary } = await import('./fixtures')
    return { summary: fixtureSummary, sites: fixtureSites }
  }
  const [summary, sites] = await Promise.all([
    fetchJson<Summary>('data/summary.json'),
    fetchJson<Site[]>('data/sites.json'),
  ])
  return { summary, sites }
}

export function useStewardData(load: () => Promise<StewardData> = loadData): Loaded {
  const [loaded, setLoaded] = useState<Loaded>({ state: 'loading' })
  useEffect(() => {
    let live = true
    load().then(
      (data) => live && setLoaded({ state: 'ready', data }),
      (error: unknown) => live && setLoaded({ state: 'failed', message: String(error) }),
    )
    return () => {
      live = false
    }
  }, [load])
  return loaded
}
