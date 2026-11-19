import { useEffect, useState } from 'react'
import { useAccount } from '../account'
import type { ClaimSummary, FollowUp } from '../api'
import { STATE_LABEL, daysLeft } from '../claims'
import { siteName } from '../format'
import { FollowUpList } from './FollowUps'
import { claimHref } from '../route'
import type { Site } from '../types'

const when = new Intl.DateTimeFormat('en-US', { dateStyle: 'medium' })

/**
 * On a site page: claim it (and its cluster), see who holds it, or, once it
 * is restored, take one of its follow-up visits (PLAN.md §6).
 */
export function ClaimPanel({ site, neighbours }: { site: Site; neighbours: Site[] }) {
  const { api, session } = useAccount()
  const [held, setHeld] = useState<ClaimSummary | null | undefined>(undefined)
  const [followUps, setFollowUps] = useState<FollowUp[]>([])
  const [problem, setProblem] = useState<string | null>(null)

  useEffect(() => {
    if (!api) return
    let live = true
    Promise.all([api.claimForSite(site.rims_id), api.followUps(site.rims_id)]).then(
      ([found, visits]) => {
        if (!live) return
        setHeld(found)
        setFollowUps(visits)
      },
      (error: Error) => live && setProblem(error.message),
    )
    return () => {
      live = false
    }
  }, [api, site.rims_id])

  const restored = followUps.some((f) => ['waiting', 'open', 'taken'].includes(f.state))
  if (
    session.state === 'off' ||
    (site.action !== 'close_restore' && site.action !== 'harden' && !restored)
  ) {
    return null
  }
  if (!api) {
    return (
      <p className="muted" style={{ margin: 0 }}>
        <a href="#/account">Sign in</a> to claim this site and restore it.
      </p>
    )
  }
  if (held === undefined) return problem ? <p role="alert">{problem}</p> : null

  if (held) {
    const what = held.kind === 'follow_up' ? `Follow-up visit ${held.visit}` : 'Claimed'
    return (
      <div
        className="note"
        style={{ display: 'flex', flexWrap: 'wrap', gap: 10, alignItems: 'center' }}
      >
        <b>
          {what} · {STATE_LABEL[held.state]}
        </b>
        {held.yours ? (
          <span>by you, due {when.format(new Date(held.due_at))}.</span>
        ) : (
          <span>
            by {held.claimer ?? 'a volunteer'}, {daysLeft(held.due_at)} days left on the
            claim.
          </span>
        )}
        <a className="button" href={claimHref(held.id)} style={{ marginLeft: 'auto' }}>
          {held.yours ? 'Open your claim' : 'See the claim'}
        </a>
      </div>
    )
  }

  if (restored) {
    const take = async (followUp: FollowUp) => {
      try {
        const taken = await api.takeFollowUp(followUp.id)
        window.location.hash = claimHref(taken.id)
      } catch (error) {
        setProblem((error as Error).message)
      }
    }
    return (
      <>
        <p className="note" style={{ margin: 0 }}>
          <b>Restored.</b>{' '}
          <a href={claimHref(followUps[0].done_claim_id)}>See the before and after</a>.
        </p>
        <FollowUpList followUps={followUps} onTake={(f) => void take(f)} />
        {problem && (
          <p role="alert" style={{ margin: 0, color: '#8a3a14' }}>
            {problem}
          </p>
        )}
      </>
    )
  }

  const claim = async (rimsIds: string[]) => {
    try {
      const made = await api.claimSites(rimsIds)
      const mine = made.find((c) => c.rims_id === site.rims_id) ?? made[0]
      window.location.hash = claimHref(mine.id)
    } catch (error) {
      setProblem((error as Error).message)
    }
  }
  const workable = neighbours.filter(
    (n) => n.action === 'close_restore' || n.action === 'harden',
  )

  return (
    <div
      className="card"
      style={{ display: 'flex', flexDirection: 'column', gap: 8, padding: 14 }}
    >
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
        <b>Open to claim.</b>
        <span className="muted">
          A claim gives you 14 days to restore the site and take before and after photos.
        </span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        <button
          type="button"
          className="button primary"
          onClick={() => void claim([site.rims_id])}
        >
          Claim this site
        </button>
        {workable.length > 0 && (
          <button
            type="button"
            className="button"
            onClick={() => void claim([site.rims_id, ...workable.map((n) => n.rims_id)])}
          >
            Claim all {workable.length + 1} in the cluster
          </button>
        )}
      </div>
      {workable.length > 0 && (
        <span className="muted" style={{ fontSize: 13 }}>
          Closing {siteName(site)} alone can send campers to{' '}
          {workable.map((n) => siteName(n)).join(', ')} instead.
        </span>
      )}
      {problem && (
        <p role="alert" style={{ margin: 0, color: '#8a3a14' }}>
          {problem}
        </p>
      )}
    </div>
  )
}
