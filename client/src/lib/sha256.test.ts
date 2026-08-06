import { describe, it, expect } from 'vitest'
import { createHash } from 'node:crypto'
import { Sha256, sha256Hex } from './sha256'

// A vendored hash is only worth what its tests are worth: a transcription
// error here does not crash, it rejects good archives on a mountain or
// accepts spliced ones. So this file pins the implementation two ways -
// against the published FIPS 180-4 vectors, and against Node's own SHA-256
// over inputs shaped like the ones the download actually produces (odd chunk
// boundaries, multi-megabyte lengths, resumed state).

/** The reference, for the cases no published vector covers. */
function reference(data: Uint8Array): string {
  return createHash('sha256').update(data).digest('hex')
}

const ascii = (text: string) => new TextEncoder().encode(text)

describe('sha256Hex', () => {
  it('matches the published vectors', () => {
    // FIPS 180-4 §B.1-B.2 and the empty-message value.
    expect(sha256Hex(ascii(''))).toBe(
      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    )
    expect(sha256Hex(ascii('abc'))).toBe(
      'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
    )
    expect(
      sha256Hex(ascii('abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq')),
    ).toBe('248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1')
  })

  it('pads correctly at every length around a block boundary', () => {
    // The length field needs a block of its own when fewer than eight bytes
    // remain, and getting that boundary wrong produces a hash that is right
    // for most inputs and wrong for a few - the worst kind of wrong.
    for (let length = 0; length <= 130; length++) {
      const data = Uint8Array.from({ length }, (_, i) => (i * 31) % 256)
      expect(sha256Hex(data), `length ${length}`).toBe(reference(data))
    }
  })

  it('agrees with the reference over megabytes fed as many chunks', () => {
    const chunk = Uint8Array.from({ length: 1 << 20 }, (_, i) => (i * 7) % 256)
    const hash = new Sha256()
    const node = createHash('sha256')
    for (let i = 0; i < 4; i++) {
      hash.update(chunk)
      node.update(chunk)
    }
    expect(hash.digest()).toBe(node.digest('hex'))
  })

  it('carries the length into its high word past 2^32 bits', () => {
    // The padded length is 64 bits, and JS bitwise operators are 32: writing
    // the high word as `bitLength >>> 32` yields `bitLength` itself, so every
    // archive from 512 MB up would be padded with the wrong length - and the
    // corridor's Standard and Fine tiers (314 MB / 1.18 GB) straddle exactly
    // that line.
    //
    // Tested by construction rather than by hashing 512 MB, which would cost
    // more seconds than the whole suite: two folds identical but for 2^29
    // bytes of length must digest differently, and under the 32-bit bug they
    // digest the same, because the shift discards precisely that difference.
    const base = new Sha256().update(ascii('abc')).toState()
    const shorter = Sha256.fromState({ ...base, byteLength: 1 << 20 })
    const longer = Sha256.fromState({ ...base, byteLength: (1 << 20) + 0x20000000 })

    expect(shorter.digest()).not.toBe(longer.digest())
  })
})

describe('chunking', () => {
  const message = Uint8Array.from({ length: 1000 }, (_, i) => (i * 17) % 256)

  it('is independent of where the chunks fall', () => {
    const whole = sha256Hex(message)

    for (const size of [1, 7, 63, 64, 65, 127, 128, 999]) {
      const hash = new Sha256()
      for (let at = 0; at < message.length; at += size) {
        hash.update(message.subarray(at, at + size))
      }
      expect(hash.digest(), `chunks of ${size}`).toBe(whole)
    }
  })

  it('hashes out of a chunk that does not start at its buffer origin', () => {
    // The read loop hands over views into a larger buffer, which a
    // Uint32Array view over the same bytes could not always address.
    const padded = new Uint8Array(message.length + 3)
    padded.set(message, 3)
    expect(sha256Hex(padded.subarray(3))).toBe(sha256Hex(message))
  })
})

describe('suspend and resume', () => {
  const message = Uint8Array.from({ length: 500 }, (_, i) => (i * 11) % 256)

  it('resumes to the same digest as an uninterrupted fold', () => {
    // Every split, not a chosen one: the interesting cases are the ones where
    // the suspension lands mid-block, and there is no reason to guess which.
    for (const at of [0, 1, 63, 64, 65, 200, 499, 500]) {
      const first = new Sha256().update(message.subarray(0, at))
      const resumed = Sha256.fromState(structuredClone(first.toState()))
      resumed.update(message.subarray(at))
      expect(resumed.digest(), `suspended at ${at}`).toBe(sha256Hex(message))
    }
  })

  it('reports how much it has consumed, so a resume knows what it still owes', () => {
    const hash = new Sha256().update(message.subarray(0, 300))
    expect(hash.bytesHashed).toBe(300)
    expect(Sha256.fromState(hash.toState()).bytesHashed).toBe(300)
  })

  it('hands out a state later updates cannot mutate', () => {
    // The state goes into IndexedDB while the download keeps running. If the
    // snapshot aliased the live buffer, the record written at 300 bytes would
    // describe whatever the fold looked like by the time it was serialised.
    const hash = new Sha256().update(message.subarray(0, 300))
    const snapshot = hash.toState()
    hash.update(message.subarray(300))

    expect(snapshot.byteLength).toBe(300)
    expect(Sha256.fromState(snapshot).digest()).toBe(sha256Hex(message.subarray(0, 300)))
  })

  it('survives the structured clone that storing it performs', () => {
    const hash = new Sha256().update(message.subarray(0, 137))
    const cloned = Sha256.fromState(structuredClone(hash.toState()))
    cloned.update(message.subarray(137))
    expect(cloned.digest()).toBe(sha256Hex(message))
  })
})

describe('digest', () => {
  it('does not end the stream', () => {
    // Callers record progress mid-download. A destructive digest would make
    // that a trap rather than an observation.
    const hash = new Sha256().update(ascii('abc'))
    expect(hash.digest()).toBe(sha256Hex(ascii('abc')))
    expect(hash.digest()).toBe(sha256Hex(ascii('abc')))
    hash.update(ascii('def'))
    expect(hash.digest()).toBe(sha256Hex(ascii('abcdef')))
  })
})
