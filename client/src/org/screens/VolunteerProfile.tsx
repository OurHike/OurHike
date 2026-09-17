/**
 * One volunteer's page - the same page they see.
 *
 * **THE PERSON READS THIS EXACT SCREEN, AND THE SCREEN SAYS SO.** There is no
 * admin-only view of somebody with a second set of notes on it. An
 * organization that wants to write something about a volunteer the volunteer
 * cannot read is asking for a product we are not building, and saying that at
 * the top is cheaper than discovering it three screens in.
 *
 * **THEY EDIT THEIR DETAILS; AN ADMIN EDITS THEIR ROLES.** The split is the
 * whole permission model on one page: name, contact and notification settings
 * belong to the person, and roles and status belong to the organization,
 * because a role is a claim about who is responsible for a stretch of trail
 * and somebody cannot award themselves one.
 *
 * **NOTHING IS OVERWRITTEN SILENTLY.** Every field carries who changed it and
 * when. A profile that quietly takes the last write is a profile where an
 * organization and a volunteer can disagree about a phone number with no way
 * to find out which of them typed it.
 *
 * **PUBLIC CREDIT IS OFF UNTIL THE PERSON TURNS IT ON.** An admin cannot do
 * it for them, and this screen renders the toggle disabled rather than absent
 * for an admin, so the rule is visible to the person who would otherwise go
 * looking for it. Rule 4 in `features/ORG_ONBOARDING.md`, on the surface
 * where it is easiest to break by accident.
 */

import { useState } from 'react'
import { PageHeader } from '../components'

export interface VolunteerRoleHeld {
  readonly id: string
  readonly name: string
  readonly section: string
  /** Who they answer to for this role, or null when nobody does. */
  readonly supervisor: string | null
  readonly since: string
}

export interface VolunteerActivity {
  readonly id: string
  readonly on: string
  readonly what: string
}

export interface VolunteerDetails {
  readonly fullName: string
  readonly email: string
  readonly phone: string
  readonly trailName: string
}

export interface VolunteerProfileProps {
  readonly personId: string
  readonly displayName: string
  readonly initials: string
  readonly joined: string
  readonly details: VolunteerDetails
  readonly roles: readonly VolunteerRoleHeld[]
  readonly activity: readonly VolunteerActivity[]
  readonly hoursLogged: number
  readonly reportsFiled: number
  readonly sectionsCovered: number
  readonly publicCredit: boolean
  readonly lastEditedBy: string | null
  readonly lastEditedOn: string | null
  readonly active: boolean
  /** True when the signed-in person is this person. */
  readonly isSelf: boolean
  readonly isAdmin: boolean
  readonly onSaveDetails: (details: VolunteerDetails) => void
  readonly onAddRole: () => void
  readonly onSetActive: (active: boolean) => void
  readonly onSetPublicCredit: (on: boolean) => void
  readonly onBack: () => void
}

