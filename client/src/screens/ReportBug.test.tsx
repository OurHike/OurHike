import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ReportBug } from './ReportBug'
import { readBuildInfo } from '../lib/buildInfo'

// #626. Two things this section has to do that no unit test of the URLs can
// see: keep a trail condition out of the issue tracker, and be honest that
// the GitHub links need signal in an app built for having none.
//
// #848 added the row that answers the second of those rather than only
// admitting it - the app-failure report, which is a screen and not a link
// precisely because the failure it is for happens where the links do not
// work. The tests for it are below, mixed in with the four they sit above.

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

  // #848. The row that is not a link, and the reason this section needed one.
  // Everything else here opens GitHub in a browser, which the note below the
  // options admits needs signal - and the app failing while somebody
  // navigates by it happens where there is none.
  it('offers the app failing on the trail as its own thing, above the four', () => {
    render(<ReportBug build={RELEASE} onReportFailure={() => {}} />)

    const row = screen.getByRole('button', { name: /broke while I was out there/i })
    expect(row).toHaveTextContent(/lost, out of water/i)
    expect(row).toHaveTextContent(/no signal/i)
    // The half a GitHub issue cannot carry.
    expect(row).toHaveTextContent(/get back to you/i)
  })

  it('opens it in the app rather than sending anybody to a browser', async () => {
    const user = userEvent.setup()
    const onReportFailure = vi.fn()
    render(<ReportBug build={RELEASE} onReportFailure={onReportFailure} />)

    await user.click(screen.getByRole('button', { name: /broke while I was out there/i }))

    expect(onReportFailure).toHaveBeenCalledTimes(1)
  })

  // Nothing rather than a dead control: a hiker should not be offered a way
  // to describe being lost that ends in nothing happening.
  it('draws no such row in a build that has not wired it up', () => {
    render(<ReportBug build={RELEASE} />)

    expect(
      screen.queryByRole('button', { name: /broke while I was out there/i }),
    ).not.toBeInTheDocument()
  })

  it('no longer claims every option here needs signal, because one does not', () => {
    render(<ReportBug build={RELEASE} onReportFailure={() => {}} />)

    const note = screen.getByText(/need signal/i)
    expect(note).toHaveTextContent(/four above/i)
    expect(note).toHaveTextContent(/works without any/i)
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
    // With the app-failure row present, so this asserts about the LINKS
    // rather than passing because the button is the only other control.
    render(<ReportBug build={RELEASE} onReportFailure={() => {}} />)

    for (const link of screen.getAllByRole('link')) {
      expect(link).toHaveAttribute('target', '_blank')
      expect(link).toHaveAttribute('rel', 'noreferrer')
    }
  })
})
