import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type ClaimDetail } from './api'
import {
  clearOffline,
  flushPhotos,
  isOffline,
  queuePhoto,
  queuedPhotos,
  saveClaim,
  savedClaim,
} from './offline'
import { fakeApi } from './test/fakeAccount'

afterEach(async () => {
  await clearOffline()
})

const jpeg = () => new Blob(['pixels'], { type: 'image/jpeg' })

it('a claim saved on the phone comes back as it was, with when it was saved', async () => {
  const claim = {
    id: 'claim-1',
    rims_id: 'example-0004',
    state: 'in_progress',
  } as ClaimDetail
  await saveClaim(claim)
  const kept = await savedClaim('claim-1')
  expect(kept?.claim).toEqual(claim)
  expect(Date.parse(kept!.savedAt)).not.toBeNaN()
  expect(await savedClaim('never-opened')).toBeNull()
})

it('isOffline tells no signal apart from the server saying no', () => {
  expect(isOffline(new TypeError('Failed to fetch'))).toBe(true)
  expect(isOffline(new ApiError(504, 'gateway'))).toBe(true)
  expect(isOffline(new ApiError(503, 'Photo storage is not set up'))).toBe(false)
  expect(isOffline(new ApiError(409, 'claim released'))).toBe(false)
})

describe('flushPhotos', () => {
  it('sends queued photos oldest first and forgets each one sent', async () => {
    const api = fakeApi()
    const [claim] = await api.claimSites(['example-0004'])
    await queuePhoto({ claimId: claim.id, phase: 'before', point: 1, photo: jpeg() })
    await queuePhoto({ claimId: claim.id, phase: 'after', point: 1, photo: jpeg() })
    const result = await flushPhotos(api)
    expect(result).toEqual({ sent: 2, refused: [], stopped: false })
    expect(api.calls.filter((c) => c.startsWith('photo'))).toEqual([
      'photo before 1 image/jpeg',
      'photo after 1 image/jpeg',
    ])
    expect(await queuedPhotos()).toEqual([])
  })

  it('stops when the signal goes and keeps the rest for next time', async () => {
    const api = {
      ...fakeApi(),
      uploadPhoto: vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))),
    }
    await queuePhoto({ claimId: 'c', phase: 'before', point: 1, photo: jpeg() })
    await queuePhoto({ claimId: 'c', phase: 'before', point: 2, photo: jpeg() })
    expect((await flushPhotos(api)).stopped).toBe(true)
    expect(api.uploadPhoto).toHaveBeenCalledTimes(1)
    expect(await queuedPhotos()).toHaveLength(2)
  })

  it('drops a photo the server refuses for good, says why, and carries on', async () => {
    const upload = vi
      .fn()
      .mockRejectedValueOnce(
        new ApiError(409, 'This claim is released, so that cannot be done now'),
      )
      .mockResolvedValueOnce({})
    const api = { ...fakeApi(), uploadPhoto: upload }
    await queuePhoto({ claimId: 'c', phase: 'before', point: 1, photo: jpeg() })
    await queuePhoto({ claimId: 'c', phase: 'after', point: 1, photo: jpeg() })
    const result = await flushPhotos(api)
    expect(result.sent).toBe(1)
    expect(result.refused.map((r) => r.reason)).toEqual([
      'This claim is released, so that cannot be done now',
    ])
    expect(await queuedPhotos()).toEqual([])
  })

  it('keeps everything while the API says sign in again', async () => {
    const api = {
      ...fakeApi(),
      uploadPhoto: vi.fn(async () => Promise.reject(new ApiError(401, 'Sign in first.'))),
    }
    await queuePhoto({ claimId: 'c', phase: 'before', point: 1, photo: jpeg() })
    expect((await flushPhotos(api)).stopped).toBe(true)
    expect(await queuedPhotos()).toHaveLength(1)
  })
})

it('clearOffline forgets saved claims and queued photos, for the next person on a shared phone', async () => {
  await saveClaim({ id: 'claim-1' } as ClaimDetail)
  await queuePhoto({ claimId: 'claim-1', phase: 'extra', point: null, photo: jpeg() })
  await clearOffline()
  expect(await savedClaim('claim-1')).toBeNull()
  expect(await queuedPhotos()).toEqual([])
})
