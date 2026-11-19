/**
 * The registry sign-off screen counts seats, not holders.
 *
 * WHY THIS TEST EXISTS. Since #1914 - GET /clubs publishes every admin's
 * account id and decline reason to anyone, and an account id is all it takes
 * to write into that person's private thanks inbox - a seat's `person_id` is
 * null to a viewer who is not one of the org's approved admins, except on
 * their own seat. OrgConsole built the sign-off screen's `confirmed` set from
 * `person_id`, so for an admin who had not approved yet, seats the approval
 * screen called approved read "not started" and the count read "0 of 3" (the
 * review of #1926). The set is keyed by seat id now.
 *
 * Rendered through OrgConsole rather than RegistrySignoff alone, because the
 * defect was in how the console built the set, not in the screen.
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { OrgConsole } from './OrgConsole'
import { DEMO_ORG, DEMO_REGISTRY } from './demoOrg'
import { orgApi, type Org, type OrgAccess } from './orgApi'

const SLUG = 'ramapo-trail-conference'
const ME = 'person-me'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

/** An invited admin who has not approved yet, as `/access` answers them. */
const NOT_YET_APPROVED: OrgAccess = {
  org_slug: SLUG,
  is_admin: false,
  is_codeowner: false,
  is_supervisor: false,
  is_volunteer: false,
  can_manage_volunteers: false,
  can_read_roster: false,
  can_touch_registry: false,
}

/** The org as the server answers that admin: two approved seats with their
 *  holders withheld, and their own seat, which shows its holder. */
const ORG: Org = {
  ...DEMO_ORG,
  slug: SLUG,
  admins: [
    {
      ...DEMO_ORG.admins[0],
      person_id: null,
      approved_at: '2026-03-01T09:12:00Z',
    },
    {
      ...DEMO_ORG.admins[1],
      person_id: null,
      approved_at: '2026-03-01T18:40:00Z',
    },
    {
      ...DEMO_ORG.admins[2],
      person_id: ME,
      approved_at: null,
    },
  ],
}

function openSignoff() {
  vi.spyOn(orgApi, 'read').mockResolvedValue(ORG)
  vi.spyOn(orgApi, 'access').mockResolvedValue(NOT_YET_APPROVED)
  vi.spyOn(orgApi, 'registry').mockResolvedValue(DEMO_REGISTRY)
  // The console lets each of its other reads fail on its own (`optional` in
  // OrgConsole.tsx), and the sign-off screen draws none of them.
  for (const read of ['roles', 'roster', 'workdays', 'coverage', 'challenges'] as const) {
    vi.spyOn(orgApi, read).mockRejectedValue(new Error('403'))
  }
  render(
    <OrgConsole
      routing={{
        route: { kind: 'setup', slug: SLUG, page: 'signoff' },
        go: vi.fn(),
        replace: vi.fn(),
      }}
      units="imperial"
    />,
  )
}

describe('the sign-off count, for an admin whose colleagues are withheld', () => {
  it('counts the two approved seats although neither holder is shown', async () => {
    openSignoff()

    expect(await screen.findByText(/sign-off · 2 of 3/)).toBeTruthy()
    expect(screen.queryByText(/sign-off · 0 of 3/)).toBeNull()
  })

  it('marks those two seats confirmed and the caller’s own not started', async () => {
    openSignoff()
    await screen.findByText(/sign-off · 2 of 3/)

    expect(screen.getAllByText('confirmed')).toHaveLength(2)
    expect(screen.getAllByText('not started')).toHaveLength(1)
  })
})
