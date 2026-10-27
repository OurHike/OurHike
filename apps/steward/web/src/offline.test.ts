import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, type ClaimDetail, type StewardApi } from './api'
import {
  clearOffline,
  discardPhoto,
  dropWaiting,
  flushPhotos,
  isOffline,
  newPhotoId,
  queuePhoto,
  queuedPhotos,
  refusedPhotos,
  retryPhoto,
  saveClaim,
  savedClaim,
  waitingPhotos,
} from './offline'
import { fakeApi } from './test/fakeAccount'

const ME = 'user-1'
const NEXT_PERSON = 'user-2'

afterEach(async () => {
  await clearOffline(ME)
  await clearOffline(NEXT_PERSON)
})

const jpeg = () => new Blob(['pixels'], { type: 'image/jpeg' })
const crewClaim = (id: string) =>
  ({
    id,
    rims_id: 'example-0004',
    state: 'in_progress',
    crew: [{ name: null, you: true, hours: null }],
  }) as unknown as ClaimDetail

function uploads(responses: (() => Promise<unknown>)[]): StewardApi {
  const upload = vi.fn()
  for (const respond of responses) upload.mockImplementationOnce(respond)
  return { ...fakeApi(), uploadPhoto: upload }
}

describe('saved claims', () => {
  it('a claim the account is crew on comes back as it was, with when it was saved', async () => {
    await saveClaim(ME, crewClaim('claim-1'))
    const kept = await savedClaim(ME, 'claim-1')
    expect(kept?.claim).toEqual(crewClaim('claim-1'))
    expect(Date.parse(kept!.savedAt)).not.toBeNaN()
    expect(await savedClaim(ME, 'never-opened')).toBeNull()
  })

  it('a claim seen as a reviewer is not kept, nor shown to the next account', async () => {
    // The third pass's P6 and P3: other people's names and notes have no use
    // on the trail, and a phone's next account should not read the last one's.
    await saveClaim(ME, {
      ...crewClaim('theirs'),
      crew: [{ name: 'A', you: false, hours: null }],
    })
    expect(await savedClaim(ME, 'theirs')).toBeNull()
    await saveClaim(ME, crewClaim('mine'))
    expect(await savedClaim(NEXT_PERSON, 'mine')).toBeNull()
  })
})

it('isOffline tells no signal apart from the server saying no', () => {
  expect(isOffline(new TypeError('Failed to fetch'))).toBe(true)
  expect(isOffline(new ApiError(504, 'gateway'))).toBe(true)
  expect(isOffline(new ApiError(503, 'Photo storage is not set up'))).toBe(false)
  expect(isOffline(new ApiError(409, 'claim released'))).toBe(false)
})

