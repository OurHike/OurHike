/**
 * A short, stable tag for an account, from its email: enough to tell two
 * accounts on one phone apart, and kept on that phone only (#1902). Not a
 * secret and not an identifier anybody else sees - the email it is made from
 * is already in the sign-in session on the same phone. cyrb53, a 53-bit
 * string hash.
 *
 * Its own module, rather than lib/usageEvents.ts where it is used, because
 * App computes it on every render and the usage registry is loaded behind
 * `import()` (features/LAUNCH_BUDGET.md §3): this is the one piece of usage
 * measurement the first frame has to carry.
 */
export function accountTag(email: string): string {
  const text = email.trim().toLowerCase()
  let h1 = 0xdeadbeef
  let h2 = 0x41c6ce57
  for (let i = 0; i < text.length; i += 1) {
    const code = text.charCodeAt(i)
    h1 = Math.imul(h1 ^ code, 2654435761)
    h2 = Math.imul(h2 ^ code, 1597334677)
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909)
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909)
  return (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(36)
}
