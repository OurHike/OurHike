// Which name a report is signed with, and what that reads as (#1563).
//
// A HIKER HAS TWO NAMES HERE AND ONE OF THEM IS NEW. The trail name is the
// identity this app shows other people - "never a hiker's real name by
// default" (features/IDENTITY_AND_PRIVACY.md), asked for once after the
// first contribution (screens/IdentitySetup.tsx) and carried on a report as
// nothing more than `reporter_type`, because the public list serves no name
// at all. The real name is the maintainer's addition of 2026-09-17: a choice
// a hiker can make for ONE report, to put their own name behind it so the
// club that follows up knows what to call them. It lives in the preferences
// as `real_name` so a second phone offers the same choice, and it reaches a
// report only as `signed_name` when the hiker picks it for that report.
//
// THE DEFAULT IS THE TRAIL NAME, ALWAYS. Nothing here changes what any other
// surface shows, and a hiker who never touches the control signs exactly as
// they did before this existed.

import type { ReportDraft } from './outbox'
import type { UserPreferences } from './userPreferences'

/** The two names a report can be signed with - the wire's `signed_name_kind`. */
export type SignedAs = NonNullable<ReportDraft['signed_name_kind']>

/** What the choice resolves to against what the hiker has told us. `name`
 *  is null when the chosen kind has no name set yet. */
export interface Signature {
  kind: SignedAs
  name: string | null
}

/** The names on offer, from the preferences. Trimmed, and empty is null:
 *  a name of spaces is not a name. */
export function namesOnOffer(
  preferences: Pick<UserPreferences, 'trail_name' | 'real_name'>,
): Record<SignedAs, string | null> {
  const clean = (value: string | null) => {
    const trimmed = value?.trim() ?? ''
    return trimmed === '' ? null : trimmed
  }
  return { trail: clean(preferences.trail_name), real: clean(preferences.real_name) }
}

export function reportSignature(
  preferences: Pick<UserPreferences, 'trail_name' | 'real_name'>,
  signedAs: SignedAs,
): Signature {
  return { kind: signedAs, name: namesOnOffer(preferences)[signedAs] }
}

/**
 * What the wire carries for a signature: the name and its kind together, or
 * neither. A kind without a name is a claim about nothing, and the server
 * drops it anyway (app/routers/reports.py); sending it would only make the
 * two ends disagree about what an unsigned report looks like.
 */
export function signatureFields(
  signature: Signature,
): Pick<ReportDraft, 'signed_name' | 'signed_name_kind'> {
  if (signature.name === null) return {}
  return { signed_name: signature.name, signed_name_kind: signature.kind }
}

/** "trail name" / "real name" - the kind as a hiker reads it. */
export function signedAsWords(kind: SignedAs): string {
  return kind === 'trail' ? 'trail name' : 'real name'
}

/**
 * "Switchback (trail name)", or "not set (trail name)" when the chosen name
 * is missing - said rather than hidden, because a report going out unsigned
 * is a thing the hiker should be able to see before it goes.
 */
export function signatureWords(signature: Signature): string {
  return `${signature.name ?? 'not set'} (${signedAsWords(signature.kind)})`
}
