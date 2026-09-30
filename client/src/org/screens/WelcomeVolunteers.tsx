/**
 * The one email the most people read, and who is about to get it.
 *
 * **NOBODY IS WELCOMED TWICE.** Not when a list is uploaded again, and not
 * when the nightly sync adds somebody back after a feed hiccup. The count on
 * this screen is people who have never had this email, derived from what was
 * sent rather than from who is on the roster today - a "send to everybody"
 * button on a 1,104-person roster is a mistake somebody makes once and cannot
 * take back.
 *
 * **THE PREVIEW IS THE EMAIL.** What renders below is what arrives, so an
 * admin reading it here has actually read what goes out in their
 * organization's name. A preview that paraphrases is worse than no preview,
 * because it gets trusted.
 *
 * **SOMEBODY WITH NO ROLE STILL GETS A USEFUL EMAIL.** Theirs drops the
 * section line and points at the workdays instead. The alternative - skipping
 * them, or sending a letter with a blank where their stretch of trail should
 * be - is how a new volunteer decides this was not for them.
 *
 * **NAMES STAY PRIVATE BY DEFAULT**, and the email says so in its own footer
 * rather than only here. Public credit is off for everybody until each person
 * turns it on.
 */

import { PageHeader } from '../components'
import welcomeBlaze from '../../design-system/assets/photos/heroes/16-water-gap-blaze.jpg'

/** The photograph at the head of the welcome email, and its licence.
 *
 *  The same frame and the same credit string `lib/heroPhotos.ts` carries for
 *  it - one home for the licence check, so a photo cannot be licence-checked
 *  in the first-run pool and unchecked here. CC BY 2.0's condition is that
 *  the credit renders on the frame, which is why it is a caption rather than
 *  a line in a manifest.
 */
const WELCOME_PHOTO = {
  src: welcomeBlaze,
  alt: 'A white blaze painted on a tree trunk beside the Appalachian Trail',
  credit: 'C. G. P. Grey · CC BY 2.0',
} as const

export interface WelcomeVolunteersProps {
  readonly orgName: string
  readonly neverWelcomed: number
  readonly alreadyWelcomed: number
  readonly onRoster: number
  /** Of those never welcomed, how many hold a role - theirs carries a section. */
  readonly withRole: number
  readonly sectionsPublished: number
  readonly hikesPublished: number
  /** A real recipient's details, to render the preview against. */
  readonly sample: {
    readonly firstName: string
    readonly role: string | null
    readonly section: string | null
    readonly sectionRange: string | null
    readonly supervisor: string | null
  } | null
  readonly canSend: boolean
  readonly onSend: () => void
  readonly onBack: () => void
}

