import { useState, type FormEvent } from 'react'
import { useAccount } from '../account'

/** Email, then the six-digit code Supabase emails back. */
export function SignInForm({ why }: { why?: string }) {
  const account = useAccount()
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)

  if (account.session.state === 'off') {
    return <p className="muted">Sign-in is not set up on this site yet.</p>
  }

  const send = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    const failure = await account.sendCode(email.trim())
    setBusy(false)
    setProblem(failure)
    if (!failure) setSent(true)
  }
  const verify = async (event: FormEvent) => {
    event.preventDefault()
    setBusy(true)
    const failure = await account.verifyCode(email.trim(), code)
    setBusy(false)
    setProblem(failure)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 420 }}>
      {why && <p style={{ margin: 0 }}>{why}</p>}
      {!sent ? (
        <form onSubmit={send} className="field">
          <label htmlFor="email">Email</label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input
              id="email"
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              style={{ flex: '1 1 220px' }}
            />
            <button type="submit" className="button primary" disabled={busy}>
              Email me a code
            </button>
          </div>
          <span className="muted" style={{ fontSize: 13 }}>
            Uses your OurHike account, or makes one. Your email stays with the sign-in
            service; Site Remediation never stores it.
          </span>
        </form>
      ) : (
        <form onSubmit={verify} className="field">
          <label htmlFor="code">The six-digit code sent to {email.trim()}</label>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <input
              id="code"
              inputMode="numeric"
              autoComplete="one-time-code"
              required
              value={code}
              onChange={(e) => setCode(e.target.value)}
              style={{ width: 160 }}
            />
            <button type="submit" className="button primary" disabled={busy}>
              Sign in
            </button>
            <button type="button" className="button" onClick={() => setSent(false)}>
              Use another email
            </button>
          </div>
        </form>
      )}
      {problem && (
        <p role="alert" style={{ margin: 0, color: '#8a3a14' }}>
          {problem}
        </p>
      )}
    </div>
  )
}