describe('flushPhotos', () => {
  it('sends waiting photos oldest first, each under its queue id, and forgets each one sent', async () => {
    const api = fakeApi()
    const [claim] = await api.claimSites(['example-0004'])
    const first = await queuePhoto({
      userId: ME,
      claimId: claim.id,
      phase: 'before',
      point: 1,
      photo: jpeg(),
    })
    await queuePhoto({
      userId: ME,
      claimId: claim.id,
      phase: 'after',
      point: 1,
      photo: jpeg(),
    })
    const upload = vi.spyOn(api, 'uploadPhoto')
    const result = await flushPhotos(api, ME)
    expect(result).toEqual({ sent: 2, refused: [], stopped: false })
    expect(api.calls.filter((c) => c.startsWith('photo'))).toEqual([
      'photo before 1 image/jpeg',
      'photo after 1 image/jpeg',
    ])
    expect(upload.mock.calls[0][4]?.clientId).toBe(first.id)
    expect(await queuedPhotos(ME)).toEqual([])
  })

  it('stops when the signal goes and keeps the rest for next time', async () => {
    const api = uploads([async () => Promise.reject(new TypeError('Failed to fetch'))])
    await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'before',
      point: 1,
      photo: jpeg(),
    })
    await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'before',
      point: 2,
      photo: jpeg(),
    })
    expect((await flushPhotos(api, ME)).stopped).toBe(true)
    expect(api.uploadPhoto).toHaveBeenCalledTimes(1)
    expect(waitingPhotos(await queuedPhotos(ME))).toHaveLength(2)
  })

  it.each([401, 429, 500, 503])(
    'keeps everything waiting while the API answers %i, which is "not now"',
    async (status) => {
      const api = uploads([async () => Promise.reject(new ApiError(status, 'Not now'))])
      await queuePhoto({
        userId: ME,
        claimId: 'c',
        phase: 'before',
        point: 1,
        photo: jpeg(),
      })
      expect((await flushPhotos(api, ME)).stopped).toBe(true)
      expect(waitingPhotos(await queuedPhotos(ME))).toHaveLength(1)
    },
  )

  it('keeps every photo of a claim that closed while the phone had no signal, and sends no more of them', async () => {
    // The third pass's P1: a volunteer works on day 14 with no signal, finds
    // signal on day 15, the claim has run out, and a 409 deleted both their
    // after photos.
    const released = new ApiError(
      409,
      'This claim is released, so that cannot be done now',
    )
    const api = uploads([async () => Promise.reject(released), async () => ({})])
    await queuePhoto({
      userId: ME,
      claimId: 'ran-out',
      phase: 'after',
      point: 1,
      photo: jpeg(),
    })
    await queuePhoto({
      userId: ME,
      claimId: 'ran-out',
      phase: 'after',
      point: 2,
      photo: jpeg(),
    })
    await queuePhoto({
      userId: ME,
      claimId: 'still-open',
      phase: 'extra',
      point: null,
      photo: jpeg(),
    })
    const result = await flushPhotos(api, ME)

    expect(result.sent).toBe(1)
    expect(result.refused.map((p) => p.refused?.reason)).toEqual([
      released.message,
      released.message,
    ])
    // One upload for the closed claim, not two: the second would get the same answer.
    expect(api.uploadPhoto).toHaveBeenCalledTimes(2)
    const kept = await queuedPhotos(ME, 'ran-out')
    expect(kept).toHaveLength(2)
    expect(refusedPhotos(kept)).toHaveLength(2)
  })

  it("keeps a photo refused on its own account (415) and carries on with the claim's others", async () => {
    const api = uploads([
      async () =>
        Promise.reject(new ApiError(415, 'That file is not a photo this app can read')),
      async () => ({}),
    ])
    await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'before',
      point: 1,
      photo: jpeg(),
    })
    await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'before',
      point: 2,
      photo: jpeg(),
    })
    const result = await flushPhotos(api, ME)
    expect(result.sent).toBe(1)
    expect(refusedPhotos(await queuedPhotos(ME)).map((p) => p.point)).toEqual([1])
  })

  it('a refused photo is not sent again until its owner says so, and goes only when they discard it', async () => {
    const api = uploads([async () => Promise.reject(new ApiError(403, 'Only the crew'))])
    await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'before',
      point: 1,
      photo: jpeg(),
    })
    await flushPhotos(api, ME)
    await flushPhotos(api, ME)
    expect(api.uploadPhoto).toHaveBeenCalledTimes(1)

    const [refused] = await queuedPhotos(ME)
    await retryPhoto(refused)
    expect(waitingPhotos(await queuedPhotos(ME))).toHaveLength(1)
    await discardPhoto((await queuedPhotos(ME))[0])
    expect(await queuedPhotos(ME)).toEqual([])
  })

  it('two sends asked for at once send a photo once', async () => {
    // The third pass's P2: the screen opening, the online event and "Send now"
    // each started a run, and two runs uploaded one queued extra twice.
    let calls = 0
    const api = {
      ...fakeApi(),
      uploadPhoto: async () => {
        calls += 1
        await new Promise((resolve) => setTimeout(resolve, 20))
        return {} as ClaimDetail
      },
    }
    await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'extra',
      point: null,
      photo: jpeg(),
    })
    const [a, b] = await Promise.all([
      flushPhotos(api, ME, 'c'),
      flushPhotos(api, ME, 'c'),
    ])
    expect(calls).toBe(1)
    expect(a.sent + b.sent).toBe(1)
  })

  it('a photo whose answer was lost is sent again under the same id, and the API keeps one copy', async () => {
    const api = fakeApi()
    const [claim] = await api.claimSites(['example-0004'])
    const real = api.uploadPhoto.bind(api)
    const lostAnswer = {
      ...api,
      uploadPhoto: async (...args: Parameters<StewardApi['uploadPhoto']>) => {
        await real(...args)
        throw new TypeError('Failed to fetch')
      },
    }
    await queuePhoto({
      userId: ME,
      claimId: claim.id,
      phase: 'extra',
      point: null,
      photo: jpeg(),
    })
    await flushPhotos(lostAnswer, ME)
    await flushPhotos(api, ME)
    expect((await api.claim(claim.id)).photos).toHaveLength(1)
    expect(await queuedPhotos(ME)).toEqual([])
  })
})

it('a photo sent straight away whose answer was lost keeps the id it was first sent under', async () => {
  // The photo may already be on the server: queued under a new id, it would
  // be stored a second time when the queue sends it.
  const api = fakeApi()
  const [claim] = await api.claimSites(['example-0004'])
  const id = newPhotoId()
  await api.uploadPhoto(claim.id, 'extra', null, jpeg(), { clientId: id })
  await queuePhoto({
    id,
    userId: ME,
    claimId: claim.id,
    phase: 'extra',
    point: null,
    photo: jpeg(),
  })
  await flushPhotos(api, ME)
  expect((await api.claim(claim.id)).photos).toHaveLength(1)
})

