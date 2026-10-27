import { useEffect, useState, type FormEvent } from 'react'
import { useAccount } from '../account'
import { SignInForm } from '../components/SignInForm'

export function AccountScreen() {
  const account = useAccount()
  return (
    <section
      className="card"
      style={{ display: 'flex', flexDirection: 'column', gap: 14, maxWidth: 640 }}
    >
      <h1 style={{ fontSize: 28 }}>Your account</h1>
      {account.session.state === 'signed_in' ? (
        <SignedIn />
      ) : account.session.state === 'loading' ? (
        <p className="muted">Checking whether you are signed in…</p>
      ) : (
        <SignInForm why="Signing in lets you save sites to lists, share them, and see and change your club's ranking weights. The map and every site stay open to everyone." />
      )}
    </section>
  )
}

function SignedIn() {
  const { api, session, signOut } = useAccount()
  const [name, setName] = useState('')
  const [saved, setSaved] = useState<string | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const [confirmDelete, setConfirmDelete] = useState(false)

  useEffect(() => {
    if (!api) return
    let live = true
    api.me().then(
      (me) => live && setName(me.display_name ?? ''),
      (error: Error) => live && setProblem(error.message),
    )
    return () => {
      live = false
    }
  }, [api])

  if (!api || session.state !== 'signed_in') return null

  const save = async (event: FormEvent) => {
    event.preventDefault()
    try {
      const me = await api.setDisplayName(name.trim() || null)
      setName(me.display_name ?? '')
      setSaved(
        me.display_name
          ? `Saved. Others see you as "${me.display_name}".`
          : 'Saved. Others see no name.',
      )
      setProblem(null)
    } catch (error) {
      setProblem((error as Error).message)
    }
  }
  const remove = async () => {
    try {
      await api.deleteMe()
      await signOut()
    } catch (error) {
      setProblem((error as Error).message)
    }
  }

  return (
    <>
      <p style={{ margin: 0 }}>Signed in{session.email ? ` as ${session.email}` : ''}.</p>
      <form onSubmit={save} className="field">
        <label htmlFor="display-name">Name others see</label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <input
            id="display-name"
            maxLength={40}
            value={name}
            placeholder="None: shown as a volunteer"
            onChange={(e) => setName(e.target.value)}
            style={{ flex: '1 1 220px' }}
          />
          <button type="submit" className="button primary">
            Save
          </button>
        </div>
        <span className="muted" style={{ fontSize: 13 }}>
          Shown on weights you change and lists you share. Leave it empty to be shown as a
          volunteer.
        </span>
      </form>
      {saved && <p style={{ margin: 0 }}>{saved}</p>}
      {problem && (
        <p role="alert" style={{ margin: 0, color: '#8a3a14' }}>
          {problem}
        </p>
      )}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <button type="button" className="button" onClick={() => void signOut()}>
          Sign out
        </button>
        {!confirmDelete ? (
          <button type="button" className="button" onClick={() => setConfirmDelete(true)}>
            Delete my Campsite Steward data
          </button>
        ) : (
          <span
            className="note"
            style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}
          >
            Your lists will be deleted. Weights you changed stay in the clubs' histories,
            without your name.
            <button
              type="button"
              className="button primary"
              onClick={() => void remove()}
            >
              Delete
            </button>
            <button
              type="button"
              className="button"
              onClick={() => setConfirmDelete(false)}
            >
              Keep
            </button>
          </span>
        )}
      </div>
    </>
  )
}
