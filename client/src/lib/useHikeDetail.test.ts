import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import 'fake-indexeddb/auto'
import { set } from 'idb-keyval'
import { conditionsCacheKey } from './conditionsCache'
import { SUGGESTED_HIKE_DETAIL_KEY } from './config'
import type { SuggestedHike } from './suggestedHikes'
import { useHikeDetail } from './useHikeDetail'

// #1473. The shelf stopped carrying every hike's turn-by-turn, because it had
// reached 1.70 MB of conditionsCache.ts's 2 MB ceiling - and that ceiling
// DELETES the copy a phone is holding rather than trimming it, so the publish
// that crossed it would have emptied the shelf offline on every phone at
// once, with no warning and no partial list.
//
// What matters in these is not that the prose arrives. It is that every way
// it can FAIL to arrive lands on a state the screen was already built for.

afterEach(() => {
  vi.unstubAllGlobals()
})

const HIKE = {
  id: 'nynjtc_hike_finder:42',
  name: 'Bearfort Ridge Loop',
  miles: 5.4,
  difficulty: 'moderate',
  author: { kind: 'club', name: 'NY-NJ Trail Conference' },
  segments: [],
  // What the shelf keeps carrying, and the reason it does: App.tsx draws the
  // line from the shelf record, so its provenance has to be there too.
  detail: { routeProvenance: 'generated', routeGrade: 'fair' },
} as unknown as SuggestedHike

describe('useHikeDetail', () => {
  it('never reaches the network with no signal', async () => {
    // The gate useSuggestedHikes, usePublishedSizes and useTrailData all
    // keep. A phone offline reaches the network ZERO times, not
    // once-and-fail: a request that cannot succeed is pure battery.
    const fetchSpy = vi.fn()
    vi.stubGlobal('fetch', fetchSpy)

    renderHook(() => useHikeDetail(HIKE, false))
    await new Promise((resolve) => setTimeout(resolve, 20))

    expect(fetchSpy).not.toHaveBeenCalled()
  })

  it('shows the shelf fields while the prose is still on its way', () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => new Promise(() => {})),
    )

    const { result } = renderHook(() => useHikeDetail(HIKE, true))

    // Not undefined, and not empty: the provenance is on the shelf precisely
    // so a line is never drawn without it.
    expect(result.current?.routeProvenance).toBe('generated')
    expect(result.current?.description).toBeUndefined()
  })

  it('keeps the shelf fields once the prose arrives, rather than replacing them', async () => {
    await set(conditionsCacheKey(SUGGESTED_HIKE_DETAIL_KEY('42')), {
      document: {
        id: 'nynjtc_hike_finder:42',
        description: ['Follow the white blazes north.'],
        url: 'https://example.test/hike/42',
      },
      storedAt: new Date().toISOString(),
    })

    const { result } = renderHook(() => useHikeDetail(HIKE, false))

    await waitFor(() =>
      expect(result.current?.description).toEqual(['Follow the white blazes north.']),
    )
    // The merge spreads the fetched object second, so this is the assertion
    // that the two sides carry nothing in common - the pipeline suite's
    // test_the_shelf_and_the_detail_share_no_field is the other half.
    expect(result.current?.routeProvenance).toBe('generated')
  })

  it('does not show one hike’s prose under another hike’s name', async () => {
    await set(conditionsCacheKey(SUGGESTED_HIKE_DETAIL_KEY('42')), {
      document: { id: 'nynjtc_hike_finder:42', description: ['The first walk.'] },
      storedAt: new Date().toISOString(),
    })

    const { result, rerender } = renderHook(
      ({ hike }: { hike: SuggestedHike }) => useHikeDetail(hike, false),
      { initialProps: { hike: HIKE } },
    )
    await waitFor(() => expect(result.current?.description).toEqual(['The first walk.']))

    // A hiker backing out and opening a different walk. Without the clear on
    // the way IN, the second screen reads the first one's prose for as long
    // as its own read takes - which offline is forever.
    const other = { ...HIKE, id: 'nynjtc_hike_finder:99', name: 'Somewhere else' }
    rerender({ hike: other as SuggestedHike })

    expect(result.current?.description).toBeUndefined()
  })

  it('treats a 404 on a hike it never opened as no prose to show', async () => {
    // The ordinary answer for a hike published before the split, or one whose
    // detail did not upload. The screen prints the figures and no prose,
    // which is the state every field in SuggestedHikeDetail was written for.
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: false, status: 404 } as Response)),
    )
    const never = { ...HIKE, id: 'nynjtc_hike_finder:404' } as SuggestedHike

    const { result } = renderHook(() => useHikeDetail(never, true))
    await new Promise((resolve) => setTimeout(resolve, 20))

    expect(result.current?.description).toBeUndefined()
    expect(result.current?.routeProvenance).toBe('generated')
  })

  it('lets a kept copy stand when the bucket stops carrying it', async () => {
    // A 404 is not evidence the prose was withdrawn - the same rule the shelf
    // keeps. A phone that has read this walk once goes on being able to read
    // it, which is the whole point of keeping anything.
    await set(conditionsCacheKey(SUGGESTED_HIKE_DETAIL_KEY('7')), {
      document: { id: 'nynjtc_hike_finder:7', description: ['Still here.'] },
      storedAt: new Date().toISOString(),
    })
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: false, status: 404 } as Response)),
    )
    const kept = { ...HIKE, id: 'nynjtc_hike_finder:7' } as SuggestedHike

    const { result } = renderHook(() => useHikeDetail(kept, true))
    await waitFor(() => expect(result.current?.description).toEqual(['Still here.']))

    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(result.current?.description).toEqual(['Still here.'])
  })
})
