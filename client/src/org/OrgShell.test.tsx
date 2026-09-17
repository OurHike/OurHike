/**
 * What the console rail offers each kind of person.
 *
 * **THE RAIL IS A DISPLAY DETAIL AND NEVER A GATE**, which is exactly why it
 * is worth testing: the server refuses every one of these endpoints on its
 * own (`backend/tests/test_org_permission_matrix.py` is the half that
 * matters), so a rail bug is not a hole - it is a supervisor being offered a
 * door that answers 403, or a maintainer being told their organization has
 * nothing in it. Both are how somebody decides this product does not work.
 *
 * The five people are the five the backend matrix uses, and the two files
 * should be read together.
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { OrgShell } from './OrgShell'
import type { OrgAccess } from './orgApi'
import type { ConsoleRoute } from '../lib/orgRoute'
import { readRepoFile } from '../test/repoFile'

const SLUG = 'ramapo-trail-conference'

// Explicit, the way every other component suite here does it: this project
// does not run Testing Library's auto-cleanup, so without it each render
// stacks on the last and `not.toContain` passes against a rail somebody
// else's test drew.
afterEach(cleanup)

/** One person's seats, as the server would answer them. */
function access(over: Partial<OrgAccess>): OrgAccess {
  const base = {
    org_slug: SLUG,
    is_admin: false,
    is_codeowner: false,
    is_supervisor: false,
    is_volunteer: false,
    can_manage_volunteers: false,
    can_read_roster: false,
    can_touch_registry: false,
    ...over,
  }
  // The derived three are derived on the server too, so a fixture that set
  // them independently could describe a person the server cannot produce.
  return {
    ...base,
    can_manage_volunteers: base.is_admin || base.is_supervisor,
    can_read_roster: base.is_admin || base.is_supervisor,
    can_touch_registry: base.is_admin,
  }
}

const ADMIN = access({ is_admin: true, is_volunteer: true })
const CODEOWNER = access({ is_admin: true, is_codeowner: true, is_volunteer: true })
const SUPERVISOR = access({ is_supervisor: true, is_volunteer: true })
const MAINTAINER = access({ is_volunteer: true })
const OUTSIDER = access({})

function draw(
  seat: OrgAccess | null,
  route: ConsoleRoute = { kind: 'setup', slug: SLUG, page: 'home' },
) {
  render(
    <OrgShell
      slug={SLUG}
      orgName="Ramapo Trail Conference"
      access={seat}
      route={route}
      go={vi.fn()}
      onLeave={vi.fn()}
      email={null}
      onboarded={false}
    >
      <p>the screen</p>
    </OrgShell>,
  )
}

/** Every rail button's label, in order. */
function railLabels(): string[] {
  return screen
    .getAllByRole('button')
    .map((button) => button.textContent?.trim() ?? '')
    .filter(Boolean)
}

