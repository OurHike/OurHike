import { describe, it, expect, vi, afterEach } from 'vitest'
import { act, render, screen, cleanup } from '@testing-library/react'
import { Downloads, type SheetDownload } from './Downloads'
import { rasterDetailOptions } from './DetailPicker'
import { ownPhotoUsage } from '../lib/poiPhotos'

// POI_PHOTOS.md's storage rule for a hiker's own photos is visibility, not a
// cap: "they should be visible in storage management for the same reason
// everything else is, not capped." The Downloads screen is that management,
// so the line renders there - measured, and only where there is something
// to measure, because "0 photos · 0 B" is a zero nobody asked about.

vi.mock('../lib/poiPhotos', () => ({ ownPhotoUsage: vi.fn() }))

const mockedUsage = vi.mocked(ownPhotoUsage)

function sheet(): SheetDownload {
  return {
    id: 'usgs-sheet',
    title: 'USGS sheet',
    summary: 'The official government topo, as an optional second map.',
    status: { state: 'not-downloaded' as const },
    sizeBytes: 314_000_000,
    detail: {
      options: rasterDetailOptions(),
      value: 'standard',
      onChange: vi.fn(),
      name: 'usgs-detail',
    },
    onStart: vi.fn(),
    onResume: vi.fn(),
    onDelete: vi.fn(),
  }
}

async function renderDownloads() {
  const view = render(<Downloads sheets={[sheet()]} />)
  await act(async () => {})
  return view
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('the own-photos storage line', () => {
  it('states the measured count and bytes when the hiker holds photos', async () => {
    mockedUsage.mockResolvedValue({ count: 12, bytes: 456_000 })
    await renderDownloads()

    expect(screen.getByTestId('downloads-own-photos')).toHaveTextContent(
      /Your waypoint photos: 12 photos · .+ on this phone/,
    )
  })

  it('says "one photo" rather than "1 photos"', async () => {
    mockedUsage.mockResolvedValue({ count: 1, bytes: 38_000 })
    await renderDownloads()

    expect(screen.getByTestId('downloads-own-photos')).toHaveTextContent(
      /Your waypoint photos: one photo ·/,
    )
  })

  it('renders no line at all for a phone with no photos', async () => {
    mockedUsage.mockResolvedValue({ count: 0, bytes: 0 })
    await renderDownloads()

    expect(screen.queryByTestId('downloads-own-photos')).not.toBeInTheDocument()
  })

  it('renders no line where the store cannot be read', async () => {
    mockedUsage.mockRejectedValue(new Error('no IndexedDB'))
    await renderDownloads()

    expect(screen.queryByTestId('downloads-own-photos')).not.toBeInTheDocument()
  })
})
