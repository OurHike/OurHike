/**
 * What the sign-off screen says happens next, against what now does.
 *
 * WHY THIS TEST EXISTS. Three console screens described a pull request that
 * no code in this repository opened - the same class of defect as the
 * coverage badge, and the one `sign_off_registry`'s own docstring had
 * already admitted to. The backend now opens one on the third signature and
 * records it on the organization, so the screen can stop describing the
 * mechanism and start pointing at the thing.
 *
 * The two states are both worth pinning. With a pull request open, the
 * screen links it and says the codeowners approve it there with their own
 * GitHub accounts - which is the whole arrangement. Without one - every
 * deployment until a service identity's token is issued - it must not
 * imply there is something waiting for them.
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { RegistrySignoff } from './RegistrySignoff'
import { DEMO_ORG, DEMO_REGISTRY } from '../demoOrg'
import type { Org } from '../orgApi'

afterEach(cleanup)

function draw(org: Org) {
  render(
    <RegistrySignoff
      org={org}
      registry={DEMO_REGISTRY}
      confirmed={new Set<string>()}
      personId={null}
      approvalsRequired={3}
      onConfirm={() => {}}
      onFlag={() => {}}
      units="imperial"
    />,
  )
}

describe('when a pull request is open for this registry', () => {
  const open: Org = {
    ...DEMO_ORG,
    registry_pr_url: 'https://github.com/OurHike/OurHike/pull/42',
  }

  it('links it rather than only describing it', () => {
    draw(open)

    const link = screen
      .queryAllByRole('link')
      .find((anchor) => anchor.getAttribute('href') === open.registry_pr_url)

    expect(link).toBeTruthy()
  })

  it('says the codeowners approve it there, with their own accounts', () => {
    draw(open)

    expect(screen.getByText(/your own GitHub account/i)).toBeTruthy()
  })
})

describe('when there is none', () => {
  it('does not link anything', () => {
    draw({ ...DEMO_ORG, registry_pr_url: null })

    const links = screen
      .queryAllByRole('link')
      .map((anchor) => anchor.getAttribute('href'))

    expect(links.some((href) => href?.includes('/pull/'))).toBe(false)
  })

  it('does not imply something is already waiting for the codeowners', () => {
    /* The failure this whole thread corrected: a screen describing a pull
       request nobody opened. Absent has to read as absent. */
    draw({ ...DEMO_ORG, registry_pr_url: null })

    expect(screen.queryByText(/approve it on GitHub now/i)).toBeNull()
  })
})
