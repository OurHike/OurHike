import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import { ReportBug } from './ReportBug'
import { readBuildInfo } from '../lib/buildInfo'

// #626. Two things this section has to do that no unit test of the URLs can
// see: keep a trail condition out of the issue tracker, and be honest that
// every one of these links needs signal in an app built for having none.

const RELEASE = readBuildInfo({
  version: '1.0.0',
  commit: '6e23f122d35c327abf6eec8ca48158e336362cc9',
  builtAt: '2026-08-07T23:51:31.603Z',
})

afterEach(cleanup)

describe('ReportBug', () => {
  it('offers the common kinds of bug rather than one link into the tracker', () => {
    render(<ReportBug build={RELEASE} />)

    expect(screen.getByRole('link', { name: /the app itself/i })).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /something on the map is wrong/i }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('link', { name: /reports, syncing or signing in/i }),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /something else/i })).toBeInTheDocument()
  })

  // The whole point of the section: the hiker never types the commit.
  it('carries this build into the report, without anybody copying it', () => {
    render(<ReportBug build={RELEASE} />)

    const href = screen
      .getByRole('link', { name: /the app itself/i })
      .getAttribute('href')

    expect(new URL(href!).searchParams.get('conditions')).toContain(
      '6e23f122d35c327abf6eec8ca48158e336362cc9',
    )
  })

  // A section called "Report a bug" sits one word from "Report a problem",
  // which is the flow a blowdown goes through and the one a moderator reads.
  // This is the sentence that keeps the two apart.
  it('sends a trail condition to the flow that reaches a moderator', () => {
    render(<ReportBug build={RELEASE} />)

    const steer = screen.getByText(/is not a bug/i)
    expect(steer).toHaveTextContent(/blowdown/i)
    expect(steer).toHaveTextContent(/Report a problem/i)
    expect(steer).toHaveTextContent(/moderator/i)
  })

  it('says plainly that these need signal, in an app built for having none', () => {
    render(<ReportBug build={RELEASE} />)

    expect(screen.getByText(/need signal/i)).toBeInTheDocument()
  })

  it('invites whoever writes code to the repository', () => {
    render(<ReportBug build={RELEASE} />)

    const invitation = screen.getByText(/open source/i)
    expect(
      within(invitation).getByRole('link', { name: /how the project works/i }),
    ).toHaveAttribute('href', expect.stringContaining('CONTRIBUTING.md'))
    expect(
      within(invitation).getByRole('link', { name: /somewhere to start/i }),
    ).toHaveAttribute('href', expect.stringContaining('good%20first%20issue'))
  })

  // Every link here leaves the app. Opening one in the same tab would take a
  // hiker out of a map they may be mid-navigation on, and an installed PWA
  // does not always give them a back button to return with.
  it('opens every link away from the app, and without handing it a window', () => {
    render(<ReportBug build={RELEASE} />)

    for (const link of screen.getAllByRole('link')) {
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', 'noreferrer')
    }
  })
})
