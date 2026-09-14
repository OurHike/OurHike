import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  clearOpenWalk,
  leftOpenBefore,
  loadOpenWalk,
  noteOpenWalk,
  OPEN_WALK_KEY,
} from './openWalk'

// The walk left open (#1373, frame 6d): the smallest record that lets the
// next morning ask, never more than which walk and which day.

const store = new Map<string, unknown>()
vi.mock('idb-keyval', () => ({
  get: vi.fn(async (key: string) => store.get(key)),
  set: vi.fn(async (key: string, value: unknown) => {
    store.set(key, value)
  }),
  del: vi.fn(async (key: string) => {
    store.delete(key)
  }),
}))

beforeEach(() => {
  store.clear()
  vi.clearAllMocks()
})

describe('the walk left open', () => {
  it('remembers which walk and which day, and nothing else', async () => {
    await noteOpenWalk('walk-1', '2026-09-12')
    expect(store.get(OPEN_WALK_KEY)).toEqual({ hikeId: 'walk-1', day: '2026-09-12' })
    expect(await loadOpenWalk()).toEqual({ hikeId: 'walk-1', day: '2026-09-12' })
  })

  it('writes once per day, not per fix', async () => {
    const { set } = await import('idb-keyval')
    await noteOpenWalk('walk-1', '2026-09-12')
    await noteOpenWalk('walk-1', '2026-09-12')
    expect(set).toHaveBeenCalledTimes(1)
  })

  it('reads anything it does not recognise as none - the ask that does not fire', async () => {
    store.set(OPEN_WALK_KEY, 'walk-1')
    expect(await loadOpenWalk()).toBeNull()
    store.set(OPEN_WALK_KEY, { hikeId: 'walk-1', day: 'yesterday' })
    expect(await loadOpenWalk()).toBeNull()
  })

  it('forgets on request', async () => {
    await noteOpenWalk('walk-1', '2026-09-12')
    await clearOpenWalk()
    expect(await loadOpenWalk()).toBeNull()
  })

  it('is yesterday’s only once the day has turned', () => {
    const open = { hikeId: 'walk-1', day: '2026-09-12' }
    expect(leftOpenBefore(open, '2026-09-12')).toBeNull()
    expect(leftOpenBefore(open, '2026-09-13')).toEqual(open)
    expect(leftOpenBefore(null, '2026-09-13')).toBeNull()
  })
})
