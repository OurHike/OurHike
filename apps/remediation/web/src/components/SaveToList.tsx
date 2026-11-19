import { useEffect, useState } from 'react'
import { useAccount } from '../account'
import type { ListSummary } from '../api'

/** On a site page: save this site to one of your lists, or to a new one. */
export function SaveToList({ rimsId }: { rimsId: string }) {
  const { api, session } = useAccount()
  const [lists, setLists] = useState<ListSummary[] | null>(null)
  const [choice, setChoice] = useState('')
  const [newName, setNewName] = useState('')
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!api) return
    let live = true
    api.lists().then(
      (found) => {
        if (!live) return
        setLists(found)
        setChoice(found[0]?.id ?? 'new')
      },
      (error: Error) => live && setMessage(error.message),
    )
    return () => {
      live = false
    }
  }, [api])

  if (session.state === 'off') return null
  if (!api) {
    return (
      <p className="muted" style={{ margin: 0 }}>
        <a href="#/account">Sign in</a> to save this site to a list.
      </p>
    )
  }
  if (lists === null) return <p className="muted">Loading your lists…</p>

  const save = async () => {
    try {
      if (choice === 'new') {
        const made = await api.createList(newName.trim() || 'My sites', [rimsId])
        setLists([made, ...lists])
        setChoice(made.id)
        setNewName('')
        setMessage(`Saved to "${made.name}".`)
      } else {
        await api.addToList(choice, rimsId)
        setMessage(`Saved to "${lists.find((l) => l.id === choice)?.name}".`)
      }
    } catch (error) {
      setMessage((error as Error).message)
    }
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'flex-end' }}>
      <div className="field">
        <label htmlFor="save-to">Save to list</label>
        <select id="save-to" value={choice} onChange={(e) => setChoice(e.target.value)}>
          {lists.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
          <option value="new">New list…</option>
        </select>
      </div>
      {choice === 'new' && (
        <div className="field">
          <label htmlFor="new-list">New list's name</label>
          <input
            id="new-list"
            maxLength={80}
            placeholder="My sites"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
          />
        </div>
      )}
      <button type="button" className="button primary" onClick={() => void save()}>
        Save
      </button>
      {message && (
        <span role="status" style={{ flexBasis: '100%' }}>
          {message} <a href="#/lists">Your lists</a>
        </span>
      )}
    </div>
  )
}
