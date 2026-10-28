import { useEffect, useState } from 'react'
import { useAccount } from '../account'
import type { ClaimSummary, HoursTotals } from '../api'
import { STATE_LABEL, daysLeft, isWorking, reminder } from '../claims'
import { SignInForm } from '../components/SignInForm'
import { siteName } from '../format'
import { claimHref } from '../route'
import type { Site } from '../types'

/** Your claims and hours, and the submissions waiting for a reviewer (PLAN.md §5, "My claims"). */
export function WorkScreen({ sites }: { sites: Site[] }) {
  const { api } = useAccount()
  const [mine, setMine] = useState<ClaimSummary[] | null>(null)
  const [waiting, setWaiting] = useState<ClaimSummary[]>([])
  const [hours, setHours] = useState<HoursTotals | null>(null)
  const [problem, setProblem] = useState<string | null>(null)

  useEffect(() => {
    if (!api) return
    let live = true
    Promise.all([api.myClaims(), api.reviews(), api.myHours()]).then(
      ([claims, reviews, totals]) => {
        if (!live) return
        setMine(claims)
        setWaiting(reviews)
        setHours(totals)
      },
      (error: Error) => live && setProblem(error.message),
    )
    return () => {
      live = false
    }
  }, [api])

  if (!api) {
    return (
      <section className="card">
        <h1 style={{ fontSize: 28, marginBottom: 10 }}>Your work</h1>
        <SignInForm why="Sign in to see your claims and hours." />
      </section>
    )
  }
  if (problem) return <p role="alert">{problem}</p>
  if (!mine || !hours) return <p className="muted">Loading…</p>
  const byId = new Map(sites.map((s) => [s.rims_id, s]))
  const name = (claim: ClaimSummary) => {
    const site = byId.get(claim.rims_id)
    return site ? siteName(site) : 'A site no longer in ATC’s inventory'
  }
  const working = mine.filter(isWorking)
  const done = mine.filter((c) => !isWorking(c))

  return (
    <>
      <h1 style={{ fontSize: 28 }}>Your work</h1>
      <div className="kpis">
        <div className="card kpi">
          <div className="big">{hours.verified}</div>
          <div className="muted">verified hours</div>
        </div>
        <div className="card kpi">
          <div className="big">{hours.waiting}</div>
          <div className="muted">hours waiting for review</div>
        </div>
        <div className="card kpi">
          <div className="big">{working.length}</div>
          <div className="muted">claims in progress</div>
        </div>
      </div>

      <section className="card" aria-labelledby="working">
        <h2 id="working" className="eyebrow" style={{ marginBottom: 8 }}>
          In progress
        </h2>
        {working.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            Nothing claimed. Pick a site from <a href="#/">the list</a> to start.
          </p>
        ) : (
          <ul
            style={{
              margin: 0,
              paddingLeft: 20,
              display: 'flex',
              flexDirection: 'column',
              gap: 6,
            }}
          >
            {working.map((claim) => (
              <li key={claim.id}>
                <a href={claimHref(claim.id)}>{name(claim)}</a> ·{' '}
                {STATE_LABEL[claim.state]} ·{' '}
                <b
                  style={{
                    color: reminder(claim.due_at) === 'warning' ? '#c23d17' : undefined,
                  }}
                >
                  {daysLeft(claim.due_at)} days left
                </b>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="card" aria-labelledby="waiting">
        <h2 id="waiting" className="eyebrow" style={{ marginBottom: 8 }}>
          Waiting for a reviewer · {waiting.length}
        </h2>
        {waiting.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            No one else’s work is waiting.
          </p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {waiting.map((claim) => (
              <li key={claim.id}>
                <a href={claimHref(claim.id)}>{name(claim)}</a> · by{' '}
                {claim.claimer ?? 'a volunteer'}
              </li>
            ))}
          </ul>
        )}
      </section>

      {done.length > 0 && (
        <section className="card" aria-labelledby="done-claims">
          <h2 id="done-claims" className="eyebrow" style={{ marginBottom: 8 }}>
            Earlier
          </h2>
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            {done.map((claim) => (
              <li key={claim.id}>
                <a href={claimHref(claim.id)}>{name(claim)}</a> ·{' '}
                {STATE_LABEL[claim.state]}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
