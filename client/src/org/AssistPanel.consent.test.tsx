/**
 * What the assist panel draws before an organization has opted in.
 *
 * **THE CLAIM UNDER TEST IS THAT NOTHING CAN BE SENT**, which is a claim
 * about what is on the screen rather than about what a handler does: with no
 * question box and no Ask button there is nothing to type into and nothing to
 * press, so no context reaches api.anthropic.com by any path through this
 * component. `POST /assist` answers 409 on its own
 * (`backend/app/routers/assist.py`) - the panel not offering the box is the
 * courtesy, the server is the gate, and this file tests the courtesy.
 *
 * `standingFor`'s own mapping, including the 409, is AssistPanel.test.ts.
 */

import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { AssistPanel } from './AssistPanel'

// Explicit, the way OrgShell.test.tsx does it: this project does not run
// Testing Library's auto-cleanup, so without it each render stacks on the
// last and a `queryByRole` finds the box a previous test drew.
afterEach(cleanup)

const SLUG = 'ramapo-trail-conference'

/** The coverage panel, which is one of the three screens that mount one. */
function draw(consented?: boolean) {
  render(
    <AssistPanel
      kind="coverage"
      slug={SLUG}
      title="Read the gaps with me"
      opening="It sees the same gap list you do."
      placeholder="Which of these has been open longest?"
      context="4 of 6 sections have no role attached."
      consented={consented}
    />,
  )
}

describe('AssistPanel with consented={false}', () => {
  it('draws no question box, so there is nothing to type a question into', () => {
    draw(false)

    expect(screen.queryByRole('textbox')).toBeNull()
  })

  it('draws no Ask button, so there is nothing to press to send the gap list', () => {
    draw(false)

    expect(screen.queryByRole('button', { name: 'Ask' })).toBeNull()
  })

  it('says the organization has not turned the assistant on, and names Settings', () => {
    draw(false)

    expect(
      screen.getByText('This organization has not turned the assistant on.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/an admin turns it on in Settings/)).toBeInTheDocument()
  })

  it('drops the "what goes over is what is on this screen" line, since nothing goes over', () => {
    // That line is a promise about a send. Leaving it under a panel that
    // cannot send would describe a transfer that is not happening.
    draw(false)

    expect(screen.queryByText(/What goes over is what is on this screen/)).toBeNull()
  })
})

describe('AssistPanel when the caller passes no `consented` at all', () => {
  it('still draws the question box, because the server and not this prop is the gate', () => {
    // Undefined means the caller did not say - a console that has not read
    // the org yet. Hiding the box on a missing prop would take the panel off
    // every screen that forgets to thread it.
    draw(undefined)

    expect(screen.getByRole('textbox')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ask' })).toBeInTheDocument()
  })
})

describe('AssistPanel with consented={true}', () => {
  it('draws the question box and the Ask button, as it did before consent existed', () => {
    draw(true)

    expect(screen.getByRole('textbox')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Ask' })).toBeInTheDocument()
  })

  it('draws no "has not turned the assistant on" notice over a panel that works', () => {
    draw(true)

    expect(
      screen.queryByText('This organization has not turned the assistant on.'),
    ).toBeNull()
  })
})
