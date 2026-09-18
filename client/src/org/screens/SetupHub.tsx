/**
 * One screen with two lives: the stage checklist while an org is onboarding,
 * then its permanent management home.
 *
 * **ONE SCREEN AND NOT TWO**, which is a decision rather than an economy. An
 * organization that finishes onboarding does not want its console to move;
 * the address is the same, the rail entry is the same, and what changes is
 * what the screen has to say. Splitting them would mean a bookmark that stops
 * working on the day the trails go live.
 *
 * **"APPROVED IS NOT PUBLISHED" IS THE SENTENCE THIS SCREEN EXISTS TO SAY.**
 * A merged proposal still has to be built into map tiles and offline packs
 * before a hiker on the trail sees it, and an organization that has just
 * merged something and cannot find it on a phone will ask us why. The release
 * panel is where that answer lives, with its four real timestamps, rather
 * than in a support reply.
 */

import { ConsoleTiles, PageHeader, type ConsoleTile } from '../components'
import type { Org, OrgPark } from '../orgApi'

export interface Proposal {
  readonly id: string
  readonly title: string
  readonly reference: string
  readonly proposedBy: string
  readonly when: string
  readonly approvals: number
  readonly approvalsNeeded: number
}

export interface ReleaseStep {
  readonly label: string
  readonly detail: string
  readonly when: string
  readonly done: boolean
}

export interface Release {
  readonly title: string
  readonly reference: string
  readonly live: boolean
  readonly steps: readonly ReleaseStep[]
}

export interface SetupHubProps {
  readonly org: Org
  readonly onboarded: boolean
  readonly registry: readonly OrgPark[]
  readonly proposals: readonly Proposal[]
  readonly releases: readonly Release[]
  readonly roleCount: number
  readonly coverageGaps: number
  readonly regions: readonly string[]
  readonly onOpen: (page: 'approve' | 'registry' | 'signoff' | 'addtrail') => void
  readonly onOpenEmbeds: () => void
  readonly onOpenSettings: () => void
  readonly stageProgress: { readonly done: number; readonly total: number }
}

function sectionCount(registry: readonly OrgPark[]): number {
  return registry.reduce(
    (total, park) =>
      total + park.trails.reduce((sum, trail) => sum + trail.sections.length, 0),
    0,
  )
}

