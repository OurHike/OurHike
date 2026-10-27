import { useEffect, useState } from 'react'
import { useAccount } from '../account'
import { SignInForm } from '../components/SignInForm'
import { claimHref } from '../route'

/** A crew invite link: sign in, join, and land on the claim. */
export function JoinScreen({ token }: { token: string }) {
  const { api } = useAccount()
  const [problem, setProblem] = useState<string | null>(null)

  useEffect(() => {
    if (!api) return
    let live = true
    api.joinClaim(token).then(
      (claim) => {
        if (live) window.location.hash = claimHref(claim.id)
      },
      (error: Error) => live && setProblem(error.message),
    )
    return () => {
      live = false
    }
  }, [api, token])

  if (!api) {
    return (
      <section className="card">
        <h1 style={{ fontSize: 28, marginBottom: 10 }}>Join a crew</h1>
        <SignInForm why="Someone invited you to help restore a campsite. Sign in to join their crew." />
      </section>
    )
  }
  return problem ? (
    <section className="card" role="alert">
      <h1 style={{ fontSize: 24 }}>This invite does not work</h1>
      <p>{problem}</p>
    </section>
  ) : (
    <p className="muted">Joining the crew…</p>
  )
}
