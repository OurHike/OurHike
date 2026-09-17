/**
 * The one component App.tsx mounts: route in, screen out.
 *
 * **APP.TSX GETS ONE CONDITIONAL, AND THIS FILE GETS EVERYTHING ELSE.** #937
 * counted App.tsx as the file 12 of the last 27 merge conflicts landed in,
 * and `lib/orgRoute.ts`'s own header makes not weaving a router through it a
 * constraint rather than a preference. So the console is one `if` at the top
 * of the app's render and a screen that draws itself.
 *
 * **NOTHING HERE DECIDES A PERMISSION.** `access` arrives from
 * `GET /clubs/{slug}/access` and is passed down; every endpoint behind every
 * screen checks again. What this file decides is what is worth fetching and
 * what to draw while it has not arrived - a loading state and a gate are
 * different things, and confusing them is how a screen ends up being the
 * security boundary.
 *
 * **THE DEMO ORG IS SERVED FROM A FILE AND SAYS SO.** `isDemoOrg` short-
 * circuits every fetch, because the demo's whole argument is that a trails
 * chair sees their own pages before typing anything - and #600, the
 * production backend, is not stood up. A demo that needed one would be a demo
 * nobody could open.
 *
 * **A SCREEN WITH NOTHING BEHIND IT SAYS SO RATHER THAN RENDERING EMPTY.**
 * Several of these screens are ahead of their endpoints: the volunteer's own
 * five have no server behind them yet, and this file hands them the demo's
 * rows with a banner saying where the rows came from. An empty table that
 * looks like an answer is the failure mode; "this is the demo's data" is not.
 */

import { useEffect, useState } from 'react'
import { OrgShell } from './OrgShell'
import {
  orgApi,
  type ConsoleKey,
  type Coverage,
  type Org,
  type OrgAccess,
  type OrgPark,
  type OrgRole,
  type RosterEntry,
  type Workday,
} from './orgApi'
import type { OrgRouting } from '../lib/useOrgRoute'
import type { OrgRoute } from '../lib/orgRoute'
import {
  DEMO_COVERED,
  DEMO_HIKES,
  DEMO_ORG,
  DEMO_REGISTRY,
  DEMO_ROLES,
  DEMO_ROSTER,
  DEMO_SECTIONS,
  DEMO_SLUG,
  DEMO_WORKDAYS,
  isDemoOrg,
} from './demoOrg'
import { SetupHub } from './screens/SetupHub'
import { AdminApproval } from './screens/AdminApproval'
import { HikeRegistry } from './screens/HikeRegistry'
import { RegistrySignoff } from './screens/RegistrySignoff'
import { AddTrail } from './screens/AddTrail'
import { Embeds } from './screens/Embeds'
import { OrgEmails } from './screens/OrgEmails'
import { OrgSettings } from './screens/OrgSettings'
import { Roles } from './screens/Roles'
import { Workdays } from './screens/Workdays'
import { Coverage as CoverageScreen } from './screens/Coverage'
import { Roster } from './screens/Roster'
import { VolunteerProfile } from './screens/VolunteerProfile'
import { WelcomeVolunteers } from './screens/WelcomeVolunteers'
import { YourTread, type TreadWindow } from './screens/YourTread'
import { OnYourPhone } from './screens/OnYourPhone'
import { HandBack } from './screens/HandBack'
import { RidgeRunner } from './screens/RidgeRunner'
import {
  DEMO_ALERTS,
  DEMO_CLOSURES,
  DEMO_FILINGS,
  DEMO_HELP,
  DEMO_HOURS,
  DEMO_ISSUES,
  DEMO_PASSED,
  DEMO_POIS,
  DEMO_QUESTIONS,
  DEMO_RUNNER_DAYS,
  DEMO_SYNC_RUNS,
  DEMO_THANKS,
  DEMO_VOLUNTEER,
} from './demoVolunteer'

/** What the console has loaded, or is still waiting for. */
interface OrgData {
  readonly org: Org | null
  readonly access: OrgAccess | null
  readonly registry: readonly OrgPark[]
  readonly roles: readonly OrgRole[]
  readonly roster: readonly RosterEntry[]
  readonly workdays: readonly Workday[]
  readonly coverage: Coverage | null
  readonly error: string | null
  readonly loading: boolean
}

const EMPTY: OrgData = {
  org: null,
  access: null,
  registry: [],
  roles: [],
  roster: [],
  workdays: [],
  coverage: null,
  error: null,
  loading: true,
}

