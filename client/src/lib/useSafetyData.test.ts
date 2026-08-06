import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useSafetyData } from './useSafetyData'
import { fetchClosures, fetchReports, ApiError } from './api'

// The three properties the module header promises: a failed fetch keeps the
// last copy (never an empty list), the two endpoints fail independently, and
// the sync age is per-collection.

vi.mock('./api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('./api')>()),
  // A test build has no VITE_API_BASE_URL, so the real flag is false and the
  // hook would correctly do nothing at all - which is itself asserted below
  // against the real module. Everything else needs the configured path.
  API_CONFIGURED: true,
  fetchClosures: vi.fn(),
  fetchReports: vi.fn(),
}))

const mockedClosures = vi.mocked(fetchClosures)
const mockedReports = vi.mocked(fetchReports)

function aClosure(id: string) {
  return { id } as Awaited<ReturnType<typeof fetchClosures>>[number]
}

function aReport(id: string) {
  return { id } as Awaited<ReturnType<typeof fetchReports>>[number]
}

beforeEach(() => {
  mockedClosures.mockResolvedValue([])
  mockedReports.mockResolvedValue([])
})

afterEach(() => {
  vi.clearAllMocks()
})

describe('useSafetyData', () => {
  it('reads both lists once online', async () => {
    mockedClosures.mockResolvedValue([aClosure('c1')])
    mockedReports.mockResolvedValue([aReport('r1')])

    const { result } = renderHook(() => useSafetyData(true, null))

    await waitFor(() => {
      expect(result.current.closures).toHaveLength(1)
      expect(result.current.reports).toHaveLength(1)
    })
    expect(result.current.closuresSyncedAt).toBeInstanceOf(Date)
    expect(result.current.reportsSyncedAt).toBeInstanceOf(Date)
  })

  it('reads nothing offline - there is no request to make', () => {
    renderHook(() => useSafetyData(false, null))

    expect(mockedClosures).not.toHaveBeenCalled()
    expect(mockedReports).not.toHaveBeenCalled()
  })

  it('starts empty with a null sync age, which is "never loaded", not "nothing out there"', () => {
    const { result } = renderHook(() => useSafetyData(false, null))

    expect(result.current.closures).toEqual([])
    expect(result.current.closuresSyncedAt).toBe(null)
  })

  it('keeps the last copy when a re-read fails, and keeps its age honest', async () => {
    // An empty list and a failed fetch draw the same map and mean opposite
    // things on the ground. The copy survives; the untouched syncedAt is
    // what says how old it is.
    mockedClosures.mockResolvedValue([aClosure('c1')])
    const { result, rerender } = renderHook(
      ({ online, account }: { online: boolean; account: string | null }) =>
        useSafetyData(online, account),
      { initialProps: { online: true, account: null as string | null } },
    )
    await waitFor(() => expect(result.current.closures).toHaveLength(1))
    const firstSync = result.current.closuresSyncedAt

    mockedClosures.mockRejectedValue(new ApiError(500, 'GET /closures failed: 500'))
    await act(async () => {
      rerender({ online: true, account: 'hiker@example.org' })
    })

    expect(result.current.closures).toHaveLength(1)
    expect(result.current.closuresSyncedAt).toBe(firstSync)
  })

  it('lets closures land when the reports read fails - the two are independent', async () => {
    mockedClosures.mockResolvedValue([aClosure('c1')])
    mockedReports.mockRejectedValue(new ApiError(500, 'GET /reports failed: 500'))

    const { result } = renderHook(() => useSafetyData(true, null))

    await waitFor(() => expect(result.current.closures).toHaveLength(1))
    expect(result.current.reports).toEqual([])
    expect(result.current.reportsSyncedAt).toBe(null)
  })

  it('re-reads when who-is-asking changes, because the server answer does', async () => {
    // A signed-in reporter is handed their own unmoderated reports alongside
    // the public set; signing out has to drop them again.
    const { rerender } = renderHook(
      ({ account }: { account: string | null }) => useSafetyData(true, account),
      { initialProps: { account: null as string | null } },
    )
    await waitFor(() => expect(mockedReports).toHaveBeenCalledTimes(1))

    await act(async () => {
      rerender({ account: 'hiker@example.org' })
    })

    await waitFor(() => expect(mockedReports).toHaveBeenCalledTimes(2))
  })
})
