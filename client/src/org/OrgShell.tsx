/**
 * The frame every organization screen renders inside: rail, top bar, crumbs.
 *
 * TWO NAVIGATIONS, AND WHICH IS WHICH IS THE DESIGN'S OWN RULE: a left
 * sidebar for org work, a top bar for anything public-facing. So the rail
 * holds the console and the top bar holds the way back out to the pages a
 * hiker sees.
 *
 * **THE RAIL SHOWS ONLY WHAT THE SERVER SAYS THIS PERSON MAY DO.** `access`
 * comes from `GET /clubs/{slug}/access`, which resolves the seats they
 * actually hold; nothing here infers a permission and nothing here is a gate.
 * A supervisor sees Manage volunteers and not the registry because the server
 * said so, and every endpoint behind those screens checks again - the rail
 * decides what is worth drawing, never what is allowed.
 *
 * **A COUNT APPEARS ONLY ON SOMETHING AWAITING ACTION.** Three signups to
 * answer is a count; 312 sections is not. A badge showing a total teaches
 * people to ignore badges, and then the one that mattered goes unread.
 */

import { useMemo } from 'react'
import './orgConsole.css'
import { Mark } from './Mark'
import type { OrgAccess } from './orgApi'
import type { OrgRoute, SetupPage, TreadPage, VolunteerPage } from '../lib/orgRoute'

export interface OrgShellProps {
  readonly slug: string
  readonly orgName: string
  /** The caller's own seats here, from the server. */
  readonly access: OrgAccess | null
  /** Where the console is now, so the rail can mark it. */
  readonly route: OrgRoute
  readonly go: (route: OrgRoute) => void
  /** Leave the console for the app. */
  readonly onLeave: () => void
  /** Their address, for the top bar. Null when it could not be read. */
  readonly email: string | null
  /** Items awaiting action, by rail key. Absent means no badge. */
  readonly waiting?: Partial<Record<string, number>>
  /** Whether onboarding has been signed off, which changes the rail's first
   *  group from a stage checklist to a permanent home. */
  readonly onboarded: boolean
  readonly children: React.ReactNode
}

interface RailItem {
  readonly key: string
  readonly label: string
  readonly route: OrgRoute
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('')
}

/** Where the crumb strip says you are, and the aside beside it. */
function crumbsFor(
  route: OrgRoute,
  onboarded: boolean,
): { trail: string[]; aside: string } {
  if (route.kind === 'tread') {
    const names: Record<TreadPage, [string, string]> = {
      tread: ['Your Tread', 'your own miles'],
      phone: ['On your phone', 'four screens, 390px'],
      handback: ['What you hand back', "the hiker's half"],
      ridge: ['Ridge Runner At-Large', 'seven days, maximum'],
      profile: ['Your profile', 'yours to edit'],
    }
    const [here, aside] = names[route.page ?? 'tread']
    return { trail: ['Volunteer', here], aside }
  }
  if (route.kind === 'setup') {
    const group = onboarded ? 'Org home' : 'Onboarding'
    const names: Record<SetupPage, [string, string]> = {
      home: [
        onboarded ? 'Org home' : 'Setup hub',
        onboarded ? 'everything you publish' : '3 stages',
      ],
      approve: ['Admin approval', 'stage 1 of 3 · admins only'],
      registry: ['Hike registry', 'stage 2 of 3 · admins only'],
      signoff: ['Registry sign-off', 'stage 3 of 3 · three approvals'],
      addtrail: ['Add a trail', 'a scoped registry run'],
      emails: ['What we email on your behalf', 'every message, in full'],
      leaving: ['Settings and leaving', 'export, remove, unpublish, delete'],
    }
    const [here, aside] = names[route.page]
    return { trail: [group, here], aside }
  }
  const names: Record<VolunteerPage, [string, string]> = {
    roles: ['Roles', 'definitions and reporting lines'],
    workdays: ['Workdays', 'post, answer, confirm hours'],
    coverage: ['Coverage report', 'sections with no role attached'],
    roster: ['Your roster', 'three ways to load it'],
    person: ['Volunteer profile', "one person's record"],
    welcome: ['Welcome them', 'one email each, with their own section'],
  }
  const [here, aside] = names[route.page]
  return { trail: ['Manage volunteers', here], aside }
}

