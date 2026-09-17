/**
 * The browser half of the nominate challenge, and that it agrees with the
 * server half.
 *
 * The property worth testing is not "it finds a number" - it always finds a
 * number. It is that THIS finds numbers the backend accepts, computed the same
 * way, counted in the same units. A client counting leading zero HEX
 * CHARACTERS instead of BITS would pass every test that only checks it
 * terminates, and would then solve a 16-bit challenge when asked for 18 and be
 * refused by a server that never explains why.
 */

import { describe, expect, it, vi } from 'vitest'

import { Sha256, sha256Hex } from './sha256'
import {
  leadingZeroBits,
  leadingZeroBitsOfWords,
  solve,
  solves,
  type Challenge,
} from './proofOfWork'

const encoder = new TextEncoder()

function challenge(difficulty: number, nonce = 'a-nonce'): Challenge {
  return { nonce, difficulty, expires_at: 2_000_000_000, signature: 'not-checked-here' }
}

describe('counting the work', () => {
  it.each([
    ['ff', 0],
    ['7f', 1],
    ['1f', 3],
    ['0f', 4],
    ['00f', 8],
    ['001', 11],
    ['000f', 12],
    ['0000f', 16],
  ])('reads %s as %i leading zero bits', (hex, expected) => {
    expect(leadingZeroBits(hex)).toBe(expected)
  })

  it('counts bits and not hex characters', () => {
    // 0x1 is one hex character and three zero BITS. A counter that worked in
    // characters would say 0 here and would accept every difficulty below 4.
    expect(leadingZeroBits('1abc')).toBe(3)
    expect(leadingZeroBits('0abc')).toBe(4)
  })

  it('an all-zero digest is all zero bits rather than an early exit', () => {
    expect(leadingZeroBits('0000')).toBe(16)
  })
})

describe('solving', () => {
  it('finds an answer the same check accepts', async () => {
    const work = challenge(10)
    const answer = await solve(work)
    expect(solves(work, answer)).toBe(true)
  })

  it('hashes the nonce and the answer the way the backend does', async () => {
    // The format is `${nonce}:${answer}` on both sides. A client that joined
    // them any other way would solve its own puzzle and fail the server's,
    // with nothing on screen to say which half was wrong.
    const work = challenge(8, 'joined-how')
    const answer = await solve(work)
    const digest = sha256Hex(encoder.encode(`joined-how:${answer}`))
    expect(leadingZeroBits(digest)).toBeGreaterThanOrEqual(8)
  })

  it('a harder challenge is not solved by an easier answer', async () => {
    const easy = challenge(4, 'shared-nonce')
    const answer = await solve(easy)
    const hard = challenge(20, 'shared-nonce')
    // Not impossible, just overwhelmingly unlikely - and if it ever were, the
    // assertion would be wrong rather than the code.
    expect(solves(hard, answer)).toBe(false)
  })

  it('reports progress rather than going quiet', async () => {
    const onProgress = vi.fn()
    await solve(challenge(12), { onProgress })
    expect(onProgress).toHaveBeenCalled()
  })

  it('yields, so a solve does not freeze the page', async () => {
    // Proved by something observable rather than by timing: a timer scheduled
    // before the solve runs DURING it, which cannot happen if the loop never
    // releases the thread. A tight loop would leave `ticked` false until the
    // solve had already returned.
    let ticked = false
    setTimeout(() => {
      ticked = true
    }, 0)
    await solve(challenge(16))
    expect(ticked).toBe(true)
  })

  it('stops when it is cancelled', async () => {
    const controller = new AbortController()
    controller.abort()
    await expect(solve(challenge(24), { signal: controller.signal })).rejects.toThrow(/cancelled/i)
  })

  it('refuses a challenge that does not say how much work to do', async () => {
    await expect(solve({ ...challenge(0) })).rejects.toThrow(/how much work/i)
  })
})

describe('the fast path agrees with the tested one', () => {
  it('counts the same bits over words as over hex', () => {
    // `leadingZeroBits` reads the hex a person can check by eye;
    // `leadingZeroBitsOfWords` is what the search runs a quarter of a million
    // times. They have to agree, and nothing else in the suite would notice if
    // they stopped - a solver counting one bit too few simply works harder.
    for (let attempt = 0; attempt < 400; attempt++) {
      const message = encoder.encode(`agreement:${attempt}`)
      const hex = sha256Hex(message)
      const words = new Sha256().update(message).finishInto(new Uint32Array(8))
      expect(leadingZeroBitsOfWords(words)).toBe(leadingZeroBits(hex))
    }
  })

  it('finishInto digests what digest() digests', () => {
    // The new path is pinned to the one the NIST vectors cover, rather than
    // being trusted because it was written carefully.
    for (const text of ['', 'abc', 'a'.repeat(55), 'a'.repeat(56), 'a'.repeat(64), 'a'.repeat(200)]) {
      const message = encoder.encode(text)
      const words = new Sha256().update(message).finishInto(new Uint32Array(8))
      const hex = [...words].map((word) => word.toString(16).padStart(8, '0')).join('')
      expect(hex).toBe(sha256Hex(message))
    }
  })

  it('a reset fold hashes as a fresh one does', () => {
    const reused = new Sha256()
    reused.update(encoder.encode('something else')).finishInto(new Uint32Array(8))
    const after = reused.reset().update(encoder.encode('abc')).finishInto(new Uint32Array(8))
    const fresh = new Sha256().update(encoder.encode('abc')).finishInto(new Uint32Array(8))
    expect([...after]).toEqual([...fresh])
  })
})
