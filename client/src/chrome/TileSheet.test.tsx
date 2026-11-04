import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TileSheet } from './TileSheet'
import { ATC_CHALLENGE } from '../lib/challenges.fixtures'
import { EMPTY_CHALLENGE_STATE, join, tag, tagsFor } from '../lib/challengeProgress'
import type { OwnCardPhoto } from '../lib/useOwnPhotos'

// The own-photo store is IndexedDB behind lib/useOwnPhotos.ts; a case that
// needs a photo, or a store that refuses, sets it here.
const own = vi.hoisted(() => ({
  photos: [] as OwnCardPhoto[],
  add: vi.fn(async () => {}),
  remove: vi.fn(async () => {}),
}))
// jsdom has no canvas to re-encode with; the re-encode is lib/reportPhoto.ts's
// own suite. Here it succeeds, so a failure after it is the store's.
vi.mock('../lib/reportPhoto', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../lib/reportPhoto')>()),
  preparePhoto: vi.fn(async () => new Blob(['jpeg'], { type: 'image/jpeg' })),
}))
vi.mock('../lib/exifDate', () => ({ exifCaptureDate: vi.fn(async () => null) }))
vi.mock('../lib/useOwnPhotos', () => ({
  useOwnPhotos: () => ({
    photos: own.photos,
    add: own.add,
    remove: own.remove,
    choose: vi.fn(async () => {}),
    setShared: vi.fn(async () => {}),
  }),
}))

afterEach(() => {
  cleanup()
  own.photos = []
  own.add = vi.fn(async () => {})
  own.remove = vi.fn(async () => {})
})

const TODAY = '2027-07-14'
const item = (id: string) => ATC_CHALLENGE.items.find((entry) => entry.id === id)!

function earned(ids: string[], how: 'gps' | 'hand' = 'hand', poi?: string) {
  let state = join(
    EMPTY_CHALLENGE_STATE,
    ATC_CHALLENGE.id,
    new Date('2027-06-01T12:00:00Z'),
  )
  for (const id of ids)
    state = tag(state, ATC_CHALLENGE, item(id), {
      at: new Date('2027-07-02T15:00:00Z'),
      how,
      poi,
      place: how === 'hand' ? { kind: 'state', state: 'VA' } : undefined,
    }).state
  return tagsFor(state, ATC_CHALLENGE.id)
}

function sheet(overrides: Partial<Parameters<typeof TileSheet>[0]> = {}) {
  const props = {
    challenge: ATC_CHALLENGE,
    item: item('mcafee-knob'),
    number: 7,
    today: TODAY,
    tags: earned([]),
    earnable: true,
    onEarn: vi.fn(),
    onTakeBack: vi.fn(),
    onSetNote: vi.fn(),
    onClose: vi.fn(),
    ...overrides,
  }
  render(<TileSheet {...props} />)
  return props
}

describe('a tile, opened (#1963)', () => {
  it('leads with the glyph when there is no photo, names the item, its number and its place', () => {
    const { container } = { container: document.body }
    sheet()
    expect(container.querySelector('.blaze-tile')).not.toBeNull()
    expect(
      screen.getByRole('heading', { name: /Take the McAfee Knob shuttle/ }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Experience · 7 of/)).toBeInTheDocument()
    expect(screen.getByText(/McAfee Knob Summit · mi 714\.9/)).toBeInTheDocument()
  })

  it('earns with one tap and never toggles: an earned tile offers Take it back instead', async () => {
    const props = sheet()
    await userEvent.click(screen.getByRole('button', { name: 'Earn some karma' }))
    expect(props.onEarn).toHaveBeenCalledOnce()
    cleanup()
    const done = sheet({ tags: earned(['mcafee-knob']) })
    expect(screen.queryByRole('button', { name: 'Earn some karma' })).toBeNull()
    expect(screen.getByRole('status')).toHaveTextContent('Earned · Jul 2')
    await userEvent.click(screen.getByRole('button', { name: 'Take it back' }))
    expect(done.onTakeBack).toHaveBeenCalledWith(undefined)
  })

  it('says where it happened, from the phone’s own record', () => {
    sheet({ item: item('white-blaze-photo'), tags: earned(['white-blaze-photo']) })
    expect(screen.getByText(/On the trail in Virginia/)).toBeInTheDocument()
  })

  it('says "Near you" only from what the phone knows: today’s walk, or the fix, never a guess', () => {
    sheet({ todayRanges: [{ startMile: 710, endMile: 716 }] })
    expect(screen.getByText('You passed it today.')).toBeInTheDocument()
    cleanup()
    sheet({ fixMile: 711.7 })
    expect(screen.getByText('3.2 mi along the trail from you.')).toBeInTheDocument()
    cleanup()
    sheet()
    expect(screen.queryByText(/Near you/)).toBeNull()
  })

  it('says how far "Near you" is in the hiker’s own units, not always in miles', () => {
    // McAfee Knob Summit is mile 714.92 in the fixture; a fix at 711.7 is
    // 3.22 miles back, 5.18 km. unitDisplay.test.ts caught this line spelling
    // "mi" itself, which a hiker on kilometres would have read as miles.
    sheet({ fixMile: 711.7, units: 'metric' })
    expect(screen.getByText('5.2 km along the trail from you.')).toBeInTheDocument()
  })

  it('tells an on-trail at-home item that earning it asks where, and a couch item nothing', () => {
    sheet({ item: item('white-blaze-photo') })
    expect(screen.getByText(/asks where it happened/)).toBeInTheDocument()
    cleanup()
    sheet({ item: item('trivia-quiz') })
    expect(screen.queryByText(/asks where it happened/)).toBeNull()
  })

  it('keeps the register line on the phone and gives it back on close', async () => {
    const props = sheet({ tags: earned(['mcafee-knob']) })
    await userEvent.type(
      screen.getByRole('textbox', { name: /register/ }),
      'cold morning',
    )
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(props.onSetNote).toHaveBeenLastCalledWith('cold morning')
    expect(props.onClose).toHaveBeenCalled()
  })

  it('never renders a sealed mystery title', () => {
    sheet({ item: item('mystery-1'), today: '2027-07-19', earnable: false })
    expect(document.body.textContent).not.toMatch(/Jefferson Rock/)
    expect(
      screen.getByRole('heading', { name: 'Sealed until Jul 20' }),
    ).toBeInTheDocument()
  })

  it('offers no Earn button on a sealed mystery item, whatever the caller says', () => {
    // ChallengeDetail decides `earnable`; this holds that the tile itself
    // never offers what the page refused (review of #2015).
    sheet({ item: item('mystery-1'), today: '2027-07-19', earnable: false })
    expect(screen.queryByRole('button', { name: /Earn/ })).toBeNull()
  })
})