export function OrgShell({
  slug,
  orgName,
  access,
  route,
  go,
  onLeave,
  email,
  waiting = {},
  onboarded,
  children,
}: OrgShellProps) {
  const groups = useMemo(() => {
    const setup = (page: SetupPage): OrgRoute => ({ kind: 'setup', slug, page })
    const volunteers = (page: VolunteerPage): OrgRoute => ({
      kind: 'volunteers',
      slug,
      page,
    })

    const onboarding: RailItem[] = [
      { key: 'home', label: onboarded ? 'Org home' : 'Setup hub', route: setup('home') },
      { key: 'approve', label: 'Admin approval', route: setup('approve') },
      { key: 'registry', label: 'Hike registry', route: setup('registry') },
      { key: 'signoff', label: 'Registry sign-off', route: setup('signoff') },
      { key: 'addtrail', label: 'Add a trail', route: setup('addtrail') },
    ]

    // Add a trail is the one management item the registry gate owns: it is a
    // scoped registry run, and a supervisor who may run crews may not publish
    // a trail.
    const manage: RailItem[] = [
      { key: 'roles', label: 'Roles', route: volunteers('roles') },
      { key: 'workdays', label: 'Workdays', route: volunteers('workdays') },
      { key: 'coverage', label: 'Coverage report', route: volunteers('coverage') },
      { key: 'roster', label: 'Your roster', route: volunteers('roster') },
      { key: 'welcome', label: 'Welcome them', route: volunteers('welcome') },
    ]

    // `page` is left off the first entry so its address stays `/my/tread`,
    // which is what a welcome email links to.
    const volunteer: RailItem[] = [
      { key: 'tread', label: 'Your Tread', route: { kind: 'tread', org: slug } },
      {
        key: 'phone',
        label: 'On your phone',
        route: { kind: 'tread', org: slug, page: 'phone' },
      },
      {
        key: 'handback',
        label: 'What you hand back',
        route: { kind: 'tread', org: slug, page: 'handback' },
      },
      {
        key: 'ridge',
        label: 'Ridge Runner',
        route: { kind: 'tread', org: slug, page: 'ridge' },
      },
      {
        key: 'profile',
        label: 'Your profile',
        route: { kind: 'tread', org: slug, page: 'profile' },
      },
    ]

    return { onboarding, manage, volunteer }
  }, [slug, onboarded])

  const canRegistry = access?.can_touch_registry ?? false
  const canManage = access?.can_manage_volunteers ?? false
  const isVolunteer = access?.is_volunteer ?? false

  const { trail, aside } = crumbsFor(route, onboarded)

  const isHere = (item: RailItem): boolean => {
    if (item.route.kind !== route.kind) return false
    if (item.route.kind === 'tread') {
      // Both are tread routes; `undefined` and 'tread' are the same screen.
      return (
        (item.route.page ?? 'tread') === ((route as { page?: TreadPage }).page ?? 'tread')
      )
    }
    if (route.kind === 'tread') return false
    return item.route.page === route.page
  }

  const railGroup = (heading: string, items: RailItem[], note?: string) => (
    <nav className="org-nav" aria-label={heading}>
      <span className="org-nav__heading">{heading}</span>
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          className="org-nav__item"
          aria-current={isHere(item) ? 'page' : undefined}
          onClick={() => go(item.route)}
        >
          {item.label}
          {waiting[item.key] ? (
            <span className="org-nav__count">{waiting[item.key]}</span>
          ) : null}
        </button>
      ))}
      {note ? <p className="org-nav__note">{note}</p> : null}
    </nav>
  )

  return (
    <div className="org">
      <aside className="org__rail">
        <button
          type="button"
          className="org-switch"
          onClick={() => go({ kind: 'setup', slug, page: 'home' })}
        >
          <span className="org-switch__initials">{initials(orgName)}</span>
          <span className="org-switch__names">
            <span className="org-switch__name">{orgName}</span>
            <span className="org-switch__role">
              {[
                access?.is_admin ? 'Org admin' : null,
                access?.is_supervisor ? 'supervisor' : null,
                access?.is_volunteer ? 'maintainer' : null,
              ]
                .filter(Boolean)
                .join(' · ') || 'no seat here'}
            </span>
          </span>
        </button>

        {canRegistry
          ? railGroup(
              onboarded ? 'Org home' : 'Onboarding',
              groups.onboarding,
              onboarded ? undefined : 'Three stages, any admin, no expiry.',
            )
          : null}
        {canManage ? railGroup('Manage volunteers', groups.manage) : null}
        {isVolunteer || canManage ? railGroup('Volunteer', groups.volunteer) : null}

        <div className="org__rail-foot">
          {canRegistry ? (
            <>
              <button
                type="button"
                className="org-nav__item"
                aria-current={
                  route.kind === 'setup' && route.page === 'emails' ? 'page' : undefined
                }
                onClick={() => go({ kind: 'setup', slug, page: 'emails' })}
              >
                What we email on your behalf
              </button>
              <button
                type="button"
                className="org-nav__item"
                aria-current={
                  route.kind === 'setup' && route.page === 'leaving' ? 'page' : undefined
                }
                onClick={() => go({ kind: 'setup', slug, page: 'leaving' })}
              >
                Settings and leaving
              </button>
            </>
          ) : null}
        </div>
      </aside>

      <div className="org__main">
        <header className="org-top">
          <button type="button" className="org-top__brand" onClick={onLeave}>
            <Mark id="org-top-mark" size={26} />
            OurHike
          </button>
          <div className="org-top__links">
            <a className="org-top__link" href="/for-orgs/">
              For orgs
            </a>
            <a className="org-top__link" href="/for-orgs/demo/">
              Demo org
            </a>
            <a className="org-top__link" href="/for-orgs/nominate/">
              Nominate an org
            </a>
            <a className="org-top__link" href="/for-orgs/claim/">
              Claim your org
            </a>
          </div>
          <div className="org-top__who">
            <span className="org-top__avatar">
              {email ? initials(email.replace(/@.*/, '')) : '—'}
            </span>
            <span className="org-top__email">{email ?? 'signed out'}</span>
          </div>
        </header>

        <nav className="org-crumbs" aria-label="Breadcrumb">
          <span>{orgName}</span>
          <span className="org-crumbs__sep">›</span>
          <span>{trail[0]}</span>
          <span className="org-crumbs__sep">›</span>
          <span className="org-crumbs__here">{trail[1]}</span>
          <span className="org-crumbs__aside">{aside}</span>
        </nav>

        <main className="org__body">{children}</main>
      </div>
    </div>
  )
}
