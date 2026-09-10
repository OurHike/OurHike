// Your photos and notes (#1373, D5): the summonable door to a hiker's own
// work, including a place that has left the map.

import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { YourWork, type YourWorkProps } from './YourWork'

const PROPS: YourWorkProps = {
  photos: [],
  notes: [],
  today: '2026-09-10',
  onOpenPlace: vi.fn(),
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the rows', () => {
  it('lists photos with their place, date and whether they were shared, and opens the place', async () => {
    const user = userEvent.setup()
    const onOpenPlace = vi.fn()
    render(
      <YourWork
        {...PROPS}
        onOpenPlace={onOpenPlace}
        photos={[
          {
            poiId: 'p1',
            id: 'a',
            kind: 'water',
            place: 'Spring at Murray property',
            date: '2026-09-04',
            shared: true,
            removed: false,
          },
          {
            poiId: 'p2',
            id: 'b',
            kind: 'shelter',
            place: 'Brink Road shelter',
            date: '2025-08-30',
            shared: false,
            removed: true,
          },
        ]}
      />,
    )

    const photos = screen.getByRole('region', { name: 'Photos' })
    expect(
      within(photos).getByText('photo · kept fri 4 sep · shared'),
    ).toBeInTheDocument()
    // A retired place keeps its photos and its row says where it went.
    expect(
      within(photos).getByText(
        'photo · kept sat 30 aug · private to this phone · a place no longer on the map',
      ),
    ).toBeInTheDocument()

    await user.click(within(photos).getByRole('button', { name: /Brink Road shelter/ }))
    expect(onOpenPlace).toHaveBeenCalledWith('p2')
  })

  it('lists the notes still waiting, and only those', () => {
    render(
      <YourWork
        {...PROPS}
        notes={[
          {
            id: 'n1',
            poiId: 'p1',
            kind: 'water',
            place: 'Spring at Murray property',
            observation: 'flowing',
            authoredAt: '2026-09-10T08:00:00.000Z',
          },
          {
            id: 'n2',
            poiId: null,
            kind: 'dot',
            place: 'mi 1,347.2',
            observation: null,
            authoredAt: '2026-09-09T08:00:00.000Z',
          },
        ]}
      />,
    )

    const notes = screen.getByRole('region', { name: 'Notes waiting to send' })
    expect(
      within(notes).getByText('note · Flowing · written today · waiting to send'),
    ).toBeInTheDocument()
    expect(
      within(notes).getByText('note · written yesterday · waiting to send'),
    ).toBeInTheDocument()
    // A note with no place is a fact, not a control.
    expect(within(notes).getAllByRole('button')).toHaveLength(1)
  })
})

describe('what it says about itself', () => {
  it('says why sent notes are absent, on every state', () => {
    render(<YourWork {...PROPS} />)
    expect(screen.getByText(/Nothing here yet/)).toBeInTheDocument()
    expect(screen.getByText(/Notes leave with the send/)).toBeInTheDocument()
  })

  it('counts nothing and scores nothing', () => {
    const { container } = render(
      <YourWork
        {...PROPS}
        photos={[
          {
            poiId: 'p1',
            id: 'a',
            kind: 'water',
            place: 'Spring',
            date: '2026-09-04',
            shared: true,
            removed: false,
          },
        ]}
      />,
    )
    expect(container.textContent).not.toMatch(/\d+ photos|%|streak|in a row/i)
  })
})