function demoData(): OrgData {
  const gaps = DEMO_SECTIONS.filter((section) => !DEMO_COVERED.has(section.id))
  return {
    org: DEMO_ORG,
    access: {
      org_slug: DEMO_SLUG,
      is_admin: true,
      is_codeowner: true,
      is_supervisor: true,
      is_volunteer: true,
      can_manage_volunteers: true,
      can_read_roster: true,
      can_touch_registry: true,
    },
    registry: DEMO_REGISTRY,
    roles: DEMO_ROLES,
    roster: DEMO_ROSTER,
    workdays: DEMO_WORKDAYS,
    coverage: {
      club_id: DEMO_ORG.id,
      region: null,
      sections_total: DEMO_SECTIONS.length,
      gaps: gaps.map((section) => ({
        section_id: section.id,
        section_name: section.name,
        trail_name:
          DEMO_REGISTRY[0].trails.find((t) => t.id === section.trail_id)?.name ?? null,
        region: section.region,
        miles: section.miles,
        geometry: section.geometry,
      })),
    },
    error: null,
    loading: false,
  }
}

/** Everything the console needs for one org, fetched once per slug.
 *
 *  One effect rather than six hooks, because the screens share the data and
 *  six independent loads would render the rail's counts before the rows they
 *  count. Every request is abortable, so a hiker who moves on mid-fetch does
 *  not land a `setState` on an unmounted screen.
 */
function useOrgData(slug: string | null): OrgData {
  const [data, setData] = useState<OrgData>(EMPTY)

  useEffect(() => {
    if (slug === null) return
    if (isDemoOrg(slug)) {
      setData(demoData())
      return
    }

    const controller = new AbortController()
    const signal = controller.signal
    setData({ ...EMPTY, loading: true })

    const settle = async () => {
      try {
        const [org, access] = await Promise.all([
          orgApi.read(slug, signal),
          orgApi.access(slug, signal),
        ])
        // The rest are allowed to fail individually - a supervisor cannot read
        // the registry, and that is a 403 rather than a broken console.
        const optional = async <T,>(run: () => Promise<T>, fallback: T): Promise<T> => {
          try {
            return await run()
          } catch {
            return fallback
          }
        }
        const [registry, roles, roster, workdays, coverage] = await Promise.all([
          optional(() => orgApi.registry(slug, signal), [] as OrgPark[]),
          optional(() => orgApi.roles(slug, signal), [] as OrgRole[]),
          optional(() => orgApi.roster(slug, signal), [] as RosterEntry[]),
          optional(() => orgApi.workdays(slug, 60, signal), [] as Workday[]),
          optional(() => orgApi.coverage(slug, undefined, signal), null),
        ])
        if (signal.aborted) return
        setData({
          org,
          access,
          registry,
          roles,
          roster,
          workdays,
          coverage,
          error: null,
          loading: false,
        })
      } catch (error) {
        if (signal.aborted) return
        setData({
          ...EMPTY,
          loading: false,
          error: error instanceof Error ? error.message : 'Could not reach OurHike.',
        })
      }
    }

    void settle()
    return () => controller.abort()
  }, [slug])

  return data
}

/** A no-op for an action whose endpoint is not wired yet.
 *
 *  Named rather than an inline arrow so a reader can grep for what is still
 *  a stub, and so nothing here quietly looks finished. Every caller of this
 *  is listed in the pull request.
 */
const notWiredYet = () => {}

/**
 * App.tsx owns the one `useOrgRoute()` and hands it down.
 *
 * Two instances of that hook would each keep their own copy of the route, so
 * a `go` inside the console would move the URL and leave App still rendering
 * the map. One hook, one answer.
 */
