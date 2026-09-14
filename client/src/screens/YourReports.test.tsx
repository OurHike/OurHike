// Your reports (#1373, frame 9d): two shelves from two sources, the status
// joined honestly, and the repository's four words rather than the frame's.

import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'

import { YourReports, type YourReportsProps } from './YourReports'
import { categoryLabel } from '../reporting/categories'

const PROPS: YourReportsProps = {
  waiting: [],
  sent: [],
  statusesRead: true,
  signedAs: null,
  today: '2026-09-10',
}

afterEach(cleanup)

describe('the two shelves', () => {
  it('lists what is waiting with when it was written, and says nothing is theirs to do', () => {
    render(
      <YourReports
        {...PROPS}
        waiting={[
          {
            id: 'w1',
            type: 'blowdown',
            place: 'Spring at Murray property',
            authoredAt: '2026-09-09T08:00:00.000Z',
          },
        ]}
      />,
    )

    const shelf = screen.getByRole('region', { name: 'Waiting to send' })
    expect(within(shelf).getByText('Waiting to send · 1')).toBeInTheDocument()
    // The tile's own label, read off the table rather than retyped.
    expect(
      within(shelf).getByText(
        `${categoryLabel('blowdown')} at Spring at Murray property`,
      ),
    ).toBeInTheDocument()
    expect(within(shelf).getByText('written yesterday')).toBeInTheDocument()
    expect(within(shelf).getByText(/nothing to do/)).toBeInTheDocument()
  })

  it('lists what was sent with the live list’s word beside it, in the reporter’s vocabulary', () => {
    render(
      <YourReports
        {...PROPS}
        sent={[
          {
            id: 's1',
            type: 'flooding',
            place: 'Stony Brook',
            sentAt: '2026-09-04T09:00:00.000Z',
            state: 'Confirmed',
          },
          {
            id: 's2',
            type: 'trash',
            place: 'Pine Meadow Shelter',
            sentAt: '2026-08-28T08:00:00.000Z',
            state: 'Not confirmed',
          },
        ]}
      />,
    )

    const shelf = screen.getByRole('region', { name: 'Sent from this phone' })
    expect(within(shelf).getByText('Sent from this phone · 2')).toBeInTheDocument()
    expect(within(shelf).getByText('sent 6 days ago · Confirmed')).toBeInTheDocument()
    expect(
      within(shelf).getByText('sent 13 days ago · Not confirmed'),
    ).toBeInTheDocument()
    // The moderator's words and any penalty stay off this screen.
    expect(shelf.textContent).not.toMatch(/verified|in review|rejected/i)
  })
})

describe('an absent status says which absence it is', () => {
  const sent = [
    {
      id: 's1',
      type: 'flooding' as const,
      place: 'Stony Brook',
      authoredAt: '2026-09-04T08:00:00.000Z',
      sentAt: '2026-09-04T09:00:00.000Z',
      state: null,
    },
  ]

  it('says the list has not been read when it has not', () => {
    render(<YourReports {...PROPS} sent={sent} statusesRead={false} />)
    expect(screen.getByText('sent 6 days ago')).toBeInTheDocument()
    expect(screen.getByText(/Statuses need signal/)).toBeInTheDocument()
  })

  it('says the list does not hold the row when it was read', () => {
    render(<YourReports {...PROPS} sent={sent} statusesRead />)
    expect(screen.getByText(/does not hold them/)).toBeInTheDocument()
    expect(screen.queryByText(/Statuses need signal/)).toBeNull()
  })
})

describe('the edges', () => {
  it('says so when nothing has been reported from this phone', () => {
    render(<YourReports {...PROPS} />)
    expect(screen.getByText(/Nothing reported from this phone yet/)).toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Waiting to send' })).toBeNull()
  })

  it('names the local signing and the one true thing about the wire', () => {
    render(
      <YourReports
        {...PROPS}
        signedAs={{ trailName: 'Switchback', reporterType: 'thru' }}
      />,
    )
    expect(
      screen.getByText(
        /Reported as Switchback, thru-hiker\. Your email is never on a report\./,
      ),
    ).toBeInTheDocument()
  })

  it('totals nothing across time and ranks nothing', () => {
    const { container } = render(<YourReports {...PROPS} />)
    expect(container.textContent).not.toMatch(/%|streak|behind|ahead of|rank/i)
  })
})
