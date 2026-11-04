import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ATC_CHALLENGE } from '../lib/challenges.fixtures'
import { EMPTY_CHALLENGE_STATE, join, tagsFor } from '../lib/challengeProgress'

// The own-photo store and the photo preparation, mocked: what this file
// holds is the tile sheet's half - the button, the chip, the add and the
// removal - not IndexedDB or the re-encoder, which their own suites hold.
const store = vi.hoisted(() => ({
  photos: [] as { id: string; url: string; taken: string; source: 'library' }[],
  add: vi.fn(async () => {}),
  remove: vi.fn(async () => {}),
}))
vi.mock('../lib/useOwnPhotos', () => ({
  useOwnPhotos: () => ({
    photos: store.photos,
    add: store.add,
    choose: vi.fn(),
    remove: store.remove,
    setShared: vi.fn(),
  }),
}))
vi.mock('../lib/reportPhoto', () => ({
  PhotoUnusable: class PhotoUnusable extends Error {},
  preparePhoto: vi.fn(async () => new Blob(['x'], { type: 'image/jpeg' })),
}))
vi.mock('../lib/exifDate', () => ({ exifCaptureDate: vi.fn(async () => '2027-07-14') }))

import { TileSheet } from './TileSheet'

afterEach(cleanup)
beforeEach(() => {
  store.photos = []
  store.add.mockClear()
  store.remove.mockClear()
})

const item = (id: string) => ATC_CHALLENGE.items.find((entry) => entry.id === id)!
const tags = tagsFor(
  join(EMPTY_CHALLENGE_STATE, ATC_CHALLENGE.id, new Date('2027-06-01T12:00:00Z')),
  ATC_CHALLENGE.id,
)

function sheet(id = 'mcafee-knob') {
  render(
    <TileSheet
      challenge={ATC_CHALLENGE}
      item={item(id)}
      number={13}
      today="2027-07-14"
      tags={tags}
      earnable
      onEarn={vi.fn()}
      onSetNote={vi.fn()}
      onClose={vi.fn()}
    />,
  )
}

describe('the tile’s own photo (maintainer, poll 2026-11-04)', () => {
  it('offers the hiker’s own photo for a place, and adds it to the place’s store on the phone', async () => {
    sheet()
    await userEvent.click(
      screen.getByRole('button', {
        name: /Use my own photo instead · stays on this phone/,
      }),
    )
    const input = screen.getByTestId('tile-sheet-library-input') as HTMLInputElement
    await userEvent.upload(input, new File(['bytes'], 'knob.jpg', { type: 'image/jpeg' }))
    await waitFor(() => expect(store.add).toHaveBeenCalledOnce())
    expect(store.add).toHaveBeenCalledWith(
      expect.objectContaining({ taken: '2027-07-14', source: 'library' }),
    )
  })

  it('shows the own photo first with its chip, and takes it back with one tap', async () => {
    store.photos = [{ id: 'p1', url: 'blob:own', taken: '2027-07-14', source: 'library' }]
    const { container } = { container: document.body }
    sheet()
    expect(screen.getByText('your photo')).toBeInTheDocument()
    expect(
      (container.querySelector('.challenge-sheet__photo') as HTMLElement).style
        .backgroundImage,
    ).toContain('blob:own')
    expect(screen.queryByRole('button', { name: /Use my own photo/ })).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Not this photo' }))
    expect(store.remove).toHaveBeenCalledWith('p1')
  })

  it('offers no photo for an item with no place - there is no waypoint to keep it against', () => {
    sheet('trivia-quiz')
    expect(screen.queryByRole('button', { name: /Use my own photo/ })).toBeNull()
  })
})
