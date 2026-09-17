/**
 * Settings and leaving - the door, with no retention team behind it.
 *
 * **WE PROMISE AN ORGANIZATION CAN WALK AWAY WITH ITS DATA, SO THIS IS THE
 * DOOR.** No export request, no waiting, no email to us, no phone call.
 * Everything here is self-serve, and `GET /clubs/{slug}/export` answers in
 * one call rather than queueing a job with an email at the end - an export
 * you have to request and wait for is an export that quietly stops working.
 *
 * **DELETING THE ORGANIZATION DOES NOT DELETE THE TRAILS**, and that sentence
 * is the most important one on the screen. The sections revert to unclaimed -
 * still on the map for hikers, with nobody behind them - and anybody with an
 * email at the domain can adopt them later from Claim your org. Taking the
 * trails down is a separate, deliberate act, because a hiker walking a
 * section this afternoon does not care that a board meeting went badly.
 *
 * **VOLUNTEERS KEEP THEIR OWN RECORDS.** Hours and reports belong to the
 * person, not the organization, and the backend's `delete_org` touches
 * neither. An organization winding up is not an event that erases somebody
 * else's logbook.
 */

import { useState } from 'react'
import { PageHeader } from '../components'
import type { Org } from '../orgApi'

export interface ExportPiece {
  readonly key: string
  readonly label: string
  readonly format: string
  readonly count: string
}

export interface OrgSettingsProps {
  readonly org: Org
  readonly exports: readonly ExportPiece[]
  readonly onDownload: () => void
  readonly onProposeRemoval: (adminId: string) => void
  readonly onUnpublish: () => void
  readonly onProposeDeletion: () => void
  readonly names?: Readonly<Record<string, string>>
  /** Roles each admin holds that would need reassigning, not deleting. */
  readonly heldRoles?: Readonly<Record<string, number>>
}

export function OrgSettings({
  org,
  exports,
  onDownload,
  onProposeRemoval,
  onUnpublish,
  onProposeDeletion,
  names = {},
  heldRoles = {},
}: OrgSettingsProps) {
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const codeowners = org.admins.filter(
    (seat) => seat.is_codeowner && seat.approved_at,
  ).length

  return (
    <>
      <PageHeader
        eyebrow="Settings · leaving OurHike"
        title="Leaving, on your terms"
        sub={
          <>
            We promise you can walk away with your data, so here is the door — no email to
            us, no phone call, no retention team. Everything below is self-serve.
          </>
        }
        glyph={
          <>
            <path d="M14 3h5v18h-5" />
            <path d="M3 12h11M10.5 8.5 14 12l-3.5 3.5" />
          </>
        }
      />

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Take your data</h2>
          <span className="org-panel__count">no request, no waiting</span>
        </div>
        <p className="org-panel__note">
          It is already public — this button just packages it for you. You can do this any
          time, not only on the way out.
        </p>
        <div className="org-grid org-grid--three">
          {exports.map((piece) => (
            <div className="org-tile" key={piece.key}>
              <span className="org-tile__label">{piece.label}</span>
              <span className="org-tile__value">{piece.count}</span>
              <span className="org-tile__meta">{piece.format}</span>
            </div>
          ))}
        </div>
        <div className="org-inline">
          <button type="button" className="org-btn" onClick={onDownload}>
            Download everything
          </button>
        </div>
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Remove an admin</h2>
          <span className="org-panel__count">{codeowners} codeowners</span>
        </div>
        <p className="org-panel__note">
          People move on. Removing somebody takes their access away and leaves everything
          they did in place — their confirmations, their hours, their name on past
          approvals.
        </p>
        <div className="org-stack">
          {org.admins.map((seat) => (
            <div className="org-card" key={seat.id}>
              <div className="org-inline">
                <span className="org-table__name">
                  {names[seat.person_id] ?? seat.person_id}
                </span>
                <span className="org-mono">
                  {seat.title ?? 'Admin'}
                  {seat.is_codeowner ? ' · codeowner' : ''}
                </span>
                <button
                  type="button"
                  className="org-btn org-btn--ghost org-btn--small"
                  style={{ marginLeft: 'auto' }}
                  onClick={() => onProposeRemoval(seat.id)}
                >
                  Propose removal
                </button>
              </div>
              {seat.is_codeowner ? (
                <p className="org-mono">
                  Removing a codeowner needs the other two to approve — you cannot drop
                  below three and keep publishing.
                </p>
              ) : null}
              {heldRoles[seat.person_id] ? (
                <p className="org-mono">
                  Holds {heldRoles[seat.person_id]} supervisor{' '}
                  {heldRoles[seat.person_id] === 1 ? 'role' : 'roles'}. Those stay with
                  the organization and need reassigning, not deleting.
                </p>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Unpublish a trail</h2>
        </div>
        <p className="org-panel__note">
          Take a single trail off the map without leaving. Hikers stop seeing it within
          the hour; the history stays in the repository, because a merged commit cannot be
          unsaid.
        </p>
        <div className="org-inline">
          <button type="button" className="org-btn org-btn--ghost" onClick={onUnpublish}>
            Choose a trail to unpublish
          </button>
        </div>
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Delete this organization</h2>
        </div>
        <p className="org-panel__note">
          This removes the organization and everybody's admin access.{' '}
          <strong>It does not delete the trails.</strong> They revert to unclaimed — still
          on the map for hikers, with nobody behind them — and anybody with an email at
          your domain can adopt them later from Claim your org.
        </p>
        <div className="org-callout" data-tone="warn">
          <span>
            <strong>What survives you.</strong> Your trails stay published; removing them
            is the separate decision above. Volunteers keep their own records — their
            hours and reports are theirs, not yours to delete. And the repository history
            remains, which is what made any of this trustworthy in the first place.
          </span>
        </div>
        {confirmingDelete ? (
          <div className="org-stack">
            <div className="org-callout" data-tone="stop">
              <span>
                All three codeowners approve, and then thirty days pass. Either of those
                can stop it, and nothing is destroyed in the meantime.
              </span>
            </div>
            <div className="org-inline">
              <button
                type="button"
                className="org-btn org-btn--danger"
                onClick={() => {
                  onProposeDeletion()
                  setConfirmingDelete(false)
                }}
              >
                Yes, propose deleting {org.name}
              </button>
              <button
                type="button"
                className="org-btn org-btn--ghost"
                onClick={() => setConfirmingDelete(false)}
              >
                Never mind
              </button>
            </div>
          </div>
        ) : (
          <div className="org-inline">
            <button
              type="button"
              className="org-btn org-btn--danger"
              onClick={() => setConfirmingDelete(true)}
            >
              Propose deletion
            </button>
            <span className="org-mono">
              All three codeowners approve, then 30 days pass.
            </span>
          </div>
        )}
      </section>
    </>
  )
}
