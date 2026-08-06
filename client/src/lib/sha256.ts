// An incremental SHA-256, because the browser's own digest cannot be fed a
// stream (#197).
//
// `crypto.subtle.digest` is one call over one buffer: to hash a 1.18 GB
// archive with it, the whole archive has to exist in memory as one
// ArrayBuffer at once - which is precisely what archiveDownload.ts's
// append-only Blob avoids, and what a phone with a full camera roll cannot
// spare. That limitation is why the archive shipped unverified against its
// published hash, and it is a limitation of the API rather than of the
// algorithm: SHA-256 is defined as a fold over 64-byte blocks, so a
// stream-shaped implementation is the natural one and the all-at-once API is
// the odd shape.
//
// So: a small vendored implementation, ~2 KB of it, fed the same chunks the
// download's read loop already receives. Two properties beyond "it hashes"
// are load-bearing here:
//
//   resumable   `toState()` / `fromState()` round-trip the fold's entire
//               working memory - the eight chaining words, the bytes of a
//               block not yet complete, and the running length. That is what
//               lets a download interrupted at 900 MB carry its hash across
//               an app restart in the `:progress` record, rather than
//               re-reading 900 MB of Blob to catch up.
//   pure        `digest()` does not consume the accumulator. Padding is
//               applied to a copy, so asking "what would the hash be here"
//               mid-stream is free of consequence - which keeps the caller
//               from having to know that a digest is destructive.
//
// This file is deliberately dependency-free and self-contained. A hashing
// bug here does not fail loudly; it rejects good archives or accepts bad
// ones, so it is pinned by the NIST vectors in the test file rather than by
// trust in the transcription.

/** The fold's complete working memory - everything needed to carry a
 *  half-hashed stream across a restart. Structured-clone-safe on purpose:
 *  this goes into IndexedDB beside the partial bytes it describes. */
export interface Sha256State {
  /** The eight chaining words, as unsigned 32-bit values. */
  h: number[]
  /** Bytes of the current 64-byte block that have arrived so far. */
  buffered: Uint8Array
  /** Total bytes consumed - the padded length the digest commits to, and
   *  what tells a resume how much of the partial this state already covers. */
  byteLength: number
}

// FIPS 180-4 §4.2.2: the first 32 bits of the fractional parts of the cube
// roots of the first 64 primes.
const K = Uint32Array.from([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4,
  0xab1c5ed5, 0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe,
  0x9bdc06a7, 0xc19bf174, 0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f,
  0x4a7484aa, 0x5cb0a9dc, 0x76f988da, 0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
  0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967, 0x27b70a85, 0x2e1b2138, 0x4d2c6dfc,
  0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85, 0xa2bfe8a1, 0xa81a664b,
  0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070, 0x19a4c116,
  0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7,
  0xc67178f2,
])

// FIPS 180-4 §5.3.3: the fractional parts of the square roots of the first
// eight primes.
const INITIAL_H = Uint32Array.from([
  0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab,
  0x5be0cd19,
])

const BLOCK_BYTES = 64

const rotr = (x: number, n: number) => (x >>> n) | (x << (32 - n))

export class Sha256 {
  private h = Uint32Array.from(INITIAL_H)
  /** The current block, filled to `bufferedLength` and compressed at 64. */
  private buffer = new Uint8Array(BLOCK_BYTES)
  private bufferedLength = 0
  private byteLength = 0
  /** The message schedule, allocated once. A chunk of a 1.18 GB download is
   *  ~18 million blocks; allocating 64 words per block is 18 million garbage
   *  arrays for no reason. */
  private readonly w = new Uint32Array(64)

  /** Restores a fold suspended by `toState` - see the module comment. */
  static fromState(state: Sha256State): Sha256 {
    const hash = new Sha256()
    hash.h = Uint32Array.from(state.h)
    hash.buffer.set(state.buffered)
    hash.bufferedLength = state.buffered.length
    hash.byteLength = state.byteLength
    return hash
  }

  /** Feeds the next bytes of the message. Chunk boundaries do not affect the
   *  result: a message fed as one call and the same message fed byte by byte
   *  digest identically (asserted in the tests). */
  update(chunk: Uint8Array): this {
    this.byteLength += chunk.length
    let offset = 0

    // Top up a block left partly filled by the previous chunk. Only then can
    // the bulk loop below assume it starts on a block boundary.
    if (this.bufferedLength > 0) {
      const take = Math.min(BLOCK_BYTES - this.bufferedLength, chunk.length)
      this.buffer.set(chunk.subarray(0, take), this.bufferedLength)
      this.bufferedLength += take
      offset = take
      if (this.bufferedLength === BLOCK_BYTES) {
        this.compress(this.buffer, 0)
        this.bufferedLength = 0
      }
    }

    // Compressed straight out of the caller's chunk - no copy per block.
    while (offset + BLOCK_BYTES <= chunk.length) {
      this.compress(chunk, offset)
      offset += BLOCK_BYTES
    }

    if (offset < chunk.length) {
      this.buffer.set(chunk.subarray(offset), 0)
      this.bufferedLength = chunk.length - offset
    }

    return this
  }

