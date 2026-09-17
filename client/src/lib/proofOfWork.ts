/**
 * The work a browser does before the backend will read a club's website.
 *
 * `backend/app/core/challenge.py` issues the challenge and checks the answer;
 * this is the other half. A hiker types an organization's address, this finds
 * a number whose SHA-256 opens with enough zero bits, and the backend refuses
 * the fetch without one.
 *
 * WHY THIS EXISTS AT ALL is in the backend module's header: signing in bounds
 * who can ask, the assist budget bounds what it costs, and neither bounds how
 * fast one signed-in account can drive a fetcher pointed at other people's
 * websites. A proof of work is the third bound, and it was chosen over a
 * CAPTCHA because a CAPTCHA puts a third party in front of every hiker who
 * nominates a club.
 *
 * IT HASHES SYNCHRONOUSLY, AND THAT IS THE WHOLE PERFORMANCE STORY. Measured
 * 2026-09-17: `await crypto.subtle.digest('SHA-256', ...)` once per candidate
 * costs about 44 microseconds, nearly all of it the `await`, which put a
 * 16-bit challenge at a 2.9 second median. The same search over `sha256Hex`
 * lands at 78 ms. A proof of work built on an awaited digest is thirty times
 * more expensive than it looks, and only for the honest hiker.
 *
 * IT REUSES `sha256.ts` RATHER THAN CARRYING ITS OWN. That file is here for
 * the archive download (#197), is pinned by the NIST vectors in its test file,
 * and is the kind of code that fails quietly when transcribed a second time.
 * Reuse cost something and was worth paying for properly rather than
 * abandoning: the first version called `sha256Hex` per candidate and measured
 * a 3.1 second median at difficulty 18, because `digest()` allocates two more
 * folds and a 64-character string every call - the right trade for one 1.18 GB
 * archive and the wrong one for a quarter of a million eleven-byte messages.
 * `reset()` and `finishInto()` were added to that file rather than a second
 * SHA-256 being written here, so there is still exactly one implementation of
 * the compression and the NIST vectors still cover it.
 *
 * AND IT YIELDS. A tight loop of a quarter of a million hashes blocks the main
 * thread for around half a second at difficulty 18 - long enough to freeze a
 * spinner, drop a tap and look broken on the slow attempt rather than the
 * median one. `CHUNK` attempts between yields is what keeps the page alive.
 */

import { Sha256 } from './sha256'

/** What the backend issued. Every field is public; the signature is what makes
 *  them unforgeable, and none of it is secret. */
export interface Challenge {
  nonce: string
  difficulty: number
  /** Unix seconds. Carried back verbatim - it is inside the signature. */
  expires_at: number
  signature: string
}

/** How many candidates to try between yields to the event loop.
 *
 *  @unvalidated. Five thousand hashes is roughly 3 ms of work at the speed
 *  measured above, which is inside one animation frame with room to spare -
 *  reasoned from the frame budget rather than measured on a phone. What would
 *  settle it: the longest frame this produces on real hardware, which is the
 *  same unanswered question `DEFAULT_DIFFICULTY` carries on the backend. */
const CHUNK = 5000

const encoder = new TextEncoder()

// ONE FOLD, ONE OUTPUT ARRAY AND ONE BYTE BUFFER FOR THE WHOLE MODULE, reused
// across every candidate. This is safe because nothing between `reset()` and
// `finishInto()` awaits, so no second caller can interleave on a single
// -threaded event loop - and it is the difference between a solve that
// allocates four objects per attempt and one that allocates none.
const fold = new Sha256()
const digest = new Uint32Array(8)
// A nonce is 24 characters and an answer at most eight digits, so 256 is
// roughly six times what is needed. `encodeInto` truncates silently rather
// than growing, which would produce a client that hashes a different message
// from the server and fails every time with nothing on screen to say why - so
// the truncation is checked rather than assumed away.
const bytes = new Uint8Array(256)

function digestOf(nonce: string, answer: string): Uint32Array {
  const message = `${nonce}:${answer}`
  const { read, written } = encoder.encodeInto(message, bytes)
  if (read < message.length) {
    throw new Error('That challenge is longer than this solver was built for.')
  }
  fold.reset().update(bytes.subarray(0, written))
  return fold.finishInto(digest)
}

/** How many zero bits a digest opens with, counted over its words.
 *
 *  The hex form below is what the tests read and what a person can check by
 *  eye; this is what the search actually runs, and they are asserted to agree. */
export function leadingZeroBitsOfWords(words: Uint32Array): number {
  let bits = 0
  for (const word of words) {
    if (word === 0) {
      bits += 32
      continue
    }
    bits += Math.clz32(word)
    break
  }
  return bits
}

/** How many zero bits a hex digest opens with.
 *
 *  Bits rather than hex characters, because the backend counts bits: reading
 *  four at a time would make every difficulty a multiple of four and silently
 *  round a 18-bit challenge down to 16. */
export function leadingZeroBits(hex: string): number {
  let bits = 0
  for (const character of hex) {
    const nibble = parseInt(character, 16)
    if (Number.isNaN(nibble)) return bits
    if (nibble === 0) {
      bits += 4
      continue
    }
    // clz32 counts across 32 bits, so 28 of them are the padding above the
    // nibble: clz32(0x1) is 31 and the nibble 0001 has three leading zeros.
    bits += Math.clz32(nibble) - 28
    break
  }
  return bits
}

/** Whether this answer solves this challenge - the backend's check, locally.
 *
 *  Exported so a caller can verify before posting rather than discovering it
 *  in a 409, and so the tests can assert the two halves agree. */
export function solves(challenge: Challenge, answer: string): boolean {
  return leadingZeroBitsOfWords(digestOf(challenge.nonce, answer)) >= challenge.difficulty
}

export interface SolveOptions {
  /** Called with the attempt count every `CHUNK` tries, for a progress bar
   *  that says something true rather than spinning. */
  onProgress?: (attempts: number) => void
  /** Aborts the search. A hiker who changes the address mid-solve should not
   *  wait for the old one to finish, and a component unmounting should not
   *  leave a loop running. */
  signal?: AbortSignal
}

/** Find an answer, yielding to the event loop as it goes.
 *
 *  Rejects on abort rather than resolving with nothing, so a caller cannot
 *  mistake "you cancelled" for "there was no answer" - there is always an
 *  answer, it is only ever a question of how long. */
export async function solve(challenge: Challenge, options: SolveOptions = {}): Promise<string> {
  const { onProgress, signal } = options
  if (!Number.isInteger(challenge.difficulty) || challenge.difficulty < 1) {
    throw new Error('That challenge does not say how much work to do.')
  }

  for (let attempt = 0; ; attempt++) {
    if (signal?.aborted) throw new DOMException('Solving was cancelled', 'AbortError')
    const answer = String(attempt)
    if (solves(challenge, answer)) {
      onProgress?.(attempt + 1)
      return answer
    }
    if (attempt > 0 && attempt % CHUNK === 0) {
      onProgress?.(attempt)
      await new Promise((resolve) => setTimeout(resolve, 0))
    }
  }
}
