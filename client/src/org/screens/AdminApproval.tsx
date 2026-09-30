/**
 * Stage 1: three people say yes before an organization appears to hikers.
 *
 * **A DECLINE PAUSES THE ORG AND IS NEVER A REJECTION**, which is the whole
 * reason this screen exists as a screen rather than as three emails. The
 * common cause of a decline is a secretary who does not know what OurHike is,
 * not a board that said no - so declining is offered plainly, it asks for a
 * reason, and approving afterwards clears it. The backend clears
 * `declined_at` on approve for the same reason.
 *
 * **NOBODY ANSWERS ON ANYBODY ELSE'S BEHALF.** The buttons appear only on the
 * caller's own seat; the other two rows are status. The endpoint refuses the
 * rest, which is the gate - this is the half that keeps an admin from
 * discovering it by pressing something.
 *
 * The audit trail beside it is not decoration. "Who approved what, when" is
 * the question an organization asks the day something is published that
 * somebody does not remember agreeing to.
 */

import { useState } from 'react'
import { PageHeader } from '../components'
import type { Org, OrgAdmin } from '../orgApi'

export interface AdminApprovalProps {
  readonly org: Org
  /** The caller's own profile id, so their own seat can be told apart. */
  readonly personId: string | null
  readonly onApprove: (seat: OrgAdmin) => void
  readonly onDecline: (seat: OrgAdmin, reason: string) => void
  readonly onRemind: (seat: OrgAdmin) => void
  readonly onContinue: () => void
  /** Names by person id, where they are known. An org that invited somebody
   *  who has never signed in has an address and no name, and the row says so
   *  rather than inventing one. */
  readonly names?: Readonly<Record<string, string>>
}

function seatState(seat: OrgAdmin): {
  label: string
  tone: 'done' | 'waiting' | 'stopped'
} {
  if (seat.approved_at) return { label: 'approved', tone: 'done' }
  if (seat.declined_at) return { label: 'paused', tone: 'stopped' }
  return { label: 'invited', tone: 'waiting' }
}

function when(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export function AdminApproval({
  org,
  personId,
  onApprove,
  onDecline,
  onRemind,
  onContinue,
  names = {},
}: AdminApprovalProps) {
  const [declining, setDeclining] = useState<string | null>(null)
  const [reason, setReason] = useState('')

  const approved = org.admins.filter((seat) => seat.approved_at !== null).length
  const needed = Math.max(3, org.admins.length)

  return (
    <>
      <PageHeader
        eyebrow={`Stage 1 of 3 · ${approved} of ${needed} answered`}
        title="Your admins are approving"
        sub={
          <>
            Three people have to say yes before {org.name} appears to hikers. Whoever
            answers first picks up the hike registry.
          </>
        }
        glyph={
          <>
            <rect x="3" y="5.5" width="18" height="13" rx="2" />
            <path d="m3.5 7 8.5 6 8.5-6" />
          </>
        }
      />

      <div className="org-grid org-grid--two">
        <div className="org-stack">
          {org.admins.map((seat) => {
            const state = seatState(seat)
            const mine = personId !== null && seat.person_id === personId
            return (
              <div className="org-card org-panel" key={seat.id}>
                <div className="org-panel__head">
                  <h2>{names[seat.person_id] ?? seat.person_id}</h2>
                  <span
                    className="org-pill"
                    data-tone={state.tone}
                    style={{ marginLeft: 'auto' }}
                  >
                    {state.label}
                  </span>
                </div>
                <p className="org-mono">
                  {seat.title ?? 'Admin'}
                  {seat.is_codeowner ? ' · codeowner' : ''}
                </p>
                <p className="org-panel__note">
                  {seat.approved_at
                    ? `Approved ${when(seat.approved_at)}`
                    : seat.declined_at
                      ? `Paused ${when(seat.declined_at)}${seat.decline_reason ? ` — “${seat.decline_reason}”` : ''}`
                      : `Emailed ${when(seat.invited_at)} · not answered`}
                </p>

                {mine && !seat.approved_at ? (
                  declining === seat.id ? (
                    <div className="org-stack">
                      <label className="org-field">
                        <span className="org-field__label">
                          Why, in your own words — “our board hasn't voted” is a perfectly
                          good answer
                        </span>
                        <textarea
                          className="org-textarea"
                          value={reason}
                          onChange={(event) => setReason(event.target.value)}
                        />
                      </label>
                      <div className="org-inline">
                        <button
                          type="button"
                          className="org-btn org-btn--small"
                          onClick={() => {
                            onDecline(seat, reason)
                            setDeclining(null)
                            setReason('')
                          }}
                        >
                          Pause the org
                        </button>
                        <button
                          type="button"
                          className="org-btn org-btn--ghost org-btn--small"
                          onClick={() => setDeclining(null)}
                        >
                          Never mind
                        </button>
                      </div>
                      <p className="org-mono">
                        Nothing is deleted. Any of you can approve afterwards and it
                        starts again from here.
                      </p>
                    </div>
                  ) : (
                    <div className="org-inline">
                      <button
                        type="button"
                        className="org-btn org-btn--small"
                        onClick={() => onApprove(seat)}
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        className="org-btn org-btn--ghost org-btn--small"
                        onClick={() => setDeclining(seat.id)}
                      >
                        Something's wrong
                      </button>
                    </div>
                  )
                ) : null}

                {mine && seat.declined_at ? (
                  <div className="org-inline">
                    <button
                      type="button"
                      className="org-btn org-btn--small"
                      onClick={() => onApprove(seat)}
                    >
                      Actually, approve it
                    </button>
                  </div>
                ) : null}

                {!mine && !seat.approved_at && !seat.declined_at ? (
                  <div className="org-inline">
                    <button
                      type="button"
                      className="org-btn org-btn--ghost org-btn--small"
                      onClick={() => onRemind(seat)}
                    >
                      Send a reminder
                    </button>
                    <span className="org-mono">
                      Once, in a week, and then never again.
                    </span>
                  </div>
                ) : null}
              </div>
            )
          })}

          <button
            type="button"
            className="org-btn"
            style={{ alignSelf: 'flex-start' }}
            onClick={onContinue}
          >
            Continue to setup
          </button>
        </div>

        <div className="org-card org-panel">
          <span className="org-eyebrow">Audit trail</span>
          <p className="org-panel__note">
            Who agreed to what, and when. This is the answer the day somebody publishes
            something another admin does not remember approving.
          </p>
          <div className="org-stack">
            <p className="org-mono">
              {when(org.created_at)} · {org.name} registered
            </p>
            {org.domain ? (
              <p className="org-mono">
                {when(org.created_at)} · {org.domain} verified by{' '}
                {org.verified_by === 'dns' ? 'DNS record' : 'an email at the domain'}
              </p>
            ) : null}
            {org.membership_url || org.donation_url ? (
              <p className="org-mono">
                {when(org.created_at)} · membership and donation pages linked
              </p>
            ) : null}
            {org.admins
              .filter((seat) => seat.approved_at || seat.declined_at)
              .map((seat) => (
                <p className="org-mono" key={`audit-${seat.id}`}>
                  {when(seat.approved_at ?? seat.declined_at)} ·{' '}
                  {seat.approved_at ? 'approved by ' : 'paused by '}
                  {names[seat.person_id] ?? seat.person_id}
                </p>
              ))}
          </div>
          <div className="org-callout" data-tone="info">
            <span>
              <strong>A decline is reversible.</strong> It pauses the organization rather
              than refusing it, and there is no state anywhere that records having been
              asked twice.
            </span>
          </div>
        </div>
      </div>
    </>
  )
}