it('keeps a queued photo of a point someone photographed since, and Try again sends it over theirs', async () => {
  // The fourth pass's C: an older photo queued on one crew phone, delivered
  // after a newer one from another, replaced the newer.
  const api = fakeApi()
  const [claim] = await api.claimSites(['example-0004'])
  await queuePhoto({
    userId: ME,
    claimId: claim.id,
    phase: 'after',
    point: 1,
    replaces: 'nothing',
    photo: jpeg(),
  })
  const theirs = (await api.uploadPhoto(claim.id, 'after', 1, jpeg())).photos[0].id

  const result = await flushPhotos(api, ME)
  expect(result.refused.map((p) => p.refused?.status)).toEqual([412])
  expect((await api.claim(claim.id)).photos.map((p) => p.id)).toEqual([theirs])

  await retryPhoto((await queuedPhotos(ME))[0])
  expect((await flushPhotos(api, ME)).sent).toBe(1)
  expect((await api.claim(claim.id)).photos.map((p) => p.id)).not.toEqual([theirs])
})

describe('one slot, one photo', () => {
  it('a newer photo of a before or after slot replaces the older one still waiting', async () => {
    await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'after',
      point: 1,
      photo: jpeg(),
    })
    const newer = await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'after',
      point: 1,
      photo: jpeg(),
    })
    expect((await queuedPhotos(ME)).map((p) => p.id)).toEqual([newer.id])
  })

  it('extras are never replaced, and refused photos never dropped', async () => {
    const api = uploads([async () => Promise.reject(new ApiError(415, 'Not a photo'))])
    await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'after',
      point: 1,
      photo: jpeg(),
    })
    await flushPhotos(api, ME)
    await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'after',
      point: 1,
      photo: jpeg(),
    })
    await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'extra',
      point: null,
      photo: jpeg(),
    })
    await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'extra',
      point: null,
      photo: jpeg(),
    })
    const kept = await queuedPhotos(ME)
    expect(refusedPhotos(kept)).toHaveLength(1)
    expect(waitingPhotos(kept).map((p) => p.phase)).toEqual(['after', 'extra', 'extra'])
  })

  it('a photo of the slot sent straight away leaves no older one waiting behind it', async () => {
    await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'before',
      point: 2,
      photo: jpeg(),
    })
    await dropWaiting(ME, 'c', 'before', 2)
    expect(await queuedPhotos(ME)).toEqual([])
  })
})

describe('one account per phone at a time', () => {
  it("the next account to sign in neither sees nor sends the last one's photos", async () => {
    // The third pass's P3: a session that ended without a sign-out left the
    // queue to the next account, whose send got 403 and deleted the photos.
    await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'before',
      point: 1,
      photo: jpeg(),
    })
    const api = uploads([])
    expect(await queuedPhotos(NEXT_PERSON)).toEqual([])
    expect((await flushPhotos(api, NEXT_PERSON)).sent).toBe(0)
    expect(api.uploadPhoto).not.toHaveBeenCalled()
    expect(await queuedPhotos(ME)).toHaveLength(1)
  })

  it("signing out forgets that account's claims and photos, and nobody else's", async () => {
    await saveClaim(ME, crewClaim('claim-1'))
    await queuePhoto({
      userId: ME,
      claimId: 'claim-1',
      phase: 'extra',
      point: null,
      photo: jpeg(),
    })
    await queuePhoto({
      userId: NEXT_PERSON,
      claimId: 'claim-2',
      phase: 'extra',
      point: null,
      photo: jpeg(),
    })
    await clearOffline(ME)
    expect(await savedClaim(ME, 'claim-1')).toBeNull()
    expect(await queuedPhotos(ME)).toEqual([])
    expect(await queuedPhotos(NEXT_PERSON)).toHaveLength(1)
  })
})

it('asks the browser to keep its storage once there is a photo worth keeping', async () => {
  // The third pass's P6: without it, Safari clears a site's storage after
  // seven days without a visit, and any browser may under storage pressure.
  const persist = vi.fn(async () => true)
  vi.stubGlobal('navigator', { ...navigator, storage: { persist } })
  try {
    await queuePhoto({
      userId: ME,
      claimId: 'c',
      phase: 'extra',
      point: null,
      photo: jpeg(),
    })
    expect(persist).toHaveBeenCalled()
  } finally {
    vi.unstubAllGlobals()
  }
})
