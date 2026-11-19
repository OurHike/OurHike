import { useEffect, useState } from 'react'
import { useAccount } from '../account'
import type { SharedList } from '../api'
import { SignInForm } from '../components/SignInForm'
import { siteName } from '../format'
import { siteHref } from '../route'
import type { Site } from '../types'

/** A list someone shared. Read-only, and sign-in first (PLAN.md §8). */
export function SharedScreen({ token, sites }: { token: string; sites: Site[] }) {
  const { api } = useAccount()
  const [list, setList] = useState<SharedList | null>(null)
  const [problem, setProblem] = useState<string | null>(null)

  useEffect(() => {
    if (!api) return
    let live = true
    api.openShared(token).then(
      (found) => live && setList(found),
      (error: Error) => live && setProblem(error.message),
    )
    return () => {
      live = false
    }
  }, [api, token])

  if (!api) {
    return (
      <section className="card">
        <h1 style={{ fontSize: 28, marginBottom: 10 }}>A shared list</h1>
        <SignInForm why="Someone shared a list of sites with you. Sign in to open it." />
      </section>
    )
  }
  if (problem) {
    return (
      <section className="card" role="alert">
        <h1 style={{ fontSize: 24 }}>This link does not open a list</h1>
        <p>{problem}</p>
      </section>
    )
  }
  if (!list) return <p className="muted">Opening the list…</p>
  const byId = new Map(sites.map((s) => [s.rims_id, s]))
  return (
    <section
      className="card"
      style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
    >
      <span className="eyebrow">
        Shared with you{list.owner ? ` by ${list.owner}` : ''}
      </span>
      <h1 style={{ fontSize: 28 }}>{list.name}</h1>
      <ol style={{ margin: 0, paddingLeft: 22 }}>
        {list.rims_ids.map((rimsId) => {
          const site = byId.get(rimsId)
          return (
            <li key={rimsId}>
              {site ? (
                <>
                  <a href={siteHref(rimsId)}>{siteName(site)}</a>
                  <span className="muted">
                    {' '}
                    · {site.club ?? 'Club not recorded'}
                    {site.mile !== null && ` · mile ${site.mile.toFixed(1)}`}
                    {site.tier && ` · ${site.tier}`}
                  </span>
                </>
              ) : (
                <span className="muted">
                  A site no longer in ATC's inventory ({rimsId})
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