export function SetupHub({
  org,
  onboarded,
  registry,
  proposals,
  releases,
  roleCount,
  coverageGaps,
  regions,
  onOpen,
  onOpenEmbeds,
  onOpenSettings,
  stageProgress,
}: SetupHubProps) {
  const sections = sectionCount(registry)
  const trails = registry.reduce((total, park) => total + park.trails.length, 0)

  const stages = [
    {
      key: 'registered',
      title: 'Org registered',
      body: org.domain
        ? `${org.domain} verified by ${org.verified_by === 'dns' ? 'a DNS record' : 'an email at the domain'}. ${org.admins.length} admins on file${org.membership_url ? ', giving pages linked' : ''}.`
        : 'Registered. No domain on file yet.',
      state: 'done' as const,
      label: 'done',
      open: null,
    },
    {
      key: 'approve',
      title: 'Admins approve',
      body: `${org.admins.filter((seat) => seat.approved_at).length} of ${Math.max(3, org.admins.length)} have said yes. Whoever answers first picks up the registry.`,
      state: org.admins.every((seat) => seat.approved_at)
        ? ('done' as const)
        : ('waiting' as const),
      label: `${org.admins.filter((seat) => seat.approved_at).length} of ${Math.max(3, org.admins.length)}`,
      open: 'approve' as const,
    },
    {
      key: 'registry',
      title: 'Hike registry',
      body: 'Featured hikes and your GIS sections, read with you.',
      state: sections > 0 ? ('done' as const) : ('waiting' as const),
      label: sections > 0 ? `${sections} sections` : 'your turn',
      open: 'registry' as const,
    },
    {
      key: 'signoff',
      title: 'Registry sign-off',
      body: 'All three admins confirm it is accurate. Publishing your trails ends onboarding.',
      state: onboarded ? ('done' as const) : ('quiet' as const),
      label: onboarded ? 'done' : 'after the registry',
      open: 'signoff' as const,
    },
    {
      key: 'volunteers',
      title: 'Then: manage volunteers',
      body: 'Roles, the coverage report, loading your roster and welcoming them. Ongoing work, not a stage — it unlocks here and stays.',
      state: 'quiet' as const,
      label: onboarded ? 'open' : 'after sign-off',
      open: null,
    },
  ]

  const tiles: ConsoleTile[] = [
    {
      key: 'details',
      label: 'Org details',
      value: org.domain ?? org.name,
      meta: org.verified_by
        ? `verified by ${org.verified_by === 'dns' ? 'DNS' : 'email'}`
        : 'not verified',
      action: (
        <button
          type="button"
          className="org-btn org-btn--ghost org-btn--small"
          onClick={onOpenSettings}
        >
          Edit
        </button>
      ),
    },
    {
      key: 'admins',
      label: 'Admins and codeowners',
      value: `${org.admins.length} on file`,
      meta: 'all of them own the registry files',
      action: (
        <button
          type="button"
          className="org-btn org-btn--ghost org-btn--small"
          onClick={() => onOpen('approve')}
        >
          Edit
        </button>
      ),
    },
    {
      key: 'giving',
      label: 'Giving links',
      value:
        [org.membership_url, org.donation_url].filter(Boolean).join(' · ') || 'none set',
      meta:
        sections > 0
          ? `shown on all ${sections} sections`
          : 'shown once your sections publish',
      action: (
        <button
          type="button"
          className="org-btn org-btn--ghost org-btn--small"
          onClick={onOpenSettings}
        >
          Edit
        </button>
      ),
    },
    {
      key: 'registry',
      label: 'Trails and sections',
      value: `${sections} sections · ${trails} trails · ${registry.length} parks`,
      meta: onboarded ? 'published' : 'not published yet',
      action: (
        <button
          type="button"
          className="org-btn org-btn--ghost org-btn--small"
          onClick={() => onOpen('addtrail')}
        >
          Add a trail
        </button>
      ),
    },
    {
      key: 'roles',
      label: 'Roles',
      value: `${roleCount} defined`,
      meta: `${coverageGaps} sections with nobody attached`,
      action: null,
    },
    {
      key: 'regions',
      label: 'Regions',
      value: regions.length ? regions.join(' · ') : 'none yet',
      meta: 'used by the coverage report only',
      action: null,
    },
  ]

  return (
    <>
      <PageHeader
        eyebrow={
          onboarded
            ? 'Org home · everything you publish'
            : 'Setup hub · home for the whole route'
        }
        title={org.name}
        sub={
          onboarded
            ? 'Anything below can change — every change is a proposal your codeowners approve, in the open.'
            : 'Any admin can pick up any stage. Nothing expires.'
        }
        glyph={
          <>
            <path d="M3 6.5 9 4l6 2.5L21 4v13.5L15 20l-6-2.5L3 20z" />
            <path d="M9 4v13.5M15 6.5V20" />
          </>
        }
        actions={
          <span className="org-mono">
            {onboarded
              ? `Live since ${new Date(org.created_at).getFullYear()}`
              : `${stageProgress.done} of ${stageProgress.total} done`}
          </span>
        }
      />

      {!onboarded ? (
        <section className="org-stack">
          {stages.map((stage) => (
            <div className="org-card org-panel" key={stage.key}>
              <div className="org-panel__head">
                <h2>{stage.title}</h2>
                <span
                  className="org-pill"
                  data-tone={stage.state}
                  style={{ marginLeft: 'auto' }}
                >
                  {stage.label}
                </span>
              </div>
              <p className="org-panel__note">{stage.body}</p>
              {stage.open ? (
                <div className="org-inline">
                  <button
                    type="button"
                    className="org-btn org-btn--ghost org-btn--small"
                    onClick={() => onOpen(stage.open!)}
                  >
                    Open
                  </button>
                </div>
              ) : null}
            </div>
          ))}
        </section>
      ) : null}

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Waiting on you</h2>
          <span className="org-panel__count">{proposals.length} open proposals</span>
        </div>
        <p className="org-panel__note">
          Nothing changes what hikers see until your codeowners approve it — including the
          nightly re-read of your own GIS. Our automation proposes; it does not publish.
        </p>
        {proposals.length === 0 ? (
          <div className="org-empty">
            <h3>Nothing is waiting</h3>
            <p>
              No proposals open. This is the ordinary state — a registry that never
              changes is a registry nobody is arguing with.
            </p>
          </div>
        ) : (
          <div className="org-stack">
            {proposals.map((proposal) => (
              <div className="org-card" key={proposal.id}>
                <div className="org-inline">
                  <span className="org-table__name">{proposal.title}</span>
                  <span className="org-mono">{proposal.reference}</span>
                  <span className="org-mono">· proposed by {proposal.proposedBy}</span>
                  <span className="org-mono">· {proposal.when}</span>
                  <span
                    className="org-pill"
                    data-tone={
                      proposal.approvals >= proposal.approvalsNeeded ? 'done' : 'waiting'
                    }
                    style={{ marginLeft: 'auto' }}
                  >
                    {proposal.approvals} of {proposal.approvalsNeeded} approvals
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Approved is not published</h2>
          <span className="org-panel__count">
            {releases.filter((release) => !release.live).length} waiting on a build
          </span>
        </div>
        <p className="org-panel__note">
          A merged proposal still has to be built into map tiles and offline packs before
          a hiker on the trail sees it. This is where that sits — you never have to guess.
        </p>
        <div className="org-stack">
          {releases.map((release) => (
            <div className="org-card org-panel" key={release.reference}>
              <div className="org-panel__head">
                <h2>{release.title}</h2>
                <span
                  className="org-pill"
                  data-tone={release.live ? 'done' : 'waiting'}
                  style={{ marginLeft: 'auto' }}
                >
                  {release.live ? 'live to hikers' : 'waiting on the build'}
                </span>
              </div>
              <p className="org-mono">{release.reference}</p>
              <ol
                className="org-stack"
                style={{ listStyle: 'none', padding: 0, margin: 0 }}
              >
                {release.steps.map((step) => (
                  <li className="org-inline" key={step.label}>
                    <span className="org-pill" data-tone={step.done ? 'done' : 'quiet'}>
                      {step.done ? '✓' : '·'}
                    </span>
                    <span className="org-table__name">{step.label}</span>
                    <span className="org-panel__note">{step.detail}</span>
                    <span className="org-mono" style={{ marginLeft: 'auto' }}>
                      {step.when}
                    </span>
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>
        <div className="org-callout" data-tone="info">
          <span>
            We email your admins the moment it goes live, and again if a build fails.
            Offline packs already on a hiker's phone refresh next time they open the app
            on wifi.
          </span>
        </div>
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>What you have published</h2>
          <span className="org-panel__count">live now · edit anything</span>
        </div>
        <p className="org-panel__note">
          Each card is what a hiker sees today. Editing one opens a proposal — the same
          pull request your registry went through the first time.
        </p>
        <ConsoleTiles tiles={tiles} />
      </section>

      <section className="org-panel">
        <div className="org-panel__head">
          <h2>Put this on your own website</h2>
          <span className="org-panel__count">3 public · 1 private</span>
        </div>
        <p className="org-panel__note">
          The first three are one line of HTML and a script tag, public, no account needed
          to view. The fourth is the private console — same paste, plus one call from your
          server to vouch for whoever is signed in. All four read your published registry,
          so they stay current without you touching them, and they carry your own
          membership and donation links, not ours.
        </p>
        <div className="org-inline">
          <button type="button" className="org-btn org-btn--ghost" onClick={onOpenEmbeds}>
            Get the paste snippets
          </button>
        </div>
      </section>

      <div className="org-callout" data-tone="good">
        <span>
          <strong>Nothing here is overwritten.</strong> Every change is dated, so a report
          written three weeks ago still routes to whoever covered that mile then.
        </span>
      </div>
    </>
  )
}