describe('the rail offers each person what the server would let them do', () => {
  it('offers an admin the registry, the volunteers and their own miles', () => {
    draw(ADMIN)
    const labels = railLabels()

    expect(labels).toContain('Hike registry')
    expect(labels).toContain('Roles')
    expect(labels).toContain('Your Tread')
    expect(labels).toContain('Settings and leaving')
  })

  it('offers a codeowner the same rail as an admin', () => {
    // The two differ only at registry sign-off, which is a button ON that
    // screen rather than a rail entry - so a rail that told them apart would
    // be claiming a difference the console does not have.
    draw(CODEOWNER)
    const labels = railLabels()

    expect(labels).toContain('Hike registry')
    expect(labels).toContain('Registry sign-off')
  })

  it('offers a supervisor the volunteers and not the registry', () => {
    draw(SUPERVISOR)
    const labels = railLabels()

    expect(labels).toContain('Roles')
    expect(labels).toContain('Your roster')
    expect(labels).not.toContain('Hike registry')
    expect(labels).not.toContain('Put this on your site')
  })

  it('does not offer a supervisor the settings-and-leaving door', () => {
    // Deleting the organization and taking its data is an admin's act, and
    // an offered door that answers 403 teaches somebody to distrust the rail.
    draw(SUPERVISOR)

    expect(railLabels()).not.toContain('Settings and leaving')
  })

  it('offers a maintainer their own miles and nothing to manage', () => {
    draw(MAINTAINER)
    const labels = railLabels()

    expect(labels).toContain('Your Tread')
    expect(labels).toContain('What you hand back')
    expect(labels).not.toContain('Your roster')
    expect(labels).not.toContain('Hike registry')
  })

  it('offers somebody with no seat here nothing but the way out', () => {
    // Signed in, with an account, and no standing at THIS organization. The
    // rail is empty rather than absent, because the screen still has to say
    // where they are.
    draw(OUTSIDER)
    const labels = railLabels()

    expect(labels).not.toContain('Your Tread')
    expect(labels).not.toContain('Roles')
    expect(labels).not.toContain('Hike registry')
  })

  it('says plainly when somebody holds no seat, rather than leaving it blank', () => {
    draw(OUTSIDER)

    expect(screen.getByText('no seat here')).toBeInTheDocument()
  })

  it('names the seats somebody does hold', () => {
    draw(SUPERVISOR)

    expect(screen.getByText(/supervisor/)).toBeInTheDocument()
  })

  it('draws nothing it cannot justify while the server has not answered', () => {
    // `access` is null until `GET /access` returns. Guessing during that
    // window would flash a registry link at a supervisor, which is the one
    // moment the rail could teach somebody the wrong thing about themselves.
    draw(null)
    const labels = railLabels()

    expect(labels).not.toContain('Hike registry')
    expect(labels).not.toContain('Roles')
    expect(labels).not.toContain('Your Tread')
  })
})

describe('the crumbs say where you are', () => {
  it('names the volunteer screen a volunteer is on', () => {
    draw(MAINTAINER, { kind: 'tread', org: SLUG, page: 'handback' })

    // The crumb specifically. The rail carries the same words, and a
    // `getByText` that matched either would pass on a crumb strip that never
    // moved off the first screen.
    expect(document.querySelector('.org-crumbs__here')).toHaveTextContent(
      'What you hand back',
    )
  })

  it('distinguishes the five volunteer screens from each other', () => {
    draw(MAINTAINER, { kind: 'tread', org: SLUG, page: 'ridge' })

    // "Ridge Runner At-Large" is the crumb; the rail says "Ridge Runner".
    // That the two differ is the point of checking the crumb.
    expect(document.querySelector('.org-crumbs__here')).toHaveTextContent(
      'Ridge Runner At-Large',
    )
  })
})

/**
 * The console and the marketing site offer the same four doors.
 *
 * They did not until 2026-09-17: the shell put For orgs, Demo org, Nominate
 * an org and Claim your org across the top of every console screen, and
 * /for-orgs/ reached its three siblings only through a section most of a page
 * down. `site/src/components/OrgNav.astro` is the row that closed it, and it
 * is read here rather than duplicated so the two surfaces cannot drift apart
 * with both suites green.
 *
 * A person crossing between them should not have to work out that two labels
 * are the same door, which is why the LABELS are compared and not only the
 * addresses.
 */
describe('the four public doors', () => {
  it('names each door in the console exactly as the site names it', () => {
    const nav = readRepoFile('site/src/components/OrgNav.astro')
    const doors = [...nav.matchAll(/href: '([^']+)', label: '([^']+)'/g)].map(
      ([, href, label]) => ({ href, label }),
    )
    expect(doors.length, 'OrgNav.astro should declare four doors').toBe(4)

    draw(access({ is_admin: true }))

    for (const door of doors) {
      const link = screen.getByRole('link', { name: door.label })
      expect(link, `${door.label} should open ${door.href}`).toHaveAttribute(
        'href',
        door.href,
      )
    }
  })
})
