import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { WorkdaySheet } from './WorkdaySheet'
import type { WorkProjectSummary } from '../lib/workProjects'

// The sheet behind a workday pin (#760). The pin was deliberately not shipped
// without this, because a dot nothing responds to is decoration - and this is
// decoration somebody might drive to a trailhead for.
//
// What these cases hold: nothing here signs anybody up or implies a place is
// held (VOLUNTEERING.md's "an introduction, never an enrolment"), no distance
// is invented for a workday nobody placed on the mile axis, and the sheet says
// out loud that a workday can be called off after it was written.

function aProject(over: Partial<WorkProjectSummary> = {}): WorkProjectSummary {
  return {
    id: 'wp-1',
    club_name: 'NY–NJ Trail Conference',
    title: 'Rock steps above the col',
    description: 'Crew day rebuilding the steps. Tools and lunch provided.',
    lat: 41.3,
    lon: -74.1,
    mile: 1400,
    starts_on: '2026-09-12',
    ends_on: '2026-09-13',
    status: 'upcoming',
    capacity: 8,
    signup_mode: 'contact',
    signup_contact: 'mailto:crew@example.org',
    ...over,
  }
}

afterEach(() => {
  cleanup()
})

describe('the workday sheet', () => {
  it('leads with what it is and when, in the tab’s own words', () => {
    render(<WorkdaySheet project={aProject()} gpsMile={null} onClose={vi.fn()} />)

    expect(
      screen.getByRole('heading', { name: /rock steps above the col/i }),
    ).toBeTruthy()
    // `workProjectDates` renders it, shared with the Volunteer tab: two
    // surfaces formatting the same day differently is a hiker reading two
    // claims where there is one.
    expect(screen.getByText('Sep 12–Sep 13')).toBeTruthy()
    expect(screen.getByText(/NY–NJ Trail Conference/)).toBeTruthy()
  })

  it('says how far away it is only when both miles are known', () => {
    const { unmount } = render(
      <WorkdaySheet
        project={aProject({ mile: 1400 })}
        gpsMile={1390}
        onClose={vi.fn()}
      />,
    )
    expect(screen.getByText(/10 trail mi away/)).toBeTruthy()
    unmount()

    // A row the reviewed file never placed on the axis gets no distance,
    // rather than one measured from a coordinate nobody surveyed against the
    // centerline.
    render(
      <WorkdaySheet
        project={aProject({ mile: null })}
        gpsMile={1390}
        onClose={vi.fn()}
      />,
    )
    expect(screen.queryByText(/trail mi away/)).toBeNull()
  })

  it('offers the club’s own channel, and calls it asking rather than joining', () => {
    render(<WorkdaySheet project={aProject()} gpsMile={null} onClose={vi.fn()} />)

    const link = screen.getByRole('link', { name: /ask the crew about joining/i })
    expect(link.getAttribute('href')).toBe('mailto:crew@example.org')
    // The failure VOLUNTEERING.md names: "the app must never leave someone
    // believing they are on a roster when they are not". Phase B has no
    // write path at all, so there is nothing here that could confirm a place.
    expect(screen.queryByRole('button', { name: /sign up|join|reserve/i })).toBeNull()
  })

  it('says a workday can be called off after this was written', () => {
    render(<WorkdaySheet project={aProject()} gpsMile={null} onClose={vi.fn()} />)

    // The sentence that makes an expiring invitation honest. The map's
    // staleness ceiling stops the pin being drawn at all past 48 hours; this
    // covers the hours before that, where the data is fresh and the workday
    // may still have been cancelled an hour ago.
    expect(screen.getByText(/check with them before travelling/i)).toBeTruthy()
  })

  it('omits the capacity line rather than printing a zero', () => {
    render(
      <WorkdaySheet
        project={aProject({ capacity: null })}
        gpsMile={null}
        onClose={vi.fn()}
      />,
    )

    // Null is "no cap stated", never zero - lib/workProjects.ts's own rule,
    // and "room for 0" would turn an open invitation into a closed one.
    expect(screen.queryByText(/room for/i)).toBeNull()
  })

  it('closes', async () => {
    const onClose = vi.fn()
    render(<WorkdaySheet project={aProject()} gpsMile={null} onClose={onClose} />)

    await userEvent.click(screen.getByRole('button', { name: /close/i }))

    expect(onClose).toHaveBeenCalled()
  })
})