  /** The digest of everything fed so far, lowercase hex.
   *
   *  Non-destructive: padding happens on a copy, so the accumulator can keep
   *  taking bytes afterwards. A digest that quietly ended the stream would be
   *  a trap for exactly the caller this exists for - one that wants to record
   *  progress and keep downloading. */
  digest(): string {
    const finishing = Sha256.fromState(this.toState())
    const bitLength = finishing.byteLength * 8

    // FIPS 180-4 §5.1.1: a 1 bit, then zeros, then the length as a 64-bit
    // big-endian integer - sized so this padding takes the message to a
    // multiple of 64 with the eight length bytes inside the final block. The
    // eight bytes need a block of their own when fewer than eight remain.
    const remainder = finishing.bufferedLength
    const padding = new Uint8Array(
      (remainder < BLOCK_BYTES - 8 ? BLOCK_BYTES : BLOCK_BYTES * 2) - remainder,
    )
    padding[0] = 0x80
    const lengthAt = padding.length - 8
    // Split rather than shifted: bitwise operators in JS are 32-bit, so
    // `bitLength >>> 32` is not the high word - it is `bitLength`. A 2^29-byte
    // archive (537 MB) is enough for that to matter, which is well inside the
    // range this hashes.
    const high = Math.floor(bitLength / 0x100000000)
    const low = bitLength >>> 0
    padding[lengthAt] = (high >>> 24) & 0xff
    padding[lengthAt + 1] = (high >>> 16) & 0xff
    padding[lengthAt + 2] = (high >>> 8) & 0xff
    padding[lengthAt + 3] = high & 0xff
    padding[lengthAt + 4] = (low >>> 24) & 0xff
    padding[lengthAt + 5] = (low >>> 16) & 0xff
    padding[lengthAt + 6] = (low >>> 8) & 0xff
    padding[lengthAt + 7] = low & 0xff

    finishing.update(padding)

    let hex = ''
    for (const word of finishing.h) hex += word.toString(16).padStart(8, '0')
    return hex
  }

  /** A snapshot that `fromState` can resume from. Copies out, so later
   *  updates cannot mutate a state already handed to storage. */
  toState(): Sha256State {
    return {
      h: Array.from(this.h),
      buffered: this.buffer.slice(0, this.bufferedLength),
      byteLength: this.byteLength,
    }
  }

  /** How many bytes this fold has consumed - what a resume compares against
   *  the held partial's size to know whether the state is caught up. */
  get bytesHashed(): number {
    return this.byteLength
  }

  private compress(data: Uint8Array, offset: number): void {
    const w = this.w

    // Big-endian, read byte by byte rather than through a DataView: `data` is
    // whatever the stream handed over, and a Uint8Array can start at any byte
    // offset in its buffer, which a Uint32Array view cannot.
    for (let i = 0; i < 16; i++) {
      const at = offset + i * 4
      w[i] =
        ((data[at] << 24) | (data[at + 1] << 16) | (data[at + 2] << 8) | data[at + 3]) >>>
        0
    }
    for (let i = 16; i < 64; i++) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3)
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10)
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0
    }

    let [a, b, c, d, e, f, g, h] = this.h

    for (let i = 0; i < 64; i++) {
      const S1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25)
      const ch = (e & f) ^ (~e & g)
      const temp1 = (h + S1 + ch + K[i] + w[i]) >>> 0
      const S0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22)
      const maj = (a & b) ^ (a & c) ^ (b & c)
      const temp2 = (S0 + maj) >>> 0

      h = g
      g = f
      f = e
      e = (d + temp1) >>> 0
      d = c
      c = b
      b = a
      a = (temp1 + temp2) >>> 0
    }

    this.h[0] = (this.h[0] + a) >>> 0
    this.h[1] = (this.h[1] + b) >>> 0
    this.h[2] = (this.h[2] + c) >>> 0
    this.h[3] = (this.h[3] + d) >>> 0
    this.h[4] = (this.h[4] + e) >>> 0
    this.h[5] = (this.h[5] + f) >>> 0
    this.h[6] = (this.h[6] + g) >>> 0
    this.h[7] = (this.h[7] + h) >>> 0
  }
}

/** One-shot convenience for callers holding the whole message already -
 *  tests, mostly. The streaming path is the reason this file exists. */
export function sha256Hex(data: Uint8Array): string {
  return new Sha256().update(data).digest()
}