describe('what the review of #2015 found in the tile sheet', () => {
  it.each(['summit-4000', 'trail-crew'])(
    'offers no Take it back on %s, which earns itself and would only be earned again',
    (id) => {
      sheet({ item: item(id), tags: earned([id], 'gps') })
      expect(screen.getByRole('status')).toHaveTextContent('Earned · Jul 2')
      expect(screen.queryByRole('button', { name: 'Take it back' })).toBeNull()
    },
  )

  it('still offers Take it back on a place a walk earned, which nothing earns again unasked', () => {
    sheet({ tags: earned(['mcafee-knob'], 'gps') })
    expect(screen.getByRole('button', { name: 'Take it back' })).toBeInTheDocument()
  })

  it('says nothing "Near you" about a place off the trail, whose mile is only where the trail passes nearest', () => {
    sheet({
      item: item('monson-visitor-center'),
      todayRanges: [{ startMile: 2070, endMile: 2090 }],
      fixMile: 2080,
    })
    expect(screen.queryByText(/Near you/)).toBeNull()
    expect(screen.queryByText(/passed it today|along the trail from you/)).toBeNull()
  })

  it('shows a Triple Crown’s first peak not yet earned, not always its last', () => {
    sheet({
      item: item('virginia-triple-crown'),
      tags: earned(
        ['virginia-triple-crown'],
        'hand',
        'atc_viewpoints:3cadebda-9d7d-4373-88f6-b240420eb958',
      ),
    })
    expect(screen.getByText(/McAfee Knob Summit · mi 714\.9/)).toBeInTheDocument()
  })

  it('moves focus to Take it back when the item is earned in place, not to the page', async () => {
    const props = {
      challenge: ATC_CHALLENGE,
      item: item('mcafee-knob'),
      number: 7,
      today: TODAY,
      earnable: true,
      onEarn: vi.fn(),
      onTakeBack: vi.fn(),
      onSetNote: vi.fn(),
      onClose: vi.fn(),
    }
    const { rerender } = render(<TileSheet {...props} tags={earned([])} />)
    screen.getByRole('button', { name: 'Earn some karma' }).focus()
    rerender(<TileSheet {...props} tags={earned(['mcafee-knob'])} />)
    expect(screen.getByRole('button', { name: 'Take it back' })).toHaveFocus()
  })

  it('removes the hiker’s own photo only on a second tap, and says so when the phone cannot', async () => {
    own.photos = [
      {
        id: 'photo-1',
        url: 'blob:own-1',
        taken: '2027-07-02',
        source: 'camera',
        blob: new Blob(['x']),
        takenClaim: null,
      },
    ]
    own.remove = vi.fn(async () => {
      throw new Error('quota')
    })
    sheet()
    expect(screen.getByText('your photo')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Not this photo' }))
    expect(own.remove).not.toHaveBeenCalled()
    await userEvent.click(
      screen.getByRole('button', { name: /Tap again to remove it · the waypoint card/ }),
    )
    expect(own.remove).toHaveBeenCalledWith('photo-1')
    expect(
      await screen.findByText('This phone could not remove the photo.'),
    ).toBeInTheDocument()
  })

  it('names storage, not the photo, when the phone refuses to keep a prepared photo', async () => {
    own.add = vi.fn(async () => {
      throw new Error('quota')
    })
    sheet()
    const input = screen.getByTestId('tile-sheet-library-input') as HTMLInputElement
    const file = new File([new Uint8Array([0xff, 0xd8, 0xff])], 'blaze.jpg', {
      type: 'image/jpeg',
    })
    await userEvent.upload(input, file)
    expect(
      await screen.findByText(
        'This phone could not store the photo, so nothing was kept.',
      ),
    ).toBeInTheDocument()
    expect(own.add).toHaveBeenCalledOnce()
    expect(screen.queryByText(/could not be prepared/)).toBeNull()
  })

  it('links to workdays under the club’s note on an item with a place', async () => {
    const onOpenWorkdays = vi.fn()
    sheet({
      item: { ...item('mcafee-knob'), note: 'Park at the Route 311 lot.', noteBy: null },
      onOpenWorkdays,
    })
    await userEvent.click(
      screen.getByRole('button', { name: 'Workdays on this section' }),
    )
    expect(onOpenWorkdays).toHaveBeenCalledOnce()
  })

  it('hands the Earn button to the caller, so focus can come back to it from the Where sheet', async () => {
    const props = sheet({ item: item('white-blaze-photo') })
    const earn = screen.getByRole('button', { name: 'Earn some karma' })
    await userEvent.click(earn)
    expect(props.onEarn).toHaveBeenCalledWith(earn)
  })
})
