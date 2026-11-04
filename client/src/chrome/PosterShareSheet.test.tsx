// The share sheet (#1965). The poster's drawing and rasterising are
// lib/challengePoster.ts's and are mocked here: jsdom has no canvas, and what
// this file holds is the sheet's own behaviour - which poster it opens on,
// that the map card says what it shows, and how the image leaves.

import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ATC_CHALLENGE } from '../lib/challenges.fixtures'
import { fixtureMap } from '../lib/challengeMap.fixtures'
import { stateAtMile } from '../lib/seasonStrip'
import { PosterShareSheet } from './PosterShareSheet'

const poster = vi.hoisted(() => ({
  drawn: [] as boolean[],
}))

vi.mock('../lib/challengePoster', () => ({
  posterFontCss: vi.fn(async () => ''),
  posterSvg: vi.fn((input: { map: unknown }) => {
    poster.drawn.push(input.map !== null)
    return '<svg/>'
  }),
  rasterise: vi.fn(async () => new Blob(['png'], { type: 'image/png' })),
}))

beforeEach(() => {
  poster.drawn = []
  let minted = 0
  URL.createObjectURL = vi.fn(() => `blob:poster-${(minted += 1)}`)
  URL.revokeObjectURL = vi.fn()
})

afterEach(() => cleanup())

function sheet(overrides: Partial<Parameters<typeof PosterShareSheet>[0]> = {}) {
  const props = {
    challenge: ATC_CHALLENGE,
    tags: [],
    today: '2027-07-14',
    stateOf: stateAtMile,
    walked: [],
    units: 'imperial' as const,
    map: fixtureMap(),
    onClose: vi.fn(),
    ...overrides,
  }
  render(<PosterShareSheet {...props} />)
  return props
}

describe('the share sheet (#1965)', () => {
  it('opens on the map poster when the phone holds the map, and the map card says what it shows', async () => {
    sheet()
    expect(screen.getByText('Making your poster…')).toBeInTheDocument()
    await screen.findByRole('img', { name: /the card, the map and the states/ })
    expect(poster.drawn).toEqual([true])
    expect(
      screen.getByRole('button', { name: /The map.*This shows where you’ve been/ }),
    ).toHaveAttribute('aria-pressed', 'true')
  })

  it('draws the states poster when the hiker picks it, and back', async () => {
    sheet()
    await screen.findByRole('img', { name: /the map/ })
    await userEvent.click(screen.getByRole('button', { name: /The states/ }))
    await screen.findByRole('img', { name: 'Your poster: the card and the states' })
    expect(poster.drawn).toEqual([true, false])
  })

  it('opens on the states poster with no map on the phone, and says why the map cannot be chosen', async () => {
    sheet({ map: null })
    await screen.findByRole('img', { name: 'Your poster: the card and the states' })
    expect(poster.drawn).toEqual([false])
    expect(
      screen.getByRole('button', { name: /The map.*No map on this phone yet/ }),
    ).toBeDisabled()
  })

  it('hands the PNG to the phone’s share sheet when it takes files, and offers to save it when it does not', async () => {
    const share = vi.fn(async () => {})
    sheet({ share, canShareFiles: () => true })
    await userEvent.click(await screen.findByRole('button', { name: 'Share' }))
    await waitFor(() => expect(share).toHaveBeenCalledTimes(1))
    const shared = (share.mock.calls[0] as unknown[])[0] as File
    expect(shared.type).toBe('image/png')
    expect(shared.name).toBe('atc-summer-bucket-list-2027-summer.png')
    cleanup()
    sheet({ canShareFiles: () => false })
    const save = await screen.findByRole('link', { name: 'Save the image' })
    expect(save).toHaveAttribute('download', 'atc-summer-bucket-list-2027-summer.png')
  })

  it('says it made the poster here and sends nothing until shared', () => {
    sheet()
    expect(
      screen.getByText('Made on this phone. Nothing is sent until you share it.'),
    ).toBeInTheDocument()
  })
})