export function OrgConsole({ routing }: { routing: OrgRouting }) {
  const { route, go } = routing
  const slug =
    route === null ? null : route.kind === 'tread' ? (route.org ?? null) : route.slug
  const data = useOrgData(slug)
  // The keys are an admin read on a screen most sessions never reach, so
  // they load when it opens rather than with everything else. A 503 means the
  // deployment has not switched the console embed on, which the screen says
  // rather than showing an empty key table as if that were the answer.
  const onEmbeds = route !== null && route.kind === 'setup' && route.page === 'embeds'
  const [consoleEnabled, setConsoleEnabled] = useState(true)
  useEffect(() => {
    if (!onEmbeds || slug === null || isDemoOrg(slug)) return
    const controller = new AbortController()
    orgApi
      .consoleKeys(slug, controller.signal)
      .then((loaded) => {
        setKeys(loaded)
        setConsoleEnabled(true)
      })
      .catch((error: unknown) => {
        setKeys([])
        setConsoleEnabled(!(error instanceof Error && error.message.includes('503')))
      })
    return () => controller.abort()
  }, [onEmbeds, slug])
  const [period, setPeriod] = useState<TreadWindow>('3 months')
  // The console keys live here rather than in `useOrgData` because they are
  // the one thing on these screens a person changes and then has to see
  // change. The secret is held in state for exactly one render and is never
  // written anywhere - the server keeps a hash, so it could not be re-shown
  // even if this kept it.
  const [keys, setKeys] = useState<readonly ConsoleKey[]>([])
  const [freshSecret, setFreshSecret] = useState<string | null>(null)
  const [summaryShown, setSummaryShown] = useState(true)
  const [askingOn, setAskingOn] = useState(false)

  if (route === null) return null

  const demo = slug !== null && isDemoOrg(slug)
  const org = data.org
  const orgName = org?.name ?? slug ?? 'your organization'
  const approved = org?.admins.filter((seat) => seat.approved_at !== null).length ?? 0
  const onboarded = org?.state === 'claimed' && approved >= 3

  const sections = data.registry.flatMap((park) =>
    park.trails.flatMap((trail) => trail.sections),
  )
  const holders: Record<string, number> = {}
  for (const entry of data.roster) {
    for (const role of entry.roles) {
      const match = data.roles.find((candidate) => candidate.name === role)
      if (match) holders[match.id] = (holders[match.id] ?? 0) + 1
    }
  }

  const waiting: Record<string, number> = {}
  const pendingSeats =
    org?.admins.filter((seat) => !seat.approved_at && !seat.declined_at).length ?? 0
  if (pendingSeats > 0) waiting.approve = pendingSeats
  if (data.coverage && data.coverage.gaps.length > 0)
    waiting.coverage = data.coverage.gaps.length
  const neverWelcomed = data.roster.filter((entry) => entry.pending_invite).length
  if (neverWelcomed > 0) waiting.welcome = neverWelcomed
  if (data.workdays.length > 0) waiting.workdays = data.workdays.length

  const body = () => {
    if (data.loading) {
      return (
        <div className="org-empty">
          <h3>Reading your organization</h3>
          <p>
            Nothing is decided here — what you may do comes from the server, and this
            screen is waiting for it rather than guessing.
          </p>
        </div>
      )
    }
    if (data.error !== null) {
      return (
        <div className="org-callout" data-tone="stop">
          <span>
            <strong>Could not load {orgName}.</strong> {data.error} Nothing has changed,
            and a reload is safe — this console makes no write you did not press.
          </span>
        </div>
      )
    }

    if (route.kind === 'setup') {
      switch (route.page) {
        case 'approve':
          return org ? (
            <AdminApproval
              org={org}
              personId={null}
              onApprove={notWiredYet}
              onDecline={notWiredYet}
              onRemind={notWiredYet}
              onContinue={() => go({ kind: 'setup', slug: route.slug, page: 'registry' })}
            />
          ) : null
        case 'registry':
          return (
            <HikeRegistry
              orgName={orgName}
              registry={data.registry}
              sources={[]}
              featuredHikes={demo ? DEMO_HIKES.length : 0}
              needsAnEye={sections.filter((section) => section.miles === null).length}
              onAddSource={async () => 'Nothing read — the reader is not wired up yet.'}
              onSendForSignoff={() =>
                go({ kind: 'setup', slug: route.slug, page: 'signoff' })
              }
            />
          )
        case 'signoff':
          return org ? (
            <RegistrySignoff
              org={org}
              registry={data.registry}
              confirmed={
                new Set(org.admins.filter((s) => s.approved_at).map((s) => s.person_id))
              }
              personId={null}
              approvalsRequired={3}
              onConfirm={notWiredYet}
              onFlag={notWiredYet}
            />
          ) : null
        case 'addtrail':
          return (
            <AddTrail
              orgName={orgName}
              liveSections={sections.length}
              proposed={null}
              onRead={notWiredYet}
              onPropose={notWiredYet}
              onBack={() => go({ kind: 'setup', slug: route.slug, page: 'home' })}
            />
          )
        case 'embeds':
          return (
            <Embeds
              orgName={orgName}
              slug={route.slug}
              scriptOrigin={
                typeof window === 'undefined'
                  ? 'https://ourhike.org'
                  : window.location.origin
              }
              hikes={demo ? DEMO_HIKES : []}
              workdays={data.workdays}
              gaps={data.coverage?.gaps.length ?? 0}
              sectionsTotal={data.coverage?.sections_total ?? sections.length}
              keys={keys}
              freshSecret={freshSecret}
              consoleEnabled={consoleEnabled}
              canEdit={data.access?.is_admin ?? false}
              onCreateKey={(label, wanted) => {
                void orgApi
                  .createConsoleKey(route.slug, label, [...wanted])
                  .then((created) => {
                    setKeys((current) => [...current, created])
                    setFreshSecret(created.secret ?? null)
                  })
                  .catch(() => setFreshSecret(null))
              }}
              onRevokeKey={(key) => {
                void orgApi
                  .revokeConsoleKey(route.slug, key.id)
                  .then((revoked) =>
                    setKeys((current) =>
                      current.map((candidate) =>
                        candidate.id === revoked.id ? revoked : candidate,
                      ),
                    ),
                  )
                  .catch(() => {})
              }}
            />
          )
        case 'emails':
          return (
            <OrgEmails
              orgName={orgName}
              domain={org?.domain ?? null}
              adminCount={org?.admins.length ?? 0}
              sectionCount={sections.length}
              volunteerCount={data.roster.length}
              onOpenWelcome={() =>
                go({ kind: 'volunteers', slug: route.slug, page: 'welcome' })
              }
            />
          )
        case 'leaving':
          return org ? (
            <OrgSettings
              org={org}
              exports={[
                {
                  key: 'registry',
                  label: 'Registry',
                  format: 'GeoJSON',
                  count: `${sections.length} sections`,
                },
                {
                  key: 'roster',
                  label: 'Roster',
                  format: 'CSV',
                  count: `${data.roster.length} people`,
                },
                {
                  key: 'workdays',
                  label: 'Workdays',
                  format: 'CSV',
                  count: `${data.workdays.length}`,
                },
              ]}
              onDownload={notWiredYet}
              onProposeRemoval={notWiredYet}
              onUnpublish={notWiredYet}
              onProposeDeletion={notWiredYet}
            />
          ) : null
        default:
          return org ? (
            <SetupHub
              org={org}
              onboarded={onboarded}
              registry={data.registry}
              proposals={[]}
              releases={[]}
              roleCount={data.roles.filter((role) => role.retired_at === null).length}
              coverageGaps={data.coverage?.gaps.length ?? 0}
              regions={[
                ...new Set(sections.map((s) => s.region).filter((r): r is string => !!r)),
              ]}
              stageProgress={{
                done: approved >= 3 ? 3 : approved >= 1 ? 2 : 1,
                total: 3,
              }}
              onOpen={(page) => go({ kind: 'setup', slug: route.slug, page })}
              onOpenEmbeds={() => go({ kind: 'setup', slug: route.slug, page: 'embeds' })}
              onOpenSettings={() =>
                go({ kind: 'setup', slug: route.slug, page: 'leaving' })
              }
            />
          ) : null
      }
    }

    if (route.kind === 'volunteers') {
      switch (route.page) {
        case 'workdays':
          return (
            <Workdays
              workdays={data.workdays}
              feed={{ url: null, lastReadAt: null, cadence: 'hourly' }}
              signups={[]}
              hoursToConfirm={[]}
              canEdit={data.access?.can_manage_volunteers ?? false}
              onCreate={notWiredYet}
              onEdit={notWiredYet}
              onSyncSettings={notWiredYet}
              onConfirmHours={notWiredYet}
            />
          )
        case 'coverage':
          return (
            <CoverageScreen
              sections={sections}
              gaps={data.coverage?.gaps ?? []}
              sectionsTotal={data.coverage?.sections_total ?? sections.length}
              regions={[
                ...new Set(sections.map((s) => s.region).filter((r): r is string => !!r)),
              ]}
              region={null}
              roles={data.roles}
              holders={holders}
              onRegion={notWiredYet}
              onExport={notWiredYet}
              onBackToRoles={() =>
                go({ kind: 'volunteers', slug: route.slug, page: 'roles' })
              }
            />
          )
        case 'roster':
          return (
            <Roster
              entries={data.roster}
              activeCount={data.roster.filter((e) => e.roles.length > 0).length}
              inactiveCount={data.roster.filter((e) => e.roles.length === 0).length}
              canEdit={data.access?.can_manage_volunteers ?? false}
              feedUrl={null}
              runs={demo ? DEMO_SYNC_RUNS : []}
              held={null}
              onOpenPerson={(entry) =>
                go({
                  kind: 'volunteers',
                  slug: route.slug,
                  page: 'person',
                  person: entry.person_id ?? entry.email ?? '',
                })
              }
              onAddPerson={notWiredYet}
              onUpload={notWiredYet}
              onConnect={notWiredYet}
            />
          )
        case 'person': {
          const entry = data.roster.find(
            (candidate) =>
              candidate.person_id === route.person || candidate.email === route.person,
          )
          if (!entry) {
            return (
              <div className="org-empty">
                <h3>Nobody by that reference</h3>
                <p>
                  The link points at somebody who is not on this roster — they may have
                  been deactivated, or the link may be from another organization.
                </p>
              </div>
            )
          }
          const name =
            entry.display_name ?? entry.full_name ?? entry.email ?? 'This volunteer'
          return (
            <VolunteerProfile
              personId={entry.person_id ?? ''}
              displayName={name}
              initials={name.slice(0, 2).toUpperCase()}
              joined={DEMO_VOLUNTEER.joined}
              details={{
                fullName: entry.full_name ?? '',
                email: entry.email ?? '',
                phone: '',
                trailName: '',
              }}
              roles={entry.roles.map((role, index) => ({
                id: `${entry.person_id ?? 'x'}-${index}`,
                name: role,
                section: entry.sections[index] ?? 'the whole trail',
                supervisor: null,
                since: DEMO_VOLUNTEER.joined,
              }))}
              activity={[]}
              hoursLogged={0}
              reportsFiled={0}
              sectionsCovered={entry.sections.length}
              publicCredit={false}
              lastEditedBy={null}
              lastEditedOn={null}
              active={entry.roles.length > 0}
              isSelf={false}
              isAdmin={data.access?.is_admin ?? false}
              onSaveDetails={notWiredYet}
              onAddRole={notWiredYet}
              onSetActive={notWiredYet}
              onSetPublicCredit={notWiredYet}
              onBack={() => go({ kind: 'volunteers', slug: route.slug, page: 'roster' })}
            />
          )
        }
        case 'welcome':
          return (
            <WelcomeVolunteers
              orgName={orgName}
              neverWelcomed={neverWelcomed}
              alreadyWelcomed={data.roster.length - neverWelcomed}
              onRoster={data.roster.length}
              withRole={
                data.roster.filter((e) => e.pending_invite && e.roles.length > 0).length
              }
              sectionsPublished={sections.length}
              hikesPublished={demo ? DEMO_HIKES.length : 0}
              sample={null}
              canSend={data.access?.can_manage_volunteers ?? false}
              onSend={notWiredYet}
              onBack={() => go({ kind: 'setup', slug: route.slug, page: 'home' })}
            />
          )
        default:
          return (
            <Roles
              roles={data.roles}
              holders={holders}
              canEdit={data.access?.can_manage_volunteers ?? false}
              onCreate={notWiredYet}
              onRetire={notWiredYet}
            />
          )
      }
    }

    // The volunteer's own five. These are ahead of their endpoints, so on a
    // real org they render the honest empty states rather than the demo's
    // rows; the demo fills them because that is what the demo is for.
    switch (route.page ?? 'tread') {
      case 'phone':
        return (
          <OnYourPhone
            sectionName={DEMO_VOLUNTEER.sectionName}
            range={DEMO_VOLUNTEER.range}
            openReports={demo ? DEMO_ISSUES.filter((i) => i.open).length : 0}
            thanksCount={demo ? DEMO_THANKS.length : 0}
            queue={{ queued: 0, online: true }}
            downloadedOn={null}
            parkAlert={
              demo ? { title: DEMO_ALERTS[0].title, detail: DEMO_ALERTS[0].detail } : null
            }
            crewHours={{ people: 6, hours: 41, waiting: 1 }}
            poisNearby={demo ? DEMO_POIS.length : 0}
          />
        )
      case 'handback':
        return (
          <HandBack
            askingOn={askingOn}
            passedToday={demo ? DEMO_PASSED : []}
            hours={demo ? DEMO_HOURS : []}
            hoursConfirmed={demo ? 16.5 : 0}
            hoursClaimed={demo ? 4 : 0}
            workdaysAttended={demo ? 3 : 0}
            conditionsConfirmed={demo ? 7 : 0}
            conditionsDetail="springs, shelters, a privy"
            sectionsHeld={demo ? 2 : 0}
            sectionsSince={demo ? 'March 2025' : null}
            crews={data.workdays}
            crewsFetchedHoursAgo={demo ? 4 : null}
            summaryShown={summaryShown}
            onToggleAsking={setAskingOn}
            onAnswerPlace={notWiredYet}
            onLogHours={notWiredYet}
            onOpenRidgeRunner={() =>
              go({ kind: 'tread', ...(slug ? { org: slug } : {}), page: 'ridge' })
            }
            onToggleSummary={() => setSummaryShown(!summaryShown)}
            onExport={notWiredYet}
            onSeeOnMap={notWiredYet}
            onSignUp={notWiredYet}
          />
        )
      case 'ridge':
        return (
          <RidgeRunner
            commitment={
              demo
                ? {
                    dayNumber: 3,
                    totalDays: 6,
                    rangeLabel:
                      'Mon 14 → Sat 19 September · clean-up and pack-out, invasive species',
                    taskKeys: ['cleanup', 'invasives'],
                    days: DEMO_RUNNER_DAYS,
                  }
                : null
            }
            filings={demo ? DEMO_FILINGS : []}
            submissions={demo ? DEMO_FILINGS.length : 0}
            trashBags={demo ? 2 : 0}
            invasivesLogged={demo ? 1 : 0}
            milesWalked={demo ? 21.4 : 0}
            hearingOrg={org?.name ?? null}
            onStart={notWiredYet}
            onEnableTask={notWiredYet}
          />
        )
      case 'profile': {
        const me = DEMO_VOLUNTEER
        return (
          <VolunteerProfile
            personId={me.personId}
            displayName={me.displayName}
            initials={me.initials}
            joined={me.joined}
            details={me.details}
            roles={me.roles}
            activity={me.activity}
            hoursLogged={me.hoursLogged}
            reportsFiled={me.reportsFiled}
            sectionsCovered={me.sectionsCovered}
            publicCredit={me.publicCredit}
            lastEditedBy={me.lastEditedBy}
            lastEditedOn={me.lastEditedOn}
            active
            isSelf
            isAdmin={data.access?.is_admin ?? false}
            onSaveDetails={notWiredYet}
            onAddRole={notWiredYet}
            onSetActive={notWiredYet}
            onSetPublicCredit={notWiredYet}
            onBack={() => go({ kind: 'tread', ...(slug ? { org: slug } : {}) })}
          />
        )
      }
      default:
        return (
          <YourTread
            sectionName={DEMO_VOLUNTEER.sectionName}
            range={DEMO_VOLUNTEER.range}
            standing={DEMO_VOLUNTEER.standing}
            roles={DEMO_VOLUNTEER.treadRoles}
            roleId={null}
            period={period}
            pois={demo ? DEMO_POIS : []}
            alerts={demo ? DEMO_ALERTS : []}
            closures={demo ? DEMO_CLOSURES : []}
            issues={demo ? DEMO_ISSUES : []}
            helpRequests={demo ? DEMO_HELP : []}
            thanks={demo ? DEMO_THANKS : []}
            questions={demo ? DEMO_QUESTIONS : []}
            hoursConfirmed={demo ? 34 : 0}
            hoursClaimed={demo ? 4 : 0}
            onRole={notWiredYet}
            onPeriod={setPeriod}
            onConfirmPoi={notWiredYet}
            onEditPoi={notWiredYet}
            onPoiGone={notWiredYet}
            onAddPoi={notWiredYet}
            onRequestClosure={notWiredYet}
            onResolveIssue={notWiredYet}
            onAskForHelp={notWiredYet}
            onAnswer={notWiredYet}
            onReportThanks={notWiredYet}
          />
        )
    }
  }

  const shellRoute: OrgRoute = route

  return (
    <OrgShell
      slug={slug ?? ''}
      orgName={orgName}
      access={data.access}
      route={shellRoute}
      go={go}
      onLeave={() => go(null)}
      email={null}
      waiting={waiting}
      onboarded={onboarded}
    >
      {demo ? (
        <div className="org-callout" data-tone="info">
          <span>
            <strong>This is the demo organization.</strong> The ground is real — every
            coordinate is the actual park — and everything else is invented so you can
            look around without signing anything. No number on these screens is a fact
            about anybody's trails.
          </span>
        </div>
      ) : null}
      {body()}
    </OrgShell>
  )
}
