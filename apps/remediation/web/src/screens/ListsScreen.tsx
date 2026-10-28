import { useCallback, useEffect, useState } from 'react'
import { useAccount } from '../account'
import type { ListDetail, ListSummary } from '../api'
import { SignInForm } from '../components/SignInForm'
import { siteName } from '../format'
import { sharedHref, siteHref } from '../route'
import type { Site } from '../types'

export function ListsScreen({ sites }: { sites: Site[] }) {
  const { api } = useAccount()
  const [lists, setLists] = useState<ListSummary[] | null>(null)
  const [problem, setProblem] = useState<string | null>(null)

  const reload = useCallback(() => {
    if (!api) return
    api.lists().then(setLists, (error: Error) => setProblem(error.message))
  }, [api])
  useEffect(reload, [reload])

  if (!api) {
    return (
      <section className="card">
        <h1 style={{ fontSize: 28, marginBottom: 10 }}>Your lists</h1>
        <SignInForm why="Sign in to keep lists of sites and share them with your crew." />
      </section>
    )
  }
  return (
    <>
      <h1 style={{ fontSize: 28 }}>Your lists</h1>
      {problem && <p role="alert">{problem}</p>}
      {lists === null ? (
        <p className="muted">Loading…</p>
      ) : lists.length === 0 ? (
        <p className="card" style={{ margin: 0 }}>
          No lists yet. Save a site from its page to start one.
        </p>
      ) : (
        lists.map((summary) => (
          <OneList key={summary.id} id={summary.id} sites={sites} onChange={reload} />
        ))
      )}
    </>
  )
}

function OneList({
  id,
  sites,
  onChange,
}: {
  id: string
  sites: Site[]
  onChange: () => void
}) {
  const { api } = useAccount()
  const [list, setList] = useState<ListDetail | null>(null)
  const [link, setLink] = useState<string | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [name, setName] = useState('')

  useEffect(() => {
    if (!api) return
    api.list(id).then(
      (found) => {
        setList(found)
        setName(found.name)
      },
      (error: Error) => setProblem(error.message),
    )
  }, [api, id])

  if (!api || !list) return problem ? <p role="alert">{problem}</p> : null
  const byId = new Map(sites.map((s) => [s.rims_id, s]))

  const act = async (step: () => Promise<unknown>) => {
    try {
      await step()
      setProblem(null)
    } catch (error) {
      setProblem((error as Error).message)
    }
  }
  const refresh = async () => setList(await api.list(id))

  return (
    <section
      className="card"
      aria-label={list.name}
      style={{ display: 'flex', flexDirection: 'column', gap: 10 }}
    >
      <form
        style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}
        onSubmit={(e) => {
          e.preventDefault()
          void act(async () => {
            setList(await api.renameList(id, name.trim()))
            onChange()
          })
        }}
      >
        <input
          aria-label="List name"
          maxLength={80}
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{
            font: '600 18px var(--display)',
            flex: '1 1 200px',
            padding: '6px 8px',
          }}
        />
        {name.trim() !== list.name && (
          <button type="submit" className="button">
            Rename
          </button>
        )}
        <span className="muted">{list.rims_ids.length} sites</span>
      </form>
      {list.rims_ids.length > 0 && (
        <ul style={{ margin: 0, paddingLeft: 20 }}>
          {list.rims_ids.map((rimsId) => {
            const site = byId.get(rimsId)
            return (
              <li key={rimsId}>
                {site ? (
                  <a href={siteHref(rimsId)}>{siteName(site)}</a>
                ) : (
                  <span className="muted">
                    A site no longer in ATC's inventory ({rimsId})
                  </span>
                )}
                {site?.tier && <span className="muted"> · {site.tier}</span>}{' '}
                <button
                  type="button"
                  className="button"
                  style={{ minHeight: 28, padding: '2px 8px', fontSize: 13 }}
                  onClick={() =>
                    void act(async () => {
                      await api.removeFromList(id, rimsId)
                      await refresh()
                    })
                  }
                >
                  Remove
                </button>
              </li>
            )
          })}
        </ul>
      )}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <button
          type="button"
          className="button"
          onClick={() =>
            void act(async () => {
              const { token } = await api.share(id)
              setLink(
                `${window.location.origin}${window.location.pathname}${sharedHref(token)}`,
              )
              await refresh()
            })
          }
        >
          {list.shared ? 'Make a new share link' : 'Share'}
        </button>
        {list.shared && (
          <button
            type="button"
            className="button"
            onClick={() =>
              void act(async () => {
                await api.unshare(id)
                setLink(null)
                await refresh()
              })
            }
          >
            Stop sharing
          </button>
        )}
        <button
          type="button"
          className="button"
          style={{ marginLeft: 'auto' }}
          onClick={() =>
            void act(async () => {
              await api.deleteList(id)
              onChange()
            })
          }
        >
          Delete list
        </button>
      </div>
      {link && (
        <p className="note" style={{ margin: 0 }}>
          Anyone signed in can open this link. Making a new one stops this one working.{' '}
          <span className="mono" style={{ wordBreak: 'break-all' }}>
            {link}
          </span>{' '}
          <button
            type="button"
            className="button"
            onClick={() => void navigator.clipboard?.writeText(link)}
          >
            Copy
          </button>
        </p>
      )}
      {list.shared && !link && (
        <p className="muted" style={{ margin: 0, fontSize: 13 }}>
          Shared. The link is shown only when it is made; make a new one to see it again.
        </p>
      )}
      {problem && (
        <p role="alert" style={{ margin: 0, color: '#8a3a14' }}>
          {problem}
        </p>
      )}
    </section>
  )
}
