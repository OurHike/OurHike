/**
 * Every email OurHike sends in an organization's name, in full.
 *
 * **THERE ARE THREE AND THE SCREEN SAYS SO.** Each has a job and stops: no
 * newsletters, no re-engagement, no unsubscribe-to-escape. An organization
 * handing us their members' addresses is entitled to read every message
 * before it goes, and "these are the only three" is a promise that can only
 * be made by a screen that shows all of them.
 *
 * **THE FIRST ONE IS THE FIRST THING MOST ADMINS EVER SEE OF OURHIKE**, read
 * by a sceptical volunteer on a phone, so its copy leads with what they are
 * agreeing to and says outright that declining is a real option. An approval
 * email that hides the decline gets approvals from people who did not read
 * it, which is worse than a decline.
 *
 * The rules underneath apply to all three and are the reason this is a screen
 * rather than three templates in a backend directory: plain text works,
 * nobody's name appears in an email to somebody outside the organization, and
 * replies reach a person rather than a no-reply void.
 */

import { PageHeader } from '../components'

export interface OrgEmailsProps {
  readonly orgName: string
  readonly domain: string | null
  readonly adminCount: number
  readonly sectionCount: number
  readonly volunteerCount: number
  readonly onOpenWelcome: () => void
}

export function OrgEmails({
  orgName,
  domain,
  adminCount,
  sectionCount,
  volunteerCount,
  onOpenWelcome,
}: OrgEmailsProps) {
  return (
    <>
      <PageHeader
        eyebrow="What we send on your behalf"
        title="The three emails"
        sub={
          <>
            Every email we send in your name, in full. Each one has a job and stops — no
            newsletters, no re-engagement, no unsubscribe-to-escape. These are the only
            three.
          </>
        }
        glyph={
          <>
            <rect x="3" y="5.5" width="18" height="13" rx="2" />
            <path d="m3.5 7 8.5 6 8.5-6" />
          </>
        }
      />

      <section className="org-card org-panel">
        <div className="org-panel__head">
          <h2>1 · Admin approval</h2>
          <span className="org-panel__count">to {adminCount} people, once</span>
        </div>
        <p className="org-panel__note">
          Sent the moment somebody registers the organization. This is the first thing
          most admins ever see of OurHike, so it has to survive being read by a sceptical
          volunteer on a phone.
        </p>
        <div className="org-card">
          <p className="org-table__name">You have been named an admin of {orgName}</p>
          <p className="org-mono">
            hello@ourhike.org → an admin{domain ? ` at ${domain}` : ''}
          </p>
          <p className="org-panel__note">
            Somebody at {orgName} has put your trails on OurHike, a free offline trail map
            built by volunteers, and named you one of three admins.{' '}
            <strong>Nothing is public yet.</strong> It needs all three of you to agree.
          </p>
          <span className="org-eyebrow">What you are agreeing to</span>
          <ul className="org-stack" style={{ margin: 0, paddingLeft: 18 }}>
            <li className="org-panel__note">
              {domain ?? 'your domain'} is yours, and you can speak for it
            </li>
            <li className="org-panel__note">
              three admins — any of you can propose changes, all three approve them
            </li>
            <li className="org-panel__note">
              your own membership and donation pages get linked from your sections
            </li>
            <li className="org-panel__note">
              no money passes through OurHike, and there is no payout programme to join
            </li>
          </ul>
          <div className="org-inline">
            <span className="org-btn org-btn--small">Approve</span>
            <span className="org-btn org-btn--ghost org-btn--small">
              Something's wrong
            </span>
          </div>
          <div className="org-callout" data-tone="info">
            <span>
              <strong>Declining is a real option.</strong> It pauses the organization
              rather than deleting anything, and you can say why — “our board hasn't
              voted” is a perfectly good answer. Whoever approves first picks up the next
              step. We will remind you once, in a week, and then never again.
            </span>
          </div>
        </div>
      </section>

      <section className="org-card org-panel">
        <div className="org-panel__head">
          <h2>2 · Registry sign-off</h2>
          <span className="org-panel__count">
            to the other {Math.max(0, adminCount - 1)} admins
          </span>
        </div>
        <p className="org-panel__note">
          Sent when the first admin finishes the registry. It is asking somebody to vouch
          for {sectionCount} sections, so it leads with the summary and the exceptions
          rather than a wall of rows.
        </p>
        <div className="org-card">
          <p className="org-table__name">
            {sectionCount} sections are ready for you to check
          </p>
          <p className="org-mono">
            hello@ourhike.org → an admin{domain ? ` at ${domain}` : ''}
          </p>
          <p className="org-panel__note">
            Before this reaches hikers, all three admins confirm it is accurate. You are
            the second.
          </p>
          <span className="org-eyebrow">What came out of your own files</span>
          <p className="org-panel__note">
            <strong>Read the exceptions first.</strong> Those are the lines where a name
            was missing or two looked like duplicates — somebody made a call on each and
            their reasoning is attached. The rest came straight from your own section-name
            attribute.
          </p>
          <p className="org-mono">
            Flagging a line sends it back with your note attached — it does not start the
            registry over. Nothing publishes on two approvals.
          </p>
        </div>
      </section>

      <section className="org-card org-panel">
        <div className="org-panel__head">
          <h2>3 · Volunteer welcome</h2>
          <span className="org-panel__count">
            to {volunteerCount} {volunteerCount === 1 ? 'person' : 'people'}, once
          </span>
        </div>
        <p className="org-panel__note">
          The one the most people read. It carries each person's own section and
          supervisor, and the three things they can do this week. Rather than duplicate it
          here, it lives where you send it from — with the roster counts and the privacy
          note beside it.
        </p>
        <div className="org-inline">
          <button
            type="button"
            className="org-btn org-btn--ghost"
            onClick={onOpenWelcome}
          >
            Open the welcome screen
          </button>
        </div>
      </section>

      <section className="org-card org-panel">
        <span className="org-eyebrow">Rules all three follow</span>
        <ul className="org-stack" style={{ margin: 0, paddingLeft: 18 }}>
          <li className="org-panel__note">
            <strong>Plain text works.</strong> Every one reads fine with images blocked.
          </li>
          <li className="org-panel__note">
            <strong>One action per email.</strong> No digests, no bundling.
          </li>
          <li className="org-panel__note">
            <strong>One reminder at most</strong>, then silence.
          </li>
          <li className="org-panel__note">
            <strong>
              Nobody's name appears in an email to somebody outside the organization.
            </strong>{' '}
            Rule 4, applied to the one surface where it is easiest to break by accident.
          </li>
          <li className="org-panel__note">
            <strong>Replies reach a person</strong>, not a no-reply void.
          </li>
        </ul>
      </section>
    </>
  )
}