export function WelcomeVolunteers({
  orgName,
  neverWelcomed,
  alreadyWelcomed,
  onRoster,
  withRole,
  sectionsPublished,
  hikesPublished,
  sample,
  canSend,
  onSend,
  onBack,
}: WelcomeVolunteersProps) {
  const withoutRole = Math.max(0, neverWelcomed - withRole)

  return (
    <>
      <PageHeader
        eyebrow="Manage volunteers · welcome"
        title="Welcome your volunteers"
        sub={
          <>
            One email each, with their section, their supervisor, and the three things
            they can do this week. Plenty of context, no jargon.
          </>
        }
        glyph={
          <>
            <rect x="3" y="5.5" width="18" height="13" rx="2" />
            <path d="m3.5 7 8.5 6 8.5-6" />
          </>
        }
      />

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Who gets this</h2>
        </div>
        <div className="org-grid org-grid--three">
          <div className="org-tile">
            <span className="org-tile__label">Never welcomed</span>
            <span className="org-tile__value">{neverWelcomed.toLocaleString()}</span>
          </div>
          <div className="org-tile">
            <span className="org-tile__label">Already welcomed</span>
            <span className="org-tile__value">{alreadyWelcomed.toLocaleString()}</span>
          </div>
          <div className="org-tile">
            <span className="org-tile__label">On your roster</span>
            <span className="org-tile__value">{onRoster.toLocaleString()}</span>
          </div>
        </div>
        <p className="org-panel__note">
          Only the {neverWelcomed.toLocaleString()} who have never had this email get it.
          Nobody is welcomed twice — not when you upload a list again, and not when the
          nightly sync adds somebody back. Of the {neverWelcomed.toLocaleString()},{' '}
          {withRole.toLocaleString()} {withRole === 1 ? 'has' : 'have'} a role and{' '}
          {withoutRole.toLocaleString()} {withoutRole === 1 ? 'does' : 'do'} not; theirs
          skips the section line and points at your workdays instead.
        </p>
      </section>

      <div className="org-callout" data-tone="info">
        <span>
          <strong>Names stay private by default.</strong> We never publish that a named
          volunteer looks after a particular stretch unless that person asks to be
          credited. Public credit is off for everybody on your roster until each one opts
          in.
        </span>
      </div>

      <div className="org-inline">
        <button
          type="button"
          className="org-btn"
          disabled={!canSend || neverWelcomed === 0}
          onClick={onSend}
        >
          {neverWelcomed === 0
            ? 'Everybody has had this'
            : `Send ${neverWelcomed.toLocaleString()} ${neverWelcomed === 1 ? 'welcome' : 'welcomes'}`}
        </button>
        <button type="button" className="org-btn org-btn--ghost" onClick={onBack}>
          Back to setup
        </button>
      </div>

      <section className="org-card org-panel">
        <div className="org-panel__head">
          <h2>What arrives</h2>
          <span className="org-panel__count">the email itself, not a summary</span>
        </div>
        <p className="org-mono">
          from hello@ourhike.org · to {neverWelcomed.toLocaleString()} new{' '}
          {neverWelcomed === 1 ? 'volunteer' : 'volunteers'}
        </p>

        <div className="org-card">
          <span className="org-eyebrow">
            Welcome to OurHike — {orgName} is on the map
          </span>
          <figure style={{ margin: '10px 0 0' }}>
            <img
              src={WELCOME_PHOTO.src}
              alt={WELCOME_PHOTO.alt}
              loading="lazy"
              style={{ width: '100%', borderRadius: 8, display: 'block' }}
            />
            <figcaption className="org-mono">{WELCOME_PHOTO.credit}</figcaption>
          </figure>
          <h3 className="org-table__name">
            {sample?.firstName ?? 'Hello'}, your organization's trails are live on
            OurHike.
          </h3>
          <p className="org-panel__note">
            {orgName} has published {sectionsPublished.toLocaleString()} sections and{' '}
            {hikesPublished.toLocaleString()} featured hikes to OurHike — a free,
            open-source offline map. Hikers walking your trails can now see them drawn
            from your own data, and tell you when something is wrong.
          </p>

          {sample?.role && sample.section ? (
            <div className="org-card">
              <p className="org-mono">Your role</p>
              <p className="org-table__name">
                {sample.role} · {sample.section}
              </p>
              {sample.sectionRange ? (
                <p className="org-mono">{sample.sectionRange}</p>
              ) : null}
              {sample.supervisor ? (
                <p className="org-mono">Supervisor: {sample.supervisor}</p>
              ) : (
                <p className="org-mono">
                  No supervisor on this section yet — your reports reach the organization
                  directly.
                </p>
              )}
            </div>
          ) : (
            <div className="org-card">
              <p className="org-mono">No role yet</p>
              <p className="org-panel__note">
                Nothing is assigned to you, so this letter points at the workdays instead
                of a stretch of trail. Turning up to one is how most people start.
              </p>
            </div>
          )}

          <span className="org-eyebrow">Three things you can do this week</span>
          <ul className="org-stack" style={{ margin: 0, paddingLeft: 18 }}>
            <li className="org-panel__note">
              Download your section so it works with no signal — the whole corridor fits
              on a phone.
            </li>
            <li className="org-panel__note">
              Report a blowdown, a dry spring or a missing blaze in three taps. It reaches
              you and your supervisor.
            </li>
            <li className="org-panel__note">
              Log your hours. The record is yours first; the organization confirms it
              afterwards for its own reporting.
            </li>
          </ul>
          <div className="org-inline">
            <span className="org-btn org-btn--small">
              {sample?.section ? 'Open your section' : 'See the workdays'}
            </span>
            <span className="org-btn org-btn--ghost org-btn--small">
              Pick a trail name
            </span>
          </div>
          <p className="org-mono">
            Your name is never shown publicly unless you ask to be credited. OurHike sends
            no push notifications, and you can leave any time — your logbook exports as a
            file you keep. This is a beta: carry a paper map.
          </p>
        </div>
      </section>
    </>
  )
}
