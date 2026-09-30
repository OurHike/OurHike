/**
 * A workday's signup link may not become an `href` the phone would act on.
 *
 * WHY THIS TEST EXISTS. `lib/safeLink.ts` states the rule and the reason
 * ("a check that only exists at the far end is one a future second producer
 * walks straight past"), and `chrome/CrewContactLink.tsx` is that rule
 * applied to the pipeline's `signup_contact`. The org console is a SECOND
 * consumer of the same two fields and was built without either - it read
 * `signup_url ?? signup_contact` and put the result straight in an `href`.
 *
 * The backend now refuses the scheme at `schemas/work_project.py`, which is
 * the producer gate. This file is the sink half, and it is not redundant:
 * the site fetcher writes mirrored workdays too, and a row already in the
 * database predates the validator that would have refused it.
 *
 * WHAT AN UNCHECKED SCHEME DOES is measured in `lib/safeLink.ts` and not
 * re-derived here: React rewrites `javascript:` to a throwing stub, and
 * `data:`, `intent:`, `vbscript:` and `file:` reach the anchor unchanged -
 * so the allowlist is the whole defence for four of those five.
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { WorkdaysWidget } from './components'
import { DEMO_WORKDAYS } from './demoOrg'
import type { Workday } from './orgApi'

afterEach(cleanup)

function mirroredWorkday(overrides: Partial<Workday>): Workday {
  const mirrored = DEMO_WORKDAYS.find((workday) => workday.source === 'mirrored')
  if (mirrored === undefined) throw new Error('the demo set has no mirrored workday')
  return { ...mirrored, ...overrides }
}

/** Every anchor the widget drew, by its `href` attribute as written. */
function renderedHrefs(): (string | null)[] {
  return screen.queryAllByRole('link').map((anchor) => anchor.getAttribute('href'))
}

describe('a mirrored workday sent to the organization’s own form', () => {
  it('links a plain https signup URL', () => {
    render(
      <WorkdaysWidget
        workdays={[
          mirroredWorkday({ signup_url: 'https://cpthroughikers.example/volunteer' }),
        ]}
      />,
    )

    expect(renderedHrefs()).toContain('https://cpthroughikers.example/volunteer')
  })

  it('draws no link at all for a javascript: signup URL', () => {
    render(
      <WorkdaysWidget
        workdays={[mirroredWorkday({ signup_url: 'javascript:alert(document.cookie)' })]}
      />,
    )

    expect(renderedHrefs()).toEqual([])
  })

  it('draws no link at all for a data: signup URL, which React does not block', () => {
    render(
      <WorkdaysWidget
        workdays={[
          mirroredWorkday({ signup_url: 'data:text/html,<script>alert(1)</script>' }),
        ]}
      />,
    )

    expect(renderedHrefs()).toEqual([])
  })

  it('links an email contact when there is no signup URL, because that is what a contact is', () => {
    render(
      <WorkdaysWidget
        workdays={[
          mirroredWorkday({
            signup_url: null,
            signup_contact: 'mailto:trails@example.org',
          }),
        ]}
      />,
    )

    expect(renderedHrefs()).toContain('mailto:trails@example.org')
  })

  it('draws no link for a contact carrying a scheme the phone would hand to an app', () => {
    render(
      <WorkdaysWidget
        workdays={[
          mirroredWorkday({
            signup_url: null,
            signup_contact: 'intent://evil#Intent;end',
          }),
        ]}
      />,
    )

    expect(renderedHrefs()).toEqual([])
  })

  it('still says where to go when the link is refused, rather than silently offering nothing', () => {
    render(
      <WorkdaysWidget
        workdays={[mirroredWorkday({ signup_url: 'javascript:alert(1)' })]}
      />,
    )

    expect(screen.getByText(/ask them directly/i)).toBeTruthy()
  })
})
