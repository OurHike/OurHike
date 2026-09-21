/**
 * A registration nobody at the organization has confirmed must not read as
 * verified anywhere on the console.
 *
 * WHY THIS TEST EXISTS. `OrgState.pending` was added because an address the
 * registrant TYPED for a colleague is a claim about that person, not
 * evidence about the registrant - so a registration resting on one is held,
 * and `verified_by` stays null until somebody who actually holds an address
 * at the domain approves a seat.
 *
 * The setup hub's first stage did not have a branch for that. It read
 * `verified_by === 'dns' ? 'a DNS record' : 'an email at the domain'`, so a
 * null - a verification nobody performed - rendered as "verified by an email
 * at the domain". CLAUDE.md's rule is the one this breaks: a display may
 * never outrun its source, and "provenance that stops at the last Python
 * file is provenance nobody has."
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { SetupHub } from './SetupHub'
import { DEMO_ORG } from '../demoOrg'
import type { Org } from '../orgApi'

afterEach(cleanup)

const held: Org = { ...DEMO_ORG, state: 'pending', verified_by: null }

function draw(org: Org) {
  render(
    <SetupHub
      org={org}
      onboarded={false}
      registry={[]}
      proposals={[]}
      releases={[]}
      roleCount={0}
      coverageGaps={0}
      regions={[]}
      onOpen={() => {}}
      onOpenEmbeds={() => {}}
      onOpenSettings={() => {}}
      stageProgress={{ done: 0, total: 6 }}
    />,
  )
}

describe('a held registration on the setup hub', () => {
  it('never says the domain was verified', () => {
    draw(held)

    expect(screen.queryByText(/verified by an email at the domain/i)).toBeNull()
    expect(screen.queryByText(/verified by a DNS record/i)).toBeNull()
  })

  it('says what it is waiting for, naming the domain', () => {
    draw(held)

    expect(
      screen.getByText(/nobody at cpthroughikers\.example has confirmed/i),
    ).toBeTruthy()
  })

  it('still says verified when somebody actually was', () => {
    // The guard must not swallow the true case: an org whose registrant held
    // the domain is verified, and the hub has always said so.
    draw({ ...DEMO_ORG, state: 'claimed', verified_by: 'email' })

    expect(screen.getByText(/verified by an email at the domain/i)).toBeTruthy()
  })
})