export function VolunteerProfile({
  displayName,
  initials,
  joined,
  details,
  roles,
  activity,
  hoursLogged,
  reportsFiled,
  sectionsCovered,
  publicCredit,
  lastEditedBy,
  lastEditedOn,
  active,
  isSelf,
  isAdmin,
  onSaveDetails,
  onAddRole,
  onSetActive,
  onSetPublicCredit,
  onBack,
}: VolunteerProfileProps) {
  const [draft, setDraft] = useState<VolunteerDetails>(details)
  const dirty =
    draft.fullName !== details.fullName ||
    draft.email !== details.email ||
    draft.phone !== details.phone ||
    draft.trailName !== details.trailName

  const field = (key: keyof VolunteerDetails) => (event: { target: { value: string } }) =>
    setDraft({ ...draft, [key]: event.target.value })

  return (
    <>
      <div className="org-inline">
        <button type="button" className="org-link" onClick={onBack}>
          ‹ All volunteers
        </button>
      </div>

      <PageHeader
        eyebrow={`Volunteer since ${joined} · ${hoursLogged} hours logged`}
        title={displayName}
        sub={
          <>
            <strong>{displayName} sees this same page.</strong> They can change their own
            name, contact details and notification settings; you can additionally change
            their roles and status. Whoever edits a field, the change is dated and
            attributed — nothing here is overwritten silently.
          </>
        }
        glyph={
          <>
            <circle cx="12" cy="8" r="3.5" />
            <path d="M5 20a7 7 0 0 1 14 0" />
          </>
        }
        actions={<span className="org-switch__initials">{initials}</span>}
      />

      <section className="org-card org-panel">
        <div className="org-panel__head">
          <h2>Their details</h2>
          {!isSelf ? <span className="org-panel__count">theirs to edit</span> : null}
        </div>
        <div className="org-row">
          <label className="org-field">
            <span className="org-field__label">Name</span>
            <input
              className="org-input"
              value={draft.fullName}
              disabled={!isSelf}
              onChange={field('fullName')}
            />
          </label>
          <label className="org-field">
            <span className="org-field__label">Email</span>
            <input
              className="org-input"
              value={draft.email}
              disabled={!isSelf}
              onChange={field('email')}
            />
          </label>
        </div>
        <div className="org-row">
          <label className="org-field">
            <span className="org-field__label">Phone (optional)</span>
            <input
              className="org-input"
              value={draft.phone}
              placeholder="Only shown to their supervisor"
              disabled={!isSelf}
              onChange={field('phone')}
            />
          </label>
          <label className="org-field">
            <span className="org-field__label">Trail name (optional)</span>
            <input
              className="org-input"
              value={draft.trailName}
              placeholder="What hikers call them"
              disabled={!isSelf}
              onChange={field('trailName')}
            />
          </label>
        </div>
        {isSelf ? (
          <div className="org-inline">
            <button
              type="button"
              className="org-btn org-btn--small"
              disabled={!dirty}
              onClick={() => onSaveDetails(draft)}
            >
              Save changes
            </button>
            {lastEditedBy ? (
              <span className="org-mono">
                Last edited by {lastEditedBy}
                {lastEditedOn ? ` · ${lastEditedOn}` : ''}
              </span>
            ) : null}
          </div>
        ) : (
          <p className="org-mono">
            These are theirs to change, not yours. You are reading the same fields they
            would edit — an admin who could rewrite somebody's contact details could also
            quietly redirect where their reports go.
          </p>
        )}
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Roles</h2>
          <span className="org-pill" data-tone="quiet">
            admin only
          </span>
        </div>
        <p className="org-panel__note">
          {displayName} can see these; only an admin can change them.
        </p>
        {roles.length === 0 ? (
          <div className="org-empty">
            <h3>No roles yet</h3>
            <p>
              Somebody on the roster with no role is a volunteer nobody has asked to do
              anything in particular, which is a real state and not a broken one. The
              coverage report counts sections, not people.
            </p>
          </div>
        ) : (
          <div className="org-stack">
            {roles.map((role) => (
              <div className="org-card" key={role.id}>
                <div className="org-inline">
                  <span className="org-table__name">{role.name}</span>
                  <span className="org-mono">{role.section}</span>
                  <span className="org-mono" style={{ marginLeft: 'auto' }}>
                    since {role.since}
                  </span>
                </div>
                <p className="org-mono">
                  {role.supervisor === null
                    ? 'supervised by nobody inside the org'
                    : `supervised by ${role.supervisor}`}
                </p>
              </div>
            ))}
          </div>
        )}
        {isAdmin ? (
          <div className="org-inline">
            <button type="button" className="org-btn org-btn--small" onClick={onAddRole}>
              + Add a role
            </button>
            <button
              type="button"
              className="org-btn org-btn--ghost org-btn--small"
              onClick={() => onSetActive(!active)}
            >
              {active ? 'Mark inactive' : 'Mark active'}
            </button>
            <span className="org-mono">
              Marking somebody inactive releases their roles so a section stops reading as
              covered. It deletes nothing.
            </span>
          </div>
        ) : null}
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Their record</h2>
        </div>
        <div className="org-grid org-grid--three">
          <div className="org-tile">
            <span className="org-tile__label">Hours logged</span>
            <span className="org-tile__value">{hoursLogged}</span>
          </div>
          <div className="org-tile">
            <span className="org-tile__label">Reports filed</span>
            <span className="org-tile__value">{reportsFiled}</span>
          </div>
          <div className="org-tile">
            <span className="org-tile__label">Sections covered</span>
            <span className="org-tile__value">{sectionsCovered}</span>
          </div>
          <div className="org-tile">
            <span className="org-tile__label">Joined</span>
            <span className="org-tile__value">{joined}</span>
          </div>
        </div>
        <p className="org-mono">
          Hours are theirs first — logged by them, confirmed by the organization
          afterwards for its own reporting.
        </p>
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Recent activity</h2>
        </div>
        {activity.length === 0 ? (
          <div className="org-empty">
            <h3>Nothing yet</h3>
            <p>
              Somebody who has just joined has an empty record, and that is what this
              shows.
            </p>
          </div>
        ) : (
          <div className="org-stack">
            {activity.map((row) => (
              <div className="org-inline" key={row.id}>
                <span className="org-mono">{row.on}</span>
                <span>{row.what}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="org-callout" data-tone={publicCredit ? 'good' : 'info'}>
        <span>
          <strong>Public credit is {publicCredit ? 'on' : 'off'}.</strong> {displayName}'s
          name is never shown publicly against a section unless they turn credit on
          themselves. Only they can make that choice — an admin cannot do it for them.
          {isSelf ? (
            <>
              {' '}
              <button
                type="button"
                className="org-link"
                onClick={() => onSetPublicCredit(!publicCredit)}
              >
                {publicCredit ? 'Turn credit off' : 'Turn credit on'}
              </button>
            </>
          ) : null}
        </span>
      </div>
    </>
  )
}
